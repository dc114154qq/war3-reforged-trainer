/* Current-build 24268 direct ability effect callbacks. */
#define EFFECT_TARGET 1u
#define EFFECT_IMMEDIATE 2u
#define EFFECT_POINT 3u
#define EFFECT_NOARG 4u
#define EFFECT_AREA_FIELD 0x61617265u

typedef uint64_t (*EffectAbilityLookupFn)(uint64_t,uint32_t);
typedef uint32_t (*EffectAbilityIdFn)(uint64_t);
typedef uint8_t (*EffectUnitAddFn)(uint64_t,uint32_t);
typedef uint8_t (*EffectUnitRemoveFn)(uint64_t,uint32_t);
typedef uint64_t (*EffectRealQueryFn)(uint64_t);
typedef void (*EffectTargetFn)(uint64_t,uint64_t);
typedef void (*EffectImmediateFn)(uint64_t);
typedef void (*EffectPointFn)(uint64_t,float *,float *);
typedef uint64_t (*EffectAreaGetFn)(uint64_t,uint32_t,int32_t);
typedef uint32_t (*EffectAreaSetFn)(uint64_t,uint32_t,int32_t,float *);

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
    EffectAreaGetFn get_area;
    EffectAreaSetFn set_area;
    void *expected_tls;
    uint32_t rawcode, action, x_bits, y_bits;
    uint32_t changed, error, completed, reserved;
    EffectRow rows[24];
} EffectWork;
_Static_assert(sizeof(EffectWork) == 1160, "EffectWork ABI");
__declspec(dllexport) const uint32_t effect_batch_abi[3] = {0x24268025u,216u,1160u};

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
        !w->remove_ability || !w->get_area || !w->set_area ||
        (w->action == EFFECT_POINT && (!w->get_x || !w->get_y)) ||
        (w->action != EFFECT_POINT && w->y_bits > 255u)) {
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
        uint64_t ability = 0, vtable = 0, callback = 0, target_object = 0;
        uint8_t temporary = 0;
        uint8_t area_touched = 0;
        uint32_t original_area = 0;
        uint32_t requested_area = w->action == EFFECT_POINT ? w->reserved : w->x_bits;
        uint32_t passes = w->action == EFFECT_POINT ? 1u : (w->y_bits ? w->y_bits : 1u);
        uint32_t error = 0;
        uint32_t success = 0;
        uint32_t offset = w->action == EFFECT_TARGET ? 0xa70u : w->action == EFFECT_IMMEDIATE ? 0x998u :
            w->action == EFFECT_POINT ? 0xa58u : 0xa78u;
        row->unit = selected->unit;
        __try {
            if (w->selection.unit_type_id(selected->unit) != selected->rawcode) { error = 153; }
            ability = w->get_ability(selected->unit, w->rawcode);
            if (!error && !ability) {
                if (!w->add_ability(selected->unit, w->rawcode)) { w->error = 154; return count; }
                temporary = 1;
                ability = w->get_ability(selected->unit, w->rawcode);
            }
            if (!error && (!ability || w->get_ability_id(ability) != w->rawcode || !BridgeEffectReadable(ability, 0x8))) {
                error = 155;
            }
            if (!error) {
                if (!BridgeEffectReadable(ability, 0x70)) error = 163;
                else target_object = *(uint64_t *)(uintptr_t)(ability + 0x68);
                if (!error && !BridgeEffectReadable(target_object, 0x20)) error = 164;
            }
            if (!error) {
                vtable = *(uint64_t *)(uintptr_t)ability;
                if (!BridgeEffectReadable(vtable, offset + 8)) error = 156;
                if (!error) {
                    callback = *(uint64_t *)(uintptr_t)(vtable + offset);
                    if (!BridgeEffectExecutable(callback)) error = 157;
                }
            }
            if (!error && w->action != EFFECT_POINT && requested_area) {
                union { uint32_t bits; float value; } area;
                original_area = (uint32_t)w->get_area(ability, EFFECT_AREA_FIELD, 0);
                area.bits = requested_area;
                if ((area.bits & 0x7f800000u) == 0x7f800000u || area.value < 0.0f || area.value > 1000000.0f ||
                    !w->set_area(ability, EFFECT_AREA_FIELD, 0, &area.value) ||
                    (uint32_t)w->get_area(ability, EFFECT_AREA_FIELD, 0) != requested_area) {
                    error = 160;
                }
                area_touched = 1;
            }
            if (!error) {
                for (uint32_t pass = 0; pass < passes; ++pass) {
                    if (w->action == EFFECT_TARGET) ((EffectTargetFn)(uintptr_t)callback)(ability, target_object);
                    else if (w->action == EFFECT_POINT) ((EffectPointFn)(uintptr_t)callback)(ability, &x.value, &y.value);
                    else ((EffectImmediateFn)(uintptr_t)callback)(ability);
                }
                ability = w->get_ability(selected->unit, w->rawcode);
                if (!ability || w->get_ability_id(ability) != w->rawcode) error = 158;
                else success = 1;
            }
        } __except(EXCEPTION_EXECUTE_HANDLER) {
            error = GetExceptionCode();
        }
        if (area_touched && ability) {
            __try {
                uint32_t current = (uint32_t)w->get_area(ability, EFFECT_AREA_FIELD, 0);
                if (current == requested_area) {
                    union { uint32_t bits; float value; } original;
                    original.bits = original_area;
                    if (!w->set_area(ability, EFFECT_AREA_FIELD, 0, &original.value) ||
                        (uint32_t)w->get_area(ability, EFFECT_AREA_FIELD, 0) != original_area) {
                        if (!error) error = 161;
                    }
                } else if (current != original_area && !error) {
                    error = 162;
                }
            } __except(EXCEPTION_EXECUTE_HANDLER) {
                if (!error) error = GetExceptionCode();
            }
        }
        if (temporary) {
            __try {
                if (!w->remove_ability(selected->unit, w->rawcode) || w->get_ability(selected->unit, w->rawcode)) {
                    if (!error) error = 159;
                }
            } __except(EXCEPTION_EXECUTE_HANDLER) {
                if (!error) error = GetExceptionCode();
            }
        }
        if (error || !success) {
            w->error = error ? error : ERROR_INVALID_DATA;
            return count;
        }
        row->temporary = temporary;
        row->status = 1;
        ++w->changed;
        ++w->completed;
    }
    return count;
}
