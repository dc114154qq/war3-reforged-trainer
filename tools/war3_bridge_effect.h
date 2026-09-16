/* Current-build 24268 direct ability effect callbacks. */
#define EFFECT_TARGET 1u
#define EFFECT_IMMEDIATE 2u
#define EFFECT_POINT 3u
#define EFFECT_NOARG 4u
#define EFFECT_AREA_FIELD 0x61617265u

typedef uint64_t (*EffectAbilityLookupFn)(uint64_t,uint32_t);
typedef uint64_t (*EffectResolveFn)(uint32_t,uint32_t);
typedef uint64_t (*EffectUnitResolveFn)(uint64_t);
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
    EffectResolveFn resolve_agent;
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
_Static_assert(sizeof(EffectWork) == 1168, "EffectWork ABI");
__declspec(dllexport) const uint32_t effect_batch_abi[3] = {0x24268027u,216u,1168u};

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
static uint64_t BridgeEffectResolveObjectTable(uint64_t module_base, uint64_t full_handle) {
    const uint64_t root_rva = 0x2f807f0ull;
    uint64_t root, table, owner, slot;
    uint32_t low, index, offset, count, marker;
    __try {
        if (!module_base || !full_handle) return 0;
        root = *(uint64_t *)(uintptr_t)(module_base + root_rva);
        if (!root) return 0;
        low = (uint32_t)full_handle;
        index = low & 0x7fffffffu;
        offset = (low & 0x80000000u) ? 0x50u : 0x18u;
        table = *(uint64_t *)(uintptr_t)(root + offset);
        count = *(uint32_t *)(uintptr_t)(root + offset + 0x18);
        if (!table || count > 0x10000000u || index >= count) return 0;
        slot = table + (uint64_t)index * 16u;
        marker = *(uint32_t *)(uintptr_t)slot;
        owner = *(uint64_t *)(uintptr_t)(slot + 8);
        if (marker != 0xfffffffeu || !owner ||
            *(uint64_t *)(uintptr_t)(owner + 0x20) != full_handle) return 0;
        if (*(uint64_t *)(uintptr_t)(root + offset) != table ||
            *(uint32_t *)(uintptr_t)(root + offset + 0x18) != count) return 0;
        return owner;
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        return 0;
    }
}

static uint64_t BridgeEffectFindAbilityDataFromOwner(uint64_t owner,
                                                     uint64_t expected_unit_object,
                                                     uint32_t rawcode,
                                                     uint32_t *diagnostic) {
    uint64_t unit_object, node, previous;
    uint32_t stage = 0;
    if (diagnostic) *diagnostic = 0;
    __try {
        stage = 1;
        if (!owner) { if (diagnostic) *diagnostic = 0xe0000101u; return 0; }
        stage = 2;
        unit_object = *(uint64_t *)(uintptr_t)(owner + 0x90);
        if (!unit_object) { if (diagnostic) *diagnostic = 0xe0000103u; return 0; }
        if (expected_unit_object && unit_object != expected_unit_object) {
            if (diagnostic) *diagnostic = 0xe0000104u;
            return 0;
        }
        stage = 3;
        node = *(uint64_t *)(uintptr_t)(owner + 0xd8);
        previous = owner + 0xd0;
        for (uint32_t index = 0; node && index < 4096u; ++index) {
            uint64_t wrapper, prior, following, backlink, data;
            stage = 4;
            if (node < 0x38) {
                if (diagnostic) *diagnostic = 0xe0000106u;
                return 0;
            }
            wrapper = node - 0x38;
            stage = 5;
            stage = 6;
            prior = *(uint64_t *)(uintptr_t)(wrapper + 0x38);
            following = *(uint64_t *)(uintptr_t)(wrapper + 0x40);
            backlink = *(uint64_t *)(uintptr_t)(wrapper + 0x50);
            data = *(uint64_t *)(uintptr_t)(wrapper + 0x90);
            stage = 7;
            if (prior != previous || backlink != owner) {
                if (diagnostic) *diagnostic = 0xe0000108u;
                return 0;
            }
            if (!data) { if (diagnostic) *diagnostic = 0xe0000109u; return 0; }
            if (*(uint64_t *)(uintptr_t)(data + 0x68) == unit_object &&
                *(uint32_t *)(uintptr_t)(data + 0x70) == rawcode &&
                *(uint32_t *)(uintptr_t)(data + 0x78) == rawcode) return data;
            previous = node;
            node = following;
        }
        if (diagnostic) *diagnostic = 0xe0000110u;
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        if (diagnostic) *diagnostic = 0xe0000000u | stage;
    }
    if (diagnostic && !*diagnostic) *diagnostic = 0xe0000010u;
    return 0;
}

