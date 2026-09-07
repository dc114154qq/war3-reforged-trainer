"""Exercise actual basic-write command construction, without a game process."""
from dataclasses import replace
from unittest.mock import Mock
import threading

import pytest
import war3_reforged_trainer as module
from test_native_snapshot_binding import make_snapshot, make_candidate, snapshot_result


@pytest.fixture
def context():
    trainer = object.__new__(module.War3Trainer)
    snapshot = make_snapshot()
    candidate = make_candidate(snapshot)
    trainer._last_persistent_native_snapshots = ()
    trainer.persistent_native_init = Mock()
    trainer.persistent_native_selected_snapshots = Mock(side_effect=AssertionError("Unexpected selection query"))
    trainer._native_handlers = {}
    trainer._elephant_handlers = Mock(side_effect=lambda pm, names: {
        name: module.NativeHandler(name, 0, index + 100)
        for index, name in enumerate(names)
    })
    trainer._run_native_helper_ops = Mock(return_value=[snapshot_result(snapshot)])
    memory = Mock()
    memory.read_f32.side_effect = AssertionError("Unexpected address read")
    memory.write_f32.side_effect = AssertionError("Unexpected address write")
    return trainer, memory, candidate, snapshot


def test_vitals_and_position_use_jass_handle_in_one_write_batch(context):
    trainer, memory, candidate, snapshot = context
    trainer._write_basic_unit_values_to_candidate(memory, candidate, 300, 90, target_x=123)
    calls = trainer._run_native_helper_ops.call_args_list
    assert len(calls) == 3  # Targeted validation/read, all setters, targeted readback.
    for call in calls:
        handle, ops = call.args
        assert handle == snapshot.handle != candidate.handle
        payload = trainer._pack_native_helper_command(handle, ops)
        assert trainer.NATIVE_HELPER_HEADER_STRUCT.unpack_from(payload)[4] == snapshot.handle
    ops = calls[1].args[1]
    assert [op[0] for op in ops] == [136, 135, 134, 135, 134, 94]
    assert ops[0][2:] == (candidate.unit_address, candidate.handle, candidate.owner_address)
    assert [ops[1][3], ops[3][3]] == [300, 90]
    assert trainer._float_from_bits(ops[-1][1]) == 123
    assert trainer._float_from_bits(ops[-1][3]) == snapshot.y
    trainer.persistent_native_selected_snapshots.assert_not_called()

    # Exercise the real whitelist and serializer too, not just a mocked entry.
    trainer._native_helper_command_path = Mock(return_value="offline-command")
    trainer._write_native_helper_command = Mock()
    trainer._native_helper_batch_hook = 1
    trainer._native_helper_batch_thread_id = threading.get_ident()
    trainer._wait_native_helper_result = Mock(return_value=[])
    trainer._run_native_helper_ops_locked(snapshot.handle, ops)
    payload = trainer._write_native_helper_command.call_args.args[1]
    header = trainer.NATIVE_HELPER_HEADER_STRUCT.unpack_from(payload)
    assert header[3:5] == (6, snapshot.handle)
    base = trainer.NATIVE_HELPER_HEADER_STRUCT.size
    size = trainer.NATIVE_HELPER_OP_STRUCT.size
    assert [trainer.NATIVE_HELPER_OP_STRUCT.unpack_from(payload, base + i * size)[:5]
            for i in range(6)] == list(ops)


@pytest.mark.parametrize('kwargs', [dict(target_hp=1e20), dict(max_mp=-1), dict(target_y=1e7)])
def test_invalid_request_never_submits_any_mutation(context, kwargs):
    trainer, memory, candidate, _ = context
    with pytest.raises(ValueError):
        trainer._write_basic_unit_values_to_candidate(memory, candidate, **{"target_hp": None, "target_mp": None, **kwargs})
    assert all(call.args[1][0][0] == 133 for call in trainer._run_native_helper_ops.call_args_list)
    memory.write_f32.assert_not_called()


def test_identity_failure_prevents_all_writes(context):
    trainer, memory, candidate, snapshot = context
    trainer._run_native_helper_ops.return_value = [snapshot_result(replace(snapshot, full_handle=0xBAD))]
    with pytest.raises(RuntimeError):
        trainer._write_basic_unit_values_to_candidate(memory, candidate, 150, None)
    assert trainer._run_native_helper_ops.call_count == 1
    assert trainer._run_native_helper_ops.call_args.args[1][0][0] == 133
    memory.write_f32.assert_not_called()


def test_missing_native_members_does_not_enable_memory_fallback(context):
    trainer, memory, candidate, _ = context
    del trainer._native_handlers
    trainer._write_basic_unit_values_to_candidate(memory, candidate, 150, None)
    assert trainer._run_native_helper_ops.call_args.args[0] == candidate.native_snapshot.handle
    memory.write_f32.assert_not_called()


def test_returned_candidate_contains_targeted_post_write_values(context):
    trainer, memory, candidate, snapshot = context
    fresh = replace(snapshot, hp=150)
    trainer._run_native_helper_ops.side_effect = [
        [snapshot_result(snapshot)], [], [snapshot_result(fresh)],
    ]
    result = trainer._write_basic_unit_values_to_candidate(memory, candidate, 150, None)
    assert result.native_snapshot.hp == 150
    assert candidate.native_snapshot.hp == 100
    trainer.persistent_native_selected_snapshots.assert_not_called()


def test_native_failure_does_not_fall_back_to_address_writes(context):
    trainer, memory, candidate, snapshot = context
    trainer._run_native_helper_ops.side_effect = [
        [snapshot_result(snapshot)], RuntimeError("native setter failed"),
    ]
    with pytest.raises(RuntimeError, match="native setter failed"):
        trainer._write_basic_unit_values_to_candidate(memory, candidate, 150, None)
    memory.write_f32.assert_not_called()


def test_unbound_identity_must_match_native_selection_before_writing(context):
    trainer, memory, candidate, snapshot = context
    manual = replace(candidate, native_snapshot=None, selection_source="memory")
    trainer.persistent_native_selected_snapshots.side_effect = None
    trainer.persistent_native_selected_snapshots.return_value = (replace(snapshot, full_handle=0xBAD),)
    with pytest.raises(RuntimeError):
        trainer._write_basic_unit_values_to_candidate(memory, manual, 150, None)
    trainer._run_native_helper_ops.assert_not_called()
    memory.write_f32.assert_not_called()
