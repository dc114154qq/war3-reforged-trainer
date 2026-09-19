"""Current-build exact attack-speed query/set ABI."""
import math
import struct

from war3_selection_protocol import (
    SIGNATURES as SELECTION_SIGNATURES,
    build_work as selection_work,
    validate_work as selection_validate,
)


WORK_SIZE = 640
ABI = struct.pack("<3I", 0x24268032, 216, WORK_SIZE)
SPEED_FACTOR_RVA = 0x509670
EFFECTIVE_INTERVAL_RVA = 0x5099A0
UNIT_RESOLVER_RVA = 0x8EDD10
SIGNATURES = (
    ("BlzGetUnitAttackCooldown", "(Hunit;I)R"),
    ("BlzSetUnitAttackCooldown", "(Hunit;RI)V"),
)


def _float_bits(value):
    return struct.unpack("<I", struct.pack("<f", float(value)))[0]


def _float_value(bits):
    return struct.unpack("<f", struct.pack("<I", bits))[0]


def build_work(entries, tls, unit_object, attack, full_handle,
               rawcode, module_base, target_aps=0.0, weapon=0):
    handlers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError("Attack-speed signature differs from current ABI: " + name)
        handlers.append(entry.handler)
    action = int(float(target_aps) > 0.0)
    payload = selection_work(entries) + struct.pack(
        "<10Q15I20s",
        *handlers,
        module_base + SPEED_FACTOR_RVA,
        module_base + EFFECTIVE_INTERVAL_RVA,
        module_base + UNIT_RESOLVER_RVA,
        tls,
        module_base,
        unit_object,
        attack,
        full_handle,
        rawcode,
        weapon,
        action,
        _float_bits(target_aps),
        *(0 for _ in range(11)),
        bytes(20),
    )
    validate_work(payload)
    return payload


def validate_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError("AttackSpeedWork must contain exactly 160 bytes")
    selection_validate(payload[:480])
    values = struct.unpack_from("<10Q15I20s", payload, 480)
    function_pointers = values[:6]
    module_base, unit_object, attack, full_handle = values[6:10]
    (rawcode, weapon, action, target_aps_bits, base_bits, factor_bits,
     effective_bits, true_aps_bits, after_base_bits, after_effective_bits,
     after_true_aps_bits, changed, error, completed, reserved) = values[10:25]
    target_aps = _float_value(target_aps_bits)
    if (
        any(not 0x10000 <= value < 0x800000000000 for value in function_pointers)
        or not full_handle
        or not 0x10000 <= module_base < 0x800000000000
        or not 0x10000 <= unit_object < 0x800000000000
        or not 0x10000 <= attack < 0x800000000000
        or not rawcode
        or weapon not in (0, 1)
        or action not in (0, 1)
        or not math.isfinite(target_aps)
        or (action and not 0.001 <= target_aps <= 1000.0)
        or (not action and target_aps_bits)
        or any((base_bits, factor_bits, effective_bits, true_aps_bits,
                after_base_bits, after_effective_bits, after_true_aps_bits,
                changed, error, completed, reserved))
        or any(values[25])
    ):
        raise ValueError("Invalid attack-speed request")


def decode_work(payload, _expected_count=None):
    if len(payload) != WORK_SIZE:
        raise ValueError("Incomplete attack-speed result")
    values = struct.unpack_from("<10Q15I20s", payload, 480)
    (rawcode, weapon, action, target_aps_bits, base_bits, factor_bits,
     effective_bits, true_aps_bits, after_base_bits, after_effective_bits,
     after_true_aps_bits, changed, error, completed, reserved) = values[10:25]
    numbers = tuple(map(_float_value, (
        base_bits, factor_bits, effective_bits, true_aps_bits,
        after_base_bits, after_effective_bits, after_true_aps_bits,
    )))
    if (
        error or reserved or completed != 1 or changed not in (0, 1)
        or any(not math.isfinite(number) or number <= 0.0 for number in numbers)
        or not 0.2 <= numbers[1] <= 5.0
        or (not action and changed)
    ):
        raise ValueError(
            f"Attack-speed batch incomplete: error={error}, completed={completed}, changed={changed}"
        )
    if action:
        target = _float_value(target_aps_bits)
        tolerance = max(0.0001, abs(target) * 0.0001)
        if abs(numbers[6] - target) > tolerance:
            raise ValueError(
                f"Attack-speed readback mismatch: target={target}, actual={numbers[6]}"
            )
    return dict(
        rawcode=rawcode,
        weapon=weapon,
        action="set" if action else "query",
        target_aps=_float_value(target_aps_bits) if action else None,
        base_cooldown=numbers[0],
        speed_factor=numbers[1],
        effective_interval=numbers[2],
        true_aps=numbers[3],
        after_base_cooldown=numbers[4],
        after_effective_interval=numbers[5],
        after_true_aps=numbers[6],
        changed=changed,
    )
