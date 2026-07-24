#include <windows.h>
#include <stdint.h>
#include <stdio.h>

#define WAR3_HOTKEY_MAGIC 0x4B485257u
#define WAR3_HOTKEY_VERSION 3u
#define WAR3_HOTKEY_STATUS_PENDING 1u
#define WAR3_HOTKEY_STATUS_OK 2u
#define WAR3_HOTKEY_STATUS_FAILED 3u
#define WAR3_HOTKEY_MAX_OPS 16u

#define WAR3_HOTKEY_OP_CLICK_ORIGIN_FRAME 1u
#define WAR3_HOTKEY_OP_QUERY_COMMAND_CONTEXT 2u
#define WAR3_HOTKEY_OP_QUERY_SELECTION_CONTEXT 3u
#define WAR3_HOTKEY_OP_OVERRIDE_COMMAND_HOTKEY 4u
#define WAR3_HOTKEY_OP_REFRESH_COMMAND_BAR 5u

typedef uint64_t (__fastcall *ConvertOriginFrameTypeFn)(int32_t value);
typedef uint64_t (__fastcall *BlzGetOriginFrameFn)(uint64_t frame_type, int32_t index);
typedef void (__fastcall *BlzFrameClickFn)(uint64_t frame);
typedef uint64_t (__fastcall *CGameUIGetFn)(uint8_t create_if_missing, uint64_t reserved);
typedef uint64_t (__fastcall *JassNoArgU64Fn)(void);
typedef void (__fastcall *JassNoArgVoidFn)(void);
typedef void (__fastcall *JassGroupEnumUnitsSelectedFn)(uint64_t group, uint64_t player, uint64_t filter);
typedef uint64_t (__fastcall *JassFirstOfGroupFn)(uint64_t group);
typedef void (__fastcall *JassDestroyGroupFn)(uint64_t group);
typedef uint64_t (__fastcall *JassGetOwningPlayerFn)(uint64_t unit);
typedef int32_t (__fastcall *JassGetPlayerIdFn)(uint64_t player);
typedef void (__fastcall *SetOverridingHotkeyFn)(uint32_t row, uint32_t column, uint32_t key, uint8_t meta_key_state);
typedef void (__fastcall *SetOverridingHotkeyBoolFn)(uint32_t row, uint32_t column, uint8_t value);
typedef uint8_t (__fastcall *SaveOverridingHotkeysFn)(void);
typedef void (__fastcall *RefreshCommandBarFn)(uint64_t command_bar);

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
    uint64_t reserved_handle;
    uint32_t last_error;
    uint32_t reserved;
    NativeOp ops[WAR3_HOTKEY_MAX_OPS];
} NativeCommand;

static volatile LONG g_processing = 0;

static int executable_pointer(const void *pointer) {
    MEMORY_BASIC_INFORMATION region;
    DWORD protection;
    if ((uintptr_t)pointer < 0x10000u) {
        return 0;
    }
    if (VirtualQuery(pointer, &region, sizeof(region)) != sizeof(region)) {
        return 0;
    }
    if (region.State != MEM_COMMIT || (region.Protect & (PAGE_GUARD | PAGE_NOACCESS))) {
        return 0;
    }
    protection = region.Protect & 0xffu;
    return protection == PAGE_EXECUTE || protection == PAGE_EXECUTE_READ ||
        protection == PAGE_EXECUTE_READWRITE || protection == PAGE_EXECUTE_WRITECOPY;
}

static int readable_pointer(const void *pointer, size_t size) {
    MEMORY_BASIC_INFORMATION region;
    uintptr_t start = (uintptr_t)pointer;
    uintptr_t end;
    uintptr_t region_end;
    DWORD protection;
    if (start < 0x10000u || size == 0 || size > SIZE_MAX - start) {
        return 0;
    }
    if (VirtualQuery(pointer, &region, sizeof(region)) != sizeof(region)) {
        return 0;
    }
    if (region.State != MEM_COMMIT || (region.Protect & (PAGE_GUARD | PAGE_NOACCESS))) {
        return 0;
    }
    protection = region.Protect & 0xffu;
    if (protection != PAGE_READONLY && protection != PAGE_READWRITE &&
        protection != PAGE_WRITECOPY && protection != PAGE_EXECUTE_READ &&
        protection != PAGE_EXECUTE_READWRITE && protection != PAGE_EXECUTE_WRITECOPY) {
        return 0;
    }
    end = start + size;
    region_end = (uintptr_t)region.BaseAddress + region.RegionSize;
    return end <= region_end;
}

