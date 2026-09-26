"""Bind public compatibility entry points to one session, including direct memory IO."""

from functools import wraps
from contextvars import ContextVar
from war3_game_session import session_scope
from war3_capabilities import CapabilitySet

_ACTIVE_TRAINER = ContextVar("active_war3_trainer", default=None)
# These wrappers only construct a native protocol. Their own OperationSpec gates dependencies.
NATIVE_ONLY = frozenset(
    {
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
            if not function.__name__.startswith(
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
            ):
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

    # Preserve the old owner's cleanup evidence. Never transplant its pointers.
    old = getattr(self, "_retired_game_sessions", [])
    old.append(session)
    self._retired_game_sessions = old
    session = GameSession(self.pid, self.hwnd, catalog=session.catalog)
    session.on_invalidate(lambda reason: invalidate_trainer(self, reason))
    self._game_session = session
    invalidate_trainer(self, "explicit process/window rebind")
    return session


def bind_trainer(cls):
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
    "_classic_object_registry": lambda: None,
    "_classic_thread_context": lambda: None,
    "_last_classic_mode": lambda: None,
    "_classic_resource_cache": lambda: None,
}


def invalidate_trainer(trainer, reason):
    for name, factory in CACHE_DEFAULTS.items():
        if hasattr(trainer, name):
            setattr(trainer, name, factory())
