/* Current-build armor, defense type, and total intelligence transaction. */
#define UNIT_STATS_QUERY 0u
#define UNIT_STATS_SET_ARMOR 1u
#define UNIT_STATS_SET_DEFENSE_TYPE 2u
#define UNIT_STATS_SET_INTELLIGENCE 3u
#define UNIT_IF_DEFENSE_TYPE_RAWCODE 0x75647479u

typedef struct UnitStatsRow {
    uint64_t unit;
    uint32_t armor_before_bits, armor_after_bits;
    uint32_t defense_before, defense_after;
    uint32_t intelligence_base_before, intelligence_base_after;
    uint32_t intelligence_total_before, intelligence_total_after;
    uint32_t status, reserved;
} UnitStatsRow;
_Static_assert(sizeof(UnitStatsRow) == 48, "UnitStatsRow ABI");

typedef struct UnitStatsWork {
    SelectionWork selection;
    uint32_t (*get_armor)(uint64_t);
    void (*set_armor)(uint64_t, float *);
    uint64_t (*convert_unit_integer_field)(uint32_t);
    int32_t (*get_unit_integer_field)(uint64_t, uint64_t);
    uint8_t (*set_unit_integer_field)(uint64_t, uint64_t, int32_t);
    int32_t (*get_hero_int)(uint64_t, uint32_t);
    void (*set_hero_int)(uint64_t, int32_t, uint32_t);
    void *expected_tls;
    uint32_t action, value_bits, changed, error, completed, reserved;
    uint64_t target_unit;
    UnitStatsRow rows[24];
} UnitStatsWork;
_Static_assert(sizeof(UnitStatsWork) == 1728, "UnitStatsWork ABI");
__declspec(dllexport) const uint32_t unit_stats_batch_abi[3] = {0x2426803Bu, 216u, 1728u};

static float UnitStatsReal(uint32_t bits) {
    union { uint32_t bits; float value; } value;
    value.bits = bits;
    return value.value;
}

static int UnitStatsFinite(uint32_t bits) {
    return (bits & 0x7f800000u) != 0x7f800000u;
}

