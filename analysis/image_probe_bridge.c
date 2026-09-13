/* Import-free mapped-image diagnostic. All OS function pointers are supplied. */
#include <windows.h>
typedef struct ProbeContext {
    void *load, *last_error;
    const wchar_t *path;
    HMODULE module;
    DWORD error, stage;
} ProbeContext;
__declspec(dllexport) DWORD WINAPI ImageProbe(ProbeContext *context) {
    context->stage=1;
    context->module=((HMODULE (WINAPI *)(LPCWSTR))context->load)(context->path);
    context->error=((DWORD (WINAPI *)(void))context->last_error)();
    context->stage=2;
    return 0;
}
