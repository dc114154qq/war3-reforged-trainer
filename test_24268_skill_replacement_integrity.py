"""24268 replacement must never relabel an existing ability as another class."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import war3_reforged_trainer as module


@pytest.mark.parametrize("instance_count", [0, 1, 2])
@pytest.mark.parametrize("new_rawcode", [0x41303031, 0x41303039])
def test_missing_engine_replacement_never_mutates_runtime_tags(instance_count, new_rawcode):
    trainer = object.__new__(module.War3Trainer)
    trainer._native_selection_unavailable = True
    trainer._native_snapshot_for_candidate = Mock(return_value=None)
    trainer._selected_components = Mock(return_value={"hero": (0x4000, 0x5000)})
    instance = SimpleNamespace(rawcode=0x41303031, wrapper_tag_address=0x6018,
                               rawcode_address=0x7070, mirror_rawcode_address=0x7078)
    trainer._ability_instances_from_candidate = Mock(return_value=[instance] * instance_count)
    trainer._run_native_helper_ops = Mock()
    candidate = SimpleNamespace(owner_address=0x4000)
    field = module.UnitMemoryField("skill1_name", "skill", "rawcode", 0x41303031,
                                   0x51BC, "skill")
    values = {0x51BC: 0x41303031, 0x51D4: 0x41303031,
              0x7070: 0x41303031, 0x7078: 0x41303031,
              0x6018: 0x414873742b61676c}
    original = dict(values)
    memory = Mock()
    memory.read_u32.side_effect = lambda address: values[address]
    memory.read_u64.side_effect = lambda address: values[address]
    memory.write_u32.side_effect = lambda address, value: values.__setitem__(address, value)
    memory.write_u64.side_effect = lambda address, value: values.__setitem__(address, value)
    with pytest.raises(RuntimeError, match="3.0.*引擎"):
        trainer._write_hero_skill_name_field(memory, candidate, field, new_rawcode)
    assert values == original
    memory.write_u32.assert_not_called()
    memory.write_u64.assert_not_called()
    trainer._run_native_helper_ops.assert_not_called()
