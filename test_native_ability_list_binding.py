from unittest.mock import Mock
import pytest
import war3_reforged_trainer as module
from test_native_snapshot_binding import make_candidate, make_snapshot


def test_persistent_native_ability_list_never_enters_wrapper_scan():
    trainer = module.War3Trainer.__new__(module.War3Trainer)
    snapshot = make_snapshot(); candidate = make_candidate(snapshot)
    trainer._persistent_native_initialized = True
    trainer._native_snapshot_for_candidate = Mock(return_value=snapshot)
    trainer._query_native_table_handlers = Mock(return_value={
        name: module.NativeHandler(name, 0, 0x1000+i)
        for i, name in enumerate(("BlzGetUnitAbilityByIndex", "BlzGetAbilityId", "GetUnitAbilityLevel"))
    })
    instance = module.AbilityInstance(0, 0x3000, 0x2000, 0x4000, 0x5000, 0x3018,
                                      0x4148737400000000, 0x6000, 0x41487374, snapshot.ability_ids[0],
                                      0x2010, 0, 0, 0)
    row = (200, 0x2000, 0x3000, 0x987600005432, 0x4148737400000000,
           0x4000, 0x5000, snapshot.ability_ids[0], 2, 0)
    trainer._run_native_helper_ops = Mock(return_value=(
        module.NativeHelperOpResult(136, 1), module.NativeHelperOpResult(146, 1, extra_results=row)))
    trainer._near_ability_instances_from_candidate = Mock(side_effect=AssertionError("wrapper scan"))
    trainer._global_ability_instances_from_candidate = Mock(side_effect=AssertionError("global scan"))
    result = trainer._ability_instances_from_candidate(Mock(), candidate, allow_global_scan=True)
    assert result[0].slot == 1 and result[0].rawcode == snapshot.ability_ids[0]
    trainer._near_ability_instances_from_candidate.assert_not_called()
    trainer._global_ability_instances_from_candidate.assert_not_called()


def test_persistent_native_ability_list_rejects_duplicate_bound_object():
    trainer = module.War3Trainer.__new__(module.War3Trainer)
    snapshot = make_snapshot(); candidate = make_candidate(snapshot)
    trainer._persistent_native_initialized = True
    trainer._native_snapshot_for_candidate = Mock(return_value=snapshot)
    trainer._query_native_table_handlers = Mock(return_value={
        name: module.NativeHandler(name, 0, 0x1000+i)
        for i, name in enumerate(("BlzGetUnitAbilityByIndex", "BlzGetAbilityId", "GetUnitAbilityLevel"))
    })
    instance = module.AbilityInstance(0, 0x3000, 0x2000, 0, 0, 0, 0, 0x6000, 0x41487374,
                                      snapshot.ability_ids[0], 0)
    row = (200, 0x2000, 0x3000, 0x987600005432, 0x4148737400000000,
           0x4000, 0x5000, snapshot.ability_ids[0], 2, 0)
    trainer._run_native_helper_ops = Mock(return_value=(
        module.NativeHelperOpResult(136, 1), module.NativeHelperOpResult(146, 2, extra_results=row+row)))
    snapshot = module.replace(snapshot, ability_ids=(snapshot.ability_ids[0], snapshot.ability_ids[0]))
    trainer._native_snapshot_for_candidate.return_value = snapshot
    with pytest.raises(RuntimeError, match="重复"):
        trainer._ability_instances_from_candidate(Mock(), candidate)
