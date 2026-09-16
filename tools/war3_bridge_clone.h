/* Current-build clone transaction. A non-keep run removes every created object. */
#define CLONE_KEEP 0x01u
#define CLONE_PRESERVE_OWNER 0x02u
#define CLONE_COPY_ABILITIES 0x04u
#define CLONE_COPY_ITEMS 0x08u
#define CLONE_USE_SPAWN 0x10u
#define CLONE_MAX_ITEM_ABILITIES (6u * 128u)

typedef struct CloneRow {
    uint64_t clone;
    uint64_t owner;
    uint32_t rawcode;
    int32_t level;
    uint32_t ability_count;
    uint32_t item_count;
    uint32_t status;
    uint32_t reserved;
    uint32_t created_items;
    uint32_t pad;
} CloneRow;
_Static_assert(sizeof(CloneRow) == 48, "CloneRow ABI");

typedef struct CloneWork {
    SelectionWork selection;
    uint64_t (*owner)(uint64_t);
    uint32_t (*type_id)(uint64_t);
    uint32_t (*get_x)(uint64_t), (*get_y)(uint64_t), (*get_facing)(uint64_t);
    uint64_t (*create)(uint64_t, uint32_t, float *, float *, float *);
    void (*set_owner)(uint64_t, uint64_t, uint32_t);
    void (*remove_unit)(uint64_t);
    int32_t (*get_level)(uint64_t);
    void (*set_level)(uint64_t, int32_t, uint32_t);
    uint64_t (*ability_by_index)(uint64_t, int32_t);
    uint32_t (*ability_id)(uint64_t);
    int32_t (*ability_level)(uint64_t, uint32_t);
    uint8_t (*add_ability)(uint64_t, uint32_t);
    int32_t (*set_ability_level)(uint64_t, uint32_t, int32_t);
    uint64_t (*item_ability_by_index)(uint64_t, int32_t);
    uint64_t (*item_in_slot)(uint64_t, int32_t);
    uint32_t (*item_type)(uint64_t);
    int32_t (*item_charges)(uint64_t);
    uint64_t (*add_item)(uint64_t, uint32_t);
    void (*set_item_charges)(uint64_t, int32_t);
    void (*detach_item)(uint64_t, uint64_t);
    void (*remove_item)(uint64_t);
    void *expected_tls;
    uint32_t flags, spawn_x_bits, spawn_y_bits, changed, error, completed, reserved, pad;
    CloneRow rows[24];
} CloneWork;
_Static_assert(sizeof(CloneWork) == 1856, "CloneWork ABI");
__declspec(dllexport) const uint32_t clone_batch_abi[3] = {0x24268015u, 216u, 1856u};

static float clone_real(uint32_t bits) {
    union { uint32_t bits; float value; } value;
    value.bits = bits;
    return value.value;
}

static int clone_set_level(CloneWork *w, uint64_t unit, int32_t level) {
    __try {
        w->set_level(unit, level, 0);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        /* The setter can fault after mutation on this build; readback is required. */
    }
    return w->get_level(unit) == level;
}

static int clone_set_ability_level(CloneWork *w, uint64_t unit, uint32_t rawcode, int32_t level) {
    AbilityWork ability = {0};
    ability.set_level = w->set_ability_level;
    ability.get_level = w->ability_level;
    ability.expected_tls = w->expected_tls;
    ability.rawcode = rawcode;
    return BridgeSetAbilityLevelChecked(&ability, unit, level) == level;
}

static int clone_is_essential_ability(uint32_t rawcode) {
    static const uint32_t essential[] = {
        0x416d6f76u, /* Amov */
        0x4161746bu, /* Aatk */
        0x41496e76u, /* AInv */
        0x41486572u, /* AHer */
        0x416c6f63u, /* Aloc */
        0x41747267u, /* Atrg, 3.0 engine-owned target component */
        0x42686561u, /* Bhea, 3.0 engine-owned component */
    };
    for (uint32_t index = 0; index < sizeof(essential) / sizeof(essential[0]); ++index)
        if (rawcode == essential[index]) return 1;
    return 0;
}

static int clone_is_noncopyable_ability(uint32_t rawcode) {
    /* 3.0 exposes engine buff objects (for example BNht) through the unit
       ability enumerator, but BlzUnitAddAbility cannot add them to a unit. */
    if (clone_is_essential_ability(rawcode)) return 1;
    return (rawcode >> 24) == (uint32_t)'B';
}