static int writable_pointer(const void *pointer, size_t size) {
    MEMORY_BASIC_INFORMATION region;
    uintptr_t start = (uintptr_t)pointer;
    uintptr_t end;
    uintptr_t region_end;
    DWORD protection;
    if (start < 0x10000u || size == 0 || size > SIZE_MAX - start) {
        return 0;
    }
    if (VirtualQuery(pointer, &region, sizeof(region)) != sizeof(region)) {
        return 0;
    }
    if (region.State != MEM_COMMIT || (region.Protect & (PAGE_GUARD | PAGE_NOACCESS))) {
        return 0;
    }
    protection = region.Protect & 0xffu;
    if (protection != PAGE_READWRITE && protection != PAGE_WRITECOPY &&
        protection != PAGE_EXECUTE_READWRITE && protection != PAGE_EXECUTE_WRITECOPY) {
        return 0;
    }
    end = start + size;
    region_end = (uintptr_t)region.BaseAddress + region.RegionSize;
    return end <= region_end;
}

static void command_path(wchar_t *path, DWORD count) {
    DWORD used = GetTempPathW(count, path);
    if (!used || used >= count) {
        path[0] = L'\0';
        return;
    }
    swprintf(path + used, count - used, L"war3_hotkey_native_%lu.bin", GetCurrentProcessId());
}

static DWORD click_origin_frame(NativeOp *op) {
    ConvertOriginFrameTypeFn convert_frame_type;
    BlzGetOriginFrameFn get_origin_frame;
    BlzFrameClickFn click_frame;
    uint64_t frame_type;
    uint64_t frame;
    int32_t frame_type_id = (int32_t)(op->rawcode & 0xffffu);
    int32_t index = (int32_t)((op->rawcode >> 16) & 0xffffu);

    if (frame_type_id < 0 || frame_type_id > 64 || index < 0 || index > 63) {
        return ERROR_INVALID_PARAMETER;
    }
    if (!executable_pointer((void *)(uintptr_t)op->handler) ||
        !executable_pointer((void *)(uintptr_t)op->arg0) ||
        !executable_pointer((void *)(uintptr_t)op->arg1)) {
        return ERROR_INVALID_ADDRESS;
    }
    convert_frame_type = (ConvertOriginFrameTypeFn)(uintptr_t)op->handler;
    get_origin_frame = (BlzGetOriginFrameFn)(uintptr_t)op->arg0;
    click_frame = (BlzFrameClickFn)(uintptr_t)op->arg1;
    __try {
        frame_type = convert_frame_type(frame_type_id);
        if (!frame_type) {
            return ERROR_INVALID_HANDLE;
        }
        frame = get_origin_frame(frame_type, index);
        if (!frame) {
            return ERROR_NOT_FOUND;
        }
        click_frame(frame);
        op->result = frame;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return GetExceptionCode();
    }
    return ERROR_SUCCESS;
}

static DWORD query_command_context(NativeOp *op) {
    CGameUIGetFn get_game_ui;
    uint32_t command_bar_offset = (uint32_t)(op->arg0 & 0xffffffffu);
    uint32_t submenu_link_offset = (uint32_t)(op->arg0 >> 32);
    uint64_t game_ui;
    uint64_t command_bar;
    uint64_t submenu_link;

    if (command_bar_offset < 0x100u || command_bar_offset > 0x2000u ||
        submenu_link_offset < 0x100u || submenu_link_offset > 0x1000u) {
        return ERROR_INVALID_PARAMETER;
    }
    if (!executable_pointer((void *)(uintptr_t)op->handler)) {
        return ERROR_INVALID_ADDRESS;
    }
    get_game_ui = (CGameUIGetFn)(uintptr_t)op->handler;
    __try {
        game_ui = get_game_ui(1, 0);
        if (!readable_pointer((void *)(uintptr_t)(game_ui + command_bar_offset), sizeof(uint64_t))) {
            return ERROR_INVALID_ADDRESS;
        }
        command_bar = *(uint64_t *)(uintptr_t)(game_ui + command_bar_offset);
        if (!readable_pointer((void *)(uintptr_t)(command_bar + submenu_link_offset), sizeof(uint64_t))) {
            return ERROR_INVALID_ADDRESS;
        }
        submenu_link = *(uint64_t *)(uintptr_t)(command_bar + submenu_link_offset);
        op->result = submenu_link != 0 && (submenu_link & 1u) == 0 ? 1u : 0u;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return GetExceptionCode();
    }
    return ERROR_SUCCESS;
}

