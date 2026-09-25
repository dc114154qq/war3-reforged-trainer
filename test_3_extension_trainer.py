from unittest.mock import Mock

import pytest

from war3_reforged_trainer import War3Trainer


def snapshot(*, full=False):
    bag = [dict(slot=index, handle=0, rawcode=0, charges=0, equipment_type=0) for index in range(30)]
    bag[4] = dict(slot=4, handle=0x101500, rawcode=int.from_bytes(b"eeh3", "big"), charges=0,
                  equipment_type=1)
    if full:
        for index, row in enumerate(bag):
            if not row["handle"]:
                row.update(handle=0x102000 + index, rawcode=int.from_bytes(b"phea", "big"), charges=1)
    equipment = [dict(slot=index, handle=0, rawcode=0, charges=0, equipment_type=0)
                 for index in range(9)]
    equipment[0] = dict(slot=0, handle=0x101600, rawcode=int.from_bytes(b"ehco", "big"),
                        charges=0, equipment_type=1)
    return dict(target_unit=0x101400, bag_size=30, bag=bag, equipment=equipment, abilities={})


def test_equipping_uses_existing_expanded_bag_item_identity():
    trainer = object.__new__(War3Trainer)
    engine = Mock()
    trainer._engine_instance_24268 = Mock(return_value=engine)
    trainer.extension_snapshot_24268 = Mock(side_effect=[snapshot(), snapshot()])

    trainer.equip_extension_bag_slot_24268(4)

    engine.extension.assert_called_once_with(
        action=4,
        target_unit=0x101400,
        item_rawcode=int.from_bytes(b"eeh3", "big"),
        item_handle=0x101500,
    )


def test_equipping_selected_bag_item_to_explicit_empty_slot_verifies_identity():
    trainer = object.__new__(War3Trainer)
    engine = Mock()
    before = snapshot()
    before["equipment"][0] = dict(slot=0, handle=0, rawcode=0, charges=0, equipment_type=0)
    after = snapshot()
    after["bag"][4] = dict(slot=4, handle=0, rawcode=0, charges=0, equipment_type=0)
    after["equipment"][8] = dict(slot=8, handle=0x101500,
                                  rawcode=int.from_bytes(b"eeh3", "big"), charges=0,
                                  equipment_type=1)
    trainer._engine_instance_24268 = Mock(return_value=engine)
    trainer.extension_snapshot_24268 = Mock(side_effect=[before, after])

    trainer.equip_extension_bag_item_to_slot_24268(4, 8)

    engine.extension.assert_called_once_with(
        (int.from_bytes(b"AEqu", "big"),), action=12, target_unit=0x101400,
        slot=8, item_rawcode=int.from_bytes(b"eeh3", "big"), item_handle=0x101500,
    )


def test_explicit_slot_equip_rejects_occupied_target_without_engine_write():
    trainer = object.__new__(War3Trainer)
    engine = Mock()
    trainer._engine_instance_24268 = Mock(return_value=engine)
    trainer.extension_snapshot_24268 = Mock(return_value=snapshot())

    with pytest.raises(RuntimeError, match="目标装备槽已有物品"):
        trainer.equip_extension_bag_item_to_slot_24268(4, 0)
    engine.extension.assert_not_called()


def test_explicit_slot_equip_rejects_implicit_native_type_replacement():
    trainer = object.__new__(War3Trainer)
    engine = Mock()
    current = snapshot()
    current["equipment"][8] = dict(slot=8, handle=0, rawcode=0, charges=0, equipment_type=0)
    trainer._engine_instance_24268 = Mock(return_value=engine)
    trainer.extension_snapshot_24268 = Mock(return_value=current)

    with pytest.raises(RuntimeError, match="原生类型槽已有装备"):
        trainer.equip_extension_bag_item_to_slot_24268(4, 8)
    engine.extension.assert_not_called()


def test_full_expanded_bag_blocks_unequip_before_engine_write():
    trainer = object.__new__(War3Trainer)
    engine = Mock()
    trainer._engine_instance_24268 = Mock(return_value=engine)
    trainer.extension_snapshot_24268 = Mock(return_value=snapshot(full=True))

    with pytest.raises(RuntimeError, match="扩展背包已满"):
        trainer.unequip_extension_slot_24268(0)

    engine.extension.assert_not_called()


def test_setting_bag_charges_uses_the_selected_item_identity():
    trainer = object.__new__(War3Trainer)
    engine = Mock()
    after = snapshot()
    after["bag"][4]["charges"] = 17
    trainer._engine_instance_24268 = Mock(return_value=engine)
    trainer.extension_snapshot_24268 = Mock(side_effect=[snapshot(), after])

    trainer.set_extension_bag_charges_24268(4, 17)

    engine.extension.assert_called_once_with(
        action=6, target_unit=0x101400, slot=17,
        item_rawcode=int.from_bytes(b"eeh3", "big"), item_handle=0x101500,
    )


def test_equipment_audit_reports_wrong_slot_type_without_writing():
    trainer = object.__new__(War3Trainer)
    current = snapshot()
    current["equipment"][0]["equipment_type"] = 4
    engine = Mock()
    trainer._engine_instance_24268 = Mock(return_value=engine)
    trainer.extension_snapshot_24268 = Mock(return_value=current)

    result = trainer.audit_extension_equipment_24268()

    assert "类型为靴子" in result["issues"][0]
    engine.extension.assert_not_called()


def test_any_slot_mode_is_local_to_the_verified_direct_record_route():
    trainer = object.__new__(War3Trainer)
    trainer.pid = 24268
    before = snapshot()
    engine = Mock()
    trainer._engine_instance_24268 = Mock(return_value=engine)
    trainer.extension_snapshot_24268 = Mock(return_value=before)
    result = trainer.set_extension_equipment_any_slot_24268(False)

    assert result is before
    engine.extension.assert_not_called()
    assert trainer._extension_any_slot_enabled == {}


def test_any_slot_mode_allows_same_type_target_when_direct_route_is_used():
    trainer = object.__new__(War3Trainer)
    trainer.pid = 24268
    trainer._extension_any_slot_enabled = {(24268, 0x101400): True}
    engine = Mock()
    before = snapshot()
    after = snapshot()
    after["equipment"][8] = dict(slot=8, handle=0x101500,
                                  rawcode=int.from_bytes(b"eeh3", "big"), charges=0,
                                  equipment_type=1)
    after["bag"][4] = dict(slot=4, handle=0, rawcode=0, charges=0, equipment_type=0)
    trainer._engine_instance_24268 = Mock(return_value=engine)
    trainer.extension_snapshot_24268 = Mock(side_effect=[before, after])

    trainer.equip_extension_bag_item_to_slot_24268(4, 8)

    engine.extension.assert_called_once_with(
        (int.from_bytes(b"AEqu", "big"),), action=12, target_unit=0x101400,
        slot=8, item_rawcode=int.from_bytes(b"eeh3", "big"), item_handle=0x101500,
    )


def test_dropping_the_bag_framework_is_restored_and_rejected():
    trainer = object.__new__(War3Trainer)
    current = snapshot()
    engine = Mock()
    engine.extension.side_effect = [{"bag_size": 0}, {"bag_size": 30}]
    trainer._engine_instance_24268 = Mock(return_value=engine)
    trainer.extension_snapshot_24268 = Mock(return_value=current)

    with pytest.raises(RuntimeError, match="已自动放回"):
        trainer.drop_extension_bag_item_24268(4)

    assert engine.extension.call_count == 2
    assert engine.extension.call_args_list[1].kwargs["action"] == 3
