"""Bind public compatibility entry points to one session, including direct memory IO."""

from functools import wraps
from functools import lru_cache
from inspect import signature
from contextvars import ContextVar
from war3_game_session import session_scope
from war3_capabilities import CapabilitySet

_ACTIVE_TRAINER = ContextVar("active_war3_trainer", default=None)


def uses_indexed_backend(host, default=False):
    """The managed session chooses the backend; legacy flags are ABI compatibility only."""
    if getattr(host, "_game_session", None) is not None:
        return True
    return bool(getattr(host, "_native_selection_unavailable", default))
# These wrappers only construct a native protocol. Their own OperationSpec gates dependencies.
NATIVE_ONLY = frozenset(
    {
        "toggle_game_speed",
        "toggle_native_game_speed",
        "hero_progress_24268",
        "hero_attributes_24268",
        "attack_speed_24268",
        "ability_batch_24268",
        "ability_field_batch_24268",
        "item_batch_24268",
        "item_field_batch_24268",
        "world_batch_24268",
        "bulk_batch_24268",
        "effect_batch_24268",
        "world_effect_batch_24268",
        "spawn_unit_24268",
        "mouse_world_point_24268",
        "mouse_screen_point_24268",
        "camera_snapshot_24268",
        "terrain_height_24268",
        "map_bounds_24268",
        "clone_batch_24268",
        "unit_action_batch_24268",
        "position_batch_24268",
    }
)
WINDOW_ONLY = frozenset({"close", "refresh_window", "focus", "send_cheat"})
READ_ONLY = frozenset({"extension_snapshot_24268", "extension_loadout_names_24268",
                       "selected_unit_summaries", "trainer_for_read_source",
                       "stat_details_24268", "prewarm_selected_unit_cache",
                       "prewarm_elephant_functions", "list_resource_caches",
                       "talent_state_24268", "prepare_extension_item_destruction_24268",
                       "save_extension_loadout_24268", "save_extension_loadouts_for_selected_24268"})

QUERY_OPERATIONS = {
    'hero_progress_24268':'hero','hero_attributes_24268':'hero_attributes',
    'attack_speed_24268':'attack_speed','ability_batch_24268':'ability',
    'ability_field_batch_24268':'ability_field','item_batch_24268':'item',
    'item_field_batch_24268':'item_field','mouse_world_point_24268':'mouse',
    'mouse_screen_point_24268':'screen_mouse','camera_snapshot_24268':'camera',
    'terrain_height_24268':'terrain','map_bounds_24268':'map_bounds',
}

@lru_cache(maxsize=None)
def _entry_signature(function):
    return signature(function)

def _native_query_entry(function, host, args, kwargs):
    kind=QUERY_OPERATIONS.get(function.__name__)
    if kind is None:return False
    from war3_operations import is_read_query
    bound=_entry_signature(function).bind(host,*args,**kwargs)
    bound.apply_defaults()
    return is_read_query(kind,bound.arguments)


def session_entry(function):
    @wraps(function)
    def call(self, *args, **kwargs):
        session = getattr(self, "_game_session", None)
        if session is None or _ACTIVE_TRAINER.get() is self:
            return function(self, *args, **kwargs)
        if (session.pid, session.hwnd) != (self.pid, self.hwnd):
            if session.pid == self.pid:
                session.hwnd = self.hwnd
                session.invalidate("window changed within the original process")
            else:
                session = rebind_process(self, session)
        with session.lock:
            with self._session_memory_factory(self.pid) as memory:
                registry, context, mode = session.prepare(memory)
            if function.__name__ not in NATIVE_ONLY:
                CapabilitySet(session.profile).require("basic_fields")
            if (function.__name__ not in READ_ONLY
                    and not _native_query_entry(function,self,args,kwargs)
                    and not function.__name__.startswith(
                (
                    "read_",
                    "get_",
                    "locate_",
                    "query_",
                    "inspect_",
                    "find_",
                    "refresh_",
                    "enumerate_",
                )
            )):
                session.require_write()
            self._classic_object_registry = registry
            self._classic_thread_context = context
            token = _ACTIVE_TRAINER.set(self)
            try:
                with session_scope(session):
                    return function(self, *args, **kwargs)
            except Exception as exc:
                exc.session_report = session.snapshot()
                raise
            finally:
                _ACTIVE_TRAINER.reset(token)

    return call


def rebind_process(self, session):
    from war3_game_session import GameSession
    from war3_adapter_state import attach_adapter_cache

    # Preserve the old owner's cleanup evidence. Never transplant its pointers.
    old = getattr(self, "_retired_game_sessions", [])
    old.append(session)
    self._retired_game_sessions = old
    session = GameSession(self.pid, self.hwnd, catalog=session.catalog)
    session.on_invalidate(lambda reason: invalidate_trainer(self, reason))
    self._game_session = session
    attach_adapter_cache(self, session, CACHE_DEFAULTS)
    invalidate_trainer(self, "explicit process/window rebind")
    return session


def bind_trainer(cls):
    from war3_adapter_state import SessionCacheField
    for name in CACHE_DEFAULTS:
        setattr(cls, name, SessionCacheField(name))
    methods = {}
    for base in reversed(cls.__mro__[:-1]):
        methods.update(vars(base))
    for name, function in tuple(methods.items()):
        if (
            not name.startswith("_")
            and name not in WINDOW_ONLY
            and callable(function)
            and hasattr(function, "__code__")
        ):
            setattr(cls, name, session_entry(function))
    return cls


CACHE_DEFAULTS = {
    "_selection_player_candidates": list,
    "_unit_component_layout_confirmed": lambda: False,
    "_native_hero_int_set_address": int,
    "_native_hero_int_get_address": int,
    "_jass_unit_resolver_address": int,
    "_buff_data_constructor_address": int,
    "_last_win10_jass_unit_handle": int,
    "_last_win10_jass_player_handle": int,
    "_last_win10_jass_handle_id": int,
    "_elephant_selection_override": lambda: None,
    "_unit_owner_index": dict,
    "_unit_object_index_cache": lambda: None,
    "_item_object_cache": dict,
    "_native_handlers": dict,
    "_native_table_region": lambda: None,
    "_native_table_regions": list,
    "_native_table_blob": lambda: None,
    "_ability_runtime_templates": dict,
    "_ability_instance_by_data": dict,
    "_selected_components_cache": dict,
    "_component_index_cache": lambda: None,
    "_component_index_misses": set,
    "_ability_instances_cache": dict,
    "_resource_candidates_by_start": dict,
    "_last_selected_summaries": tuple,
    "_last_persistent_native_snapshots": tuple,
    "_classic_selection_layout": lambda: None,
    "_classic_selection_cache": tuple,
    "_last_selection_candidate_failure": dict,
    "_classic_object_registry": lambda: None,
    "_classic_thread_context": lambda: None,
    "_last_classic_mode": lambda: None,
    "_classic_resource_cache": lambda: None,
}


def invalidate_trainer(trainer, reason):
    for name, factory in CACHE_DEFAULTS.items():
        if hasattr(trainer, name):
            setattr(trainer, name, factory())
