/* Current-build 24268 batch for typed item field reads and writes. */
#define ITEM_FIELD_MAX_FIELDS 20u
#define ITEM_FIELD_READ 0u
#define ITEM_FIELD_WRITE 1u
#define ITEM_FIELD_STATUS_OK 1u
#define ITEM_FIELD_STATUS_MISSING 2u
#define ITEM_FIELD_STATUS_SKIPPED 3u

typedef uint64_t (*ItemSlotFn)(uint64_t, int32_t);
typedef uint32_t (*ItemIdFn)(uint64_t);
typedef uint64_t (*ItemFieldGetFn)(uint64_t, uint32_t);
typedef uint32_t (*ItemFieldScalarSetFn)(uint64_t, uint32_t, uint32_t);
typedef uint32_t (*ItemFieldRealSetFn)(uint64_t, uint32_t, float *);

typedef struct ItemFieldSpec {
    uint32_t field_id, kind, scope, target;
} ItemFieldSpec;
_Static_assert(sizeof(ItemFieldSpec) == 16, "ItemFieldSpec ABI");

typedef struct ItemFieldWork {
    SelectionWork selection;
    ItemSlotFn item_in_slot;
    ItemIdFn item_type;
    ItemFieldGetFn get_boolean_field;
    ItemFieldGetFn get_integer_field;
    ItemFieldGetFn get_real_field;
    ItemFieldScalarSetFn set_boolean_field;
    ItemFieldScalarSetFn set_integer_field;
    ItemFieldRealSetFn set_real_field;
    void *expected_tls;
    uint32_t slot, action, field_count, changed;
    uint32_t error, completed, reserved0, reserved1;
    uint64_t target_unit;
    ItemFieldSpec fields[ITEM_FIELD_MAX_FIELDS];
    uint64_t item_handles[24];
    uint32_t item_codes[24];
    uint32_t statuses[24];
    uint32_t before[24 * ITEM_FIELD_MAX_FIELDS];
    uint32_t after[24 * ITEM_FIELD_MAX_FIELDS];
} ItemFieldWork;
_Static_assert(sizeof(ItemFieldWork) == 5136, "ItemFieldWork ABI");
__declspec(dllexport) const uint32_t item_field_batch_abi[3] = {0x24268022u, 216u, 5136u};

static uint32_t BridgeItemFieldRead(ItemFieldWork *w, uint64_t item,
                                    const ItemFieldSpec *field) {
    if (field->kind == 0u) return (uint32_t)w->get_boolean_field(item, field->field_id);
    if (field->kind == 1u) return (uint32_t)w->get_integer_field(item, field->field_id);
    return (uint32_t)w->get_real_field(item, field->field_id);
}

static uint32_t BridgeItemFieldWrite(ItemFieldWork *w, uint64_t item,
                                     const ItemFieldSpec *field, uint32_t value) {
    if (field->kind == 0u) return w->set_boolean_field(item, field->field_id, value & 1u);
    if (field->kind == 1u) return w->set_integer_field(item, field->field_id, value);
    {
        union { uint32_t bits; float value; } real_value;
        real_value.bits = value;
        return w->set_real_field(item, field->field_id, &real_value.value);
    }
}

static void BridgeItemFieldRollback(ItemFieldWork *w, uint32_t count, uint8_t *written) {
    uint32_t i, j, index;
    for (i = 0; i < count; ++i) {
        if (w->statuses[i] != ITEM_FIELD_STATUS_OK) continue;
        for (j = 0; j < w->field_count; ++j) {
            index = i * ITEM_FIELD_MAX_FIELDS + j;
            if (written[index]) BridgeItemFieldWrite(w, w->item_handles[i], &w->fields[j], w->before[index]);
        }
    }
}

__declspec(dllexport) uint64_t BridgeItemFieldQuery(void) {
    ItemFieldWork *w = (ItemFieldWork *)g_dispatch->work;
    uint32_t i, j, index, count, active = 0;
    uint8_t target_seen = 0;
    uint8_t written[24 * ITEM_FIELD_MAX_FIELDS] = {0};
    if (!w || w->expected_tls != g_dispatch->tls_value || w->slot >= 6u ||
        w->action > ITEM_FIELD_WRITE || !w->field_count || w->field_count > ITEM_FIELD_MAX_FIELDS ||
        w->reserved0 || w->reserved1 || !w->item_in_slot || !w->item_type ||
        !w->get_boolean_field || !w->get_integer_field || !w->get_real_field ||
        !w->set_boolean_field || !w->set_integer_field || !w->set_real_field) {
        if (w) w->error = 100;
        return 0;
    }
    for (j = 0; j < w->field_count; ++j) {
        if (!w->fields[j].field_id || w->fields[j].kind > 2u || w->fields[j].scope) {
            w->error = 101;
            return 0;
        }
    }
    count = (uint32_t)BridgeSelect();
    if (!count || w->selection.error || !w->selection.destroyed || count != w->selection.count) {
        w->error = 102;
        return count;
    }
    for (i = 0; i < count; ++i) {
        SelectionRow *selected = &w->selection.rows[i];
        uint64_t item;
        if (w->target_unit && selected->unit != w->target_unit) {
            w->statuses[i] = ITEM_FIELD_STATUS_SKIPPED;
            ++w->completed;
            continue;
        }
        target_seen = 1;
        if (w->selection.unit_type_id(selected->unit) != selected->rawcode) {
            w->error = 103;
            return count;
        }
        item = w->item_in_slot(selected->unit, (int32_t)w->slot);
        if (!item || !w->item_type(item)) {
            w->statuses[i] = ITEM_FIELD_STATUS_MISSING;
            if (w->action == ITEM_FIELD_WRITE) { w->error = 104; return count; }
            ++w->completed;
            continue;
        }
        w->item_handles[i] = item;
        w->item_codes[i] = w->item_type(item);
        w->statuses[i] = ITEM_FIELD_STATUS_OK;
        ++active;
        for (j = 0; j < w->field_count; ++j) {
            index = i * ITEM_FIELD_MAX_FIELDS + j;
            w->before[index] = BridgeItemFieldRead(w, item, &w->fields[j]);
            w->after[index] = w->before[index];
        }
        ++w->completed;
    }
    if (w->target_unit && !target_seen) { w->error = 105; w->completed = 0; return count; }
    if (w->action == ITEM_FIELD_READ || !active) return count;
    w->completed = 0;
    for (i = 0; i < count; ++i) {
        if (w->statuses[i] == ITEM_FIELD_STATUS_SKIPPED) { ++w->completed; continue; }
        for (j = 0; j < w->field_count; ++j) {
            index = i * ITEM_FIELD_MAX_FIELDS + j;
            if (!BridgeItemFieldWrite(w, w->item_handles[i], &w->fields[j], w->fields[j].target)) {
                w->error = 106 + j;
                BridgeItemFieldRollback(w, count, written);
                return count;
            }
            written[index] = 1;
            w->after[index] = BridgeItemFieldRead(w, w->item_handles[i], &w->fields[j]);
            if (w->after[index] != w->fields[j].target) {
                w->error = 130 + j;
                BridgeItemFieldRollback(w, count, written);
                return count;
            }
            if (w->before[index] != w->after[index]) ++w->changed;
        }
        ++w->completed;
    }
    return count;
}
