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
                for i, name in enumerate(module.War3Trainer.ABILITY_FIELD_NATIVE_NAMES)}
    context = module.SelectedAbilityFieldContext(candidate, 1, 200, 0x41303031, 0x41487374,
                                               True, '', 4, handlers, (200, 0x200000, 0x987600005432))
    trainer._selected_ability_field_context_locked = Mock(return_value=context)
    trainer._native_helper_transaction = Mock(side_effect=lambda: nullcontext())
    trainer._ability_field_write_disabled = False
    trainer._run_native_helper_ops = Mock()
    spec = module.ABILITY_FIELD_BY_KEY[('abpx', 'integer', 'field')]
    snapshot = module.AbilityFieldSnapshot(0x41303031, 0x41487374, 4, 1, (),
        context.unit_identity, ability_identity=context.ability_identity)
    return trainer, context, spec, snapshot


def response(value):
    return [module.NativeHelperOpResult(136, 1), module.NativeHelperOpResult(142, 200),
            module.NativeHelperOpResult(143, 0), module.NativeHelperOpResult(110, value)]


def test_write_original_and_readback_all_carry_same_full_ability_identity(setup):
    trainer, context, spec, snapshot = setup
    trainer._run_native_helper_ops.side_effect = [response(1), response(1), response(2)]
    assert trainer.set_selected_ability_field('A001', 1, spec, 2, snapshot).value == 2
    assert trainer._run_native_helper_ops.call_count == 3
    for call in trainer._run_native_helper_ops.call_args_list:
        handle, ops = call.args
        assert handle == context.unit_handle != context.ability_handle
        assert [op[0] for op in ops[:3]] == [136, 142, 143]
        assert ops[1][2:] == context.ability_identity
        assert ops[2][1] == context.effect_class and ops[2][4] == context.current_level


def test_recreated_ability_with_same_unit_id_and_level_cannot_write_from_old_ui_snapshot(setup):
    trainer, context, spec, snapshot = setup
    stale = replace(snapshot, ability_identity=(200, context.ability_identity[1], context.ability_identity[2]+1))
    with pytest.raises(RuntimeError, match='技能实例已经变化'):
        trainer.set_selected_ability_field('A001', 1, spec, 2, stale)
    trainer._run_native_helper_ops.assert_not_called()


def test_failed_write_recovery_keeps_original_identity_guards(setup):
    trainer, context, spec, snapshot = setup
    trainer._run_native_helper_ops.side_effect = [response(1), RuntimeError('instance changed'), RuntimeError('instance changed')]
    with pytest.raises(RuntimeError): trainer.set_selected_ability_field('A001', 1, spec, 2, snapshot)
    assert trainer._ability_field_write_disabled
    for call in trainer._run_native_helper_ops.call_args_list:
        assert call.args[1][1][2:] == context.ability_identity


def test_bulk_field_reads_reserve_guard_slots_and_keep_identity_in_snapshot(setup):
    trainer, context, _, _ = setup
    def run(unit, ops):
        assert unit == 1 and len(ops) <= trainer.NATIVE_HELPER_MAX_OPS
        assert [op[0] for op in ops[:3]] == [136, 142, 143]
        return [module.NativeHelperOpResult(op[0], 0) for op in ops]
    trainer._run_native_helper_ops.side_effect = run
    snapshot = trainer.read_selected_ability_fields('A001', 1)
    assert snapshot.ability_identity == context.ability_identity
    assert trainer._run_native_helper_ops.call_count > 1


def test_failed_batch_does_not_publish_partial_field_snapshot(setup):
    trainer, _, _, _ = setup
    trainer._run_native_helper_ops.side_effect = RuntimeError('identity changed')
    with pytest.raises(RuntimeError): trainer.read_selected_ability_fields('A001', 1)
    trainer._run_native_helper_ops.assert_called_once()
