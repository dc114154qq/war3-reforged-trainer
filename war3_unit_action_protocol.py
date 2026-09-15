"""Current-build 24268 batch protocol for the remaining unit actions."""
import math
import struct

from war3_selection_protocol import (
    SIGNATURES as SELECTION_SIGNATURES,
    build_work as build_selection_work,
    decode_work as decode_selection_work,
    validate_work as validate_selection_work,
)

WORK_SIZE = 1432
ROW_SIZE = 32
ROWS_OFFSET = 664
MAX_UNITS = 24

ACTION_SET_INVULNERABLE = 1
ACTION_SET_PATHING = 2
ACTION_SET_PAUSED = 3
ACTION_RESET_COOLDOWN = 4
ACTION_KILL = 5
ACTION_REMOVE = 6
ACTION_EXPLODE = 7
ACTION_SET_POSITION = 8
ACTION_SET_SCALE = 9
ACTION_TAKE_CONTROL = 10
ACTION_QUERY_INVULNERABLE = 11
ACTION_QUERY_PAUSED = 12
ACTION_ADD_SKILL_POINTS = 13

ACTION_SIGNATURES = (
    ("SetUnitInvulnerable", "(Hunit;B)V"),
    ("BlzIsUnitInvulnerable", "(Hunit;)B"),
    ("SetUnitPathing", "(Hunit;B)V"),
    ("PauseUnit", "(Hunit;B)V"),
    ("IsUnitPaused", "(Hunit;)B"),
    ("UnitResetCooldown", "(Hunit;)V"),
    ("KillUnit", "(Hunit;)V"),
    ("RemoveUnit", "(Hunit;)V"),
    ("SetUnitExploded", "(Hunit;B)V"),
    ("SetUnitScale", "(Hunit;RRR)V"),
    ("SetUnitPosition", "(Hunit;RR)V"),
    ("GetUnitX", "(Hunit;)R"),
    ("GetUnitY", "(Hunit;)R"),
    ("SetUnitOwner", "(Hunit;Hplayer;B)V"),
    ("GetOwningPlayer", "(Hunit;)Hplayer;"),
    ("UnitModifySkillPoints", "(Hunit;I)B"),
)
HANDLER_NAMES = tuple(name for name, _ in ACTION_SIGNATURES)
HANDLER_INDEX = {name: index for index, name in enumerate(HANDLER_NAMES) if name != "__reserved__"}
ABI = struct.pack("<3I", 0x24268016, 216, WORK_SIZE)

_REQUIRED = {
    ACTION_SET_INVULNERABLE: ("SetUnitInvulnerable", "BlzIsUnitInvulnerable"),
    ACTION_SET_PATHING: ("SetUnitPathing",),
    ACTION_SET_PAUSED: ("PauseUnit", "IsUnitPaused"),
    ACTION_RESET_COOLDOWN: ("UnitResetCooldown",),
    ACTION_KILL: ("KillUnit",),
    ACTION_REMOVE: ("RemoveUnit",),
    ACTION_EXPLODE: ("SetUnitExploded", "KillUnit"),
    ACTION_SET_POSITION: ("SetUnitPosition", "GetUnitX", "GetUnitY"),
    ACTION_SET_SCALE: ("SetUnitScale",),
    ACTION_TAKE_CONTROL: ("SetUnitOwner", "GetOwningPlayer"),
    ACTION_QUERY_INVULNERABLE: ("BlzIsUnitInvulnerable",),
    ACTION_QUERY_PAUSED: ("IsUnitPaused",),
    ACTION_ADD_SKILL_POINTS: ("UnitModifySkillPoints",),
}


def _bits(value: float) -> int:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("unit action coordinate/scale must be finite")
    return struct.unpack("<I", struct.pack("<f", value))[0]


