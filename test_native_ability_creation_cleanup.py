"""Creation must preserve errors and clean up only the still-bound unit."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import war3_reforged_trainer as module
from test_native_snapshot_binding import make_candidate, make_snapshot


@pytest.fixture
def creation():
    trainer = module.War3Trainer.__new__(module.War3Trainer)
    candidate = make_candidate(make_snapshot())
    memory = Mock()
    trainer._discover_native_ability_internals = Mock(return_value=SimpleNamespace(
        begin_address=0x100000, add_address=0x100100, end_address=0x100200,
        refresh_address=0x100300))
    trainer._ability_instances_from_candidate = Mock(return_value=[])
    trainer._run_native_helper_ops = Mock(return_value=[
        module.NativeHelperOpResult(136, 1),
        module.NativeHelperOpResult(30, 0), module.NativeHelperOpResult(32, 0x200000),
        module.NativeHelperOpResult(33, 0)])
    instance = SimpleNamespace(data_address=0x200000)
    trainer._native_ability_metadata = Mock(return_value=(instance, 200, 1))
    trainer._refresh_native_candidate = Mock(return_value=candidate)
    trainer._remove_engine_ability_instance = Mock()
    return trainer, memory, candidate, instance


def test_created_skill_does_not_need_to_exist_in_snapshot(creation):
    trainer, memory, candidate, instance = creation
    rawcode = 0x41393939
    assert rawcode not in candidate.native_snapshot.ability_ids
    assert trainer._create_engine_ability_instance(memory, candidate, rawcode) == (instance, True)
    trainer._remove_engine_ability_instance.assert_not_called()


@pytest.mark.parametrize('existing', [False, True])
def test_preexisting_skill_or_failed_precheck_never_creates_or_cleans(creation, existing):
    trainer, memory, candidate, instance = creation
    if existing:
        trainer._ability_instances_from_candidate.return_value = [instance]
        assert trainer._create_engine_ability_instance(memory, candidate, 0x41393939) == (instance, False)
    else:
        trainer._ability_instances_from_candidate.side_effect = RuntimeError('precheck failed')
        with pytest.raises(RuntimeError, match='precheck failed'):
            trainer._create_engine_ability_instance(memory, candidate, 0x41393939)
    trainer._run_native_helper_ops.assert_not_called()
    trainer._remove_engine_ability_instance.assert_not_called()


def test_engine_refusal_has_no_created_object_to_clean(creation):
    trainer, memory, candidate, _ = creation
    trainer._run_native_helper_ops.return_value[2] = module.NativeHelperOpResult(32, 0)
    with pytest.raises(RuntimeError):
        trainer._create_engine_ability_instance(memory, candidate, 0x41393939)
    trainer._native_ability_metadata.assert_not_called()
    trainer._remove_engine_ability_instance.assert_not_called()


@pytest.mark.parametrize('stage', ['refresh', 'lookup', 'wrong_object'])
def test_post_creation_failure_cleans_only_created_object_and_preserves_cause(creation, stage):
    trainer, memory, candidate, _ = creation
    error = RuntimeError('refresh rejected') if stage == 'refresh' else OSError('lookup failed')
    if stage == 'refresh':
        trainer._run_native_helper_ops.side_effect = [trainer._run_native_helper_ops.return_value, error]
    elif stage == 'lookup':
        trainer._native_ability_metadata.side_effect = error
    else:
        trainer._native_ability_metadata.return_value = (SimpleNamespace(data_address=0x300000), 201, 1)
    with pytest.raises((RuntimeError, OSError)) as caught:
        trainer._create_engine_ability_instance(memory, candidate, 0x41393939)
    if stage != 'wrong_object':
        assert caught.value is error
    trainer._refresh_native_candidate.assert_called_once_with(candidate)
    trainer._remove_engine_ability_instance.assert_called_once_with(memory, candidate, 0x200000)
    trainer._ability_instances_from_candidate.assert_called_once()


def test_changed_unit_is_not_cleaned_up_using_stale_pointer(creation):
    trainer, memory, candidate, _ = creation
    original = RuntimeError('lookup failed')
    trainer._native_ability_metadata.side_effect = original
    trainer._refresh_native_candidate.side_effect = RuntimeError('unit recycled')
    with pytest.raises(RuntimeError) as caught:
        trainer._create_engine_ability_instance(memory, candidate, 0x41393939)
    assert 'unit recycled' in str(caught.value)
    assert 'lookup failed' in str(caught.value)
    assert caught.value.__cause__ is original
    trainer._remove_engine_ability_instance.assert_not_called()


def test_cleanup_failure_reports_both_errors(creation):
    trainer, memory, candidate, _ = creation
    original = RuntimeError('lookup failed')
    trainer._native_ability_metadata.side_effect = original
    trainer._remove_engine_ability_instance.side_effect = RuntimeError('remove failed')
    with pytest.raises(RuntimeError) as caught:
        trainer._create_engine_ability_instance(memory, candidate, 0x41393939)
    assert 'lookup failed' in str(caught.value) and 'remove failed' in str(caught.value)
    assert caught.value.__cause__ is original
