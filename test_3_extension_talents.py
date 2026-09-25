import struct
import threading
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from war3_3_extension_catalog import OFFICIAL_BACKPACKS
from war3_reforged_trainer import War3Trainer


def code(value):
    return int.from_bytes(value.encode("ascii"), "big")


def talent_snapshot(controller="ATug", *selected, controller_level=3):
    return {
        "target_unit": 0x101400,
        "bag_size": 30,
        "bag": (),
        "equipment": (),
        "abilities": {
            code(controller): controller_level,
            **{code(value): 1 for value in selected},
        },
    }


def test_talent_state_derives_native_total_used_and_remaining_points():
    trainer = object.__new__(War3Trainer)
    state = trainer.talent_state_24268(talent_snapshot("ATug", "UT1a", controller_level=4))
    assert state["controller"] == "ATug"
    assert state["name"] == "亡灵加雷克"
    assert state["total_points"] == 3
    assert state["used_points"] == 1
    assert state["remaining_points"] == 2


def test_talent_state_counts_multiple_native_choices_in_one_tier():
    trainer = object.__new__(War3Trainer)
    state = trainer.talent_state_24268(
        talent_snapshot("ATug", "UT1a", "UT1b", controller_level=4)
    )
    assert state["used_points"] == 2
    assert state["remaining_points"] == 1
    assert state["anomalies"] == ("第 1 层同时存在多个天赋",)


def test_grant_talent_point_uses_verified_native_controller_action():
    trainer = object.__new__(War3Trainer)
    before = talent_snapshot("ATug", "UT1a", controller_level=2)
    after = talent_snapshot("ATug", "UT1a", controller_level=3)
    engine = Mock()
    trainer._engine_instance_24268 = Mock(return_value=engine)
    trainer._coerce_memory_value = lambda _kind, value: code(value)
    trainer.extension_snapshot_24268 = Mock(side_effect=[before, after])
    trainer.item_batch_24268 = Mock(side_effect=AssertionError("Auto-consumed tome must not require an inventory slot"))
    trainer.grant_talent_point_24268()
    trainer.item_batch_24268.assert_not_called()
    engine.extension.assert_called_once_with(
        (code("ATug"),), action=7, target_unit=0x101400, item_rawcode=code("ttal"),
    )


def test_add_talent_choice_retains_existing_choices_in_one_tier():
    trainer = object.__new__(War3Trainer)
    first_before = talent_snapshot("ATug", controller_level=4)
    first_after = talent_snapshot("ATug", "UT1a", controller_level=4)
    second_before = first_after
    second_after = talent_snapshot("ATug", "UT1a", "UT1b", controller_level=4)
    trainer.extension_snapshot_24268 = Mock(
        side_effect=[first_before, first_after, second_before, second_after]
    )
    trainer.ability_batch_24268 = Mock()

    trainer.add_talent_choice_24268("ATug", 0, "UT1a")
    trainer.add_talent_choice_24268("ATug", 0, "UT1b")

    assert trainer.ability_batch_24268.call_args_list == [
        call("UT1a", 1, 1, target_unit=0x101400),
        call("UT1a", 2, 0, target_unit=0x101400),
        call("UT1a", 1, 1, target_unit=0x101400),
        call("UT1b", 1, 1, target_unit=0x101400),
        call("UT1b", 2, 0, target_unit=0x101400),
        call("UT1b", 1, 1, target_unit=0x101400),
    ]
    # The remove/add pair refreshes the native command-card icon without
    # changing the tier record or consuming another point.


def test_reset_rollback_restores_only_extra_same_tier_choices():
    trainer = object.__new__(War3Trainer)
    trainer.add_talent_choice_24268 = Mock()
    state = {"controller": "ATug", "tiers": (
        {"index": 0, "native_choice": "UT1b", "selected": ("UT1a", "UT1b")},
        {"index": 1, "native_choice": "UT2b", "selected": ("UT2b",)},
    )}

    trainer._restore_extra_talent_choices_24268(state, 0x100f8c)

    trainer.add_talent_choice_24268.assert_called_once_with(
        "ATug", 0, "UT1a", target_unit=0x100f8c,
    )


