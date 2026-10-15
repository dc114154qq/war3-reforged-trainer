"""Batch unit fields through the shared session and the existing field backends."""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from contextvars import ContextVar
import struct
import traceback

from war3_external_backend import ExternalMemoryBackend
from war3_game_session import GameSession, SessionIdentity, UnitRef, session_scope
from war3_services.operation_trace import BackpackTrace

_FIELD_TARGET = ContextVar("batch_field_target", default=None)


def active_field_target():
    return _FIELD_TARGET.get()


@contextmanager
def field_target(ref):
    token = _FIELD_TARGET.set(ref)
    try:
        yield
    finally:
        _FIELD_TARGET.reset(token)


@dataclass(frozen=True)
class BatchUnit:
    ref: UnitRef
    owner: int
    fields: tuple
    error: str = ""

    @property
    def identity(self):
        return self.ref.handle.value, self.owner, self.ref.address.value


@dataclass(frozen=True)
class BatchSnapshot:
    session: GameSession
    identity: SessionIdentity
    epoch: int
    units: tuple[BatchUnit, ...]


@dataclass(frozen=True)
class FieldOption:
    key: str
    label: str
    category: str
    value_type: str
    supported: int


@dataclass(frozen=True)
class FieldResult:
    unit: BatchUnit
    key: str
    target: str
    status: str
    reason: str = ""
    actual: str = ""


@dataclass(frozen=True)
class BatchResult:
    fields: tuple[FieldResult, ...]
    log_path: str = ""
    stopped: str = ""

    def count(self, status):
        return sum(row.status == status for row in self.fields)


class BatchEditModel:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.checked = {unit.identity for unit in snapshot.units}

    def toggle(self, identity):
        if identity not in {unit.identity for unit in self.snapshot.units}:
            return
        if identity in self.checked:
            self.checked.remove(identity)
        else:
            self.checked.add(identity)

    def select_all(self, checked):
        self.checked = {unit.identity for unit in self.snapshot.units} if checked else set()

    def selected_units(self):
        return tuple(unit for unit in self.snapshot.units if unit.identity in self.checked)

    def field_options(self):
        catalog, counts = {}, {}
        for unit in self.snapshot.units:
            for field in {f.key: f for f in unit.fields if f.writable}.values():
                catalog.setdefault(field.key, field)
                counts[field.key] = counts.get(field.key, 0) + 1
        return tuple(FieldOption(key, field.label, field.category, field.value_type, counts[key])
                     for key, field in catalog.items())


class BatchTrace(BackpackTrace):
    prefix = "batch-edit"
    event_name = "batch_phase"
    source_inputs = ("batch_edit.py", "facade_fields.py", "facade_selection.py")


