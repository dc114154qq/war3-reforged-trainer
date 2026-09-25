"""Identity-bound native talent selection through the normal order API."""
import struct
from war3_selection_protocol import build_work as selection_work, validate_work as selection_validate

WORK_SIZE = 544
ABI = struct.pack("<3I", 0x24268041, 216, WORK_SIZE)
SIGNATURES = (("IssueImmediateOrderById", "(Hunit;I)B"), ("GetUnitAbilityLevel", "(Hunit;I)I"))


def build_work(entries, tls, target, controller, order, choice):
    handlers = []
    for name, signature in SIGNATURES:
        entry = entries[name]
        if entry.signature != signature:
            raise ValueError("Talent order signature differs: " + name)
        handlers.append(entry.handler)
    payload = selection_work(entries) + struct.pack("<4Q8I", *handlers, tls, target,
        controller, order, choice, 0, 0, 0, 0, 0)
    validate_work(payload)
    return payload


def validate_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError("Talent order work size differs")
    selection_validate(payload[:480])
    pointers = struct.unpack_from("<4Q", payload, 480)
    if any(not 0x10000 <= value < 0x800000000000 for value in pointers):
        raise ValueError("Invalid talent order pointer or target")
    controller, order, choice, *outputs = struct.unpack_from("<8I", payload, 512)
    if not controller or not choice or not 0xd0311 <= order <= 0xd0322 or any(outputs):
        raise ValueError("Invalid native talent choice")


def decode_work(payload, count):
    controller, order, choice, before, after, accepted, error, completed = struct.unpack_from("<8I", payload, 512)
    if error or completed != 1 or after != 1 or accepted not in (0, 1):
        raise ValueError(f"Native talent order failed: error={error}, accepted={accepted}, before={before}, after={after}")
    return dict(controller=controller, order=order, choice=choice, before=before,
                after=after, accepted=accepted, completed=completed)