def test_unlock_talent_tier_is_allowed_and_packs_controller_and_tier(tmp_path):
    trainer = object.__new__(War3Trainer)
    trainer._native_selection_unavailable = False
    trainer._native_helper_batch_hook = 1
    trainer._native_helper_batch_thread_id = threading.get_ident()
    trainer._native_helper_persistent_hook = None
    trainer._native_helper_persistent_pid = 0
    trainer._native_helper_command_path = Mock(return_value=tmp_path / "command.bin")
    trainer._write_native_helper_command = Mock()
    trainer._wait_native_helper_result = Mock(return_value=[
        Mock(kind=trainer.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, result=1, last_error=0),
        Mock(kind=trainer.NATIVE_HELPER_OP_UNLOCK_TALENT_TIER, result=2, last_error=0),
    ])

    result = trainer._run_native_helper_ops_locked(
        0x101400,
        (
            (trainer.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0, 0x123400, 0x567800, 2),
            (trainer.NATIVE_HELPER_OP_UNLOCK_TALENT_TIER, code("ATug"), 1, 0, 0),
        ),
    )

    assert len(result) == 2
    payload = trainer._write_native_helper_command.call_args.args[1]
    base = trainer.NATIVE_HELPER_HEADER_STRUCT.size
    size = trainer.NATIVE_HELPER_OP_STRUCT.size
    _, rawcode, handler, arg0, arg1, *_ = trainer.NATIVE_HELPER_OP_STRUCT.unpack_from(
        payload, base + size,
    )
    assert (rawcode, handler, arg0, arg1) == (code("ATug"), 1, 0, 0)


@pytest.mark.parametrize("item_rawcode,variant", tuple(OFFICIAL_BACKPACKS.items()))
def test_each_official_backpack_writes_slot_one_and_verifies_its_controller(
    item_rawcode, variant,
):
    _hero_name, controller = variant
    trainer = object.__new__(War3Trainer)
    before = {
        "target_unit": 0x101400, "bag_size": 0, "bag": (), "equipment": (),
        "abilities": {},
    }
    after = {
        **before, "bag_size": 30,
        "abilities": {code(controller): 1},
    }
    trainer.extension_snapshot_24268 = Mock(side_effect=[before, after])
    trainer._coerce_memory_value = lambda _kind, value: code(value)
    empty = [dict(slot=index, handle=0, rawcode=0, charges=0) for index in range(6)]
    created = [dict(item) for item in empty]
    created[0] = dict(slot=0, handle=0x101500, rawcode=code(item_rawcode), charges=0)
    trainer.item_batch_24268 = Mock(side_effect=[
        {"rows": [{"handle": 0x101400, "inventory_size": 6, "before": empty}]},
        {"rows": [{"handle": 0x101400, "inventory_size": 6,
                    "before": empty, "after": created}]},
    ])
    result = trainer.add_official_backpack_24268(item_rawcode)
    assert result is after
    assert trainer.item_batch_24268.call_args_list[1].args == (7, code(item_rawcode), 0)
    assert trainer.item_batch_24268.call_args_list[1].kwargs == {
        "target_unit": 0x101400, "expected_item": 0,
    }


def test_official_backpack_rejects_a_second_different_controller():
    trainer = object.__new__(War3Trainer)
    trainer._coerce_memory_value = lambda _kind, value: code(value)
    trainer.extension_snapshot_24268 = Mock(return_value={
        "target_unit": 0x101400, "bag_size": 30, "bag": (), "equipment": (),
        "abilities": {code("ATug"): 1},
    })
    trainer.item_batch_24268 = Mock()
    with pytest.raises(RuntimeError, match="已有其他官方天赋控制器"):
        trainer.add_official_backpack_24268("ebua")
    trainer.item_batch_24268.assert_not_called()


def test_talent_state_reports_multiple_native_controllers_as_anomaly():
    trainer = object.__new__(War3Trainer)
    snapshot = talent_snapshot("ATug", controller_level=1)
    snapshot["abilities"][code("ATua")] = 1
    state = trainer.talent_state_24268(snapshot)
    assert state["controller"] == ""
    assert state["anomalies"] == ("检测到多个官方天赋控制器",)