static int clone_has_ability(CloneWork *w, uint64_t unit, uint32_t rawcode) {
    for (int32_t index = 0; index < 128; ++index) {
        uint64_t ability = w->ability_by_index(unit, index);
        if (!ability) return 0;
        if (w->ability_id(ability) == rawcode) return 1;
    }
    return 0;
}

static int clone_is_item_ability(const uint32_t *item_abilities,
                                 uint32_t item_ability_count,
                                 uint32_t rawcode) {
    uint32_t index;
    for (index = 0; index < item_ability_count; ++index)
        if (item_abilities[index] == rawcode) return 1;
    return 0;
}

static void clone_remove_items(CloneWork *w, uint64_t unit, uint64_t *items, uint32_t count) {
    uint32_t i;
    for (i = 0; i < count; ++i) {
        if (items[i]) {
            w->detach_item(unit, items[i]);
            w->remove_item(items[i]);
        }
    }
}

static void clone_discard_row(CloneWork *w, CloneRow *row) {
    uint32_t slot;
    if (!row->clone) return;
    for (slot = 0; slot < 6; ++slot) {
        uint64_t item = w->item_in_slot(row->clone, (int32_t)slot);
        if (item) {
            w->detach_item(row->clone, item);
            w->remove_item(item);
        }
    }
    w->remove_unit(row->clone);
    row->status = 2;
}

static void clone_rollback(CloneWork *w, uint32_t count) {
    uint32_t i;
    for (i = 0; i < count; ++i) clone_discard_row(w, &w->rows[i]);
}

