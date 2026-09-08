"""Read real bounded property lists while simulating object membership changes."""
from unittest.mock import Mock

import pytest
import war3_reforged_trainer as module


@pytest.mark.parametrize('change', ['replace', 'remove', 'add_to_empty', 'wrong_owner',
                                  'change_kind', 'unreadable'])
def test_property_mapping_tracks_current_list_not_owner_address(change):
    trainer = module.War3Trainer.__new__(module.War3Trainer)
    # Seed the old cache contract so this regression also fails on the baseline.
    trainer._owner_properties_cache = {}
    owner, array, first, second = (0x100002000, 0x100003000, 0x100004000, 0x100005000)
    values = {
        owner+0xa0: array, owner+0xa8: 8, owner+0xb0: 0, owner+0xb8: 0,
        array: 0 if change == 'add_to_empty' else first,
        first+0x18: trainer.PROP_TAG, first+0x50: owner, first+0x78: 1 << 32,
        second+0x18: trainer.PROP_TAG, second+0x50: owner, second+0x78: 1 << 32,
    }
    def read(address):
        if address not in values:
            raise OSError('unreadable')
        return values[address]
    memory = Mock()
    memory.read_u64.side_effect = read
    memory.regions.side_effect = AssertionError('No process region walk')
    memory.scan_bytes_private.side_effect = AssertionError('No heap search')
    assert trainer._owner_properties(memory, owner) == ({} if change == 'add_to_empty' else {1: first})

    expected = {}
    if change in ('replace', 'add_to_empty'):
        # The detached first object remains readable and tagged correctly.
        # Revalidating its tag alone would still incorrectly accept it.
        values[array] = second
        expected = {1: second}
    elif change == 'remove':
        values[array] = 0
    elif change == 'wrong_owner':
        values[first+0x50] = owner+8
    elif change == 'change_kind':
        values[first+0x78] = 2 << 32
        expected = {2: first}
    elif change == 'unreadable':
        del values[first+0x18]
    assert trainer._owner_properties(memory, owner) == expected
    memory.regions.assert_not_called()
    memory.scan_bytes_private.assert_not_called()
