from copy import deepcopy
import pytest
from war3_reforged_trainer import War3Trainer


def model(fail_grant=False):
    trainer = object.__new__(War3Trainer)
    state = dict(controller="ATug", tier_count=1, remaining_points=1, used_points=2,
                 point_source="ATal+0x11c", tiers=[dict(index=0, choices=("UT1a", "UT1b", "UT1c"),
                 selected=["UT1a", "UT1c"], native_record_present=True, native_choice="UT1a")])
    failure = [fail_grant]
    events = []

    def snapshot(*_args):
        state["used_points"] = len(state["tiers"][0]["selected"])
        abilities = {int.from_bytes(c.encode(), "big"): 1 for c in state["tiers"][0]["selected"]}
        if state["controller"]:
            abilities[int.from_bytes(b"ATug", "big")] = 1
        return dict(target_unit=0x101400, state=deepcopy(state), abilities=abilities,
                    bag_size=30, bag=(), equipment=())

    def ability(code, action, level, *, target_unit):
        assert target_unit == 0x101400
        events.append((code, action))
        if code == "ATug":
            state["controller"] = "ATug" if action == 1 else ""
            state["remaining_points"] = 0
            state["tiers"][0].update(native_record_present=False, native_choice="")
        elif action == 1:
            if code not in state["tiers"][0]["selected"]:
                state["tiers"][0]["selected"].append(code)
        else:
            state["tiers"][0]["selected"].remove(code)

    def grant(*, target_unit):
        assert target_unit == 0x101400
        if failure[0]:
            failure[0] = False
            raise RuntimeError("injected refund failure")
        state["remaining_points"] += 1
        return snapshot()

    def select(controller, tier, choice, *, target_unit):
        assert (controller, tier, target_unit) == ("ATug", 0, 0x101400)
        state["remaining_points"] -= 1
        state["tiers"][0].update(native_record_present=True, native_choice=choice)
        state["tiers"][0]["selected"].append(choice)
        return snapshot()

    trainer.extension_snapshot_24268 = snapshot
    trainer.talent_state_24268 = lambda snap: snap["state"]
    trainer.ability_batch_24268 = ability
    trainer.grant_talent_point_24268 = grant
    trainer.select_native_talent_24268 = select
    return trainer, snapshot, events


def test_reset_refunds_only_native_debits_and_rebuilds_empty_records():
    trainer, snapshot, _ = model()
    result = trainer.reset_talents_24268(target_unit=0x101400)
    state = result["state"]
    assert state["remaining_points"] == 2
    assert state["used_points"] == 0
    assert not state["tiers"][0]["native_record_present"]


def test_failed_refund_restores_native_selection_extra_effect_and_remaining_points():
    trainer, snapshot, _ = model(fail_grant=True)
    before = snapshot()["state"]
    with pytest.raises(RuntimeError, match="injected refund failure") as raised:
        trainer.reset_talents_24268(target_unit=0x101400)
    assert "回滚异常" not in str(raised.value)
    assert snapshot()["state"] == before


def test_unidentified_record_stops_before_any_mutation():
    trainer, snapshot, events = model()
    original = trainer.talent_state_24268

    def invalid(snap):
        state = original(snap)
        state["tiers"][0]["native_choice"] = ""
        return state

    trainer.talent_state_24268 = invalid
    with pytest.raises(RuntimeError, match="无法识别"):
        trainer.reset_talents_24268(target_unit=0x101400)
    assert events == []
