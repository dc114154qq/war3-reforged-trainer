#include <windows.h>
#include <stdint.h>
typedef struct ProbeReadPage { DWORD error, copied; } ProbeReadPage;
typedef struct ProbeContext {
    void *load, *last_error, *path, *module;
    DWORD error, stage;
    DWORD mode, read_size;
    void *read_api;
    const uint8_t *read_address;
    uint8_t *read_output;
    ProbeReadPage *read_pages;
    DWORD read_failures, reserved;
} ProbeContext;