__declspec(dllexport) uint64_t BridgeCloneQuery(void) {
    CloneWork *w = (CloneWork *)g_dispatch->work;
    uint32_t i, j, count;
    if (!w || w->expected_tls != g_dispatch->tls_value ||
        !(w->flags & (CLONE_COPY_ABILITIES | CLONE_COPY_ITEMS)) ||
        !w->owner || !w->type_id || !w->get_x || !w->get_y || !w->get_facing ||
        !w->create || !w->remove_unit || !w->get_level || !w->set_level ||
        !w->ability_by_index || !w->ability_id || !w->ability_level ||
        !w->add_ability || !w->set_ability_level || !w->item_in_slot ||
        !w->item_ability_by_index ||
        !w->item_type || !w->item_charges || !w->add_item ||
        !w->set_item_charges || !w->detach_item || !w->remove_item) {
        if (w) w->error = 60;
        return 0;
    }
    count = (uint32_t)BridgeSelect();
    if (!count || w->selection.error || !w->selection.destroyed || count != w->selection.count) {
        w->error = 61;
        return count;
    }
    for (i = 0; i < count; ++i) {
        uint64_t source = w->selection.rows[i].unit;
        uint64_t source_owner = w->owner(source);
        uint64_t target_owner = (w->flags & CLONE_PRESERVE_OWNER) ? source_owner : w->selection.player;
        uint64_t created_items[6] = {0};
        uint32_t created_item_count = 0;
        uint32_t source_item_abilities[CLONE_MAX_ITEM_ABILITIES] = {0};
        uint32_t source_item_ability_count = 0;
        uint32_t ability_count = 0, item_count = 0;
        uint32_t source_x = w->get_x(source), source_y = w->get_y(source);
        uint32_t source_facing = w->get_facing(source);
        float x = (w->flags & CLONE_USE_SPAWN) ? clone_real(w->spawn_x_bits) : clone_real(source_x);
        float y = (w->flags & CLONE_USE_SPAWN) ? clone_real(w->spawn_y_bits) : clone_real(source_y);
        float facing = clone_real(source_facing);
        CloneRow *row = &w->rows[i];
        row->owner = target_owner;
        row->rawcode = w->selection.rows[i].rawcode;
        row->status = 0;
        row->created_items = 0;
        if (!source_owner || !target_owner || !row->rawcode ||
            (source_x & 0x7f800000u) == 0x7f800000u ||
            (source_y & 0x7f800000u) == 0x7f800000u ||
            (source_facing & 0x7f800000u) == 0x7f800000u) {
            w->error = 62;
            return count;
        }
        __try {
            row->clone = w->create(target_owner, row->rawcode, &x, &y, &facing);
            if (!row->clone || w->type_id(row->clone) != row->rawcode) {
                w->error = 63;
            }
            if (!w->error && w->selection.rows[i].level > 0) {
                row->level = w->selection.rows[i].level;
                if (w->get_level(row->clone) != row->level &&
                    !clone_set_level(w, row->clone, row->level)) w->error = 64;
            } else if (!w->error) {
                row->level = 0;
            }
            /* Unit ability enumeration also exposes abilities granted by
               equipped items on this build. Record the actual item-side
               ability IDs first so the ability pass does not add them as
               hero/unit abilities; copying the item later recreates them. */
            if (!w->error && (w->flags & CLONE_COPY_ABILITIES)) {
                for (j = 0; j < 6; ++j) {
                    uint64_t source_item = w->item_in_slot(source, (int32_t)j);
                    uint32_t item_index;
                    if (!source_item) continue;
                    for (item_index = 0; item_index < 128u; ++item_index) {
                        uint64_t item_ability = w->item_ability_by_index(
                            source_item, (int32_t)item_index);
                        uint32_t item_rawcode;
                        if (!item_ability) break;
                        item_rawcode = w->ability_id(item_ability);
                        if (!item_rawcode || source_item_ability_count >= CLONE_MAX_ITEM_ABILITIES) {
                            w->error = 70;
                            break;
                        }
                        if (!clone_is_item_ability(source_item_abilities,
                                                   source_item_ability_count,
                                                   item_rawcode)) {
                            source_item_abilities[source_item_ability_count++] = item_rawcode;
                        }
                    }
                    if (w->error) break;
                }
            }
            if (!w->error && (w->flags & CLONE_COPY_ABILITIES)) {
                for (j = 0; j < 128; ++j) {
                    uint64_t ability = w->ability_by_index(source, (int32_t)j);
                    uint32_t rawcode;
                    int32_t level, existing;
                    if (!ability) break;
                    rawcode = w->ability_id(ability);
                    level = w->ability_level(source, rawcode);
                    if (!rawcode || level < 1 || ability_count >= 128) { w->error = 65; break; }
                    if (clone_is_item_ability(source_item_abilities,
                                              source_item_ability_count,
                                              rawcode)) continue;
                    if (clone_is_noncopyable_ability(rawcode)) continue;
                    existing = w->ability_level(row->clone, rawcode);
                    if (!existing && clone_has_ability(w, row->clone, rawcode)) {
                        ++ability_count;
                        continue;
                    }
                    if (!existing && !w->add_ability(row->clone, rawcode)) {
                        /* Engine-owned zero-level components (Aatk/Amov/AId2, etc.)
                           are created by CreateUnit and are not addable abilities. */
                        if (level <= 0) continue;
                        row->reserved = rawcode;
                        w->error = 66;
                        break;
                    }
                    existing = w->ability_level(row->clone, rawcode);
                    if (existing != level && !clone_set_ability_level(w, row->clone, rawcode, level)) { w->error = 67; break; }
                    ++ability_count;
                }
            }
            if (!w->error && (w->flags & CLONE_COPY_ITEMS)) {
                for (j = 0; j < 6; ++j) {
                    uint64_t item = w->item_in_slot(source, (int32_t)j);
                    uint32_t rawcode;
                    int32_t charges;
                    uint64_t new_item;
                    if (!item) continue;
                    rawcode = w->item_type(item);
                    charges = w->item_charges(item);
                    new_item = rawcode ? w->add_item(row->clone, rawcode) : 0;
                    if (!rawcode || charges < 0 || !new_item || w->item_type(new_item) != rawcode || created_item_count >= 6) { w->error = 68; break; }
                    created_items[created_item_count++] = new_item;
                    if (w->item_charges(new_item) != charges) {
                        w->set_item_charges(new_item, charges);
                        if (w->item_charges(new_item) != charges) { w->error = 69; break; }
                    }
                    ++item_count;
                }
            }
            row->ability_count = ability_count;
            row->item_count = item_count;
            row->created_items = created_item_count;
            if (!w->error) {
                row->status = (w->flags & CLONE_KEEP) ? 1 : 2;
                ++w->changed;
            }
        } __finally {
            if (!(w->flags & CLONE_KEEP)) {
                clone_remove_items(w, row->clone, created_items, created_item_count);
                if (row->clone) w->remove_unit(row->clone);
            }
        }
        if (w->error) {
            if (w->flags & CLONE_KEEP) clone_rollback(w, i + 1);
            return count;
        }
        ++w->completed;
    }
    return count;
}
