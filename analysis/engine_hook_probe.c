/* Transport diagnostic only: no game addresses, handlers, commands or writes. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>

typedef struct ProbeTelemetry {
    uint32_t magic, version, requested_pid, reserved;
    uint32_t attach_pid, attach_tid, callback_pid, callback_tid;
    volatile LONG getmessage_count, callwnd_count;
    uint32_t last_message, last_error;
} ProbeTelemetry;

__declspec(dllexport) ProbeTelemetry probe_local_state;

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
    swprintf_s(name, 80, L"Local\\War3EngineHookProbe-%lu", pid);
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
