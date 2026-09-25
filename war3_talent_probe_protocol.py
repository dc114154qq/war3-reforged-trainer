"""Diagnostic native-order probe on a temporary hero, with selection restore."""
import struct
from war3_selection_protocol import build_work as selection_work, validate_work as selection_validate

WORK_SIZE = 824
ABI = struct.pack("<3I", 0x24268040, 216, WORK_SIZE)
SIGNATURES = (
    ("CreateUnit", "(Hplayer;IRRR)Hunit;"), ("GetUnitTypeId", "(Hunit;)I"),
    ("RemoveUnit", "(Hunit;)V"), ("GetUnitX", "(Hunit;)R"), ("GetUnitY", "(Hunit;)R"),
    ("UnitAddItemById", "(Hunit;I)Hitem;"), ("RemoveItem", "(Hitem;)V"),
    ("SelectUnit", "(Hunit;B)V"), ("IssueImmediateOrderById", "(Hunit;I)B"),
    ("GetUnitAbilityLevel", "(Hunit;I)I"),
)


def build_work(entries, tls, action=0, target=0, order=0, saved=(), item=0):
    pointers = []
    for name, signature in SIGNATURES:
        entry = entries[name]
        if entry.signature != signature:
            raise ValueError("Talent probe signature differs: " + name)
        pointers.append(entry.handler)
    saved = tuple(saved)
    payload = (selection_work(entries) + struct.pack("<12Q4IQ", *pointers, tls, target,
        action, order, int.from_bytes(b"Hpal", "big"), int.from_bytes(b"ATug", "big"), 0)
        + struct.pack("<24Q", *(saved + (0,) * (24 - len(saved))))
        + struct.pack("<6IQ", len(saved), 0, 0, 0, 0, 0, item))
    validate_work(payload)
    return payload


def validate_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError("Talent probe work size differs")
    selection_validate(payload[:480])
    pointers = struct.unpack_from("<11Q", payload, 480)
    if any(not 0x10000 <= value < 0x800000000000 for value in pointers):
        raise ValueError("Invalid talent probe function or TLS")
    target, action, order, rawcode, controller, created = struct.unpack_from("<Q4IQ", payload, 568)
    count, error, completed, accepted, level, reserved, item = struct.unpack_from("<6IQ", payload, 792)
    if action not in (0, 1, 2) or count > 24 or any((created, error, completed, accepted, level, reserved)) or (action != 2 and item):
        raise ValueError("Invalid talent probe request")
    if (action == 0 and (target or order or count)) or (action != 0 and not target):
        raise ValueError("Invalid talent probe target")
    if (action == 1 and not 0xd0311 <= order <= 0xd0322) or (action != 1 and order):
        raise ValueError("Invalid talent order")
    if rawcode != int.from_bytes(b"Hpal", "big") or controller != int.from_bytes(b"ATug", "big"):
        raise ValueError("Unexpected diagnostic hero or controller")
    saved = struct.unpack_from("<24Q", payload, 600)
    if any(saved[count:]) or any(not value for value in saved[:count]) or (action == 2 and not count):
        raise ValueError("Invalid saved selection")


def decode_work(payload, _count):
    target, action, order, rawcode, controller, created = struct.unpack_from("<Q4IQ", payload, 568)
    count, error, completed, accepted, level, _, item = struct.unpack_from("<6IQ", payload, 792)
    return dict(target=target, action=action, order=order, created=created, error=error,
                completed=completed, accepted=accepted, level=level, item=item,
                saved=struct.unpack_from("<24Q", payload, 600)[:min(count, 24)])
