"""Current-engine bounded world-effect batch for Warcraft III 3.0."""

from __future__ import annotations

import struct

WORK_SIZE = 656
ABI = struct.pack("<3I", 0x24268028, 216, WORK_SIZE)
ACTION_TARGET = 1
ACTION_IMMEDIATE = 2
ACTION_POINT = 3
MAX_TARGETS = 100_000
SELECTION_RESERVED_SIZE = 480

SIGNATURES = (
    ("BlzGetUnitAbility", "(Hunit;I)Hability;"),
    ("BlzGetAbilityId", "(Hability;)I"),
    ("UnitAddAbility", "(Hunit;I)B"),
    ("UnitRemoveAbility", "(Hunit;I)B"),
    ("GetLocalPlayer", "()Hplayer;"),
    ("CreateGroup", "()Hgroup;"),
    ("GroupEnumUnitsOfPlayer", "(Hgroup;Hplayer;Hboolexpr;)V"),
    ("FirstOfGroup", "(Hgroup;)Hunit;"),
    ("GroupRemoveUnit", "(Hgroup;Hunit;)B"),
    ("DestroyGroup", "(Hgroup;)V"),
    ("GetOwningPlayer", "(Hunit;)Hplayer;"),
    ("Player", "(I)Hplayer;"),
    ("IsPlayerEnemy", "(Hplayer;Hplayer;)B"),
    ("GetWidgetLife", "(Hwidget;)R"),
    ("GetUnitX", "(Hunit;)R"),
    ("GetUnitY", "(Hunit;)R"),
)


def build_work(entries, tls, rawcode, action, success_limit=0, *, resolver=0):
    if (isinstance(rawcode, bool) or not isinstance(rawcode, int) or not 0 < rawcode <= 0xFFFFFFFF
            or isinstance(action, bool) or action not in (ACTION_TARGET, ACTION_IMMEDIATE, ACTION_POINT)
            or isinstance(success_limit, bool) or not 0 <= success_limit <= 65535):
        raise ValueError("Invalid current-engine world effect operation")
    pointers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError("World effect native signature differs: " + name)
        pointers.append(entry.handler)
    ordered_pointers = pointers[:1] + [resolver] + pointers[1:]
    # Keep the historical selection block reserved for ABI compatibility, but
    # do not require GroupEnumUnitsSelected for world enumeration.
    payload = bytes(SELECTION_RESERVED_SIZE) + struct.pack(
        "<18Q8I", *(ordered_pointers + [tls]),
        rawcode, action, success_limit, 0, 0, 0, 0, 0,
    )
    validate_work(payload)
    return payload


def validate_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError(f"World effect work must contain {WORK_SIZE} bytes")
    if any(payload[:SELECTION_RESERVED_SIZE]):
        raise ValueError("World effect selection-reserved block must be zero")
    pointers = struct.unpack_from("<18Q", payload, 480)
    if (any(not 0x10000 <= value < 0x800000000000 for value in pointers[:16])
            or len(set(pointers[:16])) != 16
            or not 0x10000 <= pointers[16] < 0x800000000000
            or not 0x10000 <= pointers[17] < 0x800000000000 or pointers[17] % 8):
        raise ValueError("Invalid world effect native pointers")
    rawcode, action, limit, attempts, error, successes, completed, reserved = struct.unpack_from(
        "<8I", payload, 624,
    )
    if (not rawcode or action not in (ACTION_TARGET, ACTION_IMMEDIATE, ACTION_POINT) or limit > 65535
            or attempts or error or successes or completed or reserved):
        raise ValueError("Invalid world effect arguments")


def decode_work(payload, expected_count):
    if len(payload) != WORK_SIZE:
        raise ValueError("Incomplete world effect result")
    rawcode, action, limit, attempts, error, successes, completed, reserved = struct.unpack_from(
        "<8I", payload, 624,
    )
    if (error or reserved or completed != 1 or successes > attempts
            or attempts > MAX_TARGETS or (limit and successes > limit)):
        raise ValueError(
            f"World effect incomplete: error={error}, attempts={attempts}, successes={successes}"
        )
    return dict(
        rawcode=rawcode,
        action=action,
        success_limit=limit,
        attempts=attempts,
        successes=successes,
        changed=successes,
        count=0,
        rows=[],
    )
