"""Current-build 24268 position batch using SetUnitX/SetUnitY."""
import math
import struct

from war3_selection_protocol import (
    build_work as build_selection_work,
    decode_work as decode_selection_work,
    validate_work as validate_selection_work,
)

WORK_SIZE = 1328
ROWS_OFFSET = 560
ROW_SIZE = 32
MAX_UNITS = 24
ABI = struct.pack("<3I", 0x2426801E, 216, WORK_SIZE)
SIGNATURES = (
    ("SetUnitX", "(Hunit;R)V"),
    ("SetUnitY", "(Hunit;R)V"),
    ("GetUnitX", "(Hunit;)R"),
    ("GetUnitY", "(Hunit;)R"),
    ("IssueImmediateOrderById", "(Hunit;I)B"),
    ("GetUnitCurrentOrder", "(Hunit;)I"),
)


def _real(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", bits & 0xFFFFFFFF))[0]


def _bits(value: float) -> int:
    value = float(value)
    if not math.isfinite(value) or abs(value) > 1_000_000.0:
        raise ValueError("position coordinate must be finite and bounded")
    return struct.unpack("<I", struct.pack("<f", value))[0]


def build_work(entries, tls, x_bits: int, y_bits: int):
    handlers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError("Position native signature differs: " + name)
        handlers.append(entry.handler)
    if not isinstance(x_bits, int) or not isinstance(y_bits, int):
        raise ValueError("Position bits must be integers")
    if not math.isfinite(_real(x_bits)) or not math.isfinite(_real(y_bits)):
        raise ValueError("Position bits contain a non-finite coordinate")
    payload = (
        build_selection_work(entries)
        + struct.pack(
            "<7Q6I", *handlers, tls,
            x_bits & 0xFFFFFFFF, y_bits & 0xFFFFFFFF,
            0, 0, 0, 0,
        )
        + bytes(WORK_SIZE - ROWS_OFFSET)
    )
    validate_work(payload)
    return payload


def validate_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError("PositionWork must contain exactly 1328 bytes")
    validate_selection_work(payload[:480])
    values = struct.unpack_from("<7Q6I", payload, 480)
    handlers, tls = values[:6], values[6]
    x_bits, y_bits, changed, error, completed, reserved = values[7:]
    if len(set(handlers)) != 6 or any(not 0x10000 <= address < 0x800000000000 for address in handlers):
        raise ValueError("PositionWork contains invalid handlers")
    if not 0x10000 <= tls < 0x800000000000 or tls % 8:
        raise ValueError("PositionWork contains an invalid TLS value")
    if not math.isfinite(_real(x_bits)) or not math.isfinite(_real(y_bits)):
        raise ValueError("PositionWork contains a non-finite target")
    if changed or error or completed or reserved or any(payload[ROWS_OFFSET:]):
        raise ValueError("PositionWork output must be zero-initialized")


def decode_work(payload, expected_count):
    if len(payload) != WORK_SIZE:
        raise ValueError("Incomplete position result")
    selection = decode_selection_work(payload[:480], expected_count)
    values = struct.unpack_from("<7Q6I", payload, 480)
    x_bits, y_bits, changed, error, completed, reserved = values[7:]
    target_x, target_y = _real(x_bits), _real(y_bits)
    if error or reserved or completed != expected_count or changed != expected_count:
        raise ValueError(
            f"Position batch incomplete: error={error}, completed={completed}/{expected_count}, changed={changed}"
        )
    rows = []
    anchor_x_value = None
    anchor_y_value = None
    for index, source in enumerate(selection["rows"]):
        offset = ROWS_OFFSET + index * ROW_SIZE
        unit, before, after, status, reserved_row, actual_x, actual_y = struct.unpack_from(
            "<Q6I", payload, offset,
        )
        actual_x_value, actual_y_value = _real(actual_x), _real(actual_y)
        before_x_value, before_y_value = _real(before), _real(after)
        if anchor_x_value is None:
            anchor_x_value, anchor_y_value = before_x_value, before_y_value
        expected_x = target_x + before_x_value - anchor_x_value
        expected_y = target_y + before_y_value - anchor_y_value
        if (unit != source["handle"] or status != 1 or reserved_row
                or not math.isfinite(actual_x_value) or not math.isfinite(actual_y_value)
                or not math.isfinite(expected_x) or not math.isfinite(expected_y)
                or abs(actual_x_value - expected_x) > 0.01
                or abs(actual_y_value - expected_y) > 0.01):
            raise ValueError("Position identity or readback mismatch")
        rows.append(dict(source, unit=unit, before=before, after=after,
                         before_x=before_x_value, before_y=before_y_value,
                         expected_x=expected_x, expected_y=expected_y,
                         status=status, actual_x_bits=actual_x, actual_y_bits=actual_y))
    return dict(target_x=target_x, target_y=target_y, rows=rows,
                count=expected_count, changed=changed, completed=completed)
