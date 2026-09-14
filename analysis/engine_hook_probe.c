/* Transport diagnostic only: no game addresses, handlers, commands or writes. */
#include <windows.h>
#include <stdint.h>

typedef struct ProbeTelemetry {
    uint32_t magic, version, requested_pid, reserved;
    uint32_t attach_pid, attach_tid, callback_pid, callback_tid;
    volatile LONG getmessage_count, callwnd_count;
    uint32_t last_message, last_error;
} ProbeTelemetry;

__declspec(dllexport) ProbeTelemetry probe_local_state;

/* Avoid CRT initialization while testing whether callbacks arrive at all. */
static void mapping_name(wchar_t *name, DWORD pid) {
    static const wchar_t prefix[] = L"Local\\War3EngineHookProbe-";
    wchar_t digits[10];
    unsigned pos = 0, count = 0;
    while (prefix[pos]) { name[pos] = prefix[pos]; ++pos; }
    do { digits[count++] = (wchar_t)(L'0' + pid % 10); pid /= 10; } while (pid);
    while (count) name[pos++] = digits[--count];
    name[pos] = 0;
}

static void record_callback(int kind, UINT message) {
    wchar_t name[80];
    HANDLE mapping;
    ProbeTelemetry *shared;
    DWORD pid = GetCurrentProcessId();
    probe_local_state.callback_pid = pid;
    probe_local_state.callback_tid = GetCurrentThreadId();
    probe_local_state.last_message = message;
    if (kind == WH_GETMESSAGE) InterlockedIncrement(&probe_local_state.getmessage_count);
    else InterlockedIncrement(&probe_local_state.callwnd_count);
    mapping_name(name, pid);
    mapping = OpenFileMappingW(FILE_MAP_WRITE, FALSE, name);
    if (!mapping) { probe_local_state.last_error = GetLastError(); return; }
    shared = (ProbeTelemetry *)MapViewOfFile(mapping, FILE_MAP_WRITE, 0, 0, sizeof(*shared));
    if (shared) {
        if (shared->magic == 0x24268002 && shared->version == 1 && shared->requested_pid == pid) {
            shared->attach_pid = probe_local_state.attach_pid;
            shared->attach_tid = probe_local_state.attach_tid;
            shared->callback_pid = pid;
            shared->callback_tid = GetCurrentThreadId();
            shared->last_message = message;
            if (kind == WH_GETMESSAGE) InterlockedIncrement(&shared->getmessage_count);
            else InterlockedIncrement(&shared->callwnd_count);
        }
        UnmapViewOfFile(shared);
    } else probe_local_state.last_error = GetLastError();
    CloseHandle(mapping);
}

__declspec(dllexport) LRESULT CALLBACK ProbeGetMessage(int code, WPARAM w, LPARAM l) {
    if (code >= 0 && l) record_callback(WH_GETMESSAGE, ((MSG *)l)->message);
    return CallNextHookEx(NULL, code, w, l);
}

__declspec(dllexport) LRESULT CALLBACK ProbeCallWndProc(int code, WPARAM w, LPARAM l) {
    if (code >= 0 && l) record_callback(WH_CALLWNDPROC, ((CWPSTRUCT *)l)->message);
    return CallNextHookEx(NULL, code, w, l);
}

BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        probe_local_state.attach_pid = GetCurrentProcessId();
        probe_local_state.attach_tid = GetCurrentThreadId();
        DisableThreadLibraryCalls(module);
    }
    return TRUE;
}

/* Same marker stages as verify-loader-thread.py, but residing in a PE image.
   This export is self-contained: imports/TLS/DllMain are not needed to run it.
   All loader calls are explicitly passed by the diagnostic controller. */
typedef struct ProbeLoadCommand {
    const wchar_t *path;
    HMODULE (WINAPI *load_library)(LPCWSTR);
    DWORD (WINAPI *get_last_error)(void);
    volatile DWORD stage;
    DWORD reserved;
    HMODULE module;
    DWORD last_error;
    DWORD reserved2;
} ProbeLoadCommand;

__declspec(dllexport) DWORD WINAPI ProbeLoaderEntry(ProbeLoadCommand *cmd) {
    cmd->stage = 1;
    cmd->module = cmd->load_library(cmd->path);
    cmd->last_error = cmd->get_last_error();
    cmd->stage = 2;
    return 0;
}

