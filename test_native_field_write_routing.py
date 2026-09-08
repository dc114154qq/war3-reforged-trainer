"""Real field-table routing to guarded native writes; no process access."""
from dataclasses import replace
from unittest.mock import Mock, MagicMock

import pytest
import war3_reforged_trainer as module
from test_native_basic_writes import context
from test_native_snapshot_binding import snapshot_result


@pytest.fixture
def fields_context(context):
    trainer, memory, candidate, snapshot = context
    # Unrelated legacy fields are unavailable; all six native fields have no
    # property addresses in this candidate and must still be usable.
    memory.read_f32.side_effect = OSError('No external property')
    trainer._selected_components = Mock(return_value={})
    memory.components = {}
    memory.attack2 = False
    trainer._native_unit_field_memory = Mock(return_value=memory)
    trainer._inventory_items_from_candidate = Mock(return_value=[])
    return trainer, memory, candidate, snapshot


def test_six_native_fields_are_writable_without_fabricated_addresses(fields_context):
    trainer, memory, candidate, _ = fields_context
    fields = {f.key: f for f in trainer._unit_fields_from_candidate(memory, candidate)}
    for key in ('hp_current','hp_max','mp_current','mp_max','x','y'):
        field = fields[key]
        assert field.writable and field.native_write
        assert field.address == field.write_address == 0
        assert field.write_type == ''


def test_public_field_write_batches_values_and_returns_actual_native_readback(fields_context):
    trainer, memory, candidate, snapshot = fields_context
    fresh = replace(snapshot, hp=149, hp_max=400, mp=80, mp_max=100, x=125, y=23)
    trainer._run_native_helper_ops.side_effect = [[snapshot_result(snapshot)], [], [snapshot_result(fresh)]]
    trainer._selected_candidates_snapshot = Mock(return_value=[(candidate, snapshot.handle)])
    manager = MagicMock()
    manager.__enter__.return_value = memory
    trainer._process_memory = Mock(return_value=manager)
    requested = [('HP-当前值', 150), ('x', 125), ('hp_max', 400), ('mp_current', 80),
                 ('mp_max', 100), ('y', 23)]
    result = trainer.write_selected_unit_fields([module.MemoryWriteSpec(key, 0, '', value)
                                                for key, value in requested])
    assert [field.key for field in result] == ['hp_current', 'x', 'hp_max', 'mp_current', 'mp_max', 'y']
    assert [field.value for field in result] == [149, 125, 400, 80, 100, 23]
    calls = trainer._run_native_helper_ops.call_args_list
    assert len(calls) == 3
    handle, ops = calls[1].args
    assert handle == snapshot.handle
    assert [op[0] for op in ops] == [136, 135, 134, 135, 134, 94]
    assert ops[0][2:] == (candidate.unit_address, candidate.handle, candidate.owner_address)
    memory.write_f32.assert_not_called()
    manager.__exit__.assert_called_once()


@pytest.mark.parametrize('second', [('hero_level', 9), ('missing_field', 1), ('x', 'nan')])
def test_invalid_mixed_request_is_rejected_before_native_mutation(fields_context, second):
    trainer, memory, candidate, _ = fields_context
    specs = [module.MemoryWriteSpec('hp_current', 0, '', 150), module.MemoryWriteSpec(second[0], 0, '', second[1])]
    with pytest.raises((ValueError, RuntimeError)):
        trainer._write_unit_fields_to_candidate(memory, candidate, specs)
    trainer._run_native_helper_ops.assert_not_called()
    memory.write_f32.assert_not_called()


def test_native_failure_does_not_write_old_property_address(fields_context):
    trainer, memory, candidate, snapshot = fields_context
    candidate = replace(candidate, hp_current_address=0x123456)
    trainer._run_native_helper_ops.side_effect = [[snapshot_result(snapshot)], RuntimeError('identity changed')]
    with pytest.raises(RuntimeError, match='identity changed'):
        trainer._write_unit_fields_to_candidate(memory, candidate, [module.MemoryWriteSpec('hp_current', 0, '', 150)])
    memory.write_f32.assert_not_called()


def test_duplicate_key_and_label_are_rejected_before_writing(fields_context):
    trainer, memory, candidate, _ = fields_context
    with pytest.raises(ValueError, match='Duplicate'):
        trainer._write_unit_fields_to_candidate(memory, candidate, [module.MemoryWriteSpec(key, 0, '', 150)
                                                                  for key in ('hp_current', 'HP-当前值')])
    trainer._run_native_helper_ops.assert_not_called()
