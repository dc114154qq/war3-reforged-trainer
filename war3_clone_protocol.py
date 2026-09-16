"""Current-build clone batch ABI with explicit temporary-cleanup results."""
import struct

from war3_selection_protocol import (
    SIGNATURES as SELECTION_SIGNATURES,
    build_work as build_selection_work,
    decode_work as decode_selection_work,
    validate_work as validate_selection_work,
)

WORK_SIZE = 1872
ROW_SIZE = 48
ROWS_OFFSET = 720
MAX_ABILITIES = 128
MAX_ITEMS = 6

CLONE_KEEP = 0x01
CLONE_PRESERVE_OWNER = 0x02
CLONE_COPY_ABILITIES = 0x04
CLONE_COPY_ITEMS = 0x08
CLONE_USE_SPAWN = 0x10

SIGNATURES = (
    ("GetOwningPlayer", "(Hunit;)Hplayer;"),
    ("GetUnitTypeId", "(Hunit;)I"),
    ("GetUnitX", "(Hunit;)R"),
    ("GetUnitY", "(Hunit;)R"),
    ("GetUnitFacing", "(Hunit;)R"),
    ("CreateUnit", "(Hplayer;IRRR)Hunit;"),
    ("SetUnitOwner", "(Hunit;Hplayer;B)V"),
    ("RemoveUnit", "(Hunit;)V"),
    ("GetHeroLevel", "(Hunit;)I"),
    ("SetHeroLevel", "(Hunit;IB)V"),
    ("GetHeroSkillPoints", "(Hunit;)I"),
    ("UnitModifySkillPoints", "(Hunit;I)B"),
    ("BlzGetUnitAbilityByIndex", "(Hunit;I)Hability;"),
    ("BlzGetAbilityId", "(Hability;)I"),
    ("GetUnitAbilityLevel", "(Hunit;I)I"),
    ("UnitAddAbility", "(Hunit;I)B"),
    ("SetUnitAbilityLevel", "(Hunit;II)I"),
    ("BlzGetItemAbilityByIndex", "(Hitem;I)Hability;"),
    ("UnitItemInSlot", "(Hunit;I)Hitem;"),
    ("GetItemTypeId", "(Hitem;)I"),
    ("GetItemCharges", "(Hitem;)I"),
    ("UnitAddItemById", "(Hunit;I)Hitem;"),
    ("SetItemCharges", "(Hitem;I)V"),
    ("UnitRemoveItem", "(Hunit;Hitem;)V"),
    ("RemoveItem", "(Hitem;)V"),
)
ABI = struct.pack("<3I", 0x24268015, 216, WORK_SIZE)


def build_work(entries, tls, *, flags=CLONE_COPY_ABILITIES | CLONE_COPY_ITEMS,
               spawn_x_bits=0, spawn_y_bits=0):
    selected = build_selection_work(entries)
    handlers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError("Clone native signature differs: " + name)
        handlers.append(entry.handler)
    payload = (
        selected
        + struct.pack("<26Q8I", *handlers, tls, flags, spawn_x_bits,
                      spawn_y_bits, 0, 0, 0, 0, 0)
        + bytes(WORK_SIZE - ROWS_OFFSET)
    )
    validate_work(payload)
    return payload


def validate_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError("CloneWork must contain exactly 1872 bytes")
    validate_selection_work(payload[:480])
    values = struct.unpack_from("<26Q8I", payload, 480)
    handlers, tls = values[:25], values[25]
    flags, spawn_x, spawn_y, changed, error, completed, reserved, pad = values[26:]
    if any(not 0x10000 <= value < 0x800000000000 for value in handlers):
        raise ValueError("CloneWork contains an invalid handler")
    if len(set(handlers)) != len(handlers):
        raise ValueError("CloneWork contains duplicate handlers")
    if not 0x10000 <= tls < 0x800000000000 or tls % 8:
        raise ValueError("CloneWork contains an invalid TLS value")
    if flags & ~(CLONE_KEEP | CLONE_PRESERVE_OWNER | CLONE_COPY_ABILITIES |
                 CLONE_COPY_ITEMS | CLONE_USE_SPAWN):
        raise ValueError("CloneWork contains unknown flags")
    if changed or error or completed or reserved or pad or any(payload[ROWS_OFFSET:]):
        raise ValueError("CloneWork output must be zero-initialized")


def decode_work(payload, expected_count):
    if len(payload) != WORK_SIZE:
        raise ValueError("Incomplete clone result")
    selection = decode_selection_work(payload[:480], expected_count)
    values = struct.unpack_from("<26Q8I", payload, 480)
    flags, spawn_x, spawn_y, changed, error, completed, reserved, pad = values[26:]
    if error or reserved or pad or completed != expected_count or changed != expected_count:
        raise ValueError(
            f"Clone batch incomplete: error={error}, completed={completed}/{expected_count}, "
            f"changed={changed}"
        )
    rows = []
    seen = set()
    for index, source in enumerate(selection["rows"]):
        offset = ROWS_OFFSET + index * ROW_SIZE
        clone, owner, rawcode, level, ability_count, item_count, status, reserved_row, created_items, pad_row = struct.unpack_from(
            "<2QIi6I", payload, offset
        )
        if not clone or clone in seen or not owner or rawcode != source["rawcode"]:
            raise ValueError("Clone identity or rawcode mismatch")
        if ability_count > MAX_ABILITIES or item_count > MAX_ITEMS or reserved_row or pad_row:
            raise ValueError("Clone result count or reserved fields are invalid")
        if status not in (1, 2):
            raise ValueError("Clone result has an invalid lifecycle status")
        seen.add(clone)
        rows.append(dict(source, clone=clone, owner=owner, level=level,
                         ability_count=ability_count, item_count=item_count,
                         status=status, created_items=created_items))
    return dict(rows=rows, count=expected_count, changed=changed,
                kept=bool(flags & CLONE_KEEP), copied_abilities=bool(flags & CLONE_COPY_ABILITIES),
                copied_items=bool(flags & CLONE_COPY_ITEMS))
