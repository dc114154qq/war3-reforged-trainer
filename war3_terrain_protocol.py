"""Current-build terrain-height query used to refine mouse projection."""

import math
import struct


WORK_SIZE = 128
ABI = struct.pack("<3I", 0x2426802A, 216, WORK_SIZE)
SIGNATURES = (
    ("Location", "(RR)Hlocation;"),
    ("GetLocationZ", "(Hlocation;)R"),
    ("RemoveLocation", "(Hlocation;)V"),
)


def _real(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", bits & 0xFFFFFFFF))[0]


def build_work(entries, tls: int, x_bits: int, y_bits: int) -> bytes:
    pointers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError("Terrain native signature differs: " + name)
        pointers.append(entry.handler)
    payload = struct.pack(
        "<4Q7I", *pointers, tls, x_bits & 0xFFFFFFFF, y_bits & 0xFFFFFFFF,
        0, 0, 0, 0, 0,
    ) + bytes(WORK_SIZE - 60)
    validate_work(payload)
    return payload


def validate_work(payload: bytes) -> None:
    if len(payload) != WORK_SIZE:
        raise ValueError("TerrainWork must contain exactly 128 bytes")
    pointers = struct.unpack_from("<3Q", payload, 0)
    tls, x_bits, y_bits, z_bits, changed, error, completed, reserved = struct.unpack_from(
        "<Q7I", payload, 24,
    )
    if (any(not 0x10000 <= pointer < 0x800000000000 for pointer in pointers)
            or len(set(pointers)) != len(pointers)
            or not 0x10000 <= tls < 0x800000000000 or tls % 8
            or not math.isfinite(_real(x_bits)) or not math.isfinite(_real(y_bits))
            or z_bits or changed or error or completed or reserved
            or any(payload[60:])):
        raise ValueError("TerrainWork contains invalid input or nonzero output")


def decode_work(payload: bytes, _expected_count=None) -> dict:
    if len(payload) != WORK_SIZE:
        raise ValueError("Incomplete terrain query")
    _pointers = struct.unpack_from("<3Q", payload, 0)
    _tls, x_bits, y_bits, z_bits, changed, error, completed, reserved = struct.unpack_from(
        "<Q7I", payload, 24,
    )
    z = _real(z_bits)
    if (error or reserved or changed != 1 or completed != 1
            or not math.isfinite(z) or abs(z) > 1_000_000.0):
        raise ValueError(
            f"Terrain query incomplete: error={error}, completed={completed}, changed={changed}"
        )
    return dict(x_bits=x_bits, y_bits=y_bits, z_bits=z_bits, z=z,
                changed=changed, count=1, completed=completed)
