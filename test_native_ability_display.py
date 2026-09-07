"""Native field lists must not depend on ability wrapper proximity."""
from dataclasses import replace
from unittest.mock import Mock

import pytest
import war3_reforged_trainer as module
from test_native_hero_fields import context


@pytest.mark.parametrize('hero,component', [(False, False), (True, False), (True, True)])
@pytest.mark.parametrize('count', [0, 1, 49, 300])
def test_engine_ability_list_is_complete_for_every_unit_kind(hero, component, count):
    trainer, memory, candidate = context(component, hero)
    ids = tuple(0x41303030 + i for i in range(count))
    levels = tuple(i % 10 + 1 for i in range(count))
    snapshot = replace(candidate.native_snapshot, ability_ids=ids, ability_levels=levels)
    candidate = replace(candidate, native_snapshot=snapshot)
    trainer._ability_instances_from_candidate = Mock(side_effect=AssertionError('Unexpected wrapper scan'))
    # A concurrent read must not replace the payload owned by this candidate.
    trainer._last_persistent_native_snapshots = (replace(snapshot, ability_ids=(0x42424242,), ability_levels=(99,)),)
    fields = trainer._unit_fields_from_candidate(memory, candidate)
    ability_fields = [field for field in fields if field.key.startswith('ability_')]
    assert [field.value for field in ability_fields[::2]] == list(ids)
    assert [field.value for field in ability_fields[1::2]] == list(levels)
    assert len({field.key for field in fields}) == len(fields)
    assert all(field.address == 0 and not field.writable for field in ability_fields)
    trainer._ability_instances_from_candidate.assert_not_called()


def test_ability_list_changes_with_new_snapshot_and_can_be_empty():
    trainer, memory, candidate = context(True, True)
    trainer._ability_instances_from_candidate = Mock(side_effect=AssertionError('Unexpected cache or wrapper scan'))
    for ids, levels in [((0x41414141, 0x42424242), (1, 3)), ((0x43434343,), (2,)), ((), ())]:
        fresh = replace(candidate, native_snapshot=replace(candidate.native_snapshot, ability_ids=ids, ability_levels=levels))
        fields = trainer._unit_fields_from_candidate(memory, fresh)
        assert [f.value for f in fields if f.key.startswith('ability_') and f.key.endswith('_rawcode')] == list(ids)


def test_mismatched_native_arrays_are_not_silently_truncated():
    trainer, memory, candidate = context(False, False)
    candidate = replace(candidate, native_snapshot=replace(candidate.native_snapshot, ability_levels=()))
    with pytest.raises(RuntimeError, match='different lengths'):
        trainer._unit_fields_from_candidate(memory, candidate)


def test_displayed_ability_identity_is_not_an_address_write_target():
    trainer, memory, candidate = context(False, False)
    with pytest.raises(RuntimeError):
        trainer._write_unit_fields_to_candidate(memory, candidate, [module.MemoryWriteSpec('ability_01_rawcode', 0, '', 'A000')])
    memory.write_u32.assert_not_called()
