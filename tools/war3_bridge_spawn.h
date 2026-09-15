/* Current-build 24268 batch for one local-player unit creation. */
typedef struct SpawnWork {
    uint64_t (*get_local_player)(void);
    uint64_t (*create_unit)(uint64_t, uint32_t, float, float, float);
    uint32_t (*type_id)(uint64_t);
    void (*remove_unit)(uint64_t);
    void *expected_tls;
    uint32_t rawcode, x_bits, y_bits, facing_bits;
    uint32_t changed, error, completed, actual_rawcode;
    uint64_t created;
    uint32_t reserved;
    uint8_t padding[44];
} SpawnWork;
_Static_assert(sizeof(SpawnWork) == 128, "SpawnWork ABI");
__declspec(dllexport) const uint32_t spawn_batch_abi[3] = {0x24268018u, 216u, 128u};

static float spawn_real(uint32_t bits) {
    union { uint32_t bits; float value; } value;
    value.bits = bits;
    return value.value;
}

static int spawn_finite(uint32_t bits) {
    return (bits & 0x7f800000u) != 0x7f800000u;
}

__declspec(dllexport) uint64_t BridgeSpawnQuery(void) {
    SpawnWork *w = (SpawnWork *)g_dispatch->work;
    uint64_t player, unit = 0;
    if (!w || w->expected_tls != g_dispatch->tls_value || !w->rawcode ||
        !spawn_finite(w->x_bits) || !spawn_finite(w->y_bits) || !spawn_finite(w->facing_bits) ||
        !w->get_local_player || !w->create_unit || !w->type_id || !w->remove_unit) {
        if (w) w->error = 90;
        return 0;
    }
    player = w->get_local_player();
    if (!player) { w->error = 91; return 0; }
    __try {
        unit = w->create_unit(player, w->rawcode, spawn_real(w->x_bits),
                              spawn_real(w->y_bits), spawn_real(w->facing_bits));
        if (!unit || w->type_id(unit) != w->rawcode) {
            w->error = 92;
            if (unit) w->remove_unit(unit);
            return 0;
        }
        w->created = unit;
        w->actual_rawcode = w->type_id(unit);
        w->changed = 1;
        w->completed = 1;
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        if (unit) w->remove_unit(unit);
        w->error = 93;
        return 0;
    }
    return unit;
}
