#include <windows.h>
#include <stdint.h>
#include <stdio.h>

#define WAR3_NATIVE_MAGIC 0x33524757u
#define WAR3_NATIVE_VERSION 2u
#define WAR3_NATIVE_STATUS_PENDING 1u
#define WAR3_NATIVE_STATUS_OK 2u
#define WAR3_NATIVE_STATUS_FAILED 3u
#define WAR3_NATIVE_MAX_OPS 16u

#define WAR3_NATIVE_OP_ABILITY_ADD 1u
#define WAR3_NATIVE_OP_ABILITY_REMOVE 2u
#define WAR3_NATIVE_OP_UNIT_ADD_ITEM_TO_SLOT_BY_ID 10u
#define WAR3_NATIVE_OP_UNIT_ITEM_IN_SLOT 11u
#define WAR3_NATIVE_OP_REMOVE_ITEM 12u
#define WAR3_NATIVE_OP_UNIT_REMOVE_ITEM 13u
#define WAR3_NATIVE_OP_SET_ITEM_CHARGES 14u
#define WAR3_NATIVE_OP_GET_ITEM_TYPE_ID 15u
#define WAR3_NATIVE_OP_GET_UNIT_TYPE_ID 20u
#define WAR3_NATIVE_OP_UNIT_INVENTORY_SIZE 21u

typedef unsigned char (__fastcall *AbilityNativeFn)(uint64_t unit_handle, uint32_t rawcode);
typedef unsigned char (__fastcall *UnitAddItemToSlotByIdFn)(uint64_t unit_handle, uint32_t rawcode, int32_t slot);
typedef uint64_t (__fastcall *UnitItemInSlotFn)(uint64_t unit_handle, int32_t slot);
typedef void (__fastcall *RemoveItemFn)(uint64_t item_handle);
typedef void (__fastcall *UnitRemoveItemFn)(uint64_t unit_handle, uint64_t item_handle);
typedef void (__fastcall *SetItemChargesFn)(uint64_t item_handle, int32_t charges);
typedef uint32_t (__fastcall *GetItemTypeIdFn)(uint64_t item_handle);
typedef uint32_t (__fastcall *GetUnitTypeIdFn)(uint64_t unit_handle);
typedef int32_t (__fastcall *UnitInventorySizeFn)(uint64_t unit_handle);

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

static void command_path(wchar_t *path, DWORD count) {
    DWORD used = GetTempPathW(count, path);
    if (used == 0 || used >= count) {
        path[0] = L'\0';
        return;
    }
    swprintf(path + used, count - used, L"war3_reforged_native_%lu.bin", GetCurrentProcessId());
}

static DWORD WINAPI worker_thread(LPVOID param) {
    HMODULE self = (HMODULE)param;
    wchar_t path[MAX_PATH];
    NativeCommand cmd;
    DWORD got = 0;
    DWORD wrote = 0;
    DWORD status = WAR3_NATIVE_STATUS_FAILED;
    DWORD last_error = 0;

    ZeroMemory(&cmd, sizeof(cmd));
    command_path(path, MAX_PATH);
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
        FreeLibraryAndExitThread(self, 0);
    }

    if (!ReadFile(file, &cmd, sizeof(cmd), &got, NULL) || got < sizeof(NativeCommand) - sizeof(cmd.ops)) {
        last_error = GetLastError();
        goto finish;
    }
    if (
        cmd.magic != WAR3_NATIVE_MAGIC ||
        cmd.version != WAR3_NATIVE_VERSION ||
        cmd.op_count > WAR3_NATIVE_MAX_OPS ||
        cmd.unit_handle == 0
    ) {
        last_error = ERROR_INVALID_DATA;
        goto finish;
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
            case WAR3_NATIVE_OP_ABILITY_ADD:
            case WAR3_NATIVE_OP_ABILITY_REMOVE: {
                AbilityNativeFn fn = (AbilityNativeFn)(uintptr_t)op->handler;
                op->result = (uint64_t)fn(cmd.unit_handle, op->rawcode);
                break;
            }
            case WAR3_NATIVE_OP_UNIT_ADD_ITEM_TO_SLOT_BY_ID: {
                UnitAddItemToSlotByIdFn fn = (UnitAddItemToSlotByIdFn)(uintptr_t)op->handler;
                op->result = (uint64_t)fn(cmd.unit_handle, op->rawcode, (int32_t)op->arg0);
                break;
            }
            case WAR3_NATIVE_OP_UNIT_ITEM_IN_SLOT: {
                UnitItemInSlotFn fn = (UnitItemInSlotFn)(uintptr_t)op->handler;
                op->result = fn(cmd.unit_handle, (int32_t)op->arg0);
                break;
            }
            case WAR3_NATIVE_OP_REMOVE_ITEM: {
                RemoveItemFn fn = (RemoveItemFn)(uintptr_t)op->handler;
                fn(op->arg0);
                op->result = 1;
                break;
            }
            case WAR3_NATIVE_OP_UNIT_REMOVE_ITEM: {
                UnitRemoveItemFn fn = (UnitRemoveItemFn)(uintptr_t)op->handler;
                fn(cmd.unit_handle, op->arg0);
                op->result = 1;
                break;
            }
            case WAR3_NATIVE_OP_SET_ITEM_CHARGES: {
                SetItemChargesFn fn = (SetItemChargesFn)(uintptr_t)op->handler;
                fn(op->arg0, (int32_t)op->arg1);
                op->result = 1;
                break;
            }
            case WAR3_NATIVE_OP_GET_ITEM_TYPE_ID: {
                GetItemTypeIdFn fn = (GetItemTypeIdFn)(uintptr_t)op->handler;
                op->result = (uint64_t)fn(op->arg0);
                break;
            }
            case WAR3_NATIVE_OP_GET_UNIT_TYPE_ID: {
                GetUnitTypeIdFn fn = (GetUnitTypeIdFn)(uintptr_t)op->handler;
                op->result = (uint64_t)fn(cmd.unit_handle);
                break;
            }
            case WAR3_NATIVE_OP_UNIT_INVENTORY_SIZE: {
                UnitInventorySizeFn fn = (UnitInventorySizeFn)(uintptr_t)op->handler;
                op->result = (uint64_t)fn(cmd.unit_handle);
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
    FreeLibraryAndExitThread(self, 0);
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        HANDLE thread = CreateThread(NULL, 0, worker_thread, instance, 0, NULL);
        if (thread) {
            CloseHandle(thread);
        }
    }
    return TRUE;
}