__declspec(dllexport) uint64_t BridgeUnitStatsQuery(void) {
    UnitStatsWork *w = (UnitStatsWork *)g_dispatch->work;
    uint64_t count, defense_field;
    uint32_t i, matched = 0;
    if (!w || w->expected_tls != g_dispatch->tls_value ||
        w->action > UNIT_STATS_SET_INTELLIGENCE ||
        (w->action != UNIT_STATS_QUERY && !w->target_unit) ||
        !w->get_armor || !w->set_armor || !w->convert_unit_integer_field ||
        !w->get_unit_integer_field || !w->set_unit_integer_field ||
        !w->get_hero_int || !w->set_hero_int) {
        if (w) w->error = 251;
        return 0;
    }
    if (w->action == UNIT_STATS_SET_ARMOR && !UnitStatsFinite(w->value_bits)) {
        w->error = 252; return 0;
    }
    if (w->action == UNIT_STATS_SET_DEFENSE_TYPE && w->value_bits > 7u) {
        w->error = 253; return 0;
    }
    defense_field = w->convert_unit_integer_field(UNIT_IF_DEFENSE_TYPE_RAWCODE);
    if (!defense_field) { w->error = 254; return 0; }
    count = BridgeSelect();
    if (!count || w->selection.error || !w->selection.destroyed || count != w->selection.count) {
        w->error = 255; return count;
    }
    for (i = 0; i < count; ++i) {
        SelectionRow *selected = &w->selection.rows[i];
        UnitStatsRow *row = &w->rows[i];
        uint64_t unit = selected->unit;
        int32_t before_base = 0, before_total = 0;
        row->unit = unit;
        if (w->target_unit && unit != w->target_unit) {
            row->status = 2; ++w->completed; continue;
        }
        ++matched;
        if (w->selection.unit_type_id(unit) != selected->rawcode) {
            w->error = 256; return count;
        }
        row->armor_before_bits = w->get_armor(unit);
        row->defense_before = (uint32_t)w->get_unit_integer_field(unit, defense_field);
        if (!UnitStatsFinite(row->armor_before_bits) || row->defense_before > 7u) {
            w->error = 257; return count;
        }
        if (selected->level > 0) {
            before_base = w->get_hero_int(unit, 0);
            before_total = w->get_hero_int(unit, 1);
            if (before_base < 0 || before_total < 0) { w->error = 258; return count; }
        } else if (w->action == UNIT_STATS_SET_INTELLIGENCE) {
            w->error = 259; return count;
        }
        row->intelligence_base_before = (uint32_t)before_base;
        row->intelligence_total_before = (uint32_t)before_total;
        if (w->action == UNIT_STATS_SET_ARMOR) {
            float target = UnitStatsReal(w->value_bits);
            w->set_armor(unit, &target);
        } else if (w->action == UNIT_STATS_SET_DEFENSE_TYPE) {
            if (!w->set_unit_integer_field(unit, defense_field, (int32_t)w->value_bits)) {
                w->error = 260; return count;
            }
        } else if (w->action == UNIT_STATS_SET_INTELLIGENCE) {
            int64_t bonus = (int64_t)before_total - (int64_t)before_base;
            int64_t target_base = (int64_t)w->value_bits - bonus;
            int32_t after_total, after_base;
            if (target_base < 0 || target_base > 1000000000LL) { w->error = 261; return count; }
            w->set_hero_int(unit, (int32_t)target_base, 1);
            after_base = w->get_hero_int(unit, 0);
            after_total = w->get_hero_int(unit, 1);
            if (after_total != (int32_t)w->value_bits) {
                int64_t corrected = (int64_t)after_base + (int64_t)w->value_bits - (int64_t)after_total;
                if (corrected < 0 || corrected > 1000000000LL) {
                    w->set_hero_int(unit, before_base, 1); w->error = 262; return count;
                }
                w->set_hero_int(unit, (int32_t)corrected, 1);
            }
        }
        row->armor_after_bits = w->get_armor(unit);
        row->defense_after = (uint32_t)w->get_unit_integer_field(unit, defense_field);
        if (selected->level > 0) {
            row->intelligence_base_after = (uint32_t)w->get_hero_int(unit, 0);
            row->intelligence_total_after = (uint32_t)w->get_hero_int(unit, 1);
        }
        if (!UnitStatsFinite(row->armor_after_bits) || row->defense_after > 7u ||
            w->selection.unit_type_id(unit) != selected->rawcode) {
            if (w->action == UNIT_STATS_SET_ARMOR) {
                float restore = UnitStatsReal(row->armor_before_bits); w->set_armor(unit, &restore);
            } else if (w->action == UNIT_STATS_SET_DEFENSE_TYPE) {
                w->set_unit_integer_field(unit, defense_field, (int32_t)row->defense_before);
            } else if (w->action == UNIT_STATS_SET_INTELLIGENCE) {
                w->set_hero_int(unit, before_base, 1);
            }
            w->error = 263; return count;
        }
        if ((w->action == UNIT_STATS_SET_ARMOR && row->armor_after_bits != w->value_bits) ||
            (w->action == UNIT_STATS_SET_DEFENSE_TYPE && row->defense_after != w->value_bits) ||
            (w->action == UNIT_STATS_SET_INTELLIGENCE && row->intelligence_total_after != w->value_bits)) {
            if (w->action == UNIT_STATS_SET_ARMOR) {
                float restore = UnitStatsReal(row->armor_before_bits); w->set_armor(unit, &restore);
            } else if (w->action == UNIT_STATS_SET_DEFENSE_TYPE) {
                w->set_unit_integer_field(unit, defense_field, (int32_t)row->defense_before);
            } else {
                w->set_hero_int(unit, before_base, 1);
            }
            w->error = 264; return count;
        }
        if (w->action != UNIT_STATS_QUERY &&
            (row->armor_before_bits != row->armor_after_bits ||
             row->defense_before != row->defense_after ||
             row->intelligence_total_before != row->intelligence_total_after)) ++w->changed;
        row->status = 1; ++w->completed;
    }
    if ((w->target_unit && matched != 1u) || (!w->target_unit && matched != count)) w->error = 265;
    return count;
}
