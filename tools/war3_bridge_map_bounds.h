/* Current-build 24268 map world-bounds query. */
typedef uint64_t (*BoundsWorldFn)(void);
typedef uint32_t (*BoundsRectFn)(uint64_t);

typedef struct MapBoundsWork {
    BoundsWorldFn get_world_bounds;
    BoundsRectFn get_min_x;
    BoundsRectFn get_max_x;
    BoundsRectFn get_min_y;
    BoundsRectFn get_max_y;
    void *expected_tls;
    uint32_t min_x_bits, max_x_bits, min_y_bits, max_y_bits;
    uint32_t changed, error, completed, reserved;
} MapBoundsWork;
_Static_assert(sizeof(MapBoundsWork) == 80, "MapBoundsWork ABI");
__declspec(dllexport) const uint32_t map_bounds_batch_abi[3] = {0x2426802Cu, 216u, 128u};

static int BoundsRealIsFinite(uint32_t bits) {
    return (bits & 0x7f800000u) != 0x7f800000u;
}

__declspec(dllexport) uint64_t BridgeMapBoundsQuery(void) {
    MapBoundsWork *w = (MapBoundsWork *)g_dispatch->work;
    uint64_t rect;
    if (!w || w->expected_tls != g_dispatch->tls_value || !w->get_world_bounds ||
        !w->get_min_x || !w->get_max_x || !w->get_min_y || !w->get_max_y) {
        if (w) w->error = 100;
        return 0;
    }
    __try {
        rect = w->get_world_bounds();
        if (!rect) { w->error = 101; return 0; }
        w->min_x_bits = w->get_min_x(rect);
        w->max_x_bits = w->get_max_x(rect);
        w->min_y_bits = w->get_min_y(rect);
        w->max_y_bits = w->get_max_y(rect);
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        w->error = GetExceptionCode();
        return 0;
    }
    if (!BoundsRealIsFinite(w->min_x_bits) || !BoundsRealIsFinite(w->max_x_bits) ||
        !BoundsRealIsFinite(w->min_y_bits) || !BoundsRealIsFinite(w->max_y_bits)) {
        w->error = 102;
        return 0;
    }
    w->changed = 1;
    w->completed = 1;
    return 1;
}