def build_work(entries, tls, action, *, value=0, x_bits=0, y_bits=0,
               scale_x_bits=0, scale_y_bits=0, scale_z_bits=0):
    if action not in _REQUIRED:
        raise ValueError("Unknown current-engine unit action")
    if (action == ACTION_ADD_SKILL_POINTS and not 1 <= value <= 1_000_000) or (
            action != ACTION_ADD_SKILL_POINTS and value not in (0, 1)):
        raise ValueError("unit action boolean value must be 0 or 1")
    handlers = [0] * 16
    for name, signature in ACTION_SIGNATURES:
        entry = entries.get(name)
        if entry is not None:
            if entry.name != name or entry.signature != signature:
                raise ValueError("Unit action native signature differs: " + name)
            handlers[HANDLER_INDEX[name]] = entry.handler
    for name in _REQUIRED[action]:
        if not handlers[HANDLER_INDEX[name]]:
            raise ValueError("Missing unit action native: " + name)
    selected = build_selection_work(entries)
    payload = (
        selected
        + struct.pack(
            "<17Q12I", *handlers, tls, action, value, 0, 0, 0, 0,
            x_bits, y_bits, scale_x_bits, scale_y_bits, scale_z_bits, 0,
        )
        + bytes(WORK_SIZE - ROWS_OFFSET)
    )
    validate_work(payload)
    return payload


def validate_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError("UnitActionWork must contain exactly 1432 bytes")
    validate_selection_work(payload[:480])
    values = struct.unpack_from("<17Q12I", payload, 480)
    handlers, tls = values[:16], values[16]
    action, value, changed, error, completed, reserved, x_bits, y_bits, sx, sy, sz, pad = values[17:]
    if not 0x10000 <= tls < 0x800000000000 or tls % 8:
        raise ValueError("UnitActionWork contains an invalid TLS value")
    if action not in _REQUIRED or ((action == ACTION_ADD_SKILL_POINTS and not 1 <= value <= 1_000_000) or
                                  (action != ACTION_ADD_SKILL_POINTS and value not in (0, 1))):
        raise ValueError("UnitActionWork contains invalid action arguments")
    for name in _REQUIRED[action]:
        if not 0x10000 <= handlers[HANDLER_INDEX[name]] < 0x800000000000:
            raise ValueError("UnitActionWork is missing " + name)
    for bits in (x_bits, y_bits, sx, sy, sz):
        if not math.isfinite(struct.unpack("<f", struct.pack("<I", bits))[0]):
            raise ValueError("UnitActionWork contains a non-finite float")
    if changed or error or completed or reserved or pad or any(payload[ROWS_OFFSET:]):
        raise ValueError("UnitActionWork output must be zero-initialized")


def decode_work(payload, expected_count):
    if len(payload) != WORK_SIZE:
        raise ValueError("Incomplete unit action result")
    selection = decode_selection_work(payload[:480], expected_count)
    values = struct.unpack_from("<17Q12I", payload, 480)
    action, value, changed, error, completed, reserved, x_bits, y_bits, sx, sy, sz, pad = values[17:]
    if error or reserved or pad or completed != expected_count or changed > expected_count:
        raise ValueError(
            f"Unit action incomplete: error={error}, completed={completed}/{expected_count}, changed={changed}"
        )
    rows = []
    for index, source in enumerate(selection["rows"]):
        offset = ROWS_OFFSET + index * ROW_SIZE
        unit, before, after, status, reserved_row, actual_x, actual_y = struct.unpack_from("<Q6I", payload, offset)
        if unit != source["handle"] or not status or reserved_row:
            raise ValueError("Unit action identity or status mismatch")
        if action == ACTION_ADD_SKILL_POINTS:
            if source["level"] > 0 and status != 1:
                raise ValueError("Hero skill-point action did not acknowledge hero")
            if source["level"] <= 0 and status != 2:
                raise ValueError("Hero skill-point action touched a nonhero")
        rows.append(dict(source, unit=unit, before=before, after=after, status=status,
                         actual_x_bits=actual_x, actual_y_bits=actual_y))
    return dict(action=action, value=value, rows=rows, count=expected_count,
                changed=changed, completed=completed)
