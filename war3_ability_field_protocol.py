"""Current-engine batch ABI for Warcraft III ability field reads and writes."""

from __future__ import annotations

import struct

from war3_selection_protocol import (
    MAX_SELECTED,
    SIGNATURES as SELECTION_SIGNATURES,
    build_work as build_selection_work,
    validate_work as validate_selection_work,
    decode_work as decode_selection_work,
)

MAX_FIELDS = 32
FIELD_KINDS = {"boolean": 0, "integer": 1, "real": 2}
FIELD_SCOPES = {"field": 0, "level": 1}

# SelectionWork (480), 15 native pointers plus TLS (128), header (40),
# descriptors (32 * 16), handles (24 * 8), levels/status (24 * 4 each),
# and before/after values (24 * 32 * 4 each).
SELECTION_SIZE = 480
HANDLERS_OFFSET = SELECTION_SIZE
HEADER_OFFSET = HANDLERS_OFFSET + 16 * 8
FIELDS_OFFSET = HEADER_OFFSET + 40
HANDLES_OFFSET = FIELDS_OFFSET + MAX_FIELDS * 16
LEVELS_OFFSET = HANDLES_OFFSET + MAX_SELECTED * 8
STATUS_OFFSET = LEVELS_OFFSET + MAX_SELECTED * 4
BEFORE_OFFSET = STATUS_OFFSET + MAX_SELECTED * 4
AFTER_OFFSET = BEFORE_OFFSET + MAX_SELECTED * MAX_FIELDS * 4
WORK_SIZE = AFTER_OFFSET + MAX_SELECTED * MAX_FIELDS * 4
ABI = struct.pack("<3I", 0x24268021, 216, WORK_SIZE)

SIGNATURES = (
    ("BlzGetUnitAbilityByIndex", "(Hunit;I)Hability;"),
    ("BlzGetAbilityId", "(Hability;)I"),
    ("GetUnitAbilityLevel", "(Hunit;I)I"),
    ("BlzGetAbilityBooleanField", "(Hability;Habilitybooleanfield;)B"),
    ("BlzGetAbilityIntegerField", "(Hability;Habilityintegerfield;)I"),
    ("BlzGetAbilityRealField", "(Hability;Habilityrealfield;)R"),
    ("BlzGetAbilityBooleanLevelField", "(Hability;Habilitybooleanlevelfield;I)B"),
    ("BlzGetAbilityIntegerLevelField", "(Hability;Habilityintegerlevelfield;I)I"),
    ("BlzGetAbilityRealLevelField", "(Hability;Habilityreallevelfield;I)R"),
    ("BlzSetAbilityBooleanField", "(Hability;Habilitybooleanfield;B)B"),
    ("BlzSetAbilityIntegerField", "(Hability;Habilityintegerfield;I)B"),
    ("BlzSetAbilityRealField", "(Hability;Habilityrealfield;R)B"),
    ("BlzSetAbilityBooleanLevelField", "(Hability;Habilitybooleanlevelfield;IB)B"),
    ("BlzSetAbilityIntegerLevelField", "(Hability;Habilityintegerlevelfield;II)B"),
    ("BlzSetAbilityRealLevelField", "(Hability;Habilityreallevelfield;IR)B"),
)


