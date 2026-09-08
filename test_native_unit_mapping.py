"""Actual identity mapping with absent external property metadata."""
from dataclasses import replace
from unittest.mock import Mock, MagicMock

import pytest
import war3_reforged_trainer as module
from test_native_basic_writes import context
from test_native_snapshot_binding import make_candidate, make_snapshot, snapshot_result


@pytest.fixture
def mapping(context):
    trainer, memory, _, snapshot = context
    values = {
        snapshot.owner_address + 0x18: trainer.UNIT_OWNER_TAG,
        snapshot.owner_address + 0x20: snapshot.full_handle,
        snapshot.owner_address + 0x90: snapshot.unit_address,
        snapshot.unit_address + 0x18: snapshot.full_handle,
    }
    memory.read_u64.side_effect = lambda address: values[address]
    trainer._property_from_owner = Mock(return_value=None)
    trainer._unit_owner_index = {}
    trainer._elephant_selection_override = None
    trainer._selected_components = Mock(return_value={})
    trainer._native_unit_field_memory = Mock(return_value=module.NativeUnitFieldMemory(
        make_candidate(snapshot),
        (snapshot.unit_address, snapshot.full_handle, snapshot.owner_address) + (0,) * 290))
    trainer._inventory_items_from_candidate = Mock(return_value=[])
    trainer.persistent_native_selected_snapshots.side_effect = None
    trainer.persistent_native_selected_snapshots.return_value = (snapshot,)
    for name in ('_build_unit_owner_index', '_build_unit_object_index', '_owner_for_handle'):
        setattr(trainer, name, Mock(side_effect=AssertionError('Unexpected global lookup')))
    manager = MagicMock()
    manager.__enter__.return_value = memory
    trainer._process_memory = Mock(return_value=manager)
    return trainer, memory, snapshot, values


@pytest.mark.parametrize('property_error', [False, True])
def test_new_unit_with_no_hp_property_still_maps_native_identity(mapping, property_error):
    trainer, memory, snapshot, _ = mapping
    if property_error:
        trainer._property_from_owner.side_effect = OSError('property unreadable')
    candidate = trainer._selected_candidates_snapshot(memory)[0][0]
    assert candidate.native_snapshot is snapshot
    assert candidate.handle == snapshot.full_handle
    assert candidate.base == candidate.hp_current_address == candidate.x_address == 0
    assert trainer._panel_from_candidate(memory, candidate).current_hp == 100
    assert trainer._position_from_candidate(memory, candidate) == (10, 20)
    assert trainer._elephant_selected_candidate(memory).native_snapshot is snapshot


@pytest.mark.parametrize('attribute', ['handle', 'owner_address', 'unit_address', 'full_handle'])
def test_incomplete_native_identity_cannot_publish_selection(mapping, attribute):
    trainer, memory, snapshot, _ = mapping
    trainer.persistent_native_selected_snapshots.return_value = (replace(snapshot, **{attribute:0}),)
    with pytest.raises(RuntimeError):
        trainer._selected_candidates_snapshot(memory)
    assert trainer._unit_owner_index == {}


def test_native_identity_mapping_never_reads_external_memory(mapping):
    trainer, memory, _, _ = mapping
    for name in ('read','read_u64','read_u32','read_f32','regions'):
        getattr(memory,name).side_effect = AssertionError('external identity lookup')
    assert trainer._elephant_selected_candidate(memory).native_snapshot is not None
    assert memory.mock_calls == []
    trainer._property_from_owner.assert_not_called()


def test_public_field_read_and_write_work_without_external_hp_block(mapping):
    trainer, memory, snapshot, _ = mapping
    # All other external optional fields are unavailable.
    memory.read_f32.side_effect = OSError('optional property missing')
    memory.read_i32.side_effect = OSError('optional property missing')
    panel, candidate, fields = trainer.read_selected_unit_fields()
    assert panel.current_hp == snapshot.hp
    assert next(f for f in fields if f.key == 'hp_current').native_write
    assert candidate.hp_current_address == 0
    fresh = replace(snapshot, hp=170)
    trainer._run_native_helper_ops.side_effect = [[snapshot_result(snapshot)], [], [snapshot_result(fresh)]]
    result = trainer.write_selected_unit_field('hp_current', 170)
    assert result.value == 170
    handle, ops = trainer._run_native_helper_ops.call_args_list[1].args
    assert handle == snapshot.handle
    assert ops[0][2:] == (snapshot.unit_address, snapshot.full_handle, snapshot.owner_address)
    memory.write_f32.assert_not_called()


def test_second_invalid_unit_does_not_publish_partial_index(mapping):
    trainer, memory, snapshot, _ = mapping
    invalid = replace(snapshot, full_handle=snapshot.full_handle + 1)
    with pytest.raises(RuntimeError):
        trainer._selected_candidates_snapshot(memory, persistent_snapshots=(snapshot, invalid))
    assert trainer._unit_owner_index == {}


def test_display_identity_write_keeps_native_path_without_hp_metadata(mapping):
    trainer, memory, snapshot, _ = mapping
    trainer._last_persistent_native_snapshots = (snapshot,)
    memory.read_f32.side_effect = OSError('optional property missing')
    memory.read_i32.side_effect = OSError('optional property missing')
    fresh = replace(snapshot, hp=180)
    trainer._run_native_helper_ops.side_effect = [[snapshot_result(snapshot)], [], [snapshot_result(fresh)]]
    result = trainer.write_unit_field_by_identity(snapshot.full_handle, snapshot.owner_address,
                                                 snapshot.unit_address, 'hp_current', 180)
    assert result.value == 180
    memory.write_f32.assert_not_called()


def test_old_display_identity_cannot_use_new_generation_snapshot(mapping):
    trainer, memory, snapshot, values = mapping
    trainer._last_persistent_native_snapshots = (replace(snapshot, full_handle=snapshot.full_handle + 1),)
    values[snapshot.owner_address + 0x20] = snapshot.full_handle + 1
    with pytest.raises(RuntimeError):
        trainer.write_unit_field_by_identity(snapshot.full_handle, snapshot.owner_address,
                                             snapshot.unit_address, 'hp_current', 180)
    trainer._run_native_helper_ops.assert_not_called()
