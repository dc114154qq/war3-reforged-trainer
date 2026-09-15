/* Current-build 24268 batch for typed ability field reads and writes. */
#define ABILITY_FIELD_MAX_FIELDS 32u
#define ABILITY_FIELD_READ 0u
#define ABILITY_FIELD_WRITE 1u
#define ABILITY_FIELD_STATUS_OK 1u
#define ABILITY_FIELD_STATUS_MISSING 2u
#define ABILITY_FIELD_STATUS_SKIPPED 3u

typedef uint64_t (*AbilityLookupFn)(uint64_t, uint32_t);
typedef uint32_t (*AbilityIdFn)(uint64_t);
typedef int32_t (*AbilityLevelFn)(uint64_t, uint32_t);
typedef uint64_t (*AbilityFieldGetFn)(uint64_t, uint32_t);
typedef uint64_t (*AbilityLevelFieldGetFn)(uint64_t, uint32_t, int32_t);
typedef uint32_t (*AbilityFieldScalarSetFn)(uint64_t, uint32_t, uint32_t);
typedef uint32_t (*AbilityFieldRealSetFn)(uint64_t, uint32_t, float *);
typedef uint32_t (*AbilityLevelFieldScalarSetFn)(uint64_t, uint32_t, int32_t, uint32_t);
typedef uint32_t (*AbilityLevelFieldRealSetFn)(uint64_t, uint32_t, int32_t, float *);

typedef struct AbilityFieldSpec {
    uint32_t field_id;
    uint32_t kind;
    uint32_t scope;
    uint32_t target;
} AbilityFieldSpec;
_Static_assert(sizeof(AbilityFieldSpec) == 16, "AbilityFieldSpec ABI");

typedef struct AbilityFieldWork {
    SelectionWork selection;
    AbilityLookupFn get_ability;
    AbilityIdFn get_ability_id;
    AbilityLevelFn get_ability_level;
    AbilityFieldGetFn get_boolean_field;
    AbilityFieldGetFn get_integer_field;
    AbilityFieldGetFn get_real_field;
    AbilityLevelFieldGetFn get_boolean_level_field;
    AbilityLevelFieldGetFn get_integer_level_field;
    AbilityLevelFieldGetFn get_real_level_field;
    AbilityFieldScalarSetFn set_boolean_field;
    AbilityFieldScalarSetFn set_integer_field;
    AbilityFieldRealSetFn set_real_field;
    AbilityLevelFieldScalarSetFn set_boolean_level_field;
    AbilityLevelFieldScalarSetFn set_integer_level_field;
    AbilityLevelFieldRealSetFn set_real_level_field;
    void *expected_tls;
    uint32_t rawcode, level, action, field_count;
    uint32_t changed, error, completed, reserved;
    uint64_t target_unit;
    AbilityFieldSpec fields[ABILITY_FIELD_MAX_FIELDS];
    uint64_t ability_handles[24];
    int32_t current_levels[24];
    uint32_t statuses[24];
    uint32_t before[24 * ABILITY_FIELD_MAX_FIELDS];
    uint32_t after[24 * ABILITY_FIELD_MAX_FIELDS];
} AbilityFieldWork;
_Static_assert(sizeof(AbilityFieldWork) == 7688, "AbilityFieldWork ABI");
__declspec(dllexport) const uint32_t ability_field_batch_abi[3] = {0x24268021u, 216u, 7688u};

static uint32_t BridgeAbilityFieldRead(AbilityFieldWork *w, uint64_t ability,
                                       const AbilityFieldSpec *field) {
    uint64_t result;
    int32_t index = (int32_t)w->level - 1;
    if (field->scope == 0u) {
        if (field->kind == 0u) result = w->get_boolean_field(ability, field->field_id);
        else if (field->kind == 1u) result = w->get_integer_field(ability, field->field_id);
        else result = w->get_real_field(ability, field->field_id);
    } else {
        if (field->kind == 0u) result = w->get_boolean_level_field(ability, field->field_id, index);
        else if (field->kind == 1u) result = w->get_integer_level_field(ability, field->field_id, index);
        else result = w->get_real_level_field(ability, field->field_id, index);
    }
    return (uint32_t)result;
}

static uint32_t BridgeAbilityFieldWrite(AbilityFieldWork *w, uint64_t ability,
                                        const AbilityFieldSpec *field, uint32_t value) {
    int32_t index = (int32_t)w->level - 1;
    if (field->kind == 2u) {
        union { uint32_t bits; float value; } real_value;
        real_value.bits = value;
        if (field->scope == 0u) return w->set_real_field(ability, field->field_id, &real_value.value);
        return w->set_real_level_field(ability, field->field_id, index, &real_value.value);
    }
    if (field->scope == 0u) return field->kind == 0u
        ? w->set_boolean_field(ability, field->field_id, value & 1u)
        : w->set_integer_field(ability, field->field_id, value);
    return field->kind == 0u
        ? w->set_boolean_level_field(ability, field->field_id, index, value & 1u)
        : w->set_integer_level_field(ability, field->field_id, index, value);
}