class BatchEditService:
    def __init__(self, host, logger_factory):
        self.host, self.logger_factory = host, logger_factory

    def _session(self):
        session = getattr(self.host, "_game_session", None)
        if session is None:
            raise RuntimeError("请先连接游戏再读取批量单位")
        return session

    def read(self):
        session = self._session()
        with session.lock, session_scope(session), BatchTrace(
            self.host, self.logger_factory, {"action": "read_selection"}
        ) as trace, self.host._process_memory() as memory:
            registry, _, _ = session.prepare(memory)
            identity, epoch = session.identity, session.epoch
            refs = ExternalMemoryBackend(session).selected_units(memory)
            if not refs:
                raise ValueError("游戏当前没有可操作的选中单位")
            units = []
            for ref in refs:
                session.resolve(memory, registry, ref)
                handle, owner = registry.resolve_unit(memory, ref.address.value)
                if handle != ref.handle.value:
                    raise RuntimeError("批量单位身份已变化，请重新读取")
                error, fields = "", ()
                try:
                    with field_target(ref):
                        _panel, candidate, read_fields = self.host.read_unit_fields_by_identity(
                            ref.handle.value, owner, ref.address.value
                        )
                    if (candidate.handle, candidate.owner_address, candidate.unit_address) != (
                        ref.handle.value, owner, ref.address.value
                    ):
                        raise RuntimeError("批量单位身份已变化，请重新读取")
                    fields = tuple(read_fields)
                except Exception as exc:
                    error = str(exc)
                    trace.record("unit_read_failed", ref=ref, owner=owner,
                                 exception=repr(exc), traceback=traceback.format_exc())
                units.append(BatchUnit(ref, owner, fields, error))
                trace.record("unit_read", ref=ref, owner=owner, error=error,
                             fields=fields, writable=[f.key for f in fields if f.writable])
            session.prepare(memory)
            if session.identity != identity or session.epoch != epoch:
                raise RuntimeError("游戏或地图已变化，请重新读取批量单位")
            trace.record("selection_complete", count=len(units), identity=identity, epoch=epoch)
            return BatchSnapshot(session, identity, epoch, tuple(units))

    def apply(self, snapshot, units, targets):
        units = tuple(units)
        targets = {key: str(value).strip() for key, value in targets.items()
                   if str(value).strip()}
        if not units:
            raise ValueError("请至少勾选一个批量单位")
        if not targets:
            raise ValueError("请至少填写一个批量字段目标值")
        if any(unit not in snapshot.units for unit in units):
            raise ValueError("批量单位不属于本次读取，请重新读取")
        if len({unit.identity for unit in units}) != len(units):
            raise ValueError("批量单位身份重复，请重新读取")
        session = self._session()
        pairs = tuple((unit, key, value) for unit in units for key, value in targets.items())
        results, stopped = [], ""
        capabilities = {}
        with session.lock, session_scope(session), BatchTrace(
            self.host, self.logger_factory,
            dict(action="write_fields", targets=targets,
                 units=[dict(ref=unit.ref, owner=unit.owner) for unit in units]),
        ) as trace, self.host._process_memory() as memory:
            def ensure_session():
                if session is not snapshot.session or self.host._game_session is not session:
                    raise RuntimeError("游戏会话已变化，请重新读取批量单位")
                registry, _, _ = session.prepare(memory)
                if session.identity != snapshot.identity or session.epoch != snapshot.epoch:
                    raise RuntimeError("游戏或地图已变化，请重新读取批量单位")
                session.require_write()
                self.host._classic_object_registry = registry
                return registry

            for index, (unit, key, target) in enumerate(pairs):
                context = dict(pair=index + 1, ref=unit.ref, owner=unit.owner,
                               key=key, target=target)
                try:
                    registry = ensure_session()
                except Exception as exc:
                    stopped = str(exc)
                    trace.record("session_stopped", **context, exception=repr(exc),
                                 traceback=traceback.format_exc())
                    results.extend(FieldResult(u, k, v, "not_attempted", stopped)
                                   for u, k, v in pairs[index:])
                    break
                trace.record("field_begin", **context)
                try:
                    session.resolve(memory, registry, unit.ref)
                    # Cache capabilities within this request, never write
                    # addresses. The setter resolves its own current fields.
                    # Inventory/skill replacement invalidates this capability
                    # view before the next field is considered.
                    fields = capabilities.get(unit.identity)
                    if fields is None:
                        with field_target(unit.ref):
                            _panel, _candidate, fields = self.host.read_unit_fields_by_identity(*unit.identity)
                        capabilities[unit.identity] = fields
                    field = next((field for field in fields if field.key == key), None)
                    if field is None or not field.writable:
                        reason = "该单位没有此字段" if field is None else "该单位此字段只读"
                        result = FieldResult(unit, key, target, "skipped", reason)
                    else:
                        value_type = field.write_type or field.value_type
                        expected = self.host._coerce_memory_value(value_type, target)
                        if value_type in {"i32", "u32", "rawcode", "u64", "ptr"}:
                            struct.pack({"i32": "<i", "u32": "<I", "rawcode": "<I",
                                         "u64": "<Q", "ptr": "<Q"}[value_type], expected)
                        trace.record("field_validated", **context, field=field, expected=expected)
                        registry = ensure_session()
                        session.resolve(memory, registry, unit.ref)
                        trace.checkpoint()
                        with field_target(unit.ref):
                            written = self.host.write_unit_field_by_identity(*unit.identity, key, target)
                        if key.startswith("inventory_slot_") or (key.startswith("skill") and key.endswith("_name")):
                            capabilities.pop(unit.identity, None)
                        session.resolve(memory, registry, unit.ref)
                        if written.value != expected:
                            result = FieldResult(unit, key, target, "failed",
                                                 "写入读回与目标值不一致", written.value_text())
                        else:
                            result = FieldResult(unit, key, target, "success",
                                                 actual=written.value_text())
                        trace.record("field_readback", **context, expected=expected,
                                     actual=written, effect_verified=False)
                except Exception as exc:
                    capabilities.pop(unit.identity, None)
                    result = FieldResult(unit, key, target, "failed", str(exc))
                    trace.record("field_exception", **context, exception=repr(exc),
                                 traceback=traceback.format_exc(),
                                 execution_report=getattr(exc, "report", None),
                                 automatic_replay=False)
                results.append(result)
                trace.record("field_result", **context, status=result.status,
                             reason=result.reason, actual=result.actual, replayed=False)
            report = BatchResult(tuple(results), trace.log_path or "", stopped)
            trace.record("batch_complete", success=report.count("success"),
                         skipped=report.count("skipped"), failed=report.count("failed"),
                         not_attempted=report.count("not_attempted"), stopped=stopped)
            return report
