"""Current-engine batch ABI for direct ability effect callbacks."""

import struct

from war3_selection_protocol import (
    MAX_SELECTED,
    build_work as build_selection_work,
    validate_work as validate_selection_work,
    decode_work as decode_selection_work,
)

WORK_SIZE = 1144
ABI = struct.pack("<3I", 0x24268024, 216, WORK_SIZE)
SIGNATURES = (
    ("BlzGetUnitAbility", "(Hunit;I)Hability;"),
    ("BlzGetAbilityId", "(Hability;)I"),
    ("UnitAddAbility", "(Hunit;I)B"),
    ("UnitRemoveAbility", "(Hunit;I)B"),
    ("GetUnitX", "(Hunit;)R"),
    ("GetUnitY", "(Hunit;)R"),
)
EFFECT_TARGET = 1
EFFECT_IMMEDIATE = 2
EFFECT_POINT = 3
EFFECT_NOARG = 4


def build_work(entries, tls, rawcode, action, x_bits=0, y_bits=0):
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
    payload.extend(struct.pack("<7Q8I", *(pointers + [tls]), rawcode, action, x_bits, y_bits, 0, 0, 0, 0))
    payload.extend(bytes(24 * 24))
    payload = bytes(payload)
    validate_work(payload)
    return payload


def validate_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError(f"Effect work must contain {WORK_SIZE} bytes")
    validate_selection_work(payload[:480])
    pointers = struct.unpack_from("<7Q", payload, 480)
    if (any(not 0x10000 <= value < 0x800000000000 for value in pointers[:6])
            or len(set(pointers[:6])) != 6
            or not 0x10000 <= pointers[6] < 0x800000000000 or pointers[6] % 8):
        raise ValueError("Invalid effect native pointers")
    rawcode, action, x_bits, y_bits, changed, error, completed, reserved = struct.unpack_from("<8I", payload, 536)
    if not rawcode or action not in range(1, 5) or changed or error or completed or reserved:
        raise ValueError("Invalid effect arguments")
    if action != EFFECT_POINT and (x_bits or y_bits):
        raise ValueError("Point coordinates are valid only for point effects")


def decode_work(payload, expected_count):
    if len(payload) != WORK_SIZE:
        raise ValueError("Incomplete effect result")
    selection = decode_selection_work(payload[:480], expected_count)
    rawcode, action, x_bits, y_bits, changed, error, completed, reserved = struct.unpack_from("<8I", payload, 536)
    if error or reserved or completed != expected_count or changed != expected_count:
        raise ValueError(f"Effect batch incomplete: error={error}, completed={completed}/{expected_count}")
    rows = []
    for index, selected in enumerate(selection["rows"]):
        unit, status, temporary, reserved0, reserved1 = struct.unpack_from("<Q4I", payload, 568 + index * 24)
        if unit != selected["handle"] or status != 1 or reserved0 or reserved1:
            raise ValueError("Effect result identity or status mismatch")
        rows.append(dict(selected, unit=unit, status=status, temporary=temporary))
    return dict(rawcode=rawcode, action=action, x_bits=x_bits, y_bits=y_bits,
                changed=changed, count=expected_count, rows=rows)
