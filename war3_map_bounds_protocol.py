"""Current-build 24268 map world-bounds query."""
import math
import struct

WORK_SIZE = 128
ABI = struct.pack("<3I", 0x2426802C, 216, WORK_SIZE)
SIGNATURES = (
    ("GetWorldBounds", "()Hrect;"),
    ("GetRectMinX", "(Hrect;)R"),
    ("GetRectMaxX", "(Hrect;)R"),
    ("GetRectMinY", "(Hrect;)R"),
    ("GetRectMaxY", "(Hrect;)R"),
)


def _real(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", bits & 0xFFFFFFFF))[0]


def build_work(entries, tls):
    handlers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError("Map-bounds native signature differs: " + name)
        handlers.append(entry.handler)
    payload = struct.pack(
        "<6Q8I", *handlers, tls, 0, 0, 0, 0, 0, 0, 0, 0,
    ) + bytes(WORK_SIZE - 80)
    validate_work(payload)
    return payload


def validate_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError("MapBoundsWork must contain exactly 128 bytes")
    values = struct.unpack_from("<6Q8I", payload, 0)
    handlers, tls = values[:5], values[5]
    outputs = values[6:]
    if (any(not 0x10000 <= address < 0x800000000000 for address in handlers)
            or len(set(handlers)) != 5
            or not 0x10000 <= tls < 0x800000000000 or tls % 8
            or any(outputs)):
        raise ValueError("MapBoundsWork contains invalid handlers or outputs")


def decode_work(payload, _expected_count=None):
    if len(payload) != WORK_SIZE:
        raise ValueError("Incomplete map-bounds result")
    values = struct.unpack_from("<6Q8I", payload, 0)
    xmin, xmax, ymin, ymax, changed, error, completed, reserved = values[6:]
    bounds = tuple(_real(value) for value in (xmin, xmax, ymin, ymax))
    if (error or reserved or changed != 1 or completed != 1
            or not all(math.isfinite(value) for value in bounds)
            or not bounds[0] < bounds[1] or not bounds[2] < bounds[3]):
        raise ValueError(
            f"Map bounds incomplete: error={error}, completed={completed}, changed={changed}"
        )
    return dict(min_x=bounds[0], max_x=bounds[1], min_y=bounds[2], max_y=bounds[3],
                changed=changed, count=1, completed=completed)