static DWORD query_selection_context(NativeCommand *command, uint32_t index) {
    NativeOp *main_op;
    NativeOp *selection_op;
    NativeOp *owner_op;
    JassNoArgU64Fn create_group;
    JassNoArgVoidFn sync_selections;
    JassNoArgU64Fn get_local_player;
    JassGroupEnumUnitsSelectedFn group_enum_selected;
    JassFirstOfGroupFn first_of_group;
    JassDestroyGroupFn destroy_group;
    JassGetOwningPlayerFn get_owning_player;
    JassGetPlayerIdFn get_player_id;
    uint64_t group = 0;
    uint64_t player = 0;
    uint64_t unit = 0;
    uint64_t owner = 0;
    int32_t owner_id = -1;
    uint64_t flags = 0;
    DWORD error = ERROR_SUCCESS;

    if (index + 2 >= command->op_count) {
        return ERROR_INVALID_DATA;
    }
    main_op = &command->ops[index];
    selection_op = &command->ops[index + 1];
    owner_op = &command->ops[index + 2];
    create_group = (JassNoArgU64Fn)(uintptr_t)main_op->handler;
    sync_selections = (JassNoArgVoidFn)(uintptr_t)main_op->arg0;
    get_local_player = (JassNoArgU64Fn)(uintptr_t)main_op->arg1;
    group_enum_selected = (JassGroupEnumUnitsSelectedFn)(uintptr_t)selection_op->handler;
    first_of_group = (JassFirstOfGroupFn)(uintptr_t)selection_op->arg0;
    destroy_group = (JassDestroyGroupFn)(uintptr_t)selection_op->arg1;
    get_owning_player = (JassGetOwningPlayerFn)(uintptr_t)owner_op->handler;
    get_player_id = (JassGetPlayerIdFn)(uintptr_t)owner_op->arg0;
    if (
        !executable_pointer((void *)(uintptr_t)create_group) ||
        (sync_selections && !executable_pointer((void *)(uintptr_t)sync_selections)) ||
        !executable_pointer((void *)(uintptr_t)get_local_player) ||
        !executable_pointer((void *)(uintptr_t)group_enum_selected) ||
        !executable_pointer((void *)(uintptr_t)first_of_group) ||
        !executable_pointer((void *)(uintptr_t)destroy_group) ||
        !executable_pointer((void *)(uintptr_t)get_owning_player) ||
        !executable_pointer((void *)(uintptr_t)get_player_id)
    ) {
        return ERROR_INVALID_ADDRESS;
    }
    __try {
        group = create_group();
        player = get_local_player();
        if (!group || !player) {
            error = ERROR_NOT_FOUND;
            __leave;
        }
        if (sync_selections) {
            sync_selections();
        }
        group_enum_selected(group, player, 0);
        unit = first_of_group(group);
        if (unit) {
            flags |= 1u;
            owner = get_owning_player(unit);
            if (owner) {
                owner_id = get_player_id(owner);
                if (owner_id >= 24) {
                    flags |= 2u;
                }
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        error = GetExceptionCode();
    }
    __try {
        if (group) {
            destroy_group(group);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        if (error == ERROR_SUCCESS) {
            error = GetExceptionCode();
        }
    }
    main_op->result = flags | ((uint64_t)(uint32_t)owner_id << 32);
    selection_op->result = unit;
    owner_op->result = owner;
    selection_op->last_error = error;
    owner_op->last_error = error;
    return error;
}

static DWORD override_command_hotkey(NativeCommand *command, NativeOp *op) {
    SetOverridingHotkeyFn set_hotkey;
    SetOverridingHotkeyBoolFn set_quick_cast;
    SetOverridingHotkeyBoolFn set_hero_only;
    SaveOverridingHotkeysFn save_hotkeys;
    uint32_t row = op->rawcode & 0xffu;
    uint32_t column = (op->rawcode >> 8) & 0xffu;
    uint32_t key = (op->rawcode >> 16) & 0xffu;
    uint8_t meta_key_state = (uint8_t)((op->rawcode >> 24) & 0xffu);
    uint32_t flags = op->reserved;

    if (row >= 3 || column >= 4) {
        return ERROR_INVALID_PARAMETER;
    }
    if (!executable_pointer((void *)(uintptr_t)op->handler) ||
        !executable_pointer((void *)(uintptr_t)op->arg0) ||
        !executable_pointer((void *)(uintptr_t)op->arg1) ||
        !executable_pointer((void *)(uintptr_t)command->reserved_handle)) {
        return ERROR_INVALID_ADDRESS;
    }
    set_hotkey = (SetOverridingHotkeyFn)(uintptr_t)op->handler;
    set_quick_cast = (SetOverridingHotkeyBoolFn)(uintptr_t)op->arg0;
    set_hero_only = (SetOverridingHotkeyBoolFn)(uintptr_t)op->arg1;
    save_hotkeys = (SaveOverridingHotkeysFn)(uintptr_t)command->reserved_handle;
    __try {
        set_hotkey(row, column, key, meta_key_state);
        set_quick_cast(row, column, (uint8_t)((flags & 2u) != 0));
        set_hero_only(row, column, (uint8_t)((flags & 1u) != 0));
        if (flags & 4u) {
            if (!save_hotkeys()) {
                return ERROR_GEN_FAILURE;
            }
        }
        op->result = 1;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return GetExceptionCode();
    }
    return ERROR_SUCCESS;
}

static DWORD refresh_command_bar(NativeOp *op) {
    CGameUIGetFn get_game_ui;
    RefreshCommandBarFn refresh;
    uint32_t command_bar_offset = op->rawcode;
    uint64_t game_ui;
    uint64_t command_bar;

    if (command_bar_offset < 0x100u || command_bar_offset > 0x2000u) {
        return ERROR_INVALID_PARAMETER;
    }
    if (!executable_pointer((void *)(uintptr_t)op->handler) ||
        !executable_pointer((void *)(uintptr_t)op->arg0) ||
        !writable_pointer((void *)(uintptr_t)op->arg1, sizeof(uint8_t))) {
        return ERROR_INVALID_ADDRESS;
    }
    get_game_ui = (CGameUIGetFn)(uintptr_t)op->handler;
    refresh = (RefreshCommandBarFn)(uintptr_t)op->arg0;
    __try {
        game_ui = get_game_ui(1, 0);
        if (!readable_pointer((void *)(uintptr_t)(game_ui + command_bar_offset), sizeof(uint64_t))) {
            return ERROR_INVALID_ADDRESS;
        }
        command_bar = *(uint64_t *)(uintptr_t)(game_ui + command_bar_offset);
        if (!readable_pointer((void *)(uintptr_t)command_bar, sizeof(uint64_t))) {
            return ERROR_INVALID_ADDRESS;
        }
        *(uint8_t *)(uintptr_t)op->arg1 = op->reserved ? 1u : 0u;
        refresh(command_bar);
        op->result = command_bar;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return GetExceptionCode();
    }
    return ERROR_SUCCESS;
}

static void run_command(void) {
    wchar_t path[MAX_PATH];
    NativeCommand command;
    DWORD read_count = 0;
    DWORD write_count = 0;
    DWORD last_error = ERROR_SUCCESS;
    HANDLE file;

    ZeroMemory(&command, sizeof(command));
    command_path(path, MAX_PATH);
    if (!path[0]) {
        return;
    }
    file = CreateFileW(path, GENERIC_READ | GENERIC_WRITE, 0, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }
    if (!ReadFile(file, &command, sizeof(command), &read_count, NULL) ||
        read_count < sizeof(command) - sizeof(command.ops) ||
        command.magic != WAR3_HOTKEY_MAGIC ||
        command.version != WAR3_HOTKEY_VERSION ||
        command.status != WAR3_HOTKEY_STATUS_PENDING ||
        command.op_count == 0 || command.op_count > WAR3_HOTKEY_MAX_OPS) {
        CloseHandle(file);
        return;
    }
    for (uint32_t index = 0; index < command.op_count; ++index) {
        NativeOp *op = &command.ops[index];
        op->result = 0;
        op->last_error = ERROR_SUCCESS;
        if (op->kind == WAR3_HOTKEY_OP_CLICK_ORIGIN_FRAME) {
            op->last_error = click_origin_frame(op);
        } else if (op->kind == WAR3_HOTKEY_OP_QUERY_COMMAND_CONTEXT) {
            op->last_error = query_command_context(op);
        } else if (op->kind == WAR3_HOTKEY_OP_QUERY_SELECTION_CONTEXT) {
            op->last_error = query_selection_context(&command, index);
            index += 2;
        } else if (op->kind == WAR3_HOTKEY_OP_OVERRIDE_COMMAND_HOTKEY) {
            op->last_error = override_command_hotkey(&command, op);
        } else if (op->kind == WAR3_HOTKEY_OP_REFRESH_COMMAND_BAR) {
            op->last_error = refresh_command_bar(op);
        } else {
            op->last_error = ERROR_NOT_SUPPORTED;
        }
        if (op->last_error != ERROR_SUCCESS) {
            last_error = op->last_error;
            break;
        }
    }
    command.last_error = last_error;
    command.status = last_error == ERROR_SUCCESS ? WAR3_HOTKEY_STATUS_OK : WAR3_HOTKEY_STATUS_FAILED;
    SetFilePointer(file, 0, NULL, FILE_BEGIN);
    WriteFile(file, &command, sizeof(command), &write_count, NULL);
    SetEndOfFile(file);
    FlushFileBuffers(file);
    CloseHandle(file);
}

__declspec(dllexport) LRESULT CALLBACK War3HotkeyHookProc(int code, WPARAM w_param, LPARAM l_param) {
    (void)w_param;
    (void)l_param;
    if (code >= 0 && InterlockedCompareExchange(&g_processing, 1, 0) == 0) {
        __try {
            run_command();
        } __finally {
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
