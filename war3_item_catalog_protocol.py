"""Current-engine batch for creating/removing items from the 3.0 resource catalog."""

from __future__ import annotations

import struct

ACTION_CREATE = 1
ACTION_REMOVE = 2
ACTION_CREATE_LIST = 3
MAX_ITEMS = 100_000
DRY_RUN_FLAG = 0x80000000
WORK_BASE = struct.calcsize("<4Q10I")
ABI = struct.pack("<3I", 0x2426802B, 216, 0)
SIGNATURES = (
    ("ChooseRandomItem", "(I)I"),
    ("CreateItem", "(IRR)Hitem;"),
    ("RemoveItem", "(Hitem;)V"),
)


def _pointer(value: int, label: str, *, required: bool = True) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Invalid {label} pointer")
    if value == 0 and not required:
        return 0
    if not 0x10000 <= value < 0x800000000000:
        raise ValueError(f"Invalid {label} pointer")
    return value


def _finite_real(bits: int) -> bool:
    value = struct.unpack("<f", struct.pack("<I", bits))[0]
    return value == value and abs(value) != float("inf")


def required_signatures(action: int):
    if action == ACTION_CREATE:
        return SIGNATURES[:2]
    if action == ACTION_CREATE_LIST:
        return (SIGNATURES[1],)
    if action == ACTION_REMOVE:
        return (SIGNATURES[2],)
    raise ValueError("Invalid item catalog action")


def _handlers(entries, action: int) -> tuple[int, int, int]:
    values = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        required = (name, signature) in required_signatures(action)
        if not required:
            values.append(0)
            continue
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError("Item catalog signature differs: " + name)
        values.append(_pointer(entry.handler, name))
    return tuple(values)


def build_work(
    entries,
    tls: int,
    action: int = ACTION_CREATE,
    limit: int = 0,
    x_bits: int = 0,
    y_bits: int = 0,
    handles=(),
    rawcodes=(),
    dry_run: bool = False,
) -> bytes:
    if isinstance(action, bool) or action not in (ACTION_CREATE, ACTION_REMOVE, ACTION_CREATE_LIST):
        raise ValueError("Invalid item catalog action")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= MAX_ITEMS:
        raise ValueError("Item catalog limit must be between 0 and 100000")
    if isinstance(tls, bool) or not isinstance(tls, int):
        raise ValueError("Invalid item catalog TLS")
    _pointer(tls, "TLS")
    x_bits = int(x_bits)
    y_bits = int(y_bits)
    rawcodes = tuple(int(rawcode) for rawcode in rawcodes)
    if action == ACTION_REMOVE:
        if dry_run or limit or x_bits or y_bits:
            raise ValueError("Remove-item catalog request contains create arguments")
        if rawcodes:
            raise ValueError("Remove-item catalog request contains rawcodes")
        handles = tuple(int(handle) for handle in handles)
        if not handles or len(handles) > MAX_ITEMS or any(not handle for handle in handles):
            raise ValueError("Item handles must contain 1..100000 nonzero values")
        capacity = len(handles)
        count = len(handles)
        limit_word = 0
    elif action == ACTION_CREATE:
        if handles:
            raise ValueError("Create-item catalog request cannot contain handles")
        if rawcodes:
            raise ValueError("Runtime item catalog request cannot contain rawcodes")
        if not 0 <= x_bits <= 0xFFFFFFFF or not 0 <= y_bits <= 0xFFFFFFFF:
            raise ValueError("Invalid item catalog coordinates")
        if not _finite_real(x_bits) or not _finite_real(y_bits):
            raise ValueError("Item catalog coordinates must be finite")
        capacity = 0 if dry_run else (limit or MAX_ITEMS)
        count = 0
        limit_word = limit | (DRY_RUN_FLAG if dry_run else 0)
    else:
        if handles or dry_run or limit:
            raise ValueError("Item rawcode list request contains incompatible arguments")
        if not rawcodes or len(rawcodes) > MAX_ITEMS:
            raise ValueError("Item rawcode list must contain 1..100000 values")
        if not 0 <= x_bits <= 0xFFFFFFFF or not 0 <= y_bits <= 0xFFFFFFFF:
            raise ValueError("Invalid item catalog coordinates")
        if not _finite_real(x_bits) or not _finite_real(y_bits):
            raise ValueError("Item catalog coordinates must be finite")
        capacity = len(rawcodes)
        count = len(rawcodes)
        limit_word = 0
    choose, create, remove = _handlers(entries, action)
    payload = struct.pack(
        "<4Q10I",
        choose,
        create,
        remove,
        tls,
        action,
        limit_word,
        x_bits,
        y_bits,
        capacity,
        count,
        0,
        0,
        0,
        0,
    )
    if capacity:
        if action == ACTION_REMOVE:
            payload += struct.pack(f"<{capacity}Q", *handles)
        elif action == ACTION_CREATE_LIST:
            payload += struct.pack(f"<{capacity}Q", *rawcodes)
        else:
            payload += bytes(capacity * 8)
    validate_work(payload)
    return payload