/* Install from inside the target process: no remote DLL-loading hook path. */
typedef struct ProbeHookCommand {
    HWND window;
    HHOOK (WINAPI *set_hook)(int, HOOKPROC, HINSTANCE, DWORD);
    BOOL (WINAPI *unhook)(HHOOK);
    LRESULT (WINAPI *next_hook)(HHOOK, int, WPARAM, LPARAM);
    DWORD (WINAPI *current_tid)(void);
    DWORD (WINAPI *get_error)(void);
    HHOOK hook;
    DWORD target_tid, message;
    uintptr_t nonce;
    volatile LONG stage;
    DWORD last_error, callback_tid;
    volatile LONG callback_count, detached, active;
    void (WINAPI *sleep_ms)(DWORD);
    volatile LONG stop_requested;
    DWORD reserved;
    LPVOID (WINAPI *get_tls)(DWORD);
    BOOLEAN (WINAPI *add_table)(PRUNTIME_FUNCTION,DWORD,DWORD64);
    BOOLEAN (WINAPI *delete_table)(PRUNTIME_FUNCTION);
    PRUNTIME_FUNCTION unwind_table;
    DWORD64 image_base;
    uint64_t (*query)(void);
    uint64_t query_result;
    LPVOID tls_value;
    void *specific_handler;
    DWORD unwind_count, tls_index, query_stage, exception_code, unwind_registered, unwind_removed;
} ProbeHookCommand;
_Static_assert(sizeof(ProbeHookCommand) == 208, "ProbeHookCommand ABI");
static ProbeHookCommand *g_dispatch;
typedef EXCEPTION_DISPOSITION (*ProbeHandler)(PEXCEPTION_RECORD,void *,PCONTEXT,PDISPATCHER_CONTEXT);
EXCEPTION_DISPOSITION ProbeSpecificHandler(PEXCEPTION_RECORD e,void *f,PCONTEXT c,PDISPATCHER_CONTEXT d) {
    return ((ProbeHandler)g_dispatch->specific_handler)(e,f,c,d);
}
__declspec(dllexport) uint64_t ProbeConstantQuery(void) { return 0x24268001; }
__declspec(dllexport) uint64_t ProbeFaultQuery(void) { return *(volatile uint64_t *)g_dispatch->nonce; }


static LRESULT CALLBACK ProbeLocalCallback(int code, WPARAM w, LPARAM l) {
    ProbeHookCommand *cmd = g_dispatch;
    LRESULT result;
    if (!cmd) return 0;
    InterlockedIncrement(&cmd->active);
    if (code >= 0 && l) {
        const CWPSTRUCT *message = (const CWPSTRUCT *)l;
        if (message->hwnd == cmd->window && message->message == cmd->message &&
            message->wParam == cmd->nonce) {
            cmd->callback_tid = cmd->current_tid();
            InterlockedIncrement(&cmd->callback_count);
            __try {
                cmd->tls_value = cmd->get_tls(cmd->tls_index);
                if (cmd->query) {
                    cmd->query_stage = 1;
                    cmd->query_result = cmd->query();
                    cmd->query_stage = 2;
                }
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                cmd->exception_code = GetExceptionCode();
                cmd->query_stage = 3;
            }
            cmd->detached = cmd->unhook(cmd->hook);
            if (!cmd->detached) cmd->last_error = cmd->get_error();
            cmd->stage = 3;
        }
    }
    result = cmd->next_hook(NULL, code, w, l);
    InterlockedDecrement(&cmd->active);
    return result;
}

__declspec(dllexport) DWORD WINAPI ProbeInstallLocalHook(ProbeHookCommand *cmd) {
    cmd->stage = 1;
    g_dispatch = cmd;
    cmd->unwind_registered = cmd->add_table(cmd->unwind_table, cmd->unwind_count, cmd->image_base);
    if (!cmd->unwind_registered) { cmd->last_error = cmd->get_error(); cmd->stage = 2; return 0; }
    cmd->hook = cmd->set_hook(WH_CALLWNDPROC, ProbeLocalCallback, NULL, cmd->target_tid);
    if (!cmd->hook) cmd->last_error = cmd->get_error();
    cmd->stage = 2;
    /* Hooks belong to the installing thread; keep it alive through dispatch. */
    if (cmd->hook) {
        while (!cmd->stop_requested) cmd->sleep_ms(1);
        if (!cmd->detached) {
            cmd->detached = cmd->unhook(cmd->hook);
            if (!cmd->detached) cmd->last_error = cmd->get_error();
        }
    }
    if ((!cmd->hook || cmd->detached) && !cmd->active)
        cmd->unwind_removed = cmd->delete_table(cmd->unwind_table);
    return 0;
}

__declspec(dllexport) DWORD WINAPI ProbeUninstallLocalHook(ProbeHookCommand *cmd) {
    if (cmd->hook && !cmd->detached) {
        cmd->detached = cmd->unhook(cmd->hook);
        if (!cmd->detached) cmd->last_error = cmd->get_error();
    }
    return 0;
}
