/* Current-build transactional hero base-attribute update. */
typedef struct HeroAttributesWork {
    SelectionWork selection;
    int32_t (*get_strength)(uint64_t, uint32_t);
    int32_t (*get_agility)(uint64_t, uint32_t);
    int32_t (*get_intelligence)(uint64_t, uint32_t);
    void (*set_strength)(uint64_t, int32_t, uint32_t);
    void (*set_agility)(uint64_t, int32_t, uint32_t);
    void (*set_intelligence)(uint64_t, int32_t, uint32_t);
    void *expected_tls;
    uint32_t target[3], changed, error, completed, rollback_error, mode;
    int32_t before[24][3];
    int32_t after[24][3];
} HeroAttributesWork;
_Static_assert(sizeof(HeroAttributesWork) == 1144, "HeroAttributesWork ABI");
__declspec(dllexport) const uint32_t hero_attributes_batch_abi[3] = {
    0x24268030u, 216u, 1144u
};

static void BridgeHeroAttributesRestore(HeroAttributesWork *w, uint32_t last) {
    uint32_t i;
    for (i = 0; i <= last && i < w->selection.count; ++i) {
        SelectionRow *row = &w->selection.rows[i];
        if (row->level <= 0) continue;
        w->set_strength(row->unit, w->before[i][0], 1);
        w->set_agility(row->unit, w->before[i][1], 1);
        w->set_intelligence(row->unit, w->before[i][2], 1);
        if (w->get_strength(row->unit, 0) != w->before[i][0] ||
            w->get_agility(row->unit, 0) != w->before[i][1] ||
            w->get_intelligence(row->unit, 0) != w->before[i][2])
            w->rollback_error = 1;
    }
}

__declspec(dllexport) uint64_t BridgeHeroAttributesQuery(void) {
    HeroAttributesWork *w = (HeroAttributesWork *)g_dispatch->work;
    uint64_t count;
    uint32_t i, heroes = 0;
    if (!w || w->expected_tls != g_dispatch->tls_value ||
        !w->get_strength || !w->get_agility || !w->get_intelligence ||
        !w->set_strength || !w->set_agility || !w->set_intelligence ||
        w->target[0] > 1000000000u || w->target[1] > 1000000000u ||
        w->target[2] > 1000000000u || w->mode > 1u) {
        if (w) w->error = 90;
        return 0;
    }
    count = BridgeSelect();
    if (!count || w->selection.error || !w->selection.destroyed || count != w->selection.count) {
        w->error = 91;
        return count;
    }
    /* Capture every original value and validate all identities before writing. */
    for (i = 0; i < count; ++i) {
        SelectionRow *row = &w->selection.rows[i];
        if (row->level <= 0) continue;
        ++heroes;
        if (w->selection.unit_type_id(row->unit) != row->rawcode ||
            w->selection.hero_level(row->unit) != row->level) {
            w->error = 92;
            return count;
        }
        w->before[i][0] = w->get_strength(row->unit, 0);
        w->before[i][1] = w->get_agility(row->unit, 0);
        w->before[i][2] = w->get_intelligence(row->unit, 0);
    }
    if (!heroes) {
        w->error = 93;
        return count;
    }
    if (!w->mode) {
        for (i = 0; i < count; ++i) {
            if (w->selection.rows[i].level <= 0) continue;
            w->after[i][0] = w->before[i][0];
            w->after[i][1] = w->before[i][1];
            w->after[i][2] = w->before[i][2];
            ++w->completed;
        }
        return count;
    }
    for (i = 0; i < count; ++i) {
        SelectionRow *row = &w->selection.rows[i];
        if (row->level <= 0) continue;
        if (w->selection.unit_type_id(row->unit) != row->rawcode ||
            w->selection.hero_level(row->unit) != row->level) {
            w->error = 94;
            __try { BridgeHeroAttributesRestore(w, i ? i - 1 : 0); }
            __except (EXCEPTION_EXECUTE_HANDLER) { w->rollback_error = GetExceptionCode(); }
            return count;
        }
        __try {
            if (w->before[i][0] != (int32_t)w->target[0])
                w->set_strength(row->unit, (int32_t)w->target[0], 1);
            if (w->before[i][1] != (int32_t)w->target[1])
                w->set_agility(row->unit, (int32_t)w->target[1], 1);
            if (w->before[i][2] != (int32_t)w->target[2])
                w->set_intelligence(row->unit, (int32_t)w->target[2], 1);
            w->after[i][0] = w->get_strength(row->unit, 0);
            w->after[i][1] = w->get_agility(row->unit, 0);
            w->after[i][2] = w->get_intelligence(row->unit, 0);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            w->error = GetExceptionCode();
            __try { BridgeHeroAttributesRestore(w, i); }
            __except (EXCEPTION_EXECUTE_HANDLER) { w->rollback_error = GetExceptionCode(); }
            return count;
        }
        if (w->after[i][0] != (int32_t)w->target[0] ||
            w->after[i][1] != (int32_t)w->target[1] ||
            w->after[i][2] != (int32_t)w->target[2]) {
            w->error = 95;
            __try { BridgeHeroAttributesRestore(w, i); }
            __except (EXCEPTION_EXECUTE_HANDLER) { w->rollback_error = GetExceptionCode(); }
            return count;
        }
        if (w->before[i][0] != w->after[i][0] ||
            w->before[i][1] != w->after[i][1] ||
            w->before[i][2] != w->after[i][2]) ++w->changed;
        ++w->completed;
    }
    return count;
}