static void BridgeAbilityFieldRollback(AbilityFieldWork *w, uint32_t count,
                                       uint8_t *written) {
    uint32_t i, j, index;
    for (i = 0; i < count; ++i) {
        if (w->statuses[i] != ABILITY_FIELD_STATUS_OK) continue;
        for (j = 0; j < w->field_count; ++j) {
            index = i * ABILITY_FIELD_MAX_FIELDS + j;
            if (!written[index]) continue;
            BridgeAbilityFieldWrite(w, w->ability_handles[i], &w->fields[j], w->before[index]);
        }
    }
}

__declspec(dllexport) uint64_t BridgeAbilityFieldQuery(void) {
    AbilityFieldWork *w = (AbilityFieldWork *)g_dispatch->work;
    uint32_t i, j, index, count, active = 0;
    uint8_t target_seen = 0;
    uint8_t written[24 * ABILITY_FIELD_MAX_FIELDS] = {0};
    if (!w || w->expected_tls != g_dispatch->tls_value || !w->rawcode ||
        !w->level || w->level > 1000u || w->action > ABILITY_FIELD_WRITE ||
        !w->field_count || w->field_count > ABILITY_FIELD_MAX_FIELDS || w->reserved ||
        !w->get_ability || !w->get_ability_id || !w->get_ability_level ||
        !w->get_boolean_field || !w->get_integer_field || !w->get_real_field ||
        !w->get_boolean_level_field || !w->get_integer_level_field || !w->get_real_level_field ||
        !w->set_boolean_field || !w->set_integer_field || !w->set_real_field ||
        !w->set_boolean_level_field || !w->set_integer_level_field || !w->set_real_level_field) {
        if (w) w->error = 90;
        return 0;
    }
    for (j = 0; j < w->field_count; ++j) {
        if (!w->fields[j].field_id || w->fields[j].kind > 2u || w->fields[j].scope > 1u) {
            w->error = 91;
            return 0;
        }
    }
    count = (uint32_t)BridgeSelect();
    if (!count || w->selection.error || !w->selection.destroyed || count != w->selection.count) {
        w->error = 92;
        return count;
    }
    for (i = 0; i < count; ++i) {
        SelectionRow *selected = &w->selection.rows[i];
        uint64_t ability;
        if (w->target_unit && selected->unit != w->target_unit) {
            w->statuses[i] = ABILITY_FIELD_STATUS_SKIPPED;
            ++w->completed;
            continue;
        }
        target_seen = 1;
        if (w->selection.unit_type_id(selected->unit) != selected->rawcode) {
            w->error = 93;
            return count;
        }
        ability = w->get_ability(selected->unit, w->rawcode);
        if (!ability || w->get_ability_id(ability) != w->rawcode) {
            w->statuses[i] = ABILITY_FIELD_STATUS_MISSING;
            if (w->action == ABILITY_FIELD_WRITE) {
                w->error = 94;
                return count;
            }
            ++w->completed;
            continue;
        }
        w->ability_handles[i] = ability;
        w->current_levels[i] = w->get_ability_level(selected->unit, w->rawcode);
        if (w->current_levels[i] < 0) {
            w->error = 95;
            return count;
        }
        w->statuses[i] = ABILITY_FIELD_STATUS_OK;
        ++active;
        for (j = 0; j < w->field_count; ++j) {
            index = i * ABILITY_FIELD_MAX_FIELDS + j;
            w->before[index] = BridgeAbilityFieldRead(w, ability, &w->fields[j]);
            w->after[index] = w->before[index];
        }
        ++w->completed;
    }
    if (w->target_unit && !target_seen) {
        w->error = 96;
        w->completed = 0;
        return count;
    }
    if (w->action == ABILITY_FIELD_READ || !active) return count;
    w->completed = 0;
    for (i = 0; i < count; ++i) {
        if (w->statuses[i] == ABILITY_FIELD_STATUS_SKIPPED) {
            ++w->completed;
            continue;
        }
        for (j = 0; j < w->field_count; ++j) {
            index = i * ABILITY_FIELD_MAX_FIELDS + j;
            if (!BridgeAbilityFieldWrite(w, w->ability_handles[i], &w->fields[j], w->fields[j].target)) {
                w->error = 97 + j;
                BridgeAbilityFieldRollback(w, count, written);
                return count;
            }
            written[index] = 1;
            w->after[index] = BridgeAbilityFieldRead(w, w->ability_handles[i], &w->fields[j]);
            if (w->after[index] != w->fields[j].target) {
                w->error = 130 + j;
                BridgeAbilityFieldRollback(w, count, written);
                return count;
            }
            if (w->before[index] != w->after[index]) ++w->changed;
        }
        ++w->completed;
    }
    return count;
}
