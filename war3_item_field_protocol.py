"""Current-engine batch ABI for typed item field reads and writes."""

from __future__ import annotations

import struct

from war3_selection_protocol import (
    MAX_SELECTED,
    build_work as build_selection_work,
    validate_work as validate_selection_work,
    decode_work as decode_selection_work,
)

MAX_FIELDS = 20
FIELD_KINDS = {"boolean": 0, "integer": 1, "real": 2}
SELECTION_SIZE = 480
HANDLERS_OFFSET = SELECTION_SIZE
HEADER_OFFSET = HANDLERS_OFFSET + 9 * 8
FIELDS_OFFSET = HEADER_OFFSET + 40
ITEM_HANDLES_OFFSET = FIELDS_OFFSET + MAX_FIELDS * 16
ITEM_CODES_OFFSET = ITEM_HANDLES_OFFSET + MAX_SELECTED * 8
STATUS_OFFSET = ITEM_CODES_OFFSET + MAX_SELECTED * 4
BEFORE_OFFSET = STATUS_OFFSET + MAX_SELECTED * 4
AFTER_OFFSET = BEFORE_OFFSET + MAX_SELECTED * MAX_FIELDS * 4
WORK_SIZE = AFTER_OFFSET + MAX_SELECTED * MAX_FIELDS * 4
ABI = struct.pack("<3I", 0x24268022, 216, WORK_SIZE)

SIGNATURES = (
    ("UnitItemInSlot", "(Hunit;I)Hitem;"),
    ("GetItemTypeId", "(Hitem;)I"),
    ("BlzGetItemBooleanField", "(Hitem;Hitembooleanfield;)B"),
    ("BlzGetItemIntegerField", "(Hitem;Hitemintegerfield;)I"),
    ("BlzGetItemRealField", "(Hitem;Hitemrealfield;)R"),
    ("BlzSetItemBooleanField", "(Hitem;Hitembooleanfield;B)B"),
    ("BlzSetItemIntegerField", "(Hitem;Hitemintegerfield;I)B"),
    ("BlzSetItemRealField", "(Hitem;Hitemrealfield;R)B"),
)


