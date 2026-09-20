from unittest.mock import Mock

from war3_reforged_trainer import War3Trainer


def code(value):
    return int.from_bytes(value.encode("ascii"), "big")


def talent_snapshot(*selected, controller_level=3):
    return {
        "target_unit": 0x101400,
        "bag_size": 30,
        "bag": (),
        "equipment": (),
        "abilities": {
            code("ATug"): controller_level,
            **{code(value): 1 for value in selected},
        },
    }


def test_talent_state_derives_total_used_and_remaining_points():
    trainer = object.__new__(War3Trainer)

    state = trainer.talent_state_24268(talent_snapshot("UT1a", controller_level=4))

    assert state["controller"] == "ATug"
    assert state["total_points"] == 3
    assert state["used_points"] == 1
    assert state["remaining_points"] == 2


def test_talent_choice_replaces_same_tier_transactionally():
    trainer = object.__new__(War3Trainer)
    before = talent_snapshot("UT1a", controller_level=2)
    after = talent_snapshot("UT1b", controller_level=2)
    trainer.extension_snapshot_24268 = Mock(side_effect=[before, after])
    trainer.ability_batch_24268 = Mock(return_value={"changed": 1})

    result = trainer.set_talent_choice_24268("ATug", 0, "UT1b")

    assert result is after
    assert trainer.ability_batch_24268.call_args_list == [
        (("UT1a", 2, 0),),
        (("UT1b", 1, 1),),
    ]


def test_grant_talent_point_uses_verified_controller_action():
    trainer = object.__new__(War3Trainer)
    before = talent_snapshot("UT1a", controller_level=2)
    after = talent_snapshot("UT1a", controller_level=3)
    engine = Mock()
    trainer._engine_instance_24268 = Mock(return_value=engine)
    trainer._coerce_memory_value = lambda _kind, value: code(value)
    trainer.extension_snapshot_24268 = Mock(side_effect=[before, after])

    trainer.grant_talent_point_24268()

    engine.extension.assert_called_once_with(
        (code("ATug"),), action=7, target_unit=0x101400, item_rawcode=code("ttal"),
    )


def test_generic_template_uses_stock_passives_without_official_controller():
    trainer = object.__new__(War3Trainer)
    snapshot = {
        "target_unit": 0x101400,
        "bag_size": 30,
        "bag": (),
        "equipment": (),
        "abilities": {},
    }
    trainer._generic_talent_points = {0x101400: 2}

    state = trainer.talent_state_24268(snapshot)

    assert state["controller"] == "GENERIC"
    assert state["remaining_points"] == 2
    assert state["tiers"][0]["choices"] == ("AIs1", "AIa1", "AIi1")


def test_generic_talent_point_is_accounted_without_creating_tome():
    trainer = object.__new__(War3Trainer)
    snapshot = {
        "target_unit": 0x101400,
        "bag_size": 30,
        "bag": (),
        "equipment": (),
        "abilities": {},
    }
    trainer._generic_talent_points = {0x101400: 0}
    trainer.extension_snapshot_24268 = Mock(side_effect=[snapshot, snapshot])
    engine = Mock()
    trainer._engine_instance_24268 = Mock(return_value=engine)

    result = trainer.grant_talent_point_24268()

    assert result is snapshot
    assert trainer._generic_talent_points[0x101400] == 1
    engine.extension.assert_not_called()
