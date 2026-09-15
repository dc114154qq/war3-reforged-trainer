"""Current-engine batch ABI for elephant/global unit-group operations."""

import struct

from war3_selection_protocol import (
    build_work as build_selection_work,
    validate_work as validate_selection_work,
)

SELECTION_SIZE = 480
WORK_SIZE = 624
ABI = struct.pack("<3I", 0x24268023, 216, WORK_SIZE)
SIGNATURES = (
    ("GetLocalPlayer", "()Hplayer;"),
    ("CreateGroup", "()Hgroup;"),
    ("GroupEnumUnitsOfPlayer", "(Hgroup;Hplayer;Hboolexpr;)V"),
    ("FirstOfGroup", "(Hgroup;)Hunit;"),
    ("GroupRemoveUnit", "(Hgroup;Hunit;)B"),
    ("DestroyGroup", "(Hgroup;)V"),
    ("GetOwningPlayer", "(Hunit;)Hplayer;"),
    ("GetWidgetLife", "(Hwidget;)R"),
    ("BlzGetUnitMaxHP", "(Hunit;)R"),
    ("SetWidgetLife", "(Hwidget;R)V"),
    ("UnitResetCooldown", "(Hunit;)V"),
    ("KillUnit", "(Hunit;)V"),
    ("Player", "(I)Hplayer;"),
    ("SetPlayerAlliance", "(Hplayer;Hplayer;Halliancetype;B)V"),
)

BULK_HEAL_LOCAL = 1
BULK_RESET_LOCAL_COOLDOWNS = 2
BULK_KILL_SELECTED_OWNER = 3
BULK_PEACE_MODE = 4


def build_work(entries, tls, action, value=0):
    if isinstance(action, bool) or action not in range(1, 5) or isinstance(value, bool) or not 0 <= value <= 1:
        raise ValueError("Invalid current-engine bulk action")
    pointers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError("Bulk native signature differs: " + name)
        pointers.append(entry.handler)
    payload = build_selection_work(entries) + struct.pack(
        "<15Q6I", *(pointers + [tls]), action, value, 0, 0, 0, 0,
    )
    validate_work(payload)
    return payload


def validate_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError(f"Bulk work must contain {WORK_SIZE} bytes")
    validate_selection_work(payload[:SELECTION_SIZE])
    pointers = struct.unpack_from("<15Q", payload, SELECTION_SIZE)
    if (any(not 0x10000 <= value < 0x800000000000 for value in pointers[:14])
            or len(set(pointers[:14])) != 14
            or not 0x10000 <= pointers[14] < 0x800000000000 or pointers[14] % 8):
        raise ValueError("Invalid bulk native pointers")
    action, value, changed, error, completed, reserved = struct.unpack_from("<6I", payload, SELECTION_SIZE + 120)
    if action not in range(1, 5) or value > 1 or changed or error or completed or reserved:
        raise ValueError("Invalid bulk arguments")


def decode_work(payload, _expected_count=None):
    if len(payload) != WORK_SIZE:
        raise ValueError("Incomplete bulk result")
    action, value, changed, error, completed, reserved = struct.unpack_from(
        "<6I", payload, SELECTION_SIZE + 120,
    )
    if error or completed != 1 or reserved or not changed:
        raise ValueError(f"Bulk operation incomplete: error={error}, changed={changed}")
    return dict(action=action, value=value, changed=changed, count=changed)
