/* Current-build 24268 position batch using SetUnitPosition. */
typedef void (*PositionSetPositionFn)(uint64_t, float *, float *);
typedef uint32_t (*PositionGetRealFn)(uint64_t);

typedef struct PositionRow {
    uint64_t unit;
    uint32_t before, after, status, reserved, actual_x_bits, actual_y_bits;
} PositionRow;
_Static_assert(sizeof(PositionRow) == 32, "PositionRow ABI");

typedef struct PositionWork {
    SelectionWork selection;
    PositionSetPositionFn set_position;
    PositionGetRealFn get_x;
    PositionGetRealFn get_y;
    uint64_t reserved_handler;
    void *expected_tls;
    uint32_t x_bits, y_bits, changed, error, completed, reserved;
    PositionRow rows[24];
} PositionWork;
_Static_assert(sizeof(PositionWork) == 1312, "PositionWork ABI");

__declspec(dllexport) const uint32_t position_batch_abi[3] = {0x24268020u, 216u, 1312u};

static uint32_t PositionRealIsFinite(uint32_t bits) {
    return (bits & 0x7f800000u) != 0x7f800000u;
}

__declspec(dllexport) uint64_t BridgePositionQuery(void) {
    PositionWork *w = (PositionWork *)g_dispatch->work;
    uint32_t i;
    uint64_t count;
    union { uint32_t bits; float value; } x, y;
    if (!w || w->expected_tls != g_dispatch->tls_value ||
        !w->set_position || !w->get_x || !w->get_y ||
        w->reserved_handler ||
        !PositionRealIsFinite(w->x_bits) || !PositionRealIsFinite(w->y_bits)) {
        if (w) w->error = 80;
        return 0;
    }
    count = BridgeSelect();
    if (!count || w->selection.error || !w->selection.destroyed || count != w->selection.count) {
        w->error = 81;
        return count;
    }

    /* Snapshot identities and native coordinates before the batch. The current
       build owns collision/path placement, so every selected unit receives the
       same requested point in this one callback; do not synthesize orders or
       force a geometric formation that the engine may rewrite synchronously. */
    for (i = 0; i < count; ++i) {
        PositionRow *row = &w->rows[i];
        uint64_t unit = w->selection.rows[i].unit;
        uint32_t before_x, before_y;
        row->unit = unit;
        if (w->selection.unit_type_id(unit) != w->selection.rows[i].rawcode) {
            w->error = 82;
            return count;
        }
        __try {
            before_x = w->get_x(unit);
            before_y = w->get_y(unit);
            row->before = before_x;
            row->after = before_y;
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            w->error = GetExceptionCode();
            return count;
        }
        if (!PositionRealIsFinite(before_x) || !PositionRealIsFinite(before_y)) {
            w->error = 83;
            return count;
        }
    }

    x.bits = w->x_bits;
    y.bits = w->y_bits;
    for (i = 0; i < count; ++i) {
        PositionRow *row = &w->rows[i];
        uint64_t unit = w->selection.rows[i].unit;
        if (!PositionRealIsFinite(x.bits) || !PositionRealIsFinite(y.bits)) {
            w->error = 85;
            return count;
        }
        __try {
            w->set_position(unit, &x.value, &y.value);
            row->actual_x_bits = w->get_x(unit);
            row->actual_y_bits = w->get_y(unit);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            w->error = GetExceptionCode();
            return count;
        }
        if (!PositionRealIsFinite(row->actual_x_bits) || !PositionRealIsFinite(row->actual_y_bits)) {
            w->error = 83;
            return count;
        }
        row->status = 1;
        ++w->changed;
        ++w->completed;
    }
    return count;
}