def validate_work(payload: bytes) -> None:
    if len(payload) < WORK_BASE or (len(payload) - WORK_BASE) % 8:
        raise ValueError("Invalid item catalog work size")
    values = struct.unpack_from("<4Q10I", payload, 0)
    choose, create, remove, tls = values[:4]
    action, limit_word, x_bits, y_bits, capacity, count = values[4:10]
    outputs = values[10:]
    limit = limit_word & ~DRY_RUN_FLAG
    dry_run = bool(limit_word & DRY_RUN_FLAG)
    if action not in (ACTION_CREATE, ACTION_REMOVE, ACTION_CREATE_LIST) or limit > MAX_ITEMS:
        raise ValueError("Invalid item catalog request")
    required = required_signatures(action)
    if action == ACTION_CREATE:
        if not choose or not create or remove or count or (dry_run and capacity) or (not dry_run and capacity != (limit or MAX_ITEMS)):
            raise ValueError("Invalid item catalog create pointers or capacity")
        if not _finite_real(x_bits) or not _finite_real(y_bits):
            raise ValueError("Invalid item catalog coordinates")
    elif action == ACTION_CREATE_LIST:
        if choose or not create or remove or dry_run or not count or count != capacity:
            raise ValueError("Invalid item rawcode list pointers or count")
        if not _finite_real(x_bits) or not _finite_real(y_bits):
            raise ValueError("Invalid item catalog coordinates")
        for index in range(count):
            rawcode = struct.unpack_from("<Q", payload, WORK_BASE + index * 8)[0]
            if rawcode > 0xFFFFFFFF:
                raise ValueError("Item rawcode list contains a wide value")
    else:
        if choose or create or not remove or dry_run or not count or count != capacity:
            raise ValueError("Invalid item catalog remove pointers or count")
        if any(struct.unpack_from("<Q", payload, WORK_BASE + index * 8)[0] == 0 for index in range(count)):
            raise ValueError("Item catalog remove handles must be nonzero")
    for index, (name, _signature) in enumerate(SIGNATURES):
        pointer = (choose, create, remove)[index]
        if (name, _signature) in required:
            _pointer(pointer, name)
        elif pointer:
            _pointer(pointer, name, required=False)
    _pointer(tls, "TLS")
    if any(outputs):
        raise ValueError("Item catalog outputs must be zero-initialized")


def decode_work(payload: bytes, _expected_count=None) -> dict:
    if len(payload) < WORK_BASE or (len(payload) - WORK_BASE) % 8:
        raise ValueError("Incomplete item catalog result")
    values = struct.unpack_from("<4Q10I", payload, 0)
    action, limit_word, _x_bits, _y_bits, capacity, count = values[4:10]
    total, created, error, completed = values[10:]
    if error or completed != 1:
        raise ValueError(
            f"Item catalog incomplete: error={error}, completed={completed}"
        )
    if action in (ACTION_CREATE, ACTION_CREATE_LIST):
        if not total or created > capacity or created > len(payload[WORK_BASE:]) // 8:
            raise ValueError("Invalid item catalog create counts")
        handles = tuple(
            struct.unpack_from("<Q", payload, WORK_BASE + index * 8)[0]
            for index in range(created)
        )
        if len(handles) != created or any(not handle for handle in handles):
            raise ValueError("Item catalog returned incomplete handles")
        return dict(total=total, created=created, handles=handles, dry_run=bool(limit_word & DRY_RUN_FLAG))
    if action == ACTION_REMOVE:
        if count != capacity or created > count:
            raise ValueError("Invalid item catalog remove counts")
        return dict(removed=created, count=count)
    raise ValueError("Invalid item catalog action in result")
