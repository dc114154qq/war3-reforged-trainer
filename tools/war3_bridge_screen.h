/* Current-build 24268 screen mouse coordinate probe. */
typedef struct ScreenMouseWork {
    int32_t (*get_x)(void);
    int32_t (*get_y)(void);
    void *expected_tls;
    int32_t x, y, changed, error, completed, reserved0, reserved1;
    uint8_t padding[76];
} ScreenMouseWork;
_Static_assert(sizeof(ScreenMouseWork) == 128, "ScreenMouseWork ABI");
__declspec(dllexport) const uint32_t screen_mouse_batch_abi[3] = {0x2426801Au, 216u, 128u};

__declspec(dllexport) uint64_t BridgeScreenMouseQuery(void) {
    ScreenMouseWork *w = (ScreenMouseWork *)g_dispatch->work;
    if (!w) return 0;
    if (w->error) return 0;
    if (w->expected_tls != g_dispatch->tls_value || !w->get_x || !w->get_y) {
        w->error = 100;
        return 0;
    }
    __try {
        w->x = w->get_x();
        w->y = w->get_y();
        w->changed = 1;
        w->completed = 1;
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        w->error = GetExceptionCode();
        return 0;
    }
    return (uint64_t)(uint32_t)w->x | ((uint64_t)(uint32_t)w->y << 32);
}
