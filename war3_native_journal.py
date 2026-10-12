"""Decode bounded native-call observations; this module performs no game calls."""
import struct

CAPACITY = 1024
EVENT_SIZE = 56
HEADER_SIZE = 16 + EVENT_SIZE
WORK_SIZE = HEADER_SIZE + CAPACITY * EVENT_SIZE
NATIVES = {
    1: ("BlzGetUnitAbility", "handle"),
    2: ("BlzGetUnitAbilityByIndex", "handle"),
    3: ("BlzGetAbilityId", "rawcode"),
    4: ("GetUnitAbilityLevel", "integer"),
    5: ("UnitAddAbility", "boolean"),
    6: ("SetUnitAbilityLevel", "integer"),
    7: ("UnitRemoveAbility", "boolean"),
    8: ("BlzGetItemAbility", "handle"),
    9: ("BlzGetItemAbilityByIndex", "handle"),
    10: ("BlzItemAddAbility", "boolean"),
    11: ("UnitItemInSlot", "handle"),
    12: ("GetItemTypeId", "rawcode"),
    13: ("GetItemCharges", "integer"),
    14: ("CreateItem", "handle"),
    15: ("UnitAddItem", "boolean"),
    16: ("UnitDropItemSlot", "boolean"),
    17: ("UnitAddItemToSlotById", "boolean"),
    18: ("BlzGetAbilityRealLevelField", "real_bits"),
    19: ("BlzSetAbilityRealLevelField", "boolean"),
    20: ("BlzGetAbilityIntegerLevelField", "integer"),
    21: ("BlzSetAbilityIntegerLevelField", "boolean"),
    22: ("GetUnitCurrentOrder", "integer"),
    23: ("IssueImmediateOrderById", "boolean"),
    24: ("IssuePointOrderById", "boolean"),
    25: ("GetUnitState", "real_bits"),
    26: ("BlzGetUnitAbilityCooldownRemaining", "real_bits"),
    27: ("BlzEndUnitAbilityCooldown", "void"),
    28: ("BlzStartUnitAbilityCooldown", "void"),
    29: ("CreateTimer", "handle"),
    30: ("TimerStart", "void"),
    31: ("TimerGetElapsed", "real_bits"),
    32: ("DestroyTimer", "void"),
    33: ("UnitRemoveItem", "void"),
    34: ("RemoveItem", "void"),
    35: ("GetUnitX", "real_bits"),
    36: ("GetUnitY", "real_bits"),
    37: ("GetUnitTypeId", "rawcode"),
}
PHASES = {
    0: "entry", 1: "ability_before", 2: "ability_identity_recheck",
    3: "ability_add_or_activate", 4: "ability_remove_or_reset",
    5: "ability_final_readback_or_restore",
    10: "item_identity_before", 11: "item_abilities_before",
    12: "item_ability_add", 13: "item_identity_after",
    14: "item_abilities_after",
    20: "cast_capture", 21: "cast_ability_add_or_activate",
    22: "cast_area", 23: "cast_cost_and_cooldown", 24: "cast_issue_order",
    25: "cast_observe", 26: "cast_cleanup",
    30: "item_creation_before", 31: "item_creation",
    32: "item_creation_readback", 33: "item_creation_rollback",
}


def rawcode(value):
    if not isinstance(value, int) or not 0 < value <= 0xFFFFFFFF:
        return None
    data = value.to_bytes(4, "big")
    return data.decode("ascii") if all(32 <= byte < 127 for byte in data) else None


def build_work(enabled=None):
    if enabled is None:
        from war3_services.operation_trace import active_trace
        enabled = active_trace() is not None
    return struct.pack("<4I", int(bool(enabled)), 0, 0, 0) + bytes(WORK_SIZE - 16)


def validate_work(payload):
    if len(payload) != WORK_SIZE or struct.unpack_from("<I", payload)[0] not in (0, 1):
        raise ValueError("Native journal size or enable flag differs")
    if any(payload[4:]):
        raise ValueError("Native journal input contains observations")


def decode_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError("Native journal response size differs")
    enabled, count, dropped, phase = struct.unpack_from("<4I", payload)
    if enabled not in (0, 1) or count > CAPACITY:
        raise ValueError("Native journal response header differs")

    def event(offset):
        sequence, native, stage, flags, a, b, c, d, result = struct.unpack_from("<4I5Q", payload, offset)
        name, kind = NATIVES.get(native, (f"unknown_native_{native}", "unknown"))
        row = dict(sequence=sequence, native=name, native_id=native,
                   phase=PHASES.get(stage, f"phase_{stage}"), phase_id=stage,
                   entered=bool(flags & 1), returned=bool(flags & 2),
                   arguments=[a, b, c, d], arguments_hex=[hex(v) for v in (a, b, c, d)],
                   result_raw=result if flags & 2 else None, result_kind=kind,
                   result_hex=hex(result) if flags & 2 else None,
                   tail_exception_recovered=bool(flags & 4))
        argument_names={
            1:('unit','ability_rawcode'),2:('unit','index'),3:('ability',),
            4:('unit','ability_rawcode'),5:('unit','ability_rawcode'),
            6:('unit','ability_rawcode','level'),7:('unit','ability_rawcode'),
            8:('item','ability_rawcode'),9:('item','index'),10:('item','ability_rawcode'),
            11:('unit','slot'),12:('item',),13:('item',),14:('item_rawcode','x_bits','y_bits'),
            15:('unit','item'),16:('unit','item','slot'),17:('unit','item_rawcode','slot'),
            18:('ability','field_rawcode','level_index'),19:('ability','field_rawcode','level_index','value_bits'),
            20:('ability','field_rawcode','level_index'),21:('ability','field_rawcode','level_index','integer_value'),
            22:('unit',),23:('unit','order_id'),24:('unit','order_id','x_bits','y_bits'),
            25:('unit','state_id'),26:('unit','ability_rawcode'),27:('unit','ability_rawcode'),
            28:('unit','ability_rawcode','remaining_bits'),29:(),
            30:('timer','timeout_bits','periodic','callback'),31:('timer',),32:('timer',),
            33:('unit','item'),34:('item',),35:('unit',),36:('unit',),37:('unit',),
        }.get(native,('a','b','c','d'))
        row['named_arguments']=dict(zip(argument_names,(a,b,c,d)))
        row['argument_rawcodes']={key:rawcode(value) for key,value in row['named_arguments'].items() if key.endswith('_rawcode')}
        if flags & 2:
            if kind == "integer":
                row["result"] = struct.unpack("<i", struct.pack("<I", result & 0xFFFFFFFF))[0]
            elif kind == "real_bits":
                row["result"] = struct.unpack("<f", struct.pack("<I", result & 0xFFFFFFFF))[0]
            elif kind == "boolean":
                row["result"] = bool(result)
            elif kind != "void":
                row["result"] = result
            if kind == "rawcode":
                row["result_rawcode"] = rawcode(result)
        return row

    calls = [event(HEADER_SIZE + i * EVENT_SIZE) for i in range(count)]
    last = event(16) if struct.unpack_from("<I", payload, 16)[0] else None
    return dict(enabled=bool(enabled), capacity=CAPACITY, recorded_count=count,
                dropped_count=dropped, complete=enabled == 1 and dropped == 0,
                phase=PHASES.get(phase, f"phase_{phase}"), calls=calls,
                last_call=last, total_calls_started=count + dropped,
                omission_reason="bounded_capacity_exceeded" if dropped else None,
                evidence_scope="observed calls only; object-definition registration cause is not inferred")
