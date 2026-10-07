"""Process/map ownership, typed identities and no-replay execution evidence."""

from __future__ import annotations
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, asdict
import ctypes, struct, threading
from war3_game_profile import (
    profile_scope,
    ProfileCatalog,
)


class SessionError(RuntimeError):
    pass


_ACTIVE_SESSION = ContextVar("war3_active_session", default=None)
_ACTIVE_EPOCH = ContextVar("war3_active_epoch", default=None)


@contextmanager
def session_scope(session):
    token = _ACTIVE_SESSION.set(session)
    epoch_token = _ACTIVE_EPOCH.set((session, session.epoch))
    try:
        with profile_scope(session.profile):
            yield session
    finally:
        _ACTIVE_EPOCH.reset(epoch_token)
        _ACTIVE_SESSION.reset(token)


def verify_opened_process(memory):
    session = _ACTIVE_SESSION.get()
    if session is None:
        return
    identity = session.identity
    if (
        identity is None
        or memory.pid != identity.pid
        or session.creation_reader(memory) != identity.created
    ):
        session.invalidate("process changed between verification and access")
        raise SessionError("Process identity changed; no access to replacement process")


@dataclass(frozen=True)
class NativeHandle:
    value: int

    def __post_init__(self):
        if type(self.value) is not int or not 0 < self.value <= 0xFFFFFFFFFFFFFFFF:
            raise ValueError("Invalid native handle")


@dataclass(frozen=True)
class FullHandle:
    value: int

    def __post_init__(self):
        if type(self.value) is not int or not 0 <= self.value <= 0xFFFFFFFFFFFFFFFF:
            raise ValueError("Invalid full handle")


@dataclass(frozen=True)
class ObjectAddress:
    value: int

    def __post_init__(self):
        if (
            type(self.value) is not int
            or not 0x10000 <= self.value < 0x800000000000
            or self.value % 8
        ):
            raise ValueError("Invalid object address")


@dataclass(frozen=True)
class SessionIdentity:
    pid: int
    created: int
    module_base: int
    fingerprint: tuple
    profile_digest: str


@dataclass(frozen=True)
class UnitRef:
    session: SessionIdentity
    epoch: int
    handle: FullHandle
    address: ObjectAddress
    rawcode: int


@dataclass(frozen=True)
class ItemRef(UnitRef):
    pass


@dataclass
class OperationEvidence:
    delivered: bool = False
    readback_verified: bool = False
    effect_verified: bool = False
    cleanup_complete: bool = False
    uncertain: bool = False
    callback_exited: bool = False


def process_creation(memory):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    fn = kernel.GetProcessTimes
    fn.argtypes = (ctypes.c_void_p,) + (ctypes.POINTER(ctypes.c_ulonglong),) * 4
    fn.restype = ctypes.c_int
    values = [ctypes.c_ulonglong() for _ in range(4)]
    if not fn(memory.handle, *(ctypes.byref(v) for v in values)):
        raise ctypes.WinError(ctypes.get_last_error())
    return values[0].value


def read_fingerprint(memory, base):
    header = memory.read(base, 64)
    if len(header) != 64 or header[:2] != b"MZ":
        raise SessionError("Invalid game DOS header")
    offset = struct.unpack_from("<I", header, 60)[0]
    if not 64 <= offset <= 4096:
        raise SessionError("Invalid game PE offset")
    nt = memory.read(base + offset, 88)
    if len(nt) != 88 or nt[:4] != b"PE\0\0":
        raise SessionError("Invalid game PE header")
    return (
        struct.unpack_from("<H", nt, 4)[0],
        struct.unpack_from("<I", nt, 8)[0],
        struct.unpack_from("<I", nt, 80)[0],
    )


