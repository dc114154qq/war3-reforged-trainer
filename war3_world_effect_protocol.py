"""Current-engine bounded world-effect batch for Warcraft III 3.0."""

from __future__ import annotations

import struct

from war3_selection_protocol import (
    build_work as build_selection_work,
    decode_work as decode_selection_work,
    validate_work as validate_selection_work,
)

WORK_SIZE = 648
ABI = struct.pack("<3I", 0x24268026, 216, WORK_SIZE)
ACTION_TARGET = 1
ACTION_POINT = 3
MAX_TARGETS = 100_000

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


def build_work(entries, tls, rawcode, action, success_limit=0):
    if (isinstance(rawcode, bool) or not isinstance(rawcode, int) or not 0 < rawcode <= 0xFFFFFFFF
            or isinstance(action, bool) or action not in (ACTION_TARGET, ACTION_POINT)
            or isinstance(success_limit, bool) or not 0 <= success_limit <= 65535):
        raise ValueError("Invalid current-engine world effect operation")
    pointers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError("World effect native signature differs: " + name)
        pointers.append(entry.handler)
    payload = build_selection_work(entries) + struct.pack(
        "<17Q8I", *(pointers + [tls]),
        rawcode, action, success_limit, 0, 0, 0, 0, 0,
    )
    validate_work(payload)
    return payload


def validate_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError(f"World effect work must contain {WORK_SIZE} bytes")
    validate_selection_work(payload[:480])
    pointers = struct.unpack_from("<17Q", payload, 480)
    if (any(not 0x10000 <= value < 0x800000000000 for value in pointers[:16])
            or len(set(pointers[:16])) != 16
            or not 0x10000 <= pointers[16] < 0x800000000000 or pointers[16] % 8):
        raise ValueError("Invalid world effect native pointers")
    rawcode, action, limit, attempts, error, successes, completed, reserved = struct.unpack_from(
        "<8I", payload, 616,
    )
    if (not rawcode or action not in (ACTION_TARGET, ACTION_POINT) or limit > 65535
            or attempts or error or successes or completed or reserved):
        raise ValueError("Invalid world effect arguments")


def decode_work(payload, expected_count):
    if len(payload) != WORK_SIZE:
        raise ValueError("Incomplete world effect result")
    selection = decode_selection_work(payload[:480], expected_count)
    rawcode, action, limit, attempts, error, successes, completed, reserved = struct.unpack_from(
        "<8I", payload, 616,
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
        count=expected_count,
        rows=selection["rows"],
    )
