/* Current-build 24268 mouse world-point query through registered natives. */
typedef struct MouseWork {
    uint64_t (*get_mouse_position)(void);
    float (*get_location_x)(uint64_t);
    float (*get_location_y)(uint64_t);
    void (*remove_location)(uint64_t);
    void *expected_tls;
    uint32_t x_bits, y_bits, changed, error, completed, reserved0, reserved1;
    uint8_t padding[60];
} MouseWork;
_Static_assert(sizeof(MouseWork) == 128, "MouseWork ABI");
__declspec(dllexport) const uint32_t mouse_batch_abi[3] = {0x24268019u, 216u, 128u};

__declspec(dllexport) uint64_t BridgeMouseQuery(void) {
    MouseWork *w = (MouseWork *)g_dispatch->work;
    float x, y;
    uint64_t location;
    if (!w) return 0;
    if (w->error) return 0;
    if (w->expected_tls != g_dispatch->tls_value || !w->get_mouse_position ||
        !w->get_location_x || !w->get_location_y || !w->remove_location) {
        w->error = 100;
        return 0;
    }
    __try {
        location = w->get_mouse_position();
        if (!location) { w->error = 102; return 0; }
        x = w->get_location_x(location);
        y = w->get_location_y(location);
        w->remove_location(location);
        if (!(x == x) || !(y == y) || x < -1000000.0f || x > 1000000.0f ||
            y < -1000000.0f || y > 1000000.0f) {
            w->error = 101;
            return 0;
        }
        w->x_bits = ((union { float value; uint32_t bits; }){x}).bits;
        w->y_bits = ((union { float value; uint32_t bits; }){y}).bits;
        w->changed = 1;
        w->completed = 1;
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        w->error = GetExceptionCode();
        return 0;
    }
    return (uint64_t)w->x_bits | ((uint64_t)w->y_bits << 32);
}
