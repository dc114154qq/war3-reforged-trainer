from contextlib import nullcontext
from dataclasses import replace
from unittest.mock import Mock
import pytest
import war3_reforged_trainer as module
from test_native_snapshot_binding import make_candidate, make_snapshot


@pytest.fixture
def setup():
    trainer = module.War3Trainer.__new__(module.War3Trainer)
    candidate = make_candidate(make_snapshot())
    handlers = {name: module.NativeHandler(name, 0, 0x100000+i*0x100)
                for i, name in enumerate(trainer.ITEM_FIELD_NATIVE_NAMES)}
    trainer._native_helper_transaction = Mock(side_effect=lambda: nullcontext())
    trainer._item_field_write_disabled = False
    trainer._run_native_helper_ops = Mock()
    memory = Mock()
    trainer._discover_native_handlers_near_table = Mock(return_value=handlers)
    context = trainer._item_field_context_from_candidate_locked(memory, candidate, 1, 1, handlers)
    trainer._item_field_context_by_identity_locked = Mock(return_value=context)
    spec = module.ITEM_FIELD_CATALOG[0]
    snapshot = module.ItemFieldSnapshot(1, 100, 0x49303031, (), context.unit_identity,
                                        item_identity=context.item_identity)
    return trainer, context, spec, snapshot, memory


def response(value):
    return [module.NativeHelperOpResult(136, 1), module.NativeHelperOpResult(144, 100),
            module.NativeHelperOpResult(145, 0), module.NativeHelperOpResult(115, value)]


def test_context_uses_snapshot_without_requerying_item_or_reading_components(setup):
    trainer, context, _, _, memory = setup
    assert context.item_identity == (100, 0x100005000, 0x123400000064)
    trainer._run_native_helper_ops.assert_not_called()
    assert memory.mock_calls == []


def test_write_and_readback_bind_unit_slot_and_full_item_identity(setup):
    trainer, context, spec, snapshot, _ = setup
    trainer._run_native_helper_ops.side_effect = [response(1), response(1), response(2)]
    assert trainer.set_selected_item_field(1, spec, 2, snapshot, unit_identity=context.unit_identity).value == 2
    for call in trainer._run_native_helper_ops.call_args_list:
        unit, ops = call.args
        assert unit == 1 and [op[0] for op in ops[:3]] == [136, 144, 145]
        assert ops[1][1] == 0 and ops[1][2:] == context.item_identity
        assert ops[2][1] == context.item_rawcode


def test_recycled_item_with_same_id_handle_and_address_rejects_old_field_snapshot(setup):
    trainer, context, spec, snapshot, _ = setup
    stale = replace(snapshot, item_identity=(100, context.item_identity[1], context.item_identity[2]+1))
    with pytest.raises(RuntimeError):
        trainer.set_selected_item_field(1, spec, 2, stale, unit_identity=context.unit_identity)
    trainer._run_native_helper_ops.assert_not_called()


def test_recovery_does_not_remove_item_guard(setup):
    trainer, context, spec, snapshot, _ = setup
    trainer._run_native_helper_ops.side_effect = [response(1), RuntimeError('changed'), RuntimeError('changed')]
    with pytest.raises(RuntimeError):
        trainer.set_selected_item_field(1, spec, 2, snapshot, unit_identity=context.unit_identity)
    assert trainer._item_field_write_disabled
    for call in trainer._run_native_helper_ops.call_args_list:
        assert call.args[1][1][2:] == context.item_identity


def test_bulk_reads_reduce_round_trips_and_preserve_catalog_order_and_identity(setup):
    trainer, context, _, _, _ = setup
    def run(unit, ops):
        assert unit == 1 and len(ops) <= trainer.NATIVE_HELPER_MAX_OPS
        return [module.NativeHelperOpResult(op[0], 0) for op in ops]
    trainer._run_native_helper_ops.side_effect = run
    snapshot = trainer.read_selected_item_fields(1, unit_identity=context.unit_identity)
    assert snapshot.item_identity == context.item_identity
    assert [field.spec for field in snapshot.fields] == list(module.ITEM_FIELD_CATALOG)
    supported = sum(spec.runtime_supported for spec in module.ITEM_FIELD_CATALOG)
    assert trainer._run_native_helper_ops.call_count == (supported+12)//13


def test_failed_batch_does_not_publish_partial_item_snapshot(setup):
    trainer, context, _, _, _ = setup
    trainer._run_native_helper_ops.side_effect = RuntimeError('slot changed')
    with pytest.raises(RuntimeError): trainer.read_selected_item_fields(1, unit_identity=context.unit_identity)
    trainer._run_native_helper_ops.assert_called_once()


@pytest.mark.parametrize('compat', [False, True])
def test_both_ui_editions_recover_bound_display_identity_without_legacy_recovery(setup, compat):
    trainer, context, _, _, memory = setup
    trainer._process_memory = Mock(return_value=nullcontext(memory))
    trainer._candidate_from_display_identity = Mock(return_value=context.candidate)
    trainer._recover_win10_native_handlers = Mock(side_effect=AssertionError('No legacy recovery'))
    result = module.War3Trainer._item_field_context_by_identity_locked(trainer, 1, context.unit_identity, compat)
    assert result.item_identity == context.item_identity
    trainer._recover_win10_native_handlers.assert_not_called()