static uint64_t BridgeEffectFindAbilityDataByFullHandle(EffectResolveFn resolve_agent,
                                                        uint64_t full_handle, uint32_t rawcode,
                                                        uint32_t *diagnostic) {
    uint64_t owner = 0;
    if (diagnostic) *diagnostic = 0;
    __try {
        if (!full_handle) return 0;
        owner = BridgeEffectResolveObjectTable((uint64_t)(uintptr_t)resolve_agent, full_handle);
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        if (diagnostic) *diagnostic = 0xe0000020u | (GetExceptionCode() & 0xffffu);
        return 0;
    }
    if (!owner) {
        if (diagnostic) *diagnostic = 0xe0000201u;
        return 0;
    }
    return BridgeEffectFindAbilityDataFromOwner(owner, 0, rawcode, diagnostic);
}

__declspec(dllexport) uint64_t BridgeEffectQuery(void) {
    EffectWork *w = (EffectWork *)g_dispatch->work;
    uint32_t i, count;
    uint64_t mapped_units[24] = {0};
    uint32_t mapped_rawcodes[24] = {0};
    uint8_t mapped_used[24] = {0};
    union { uint32_t bits; float value; } x, y;
    if (!w || w->expected_tls != g_dispatch->tls_value || !w->rawcode || w->action < EFFECT_TARGET ||
        w->action > EFFECT_NOARG || !w->get_ability || !w->resolve_agent || !w->get_ability_id || !w->add_ability ||
        !w->remove_ability || !w->get_area || !w->set_area ||
        (w->action == EFFECT_POINT && (!w->get_x || !w->get_y)) ||
        (w->action != EFFECT_POINT && w->y_bits > 255u)) {
        if (w) w->error = 150;
        return 0;
    }
    x.bits = w->x_bits; y.bits = w->y_bits;
    if (w->action == EFFECT_POINT && ((x.bits & 0x7f800000u) == 0x7f800000u ||
        (y.bits & 0x7f800000u) == 0x7f800000u)) { w->error = 151; return 0; }
    for (i = 0; i < 24; ++i) {
        mapped_units[i] = w->rows[i].unit;
        mapped_rawcodes[i] = w->rows[i].status;
    }
    count = (uint32_t)BridgeSelect();
    if (!count || w->selection.error || !w->selection.destroyed || count != w->selection.count) {
        w->error = 152; return count;
    }
    for (i = 0; i < count; ++i) {
        SelectionRow *selected = &w->selection.rows[i];
        EffectRow *row = &w->rows[i];
        uint64_t ability_handle = 0, ability = 0, vtable = 0, callback = 0, target_object = 0;
        uint8_t temporary = 0;
        uint8_t area_touched = 0;
        uint32_t original_area = 0;
        uint32_t requested_area = w->action == EFFECT_POINT ? w->reserved : w->x_bits;
        uint32_t passes = w->action == EFFECT_POINT ? 1u : (w->y_bits ? w->y_bits : 1u);
        uint32_t error = 0;
        uint32_t success = 0;
        uint32_t stage = 0;
        int map_index = -1;
        uint32_t offset = w->action == EFFECT_TARGET ? 0xa70u : w->action == EFFECT_IMMEDIATE ? 0x998u :
            w->action == EFFECT_POINT ? 0xa58u : 0xa78u;
        row->unit = selected->unit;
        __try {
            stage = 1;
            if (w->selection.unit_type_id(selected->unit) != selected->rawcode) { error = 153; }
            stage = 2;
            ability_handle = w->get_ability(selected->unit, w->rawcode);
            if (!error && !ability_handle) {
                stage = 3;
                if (!w->add_ability(selected->unit, w->rawcode)) { w->error = 154; return count; }
                temporary = 1;
                stage = 4;
                ability_handle = w->get_ability(selected->unit, w->rawcode);
            }
            stage = 5;
            if (!error && (!ability_handle || w->get_ability_id(ability_handle) != w->rawcode)) {
                error = 155;
            }
            if (!error) {
                stage = 6;
                for (uint32_t map = 0; map < count; ++map) {
                    if (!mapped_used[map] && mapped_units[map] &&
                        mapped_rawcodes[map] == selected->rawcode) {
                        map_index = (int)map;
                        break;
                    }
                }
                if (map_index < 0) { error = 153; }
                else {
                    stage = 7;
                    mapped_used[map_index] = 1;
                    if (!mapped_units[map_index])
                        error = 167;
                }
                {
                    uint32_t find_diagnostic = 0;
                    stage = 8;
                    ability = !error ? BridgeEffectFindAbilityDataByFullHandle(w->resolve_agent,
                        mapped_units[map_index], w->rawcode, &find_diagnostic) : 0;
                    if (!error && !ability) error = find_diagnostic ? find_diagnostic : 165;
                }
            }
            if (!error) {
                stage = 9;
                if (!ability) error = 163;
                else target_object = *(uint64_t *)(uintptr_t)(ability + 0x68);
                stage = 10;
                if (!error && !target_object) error = 164;
            }
            if (!error) {
                stage = 11;
                vtable = *(uint64_t *)(uintptr_t)ability;
                if (!vtable) error = 156;
                stage = 12;
                if (!error) callback = *(uint64_t *)(uintptr_t)(vtable + offset);
                stage = 13;
                if (!error && !callback) error = 157;
            }
            if (!error && w->action != EFFECT_POINT && requested_area) {
                stage = 15;
                union { uint32_t bits; float value; } area;
                original_area = (uint32_t)w->get_area(ability_handle, EFFECT_AREA_FIELD, 0);
                stage = 16;
                area.bits = requested_area;
                if ((area.bits & 0x7f800000u) == 0x7f800000u || area.value < 0.0f || area.value > 1000000.0f ||
                    !w->set_area(ability_handle, EFFECT_AREA_FIELD, 0, &area.value) ||
                    (uint32_t)w->get_area(ability_handle, EFFECT_AREA_FIELD, 0) != requested_area) {
                    error = 160;
                }
                area_touched = 1;
            }
            if (!error) {
                stage = 17;
                for (uint32_t pass = 0; pass < passes; ++pass) {
                    __try {
                        if (w->action == EFFECT_TARGET) ((EffectTargetFn)(uintptr_t)callback)(ability, target_object);
                        else if (w->action == EFFECT_POINT) ((EffectPointFn)(uintptr_t)callback)(ability, &x.value, &y.value);
                        else ((EffectImmediateFn)(uintptr_t)callback)(ability);
                    } __except(EXCEPTION_EXECUTE_HANDLER) {
                        error = 0xe1000000u | (GetExceptionCode() & 0xffffu);
                        break;
                    }
                }
                if (!error) {
                    stage = 18;
                    ability_handle = w->get_ability(selected->unit, w->rawcode);
                    stage = 19;
                    if (!ability_handle || w->get_ability_id(ability_handle) != w->rawcode ||
                        !BridgeEffectFindAbilityDataByFullHandle(w->resolve_agent, mapped_units[map_index], w->rawcode, 0)) error = 158;
                    else success = 1;
                }
            }
        } __except(EXCEPTION_EXECUTE_HANDLER) {
            error = 0xe2000000u | ((stage & 0xffu) << 16) | (GetExceptionCode() & 0xffffu);
        }
        if (area_touched && ability_handle) {
            __try {
                uint32_t current = (uint32_t)w->get_area(ability_handle, EFFECT_AREA_FIELD, 0);
                if (current == requested_area) {
                    union { uint32_t bits; float value; } original;
                    original.bits = original_area;
                    if (!w->set_area(ability_handle, EFFECT_AREA_FIELD, 0, &original.value) ||
                        (uint32_t)w->get_area(ability_handle, EFFECT_AREA_FIELD, 0) != original_area) {
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
