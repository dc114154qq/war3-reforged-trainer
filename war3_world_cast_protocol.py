"""Current-build staged native orders for temporary full-screen abilities."""

import math
import struct

from war3_selection_protocol import SIGNATURES as SELECTION, build_work as selection_work
from war3_selection_protocol import decode_work as selection_result, validate_work as selection_validate


WORK_SIZE = 760
ABI = struct.pack("<3I", 0x24268048, 216, WORK_SIZE)
CAST_IMMEDIATE = 1
CAST_POINT = 2
CAST_TARGET = 3
SIGNATURES = (
    ("BlzGetUnitAbility", "(Hunit;I)Hability;"),
    ("BlzGetAbilityId", "(Hability;)I"),
    ("UnitAddAbility", "(Hunit;I)B"),
    ("UnitRemoveAbility", "(Hunit;I)B"),
    ("BlzGetAbilityRealLevelField", "(Hability;Habilityreallevelfield;I)R"),
    ("BlzSetAbilityRealLevelField", "(Hability;Habilityreallevelfield;IR)B"),
    ("IssueImmediateOrderById", "(Hunit;I)B"),
    ("IssuePointOrderById", "(Hunit;IRR)B"),
    ("IssueTargetOrderById", "(Hunit;IHwidget;)B"),
    ("GetOwningPlayer", "(Hunit;)Hplayer;"),
    ("GetWidgetLife", "(Hwidget;)R"),
    ("GetUnitState", "(Hunit;Hunitstate;)R"),
    ("BlzGetUnitAbilityCooldownRemaining", "(Hunit;I)R"),
    ("GetUnitCurrentOrder", "(Hunit;)I"),
    ("GetUnitX", "(Hunit;)R"),
    ("GetUnitY", "(Hunit;)R"),
    ("CreateGroup", "()Hgroup;"),
    ("GroupEnumUnitsOfPlayer", "(Hgroup;Hplayer;Hboolexpr;)V"),
    ("FirstOfGroup", "(Hgroup;)Hunit;"),
    ("GroupRemoveUnit", "(Hgroup;Hunit;)B"),
    ("DestroyGroup", "(Hgroup;)V"),
    ("Player", "(I)Hplayer;"),
    ("IsPlayerEnemy", "(Hplayer;Hplayer;)B"),
)


def build_work(entries, tls, *, action, rawcode, order_id=0, cast_kind=CAST_IMMEDIATE,
               area=0.0, source=0, ability_handle=0, target=0,
               prior_area=0, added=0):
    pointers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError("World cast native signature differs: " + name)
        pointers.append(entry.handler)
    area_bits = struct.unpack("<I", struct.pack("<f", float(area)))[0]
    payload = selection_work(entries) + struct.pack(
        "<27Q16I", *pointers, tls, source, ability_handle, target,
        action, rawcode, order_id, cast_kind, area_bits, prior_area, added,
        0, 0, 0, 0, 0, 0, 0, 0, 0,
    )
    validate_work(payload)
    return payload


def validate_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError("World cast work size differs")
    selection_validate(payload[:480])
    pointers = struct.unpack_from("<27Q", payload, 480)
    handlers = pointers[:23]
    tls, source, ability_handle, target = pointers[23:]
    if (any(not 0x10000 <= pointer < 0x800000000000 for pointer in handlers)
            or len(set(handlers)) != len(handlers) or not tls or tls % 8):
        raise ValueError("World cast handler or TLS is invalid")
    (action, rawcode, order_id, cast_kind, area_bits, prior_area, added,
     issued, error, completed, mana_before, mana_after, cooldown_after,
     order_after, target_x, target_y) = struct.unpack_from("<16I", payload, 696)
    area = struct.unpack("<f", struct.pack("<I", area_bits))[0]
    if (action not in (1, 2, 3) or not rawcode or cast_kind not in
            (CAST_IMMEDIATE, CAST_POINT, CAST_TARGET) or
            any((issued, error, completed, mana_before, mana_after,
                 cooldown_after, order_after, target_x, target_y))):
        raise ValueError("World cast request is invalid")
    if action == 1:
        if ((source and not 0x10000 <= source < 0x800000000000) or
                ability_handle or target or not order_id or not 1 <= area <= 100000 or
                prior_area or added):
            raise ValueError("World cast start request is invalid")
    elif (not 0x10000 <= source < 0x800000000000 or
          not 0x10000 <= ability_handle < 0x800000000000 or order_id or
          (target and not 0x10000 <= target < 0x800000000000) or
          added not in (0, 1) or not math.isfinite(area)):
        raise ValueError("World cast continuation identity is invalid")


def decode_work(payload, _count):
    if len(payload) != WORK_SIZE:
        raise ValueError("World cast response is incomplete")
    source, ability_handle, target = struct.unpack_from("<3Q", payload, 672)
    (action, rawcode, order_id, cast_kind, area_bits, prior_area, added,
     issued, error, completed, mana_before, mana_after, cooldown_after,
     order_after, target_x, target_y) = struct.unpack_from("<16I", payload, 696)
    if error or completed != 1 or (action == 1 and issued != 1):
        raise ValueError(f"World cast incomplete: action={action}, error={error}, completed={completed}")
    selected_count = struct.unpack_from("<I", payload, 80)[0]
    selection = selection_result(payload[:480], selected_count) if action == 1 else None
    real = lambda bits: struct.unpack("<f", struct.pack("<I", bits))[0]
    return dict(action=action, rawcode=rawcode, cast_kind=cast_kind,
                source=source, ability_handle=ability_handle, target=target,
                area_bits=area_bits, prior_area=prior_area, added=added, issued=issued,
                mana_before=real(mana_before), mana_after=real(mana_after),
                cooldown_after=real(cooldown_after), order_after=order_after,
                target_x=real(target_x), target_y=real(target_y), selection=selection)
