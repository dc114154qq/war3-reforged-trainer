#include <windows.h>
#include <stdint.h>
#include <stdio.h>

#define WAR3_NATIVE_MAGIC 0x33524757u
#define WAR3_NATIVE_VERSION 3u
#define WAR3_NATIVE_STATUS_PENDING 1u
#define WAR3_NATIVE_STATUS_OK 2u
#define WAR3_NATIVE_STATUS_FAILED 3u
#define WAR3_NATIVE_MAX_OPS 16u

#define WAR3_NATIVE_OP_INTERNAL_ABILITY_BEGIN 30u
#define WAR3_NATIVE_OP_INTERNAL_ABILITY_FIND 31u
#define WAR3_NATIVE_OP_INTERNAL_ABILITY_ADD 32u
#define WAR3_NATIVE_OP_INTERNAL_ABILITY_END 33u
#define WAR3_NATIVE_OP_INTERNAL_ABILITY_REFRESH 34u
#define WAR3_NATIVE_OP_INTERNAL_ABILITY_REMOVE 35u

typedef void (__fastcall *InternalAbilityUnitFn)(uint64_t unit_address);
typedef uint64_t (__fastcall *InternalAbilityFindFn)(
    uint64_t unit_address,
    uint32_t rawcode,
    uint32_t arg2,
    uint8_t arg3,
    uint8_t arg4,
    uint8_t arg5,
    uint8_t arg6
);
typedef uint64_t (__fastcall *InternalAbilityAddFn)(
    uint64_t unit_address,
    uint32_t rawcode,
    uint32_t arg2,
    uint32_t arg3,
    uint32_t arg4,
    uint32_t arg5
);
typedef void (__fastcall *InternalAbilityRemoveFn)(uint64_t unit_address, uint64_t data_address);

typedef struct NativeOp {
    uint32_t kind;
    uint32_t rawcode;
    uint64_t handler;
    uint64_t arg0;
    uint64_t arg1;
    uint64_t result;
    uint32_t last_error;
    uint32_t reserved;
} NativeOp;

typedef struct NativeCommand {
    uint32_t magic;
    uint32_t version;
    uint32_t status;
    uint32_t op_count;
    uint64_t unit_handle;
    uint32_t last_error;
    uint32_t reserved;
    NativeOp ops[WAR3_NATIVE_MAX_OPS];
} NativeCommand;

static volatile LONG g_processing = 0;

static void command_path(wchar_t *path, DWORD count) {
    DWORD used = GetTempPathW(count, path);
    if (used == 0 || used >= count) {
        path[0] = L'\0';
        return;
    }
    swprintf(path + used, count - used, L"war3_reforged_native_%lu.bin", GetCurrentProcessId());
}

static void run_command(void) {
    wchar_t path[MAX_PATH];
    NativeCommand cmd;
    DWORD got = 0;
    DWORD wrote = 0;
    DWORD status = WAR3_NATIVE_STATUS_FAILED;
    DWORD last_error = 0;

    ZeroMemory(&cmd, sizeof(cmd));
    command_path(path, MAX_PATH);
    if (!path[0]) {
        return;
    }

    HANDLE file = CreateFileW(
        path,
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        NULL,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        NULL
    );
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }

    if (!ReadFile(file, &cmd, sizeof(cmd), &got, NULL) || got < sizeof(NativeCommand) - sizeof(cmd.ops)) {
        last_error = GetLastError();
        goto finish;
    }
    if (
        cmd.magic != WAR3_NATIVE_MAGIC ||
        cmd.version != WAR3_NATIVE_VERSION ||
        cmd.status != WAR3_NATIVE_STATUS_PENDING ||
        cmd.op_count > WAR3_NATIVE_MAX_OPS ||
        cmd.unit_handle == 0
    ) {
        CloseHandle(file);
        return;
    }

    for (uint32_t i = 0; i < cmd.op_count; ++i) {
        NativeOp *op = &cmd.ops[i];
        op->result = 0;
        op->last_error = 0;
        if (op->handler == 0) {
            op->last_error = ERROR_INVALID_DATA;
            last_error = ERROR_INVALID_DATA;
            goto finish;
        }
        switch (op->kind) {
            case WAR3_NATIVE_OP_INTERNAL_ABILITY_BEGIN:
            case WAR3_NATIVE_OP_INTERNAL_ABILITY_END:
            case WAR3_NATIVE_OP_INTERNAL_ABILITY_REFRESH: {
                InternalAbilityUnitFn fn = (InternalAbilityUnitFn)(uintptr_t)op->handler;
                fn(cmd.unit_handle);
                op->result = 1;
                break;
            }
            case WAR3_NATIVE_OP_INTERNAL_ABILITY_FIND: {
                InternalAbilityFindFn fn = (InternalAbilityFindFn)(uintptr_t)op->handler;
                op->result = fn(cmd.unit_handle, op->rawcode, 0, 1, 1, 1, 0);
                break;
            }
            case WAR3_NATIVE_OP_INTERNAL_ABILITY_ADD: {
                InternalAbilityAddFn fn = (InternalAbilityAddFn)(uintptr_t)op->handler;
                op->result = fn(cmd.unit_handle, op->rawcode, 0, 0, 0, 0);
                break;
            }
            case WAR3_NATIVE_OP_INTERNAL_ABILITY_REMOVE: {
                InternalAbilityRemoveFn fn = (InternalAbilityRemoveFn)(uintptr_t)op->handler;
                fn(cmd.unit_handle, op->arg0);
                op->result = 1;
                break;
            }
            default:
                op->last_error = ERROR_INVALID_DATA;
                last_error = ERROR_INVALID_DATA;
                goto finish;
        }
    }
    status = WAR3_NATIVE_STATUS_OK;

finish:
    cmd.status = status;
    cmd.last_error = last_error;
    SetFilePointer(file, 0, NULL, FILE_BEGIN);
    WriteFile(file, &cmd, sizeof(cmd), &wrote, NULL);
    CloseHandle(file);
}

__declspec(dllexport) LRESULT CALLBACK War3HookProc(int code, WPARAM w_param, LPARAM l_param) {
    if (code >= 0) {
        if (InterlockedCompareExchange(&g_processing, 1, 0) == 0) {
            run_command();
            InterlockedExchange(&g_processing, 0);
        }
    }
    return CallNextHookEx(NULL, code, w_param, l_param);
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)instance;
    (void)reason;
    (void)reserved;
    return TRUE;
}
