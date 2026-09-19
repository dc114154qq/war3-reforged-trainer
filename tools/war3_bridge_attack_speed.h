/* Exact current-build attack-speed query/set transaction. */
typedef struct AttackSpeedWork {
    SelectionWork selection;
    uint32_t (*get_handle_id)(uint64_t);
    uint32_t (*get_cooldown)(uint64_t, int32_t);
    void (*set_cooldown)(uint64_t, float *, int32_t);
    void *(*get_factor)(void *, float *, uint32_t, int32_t);
    void *(*get_effective)(void *, float *, int32_t);
    void *expected_tls;
    uint64_t module_base, unit_object, attack, full_handle;
    uint32_t rawcode, weapon, action, target_aps_bits;
    uint32_t base_bits, factor_bits, effective_bits, true_aps_bits;
    uint32_t after_base_bits, after_effective_bits, after_true_aps_bits;
    uint32_t changed, error, completed, reserved;
    uint8_t padding[20];
} AttackSpeedWork;
_Static_assert(sizeof(AttackSpeedWork) == 640, "AttackSpeedWork ABI");
__declspec(dllexport) const uint32_t attack_speed_batch_abi[3] = {
    0x24268032u, 216u, 640u
};

static float AttackSpeedReal(uint32_t bits) {
    union { uint32_t bits; float value; } real;
    real.bits = bits;
    return real.value;
}

static uint32_t AttackSpeedBits(float value) {
    union { uint32_t bits; float value; } real;
    real.value = value;
    return real.bits;
}

static int AttackSpeedFinitePositive(float value) {
    uint32_t bits = AttackSpeedBits(value);
    return value > 0.0f && (bits & 0x7f800000u) != 0x7f800000u;
}

static uint64_t AttackSpeedResolveOwner(uint64_t module_base, uint64_t full_handle) {
    const uint64_t root_rva = 0x2f807f0ull;
    uint64_t root, table, owner, slot;
    uint32_t low, index, offset, count, marker;
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
}

__declspec(dllexport) uint64_t BridgeAttackSpeedQuery(void) {
    AttackSpeedWork *w = (AttackSpeedWork *)g_dispatch->work;
    uint64_t target_unit = 0, owner, count;
    uint32_t i;
    float base, factor = 0.0f, effective = 0.0f, true_aps;
    float after_base, after_effective = 0.0f, after_true_aps;
    if (!w || w->expected_tls != g_dispatch->tls_value || !w->module_base ||
        !w->unit_object || !w->attack || !w->full_handle || !w->rawcode ||
        w->weapon > 1 || w->action > 1 || !w->get_handle_id || !w->get_cooldown ||
        !w->set_cooldown || !w->get_factor || !w->get_effective) {
        if (w) w->error = 100;
        return 0;
    }
    __try {
        owner = AttackSpeedResolveOwner(w->module_base, w->full_handle);
        if (!owner || *(uint64_t *)(uintptr_t)(owner + 0x90) != w->unit_object ||
            *(uint64_t *)(uintptr_t)(w->unit_object + 0x18) != w->full_handle ||
            *(uint32_t *)(uintptr_t)(w->unit_object + 0x70) != w->rawcode ||
            *(uint64_t *)(uintptr_t)(w->unit_object + 0x760) != w->attack) {
            w->error = 101;
            return 0;
        }
        count = BridgeSelect();
        if (!count || w->selection.error || !w->selection.destroyed || count != w->selection.count) {
            w->error = 107;
            return 0;
        }
        for (i = 0; i < count; ++i) {
            SelectionRow *row = &w->selection.rows[i];
            if (row->rawcode == w->rawcode &&
                w->get_handle_id(row->unit) == (uint32_t)w->full_handle) {
                if (target_unit) { w->error = 108; return 0; }
                target_unit = row->unit;
            }
        }
        if (!target_unit) { w->error = 109; return 0; }
        base = AttackSpeedReal(w->get_cooldown(target_unit, (int32_t)w->weapon));
        w->get_factor((void *)(uintptr_t)w->attack, &factor, 1, (int32_t)w->weapon);
        w->get_effective((void *)(uintptr_t)w->attack, &effective, (int32_t)w->weapon);
        if (!AttackSpeedFinitePositive(base) || !AttackSpeedFinitePositive(factor) ||
            factor < 0.2f || factor > 5.0f || !AttackSpeedFinitePositive(effective)) {
            w->error = 102;
            return 0;
        }
        true_aps = 1.0f / effective;
        w->base_bits = AttackSpeedBits(base);
        w->factor_bits = AttackSpeedBits(factor);
        w->effective_bits = AttackSpeedBits(effective);
        w->true_aps_bits = AttackSpeedBits(true_aps);
        if (w->action) {
            float target_aps = AttackSpeedReal(w->target_aps_bits);
            float target_base;
            uint32_t setter_error = 0;
            if (!AttackSpeedFinitePositive(target_aps) || target_aps < 0.001f ||
                target_aps > 1000.0f) {
                w->error = 103;
                return 0;
            }
            target_base = factor / target_aps;
            if (!AttackSpeedFinitePositive(target_base) || target_base < 0.001f ||
                target_base > 1000.0f) {
                w->error = 104;
                return 0;
            }
            __try {
                w->set_cooldown(target_unit, &target_base, (int32_t)w->weapon);
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                setter_error = GetExceptionCode();
            }
            after_base = AttackSpeedReal(w->get_cooldown(target_unit, (int32_t)w->weapon));
            w->get_effective((void *)(uintptr_t)w->attack, &after_effective, (int32_t)w->weapon);
            if (!AttackSpeedFinitePositive(after_base) ||
                !AttackSpeedFinitePositive(after_effective)) {
                w->error = setter_error ? setter_error : 105;
                return 0;
            }
            after_true_aps = 1.0f / after_effective;
            if (after_true_aps < target_aps - (target_aps * 0.0001f + 0.0001f) ||
                after_true_aps > target_aps + (target_aps * 0.0001f + 0.0001f)) {
                __try {
                    w->set_cooldown(target_unit, &base, (int32_t)w->weapon);
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    w->reserved = GetExceptionCode();
                }
                w->error = setter_error ? setter_error : 106;
                return 0;
            }
        } else {
            after_base = base;
            after_effective = effective;
            after_true_aps = true_aps;
        }
        w->after_base_bits = AttackSpeedBits(after_base);
        w->after_effective_bits = AttackSpeedBits(after_effective);
        w->after_true_aps_bits = AttackSpeedBits(after_true_aps);
        if (w->action) w->changed = w->after_base_bits != w->base_bits;
        w->completed = 1;
        return target_unit;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        w->error = GetExceptionCode();
        return 0;
    }
}
