"""Current-engine 24268 screen mouse coordinate probe."""
import struct


WORK_SIZE = 128
ABI = struct.pack("<3I", 0x2426801A, 216, WORK_SIZE)
SIGNATURES = (
    ("BlzGetMouseScreenPosX", "()I"),
    ("BlzGetMouseScreenPosY", "()I"),
)


def build_work(entries, tls):
    pointers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError("Screen mouse native signature differs: " + name)
        pointers.append(entry.handler)
    payload = struct.pack("<3Q7i", *pointers, tls, 0, 0, 0, 0, 0, 0, 0) + bytes(WORK_SIZE - 52)
    validate_work(payload)
    return payload


def validate_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError("ScreenMouseWork must contain exactly 128 bytes")
    pointers = struct.unpack_from("<2Q", payload, 0)
    tls, x, y, changed, error, completed, reserved0, reserved1 = struct.unpack_from(
        "<Q7i", payload, 16,
    )
    if (any(not 0x10000 <= pointer < 0x800000000000 for pointer in pointers)
            or len(set(pointers)) != len(pointers)
            or not 0x10000 <= tls < 0x800000000000 or tls % 8):
        raise ValueError("ScreenMouseWork contains invalid pointers")
    if any((x, y, changed, error, completed, reserved0, reserved1)) or any(payload[52:]):
        raise ValueError("Screen mouse outputs must be zero-initialized")


def decode_work(payload, _expected_count=None):
    if len(payload) != WORK_SIZE:
        raise ValueError("Incomplete screen mouse query")
    _pointers = struct.unpack_from("<2Q", payload, 0)
    _tls, x, y, changed, error, completed, reserved0, reserved1 = struct.unpack_from(
        "<Q7i", payload, 16,
    )
    if error or reserved0 or reserved1 or completed != 1 or changed != 1:
        raise ValueError(
            f"Screen mouse query incomplete: error={error}, completed={completed}, changed={changed}"
        )
    return dict(x=x, y=y, changed=changed, count=1, completed=completed)