def _pointer(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0x10000 <= value < 0x800000000000:
        raise ValueError("Invalid item field handler")
    return value


def descriptor(field_id: int, value_kind: str, target: int = 0) -> tuple[int, int, int, int]:
    if (isinstance(field_id, bool) or not isinstance(field_id, int)
            or not 0 < field_id <= 0xFFFFFFFF):
        raise ValueError("Invalid item field id")
    try:
        kind = FIELD_KINDS[value_kind]
    except KeyError as exc:
        raise ValueError("Unsupported item field kind") from exc
    if isinstance(target, bool) or not isinstance(target, int) or not 0 <= target <= 0xFFFFFFFF:
        raise ValueError("Invalid item field target")
    return field_id, kind, 0, target


def build_work(entries, tls: int, slot: int, action: int, fields,
               target_unit: int = 0) -> bytes:
    if (isinstance(tls, bool) or not isinstance(tls, int) or not 0x10000 <= tls < 0x800000000000
            or tls % 8 or isinstance(slot, bool) or not isinstance(slot, int) or not 0 <= slot < 6
            or isinstance(action, bool) or action not in (0, 1)
            or isinstance(target_unit, bool) or not isinstance(target_unit, int)
            or not 0 <= target_unit <= 0xFFFFFFFFFFFFFFFF):
        raise ValueError("Invalid current-engine item field operation")
    descriptors = tuple(descriptor(*value) if len(value) == 3 else tuple(value) for value in fields)
    if not 0 < len(descriptors) <= MAX_FIELDS:
        raise ValueError(f"Item field batch must contain 1..{MAX_FIELDS} fields")
    for field_id, kind, scope, target in descriptors:
        if (not field_id or kind not in range(3) or scope or not 0 <= target <= 0xFFFFFFFF):
            raise ValueError("Invalid item field descriptor")
    handlers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError("Item field signature differs: " + name)
        handlers.append(_pointer(entry.handler))
    payload = bytearray(build_selection_work(entries))
    payload.extend(struct.pack("<9Q", *(handlers + [tls])))
    payload.extend(struct.pack("<8IQ", slot, action, len(descriptors), 0, 0, 0, 0, 0, target_unit))
    for row in descriptors:
        payload.extend(struct.pack("<4I", *row))
    payload.extend(bytes((MAX_FIELDS - len(descriptors)) * 16))
    payload.extend(bytes(MAX_SELECTED * 8 + MAX_SELECTED * 4 + MAX_SELECTED * 4))
    payload.extend(bytes(MAX_SELECTED * MAX_FIELDS * 4 * 2))
    payload = bytes(payload)
    validate_work(payload)
    return payload


def validate_work(payload: bytes) -> None:
    if len(payload) != WORK_SIZE:
        raise ValueError(f"Item field work must contain {WORK_SIZE} bytes")
    validate_selection_work(payload[:SELECTION_SIZE])
    handlers = struct.unpack_from("<9Q", payload, HANDLERS_OFFSET)
    if any(not 0x10000 <= value < 0x800000000000 for value in handlers[:8]):
        raise ValueError("Item field work contains an invalid handler")
    if len(set(handlers[:8])) != 8 or not 0x10000 <= handlers[8] < 0x800000000000 or handlers[8] % 8:
        raise ValueError("Item field work contains invalid pointers")
    slot, action, field_count, changed, error, completed, reserved0, reserved1, target_unit = struct.unpack_from(
        "<8IQ", payload, HEADER_OFFSET
    )
    if (slot >= 6 or action not in (0, 1) or not 1 <= field_count <= MAX_FIELDS
            or changed or error or completed or reserved0 or reserved1):
        raise ValueError("Invalid item field batch arguments")
    seen = set()
    for index in range(MAX_FIELDS):
        field_id, kind, scope, target = struct.unpack_from("<4I", payload, FIELDS_OFFSET + index * 16)
        if index < field_count:
            if not field_id or kind not in range(3) or scope or (field_id, kind) in seen:
                raise ValueError("Invalid item field descriptor")
            seen.add((field_id, kind))
        elif any((field_id, kind, scope, target)):
            raise ValueError("Item field work contains trailing descriptors")
    if any(payload[AFTER_OFFSET:]):
        raise ValueError("Item field output must be zero-initialized")


def decode_work(payload: bytes, expected_count: int) -> dict:
    if len(payload) != WORK_SIZE:
        raise ValueError("Truncated item field result")
    selection = decode_selection_work(payload[:SELECTION_SIZE], expected_count)
    slot, action, field_count, changed, error, completed, reserved0, reserved1, target_unit = struct.unpack_from(
        "<8IQ", payload, HEADER_OFFSET
    )
    if error or reserved0 or reserved1 or completed != expected_count or not field_count:
        raise ValueError(f"Item field batch incomplete: error={error}, completed={completed}/{expected_count}")
    descriptors = [
        struct.unpack_from("<4I", payload, FIELDS_OFFSET + index * 16)
        for index in range(field_count)
    ]
    handles = struct.unpack_from(f"<{MAX_SELECTED}Q", payload, ITEM_HANDLES_OFFSET)
    codes = struct.unpack_from(f"<{MAX_SELECTED}I", payload, ITEM_CODES_OFFSET)
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
            offset = (row_index * MAX_FIELDS + field_index) * 4
            before = struct.unpack_from("<I", payload, BEFORE_OFFSET + offset)[0]
            after = struct.unpack_from("<I", payload, AFTER_OFFSET + offset)[0]
            if status == 1 and ((action == 0 and after != before) or (action == 1 and after != target)):
                valid = False
            values.append(dict(field_id=field_id, kind=kind, target=target, before=before, after=after))
        rows.append(dict(
            handle=selected["handle"], rawcode=selected["rawcode"], level=selected["level"],
            status=status, item_handle=handles[row_index], item_rawcode=codes[row_index], values=values,
        ))
    if not valid:
        raise ValueError(f"Item field batch readback mismatch: changed={changed}")
    return dict(slot=slot, action=action, field_count=field_count, target_unit=target_unit,
                changed=changed, count=expected_count, rows=rows)
