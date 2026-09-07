"""Native hero field semantics and write permissions without a game process."""
from dataclasses import replace
from unittest.mock import Mock

import pytest
import war3_reforged_trainer as module
from test_native_snapshot_binding import make_snapshot, make_candidate, snapshot_result


def context(has_component=True, hero=True):
    trainer = object.__new__(module.War3Trainer)
    snapshot = make_snapshot()
    if not hero:
        snapshot = replace(snapshot, hero_level=0, hero_xp=0, strength=0, agility=0,
                           intelligence=0, base_strength=0, base_agility=0, base_intelligence=0)
    candidate = make_candidate(snapshot)
    memory = Mock()
    for name in ('read_f32', 'read_i32', 'read_u32', 'read_u64'):
        getattr(memory, name).side_effect = OSError('No external field data')
    trainer._selected_components = Mock(return_value={'hero': (0, 0x5000)} if has_component else {})
    trainer._ability_instances_from_candidate = Mock(return_value=[])
    trainer._inventory_items_from_candidate = Mock(return_value=[])
    trainer._get_hero_intelligence_pair_via_native_internal = Mock(side_effect=AssertionError('Unexpected second stat query'))
    return trainer, memory, candidate


@pytest.mark.parametrize('has_component', [False, True])
def test_base_and_total_are_distinct_even_when_external_fields_unreadable(has_component):
    trainer, memory, candidate = context(has_component)
    fields = {field.key: field for field in trainer._unit_fields_from_candidate(memory, candidate)}
    assert fields['base_strength'].value == 4
    assert fields['base_agility'].value == 5
    assert fields['base_intelligence'].value == 6
    assert fields['strength_total'].value == 10
    assert fields['agility_total'].value == 20
    assert fields['intelligence_total'].value == 30
    assert fields['hero_level'].value == 5
    assert fields['hero_level'].address == 0
    assert not fields['hero_level'].writable
    assert not fields['strength_total'].writable
    assert not fields['agility_total'].writable
    assert fields['base_strength'].writable == has_component
    trainer._get_hero_intelligence_pair_via_native_internal.assert_not_called()


@pytest.mark.parametrize('key', ['hero_level', 'strength_total', 'agility_total'])
def test_generic_field_writer_cannot_write_guessed_hero_addresses(key):
    trainer, memory, candidate = context()
    with pytest.raises(RuntimeError):
        trainer._write_unit_fields_to_candidate(memory, candidate, [module.MemoryWriteSpec(key, 0, '', 77)])
    memory.write_i32.assert_not_called()
    memory.write_f32.assert_not_called()


def test_nonhero_does_not_display_hero_stats():
    trainer, memory, candidate = context(False, False)
    fields = {field.key for field in trainer._unit_fields_from_candidate(memory, candidate)}
    assert not fields.intersection({'hero_level', 'base_strength', 'base_agility', 'base_intelligence',
                                    'strength_total', 'agility_total', 'intelligence_total'})


def test_protocol_decodes_signed_stats_and_rejects_previous_fixed_header():
    trainer, _, candidate = context()
    result = snapshot_result(candidate.native_snapshot)
    payload = list(result.extra_results)
    for index in (14, 15, 16, 140, 141, 142):
        payload[index] = (1 << 64) - 3
    snapshot = trainer._parse_persistent_native_snapshots(replace(result, extra_results=tuple(payload)))[0]
    assert (snapshot.strength, snapshot.agility, snapshot.intelligence,
            snapshot.base_strength, snapshot.base_agility, snapshot.base_intelligence) == (-3,) * 6
    with pytest.raises(RuntimeError):
        trainer._parse_persistent_native_snapshots(replace(result, extra_results=result.extra_results[:140]))
