"""Current-build transactional armor, defense-type, and intelligence ABI."""
import math
import struct

from war3_selection_protocol import (
    SIGNATURES as SELECTION_SIGNATURES,
    build_work as build_selection_work,
    decode_work as decode_selection_work,
    validate_work as validate_selection_work,
)

WORK_SIZE = 1728
ROWS_OFFSET = 576
ROW_SIZE = 48
MAX_UNITS = 24
ABI = struct.pack("<3I", 0x2426803B, 216, WORK_SIZE)

ACTION_QUERY = 0
ACTION_SET_ARMOR = 1
ACTION_SET_DEFENSE_TYPE = 2
ACTION_SET_INTELLIGENCE = 3

SIGNATURES = (
    ("BlzGetUnitArmor", "(Hunit;)R"),
    ("BlzSetUnitArmor", "(Hunit;R)V"),
    ("ConvertUnitIntegerField", "(I)Hunitintegerfield;"),
    ("BlzGetUnitIntegerField", "(Hunit;Hunitintegerfield;)I"),
    ("BlzSetUnitIntegerField", "(Hunit;Hunitintegerfield;I)B"),
    ("GetHeroInt", "(Hunit;B)I"),
    ("SetHeroInt", "(Hunit;IB)V"),
)


def _float_bits(value):
    value = float(value)
    if not math.isfinite(value) or not -1_000_000.0 <= value <= 1_000_000.0:
        raise ValueError("Armor must be finite and within -1000000..1000000")
    return struct.unpack("<I", struct.pack("<f", value))[0]


def build_work(entries, tls, action=ACTION_QUERY, value=0, target_unit=0):
    if action not in (ACTION_QUERY, ACTION_SET_ARMOR, ACTION_SET_DEFENSE_TYPE,
                      ACTION_SET_INTELLIGENCE):
        raise ValueError("Unknown unit-stat action")
    if isinstance(target_unit, bool) or not isinstance(target_unit, int) or not 0 <= target_unit <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError("Invalid unit-stat target")
    if action != ACTION_QUERY and not target_unit:
        raise ValueError("Unit-stat mutation requires one exact target")
    if action == ACTION_SET_ARMOR:
        value_bits = _float_bits(value)
    elif action == ACTION_SET_DEFENSE_TYPE:
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 7:
            raise ValueError("Defense type must be an integer in 0..7")
        value_bits = value
    elif action == ACTION_SET_INTELLIGENCE:
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 1_000_000_000:
            raise ValueError("Intelligence must be an integer in 0..1000000000")
        value_bits = value
    else:
        value_bits = 0
    handlers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError("Unit-stat native signature differs: " + name)
        handlers.append(entry.handler)
    payload = (
        build_selection_work(entries)
        + struct.pack("<8Q6IQ", *handlers, tls, action, value_bits, 0, 0, 0, 0, target_unit)
        + bytes(WORK_SIZE - ROWS_OFFSET)
    )
    validate_work(payload)
    return payload


def validate_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError(f"UnitStatsWork must contain exactly {WORK_SIZE} bytes")
    validate_selection_work(payload[:480])
    values = struct.unpack_from("<8Q6IQ", payload, 480)
    handlers, tls = values[:7], values[7]
    action, value_bits, changed, error, completed, reserved, target_unit = values[8:]
    if any(not 0x10000 <= pointer < 0x800000000000 for pointer in handlers):
        raise ValueError("UnitStatsWork contains an invalid native handler")
    if not 0x10000 <= tls < 0x800000000000 or tls % 8:
        raise ValueError("UnitStatsWork contains an invalid TLS value")
    if action not in (ACTION_QUERY, ACTION_SET_ARMOR, ACTION_SET_DEFENSE_TYPE,
                      ACTION_SET_INTELLIGENCE):
        raise ValueError("UnitStatsWork contains an invalid action")
    if action != ACTION_QUERY and not target_unit:
        raise ValueError("UnitStatsWork mutation has no exact target")
    if action == ACTION_SET_ARMOR:
        value = struct.unpack("<f", struct.pack("<I", value_bits))[0]
        if not math.isfinite(value) or not -1_000_000.0 <= value <= 1_000_000.0:
            raise ValueError("UnitStatsWork armor is invalid")
    elif action == ACTION_SET_DEFENSE_TYPE and value_bits > 7:
        raise ValueError("UnitStatsWork defense type is invalid")
    elif action == ACTION_QUERY and value_bits:
        raise ValueError("UnitStatsWork query contains a value")
    if changed or error or completed or reserved or any(payload[ROWS_OFFSET:]):
        raise ValueError("UnitStatsWork output must be zero-initialized")


def decode_work(payload, expected_count):
    if len(payload) != WORK_SIZE:
        raise ValueError("Incomplete unit-stat result")
    selection = decode_selection_work(payload[:480], expected_count)
    values = struct.unpack_from("<8Q6IQ", payload, 480)
    action, value_bits, changed, error, completed, reserved, target_unit = values[8:]
    if error or reserved or completed != expected_count or changed > 1:
        raise ValueError(
            f"Unit-stat transaction incomplete: error={error}, "
            f"completed={completed}/{expected_count}, changed={changed}"
        )
    rows = []
    matched = 0
    for index, source in enumerate(selection["rows"]):
        offset = ROWS_OFFSET + index * ROW_SIZE
        unpacked = struct.unpack_from("<Q10I", payload, offset)
        unit = unpacked[0]
        armor_before_bits, armor_after_bits, defense_before, defense_after = unpacked[1:5]
        base_before, base_after, total_before, total_after, status, row_reserved = unpacked[5:]
        if unit != source["handle"] or status not in (1, 2) or row_reserved:
            raise ValueError("Unit-stat identity or status mismatch")
        if status == 1:
            matched += 1
        rows.append(dict(
            source,
            unit=unit,
            armor_before=struct.unpack("<f", struct.pack("<I", armor_before_bits))[0],
            armor_after=struct.unpack("<f", struct.pack("<I", armor_after_bits))[0],
            defense_before=defense_before,
            defense_after=defense_after,
            intelligence_base_before=base_before,
            intelligence_base_after=base_after,
            intelligence_total_before=total_before,
            intelligence_total_after=total_after,
            status=status,
        ))
    if target_unit and matched != 1:
        raise ValueError("Unit-stat target was not matched exactly once")
    if not target_unit and matched != expected_count:
        raise ValueError("Unit-stat query skipped a selected unit")
    return dict(action=action, value_bits=value_bits, target_unit=target_unit,
                rows=rows, count=expected_count, changed=changed, completed=completed)
