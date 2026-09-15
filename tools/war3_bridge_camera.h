/* Current-build 24268 camera snapshot. */
typedef struct CameraWork {
    float (*target_x)(void), (*target_y)(void), (*target_z)(void);
    float (*eye_x)(void), (*eye_y)(void), (*eye_z)(void);
    float (*get_field)(uint64_t);
    uint64_t (*convert_field)(uint32_t);
    float (*get_margin)(uint32_t);
    int32_t (*screen_x)(void), (*screen_y)(void);
    void *expected_tls;
    float target[3], eye[3], fields[8], margins[4];
    uint32_t screen[2], changed, error, completed, reserved;
    uint8_t padding[64];
} CameraWork;
_Static_assert(sizeof(CameraWork) == 256, "CameraWork ABI");
__declspec(dllexport) const uint32_t camera_batch_abi[3] = {0x2426801Bu, 216u, 256u};

__declspec(dllexport) uint64_t BridgeCameraQuery(void) {
    CameraWork *w = (CameraWork *)g_dispatch->work;
    uint32_t index;
    if (!w) return 0;
    if (w->expected_tls != g_dispatch->tls_value || !w->target_x || !w->target_y ||
        !w->target_z || !w->eye_x || !w->eye_y || !w->eye_z || !w->get_field ||
        !w->convert_field || !w->get_margin || !w->screen_x || !w->screen_y) {
        w->error = 100;
        return 0;
    }
    __try {
        w->target[0] = w->target_x(); w->target[1] = w->target_y(); w->target[2] = w->target_z();
        w->eye[0] = w->eye_x(); w->eye[1] = w->eye_y(); w->eye[2] = w->eye_z();
        for (index = 0; index < 8; ++index) {
            uint64_t field = w->convert_field(index);
            w->fields[index] = field ? w->get_field(field) : 0.0f;
        }
        for (index = 0; index < 4; ++index) w->margins[index] = w->get_margin(index);
        w->screen[0] = (uint32_t)w->screen_x();
        w->screen[1] = (uint32_t)w->screen_y();
        w->changed = 1;
        w->completed = 1;
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        w->error = GetExceptionCode();
        return 0;
    }
    return (uint64_t)w->screen[0] | ((uint64_t)w->screen[1] << 32);
}