def _pointer(value: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0x10000 <= value < 0x800000000000:
        raise ValueError(f"Invalid {label} pointer")
    return value


def _field_row(value) -> tuple[int, int, int, int]:
    if not isinstance(value, (tuple, list)) or len(value) != 4:
        raise ValueError("Ability field descriptors must contain four values")
    field_id, kind, scope, target = value
    if any(isinstance(item, bool) or not isinstance(item, int) for item in value):
        raise ValueError("Ability field descriptors must be integers")
    if not 0 < field_id <= 0xFFFFFFFF or kind not in range(3) or scope not in range(2):
        raise ValueError("Invalid ability field descriptor")
    if not 0 <= target <= 0xFFFFFFFF:
        raise ValueError("Invalid ability field target")
    return field_id, kind, scope, target


def build_work(entries, tls: int, rawcode: int, level: int, action: int,
               fields, target_unit: int = 0) -> bytes:
    if isinstance(tls, bool) or not isinstance(tls, int):
        raise ValueError("Invalid ability field TLS")
    if (isinstance(rawcode, bool) or not isinstance(rawcode, int) or not 0 < rawcode <= 0xFFFFFFFF
            or isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= 1000
            or isinstance(action, bool) or action not in (0, 1)
            or isinstance(target_unit, bool) or not isinstance(target_unit, int)
            or not 0 <= target_unit <= 0xFFFFFFFFFFFFFFFF):
        raise ValueError("Invalid current-engine ability field operation")
    descriptors = tuple(_field_row(value) for value in fields)
    if not 0 < len(descriptors) <= MAX_FIELDS:
        raise ValueError(f"Ability field batch must contain 1..{MAX_FIELDS} fields")
    handlers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError("Ability field signature differs: " + name)
        handlers.append(_pointer(entry.handler, name))
    _pointer(tls, "TLS")
    payload = bytearray(build_selection_work(entries))
    payload.extend(struct.pack("<16Q", *(handlers + [tls])))
    payload.extend(struct.pack(
        "<8IQ", rawcode, level, action, len(descriptors), 0, 0, 0, 0, target_unit,
    ))
    for descriptor in descriptors:
        payload.extend(struct.pack("<4I", *descriptor))
    payload.extend(bytes((MAX_FIELDS - len(descriptors)) * 16))
    payload.extend(bytes(MAX_SELECTED * 8))
    payload.extend(bytes(MAX_SELECTED * 4))
    payload.extend(bytes(MAX_SELECTED * 4))
    payload.extend(bytes(MAX_SELECTED * MAX_FIELDS * 4 * 2))
    payload = bytes(payload)
    validate_work(payload)
    return payload


def validate_work(payload: bytes) -> None:
    if len(payload) != WORK_SIZE:
        raise ValueError(f"Ability field work must contain {WORK_SIZE} bytes")
    validate_selection_work(payload[:SELECTION_SIZE])
    values = struct.unpack_from("<16Q", payload, HANDLERS_OFFSET)
    handlers, tls = values[:15], values[15]
    if any(not 0x10000 <= pointer < 0x800000000000 for pointer in handlers):
        raise ValueError("Ability field work contains an invalid handler")
    if len(set(handlers)) != len(handlers):
        raise ValueError("Ability field handlers must be distinct")
    if not 0x10000 <= tls < 0x800000000000 or tls % 8:
        raise ValueError("Ability field work contains an invalid TLS pointer")
    rawcode, level, action, field_count, changed, error, completed, reserved, target_unit = struct.unpack_from(
        "<8IQ", payload, HEADER_OFFSET
    )
    if (not rawcode or not 1 <= level <= 1000 or action not in (0, 1)
            or not 1 <= field_count <= MAX_FIELDS or changed or error or completed or reserved
            or target_unit > 0xFFFFFFFFFFFFFFFF):
        raise ValueError("Invalid ability field batch arguments")
    descriptors = []
    for index in range(MAX_FIELDS):
        field_id, kind, scope, target = struct.unpack_from(
            "<4I", payload, FIELDS_OFFSET + index * 16
        )
        if index < field_count:
            if not field_id or kind not in range(3) or scope not in range(2):
                raise ValueError("Invalid ability field descriptor")
            descriptors.append((field_id, kind, scope, target))
        elif any((field_id, kind, scope, target)):
            raise ValueError("Ability field work contains trailing descriptors")
    if len({(field_id, kind, scope) for field_id, kind, scope, _ in descriptors}) != len(descriptors):
        raise ValueError("Ability field descriptors must be unique")
    if any(payload[AFTER_OFFSET:]):
        raise ValueError("Ability field output must be zero-initialized")


def decode_work(payload: bytes, expected_count: int) -> dict:
    if len(payload) != WORK_SIZE:
        raise ValueError("Truncated ability field result")
    selection = decode_selection_work(payload[:SELECTION_SIZE], expected_count)
    rawcode, level, action, field_count, changed, error, completed, reserved, target_unit = struct.unpack_from(
        "<8IQ", payload, HEADER_OFFSET
    )
    if error or reserved or completed != expected_count or not field_count:
        raise ValueError(
            f"Ability field batch incomplete: error={error}, completed={completed}/{expected_count}"
        )
    descriptors = [
        struct.unpack_from("<4I", payload, FIELDS_OFFSET + index * 16)
        for index in range(field_count)
    ]
    handles = struct.unpack_from(f"<{MAX_SELECTED}Q", payload, HANDLES_OFFSET)
    levels = struct.unpack_from(f"<{MAX_SELECTED}i", payload, LEVELS_OFFSET)
    statuses = struct.unpack_from(f"<{MAX_SELECTED}I", payload, STATUS_OFFSET)
    rows = []
    valid = changed <= expected_count * field_count
    for row_index, selected in enumerate(selection["rows"]):
        status = statuses[row_index]
        if status not in (1, 2, 3):
            valid = False
        if target_unit and selected["handle"] == target_unit and status != 1:
            valid = False
        values = []
        for field_index, (field_id, kind, scope, target) in enumerate(descriptors):
            index = row_index * MAX_FIELDS + field_index
            before = struct.unpack_from("<I", payload, BEFORE_OFFSET + index * 4)[0]
            after = struct.unpack_from("<I", payload, AFTER_OFFSET + index * 4)[0]
            field_ok = status != 1 or (action == 0 and after == before) or (action == 1 and after == target)
            if not field_ok:
                valid = False
            values.append(dict(field_id=field_id, kind=kind, scope=scope,
                               target=target, before=before, after=after))
        rows.append(dict(
            handle=selected["handle"],
            rawcode=selected["rawcode"],
            level=selected["level"],
            status=status,
            ability_handle=handles[row_index],
            ability_level=levels[row_index],
            values=values,
        ))
    if not valid:
        raise ValueError(f"Ability field batch readback mismatch: changed={changed}")
    return dict(
        rawcode=rawcode,
        level=level,
        action=action,
        field_count=field_count,
        target_unit=target_unit,
        changed=changed,
        count=expected_count,
        rows=rows,
    )


def descriptor(field_id: int, value_kind: str, scope: str, target: int = 0) -> tuple[int, int, int, int]:
    try:
        kind = FIELD_KINDS[value_kind]
        scope_id = FIELD_SCOPES[scope]
    except KeyError as exc:
        raise ValueError("Unsupported ability field kind or scope") from exc
    return _field_row((field_id, kind, scope_id, target))