def test_live_talent_points_bind_snapshot_target_not_first_candidate(monkeypatch):
    trainer = object.__new__(War3Trainer)
    trainer.pid = 123
    snapshot = talent_snapshot("ATug", controller_level=1)
    snapshot["selection"] = {"rows": [
        {"handle": snapshot["target_unit"], "rawcode": 200},
        {"handle": 0x101401, "rawcode": 100},
    ]}
    other = SimpleNamespace(unit_type_id=100)
    target = SimpleNamespace(unit_type_id=200)
    trainer._selected_candidates_snapshot = Mock(return_value=[(other, 0xCAFE01), (target, 0xCAFE02)])
    memory = Mock()
    memory.read_u32.return_value = 0x80000100
    memory.read.return_value = struct.pack("<QI", 0xFFFFFFFFFFFFFFFF, 0) * 6 + struct.pack("<I", 3)
    context = Mock()
    context.__enter__ = Mock(return_value=memory)
    context.__exit__ = Mock(return_value=False)
    monkeypatch.setattr("war3_reforged_trainer.ProcessMemory", Mock(return_value=context))
    trainer._ability_instances_from_candidate = Mock(return_value=[SimpleNamespace(data_address=0x200000)])
    state = trainer.talent_state_24268(snapshot)
    assert state["remaining_points"] == 3
    assert trainer._ability_instances_from_candidate.call_args.args[1] is target
    assert memory.read.call_args_list == [call(0x2000D4, 76), call(0x2000D4, 76)]
    assert not state["tiers"][0]["native_record_present"]


def test_selected_batch_skips_non_talent_units_and_continues_after_failure():
    trainer=object.__new__(War3Trainer)
    first=talent_snapshot()
    first['selection']={'rows':[{'handle':i} for i in (100,200,300,400)]}
    def snapshot(target=0):
        if not target:return first
        result=talent_snapshot();result['target_unit']=target
        if target==200:result['abilities']={}
        return result
    trainer.extension_snapshot_24268=Mock(side_effect=snapshot)
    trainer.grant_talent_point_24268=Mock(side_effect=[snapshot(100),RuntimeError('native failure'),snapshot(400)])
    result=trainer.selected_talent_batch_24268('grant')
    assert (result['succeeded'],result['skipped'],result['failed'])==(2,1,1)
    assert trainer.grant_talent_point_24268.call_args_list==[call(target_unit=100),call(target_unit=300),call(target_unit=400)]


def test_selected_talent_batch_deduplicates_handles_preserving_selection_order():
    trainer = object.__new__(War3Trainer)
    first = talent_snapshot()
    first["selection"] = {"rows": [{"handle": handle} for handle in (100, 200, 100)]}
    trainer.extension_snapshot_24268 = Mock(side_effect=[
        first, talent_snapshot(), talent_snapshot(),
    ])
    operation = Mock(side_effect=lambda *, target_unit: talent_snapshot())
    trainer.grant_talent_point_24268 = operation

    result = trainer.selected_talent_batch_24268("grant")

    assert result["succeeded"] == 2
    assert operation.call_args_list == [call(target_unit=100), call(target_unit=200)]


def test_selected_talent_batch_rejects_empty_selection():
    trainer = object.__new__(War3Trainer)
    first = talent_snapshot()
    first["selection"] = {"rows": []}
    trainer.extension_snapshot_24268 = Mock(return_value=first)

    with pytest.raises(RuntimeError, match="没有可处理的选中单位"):
        trainer.selected_talent_batch_24268("grant")


def test_selected_choice_skips_incompatible_talent_tree():
    trainer=object.__new__(War3Trainer)
    first=talent_snapshot();first['selection']={'rows':[{'handle':100}]}
    trainer.extension_snapshot_24268=Mock(side_effect=[first,talent_snapshot('ATua')])
    trainer.add_talent_choice_24268=Mock()
    result=trainer.selected_talent_batch_24268('choice','ATug',0,'UT1a')
    assert result['skipped']==1 and result['failed']==0
    trainer.add_talent_choice_24268.assert_not_called()


@pytest.mark.parametrize("action", ("grant", "reset"))
def test_selected_talent_batch_processes_both_heroes_after_leading_creep(action):
    trainer = object.__new__(War3Trainer)
    first = talent_snapshot()
    first["selection"] = {"rows": [{"handle": handle} for handle in (100, 200, 300)]}

    def snapshot(target=0):
        if not target:
            return first
        result = talent_snapshot("ATug" if target == 200 else "ATua")
        result["target_unit"] = target
        if target == 100:
            result["abilities"] = {}
        return result

    trainer.extension_snapshot_24268 = Mock(side_effect=snapshot)
    operation = Mock(side_effect=lambda *, target_unit: snapshot(target_unit))
    setattr(trainer, "grant_talent_point_24268" if action == "grant" else "reset_talents_24268", operation)
    result = trainer.selected_talent_batch_24268(action)
    assert (result["succeeded"], result["skipped"], result["failed"]) == (2, 1, 0)
    assert operation.call_args_list == [call(target_unit=200), call(target_unit=300)]
    assert result["results"][0]["status"] == "skipped"
