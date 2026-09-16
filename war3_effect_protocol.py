"""Current-engine batch ABI for direct ability effect callbacks.

For non-point effects ``x_bits`` carries the optional ``aare`` area field
bits and ``y_bits`` carries the bounded pass count. Point effects retain the
original x/y coordinate encoding.
"""

import struct

from war3_selection_protocol import (
    MAX_SELECTED,
    build_work as build_selection_work,
    validate_work as validate_selection_work,
    decode_work as decode_selection_work,
)

WORK_SIZE = 1168
ABI = struct.pack("<3I", 0x24268027, 216, WORK_SIZE)
SIGNATURES = (
    ("BlzGetUnitAbility", "(Hunit;I)Hability;"),
    ("BlzGetAbilityId", "(Hability;)I"),
    ("UnitAddAbility", "(Hunit;I)B"),
    ("UnitRemoveAbility", "(Hunit;I)B"),
    ("GetUnitX", "(Hunit;)R"),
    ("GetUnitY", "(Hunit;)R"),
    ("BlzGetAbilityRealLevelField", "(Hability;Habilityreallevelfield;I)R"),
    ("BlzSetAbilityRealLevelField", "(Hability;Habilityreallevelfield;IR)B"),
)
EFFECT_TARGET = 1
EFFECT_IMMEDIATE = 2
EFFECT_POINT = 3
EFFECT_NOARG = 4


def build_work(entries, tls, rawcode, action, x_bits=0, y_bits=0, area_bits=0, *, resolver=0, unit_map=()):
    if (isinstance(rawcode, bool) or not isinstance(rawcode, int) or not rawcode <= 0xFFFFFFFF or rawcode <= 0
            or isinstance(action, bool) or action not in range(1, 5)
            or any(isinstance(value, bool) or not isinstance(value, int) for value in (x_bits, y_bits))):
        raise ValueError("Invalid current-engine effect operation")
    pointers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError("Effect native signature differs: " + name)
        pointers.append(entry.handler)
    payload = bytearray(build_selection_work(entries))
    if isinstance(area_bits, bool) or not isinstance(area_bits, int) or not 0 <= area_bits <= 0xFFFFFFFF:
        raise ValueError("Invalid effect area bits")
    ordered_pointers = pointers[:1] + [resolver] + pointers[1:]
    payload.extend(struct.pack(
        "<10Q8I", *(ordered_pointers + [tls]), rawcode, action, x_bits, y_bits,
        0, 0, 0, area_bits if action == EFFECT_POINT else 0,
    ))
    if len(unit_map) > 24:
        raise ValueError("Effect unit map exceeds the 24-unit selection limit")
    payload.extend(bytes(24 * 24))
    for index, row in enumerate(unit_map):
        if (not isinstance(row, (tuple, list)) or len(row) != 2
                or not isinstance(row[0], int) or not 0 < row[0] <= 0xFFFFFFFFFFFFFFFF
                or not isinstance(row[1], int) or not 0 < row[1] <= 0xFFFFFFFF):
            raise ValueError("Invalid effect unit map row")
        struct.pack_into("<Q4I", payload, 592 + index * 24, row[0], row[1], 0, 0, 0)
    payload = bytes(payload)
    validate_work(payload)
    return payload


def validate_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError(f"Effect work must contain {WORK_SIZE} bytes")
    validate_selection_work(payload[:480])
    pointers = struct.unpack_from("<10Q", payload, 480)
    if (any(not 0x10000 <= value < 0x800000000000 for value in pointers[:8])
            or len(set(pointers[:8])) != 8
            or not 0x10000 <= pointers[8] < 0x800000000000
            or not 0x10000 <= pointers[9] < 0x800000000000 or pointers[9] % 8):
        raise ValueError("Invalid effect native pointers")
    rawcode, action, x_bits, y_bits, changed, error, completed, reserved = struct.unpack_from("<8I", payload, 560)
    if (not rawcode or action not in range(1, 5) or changed or error or completed
            or (action != EFFECT_POINT and reserved)):
        raise ValueError("Invalid effect arguments")
    if action == EFFECT_POINT:
        if (x_bits & 0x7f800000) == 0x7f800000 or (y_bits & 0x7f800000) == 0x7f800000:
            raise ValueError("Point coordinates must be finite")
    elif y_bits > 255:
        raise ValueError("Effect pass count must be in 0..255")


def decode_work(payload, expected_count):
    if len(payload) != WORK_SIZE:
        raise ValueError("Incomplete effect result")
    selection = decode_selection_work(payload[:480], expected_count)
    rawcode, action, x_bits, y_bits, changed, error, completed, reserved = struct.unpack_from("<8I", payload, 560)
    if error or (action != EFFECT_POINT and reserved) or completed != expected_count or changed != expected_count:
        raise ValueError(f"Effect batch incomplete: error={error}, completed={completed}/{expected_count}")
    rows = []
    for index, selected in enumerate(selection["rows"]):
        unit, status, temporary, reserved0, reserved1 = struct.unpack_from("<Q4I", payload, 592 + index * 24)
        if unit != selected["handle"] or status != 1 or reserved0 or reserved1:
            raise ValueError("Effect result identity or status mismatch")
        rows.append(dict(selected, unit=unit, status=status, temporary=temporary))
    return dict(rawcode=rawcode, action=action, x_bits=x_bits, y_bits=y_bits,
                area_bits=reserved if action == EFFECT_POINT else x_bits,
                passes=1 if action == EFFECT_POINT else (y_bits or 1),
                changed=changed, count=expected_count, rows=rows)
