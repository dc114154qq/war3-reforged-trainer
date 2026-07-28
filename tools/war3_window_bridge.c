#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <stdio.h>
#include <stdlib.h>

typedef struct FindWindowContext {
    DWORD pid;
    HWND hwnd;
} FindWindowContext;

static BOOL CALLBACK find_process_window(HWND hwnd, LPARAM parameter) {
    FindWindowContext *context = (FindWindowContext *)parameter;
    DWORD owner_pid = 0;
    RECT rectangle;
    GetWindowThreadProcessId(hwnd, &owner_pid);
    if (owner_pid != context->pid || GetWindow(hwnd, GW_OWNER) != NULL) {
        return TRUE;
    }
    if (!GetWindowRect(hwnd, &rectangle) || rectangle.right <= rectangle.left ||
        rectangle.bottom <= rectangle.top) {
        return TRUE;
    }
    context->hwnd = hwnd;
    return FALSE;
}

int wmain(int argc, wchar_t **argv) {
    FindWindowContext context;
    DWORD foreground_thread;
    DWORD current_thread;
    wchar_t title[256];
    LONG_PTR style;
    LONG_PTR extended_style;
    RECT rectangle;
    if (argc != 2) {
        fwprintf(stderr, L"usage: %s PID\n", argv[0]);
        return 2;
    }
    context.pid = wcstoul(argv[1], NULL, 0);
    context.hwnd = NULL;
    EnumWindows(find_process_window, (LPARAM)&context);
    if (!context.hwnd) {
        fwprintf(stderr, L"window not found pid=%lu\n", context.pid);
        return 3;
    }
    ShowWindow(context.hwnd, SW_RESTORE);
    foreground_thread = GetWindowThreadProcessId(GetForegroundWindow(), NULL);
    current_thread = GetCurrentThreadId();
    if (foreground_thread && foreground_thread != current_thread) {
        AttachThreadInput(current_thread, foreground_thread, TRUE);
    }
    BringWindowToTop(context.hwnd);
    SetForegroundWindow(context.hwnd);
    SetActiveWindow(context.hwnd);
    SetFocus(context.hwnd);
    if (foreground_thread && foreground_thread != current_thread) {
        AttachThreadInput(current_thread, foreground_thread, FALSE);
    }
    title[0] = L'\0';
    GetWindowTextW(context.hwnd, title, (int)(sizeof(title) / sizeof(title[0])));
    GetWindowRect(context.hwnd, &rectangle);
    style = GetWindowLongPtrW(context.hwnd, GWL_STYLE);
    extended_style = GetWindowLongPtrW(context.hwnd, GWL_EXSTYLE);
    wprintf(L"pid=%lu hwnd=%p visible=%d iconic=%d title=%ls rect=%ld,%ld,%ld,%ld "
            L"style=0x%llx exstyle=0x%llx foreground=%d\n",
            context.pid, context.hwnd, IsWindowVisible(context.hwnd), IsIconic(context.hwnd),
            title, rectangle.left, rectangle.top, rectangle.right, rectangle.bottom,
            (unsigned long long)style, (unsigned long long)extended_style,
            GetForegroundWindow() == context.hwnd);
    return 0;
}
