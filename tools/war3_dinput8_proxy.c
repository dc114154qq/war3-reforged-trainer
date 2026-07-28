#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <stdint.h>
#include <wchar.h>

#define DINPUT_PROXY_MARKER_MAGIC 0x38444957u
#define DINPUT_PROXY_MARKER_VERSION 2u

#pragma pack(push, 1)
typedef struct DInputProxyMarker {
    uint32_t magic;
    uint32_t version;
    uint32_t process_id;
    uint32_t thread_id;
    uint32_t plugin_loaded;
    uint32_t last_error;
} DInputProxyMarker;
#pragma pack(pop)

static HMODULE g_proxy_module = NULL;
static INIT_ONCE g_initialize_once = INIT_ONCE_STATIC_INIT;

FARPROC g_original_DirectInput8Create = NULL;
FARPROC g_original_DllCanUnloadNow = NULL;
FARPROC g_original_DllGetClassObject = NULL;
FARPROC g_original_DllRegisterServer = NULL;
FARPROC g_original_DllUnregisterServer = NULL;
FARPROC g_original_GetdfDIJoystick = NULL;

static BOOL replace_file_name(
    wchar_t *path,
    size_t path_capacity,
    const wchar_t *file_name
) {
    wchar_t *separator;
    size_t remaining;

    separator = wcsrchr(path, L'\\');
    if (!separator) {
        return FALSE;
    }

    remaining = path_capacity - (size_t)(separator + 1 - path);
    return wcscpy_s(separator + 1, remaining, file_name) == 0;
}

static void write_marker(DWORD plugin_loaded, DWORD error) {
    wchar_t path[MAX_PATH];
    DWORD length;
    HANDLE file;
    DWORD written = 0u;
    DInputProxyMarker marker;

    length = GetModuleFileNameW(g_proxy_module, path, ARRAYSIZE(path));
    if (!length || length >= ARRAYSIZE(path)) {
        return;
    }
    if (!replace_file_name(
            path,
            ARRAYSIZE(path),
            L"war3_dinput8_proxy_loaded.bin")) {
        return;
    }

    marker.magic = DINPUT_PROXY_MARKER_MAGIC;
    marker.version = DINPUT_PROXY_MARKER_VERSION;
    marker.process_id = GetCurrentProcessId();
    marker.thread_id = GetCurrentThreadId();
    marker.plugin_loaded = plugin_loaded;
    marker.last_error = error;

    file = CreateFileW(
        path,
        GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL
    );
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }

    if (WriteFile(file, &marker, sizeof(marker), &written, NULL) &&
        written == sizeof(marker)) {
        FlushFileBuffers(file);
    }
    CloseHandle(file);
}

static BOOL CALLBACK initialize_proxy(
    PINIT_ONCE initialize_once,
    PVOID parameter,
    PVOID *context
) {
    wchar_t path[MAX_PATH];
    DWORD length;
    HMODULE original;
    HMODULE plugin;
    DWORD error = ERROR_SUCCESS;

    (void)initialize_once;
    (void)parameter;
    (void)context;

    length = GetModuleFileNameW(g_proxy_module, path, ARRAYSIZE(path));
    if (!length || length >= ARRAYSIZE(path)) {
        error = GetLastError();
        write_marker(
            0u,
            error != ERROR_SUCCESS ? error : ERROR_INSUFFICIENT_BUFFER
        );
        return TRUE;
    }

    if (!replace_file_name(
            path,
            ARRAYSIZE(path),
            L"DINPUT8Original.dll")) {
        write_marker(0u, ERROR_BAD_PATHNAME);
        return TRUE;
    }

    original = LoadLibraryW(path);
    if (!original) {
        write_marker(0u, GetLastError());
        return TRUE;
    }

    g_original_DirectInput8Create =
        GetProcAddress(original, "DirectInput8Create");
    g_original_DllCanUnloadNow =
        GetProcAddress(original, "DllCanUnloadNow");
    g_original_DllGetClassObject =
        GetProcAddress(original, "DllGetClassObject");
    g_original_DllRegisterServer =
        GetProcAddress(original, "DllRegisterServer");
    g_original_DllUnregisterServer =
        GetProcAddress(original, "DllUnregisterServer");
    g_original_GetdfDIJoystick =
        GetProcAddress(original, "GetdfDIJoystick");

    if (!g_original_DirectInput8Create ||
        !g_original_DllCanUnloadNow ||
        !g_original_DllGetClassObject ||
        !g_original_DllRegisterServer ||
        !g_original_DllUnregisterServer ||
        !g_original_GetdfDIJoystick) {
        error = GetLastError();
        write_marker(
            0u,
            error != ERROR_SUCCESS ? error : ERROR_PROC_NOT_FOUND
        );
        return TRUE;
    }

    length = GetModuleFileNameW(g_proxy_module, path, ARRAYSIZE(path));
    if (!length || length >= ARRAYSIZE(path)) {
        error = GetLastError();
        write_marker(
            0u,
            error != ERROR_SUCCESS ? error : ERROR_INSUFFICIENT_BUFFER
        );
        return TRUE;
    }
    if (!replace_file_name(
            path,
            ARRAYSIZE(path),
            L"War3SelectionPlugin.dll")) {
        write_marker(0u, ERROR_BAD_PATHNAME);
        return TRUE;
    }

    plugin = LoadLibraryW(path);
    if (!plugin) {
        error = GetLastError();
        if (error == ERROR_MOD_NOT_FOUND ||
            error == ERROR_FILE_NOT_FOUND ||
            error == ERROR_PATH_NOT_FOUND) {
            error = ERROR_SUCCESS;
        }
        write_marker(0u, error);
        return TRUE;
    }

    write_marker(1u, ERROR_SUCCESS);
    return TRUE;
}

void __cdecl War3DInput8ProxyEnsureInitialized(void) {
    InitOnceExecuteOnce(&g_initialize_once, initialize_proxy, NULL, NULL);
}

static DWORD WINAPI initialize_proxy_thread(void *parameter) {
    (void)parameter;
    War3DInput8ProxyEnsureInitialized();
    return ERROR_SUCCESS;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;

    if (reason == DLL_PROCESS_ATTACH) {
        HANDLE thread;

        g_proxy_module = instance;
        DisableThreadLibraryCalls(instance);
        thread = CreateThread(
            NULL,
            0u,
            initialize_proxy_thread,
            NULL,
            0u,
            NULL
        );
        if (thread) {
            CloseHandle(thread);
        }
    }
    return TRUE;
}
