#include <windows.h>
#include <stdio.h>

#define PROBE_MESSAGE (WM_APP + 0x451)

__declspec(dllexport) LRESULT CALLBACK ProbeHook(int code, WPARAM wparam, LPARAM lparam) {
    if (code >= 0 && lparam) {
        const CWPSTRUCT *message = (const CWPSTRUCT *)lparam;
        if (message->message == PROBE_MESSAGE) {
            wchar_t directory[MAX_PATH], path[MAX_PATH];
            char result[80];
            DWORD written;
            if (GetTempPathW(MAX_PATH, directory)
                    && swprintf(path, MAX_PATH, L"%lswar3-hook-probe-%llu.txt", directory,
                                (unsigned long long)message->wParam) > 0) {
                HANDLE file = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_NEW,
                                          FILE_ATTRIBUTE_NORMAL, NULL);
                if (file != INVALID_HANDLE_VALUE) {
                    int length = snprintf(result, sizeof(result), "pid=%lu tid=%lu\n",
                                          GetCurrentProcessId(), GetCurrentThreadId());
                    if (length > 0) WriteFile(file, result, (DWORD)length, &written, NULL);
                    CloseHandle(file);
                }
            }
        }
    }
    return CallNextHookEx(NULL, code, wparam, lparam);
}

BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID reserved) {
    (void)module;
    (void)reason;
    (void)reserved;
    return TRUE;
}
