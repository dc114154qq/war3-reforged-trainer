import struct
import pytest
from types import SimpleNamespace
from unittest.mock import Mock
from war3_reforged_trainer import War3Trainer

from war3_3_stats import STAT_DETAIL_SPECS
from war3_native_table import LiveNativeEntry
from war3_selection_protocol import SIGNATURES as SELECTION_SIGNATURES
from war3_stat_details_protocol import (
    SIGNATURES as STAT_SIGNATURES,
    WORK_SIZE,
    build_work,
    decode_work,
    validate_work,
)


def entries():
    return {
        name: LiveNativeEntry(name, signature, 0x300000 + index * 0x80, 0x500000 + index * 0x100)
        for index, (name, signature) in enumerate(SELECTION_SIGNATURES + STAT_SIGNATURES)
    }


def test_stat_details_read_roundtrip_preserves_percent_baselines():
    payload = bytearray(build_work(entries(), 0x10000000))
    unit = 0x110000
    struct.pack_into("<2Q4I", payload, 64, 0x120000, 0x130000, 1, 0, 1, 0)
    struct.pack_into("<QIi", payload, 96, unit, int.from_bytes(b"HERO", "big"), 8)
    struct.pack_into("<Q8I", payload, 576, unit, 0, 0, 0, 0, 0, 0, 1, 1)
    before = [0.0] * len(STAT_DETAIL_SPECS)
    before[1] = 25.0
    after = list(before)
    struct.pack_into(f"<{len(before)}f", payload, 616, *before)
    struct.pack_into(f"<{len(after)}f", payload, 616 + len(before) * 4, *after)
    struct.pack_into("<I", payload, 616 + len(STAT_DETAIL_SPECS) * 8, int.from_bytes(b"AIxr", "big"))
    result = decode_work(bytes(payload), 1)

    assert len(payload) == WORK_SIZE
    assert result["before"][1] == 25.0
    assert result["after"] == result["before"]


def test_stat_details_write_requires_controller_and_target_roundtrips():
    payload = build_work(
        entries(), 0x10000000, action=1, stat_index=0, target=30.0,
        controller="AIxr", target_unit=0x8CE100008CD5,
    )
    validate_work(payload)


def test_ability_visibility_refresh_requires_unique_target():
    payload = build_work(
        entries(), 0x10000000, action=2, controller="UT1a", target_unit=0x100002,
    )
    validate_work(payload)
    with pytest.raises(ValueError, match="target unit"):
        build_work(entries(), 0x10000000, action=2, controller="UT1a")


def test_stat_details_rejects_nonfinite_target():
    try:
        build_work(entries(), 0x10000000, action=1, stat_index=0,
                   target=float("nan"), controller="AIxr")
    except ValueError as exc:
        assert "supported range" in str(exc)
    else:
        raise AssertionError("non-finite stat target was accepted")


def test_failed_field_reports_native_operation_and_exception_location():
    payload = bytearray(build_work(entries(), 0x10000000))
    unit = 0x110000
    struct.pack_into("<2Q4I", payload, 64, 0x120000, 0x130000, 1, 0, 1, 0)
    struct.pack_into("<QIi", payload, 96, unit, int.from_bytes(b"HERO", "big"), 8)
    struct.pack_into("<Q8I", payload, 576, unit, 0, 0, 0, 0, 0, 0xC0000005, 0, 1)
    field = int.from_bytes(b"Icr2", "big")
    struct.pack_into("<2Q2IQ", payload, 984, 0x100FEB, 0x7FF75341D43D, field, 4, field)
    with pytest.raises(ValueError) as raised:
        decode_work(bytes(payload), 1)
    message = str(raised.value)
    assert "stage=4" in message and "field='Icr2'" in message
    assert "ability=0x100feb" in message
    assert "converted_field=0x49637232" in message
    assert "exception_address=0x7ff75341d43d" in message


def test_stat_write_binds_reordered_native_selection_instead_of_first_unit():
    trainer = object.__new__(War3Trainer)
    candidate = SimpleNamespace(handle=0xCAFE00008000, unit_type_id=100,
                                owner_address=0x123000, unit_address=0x124000)
    trainer._direct_selected_context = Mock(return_value=(candidate, candidate.handle))
    engine = Mock()
    engine.ability_batch.return_value = {"rows": [
        {"handle": 0x100001, "rawcode": 200}, {"handle": 0x100002, "rawcode": 100},
    ]}
    engine.stat_details.return_value = {"after": (0, 350) + (0,) * 12}
    trainer._engine_instance_24268 = Mock(return_value=engine)
    assert trainer.set_stat_detail_24268("critical_damage", 500) == 500
    assert engine.stat_details.call_args.kwargs["target_unit"] == 0x100002


def test_ambiguous_native_stat_target_does_not_write():
    trainer = object.__new__(War3Trainer)
    candidate = SimpleNamespace(handle=0xCAFE00008000, unit_type_id=100)
    trainer._direct_selected_context = Mock(return_value=(candidate, candidate.handle))
    engine = Mock()
    engine.ability_batch.return_value = {"rows": [
        {"handle": 0x100001, "rawcode": 100}, {"handle": 0x100002, "rawcode": 100},
    ]}
    trainer._engine_instance_24268 = Mock(return_value=engine)
    with pytest.raises(RuntimeError, match="身份不唯一"):
        trainer.set_stat_detail_24268("critical_damage", 500)
    engine.stat_details.assert_not_called()
