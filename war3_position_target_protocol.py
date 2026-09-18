"""24268 targeted SetUnitPosition form used only for reversible cleanup."""

import math
import struct

from war3_position_protocol import (
    ROWS_OFFSET,
    ROW_SIZE,
    SIGNATURES,
    WORK_SIZE,
)
from war3_selection_protocol import (
    build_work as build_selection_work,
    validate_work as validate_selection_work,
)

ABI = struct.pack("<3I", 0x24268020, 216, WORK_SIZE)


def _real(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", bits & 0xFFFFFFFF))[0]


def build_work(entries, tls: int, target_unit: int, x_bits: int, y_bits: int) -> bytes:
    if (isinstance(target_unit, bool) or not isinstance(target_unit, int)
            or not 0 < target_unit <= 0xFFFFFFFFFFFFFFFF):
        raise ValueError("target unit must be a non-zero JASS handle")
    handlers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError("Position native signature differs: " + name)
        handlers.append(entry.handler)
    payload = (
        build_selection_work(entries)
        + struct.pack(
            "<5Q6I", *handlers, target_unit, tls,
            x_bits & 0xFFFFFFFF, y_bits & 0xFFFFFFFF, 0, 0, 0, 0,
        )
        + bytes(WORK_SIZE - ROWS_OFFSET)
    )
    validate_work(payload)
    return payload


def validate_work(payload: bytes) -> None:
    if len(payload) != WORK_SIZE:
        raise ValueError("Targeted position work must contain exactly 1312 bytes")
    validate_selection_work(payload[:480])
    values = struct.unpack_from("<5Q6I", payload, 480)
    handlers, target_unit, tls = values[:3], values[3], values[4]
    x_bits, y_bits, changed, error, completed, reserved = values[5:]
    if (len(set(handlers)) != 3
            or any(not 0x10000 <= address < 0x800000000000 for address in handlers)
            or not 0 < target_unit <= 0xFFFFFFFFFFFFFFFF
            or not 0x10000 <= tls < 0x800000000000 or tls % 8
            or not math.isfinite(_real(x_bits)) or not math.isfinite(_real(y_bits))
            or changed or error or completed or reserved or any(payload[ROWS_OFFSET:])):
        raise ValueError("Targeted position work contains invalid arguments or output")


def decode_work(payload: bytes, expected_count: int) -> dict:
    if len(payload) != WORK_SIZE or expected_count != 1:
        raise ValueError("Incomplete targeted position result")
    values = struct.unpack_from("<5Q6I", payload, 480)
    handlers, target_unit, tls = values[:3], values[3], values[4]
    x_bits, y_bits, changed, error, completed, reserved = values[5:]
    row_unit, before_x, before_y, status, row_reserved, actual_x, actual_y = struct.unpack_from(
        "<Q6I", payload, ROWS_OFFSET,
    )
    if (not 0 < target_unit <= 0xFFFFFFFFFFFFFFFF or row_unit != target_unit
            or error or reserved or completed != 1 or changed != 1
            or status != 1 or row_reserved
            or not all(math.isfinite(_real(bits)) for bits in (x_bits, y_bits, before_x, before_y, actual_x, actual_y))):
        raise ValueError(
            f"Targeted position incomplete: error={error}, completed={completed}/1, changed={changed}"
        )
    return {
        "target_unit": target_unit,
        "target_x": _real(x_bits),
        "target_y": _real(y_bits),
        "before_x": _real(before_x),
        "before_y": _real(before_y),
        "actual_x": _real(actual_x),
        "actual_y": _real(actual_y),
        "changed": changed,
        "completed": completed,
    }
