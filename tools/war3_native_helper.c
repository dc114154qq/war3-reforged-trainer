#include <windows.h>
#include <stdint.h>
#include <stdio.h>

#define WAR3_NATIVE_MAGIC 0x33524757u
#define WAR3_NATIVE_VERSION 5u
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
#define WAR3_NATIVE_OP_SET_ITEM_CHARGES 40u
#define WAR3_NATIVE_OP_SET_HERO_INT 60u
#define WAR3_NATIVE_OP_GET_HERO_INT 61u
#define WAR3_NATIVE_OP_JASS_SELECTED_UNIT 50u
#define WAR3_NATIVE_OP_JASS_SELECTED_UNIT_ARG 51u
#define WAR3_ITEM_FLAGS_OFFSET 0x38u
#define WAR3_ITEM_CHARGES_OFFSET 0x8d0u
#define WAR3_ITEM_CHARGES_EMPTY_FLAG 0x1000u

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
typedef void (__fastcall *ItemChargesNotifyFn)(uint32_t value);
typedef void (__fastcall *InternalHeroIntSetFn)(uint64_t unit_address, int32_t value, uint8_t permanent);
typedef int32_t (__fastcall *InternalHeroIntGetFn)(uint64_t unit_address, uint8_t include_bonus);
typedef uint64_t (__fastcall *JassNoArgU64Fn)(void);
typedef void (__fastcall *JassNoArgVoidFn)(void);
typedef void (__fastcall *JassGroupEnumUnitsSelectedFn)(uint64_t group, uint64_t player, uint64_t filter);
typedef uint64_t (__fastcall *JassFirstOfGroupFn)(uint64_t group);
typedef uint32_t (__fastcall *JassGetHandleIdFn)(uint64_t handle);
typedef void (__fastcall *JassDestroyGroupFn)(uint64_t group);

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

