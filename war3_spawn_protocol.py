"""Current-engine 24268 batch for creating one local-player unit."""
import math
import struct


WORK_SIZE = 128
ABI = struct.pack("<3I", 0x24268018, 216, WORK_SIZE)
SIGNATURES = (
    ("GetLocalPlayer", "()Hplayer;"),
    ("CreateUnit", "(Hplayer;IRRR)Hunit;"),
    ("GetUnitTypeId", "(Hunit;)I"),
    ("RemoveUnit", "(Hunit;)V"),
)


def _valid_ptr(value: int) -> bool:
    return 0x10000 <= value < 0x800000000000


def _finite_real(bits: int) -> bool:
    value = struct.unpack("<f", struct.pack("<I", bits))[0]
    return math.isfinite(value)


def _pointers(entries):
    pointers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError("Spawn native signature differs: " + name)
        pointers.append(entry.handler)
    return pointers


def build_work(entries, tls, rawcode, x_bits=0, y_bits=0, facing_bits=0):
    rawcode = int(rawcode)
    x_bits = int(x_bits)
    y_bits = int(y_bits)
    facing_bits = int(facing_bits)
    payload = struct.pack(
        "<5Q8IQI",
        *_pointers(entries),
        tls,
        rawcode,
        x_bits,
        y_bits,
        facing_bits,
        0,
        0,
        0,
        0,
        0,
        0,
    ) + bytes(WORK_SIZE - 84)
    validate_work(payload)
    return payload


def validate_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError("SpawnWork must contain exactly 128 bytes")
    values = struct.unpack_from("<5Q8IQI", payload, 0)
    pointers, tls = values[:4], values[4]
    rawcode, x_bits, y_bits, facing_bits, changed, error, completed, actual_rawcode = values[5:13]
    created, reserved = values[13:]
    if (any(not _valid_ptr(pointer) for pointer in pointers)
            or len(set(pointers)) != len(pointers)
            or not _valid_ptr(tls) or tls % 8
            or not rawcode
            or any(not 0 <= bits <= 0xFFFFFFFF for bits in (x_bits, y_bits, facing_bits))
            or any(not _finite_real(bits) for bits in (x_bits, y_bits, facing_bits))):
        raise ValueError("Invalid spawn native pointers or request")
    if changed or error or completed or actual_rawcode or created or reserved or any(payload[84:]):
        raise ValueError("Spawn outputs must be zero-initialized")


def decode_work(payload, _expected_count=None):
    if len(payload) != WORK_SIZE:
        raise ValueError("Incomplete spawn batch")
    values = struct.unpack_from("<5Q8IQI", payload, 0)
    rawcode, x_bits, y_bits, facing_bits, changed, error, completed, actual_rawcode = values[5:13]
    created, reserved = values[13:]
    if (error or reserved or completed != 1 or changed != 1 or not created
            or actual_rawcode != rawcode):
        raise ValueError(
            f"Spawn batch incomplete: error={error}, completed={completed}, changed={changed}"
        )
    return dict(rawcode=rawcode, x_bits=x_bits, y_bits=y_bits, facing_bits=facing_bits,
                changed=changed, count=1, completed=completed,
                created=created, actual_rawcode=actual_rawcode)
