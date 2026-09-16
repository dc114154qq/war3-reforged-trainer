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


def test_engine_replacement_binds_ability_rows_by_handle():
    trainer = object.__new__(module.War3Trainer)
    trainer._native_selection_unavailable = True
    candidate = SimpleNamespace(
        owner_address=0x4000,
        unit_address=0x6000,
        handle=7,
    )
    trainer._selected_candidates_snapshot = Mock(return_value=[(candidate, 7)])
    trainer._selected_components = Mock(return_value={"hero": (0x4800, 0x5000)})

    old_rawcode = 0x41303031
    new_rawcode = 0x41303039
    values = {
        0x5068: candidate.unit_address,
        0x51BC: old_rawcode,
        0x51D4: old_rawcode,
        **{0x51BC + slot * 4: (old_rawcode if slot == 0 else 0) for slot in range(5)},
    }
    memory = Mock()
    memory.read_u64.side_effect = lambda address: values[address]
    memory.read_u32.side_effect = lambda address: values[address]
    memory.write_u32.side_effect = lambda address, value: values.__setitem__(address, value)

    def ability_batch(rawcode, action=0, level=0):
        if action == 0:
            after = 3 if rawcode == old_rawcode else 0
        elif action == 2:
            after = 0
        else:
            after = level
        return {"rows": [{"handle": 7, "before": after, "after": after}]}

    trainer.ability_batch_24268 = Mock(side_effect=ability_batch)
    field = module.UnitMemoryField(
        "skill1_name", "skill", "rawcode", old_rawcode, 0x51BC, "skill",
    )

    result = trainer._write_hero_skill_name_field_24268(
        memory, candidate, field, 0, new_rawcode,
    )

    assert result.value == new_rawcode
    assert values[0x51BC] == new_rawcode
    assert values[0x51D4] == new_rawcode
    assert [call.args[:2] for call in trainer.ability_batch_24268.call_args_list] == [
        (old_rawcode, 0),
        (new_rawcode, 0),
        (old_rawcode, 2),
        (new_rawcode, 1),
    ]
