"""Current-build map visibility flags used when direct fog setters fault."""

import struct


WORK_SIZE = 128
ABI = struct.pack("<3I", 0x2426802C, 216, WORK_SIZE)
SIGNATURES = (
    ("ConvertMapFlag", "(I)Hmapflag;"),
    ("SetMapFlag", "(Hmapflag;B)V"),
    ("IsMapFlagSet", "(Hmapflag;)B"),
)
ACTION_QUERY = 1
ACTION_SET = 2


def build_work(entries, tls, action, revealed=0):
    if action not in (ACTION_QUERY, ACTION_SET) or revealed not in (0, 1):
        raise ValueError("Invalid map visibility operation")
    pointers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError("Map flag native signature differs: " + name)
        pointers.append(entry.handler)
    payload = struct.pack(
        "<4Q8I", *pointers, tls, action, revealed, 0, 0, 0, 0, 0, 0,
    ) + bytes(WORK_SIZE - 64)
    validate_work(payload)
    return payload


def validate_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError("MapFlagsWork must contain exactly 128 bytes")
    pointers = struct.unpack_from("<3Q", payload, 0)
    tls, action, revealed, changed, error, completed, after0, after1, reserved = struct.unpack_from(
        "<Q8I", payload, 24,
    )
    if (any(not 0x10000 <= pointer < 0x800000000000 for pointer in pointers)
            or len(set(pointers)) != len(pointers)
            or not 0x10000 <= tls < 0x800000000000 or tls % 8
            or action not in (ACTION_QUERY, ACTION_SET) or revealed not in (0, 1)
            or changed or error or completed or after0 or after1 or reserved
            or any(payload[64:])):
        raise ValueError("MapFlagsWork contains invalid input or nonzero output")


def decode_work(payload, _expected_count=None):
    if len(payload) != WORK_SIZE:
        raise ValueError("Incomplete map visibility query")
    action, revealed, changed, error, completed, after0, after1, reserved = struct.unpack_from(
        "<8I", payload, 32,
    )
    desired = 0 if revealed else 1
    valid = (not error and completed == 1 and not reserved and
             after0 <= 1 and after1 <= 1)
    if action == ACTION_QUERY:
        valid &= not changed
    elif action == ACTION_SET:
        valid &= changed == 1 and after0 == desired and after1 == desired
    else:
        valid = False
    if not valid:
        raise ValueError(
            f"Map visibility incomplete: error={error}, completed={completed}, changed={changed}, "
            f"after=({after0},{after1})"
        )
    return dict(action=action, revealed=bool(revealed), changed=changed,
                count=1, after0=after0, after1=after1)
