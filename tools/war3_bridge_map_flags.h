/* Current-build map visibility flags used as the fog-setter fallback. */
typedef uint64_t (*MapFlagConvertFn)(uint32_t);
typedef void (*MapFlagSetFn)(uint64_t, uint32_t);
typedef uint8_t (*MapFlagIsSetFn)(uint64_t);

typedef struct MapFlagsWork {
    MapFlagConvertFn convert_map_flag;
    MapFlagSetFn set_map_flag;
    MapFlagIsSetFn is_map_flag_set;
    void *expected_tls;
    uint32_t action, revealed, changed, error, completed, after0, after1, reserved;
    uint8_t padding[64];
} MapFlagsWork;
_Static_assert(sizeof(MapFlagsWork) == 128, "MapFlagsWork ABI");
__declspec(dllexport) const uint32_t map_flags_batch_abi[3] = {0x2426802Cu, 216u, 128u};

__declspec(dllexport) uint64_t BridgeMapFlagsQuery(void) {
    MapFlagsWork *w = (MapFlagsWork *)g_dispatch->work;
    uint64_t fog_flag, mask_flag;
    uint32_t desired;
    if (!w || w->expected_tls != g_dispatch->tls_value ||
        (w->action != 1u && w->action != 2u) || w->revealed > 1u ||
        !w->convert_map_flag || !w->set_map_flag || !w->is_map_flag_set) {
        if (w) w->error = 100;
        return 0;
    }
    __try {
        fog_flag = w->convert_map_flag(1u);
        mask_flag = w->convert_map_flag(2u);
        if (!fog_flag || !mask_flag) { w->error = 101; return 0; }
        desired = w->revealed ? 0u : 1u;
        if (w->action == 2u) {
            w->set_map_flag(fog_flag, desired);
            w->set_map_flag(mask_flag, desired);
        }
        w->after0 = w->is_map_flag_set(fog_flag) ? 1u : 0u;
        w->after1 = w->is_map_flag_set(mask_flag) ? 1u : 0u;
        if (w->action == 2u && (w->after0 != desired || w->after1 != desired)) {
            w->error = 102;
            return 0;
        }
        w->changed = w->action == 2u ? 1u : 0u;
        w->completed = 1u;
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        w->error = GetExceptionCode();
        return 0;
    }
    return (uint64_t)w->after0 | ((uint64_t)w->after1 << 32);
}
