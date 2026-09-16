/* Current-build 24268 terrain-height query. */
typedef uint64_t (*TerrainLocationFn)(float *, float *);
typedef uint32_t (*TerrainGetZFn)(uint64_t);
typedef void (*TerrainRemoveFn)(uint64_t);

typedef struct TerrainWork {
    TerrainLocationFn location;
    TerrainGetZFn get_z;
    TerrainRemoveFn remove_location;
    void *expected_tls;
    uint32_t x_bits, y_bits, z_bits, changed, error, completed, reserved;
    uint8_t padding[68];
} TerrainWork;
_Static_assert(sizeof(TerrainWork) == 128, "TerrainWork ABI");
__declspec(dllexport) const uint32_t terrain_batch_abi[3] = {0x2426802Au, 216u, 128u};

static uint32_t TerrainRealIsFinite(uint32_t bits) {
    return (bits & 0x7f800000u) != 0x7f800000u;
}

__declspec(dllexport) uint64_t BridgeTerrainQuery(void) {
    TerrainWork *w = (TerrainWork *)g_dispatch->work;
    union { uint32_t bits; float value; } x, y;
    uint64_t location;
    if (!w || w->expected_tls != g_dispatch->tls_value || !w->location ||
        !w->get_z || !w->remove_location || !TerrainRealIsFinite(w->x_bits) ||
        !TerrainRealIsFinite(w->y_bits)) {
        if (w) w->error = 100;
        return 0;
    }
    x.bits = w->x_bits;
    y.bits = w->y_bits;
    __try {
        location = w->location(&x.value, &y.value);
        if (!location) { w->error = 101; return 0; }
        w->z_bits = w->get_z(location);
        w->remove_location(location);
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        w->error = GetExceptionCode();
        return 0;
    }
    if (!TerrainRealIsFinite(w->z_bits)) {
        w->error = 102;
        return 0;
    }
    w->changed = 1;
    w->completed = 1;
    return (uint64_t)w->z_bits;
}
