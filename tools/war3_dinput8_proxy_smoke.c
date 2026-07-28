#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <stdio.h>

typedef HRESULT (WINAPI *DllCanUnloadNowFunction)(void);

int wmain(int argument_count, wchar_t **arguments) {
    static const char *const export_names[] = {
        "DirectInput8Create",
        "DllCanUnloadNow",
        "DllGetClassObject",
        "DllRegisterServer",
        "DllUnregisterServer",
        "GetdfDIJoystick"
    };
    HMODULE module;
    FARPROC export_address;
    DllCanUnloadNowFunction can_unload;
    HRESULT result;
    size_t index;

    if (argument_count != 2) {
        fwprintf(stderr, L"usage: %ls path-to-DINPUT8.dll\n", arguments[0]);
        return 2;
    }

    module = LoadLibraryW(arguments[1]);
    if (!module) {
        fwprintf(stderr, L"LoadLibraryW failed: %lu\n", GetLastError());
        return 3;
    }

    for (index = 0u; index < ARRAYSIZE(export_names); ++index) {
        export_address = GetProcAddress(module, export_names[index]);
        if (!export_address) {
            fprintf(stderr, "missing export: %s (%lu)\n",
                    export_names[index], GetLastError());
            FreeLibrary(module);
            return 4;
        }
    }

    for (index = 1u; index <= ARRAYSIZE(export_names); ++index) {
        export_address = GetProcAddress(module, MAKEINTRESOURCEA((WORD)index));
        if (!export_address) {
            fprintf(stderr, "missing ordinal: %zu (%lu)\n", index, GetLastError());
            FreeLibrary(module);
            return 5;
        }
    }

    can_unload = (DllCanUnloadNowFunction)GetProcAddress(module, "DllCanUnloadNow");
    result = can_unload();
    printf("PASS DllCanUnloadNow=0x%08lX\n", (unsigned long)result);
    Sleep(100u);
    FreeLibrary(module);
    return 0;
}
