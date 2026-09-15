"""Current-engine 24268 mouse-to-world coordinate query ABI."""
import math
import struct


WORK_SIZE = 128
ABI = struct.pack("<3I", 0x24268019, 216, WORK_SIZE)
SIGNATURES = (
    ("BlzGetTriggerPlayerMousePosition", "()Hlocation;"),
    ("GetLocationX", "(Hlocation;)R"),
    ("GetLocationY", "(Hlocation;)R"),
    ("RemoveLocation", "(Hlocation;)V"),
)


def build_work(entries, tls):
    pointers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError("Mouse native signature differs: " + name)
        pointers.append(entry.handler)
    payload = struct.pack("<5Q7I", *pointers, tls, 0, 0, 0, 0, 0, 0, 0) + bytes(WORK_SIZE - 68)
    validate_work(payload)
    return payload


def _real(bits):
    return struct.unpack("<f", struct.pack("<I", bits))[0]


def validate_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError("MouseWork must contain exactly 128 bytes")
    pointers = struct.unpack_from("<4Q", payload, 0)
    tls, x_bits, y_bits, changed, error, completed, reserved0, reserved1 = struct.unpack_from(
        "<Q7I", payload, 32,
    )
    if (any(not 0x10000 <= pointer < 0x800000000000 for pointer in pointers)
            or len(set(pointers)) != len(pointers)
            or not 0x10000 <= tls < 0x800000000000 or tls % 8):
        raise ValueError("MouseWork contains an invalid TLS value")
    if any(not math.isfinite(_real(bits)) for bits in (x_bits, y_bits)):
        raise ValueError("MouseWork contains non-finite coordinates")
    if changed or error or completed or reserved0 or reserved1 or any(payload[68:]):
        raise ValueError("Mouse outputs must be zero-initialized")


def decode_work(payload, _expected_count=None):
    if len(payload) != WORK_SIZE:
        raise ValueError("Incomplete mouse query")
    _pointers = struct.unpack_from("<4Q", payload, 0)
    _tls, x_bits, y_bits, changed, error, completed, reserved0, reserved1 = struct.unpack_from(
        "<Q7I", payload, 32,
    )
    x, y = _real(x_bits), _real(y_bits)
    if (error or reserved0 or reserved1 or completed != 1 or changed != 1
            or not math.isfinite(x) or not math.isfinite(y)
            or abs(x) > 1_000_000.0 or abs(y) > 1_000_000.0):
        raise ValueError(
            f"Mouse query incomplete: error={error}, completed={completed}, changed={changed}"
        )
    return dict(x=x, y=y, x_bits=x_bits, y_bits=y_bits, changed=changed,
                count=1, completed=completed)
