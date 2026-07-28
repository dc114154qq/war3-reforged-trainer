#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <stdint.h>
#include <stdio.h>
#include <wchar.h>

typedef DWORD (WINAPI *War3SelectionLimitSelfTestFn)(uint32_t scenario);

int wmain(int argc, wchar_t **argv) {
    DLL_DIRECTORY_COOKIE cookie;
    HMODULE module;
    War3SelectionLimitSelfTestFn self_test;
    uint32_t scenario;
    DWORD result;

    if (argc != 4) {
        fwprintf(
            stderr,
            L"usage: %ls DLL_PATH DEPENDENCY_DIRECTORY SCENARIO\n",
            argv[0]
        );
        return 2;
    }
    scenario = (uint32_t)wcstoul(argv[3], NULL, 0);
    if (!SetDefaultDllDirectories(
            LOAD_LIBRARY_SEARCH_USER_DIRS |
            LOAD_LIBRARY_SEARCH_SYSTEM32
        )) {
        fwprintf(stderr, L"SetDefaultDllDirectories failed: %lu\n", GetLastError());
        return 3;
    }
    cookie = AddDllDirectory(argv[2]);
    if (!cookie) {
        fwprintf(stderr, L"AddDllDirectory failed: %lu\n", GetLastError());
        return 4;
    }
    module = LoadLibraryExW(
        argv[1],
        NULL,
        LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR |
        LOAD_LIBRARY_SEARCH_USER_DIRS |
        LOAD_LIBRARY_SEARCH_SYSTEM32
    );
    if (!module) {
        fwprintf(stderr, L"LoadLibraryExW failed: %lu\n", GetLastError());
        RemoveDllDirectory(cookie);
        return 5;
    }
    self_test = (War3SelectionLimitSelfTestFn)(void *)GetProcAddress(
        module,
        "War3SelectionLimitSelfTest"
    );
    if (!self_test) {
        fwprintf(stderr, L"GetProcAddress failed: %lu\n", GetLastError());
        FreeLibrary(module);
        RemoveDllDirectory(cookie);
        return 6;
    }
    result = self_test(scenario);
    wprintf(L"scenario=%lu result=%lu\n", scenario, result);
    RemoveDllDirectory(cookie);
    return result == ERROR_SUCCESS ? 0 : 1;
}
