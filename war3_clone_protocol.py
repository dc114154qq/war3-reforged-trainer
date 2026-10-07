"""Current-build clone batch ABI with explicit temporary-cleanup results."""
import struct

from war3_selection_protocol import (
    SIGNATURES as SELECTION_SIGNATURES,
    build_work as build_selection_work,
    decode_work as decode_selection_work,
    validate_work as validate_selection_work,
)

WORK_SIZE = 1888
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
    ("GroupEnumUnitsOfPlayer", "(Hgroup;Hplayer;Hboolexpr;)V"),
    ("IsUnitInGroup", "(Hunit;Hgroup;)B"),
)
ABI = struct.pack("<3I", 0x24268063, 216, WORK_SIZE)


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
        + struct.pack("<26Q8I", *handlers[:25], tls, flags, spawn_x_bits,
                      spawn_y_bits, 0, 0, 0, 0, 0)
        + bytes(1872 - ROWS_OFFSET)
        + struct.pack('<2Q', *handlers[25:])
    )
    validate_work(payload)
    return payload


def validate_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError("CloneWork must contain exactly 1888 bytes")
    validate_selection_work(payload[:480])
    values = struct.unpack_from("<26Q8I", payload, 480)
    handlers, tls = values[:25] + struct.unpack_from('<2Q', payload, 1872), values[25]
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
    if changed or error or completed or reserved or pad or any(payload[ROWS_OFFSET:1872]):
        raise ValueError("CloneWork output must be zero-initialized")
    if flags & CLONE_USE_SPAWN and any(bits & 0x7F800000 == 0x7F800000 for bits in (spawn_x, spawn_y)):
        raise ValueError("Clone spawn coordinates must be finite")


def failure_status(payload):
    """Only completed deletion readback, or no creation, permits continuation."""
    if len(payload) != WORK_SIZE:
        return None
    count, selection_error, destroyed, _ = struct.unpack_from('<4I', payload, 80)
    changed, error, completed, exception_code, original_error = struct.unpack_from('<5I', payload, 700)
    if not error or not 0 <= count <= 24:
        return None
    rows = []
    for index in range(count):
        clone, owner, rawcode, level, abilities, items, status, failed_ability, created_items, pad = struct.unpack_from('<2QIi6I', payload, ROWS_OFFSET + index * ROW_SIZE)
        source, source_rawcode, source_level = struct.unpack_from('<QIi', payload, 96 + index * 16)
        rows.append(dict(source=source, source_rawcode=source_rawcode, clone=clone,
                         status=status, failed_ability=failed_ability, created_items=created_items,
                         cleanup_exception_code=pad))
    clean = not changed and not completed and not original_error and all(not r['clone'] or r['status'] == 2 for r in rows)
    return dict(error=error, changed=changed, completed=completed,
                exception_code=exception_code, original_error=original_error, rows=rows,
                session_continuable=bool(clean and not exception_code and error not in (73, 74)),
                cleanup_verified=bool(clean))


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
        if not clone or clone in seen or clone in {r['handle'] for r in selection['rows']} or not owner or rawcode != source["rawcode"]:
            raise ValueError("Clone identity or rawcode mismatch")
        if ability_count > MAX_ABILITIES or item_count > MAX_ITEMS or reserved_row or pad_row:
            raise ValueError("Clone result count or reserved fields are invalid")
        if status not in (1, 2):
            raise ValueError("Clone result has an invalid lifecycle status")
        if level != source['level'] or status != (1 if flags & CLONE_KEEP else 2) or created_items != item_count:
            raise ValueError("Clone progression or lifecycle readback differs from request")
        if not flags & CLONE_PRESERVE_OWNER and owner != struct.unpack_from('<Q', payload, 64)[0]:
            raise ValueError("Clone owner differs from requested local player")
        seen.add(clone)
        rows.append(dict(source, clone=clone, owner=owner, level=level,
                         ability_count=ability_count, item_count=item_count,
                         status=status, created_items=created_items))
    return dict(rows=rows, count=expected_count, changed=changed,
                kept=bool(flags & CLONE_KEEP), copied_abilities=bool(flags & CLONE_COPY_ABILITIES),
                copied_items=bool(flags & CLONE_COPY_ITEMS))
