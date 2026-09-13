/* Hidden, owned message-only window for testing the exact probe transport. */
#include <windows.h>
#include <stdio.h>

int main(void) {
    WNDCLASSW wc = {0};
    MSG msg;
    wc.lpfnWndProc = DefWindowProcW;
    wc.hInstance = GetModuleHandleW(NULL);
    wc.lpszClassName = L"War3EngineHookProbeHost";
    if (!RegisterClassW(&wc)) return 1;
    HWND window = CreateWindowExW(0, wc.lpszClassName, L"Engine probe host", 0,
        0, 0, 0, 0, HWND_MESSAGE, NULL, wc.hInstance, NULL);
    if (!window) return 2;
    printf("%lu %lu %llu\n", GetCurrentProcessId(), GetCurrentThreadId(), (unsigned long long)(uintptr_t)window);
    fflush(stdout);
    while (GetMessageW(&msg, NULL, 0, 0) > 0) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    DestroyWindow(window);
    return 0;
}