class GameSession:
    def __init__(
        self, pid, hwnd, profile=None, catalog=None, creation_reader=process_creation
    ):
        self.pid, self.hwnd = pid, hwnd
        self.profile = profile
        self._explicit_profile = profile
        self.catalog = catalog or ProfileCatalog()
        self.creation_reader = creation_reader
        self.identity = None
        self.epoch = 0
        self.context_key = None
        self.cache = {}
        self.adapter_cache = {}
        self.adapter_cache_defaults = {}
        self.retained = {}
        self.resources = {}
        self.uncertain = False
        self.closed = False
        self.lock = threading.RLock()
        self._invalidators = []
        self.last_evidence = OperationEvidence()

    @property
    def adapter(self):
        if self.profile is None:
            raise SessionError("Game adapter has not been bound to a build")
        return self.profile.adapter

    def on_invalidate(self, callback):
        self._invalidators.append(callback)

    def invalidate(self, reason):
        self.epoch += 1
        self.cache.clear()
        self.adapter_cache.clear()
        self.adapter_cache.update((name, factory())
                                  for name, factory in self.adapter_cache_defaults.items())
        self.context_key = None
        self.last_invalidation = reason
        for callback in self._invalidators:
            callback(reason)

    def observe(self, identity, context_key):
        if self.closed:
            raise SessionError("Game session closed")
        if self.identity is not None and (self.identity.pid, self.identity.created) != (
            identity.pid,
            identity.created,
        ):
            # A verified creation timestamp distinguishes PID reuse from a live map change.
            # Old remote allocations cannot belong to the newly created process.
            self.previous_process_evidence = self.snapshot()
            for resource in self.resources.values():
                try:
                    resource.close()
                except Exception:
                    pass  # Preserve old object below; never run it on the replacement process.
            self.previous_resources = self.resources
            self.resources = {}
            self.retained = {}
            self.uncertain = False
        if self.identity != identity or self.context_key != context_key:
            self.invalidate("process/module/map/window context changed")
            self.identity = identity
            self.context_key = context_key

    def prepare(self, memory):
        with self.lock:
            try:
                return self._prepare_locked(memory)
            except Exception as exc:
                exc.session_report = self.snapshot()
                raise

    def _prepare_locked(self, memory):
        from war3_game_profile import ProfileError, BorrowedGameProfile
        from war3_object_registry import ObjectRegistry24268, _enumerate_process_modules
        from war3_thread_context import GameThreadContext24268

        created = self.creation_reader(memory)
        if self.identity is None or self.identity.created != created:
            records = _enumerate_process_modules(memory)
            matches = []
            self.build_diagnostics = []
            for base, name, path in records:
                try:
                    fingerprint = read_fingerprint(memory, base)
                    if len(self.build_diagnostics) < 96:
                        self.build_diagnostics.append(
                            {
                                "module": name,
                                "base": hex(base),
                                "fingerprint": fingerprint,
                            }
                        )
                    if self._explicit_profile is not None:
                        profile = self._explicit_profile
                    else:
                        try:
                            profile = self.catalog.select(fingerprint)
                        except ProfileError:
                            profile = self.catalog.select_for_image(fingerprint, name, path)
                    if profile.fingerprint == fingerprint:
                        matches.append((base, profile))
                except (OSError, ValueError, SessionError) as exc:
                    if self.build_diagnostics and self.build_diagnostics[-1]["base"] == hex(base):
                        self.build_diagnostics[-1]["adapter_selection_error"] = str(exc)
                    continue
            if len(matches) != 1:
                raise SessionError(
                    "Unknown or ambiguous game build; read-only diagnostics required"
                )
            base, profile = matches[0]
            self.profile = profile
        else:
            base = self.identity.module_base
            if read_fingerprint(memory, base) != self.profile.fingerprint:
                self.invalidate("game module fingerprint changed")
                raise SessionError("Game module changed; reconnect required")
        if self.profile.data["status"] != "validated" and not isinstance(self.profile, BorrowedGameProfile):
            raise SessionError("Candidate adapter is diagnostic-only")
        identity = SessionIdentity(
            self.pid, created, base, self.profile.fingerprint, self.profile.digest
        )
        with profile_scope(self.profile):
            cached = self.cache.get("context") if self.identity == identity else None
            registry = cached[0] if cached else ObjectRegistry24268(memory, base)
            context = (
                cached[1]
                if cached
                else GameThreadContext24268(memory, base, self.hwnd, self.pid)
            )
            try:
                mode = context.read_mode(memory)
            except Exception:
                self.invalidate("thread context unavailable")
                raise
            a = self.profile.section("addresses")
            q = lambda address: struct.unpack("<Q", memory.read(address, 8))[0]
            native_layout = self.profile.section("native_table")
            try:
                context5 = q(mode.tls + self.profile.section("context")["native_slot"])
                native_head = (
                    q(context5 + native_layout["table"] + native_layout["head"])
                    if context5 >= 0x10000
                    else 0
                )
                native_error = (
                    None if native_head else "Native registry is not initialized"
                )
            except (OSError, struct.error) as exc:
                context5 = native_head = 0
                native_error = str(exc)
            self.native_registry_error = native_error
            key = (
                self.hwnd,
                mode.thread_id,
                mode.tls,
                mode.context,
                mode.mode_object,
                q(base + a["registry_root"]),
                q(base + a["game_state"]),
                context5,
                native_head,
            )
            if (q(base + a["registry_root"]), q(base + a["game_state"])) != key[5:7]:
                self.invalidate("map changed while binding session")
                raise SessionError("Map changed while binding session")
            self.observe(identity, key)
            self.cache["context"] = (registry, context, mode)
            return registry, context, mode

    def require_write(self):
        active = _ACTIVE_EPOCH.get()
        if active is not None and active[0] is self and active[1] != self.epoch:
            raise SessionError(
                "Map context changed during the operation; stale request was not dispatched"
            )
        if self.closed or self.uncertain or self.retained:
            raise SessionError(
                "Session has unresolved execution/resources; write blocked, no automatic replay"
            )
        if self.identity is None:
            raise SessionError("Game session has not been verified")

    def finish(self, dispatch, readback=False):
        cleanup = bool(
            not dispatch.get("allocations_retained")
            and dispatch.get("cleanup_verified") is not False
            and dispatch.get("safe_to_release") is not False
            and (
                dispatch.get("work_freed")
                and dispatch.get("block_freed")
                and dispatch.get("image_unmap_status") == "0x0"
                or dispatch.get("safe_to_release")
                and dispatch.get("work_freed") is not False
                and dispatch.get("block_freed") is not False
            )
        )
        state = dispatch.get("after_cleanup") or dispatch.get("after_send") or {}
        # Receipt is distinct from callback exit and resource release. Legacy
        # fixture reports may only carry callback_verified; an explicit new
        # lifecycle result always takes precedence over that compatibility key.
        delivered = bool(dispatch.get("callback_received", dispatch.get("callback_verified")))
        exited = bool(dispatch.get("callback_exited", dispatch.get("callback_verified")))
        began = bool(state.get("callback_count") or state.get("query_stage") or delivered)
        completed = bool(dispatch.get("query_completed"))
        self.last_evidence = OperationEvidence(
            delivered=delivered,
            readback_verified=bool(readback and delivered and completed),
            effect_verified=False,
            cleanup_complete=cleanup,
            uncertain=bool(began and (not completed or not exited) or not cleanup),
            callback_exited=exited,
        )
        if self.last_evidence.uncertain:
            self.uncertain = True
        if dispatch.get("allocations_retained"):
            self.retained["dispatch"] = dispatch
        return self.last_evidence

    def require_native_query(self):
        active=_ACTIVE_EPOCH.get()
        if active is not None and active[0] is self and active[1]!=self.epoch:
            raise SessionError('Map context changed; stale query was not dispatched')
        if self.closed or self.identity is None:
            raise SessionError('Game session has not been verified')
        if self.retained or self.uncertain and not (
                self.last_evidence.callback_exited and self.last_evidence.cleanup_complete):
            raise SessionError('Previous callback or execution channel is still unresolved; native query deferred')
        # A business write remains uncertain, but the execution channel is
        # independently known to have exited and released its resources.
        # Queries do not clear that uncertainty or permit write replay.

    def bind_unit(self, memory, registry, address):
        if self.identity is None or self.closed:
            raise SessionError("Object binding requires a live verified session")
        if type(address) is not ObjectAddress:
            raise TypeError("Expected ObjectAddress, not a native/full handle")
        handle, _ = registry.resolve_unit(memory, address.value)
        rawcode = struct.unpack(
            "<I", memory.read(address.value + registry.layout["object_rawcode"], 4)
        )[0]
        return UnitRef(self.identity, self.epoch, FullHandle(handle), address, rawcode)

    def bind_item(self, memory, registry, handle):
        if self.identity is None or self.closed:
            raise SessionError("Object binding requires a live verified session")
        if type(handle) is not FullHandle:
            raise TypeError("Item resolver requires FullHandle")
        if handle.value in self.cache.get('retired_items', ()):
            raise SessionError('Item was explicitly removed; stale references are invalid')
        owner = registry.resolve_handle(memory, handle.value)
        layout = registry.layout
        q = lambda address: struct.unpack("<Q", memory.read(address, 8))[0]
        if q(owner + layout["owner_tag"]) != layout["item_tag"]:
            raise SessionError("Object is not an item")
        address = ObjectAddress(q(owner + layout["owner_data"]))
        rawcode = struct.unpack(
            "<I", memory.read(address.value + layout["object_rawcode"], 4)
        )[0]
        mirror = struct.unpack(
            "<I", memory.read(address.value + layout["item_rawcode_mirror"], 4)
        )[0]
        if rawcode != mirror:
            raise SessionError("Item type mirror differs")
        ref = ItemRef(self.identity, self.epoch, handle, address, rawcode)
        self.resolve(memory, registry, ref)
        return ref

    def retire_item(self, ref):
        """Native deletion can leave an engine tombstone; reject its cached refs."""
        if type(ref) is not ItemRef:
            raise TypeError('Expected ItemRef for retirement')
        with self.lock:
            if ref.session==self.identity and ref.epoch==self.epoch:
                self.cache.setdefault('retired_items',set()).add(ref.handle.value)

    def resolve(self, memory, registry, ref):
        if type(ref) not in (UnitRef, ItemRef):
            raise TypeError("Expected typed object reference")
        if ref.session != self.identity or ref.epoch != self.epoch:
            raise SessionError("Stale object reference")
        if type(ref.handle) is not FullHandle or type(ref.address) is not ObjectAddress:
            raise TypeError("Invalid object identity type")
        if type(ref) is ItemRef and ref.handle.value in self.cache.get('retired_items', ()):
            raise SessionError('Item was explicitly removed; stale references are invalid')
        owner = registry.resolve_handle(memory, ref.handle.value)
        address = struct.unpack(
            "<Q", memory.read(owner + registry.layout["owner_data"], 8)
        )[0]
        full = struct.unpack(
            "<Q", memory.read(address + registry.layout["object_handle"], 8)
        )[0]
        rawcode = struct.unpack(
            "<I", memory.read(address + registry.layout["object_rawcode"], 4)
        )[0]
        if (address, full, rawcode) != (
            ref.address.value,
            ref.handle.value,
            ref.rawcode,
        ):
            raise SessionError("Object destroyed or replaced")
        if type(ref) is UnitRef:
            registry.resolve_unit(memory, address)
        elif (
            struct.unpack("<Q", memory.read(owner + registry.layout["owner_tag"], 8))[0]
            != registry.layout["item_tag"]
        ):
            raise SessionError("Item object type changed")
        return address

    def snapshot(self):
        return {
            "identity": asdict(self.identity) if self.identity else None,
            "epoch": self.epoch,
            "profile_id": self.profile.id if self.profile else None,
            "game_version": self.profile.data["game_version"] if self.profile else None,
            "adapter_selection": self.profile.selection_report() if self.profile else None,
            "adapter_version": self.profile.data["adapter_version"]
            if self.profile
            else None,
            "bridge_profile_version": self.profile.data["bridge_profile_version"]
            if self.profile
            else None,
            "verification": asdict(self.last_evidence),
            "uncertain": self.uncertain,
            "retained_resources": list(self.retained),
            "owned_resources": list(self.resources),
            "last_invalidation": getattr(self, "last_invalidation", None),
            "native_registry_error": getattr(self, "native_registry_error", None),
            "adapter_import_errors": self.catalog.errors,
            "build_diagnostics": getattr(self, "build_diagnostics", []),
        }

    def close(self):
        with self.lock:
            return self._close_locked()

    def _close_locked(self):
        for name, resource in tuple(self.resources.items()):
            try:
                resource.close()
            except Exception as exc:
                self.retained[name] = {"error": str(exc), "resource": resource}
            else:
                self.resources.pop(name, None)
        self.closed = True
        self.invalidate("closed")
        return {
            "closed": True,
            "retained": bool(self.retained),
            "uncertain": self.uncertain,
        }
