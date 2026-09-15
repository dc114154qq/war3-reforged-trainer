/* Current-build 24268 direct ability effect callbacks. */
#define EFFECT_TARGET 1u
#define EFFECT_IMMEDIATE 2u
#define EFFECT_POINT 3u
#define EFFECT_NOARG 4u

typedef uint64_t (*EffectAbilityLookupFn)(uint64_t,uint32_t);
typedef uint32_t (*EffectAbilityIdFn)(uint64_t);
typedef uint8_t (*EffectUnitAddFn)(uint64_t,uint32_t);
typedef uint8_t (*EffectUnitRemoveFn)(uint64_t,uint32_t);
typedef uint64_t (*EffectRealQueryFn)(uint64_t);
typedef void (*EffectTargetFn)(uint64_t,uint64_t);
typedef void (*EffectImmediateFn)(uint64_t);
typedef void (*EffectPointFn)(uint64_t,float *,float *);

typedef struct EffectRow {
    uint64_t unit;
    uint32_t status, temporary, reserved0, reserved1;
} EffectRow;
_Static_assert(sizeof(EffectRow) == 24, "EffectRow ABI");

typedef struct EffectWork {
    SelectionWork selection;
    EffectAbilityLookupFn get_ability;
    EffectAbilityIdFn get_ability_id;
    EffectUnitAddFn add_ability;
    EffectUnitRemoveFn remove_ability;
    EffectRealQueryFn get_x;
    EffectRealQueryFn get_y;
    void *expected_tls;
    uint32_t rawcode, action, x_bits, y_bits;
    uint32_t changed, error, completed, reserved;
    EffectRow rows[24];
} EffectWork;
_Static_assert(sizeof(EffectWork) == 1144, "EffectWork ABI");
__declspec(dllexport) const uint32_t effect_batch_abi[3] = {0x24268024u,216u,1144u};

static int BridgeEffectReadable(uint64_t address, size_t size) {
    MEMORY_BASIC_INFORMATION region;
    if (!address || VirtualQuery((void *)(uintptr_t)address, &region, sizeof(region)) != sizeof(region)) return 0;
    if (region.State != MEM_COMMIT || address < (uint64_t)(uintptr_t)region.BaseAddress ||
        address + size < address || address + size > (uint64_t)(uintptr_t)region.BaseAddress + region.RegionSize) return 0;
    return !(region.Protect & PAGE_NOACCESS) && !(region.Protect & PAGE_GUARD);
}
static int BridgeEffectExecutable(uint64_t address) {
    MEMORY_BASIC_INFORMATION region;
    if (!address || VirtualQuery((void *)(uintptr_t)address, &region, sizeof(region)) != sizeof(region)) return 0;
    return region.State == MEM_COMMIT && (region.Protect & (PAGE_EXECUTE | PAGE_EXECUTE_READ |
        PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY));
}

__declspec(dllexport) uint64_t BridgeEffectQuery(void) {
    EffectWork *w = (EffectWork *)g_dispatch->work;
    uint32_t i, count;
    union { uint32_t bits; float value; } x, y;
    if (!w || w->expected_tls != g_dispatch->tls_value || !w->rawcode || w->action < EFFECT_TARGET ||
        w->action > EFFECT_NOARG || !w->get_ability || !w->get_ability_id || !w->add_ability ||
        !w->remove_ability || (w->action == EFFECT_POINT && (!w->get_x || !w->get_y))) {
        if (w) w->error = 150;
        return 0;
    }
    x.bits = w->x_bits; y.bits = w->y_bits;
    if (w->action == EFFECT_POINT && ((x.bits & 0x7f800000u) == 0x7f800000u ||
        (y.bits & 0x7f800000u) == 0x7f800000u)) { w->error = 151; return 0; }
    count = (uint32_t)BridgeSelect();
    if (!count || w->selection.error || !w->selection.destroyed || count != w->selection.count) {
        w->error = 152; return count;
    }
    for (i = 0; i < count; ++i) {
        SelectionRow *selected = &w->selection.rows[i];
        EffectRow *row = &w->rows[i];
        uint64_t ability, vtable, callback;
        uint8_t temporary = 0;
        uint32_t offset = w->action == EFFECT_TARGET ? 0xa70u : w->action == EFFECT_IMMEDIATE ? 0x998u :
            w->action == EFFECT_POINT ? 0xa58u : 0xa78u;
        row->unit = selected->unit;
        if (w->selection.unit_type_id(selected->unit) != selected->rawcode) { w->error = 153; return count; }
        __try {
            ability = w->get_ability(selected->unit, w->rawcode);
            if (!ability) {
                if (!w->add_ability(selected->unit, w->rawcode)) { w->error = 154; return count; }
                temporary = 1;
                ability = w->get_ability(selected->unit, w->rawcode);
            }
            if (!ability || w->get_ability_id(ability) != w->rawcode || !BridgeEffectReadable(ability, 0x8)) {
                w->error = 155; return count;
            }
            vtable = *(uint64_t *)(uintptr_t)ability;
            if (!BridgeEffectReadable(vtable, offset + 8)) { w->error = 156; return count; }
            callback = *(uint64_t *)(uintptr_t)(vtable + offset);
            if (!BridgeEffectExecutable(callback)) { w->error = 157; return count; }
            if (w->action == EFFECT_TARGET) ((EffectTargetFn)(uintptr_t)callback)(ability, selected->unit);
            else if (w->action == EFFECT_POINT) ((EffectPointFn)(uintptr_t)callback)(ability, &x.value, &y.value);
            else ((EffectImmediateFn)(uintptr_t)callback)(ability);
            if (w->get_ability_id(w->get_ability(selected->unit, w->rawcode)) != w->rawcode) {
                w->error = 158; return count;
            }
            if (temporary) {
                if (!w->remove_ability(selected->unit, w->rawcode) || w->get_ability(selected->unit, w->rawcode)) {
                    w->error = 159; return count;
                }
            }
            row->temporary = temporary;
            row->status = 1;
            ++w->changed;
            ++w->completed;
        } __except(EXCEPTION_EXECUTE_HANDLER) {
            w->error = GetExceptionCode();
            return count;
        }
    }
    return count;
}
