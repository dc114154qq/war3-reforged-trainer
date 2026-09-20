"""Warcraft III 3.0 expanded bag, loadout, and talent snapshot ABI."""

import struct

from war3_selection_protocol import (
    build_work as selection_work,
    decode_work as selection_result,
    validate_work as selection_validate,
)


MAX_ABILITIES = 24
MAX_BAG_SLOTS = 30
EQUIPMENT_SLOTS = 9
WORK_SIZE = 1808
ABI = struct.pack("<3I", 0x24268039, 216, WORK_SIZE)
SIGNATURES = (
    ("UnitExtendedInventorySize", "(Hunit;)I"),
    ("UnitItemInBagSlot", "(Hunit;I)Hitem;"),
    ("ConvertLoadoutSlot", "(I)Hloadoutslot;"),
    ("UnitItemInEquipmentSlot", "(Hunit;Hloadoutslot;)Hitem;"),
    ("UnitUnequipItemFromSlot", "(Hunit;Hloadoutslot;)Hitem;"),
    ("GetItemTypeId", "(Hitem;)I"),
    ("GetItemCharges", "(Hitem;)I"),
    ("GetUnitAbilityLevel", "(Hunit;I)I"),
    ("UnitAddItemById", "(Hunit;I)Hitem;"),
    ("UnitAddItem", "(Hunit;Hitem;)B"),
    ("UnitEquipItem", "(Hunit;Hitem;)B"),
    ("SetItemCharges", "(Hitem;I)V"),
    ("UnitRemoveItem", "(Hunit;Hitem;)V"),
    ("GetUnitX", "(Hunit;)R"),
    ("GetUnitY", "(Hunit;)R"),
    ("GetItemEquipmentType", "(Hitem;)HequipmentType;"),
    ("RemoveItem", "(Hitem;)V"),
)


def build_work(
    entries,
    tls,
    ability_rawcodes=(),
    action=0,
    target_unit=0,
    slot=0,
    item_rawcode=0,
    item_handle=0,
):
    handlers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError("3.0 extension signature differs: " + name)
        handlers.append(entry.handler)
    ability_rawcodes = tuple(int(value) for value in ability_rawcodes)
    if len(ability_rawcodes) > MAX_ABILITIES:
        raise ValueError("3.0 extension ability probe exceeds 24 entries")
    codes = ability_rawcodes + (0,) * (MAX_ABILITIES - len(ability_rawcodes))
    payload = (
        selection_work(entries)
        + struct.pack(
            "<20Q10I",
            *handlers,
            tls,
            target_unit,
            item_handle,
            action,
            slot,
            item_rawcode,
            len(ability_rawcodes),
            0,
            0,
            0,
            0,
            0,
            0,
        )
        + struct.pack("<24I", *codes)
        + bytes(WORK_SIZE - 776)
    )
    validate_work(payload)
    return payload


def validate_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError("3.0 extension work size differs")
    selection_validate(payload[:480])
    pointers = struct.unpack_from("<18Q", payload, 480)
    if any(not 0x10000 <= value < 0x800000000000 for value in pointers):
        raise ValueError("3.0 extension handler or TLS is invalid")
    target_unit, item_handle = struct.unpack_from("<2Q", payload, 624)
    values = struct.unpack_from("<10I", payload, 640)
    action, slot, item_rawcode, ability_count = values[:4]
    if target_unit and not 0x10000 <= target_unit < 0x800000000000:
        raise ValueError("3.0 extension target is invalid")
    if action not in (0, 1, 2, 3, 4, 5, 6, 7, 8) or ability_count > MAX_ABILITIES:
        raise ValueError("3.0 extension request is invalid")
    if action == 0 and (slot or item_rawcode):
        raise ValueError("3.0 extension snapshot contains write arguments")
    if action == 1 and (slot or not item_rawcode):
        raise ValueError("3.0 talent-point request is invalid")
    if action == 2 and (slot >= EQUIPMENT_SLOTS or item_rawcode):
        raise ValueError("3.0 unequip request is invalid")
    if action in (3, 4) and (slot or not item_rawcode or not item_handle):
        raise ValueError("3.0 existing-item recovery request is invalid")
    if action in (5, 6, 8) and (not item_rawcode or not item_handle):
        raise ValueError("3.0 bag-item request is invalid")
    if action in (5, 8) and slot:
        raise ValueError("3.0 item removal request contains a value")
    if action == 7 and (slot or not item_rawcode or item_handle or ability_count != 1):
        raise ValueError("3.0 talent-point request is invalid")
    if action not in (3, 4, 5, 6, 8) and item_handle:
        raise ValueError("3.0 extension item handle is unexpected")
    codes = struct.unpack_from("<24I", payload, 680)
    active = codes[:ability_count]
    if any(not value for value in active) or len(set(active)) != len(active):
        raise ValueError("3.0 extension ability probes are invalid")
    if any(codes[ability_count:]) or any(values[4:]) or any(payload[776:]):
        raise ValueError("3.0 extension output must start empty")


def decode_work(payload, count):
    if len(payload) != WORK_SIZE:
        raise ValueError("3.0 extension response is incomplete")
    selection = selection_result(payload[:480], count)
    target_unit, item_handle = struct.unpack_from("<2Q", payload, 624)
    (action, slot, item_rawcode, ability_count, error, completed, changed,
     bag_size, removed_rawcode, reserved) = struct.unpack_from("<10I", payload, 640)
    if (error or completed != 1 or reserved or bag_size > MAX_BAG_SLOTS
            or ability_count > MAX_ABILITIES):
        raise ValueError(
            f"3.0 extension incomplete: error={error}, completed={completed}, "
            f"bag_size={bag_size}"
        )
    if sum(row["handle"] == target_unit for row in selection["rows"]) != 1:
        raise ValueError("3.0 extension target changed")
    codes = struct.unpack_from("<24I", payload, 680)
    levels = struct.unpack_from("<24i", payload, 776)

    def item_rows(offset, total):
        rows = []
        for index in range(total):
            handle, rawcode, charges, equipment_type, row_reserved = struct.unpack_from(
                "<QIiII", payload, offset + index * 24,
            )
            if row_reserved:
                raise ValueError("3.0 extension item row is invalid")
            rows.append(dict(slot=index, handle=handle, rawcode=rawcode, charges=charges,
                             equipment_type=equipment_type))
        return tuple(rows)

    if action == 0 and changed:
        raise ValueError("3.0 extension snapshot unexpectedly changed state")
    if action in (1, 2, 3, 4, 5, 6, 7, 8) and changed != 1:
        raise ValueError("3.0 extension write was not confirmed")
    return dict(
        selection=selection,
        target_unit=target_unit,
        action=action,
        item_rawcode=item_rawcode,
        slot=slot,
        changed=changed,
        removed_rawcode=removed_rawcode,
        bag_size=bag_size,
        item_handle=item_handle,
        bag=item_rows(872, MAX_BAG_SLOTS),
        equipment=item_rows(1592, EQUIPMENT_SLOTS),
        abilities={codes[index]: levels[index] for index in range(ability_count)},
    )
