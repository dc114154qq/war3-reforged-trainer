"""Native skill metadata must not fall back to wrapper or component scanning."""
from dataclasses import replace
from unittest.mock import Mock
import pytest
import war3_reforged_trainer as module
from test_native_snapshot_binding import make_candidate, make_snapshot


@pytest.fixture
def setup():
    trainer = module.War3Trainer.__new__(module.War3Trainer)
    candidate = make_candidate(make_snapshot())
    handlers = {name: module.NativeHandler(name, 0, 0x100000 + i*0x100)
                for i, name in enumerate(('BlzGetUnitAbility', 'BlzGetAbilityId'))}
    trainer._query_native_table_handlers = Mock(return_value=handlers)
    metadata = (200, 0x200000, 0x300000, 0x987600005432, 0x4148737430303030,
                0x400000, 0x500000, 0x41303031, 4, 0x600000)
    trainer._run_native_helper_ops = Mock(return_value=(
        module.NativeHelperOpResult(136, 1, extra_results=metadata),
        module.NativeHelperOpResult(141, 200),
    ))
    trainer._scan_bytes_private_between = Mock(side_effect=AssertionError('No neighborhood scan'))
    trainer._find_engine_ability_data = Mock(side_effect=AssertionError('No separate ability data query'))
    memory = Mock()
    return trainer, candidate, handlers, metadata, memory


@pytest.mark.parametrize('hero_level', [0, 7])
def test_field_context_gets_handle_level_and_effect_class_together_without_external_reads(setup, hero_level):
    trainer, candidate, handlers, _, memory = setup
    candidate = replace(candidate, native_snapshot=replace(candidate.native_snapshot, hero_level=hero_level))
    context = trainer._ability_field_context_from_candidate_locked(memory, candidate, 1, 'A001', 1, handlers)
    assert (context.ability_handle, context.current_level, context.effect_class) == (200, 4, 0x41487374)
    assert context.effect_class_verified
    trainer._run_native_helper_ops.assert_called_once_with(1, (
        (136, 0, candidate.unit_address, candidate.handle, candidate.owner_address),
        (141, 0x41303031, handlers['BlzGetUnitAbility'].handler_address,
         handlers['BlzGetAbilityId'].handler_address, 0),
    ))
    assert memory.mock_calls == []
    trainer._find_engine_ability_data.assert_not_called()


def test_wrapper_lookup_uses_bound_metadata_and_rejects_a_different_data_object(setup):
    trainer, candidate, _, _, memory = setup
    instance = trainer._ability_instance_from_data_for_candidate(memory, candidate, 0x200000, 0x41303031)
    assert instance.wrapper_address == 0x300000 and instance.handle == 0x987600005432
    assert trainer._ability_instance_from_data_for_candidate(memory, candidate, 0x200008, 0x41303031) is None
    trainer._scan_bytes_private_between.assert_not_called()
    assert memory.mock_calls == []


@pytest.mark.parametrize('fault', ['exception', 'length', 'wrong_id', 'zero_handle', 'bad_class', 'wrong_result'])
def test_failed_metadata_is_not_recovered_by_scanning(setup, fault):
    trainer, candidate, _, metadata, memory = setup
    if fault == 'exception':
        trainer._run_native_helper_ops.side_effect = RuntimeError('Object recycled')
    else:
        row = list(metadata)
        if fault == 'length': row.pop()
        if fault == 'wrong_id': row[7] += 1
        if fault == 'zero_handle': row[3] = 0
        if fault == 'bad_class': row[4] = 0
        trainer._run_native_helper_ops.return_value = (
            module.NativeHelperOpResult(136, 1, extra_results=tuple(row)),
            module.NativeHelperOpResult(141, 201 if fault == 'wrong_result' else 200),
        )
    with pytest.raises(RuntimeError):
        trainer._ability_instance_from_data_for_candidate(memory, candidate, 0x200000, 0x41303031)
    trainer._scan_bytes_private_between.assert_not_called()
    assert memory.mock_calls == []


def test_mismatched_unit_handle_cannot_query_another_units_ability(setup):
    trainer, candidate, handlers, _, memory = setup
    with pytest.raises(RuntimeError):
        trainer._ability_field_context_from_candidate_locked(memory, candidate, 2, 'A001', 1, handlers)
    trainer._run_native_helper_ops.assert_not_called()


@pytest.mark.parametrize('compat', [False, True])
def test_display_identity_enters_same_native_path_in_both_ui_editions(setup, compat):
    from contextlib import nullcontext
    trainer, candidate, handlers, _, memory = setup
    trainer._process_memory = Mock(return_value=nullcontext(memory))
    trainer._candidate_from_display_identity = Mock(return_value=candidate)
    trainer._discover_native_handlers_near_table = Mock(return_value=handlers)
    trainer._recover_win10_native_handlers = Mock(side_effect=AssertionError('No compatibility recovery'))
    identity = (candidate.handle, candidate.owner_address, candidate.unit_address)
    context = trainer._ability_field_context_by_identity_locked('A001', 1, identity, compat)
    assert context.unit_identity == identity and context.effect_class_verified
    assert trainer._run_native_helper_ops.call_count == 1
    trainer._recover_win10_native_handlers.assert_not_called()
