/* Current-build 24268 position batch using the narrow SetUnitX/SetUnitY natives. */
typedef void (*PositionSetRealFn)(uint64_t, float *);
typedef uint32_t (*PositionGetRealFn)(uint64_t);
typedef uint32_t (*PositionStopOrderFn)(uint64_t, int32_t);
typedef int32_t (*PositionCurrentOrderFn)(uint64_t);

typedef struct PositionRow {
    uint64_t unit;
    uint32_t before, after, status, reserved, actual_x_bits, actual_y_bits;
} PositionRow;
_Static_assert(sizeof(PositionRow) == 32, "PositionRow ABI");

typedef struct PositionWork {
    SelectionWork selection;
    PositionSetRealFn set_x;
    PositionSetRealFn set_y;
    PositionGetRealFn get_x;
    PositionGetRealFn get_y;
    PositionStopOrderFn stop_order;
    PositionCurrentOrderFn current_order;
    void *expected_tls;
    uint32_t x_bits, y_bits, changed, error, completed, reserved;
    PositionRow rows[24];
} PositionWork;
_Static_assert(sizeof(PositionWork) == 1328, "PositionWork ABI");

__declspec(dllexport) const uint32_t position_batch_abi[3] = {0x2426801Eu, 216u, 1328u};

static uint32_t PositionRealIsFinite(uint32_t bits) {
    return (bits & 0x7f800000u) != 0x7f800000u;
}

__declspec(dllexport) uint64_t BridgePositionQuery(void) {
    PositionWork *w = (PositionWork *)g_dispatch->work;
    uint32_t i;
    uint64_t count;
    union { uint32_t bits; float value; } x, y;
    if (!w || w->expected_tls != g_dispatch->tls_value ||
        !w->set_x || !w->set_y || !w->get_x || !w->get_y ||
        !w->stop_order || !w->current_order ||
        !PositionRealIsFinite(w->x_bits) || !PositionRealIsFinite(w->y_bits)) {
        if (w) w->error = 80;
        return 0;
    }
    count = BridgeSelect();
    if (!count || w->selection.error || !w->selection.destroyed || count != w->selection.count) {
        w->error = 81;
        return count;
    }

    /* Snapshot each real coordinate and clear active orders before changing
       positions. Preserve the selected formation instead of stacking every
       unit on the same point, which can make 3.0 pathing resolve collisions
       indefinitely after a teleport. */
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
            if (w->current_order(unit) && !w->stop_order(unit, 851972)) {
                w->error = 84;
                return count;
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            w->error = GetExceptionCode();
            return count;
        }
        if (!PositionRealIsFinite(before_x) || !PositionRealIsFinite(before_y)) {
            w->error = 83;
            return count;
        }
    }

    {
        union { uint32_t bits; float value; } anchor_x, anchor_y, before_x, before_y, target_x, target_y;
        anchor_x.bits = w->rows[0].before;
        anchor_y.bits = w->rows[0].after;
        target_x.bits = w->x_bits;
        target_y.bits = w->y_bits;
    for (i = 0; i < count; ++i) {
        PositionRow *row = &w->rows[i];
        uint64_t unit = w->selection.rows[i].unit;
        before_x.bits = row->before;
        before_y.bits = row->after;
        x.value = target_x.value + before_x.value - anchor_x.value;
        y.value = target_y.value + before_y.value - anchor_y.value;
        if (!PositionRealIsFinite(x.bits) || !PositionRealIsFinite(y.bits)) {
            w->error = 85;
            return count;
        }
        __try {
            w->set_x(unit, &x.value);
            w->set_y(unit, &y.value);
            row->actual_x_bits = w->get_x(unit);
            row->actual_y_bits = w->get_y(unit);
            if (w->current_order(unit)) w->stop_order(unit, 851972);
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
    }
    return count;
}
