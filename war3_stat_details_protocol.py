"""Single-dispatch Warcraft III 3.0 stat-details read/write ABI."""

from __future__ import annotations

import math
import struct

from war3_selection_protocol import (
    build_work as selection_work,
    decode_work as selection_result,
    validate_work as selection_validate,
)
from war3_3_stats import STAT_DETAIL_SPECS


STAT_COUNT = len(STAT_DETAIL_SPECS)
MAX_PRESENT = 64
WORK_SIZE = 1032
ABI = struct.pack("<3I", 0x2426803E, 216, WORK_SIZE)
SIGNATURES = (
    ("BlzGetUnitAbilityByIndex", "(Hunit;I)Hability;"),
    ("BlzGetAbilityId", "(Hability;)I"),
    ("ConvertAbilityRealLevelField", "(I)Habilityreallevelfield;"),
    ("ConvertAbilityBooleanLevelField", "(I)Habilitybooleanlevelfield;"),
    ("BlzGetAbilityRealLevelField", "(Hability;Habilityreallevelfield;I)R"),
    ("BlzGetAbilityBooleanLevelField", "(Hability;Habilitybooleanlevelfield;I)B"),
    ("BlzSetAbilityRealLevelField", "(Hability;Habilityreallevelfield;IR)B"),
    ("BlzSetAbilityBooleanLevelField", "(Hability;Habilitybooleanlevelfield;IB)B"),
    ("UnitAddAbility", "(Hunit;I)B"),
    ("UnitRemoveAbility", "(Hunit;I)B"),
    ("BlzUnitHideAbility", "(Hunit;IB)V"),
)


def _rawcode(value: str | int) -> int:
    if isinstance(value, str):
        if len(value) != 4:
            raise ValueError("Stat controller rawcode must contain four characters")
        return int.from_bytes(value.encode("ascii"), "big")
    return int(value)


def build_work(entries, tls: int, action: int = 0, stat_index: int = 0,
               target: float = 0.0, controller: str | int = 0,
               target_unit: int = 0, target_full_handle: int = 0, resolver_base: int = 0) -> bytes:
    if action not in (0, 1, 2) or not 0 <= stat_index < STAT_COUNT:
        raise ValueError("Invalid stat-details operation")
    if not math.isfinite(float(target)) or abs(float(target)) > 1_000_000.0:
        raise ValueError("Stat-details target is outside the supported range")
    controller_rawcode = _rawcode(controller) if controller else 0
    if action in (1, 2) and not controller_rawcode:
        raise ValueError("Stat-details write requires a controller ability")
    if action == 2 and (stat_index != 0 or target != 0.0 or not target_unit):
        raise ValueError("Ability visibility refresh requires a target unit")
    handlers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError("Stat-details signature differs: " + name)
        handlers.append(int(entry.handler))
    target_bits = struct.unpack("<I", struct.pack("<f", float(target)))[0]
    payload = (
        selection_work(entries)
        + struct.pack("<12Q", *handlers, int(tls))
        + struct.pack("<Q8I", int(target_unit), action, stat_index, target_bits,
                      controller_rawcode, 0, 0, 0, 0)
        + bytes(STAT_COUNT * 8 + MAX_PRESENT * 4 + 32)
        + struct.pack("<2Q", int(target_full_handle), int(resolver_base))
    )
    validate_work(payload)
    return payload


def validate_work(payload: bytes) -> None:
    if len(payload) != WORK_SIZE:
        raise ValueError("Stat-details work size differs")
    selection_validate(payload[:480])
    pointers = struct.unpack_from("<12Q", payload, 480)
    if any(not 0x10000 <= value < 0x800000000000 for value in pointers):
        raise ValueError("Stat-details handler or TLS is invalid")
    target_unit, action, stat_index, target_bits, controller, changed, error, completed, count = struct.unpack_from(
        "<Q8I", payload, 576,
    )
    target = struct.unpack("<f", struct.pack("<I", target_bits))[0]
    if (action not in (0, 1, 2) or not 0 <= stat_index < STAT_COUNT
            or not math.isfinite(target) or abs(target) > 1_000_000.0
            or bool(controller) != (action in (1, 2))
            or (action == 2 and (stat_index != 0 or target != 0.0 or not target_unit))
            or changed or error or completed or count):
        raise ValueError("Invalid stat-details request")
    if target_unit and not 0x10000 <= target_unit < 0x10000000000000000:
        raise ValueError("Invalid stat-details target unit")
    full, base = struct.unpack_from("<2Q", payload, 1016)
    if bool(full) != bool(base) or (base and (not 0x10000 <= base < 0x800000000000 or base % 0x1000)):
        raise ValueError("Invalid stat-details runtime binding")
    if any(payload[616:1016]):
        raise ValueError("Stat-details output must start empty")


def decode_work(payload: bytes, expected_count: int) -> dict:
    if len(payload) != WORK_SIZE:
        raise ValueError("Stat-details response is incomplete")
    selection = selection_result(payload[:480], expected_count)
    target_unit, action, stat_index, target_bits, controller, changed, error, completed, count = struct.unpack_from(
        "<Q8I", payload, 576,
    )
    if error or completed != 1 or count > MAX_PRESENT:
        ability, exception_address, field, stage = struct.unpack_from("<2Q2I", payload, 984)
        field_text = field.to_bytes(4, "big").decode("ascii", errors="replace")
        converted = struct.unpack_from("<Q", payload, 1008)[0]
        raise ValueError(
            f"Stat-details incomplete: error={error}, completed={completed}, abilities={count}; "
            f"stage={stage}, ability=0x{ability:x}, field={field_text!r}, "
            f"converted_field=0x{converted:x}, exception_address=0x{exception_address:x}"
        )
    if sum(row["handle"] == target_unit for row in selection["rows"]) != 1:
        raise ValueError("Stat-details target changed")
    before_bits = struct.unpack_from(f"<{STAT_COUNT}I", payload, 616)
    after_bits = struct.unpack_from(f"<{STAT_COUNT}I", payload, 616 + STAT_COUNT * 4)
    before = tuple(struct.unpack("<f", struct.pack("<I", value))[0] for value in before_bits)
    after = tuple(struct.unpack("<f", struct.pack("<I", value))[0] for value in after_bits)
    if any(not math.isfinite(value) for value in before + after):
        raise ValueError("Stat-details returned a non-finite value")
    if action == 0 and (changed or before != after):
        raise ValueError("Stat-details read unexpectedly changed state")
    if action in (1, 2) and changed != 1:
        raise ValueError("Stat-details write was not confirmed")
    present = struct.unpack_from(f"<{MAX_PRESENT}I", payload, 616 + STAT_COUNT * 8)
    if any(not value for value in present[:count]) or any(present[count:]):
        raise ValueError("Stat-details ability list is invalid")
    return {
        "selection": selection,
        "target_unit": target_unit,
        "action": action,
        "stat_index": stat_index,
        "target": struct.unpack("<f", struct.pack("<I", target_bits))[0],
        "controller": controller,
        "changed": changed,
        "before": before,
        "after": after,
        "present": tuple(present[:count]),
    }
