"""A failed optional 3.0 bridge query must not erase indexed unit fields."""

from unittest.mock import Mock, patch

import pytest

from war3_engine_24268 import EngineExecutionError
from war3_reforged_trainer import UnitCandidate, War3Trainer


def selected_unit():
    return UnitCandidate(
        base=0, score=100, hp_current_address=0x1000,
        hp_max_address=0x1004, mp_current_address=0x1008,
        mp_max_address=0x100C, note="", owner_address=0x2000,
        handle=0x3000, unit_address=0x4000, unit_type_id=0x4845524F,
    )


def indexed_reader():
    trainer = object.__new__(War3Trainer)
    trainer.pid, trainer.hwnd = 1234, 5678
    trainer._native_selection_unavailable = True
    trainer._last_persistent_native_snapshots = ()
    trainer._selected_components = Mock(return_value={})
    memory = Mock()
    memory.read_f32.return_value = 100.0
    return trainer, memory


def install_failure(retained=False):
    return EngineExecutionError("bridge installation failed", {
        "dispatch": {"allocations_retained": retained, "image_route": "sec_image_fallback"},
    })


def test_bridge_install_failure_keeps_basic_fields_and_omits_unverified_stats():
    trainer, memory = indexed_reader()
    trainer._unit_stats_for_candidate_24268 = Mock(side_effect=install_failure())
    trainer.stat_details_24268 = Mock(side_effect=AssertionError("same failed bridge retried"))
    with patch("war3_reforged_trainer.record_operation_failure", return_value="diagnostic.log") as log:
        fields = {field.key: field for field in trainer._unit_fields_from_candidate(memory, selected_unit())}
    assert fields["hp_current"].value == 100.0
    assert fields["mp_current"].value == 100.0
    assert not any(key in fields for key in ("armor", "armor_type", "intelligence_total"))
    assert fields["unit_stats_unavailable"].value_text() == "不可用"
    assert not fields["unit_stats_unavailable"].writable
    assert fields["stat_details_unavailable"].value_text() == "不可用"
    assert "diagnostic.log" in fields["unit_stats_unavailable"].note
    trainer.stat_details_24268.assert_not_called()
    log.assert_called_once()


def test_stat_details_failure_preserves_verified_native_armor():
    trainer, memory = indexed_reader()
    trainer._unit_stats_for_candidate_24268 = Mock(return_value={
        "unit": 0x1234, "rawcode": selected_unit().unit_type_id,
        "armor_after": 12.5, "defense_after": 4,
    })
    trainer.stat_details_24268 = Mock(side_effect=install_failure())
    with patch("war3_reforged_trainer.record_operation_failure", return_value="stat.log"):
        fields = {field.key: field for field in trainer._unit_fields_from_candidate(memory, selected_unit())}
    assert fields["armor"].value == 12.5
    assert fields["armor_type"].value == 4
    assert fields["stat_details_unavailable"].value_text() == "不可用"
    assert not any(key.startswith("stat3_") for key in fields)


def test_hero_intelligence_is_not_faked_after_bridge_failure():
    trainer, memory = indexed_reader()
    trainer._selected_components.return_value = {"hero": (0x5000, 0x6000)}
    trainer._ability_instances_from_candidate = Mock(return_value=[])
    memory.read_i32.return_value = 47
    memory.read_u32.return_value = 0
    trainer._unit_stats_for_candidate_24268 = Mock(side_effect=install_failure())
    trainer.stat_details_24268 = Mock(side_effect=AssertionError("same failed bridge retried"))
    with patch("war3_reforged_trainer.record_operation_failure", return_value="diagnostic.log"):
        fields = {field.key: field for field in trainer._unit_fields_from_candidate(memory, selected_unit())}
    assert fields["base_strength"].value == 47
    assert fields["base_agility"].value == 47
    assert "base_intelligence" not in fields
    assert "intelligence_total" not in fields


def test_retained_bridge_resources_still_abort_read():
    trainer, memory = indexed_reader()
    trainer._unit_stats_for_candidate_24268 = Mock(side_effect=install_failure(retained=True))
    with patch("war3_reforged_trainer.record_operation_failure") as log:
        with pytest.raises(EngineExecutionError):
            trainer._unit_fields_from_candidate(memory, selected_unit())
    log.assert_not_called()