static DWORD run_jass_selected_unit(NativeCommand *cmd, uint32_t index) {
    if (index + 2 >= cmd->op_count) {
        return ERROR_INVALID_DATA;
    }

    NativeOp *main_op = &cmd->ops[index];
    NativeOp *call_op = &cmd->ops[index + 1];
    NativeOp *cleanup_op = &cmd->ops[index + 2];
    JassNoArgU64Fn create_group = (JassNoArgU64Fn)(uintptr_t)main_op->handler;
    JassNoArgVoidFn sync_selections = (JassNoArgVoidFn)(uintptr_t)main_op->arg0;
    JassNoArgU64Fn get_local_player = (JassNoArgU64Fn)(uintptr_t)main_op->arg1;
    JassGroupEnumUnitsSelectedFn group_enum_selected =
        (JassGroupEnumUnitsSelectedFn)(uintptr_t)call_op->handler;
    JassFirstOfGroupFn first_of_group = (JassFirstOfGroupFn)(uintptr_t)call_op->arg0;
    JassGetHandleIdFn get_handle_id = (JassGetHandleIdFn)(uintptr_t)call_op->arg1;
    JassDestroyGroupFn destroy_group = (JassDestroyGroupFn)(uintptr_t)cleanup_op->handler;
    uint64_t player_override = cleanup_op->arg0;
    uint64_t group = 0;
    uint64_t player = 0;
    uint64_t unit = 0;
    uint32_t handle_id = 0;
    DWORD error = 0;

    if (!create_group || !get_local_player || !group_enum_selected || !first_of_group || !get_handle_id) {
        return ERROR_INVALID_DATA;
    }

    __try {
        main_op->result = 1;
        group = create_group();
        call_op->result = group;
        if (!group) {
            error = ERROR_NOT_FOUND;
            __leave;
        }
        main_op->result = 2;
        if (sync_selections) {
            sync_selections();
        }
        main_op->result = 3;
        player = player_override ? player_override : get_local_player();
        cleanup_op->result = player;
        if (!player) {
            error = ERROR_NOT_FOUND;
            __leave;
        }
        main_op->result = 4;
        group_enum_selected(group, player, 0);
        main_op->result = 5;
        unit = first_of_group(group);
        if (unit) {
            main_op->result = 6;
            handle_id = get_handle_id(unit);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        error = GetExceptionCode();
    }

    __try {
        if (destroy_group && group) {
            destroy_group(group);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        if (!error) {
            error = GetExceptionCode();
        }
    }

    main_op->result = unit;
    main_op->last_error = error;
    call_op->result = handle_id;
    call_op->last_error = error;
    cleanup_op->result = player;
    cleanup_op->last_error = error;
    return error;
}

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
        cmd.op_count > WAR3_NATIVE_MAX_OPS
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
                if (cmd.unit_handle == 0) {
                    op->last_error = ERROR_INVALID_ADDRESS;
                    last_error = ERROR_INVALID_ADDRESS;
                    goto finish;
                }
                InternalAbilityUnitFn fn = (InternalAbilityUnitFn)(uintptr_t)op->handler;
                fn(cmd.unit_handle);
                op->result = 1;
                break;
            }
            case WAR3_NATIVE_OP_INTERNAL_ABILITY_FIND: {
                if (cmd.unit_handle == 0) {
                    op->last_error = ERROR_INVALID_ADDRESS;
                    last_error = ERROR_INVALID_ADDRESS;
                    goto finish;
                }
                InternalAbilityFindFn fn = (InternalAbilityFindFn)(uintptr_t)op->handler;
                op->result = fn(cmd.unit_handle, op->rawcode, 0, 1, 1, 1, 0);
                break;
            }
            case WAR3_NATIVE_OP_INTERNAL_ABILITY_ADD: {
                if (cmd.unit_handle == 0) {
                    op->last_error = ERROR_INVALID_ADDRESS;
                    last_error = ERROR_INVALID_ADDRESS;
                    goto finish;
                }
                InternalAbilityAddFn fn = (InternalAbilityAddFn)(uintptr_t)op->handler;
                op->result = fn(cmd.unit_handle, op->rawcode, 0, 0, 0, 0);
                break;
            }
            case WAR3_NATIVE_OP_INTERNAL_ABILITY_REMOVE: {
                if (cmd.unit_handle == 0) {
                    op->last_error = ERROR_INVALID_ADDRESS;
                    last_error = ERROR_INVALID_ADDRESS;
                    goto finish;
                }
                InternalAbilityRemoveFn fn = (InternalAbilityRemoveFn)(uintptr_t)op->handler;
                fn(cmd.unit_handle, op->arg0);
                op->result = 1;
                break;
            }
            case WAR3_NATIVE_OP_SET_ITEM_CHARGES: {
                uint8_t *item = (uint8_t *)(uintptr_t)op->arg0;
                int32_t charges = (int32_t)op->arg1;
                uint32_t *flags = (uint32_t *)(void *)(item + WAR3_ITEM_FLAGS_OFFSET);
                int32_t *item_charges = (int32_t *)(void *)(item + WAR3_ITEM_CHARGES_OFFSET);
                ItemChargesNotifyFn notify = (ItemChargesNotifyFn)(uintptr_t)op->handler;
                if (item == NULL) {
                    op->last_error = ERROR_INVALID_ADDRESS;
                    last_error = ERROR_INVALID_ADDRESS;
                    goto finish;
                }
                if (charges < 0) {
                    charges = 0;
                }
                if (charges == 0) {
                    *flags |= WAR3_ITEM_CHARGES_EMPTY_FLAG;
                } else {
                    *flags &= ~WAR3_ITEM_CHARGES_EMPTY_FLAG;
                }
                *item_charges = charges;
                notify(0);
                op->result = 1;
                break;
            }
            case WAR3_NATIVE_OP_SET_HERO_INT: {
                InternalHeroIntSetFn fn = (InternalHeroIntSetFn)(uintptr_t)op->handler;
                int32_t value = (int32_t)op->rawcode;
                uint8_t permanent = op->arg0 ? 1u : 0u;
                if (cmd.unit_handle == 0) {
                    op->last_error = ERROR_INVALID_ADDRESS;
                    last_error = ERROR_INVALID_ADDRESS;
                    goto finish;
                }
                __try {
                    fn(cmd.unit_handle, value, permanent);
                    op->result = 1;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_GET_HERO_INT: {
                InternalHeroIntGetFn fn = (InternalHeroIntGetFn)(uintptr_t)op->handler;
                uint8_t include_bonus = op->arg0 ? 1u : 0u;
                if (cmd.unit_handle == 0) {
                    op->last_error = ERROR_INVALID_ADDRESS;
                    last_error = ERROR_INVALID_ADDRESS;
                    goto finish;
                }
                __try {
                    op->result = (uint32_t)fn(cmd.unit_handle, include_bonus);
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_SELECTED_UNIT: {
                last_error = run_jass_selected_unit(&cmd, i);
                if (last_error) {
                    goto finish;
                }
                i += 2;
                break;
            }
            case WAR3_NATIVE_OP_JASS_SELECTED_UNIT_ARG:
                break;
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
