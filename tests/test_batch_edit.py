"""Offline mixed-unit, stale-session, per-field and Tk interaction coverage."""
from dataclasses import replace
import ast
import json
from pathlib import Path
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import war3_reforged_trainer as product
from war3_game_session import FullHandle, ObjectAddress, SessionIdentity, UnitRef
from war3_game_profile import default_profile
from war3_services import batch_edit as batch
from war3_ui_i18n import translate_ui_text


def field(key="hp_current", *, writable=True, value=10.0, kind="f32"):
    return product.UnitMemoryField(
        key=key, label=key, value_type=kind, value=value, address=0x1000,
        category="base", write_address=0x1000 if writable else 0,
        write_type=kind if writable else "",
    )


class Memory:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


class Session:
    def __init__(self):
        self.identity = SessionIdentity(42, 1, 0x10000, (1, 2, 3), "profile")
        self.epoch = 1
        self.lock = threading.RLock()
        self.profile = default_profile()
        self.retained = False
        self.dead = set()
        self.registry = SimpleNamespace(resolve_unit=lambda _m, address: (address // 8, address + 8))

    def prepare(self, _memory):
        return self.registry, None, None

    def resolve(self, _memory, _registry, ref):
        if ref.handle.value in self.dead:
            raise ValueError("unit destroyed")
        if ref.session != self.identity or ref.epoch != self.epoch:
            raise ValueError("stale reference")
        return ref.address.value

    def require_write(self):
        if self.retained:
            raise ValueError("callback resources retained")


class Logger:
    def __init__(self, path):
        self.archive_path = path
        self.events = []
        self._files = [True]

    def log(self, event, **data):
        self.events.append((event, data))
        with self.archive_path.open("a", encoding="utf8") as stream:
            stream.write(event + " " + repr(data) + "\n")

    def close(self):
        self._files = []


@pytest.fixture
def setup_batch(tmp_path):
    session = Session()
    refs = tuple(UnitRef(session.identity, 1, FullHandle(address // 8),
                         ObjectAddress(address), int.from_bytes(b"hfoo", "big"))
                 for address in (0x10000, 0x20000))
    units = tuple(batch.BatchUnit(ref, ref.address.value + 8, (field(),)) for ref in refs)
    snapshot = batch.BatchSnapshot(session, session.identity, 1, units)
    host = SimpleNamespace(
        _game_session=session, _process_memory=lambda: Memory(),
        _coerce_memory_value=product.War3Trainer._coerce_memory_value,
        read_unit_fields_by_identity=Mock(return_value=(None, None, [field()])),
        write_unit_field_by_identity=Mock(side_effect=lambda h, o, u, k, v: replace(field(k), value=float(v))),
    )
    logs = []

    def factory(_pid, **_kwargs):
        logger = Logger(tmp_path / f"batch-{len(logs)}.log")
        logs.append(logger)
        return logger
    return batch.BatchEditService(host, factory), host, session, snapshot, logs


def test_same_rawcode_units_toggle_independently_and_keep_order(setup_batch):
    _, _, _, snapshot, _ = setup_batch
    model = batch.BatchEditModel(snapshot)
    assert len(model.selected_units()) == 2
    model.toggle(snapshot.units[0].identity)
    assert model.selected_units() == (snapshot.units[1],)
    model.toggle(snapshot.units[0].identity)
    assert model.selected_units() == snapshot.units
    model.select_all(False)
    assert not model.selected_units()
    model.select_all(True)
    assert model.selected_units() == snapshot.units


def test_field_catalog_is_union_of_writable_capabilities(setup_batch):
    _, _, _, snapshot, _ = setup_batch
    units = (replace(snapshot.units[0], fields=(field(), field("xp", kind="i32", value=1),
                                               field("pointer", writable=False))),
             replace(snapshot.units[1], fields=(field(), field("xp", writable=False))))
    options = batch.BatchEditModel(replace(snapshot, units=units)).field_options()
    assert {row.key: row.supported for row in options} == {"hp_current": 2, "xp": 1}


def test_mixed_units_skip_missing_and_readonly_fields_then_continue(setup_batch):
    service, host, _, snapshot, _ = setup_batch
    first, second = snapshot.units
    host.read_unit_fields_by_identity.side_effect = lambda h, o, u: (
        None, None, [field(), field("xp", value=1, kind="i32")] if h == first.ref.handle.value
        else [field(), field("xp", writable=False)])
    result = service.apply(snapshot, snapshot.units, {"hp_current": "77", "xp": "8", "blank": " "})
    assert result.count("success") == 3 and result.count("skipped") == 1
    assert host.write_unit_field_by_identity.call_count == 3
    host.read_unit_fields_by_identity.side_effect = None
    host.read_unit_fields_by_identity.return_value = (None, None, [field()])
    missing = service.apply(snapshot, (second,), {"xp": "8", "hp_current": "88"})
    assert [row.status for row in missing.fields] == ["skipped", "success"]


def test_field_failure_is_never_replayed_and_next_unit_still_runs(setup_batch):
    service, host, _, snapshot, _ = setup_batch
    host.write_unit_field_by_identity.side_effect = [OSError("write fault"), field(value=77.0)]
    report = service.apply(snapshot, snapshot.units, {"hp_current": "77"})
    assert [row.status for row in report.fields] == ["failed", "success"]
    assert host.write_unit_field_by_identity.call_count == 2
    assert host.write_unit_field_by_identity.call_args_list[0].args[:3] == snapshot.units[0].identity
    assert host.write_unit_field_by_identity.call_args_list[1].args[:3] == snapshot.units[1].identity


def test_destroyed_unit_is_skipped_without_writing_or_blocking_other_unit(setup_batch):
    service, host, session, snapshot, _ = setup_batch
    session.dead.add(snapshot.units[0].ref.handle.value)
    report = service.apply(snapshot, snapshot.units, {"hp_current": "11"})
    assert [row.status for row in report.fields] == ["failed", "success"]
    assert host.write_unit_field_by_identity.call_count == 1


@pytest.mark.parametrize("change", ["epoch", "identity", "retained", "session"])
def test_session_change_stops_all_remaining_pairs(setup_batch, change):
    service, host, session, snapshot, _ = setup_batch
    def write(*_args):
        if change == "epoch":
            session.epoch += 1
        elif change == "identity":
            session.identity = replace(session.identity, created=2)
        elif change == "session":
            host._game_session = Session()
        else:
            session.retained = True
        return field(value=77.0)
    host.write_unit_field_by_identity.side_effect = write
    result = service.apply(snapshot, snapshot.units, {"hp_current": "77"})
    assert host.write_unit_field_by_identity.call_count == 1
    assert result.count("not_attempted") == 1 and result.stopped


def test_another_trainer_session_cannot_reuse_snapshot_even_with_same_values(setup_batch):
    service, host, _, snapshot, _ = setup_batch
    host._game_session = Session()
    report = service.apply(snapshot, snapshot.units, {"hp_current": "2"})
    assert report.count("not_attempted") == 2
    host.write_unit_field_by_identity.assert_not_called()


@pytest.mark.parametrize("kind,target", [("i32", str(2**31)), ("u32", "-1"),
                                       ("f32", "nan"), ("rawcode", "too long")])
def test_invalid_input_skips_pair_before_write(setup_batch, kind, target):
    service, host, _, snapshot, _ = setup_batch
    host.read_unit_fields_by_identity.return_value = (None, None, [field(kind=kind, value=1)])
    report = service.apply(snapshot, snapshot.units, {"hp_current": target})
    assert report.count("failed") == 2
    host.write_unit_field_by_identity.assert_not_called()


def test_wrong_readback_is_reported_and_no_retry_occurs(setup_batch):
    service, host, _, snapshot, _ = setup_batch
    host.write_unit_field_by_identity.side_effect = None
    host.write_unit_field_by_identity.return_value = field(value=12.0)
    result = service.apply(snapshot, (snapshot.units[0],), {"hp_current": "77"})
    assert result.count("failed") == 1 and result.fields[0].actual == "12"
    assert host.write_unit_field_by_identity.call_count == 1


def test_f32_and_rawcode_targets_use_existing_coercion_and_exact_readback(setup_batch):
    service, host, _, snapshot, _ = setup_batch
    values = [field(value=1, kind="f32"), field("slot", value=0, kind="rawcode")]
    host.read_unit_fields_by_identity.return_value = (None, None, values)
    host.write_unit_field_by_identity.side_effect = lambda h, o, u, k, v: replace(
        values[0 if k == "hp_current" else 1],
        value=host._coerce_memory_value("f32" if k == "hp_current" else "rawcode", v))
    result = service.apply(snapshot, (snapshot.units[0],), {"hp_current": "0.1", "slot": "ckng"})
    assert result.count("success") == 2


def test_empty_selection_and_blank_targets_do_zero_writes(setup_batch):
    service, host, _, snapshot, _ = setup_batch
    for units, targets in [((), {"hp_current": "5"}), (snapshot.units, {"hp_current": " "})]:
        with pytest.raises(ValueError):
            service.apply(snapshot, units, targets)
    host.write_unit_field_by_identity.assert_not_called()


def test_live_fields_are_read_again_after_item_replacement(setup_batch):
    service, host, _, snapshot, _ = setup_batch
    host.read_unit_fields_by_identity.side_effect = [
        (None, None, [field("inventory_slot_1", kind="rawcode", value=0)]),
        (None, None, [field("inventory_slot_1_charges", kind="i32", value=1)]),
    ]
    host.write_unit_field_by_identity.side_effect = [
        field("inventory_slot_1", kind="rawcode", value=int.from_bytes(b"ckng", "big")),
        field("inventory_slot_1_charges", kind="i32", value=20),
    ]
    report = service.apply(snapshot, (snapshot.units[0],),
                           {"inventory_slot_1": "ckng", "inventory_slot_1_charges": "20"})
    assert report.count("success") == 2


def test_real_trace_contains_pairs_targets_identity_readback_and_failures(setup_batch):
    service, host, _, snapshot, logs = setup_batch
    host.write_unit_field_by_identity.side_effect = [OSError("external error"), field(value=77.0)]
    report = service.apply(snapshot, snapshot.units, {"hp_current": "77"})
    text = Path(report.log_path).read_text(encoding="utf8")
    rows = [json.loads(line) for line in Path(report.log_path).with_suffix(".jsonl").read_text().splitlines()]
    phases = [row.get("phase") for row in rows]
    assert "field_begin" in phases and "field_exception" in phases and "field_readback" in phases
    assert "batch_complete" in phases and "external error" in text
    assert "automatic_replay" in text and "target" in text and "full_handle" not in text
    assert any(event == "batch_phase" for event, _ in logs[0].events)


def test_selection_read_binds_every_unit_including_failed_field_read(setup_batch, monkeypatch):
    service, host, _, snapshot, _ = setup_batch
    monkeypatch.setattr(batch.ExternalMemoryBackend, "selected_units",
                        lambda *_: tuple(unit.ref for unit in snapshot.units))
    def read(h, owner, address):
        if address == snapshot.units[1].ref.address.value:
            raise OSError("one unit field read failed")
        return None, SimpleNamespace(handle=h, owner_address=owner, unit_address=address), [field()]
    host.read_unit_fields_by_identity.side_effect = read
    actual = service.read()
    assert len(actual.units) == 2
    assert actual.units[0].fields and not actual.units[1].fields
    assert "failed" in actual.units[1].error


def test_targeted_stat_query_uses_native_binding_not_rawcode_or_object_pointer(setup_batch):
    _, _, _, snapshot, _ = setup_batch
    ref = snapshot.units[1].ref
    candidate = SimpleNamespace(handle=ref.handle.value, unit_address=ref.address.value,
                                unit_type_id=ref.rawcode)
    row = dict(status=1, unit=0x100099, rawcode=ref.rawcode)
    engine = SimpleNamespace(unit_stats=Mock(return_value={"rows": [row]}))
    host = SimpleNamespace(_engine_instance_24268=lambda: engine,
                           _stat_target_24268=Mock(return_value=(candidate, 0x100099)))
    from war3_services.facade_native import NativeFacade
    with batch.field_target(ref):
        actual = NativeFacade._unit_stats_for_candidate_24268(host, candidate)
    assert actual == row
    engine.unit_stats.assert_called_once_with(target_unit=0x100099)
    assert batch.active_field_target() is None


def test_new_strings_are_localized():
    import re
    for path in (Path(batch.__file__), Path(product.__file__).with_name("war3_batch_edit_ui.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not re.search("[\u4e00-\u9fff]", translate_ui_text(node.value, "en")), node.value


def test_offline_tk_tab_toggle_inputs_and_language_preserve_values(setup_batch):
    import tkinter as tk
    from tkinter import ttk
    from war3_batch_edit_ui import BatchEditTab
    root = tk.Tk()
    root.withdraw()
    try:
        notebook = ttk.Notebook(root)
        language = ["zh"]
        ui = BatchEditTab(notebook, get_trainer=lambda: None, call_async=lambda *_: None,
                          ui_text=lambda s: translate_ui_text(s, language[0]), logger_factory=None)
        notebook.add(ui.frame, text="批量修改")
        ui.populate(setup_batch[3])
        assert len(ui.units.get_children()) == 2
        ui.toggle("0")
        assert len(ui.model.checked) == 1
        ui.select_all(False)
        assert not ui.model.checked
        ui.select_all(True)
        assert len(ui.model.checked) == 2
        ui.targets["hp_current"].set("999")
        language[0] = "en"
        ui.refresh_language()
        assert ui.targets["hp_current"].get() == "999"
        assert ui.read_button.cget("text") == "Read all selected units"
        ui.clear_targets()
        assert not ui.targets["hp_current"].get()
        ui._busy(True)
        assert ui.read_button.instate(["disabled"]) and ui.write_button.instate(["disabled"])
    finally:
        root.destroy()
