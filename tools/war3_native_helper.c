#include <windows.h>
#include <stdint.h>
#include <stdio.h>

#define WAR3_NATIVE_MAGIC 0x33524757u
#define WAR3_NATIVE_VERSION 15u
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
#define WAR3_NATIVE_OP_REMOVE_ITEM_SLOT 41u
#define WAR3_NATIVE_OP_ADD_ITEM_TO_SLOT_BY_ID 42u
#define WAR3_NATIVE_OP_GET_ITEM_TYPE_IN_SLOT 43u
#define WAR3_NATIVE_OP_SET_HERO_INT 60u
#define WAR3_NATIVE_OP_GET_HERO_INT 61u
#define WAR3_NATIVE_OP_JASS_SELECTED_UNIT 50u
#define WAR3_NATIVE_OP_JASS_SELECTED_UNIT_ARG 51u
#define WAR3_NATIVE_OP_JASS_LOCAL_PLAYER_QUERY 52u
#define WAR3_NATIVE_OP_JASS_LOCAL_PLAYER_SET 53u
#define WAR3_NATIVE_OP_JASS_UNIT_VOID 70u
#define WAR3_NATIVE_OP_JASS_UNIT_BOOL 71u
#define WAR3_NATIVE_OP_JASS_UNIT_INT_BOOL 72u
#define WAR3_NATIVE_OP_JASS_UNIT_RAWCODE 73u
#define WAR3_NATIVE_OP_JASS_UNIT_RAWCODE_LEVEL 74u
#define WAR3_NATIVE_OP_JASS_UNIT_SCALE 75u
#define WAR3_NATIVE_OP_JASS_WORLD_BOOL 76u
#define WAR3_NATIVE_OP_JASS_UNIT_INT_QUERY 77u
#define WAR3_NATIVE_OP_JASS_EXPLODE_UNIT 78u
#define WAR3_NATIVE_OP_JASS_TAKE_OWNERSHIP 79u
#define WAR3_NATIVE_OP_JASS_CREATE_LOCAL_UNIT 80u
#define WAR3_NATIVE_OP_JASS_CLEAR_INVENTORY 81u
#define WAR3_NATIVE_OP_JASS_SET_LOCAL_TECH 82u
#define WAR3_NATIVE_OP_JASS_SET_LOCAL_XP_RATE 83u
#define WAR3_NATIVE_OP_JASS_KILL_OWNER_UNITS 84u
#define WAR3_NATIVE_OP_JASS_MULTI_ARG 85u
#define WAR3_NATIVE_OP_JASS_PEACE_MODE 86u
#define WAR3_NATIVE_OP_JASS_WORLD_INT_QUERY 87u
#define WAR3_NATIVE_OP_JASS_FOG_BOOL 88u
#define WAR3_NATIVE_OP_JASS_SET_INVENTORY_CHARGES 89u
#define WAR3_NATIVE_OP_JASS_DUPLICATE_INVENTORY 90u
#define WAR3_NATIVE_OP_JASS_DROP_INVENTORY 91u
#define WAR3_NATIVE_OP_JASS_REMOVE_ALL_ABILITIES 92u
#define WAR3_NATIVE_OP_QUERY_WORLD_POINT 93u
#define WAR3_NATIVE_OP_JASS_SET_UNIT_POSITION 94u
#define WAR3_NATIVE_OP_CREATE_ALL_ITEMS 95u
#define WAR3_NATIVE_OP_REMOVE_ITEM_HANDLES 98u
#define WAR3_NATIVE_OP_REMOVE_ITEM_HANDLES_ARG 99u
#define WAR3_NATIVE_OP_CAST_ABILITY 100u
#define WAR3_NATIVE_OP_DIRECT_ABILITY_TARGET 101u
#define WAR3_NATIVE_OP_DIRECT_ABILITY_IMMEDIATE 102u
#define WAR3_NATIVE_OP_DIRECT_ABILITY_POINT 103u
#define WAR3_NATIVE_OP_DIRECT_ABILITY_NOARG_DERIVED 104u
#define WAR3_NATIVE_OP_DIRECT_ABILITY_BUFF 105u
#define WAR3_NATIVE_OP_DIRECT_ABILITY_ENUM 106u
#define WAR3_NATIVE_OP_JASS_ABILITY_REAL_LEVEL_FIELD_SET 107u
#define WAR3_NATIVE_OP_JASS_UNIT_RESOLVE 109u
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
typedef uint64_t (__fastcall *InternalUnitItemInSlotFn)(uint64_t unit, int32_t slot);
typedef uint8_t (__fastcall *InternalUnitRemoveItemFn)(uint64_t unit, uint64_t item);
typedef uint64_t (__fastcall *InternalCreateItemFn)(uint32_t item_id, float *x, float *y, uint32_t player);
typedef uint8_t (__fastcall *InternalUnitAddItemToSlotFn)(
    uint64_t unit,
    uint64_t item,
    int32_t slot,
    uint8_t unknown
);
typedef void (__fastcall *InternalItemPreRemoveFn)(uint64_t item);
typedef void (__fastcall *InternalItemRemoveFn)(uint64_t item, const char *reason);
typedef void (__fastcall *InternalHeroIntSetFn)(uint64_t unit_address, int32_t value, uint8_t permanent);
typedef int32_t (__fastcall *InternalHeroIntGetFn)(uint64_t unit_address, uint8_t include_bonus);
typedef uint64_t (__fastcall *JassNoArgU64Fn)(void);
typedef void (__fastcall *JassNoArgVoidFn)(void);
typedef void (__fastcall *JassGroupEnumUnitsSelectedFn)(uint64_t group, uint64_t player, uint64_t filter);
typedef uint64_t (__fastcall *JassFirstOfGroupFn)(uint64_t group);
typedef uint32_t (__fastcall *JassGetHandleIdFn)(uint64_t handle);
typedef void (__fastcall *JassDestroyGroupFn)(uint64_t group);
typedef int32_t (__fastcall *JassGetPlayerIdFn)(uint64_t player);
typedef int32_t (__fastcall *JassGetPlayerStateFn)(uint64_t player, uint32_t state);
typedef void (__fastcall *JassSetPlayerStateFn)(uint64_t player, uint32_t state, int32_t value);
typedef void (__fastcall *JassUnitVoidFn)(uint64_t unit);
typedef void (__fastcall *JassUnitBoolFn)(uint64_t unit, uint32_t value);
typedef void (__fastcall *JassUnitIntBoolFn)(uint64_t unit, int32_t value, uint32_t flag);
typedef uint64_t (__fastcall *JassUnitRawcodeFn)(uint64_t unit, uint32_t rawcode);
typedef uint64_t (__fastcall *JassUnitRawcodeLevelFn)(uint64_t unit, uint32_t rawcode, int32_t level);
typedef void (__fastcall *JassUnitScaleFn)(uint64_t unit, float *x, float *y, float *z);
typedef void (__fastcall *JassBoolFn)(uint32_t value);
typedef int32_t (__fastcall *JassUnitIntQueryFn)(uint64_t unit);
typedef void (__fastcall *JassSetUnitOwnerFn)(uint64_t unit, uint64_t player, uint32_t change_color);
typedef uint64_t (__fastcall *JassCreateUnitFn)(
    uint64_t player,
    uint32_t rawcode,
    float *x,
    float *y,
    float *facing
);
typedef uint64_t (__fastcall *JassUnitItemInSlotFn)(uint64_t unit, int32_t slot);
typedef void (__fastcall *JassRemoveItemFn)(uint64_t item);
typedef void (__fastcall *JassSetItemChargesFn)(uint64_t item, int32_t charges);
typedef uint32_t (__fastcall *JassGetItemTypeIdFn)(uint64_t item);
typedef void (__fastcall *JassUnitRemoveItemFn)(uint64_t unit, uint64_t item);
typedef uint64_t (__fastcall *JassGetUnitAbilityByIndexFn)(uint64_t unit, int32_t index);
typedef uint32_t (__fastcall *JassGetAbilityIdFn)(uint64_t ability);
typedef void (__fastcall *JassSetPlayerTechFn)(uint64_t player, uint32_t rawcode, int32_t level);
typedef void (__fastcall *JassSetPlayerRealFn)(uint64_t player, float *value);
typedef uint64_t (__fastcall *JassGetOwningPlayerFn)(uint64_t unit);
typedef void (__fastcall *JassGroupEnumUnitsOfPlayerFn)(uint64_t group, uint64_t player, uint64_t filter);
typedef void (__fastcall *JassGroupRemoveUnitFn)(uint64_t group, uint64_t unit);
typedef uint64_t (__fastcall *JassPlayerFn)(int32_t player_id);
typedef uint32_t (__fastcall *JassGetUnitTypeIdFn)(uint64_t unit);
typedef uint32_t (__fastcall *JassUnitRealQueryFn)(uint64_t unit);
typedef uint32_t (__fastcall *JassUnitAddAbilityFn)(uint64_t unit, uint32_t rawcode);
typedef uint32_t (__fastcall *JassSetUnitAbilityLevelFn)(
    uint64_t unit,
    uint32_t rawcode,
    int32_t level
);
typedef void (__fastcall *JassSetUnitStateFn)(uint64_t unit, int32_t state, float *value);
typedef uint32_t (__fastcall *JassIssuePointOrderByIdFn)(
    uint64_t unit,
    int32_t order_id,
    float *x,
    float *y
);
typedef uint32_t (__fastcall *JassIssueTargetOrderByIdFn)(
    uint64_t unit,
    int32_t order_id,
    uint64_t target
);
typedef uint32_t (__fastcall *JassIssueImmediateOrderByIdFn)(uint64_t unit, int32_t order_id);
typedef void (__fastcall *JassUnitApplyTimedLifeFn)(
    uint64_t unit,
    uint32_t buff_rawcode,
    float *duration
);
typedef uint32_t (__fastcall *JassIsPlayerEnemyFn)(uint64_t player, uint64_t other_player);
typedef uint32_t (__fastcall *JassUnitRemoveAbilityFn)(uint64_t unit, uint32_t rawcode);
typedef void (__fastcall *JassUnitIntVoidFn)(uint64_t unit, int32_t value);
typedef void (__fastcall *DirectAbilityTargetFn)(uint64_t ability, uint64_t target_unit);
typedef void (__fastcall *DirectAbilityImmediateFn)(uint64_t ability);
typedef void (__fastcall *DirectAbilityPointFn)(uint64_t ability, float *x, float *y);
typedef uint64_t (__fastcall *JassUnitHandleResolveFn)(uint64_t unit_handle);
typedef uint32_t (__fastcall *JassAbilityRealLevelFieldSetFn)(
    uint64_t ability,
    uint32_t field,
    int32_t level,
    float *value
);
typedef struct War3BuffData {
    uint32_t alias;
    uint32_t item_id;
    int32_t target_flags;
    int32_t level;
    int32_t priority;
    uint8_t has_levels;
    uint8_t hero_buff;
    uint16_t padding;
    float duration;
    float hero_duration;
    int32_t addon;
} War3BuffData;
typedef void (__fastcall *War3BuffDataConstructFn)(
    War3BuffData *buff_data,
    uint64_t ability,
    uint32_t index
);
typedef void (__fastcall *DirectAbilityBuffFn)(
    uint64_t ability,
    uint64_t target_unit,
    War3BuffData *buff_data,
    float *duration
);
typedef void (__fastcall *JassSetPlayerAllianceFn)(
    uint64_t source,
    uint64_t other,
    int32_t alliance_type,
    uint32_t value
);
typedef int32_t (__fastcall *JassNoArgIntFn)(void);
typedef void (__fastcall *JassSetUnitPositionFn)(uint64_t unit, float *x, float *y);
typedef uint64_t (__fastcall *JassCreateItemFn)(uint32_t rawcode, float *x, float *y);
typedef void *(__fastcall *War3GetGameUIFn)(uint8_t in_game, uint8_t unused);
typedef void *(__fastcall *War3WorldFrameFn)(void *game_ui);
typedef uint8_t (__fastcall *War3GetWorldPointFn)(
    void *world_frame,
    float *world_point,
    uint8_t clamp
);

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

typedef struct War3CastPendingEntry {
    uint64_t dummy;
    uint64_t target;
    float order_x;
    float order_y;
} War3CastPendingEntry;

typedef struct War3CastPendingState {
    int active;
    uint64_t unit_handle;
    NativeOp signature[8];
    War3CastPendingEntry *entries;
    uint32_t entry_count;
    uint32_t cast_type;
    uint32_t order_id;
    uint32_t success_limit;
    float duration;
    ULONGLONG ready_tick;
    uint64_t issue_point_order;
    uint64_t issue_target_order;
    uint64_t issue_immediate_order;
    uint64_t unit_apply_timed_life;
    uint64_t remove_unit;
} War3CastPendingState;

static DWORD war3_remove_item_handles(NativeCommand *cmd, uint32_t index);
static DWORD war3_cast_ability(NativeCommand *cmd, uint32_t index);
static DWORD war3_direct_ability_enum(
    NativeCommand *cmd,
    uint32_t index,
    uint64_t **extra_results,
    uint32_t *extra_result_count
);

static volatile LONG g_processing = 0;
static const char g_item_remove_reason[] = "War3TrainerReplaceItem";
static War3CastPendingState g_cast_pending = {0};

typedef struct War3CodeRange {
    uint8_t *begin;
    size_t size;
} War3CodeRange;

typedef struct War3WorldPointFunctions {
    War3GetGameUIFn get_game_ui;
    War3WorldFrameFn world_frame;
    War3GetWorldPointFn get_world_point;
} War3WorldPointFunctions;

static War3WorldPointFunctions g_world_point_functions = {0};
static HMODULE g_world_point_module = NULL;

static DWORD war3_query_world_point(uint64_t *packed_result);

static float war3_real_from_bits(uint32_t bits) {
    float value = 0.0f;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

static int war3_readable_pointer(const void *pointer) {
    MEMORY_BASIC_INFORMATION region;
    uintptr_t value = (uintptr_t)pointer;
    if (value < 0x10000u || value > 0x00007fffffffffffULL) {
        return 0;
    }
    if (VirtualQuery(pointer, &region, sizeof(region)) != sizeof(region)) {
        return 0;
    }
    if (region.State != MEM_COMMIT || (region.Protect & (PAGE_GUARD | PAGE_NOACCESS))) {
        return 0;
    }
    return 1;
}

static int war3_executable_pointer(uint64_t address) {
    MEMORY_BASIC_INFORMATION region;
    DWORD protection;
    if (address < 0x10000u || address > 0x00007fffffffffffULL) {
        return 0;
    }
    if (VirtualQuery((const void *)(uintptr_t)address, &region, sizeof(region)) != sizeof(region)) {
        return 0;
    }
    if (region.State != MEM_COMMIT || (region.Protect & (PAGE_GUARD | PAGE_NOACCESS))) {
        return 0;
    }
    protection = region.Protect & 0xffu;
    return
        protection == PAGE_EXECUTE ||
        protection == PAGE_EXECUTE_READ ||
        protection == PAGE_EXECUTE_READWRITE ||
        protection == PAGE_EXECUTE_WRITECOPY;
}

static int war3_section_range(HMODULE module, const char *name, War3CodeRange *range) {
    uint8_t *base = (uint8_t *)(void *)module;
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)(void *)base;
    IMAGE_NT_HEADERS64 *nt;
    IMAGE_SECTION_HEADER *section;
    if (!module || !name || !range || dos->e_magic != IMAGE_DOS_SIGNATURE) {
        return 0;
    }
    nt = (IMAGE_NT_HEADERS64 *)(void *)(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE || nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR64_MAGIC) {
        return 0;
    }
    section = IMAGE_FIRST_SECTION(nt);
    for (uint16_t index = 0; index < nt->FileHeader.NumberOfSections; ++index, ++section) {
        char section_name[9] = {0};
        memcpy(section_name, section->Name, 8);
        if (strcmp(section_name, name) == 0) {
            size_t size = section->Misc.VirtualSize;
            if (size == 0) {
                size = section->SizeOfRawData;
            }
            range->begin = base + section->VirtualAddress;
            range->size = size;
            return range->begin != NULL && range->size != 0;
        }
    }
    return 0;
}

static int war3_address_in_range(const void *address, const War3CodeRange *range) {
    uintptr_t value = (uintptr_t)address;
    uintptr_t begin = (uintptr_t)range->begin;
    return value >= begin && value < begin + range->size;
}

static void *war3_rel32_target(const uint8_t *call_instruction) {
    int32_t displacement = 0;
    memcpy(&displacement, call_instruction + 1, sizeof(displacement));
    return (void *)(call_instruction + 5 + displacement);
}

static void *war3_rip_target(
    const uint8_t *instruction,
    size_t instruction_length,
    size_t displacement_offset
) {
    int32_t displacement = 0;
    memcpy(&displacement, instruction + displacement_offset, sizeof(displacement));
    return (void *)(instruction + instruction_length + displacement);
}

static int war3_pattern_matches(
    const uint8_t *candidate,
    const uint8_t *pattern,
    const uint8_t *fixed,
    size_t length
) {
    for (size_t index = 0; index < length; ++index) {
        if (fixed[index] && candidate[index] != pattern[index]) {
            return 0;
        }
    }
    return 1;
}

static const uint8_t *war3_find_unique_pattern(
    const uint8_t *begin,
    size_t size,
    const uint8_t *pattern,
    const uint8_t *fixed,
    size_t pattern_size
) {
    const uint8_t *match = NULL;
    if (!begin || size < pattern_size) {
        return NULL;
    }
    for (size_t offset = 0; offset <= size - pattern_size; ++offset) {
        const uint8_t *candidate = begin + offset;
        if (!war3_pattern_matches(candidate, pattern, fixed, pattern_size)) {
            continue;
        }
        if (match) {
            return NULL;
        }
        match = candidate;
    }
    return match;
}

static DWORD war3_resolve_loaded_item_list(
    const uint8_t *choose_random_item,
    uint32_t **count_pointer,
    uint64_t **root_pointer,
    int32_t **link_offset_pointer,
    uint8_t *rawcode_offset
) {
    static const uint8_t count_pattern[] = {
        0x8b, 0x1d, 0, 0, 0, 0, 0x85, 0xdb, 0x74,
    };
    static const uint8_t count_fixed[] = {
        1, 1, 0, 0, 0, 0, 1, 1, 1,
    };
    static const uint8_t root_pattern[] = {
        0x48, 0x8b, 0x05, 0, 0, 0, 0, 0xa8, 0x01,
    };
    static const uint8_t root_fixed[] = {
        1, 1, 1, 0, 0, 0, 0, 1, 1,
    };
    static const uint8_t offset_pattern[] = {
        0x48, 0x63, 0x05, 0, 0, 0, 0, 0x48, 0x8b, 0x54, 0x08, 0x08,
    };
    static const uint8_t offset_fixed[] = {
        1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 1,
    };
    static const uint8_t rawcode_pattern[] = {
        0x8b, 0x59, 0, 0x8b, 0xcb,
    };
    static const uint8_t rawcode_fixed[] = {
        1, 1, 0, 1, 1,
    };
    HMODULE module = GetModuleHandleW(NULL);
    War3CodeRange text = {0};
    const uint8_t *enumerator = NULL;
    const uint8_t *selected_count_match = NULL;
    const uint8_t *selected_root_match = NULL;
    const uint8_t *selected_offset_match = NULL;
    const uint8_t *selected_rawcode_match = NULL;

    if (
        !choose_random_item || !count_pointer || !root_pointer ||
        !link_offset_pointer || !rawcode_offset ||
        !war3_section_range(module, ".text", &text) ||
        !war3_address_in_range(choose_random_item, &text)
    ) {
        return ERROR_INVALID_ADDRESS;
    }
    for (size_t offset = 0; offset < 0x60; ++offset) {
        const uint8_t *instruction = choose_random_item + offset;
        const uint8_t *target;
        const uint8_t *count_match;
        const uint8_t *root_match;
        const uint8_t *offset_match;
        const uint8_t *rawcode_match;
        if (instruction[0] != 0xe8) {
            continue;
        }
        target = (const uint8_t *)war3_rel32_target(instruction);
        if (!war3_address_in_range(target, &text)) {
            continue;
        }
        count_match = war3_find_unique_pattern(
            target,
            0x180,
            count_pattern,
            count_fixed,
            sizeof(count_pattern)
        );
        root_match = war3_find_unique_pattern(
            target,
            0x180,
            root_pattern,
            root_fixed,
            sizeof(root_pattern)
        );
        offset_match = war3_find_unique_pattern(
            target,
            0x180,
            offset_pattern,
            offset_fixed,
            sizeof(offset_pattern)
        );
        rawcode_match = war3_find_unique_pattern(
            target,
            0x180,
            rawcode_pattern,
            rawcode_fixed,
            sizeof(rawcode_pattern)
        );
        if (count_match && root_match && offset_match && rawcode_match) {
            if (enumerator && enumerator != target) {
                return ERROR_MORE_DATA;
            }
            enumerator = target;
            selected_count_match = count_match;
            selected_root_match = root_match;
            selected_offset_match = offset_match;
            selected_rawcode_match = rawcode_match;
        }
    }
    if (!enumerator) {
        return ERROR_NOT_FOUND;
    }
    *count_pointer = (uint32_t *)war3_rip_target(selected_count_match, 6, 2);
    *root_pointer = (uint64_t *)war3_rip_target(selected_root_match, 7, 3);
    *link_offset_pointer = (int32_t *)war3_rip_target(selected_offset_match, 7, 3);
    *rawcode_offset = selected_rawcode_match[2];
    if (
        !war3_readable_pointer(*count_pointer) ||
        !war3_readable_pointer(*root_pointer) ||
        !war3_readable_pointer(*link_offset_pointer) ||
        *rawcode_offset > 0x80u
    ) {
        return ERROR_INVALID_DATA;
    }
    return ERROR_SUCCESS;
}

static int war3_valid_rawcode(uint32_t rawcode) {
    for (int shift = 24; shift >= 0; shift -= 8) {
        uint8_t character = (uint8_t)(rawcode >> shift);
        if (character < 0x21u || character > 0x7eu) {
            return 0;
        }
    }
    return 1;
}

static DWORD war3_create_all_loaded_items(
    const uint8_t *choose_random_item,
    JassCreateItemFn create_item,
    uint32_t limit,
    int dry_run,
    uint64_t *packed_result,
    uint64_t **created_items,
    uint32_t *created_item_count
) {
    uint32_t *count_pointer = NULL;
    uint64_t *root_pointer = NULL;
    int32_t *link_offset_pointer = NULL;
    uint8_t rawcode_offset = 0;
    uint32_t total = 0;
    uint64_t root = 0;
    int32_t link_offset = 0;
    uint64_t node = 0;
    uint32_t validated = 0;
    uint32_t created = 0;
    uint32_t capacity = 0;
    uint64_t *items = NULL;
    uint64_t position_bits = 0;
    float x = 0.0f;
    float y = 0.0f;
    DWORD error = ERROR_SUCCESS;
    __try {
        error = war3_resolve_loaded_item_list(
            choose_random_item,
            &count_pointer,
            &root_pointer,
            &link_offset_pointer,
            &rawcode_offset
        );
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return GetExceptionCode();
    }
    if (error != ERROR_SUCCESS) {
        return error;
    }
    if (!create_item || !packed_result || !created_items || !created_item_count) {
        return ERROR_INVALID_PARAMETER;
    }
    *created_items = NULL;
    *created_item_count = 0;
    __try {
        total = *count_pointer;
        root = *root_pointer;
        link_offset = *link_offset_pointer;
        if (
            total == 0 || total > 100000u ||
            link_offset < -0x1000 || link_offset > 0x1000
        ) {
            error = ERROR_INVALID_DATA;
            __leave;
        }
        node = (!root || (root & 1u)) ? 0 : root;
        while (validated < total) {
            uint64_t next;
            uint32_t rawcode;
            if (!node || !war3_readable_pointer((void *)(uintptr_t)node)) {
                error = ERROR_INVALID_ADDRESS;
                __leave;
            }
            rawcode = *(uint32_t *)(uintptr_t)(node + rawcode_offset);
            if (!war3_valid_rawcode(rawcode)) {
                error = ERROR_INVALID_DATA;
                __leave;
            }
            next = *(uint64_t *)(uintptr_t)(node + link_offset + 8);
            if (next == node) {
                error = ERROR_CIRCULAR_DEPENDENCY;
                __leave;
            }
            node = (!next || (next & 1u)) ? 0 : next;
            ++validated;
        }
        if (node != 0) {
            error = ERROR_MORE_DATA;
            __leave;
        }
        if (dry_run) {
            *packed_result = (uint64_t)total << 32;
            error = ERROR_SUCCESS;
            __leave;
        }
        capacity = limit && limit < total ? limit : total;
        items = (uint64_t *)HeapAlloc(
            GetProcessHeap(),
            HEAP_ZERO_MEMORY,
            (SIZE_T)capacity * sizeof(uint64_t)
        );
        if (!items) {
            error = ERROR_OUTOFMEMORY;
            __leave;
        }
        error = war3_query_world_point(&position_bits);
        if (error != ERROR_SUCCESS) {
            __leave;
        }
        {
            uint32_t x_bits = (uint32_t)position_bits;
            uint32_t y_bits = (uint32_t)(position_bits >> 32);
            memcpy(&x, &x_bits, sizeof(x));
            memcpy(&y, &y_bits, sizeof(y));
        }
        node = (!root || (root & 1u)) ? 0 : root;
        while (node && created < total && (!limit || created < limit)) {
            uint32_t rawcode = *(uint32_t *)(uintptr_t)(node + rawcode_offset);
            uint64_t next = *(uint64_t *)(uintptr_t)(node + link_offset + 8);
            uint64_t item = create_item(rawcode, &x, &y);
            if (item) {
                items[created] = item;
                ++created;
            }
            node = (!next || (next & 1u)) ? 0 : next;
        }
        *packed_result = (uint64_t)created | ((uint64_t)total << 32);
        *created_items = items;
        *created_item_count = created;
        items = NULL;
        error = ERROR_SUCCESS;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        error = GetExceptionCode();
    }
    if (items) {
        HeapFree(GetProcessHeap(), 0, items);
    }
    return error;
}

static DWORD war3_resolve_world_point_functions(War3WorldPointFunctions *functions) {
    static const uint8_t pattern[] = {
        0x33, 0xd2, 0xb1, 0x01, 0x40, 0x32, 0xf6, 0xe8, 0, 0, 0, 0,
        0x48, 0x89, 0x5c, 0x24, 0x30, 0x89, 0x5c, 0x24, 0x38,
        0x48, 0x85, 0xc0, 0x74, 0x28, 0x48, 0x8b, 0xc8, 0xe8, 0, 0, 0, 0,
        0x48, 0x85, 0xc0, 0x74, 0x1b, 0x45, 0x33, 0xc0,
        0x48, 0x8d, 0x54, 0x24, 0x30, 0x48, 0x8b, 0xc8, 0xe8, 0, 0, 0, 0,
        0x84, 0xc0,
    };
    static const uint8_t fixed[] = {
        1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0,
        1, 1, 1, 1, 1, 1, 1, 1, 1,
        1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0,
        1, 1, 1, 1, 1, 1, 1, 1,
        1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0,
        1, 1,
    };
    HMODULE module = GetModuleHandleW(NULL);
    War3CodeRange text = {0};
    const uint8_t *match = NULL;
    size_t match_count = 0;
    void *get_game_ui;
    void *world_frame;
    void *get_world_point;

    if (!functions || !module || !war3_section_range(module, ".text", &text)) {
        return ERROR_BAD_EXE_FORMAT;
    }
    if (
        g_world_point_module == module &&
        g_world_point_functions.get_game_ui &&
        g_world_point_functions.world_frame &&
        g_world_point_functions.get_world_point
    ) {
        *functions = g_world_point_functions;
        return ERROR_SUCCESS;
    }
    if (text.size < sizeof(pattern)) {
        return ERROR_NOT_FOUND;
    }
    for (size_t offset = 0; offset <= text.size - sizeof(pattern); ++offset) {
        const uint8_t *candidate = text.begin + offset;
        if (!war3_pattern_matches(candidate, pattern, fixed, sizeof(pattern))) {
            continue;
        }
        match = candidate;
        ++match_count;
        if (match_count > 1) {
            return ERROR_MORE_DATA;
        }
    }
    if (!match) {
        return ERROR_NOT_FOUND;
    }
    get_game_ui = war3_rel32_target(match + 7);
    world_frame = war3_rel32_target(match + 29);
    get_world_point = war3_rel32_target(match + 50);
    if (
        !war3_address_in_range(get_game_ui, &text) ||
        !war3_address_in_range(world_frame, &text) ||
        !war3_address_in_range(get_world_point, &text)
    ) {
        return ERROR_INVALID_ADDRESS;
    }
    functions->get_game_ui = (War3GetGameUIFn)(uintptr_t)get_game_ui;
    functions->world_frame = (War3WorldFrameFn)(uintptr_t)world_frame;
    functions->get_world_point = (War3GetWorldPointFn)(uintptr_t)get_world_point;
    g_world_point_functions = *functions;
    g_world_point_module = module;
    return ERROR_SUCCESS;
}

static DWORD war3_query_world_point(uint64_t *packed_result) {
    War3WorldPointFunctions functions = {0};
    War3CodeRange text = {0};
    HMODULE module = GetModuleHandleW(NULL);
    void *game_ui = NULL;
    void *world_frame = NULL;
    void **vtable = NULL;
    float point[4] = {0.0f, 0.0f, 0.0f, 0.0f};
    uint32_t x_bits = 0;
    uint32_t y_bits = 0;
    uint8_t ok = 0;
    DWORD error = war3_resolve_world_point_functions(&functions);
    if (error != ERROR_SUCCESS) {
        return error;
    }
    if (!war3_section_range(module, ".text", &text)) {
        return ERROR_BAD_EXE_FORMAT;
    }
    __try {
        game_ui = functions.get_game_ui(1, 0);
        if (!war3_readable_pointer(game_ui)) {
            error = ERROR_NOT_READY;
            __leave;
        }
        world_frame = functions.world_frame(game_ui);
        if (!war3_readable_pointer(world_frame)) {
            error = ERROR_INVALID_ADDRESS;
            __leave;
        }
        vtable = *(void ***)world_frame;
        if (
            !war3_readable_pointer(vtable) ||
            !war3_address_in_range(vtable[0], &text)
        ) {
            error = ERROR_INVALID_DATA;
            __leave;
        }
        ok = functions.get_world_point(world_frame, point, 0);
        if (!ok) {
            error = ERROR_NOT_FOUND;
            __leave;
        }
        if (
            !(point[0] == point[0]) || !(point[1] == point[1]) ||
            point[0] < -1000000.0f || point[0] > 1000000.0f ||
            point[1] < -1000000.0f || point[1] > 1000000.0f
        ) {
            error = ERROR_ARITHMETIC_OVERFLOW;
            __leave;
        }
        memcpy(&x_bits, &point[0], sizeof(x_bits));
        memcpy(&y_bits, &point[1], sizeof(y_bits));
        *packed_result = (uint64_t)x_bits | ((uint64_t)y_bits << 32);
        error = ERROR_SUCCESS;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        error = GetExceptionCode();
    }
    return error;
}

static int war3_is_essential_ability(uint32_t rawcode) {
    static const uint32_t essential[] = {
        0x416d6f76u, /* Amov */
        0x4161746bu, /* Aatk */
        0x41496e76u, /* AInv */
        0x41486572u, /* AHer */
        0x416c6f63u, /* Aloc */
    };
    for (size_t index = 0; index < sizeof(essential) / sizeof(essential[0]); ++index) {
        if (rawcode == essential[index]) {
            return 1;
        }
    }
    return 0;
}

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

static int war3_cast_signature_matches(const NativeCommand *cmd) {
    if (!g_cast_pending.active || !cmd || cmd->op_count != 8u) {
        return 0;
    }
    if (cmd->unit_handle != g_cast_pending.unit_handle) {
        return 0;
    }
    for (uint32_t index = 0; index < 8u; ++index) {
        const NativeOp *left = &cmd->ops[index];
        const NativeOp *right = &g_cast_pending.signature[index];
        if (
            left->kind != right->kind || left->rawcode != right->rawcode ||
            left->handler != right->handler || left->arg0 != right->arg0 ||
            left->arg1 != right->arg1
        ) {
            return 0;
        }
    }
    return 1;
}

static DWORD war3_release_cast_pending(int remove_dummies) {
    DWORD error = ERROR_SUCCESS;
    JassUnitVoidFn remove_unit =
        (JassUnitVoidFn)(uintptr_t)g_cast_pending.remove_unit;
    if (remove_dummies && remove_unit && g_cast_pending.entries) {
        for (uint32_t index = 0; index < g_cast_pending.entry_count; ++index) {
            uint64_t dummy = g_cast_pending.entries[index].dummy;
            if (!dummy) {
                continue;
            }
            __try {
                remove_unit(dummy);
                g_cast_pending.entries[index].dummy = 0;
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                if (!error) {
                    error = GetExceptionCode();
                }
            }
        }
    }
    if (g_cast_pending.entries) {
        HeapFree(GetProcessHeap(), 0, g_cast_pending.entries);
    }
    ZeroMemory(&g_cast_pending, sizeof(g_cast_pending));
    return error;
}

static DWORD war3_finish_cast_pending(NativeCommand *cmd) {
    NativeOp *main_op = &cmd->ops[0];
    JassIssuePointOrderByIdFn issue_point_order =
        (JassIssuePointOrderByIdFn)(uintptr_t)g_cast_pending.issue_point_order;
    JassIssueTargetOrderByIdFn issue_target_order =
        (JassIssueTargetOrderByIdFn)(uintptr_t)g_cast_pending.issue_target_order;
    JassIssueImmediateOrderByIdFn issue_immediate_order =
        (JassIssueImmediateOrderByIdFn)(uintptr_t)g_cast_pending.issue_immediate_order;
    JassUnitApplyTimedLifeFn unit_apply_timed_life =
        (JassUnitApplyTimedLifeFn)(uintptr_t)g_cast_pending.unit_apply_timed_life;
    JassUnitVoidFn remove_unit =
        (JassUnitVoidFn)(uintptr_t)g_cast_pending.remove_unit;
    uint32_t attempts = g_cast_pending.entry_count;
    uint32_t successes = 0;
    DWORD error = ERROR_SUCCESS;
    static const uint32_t btlf_rawcode = 0x42544c46u;

    for (uint32_t index = 0; index < g_cast_pending.entry_count && !error; ++index) {
        War3CastPendingEntry *entry = &g_cast_pending.entries[index];
        uint32_t issued = 0;
        if (g_cast_pending.success_limit && successes >= g_cast_pending.success_limit) {
            break;
        }
        __try {
            if (g_cast_pending.cast_type == 0u) {
                issued = issue_point_order(
                    entry->dummy,
                    (int32_t)g_cast_pending.order_id,
                    &entry->order_x,
                    &entry->order_y
                ) ? 1u : 0u;
            } else if (g_cast_pending.cast_type == 1u) {
                issued = issue_target_order(
                    entry->dummy,
                    (int32_t)g_cast_pending.order_id,
                    entry->target
                ) ? 1u : 0u;
            } else {
                issued = issue_immediate_order(
                    entry->dummy,
                    (int32_t)g_cast_pending.order_id
                ) ? 1u : 0u;
            }
            if (issued) {
                ++successes;
                ((JassUnitAddAbilityFn)(uintptr_t)g_cast_pending.signature[4].handler)(
                    entry->dummy,
                    0x416c6f63u
                );
                unit_apply_timed_life(
                    entry->dummy,
                    btlf_rawcode,
                    &g_cast_pending.duration
                );
                entry->dummy = 0;
            } else {
                remove_unit(entry->dummy);
                entry->dummy = 0;
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            error = GetExceptionCode();
        }
    }
    main_op->result = ((uint64_t)attempts << 32) | successes;
    {
        DWORD cleanup_error = war3_release_cast_pending(1);
        if (!error) {
            error = cleanup_error;
        }
    }
    return error;
}

static DWORD war3_direct_ability_enum(
    NativeCommand *cmd,
    uint32_t index,
    uint64_t **extra_results,
    uint32_t *extra_result_count
) {
    NativeOp *main_op;
    NativeOp *descriptors[5];
    JassGetOwningPlayerFn get_owning_player;
    JassNoArgU64Fn create_group;
    JassGroupEnumUnitsOfPlayerFn enum_units;
    JassFirstOfGroupFn first_of_group;
    JassGroupRemoveUnitFn group_remove_unit;
    JassDestroyGroupFn destroy_group;
    JassPlayerFn player_fn;
    JassGetUnitTypeIdFn get_unit_type_id;
    JassUnitRealQueryFn get_widget_life;
    JassUnitRealQueryFn get_unit_x;
    JassUnitRealQueryFn get_unit_y;
    JassIsPlayerEnemyFn is_player_enemy;
    JassUnitHandleResolveFn resolve_unit;
    uint64_t ability;
    uint64_t vtable = 0;
    uint64_t expected_handler = 0;
    uint64_t source_owner = 0;
    uint64_t group = 0;
    uint32_t flags;
    uint32_t mode;
    uint32_t success_limit;
    uint32_t vtable_offset;
    uint32_t scanned = 0;
    uint32_t attempts = 0;
    uint32_t successes = 0;
    uint64_t *affected_units = NULL;
    uint32_t affected_capacity = 0;
    uint32_t timeout_ms = 0;
    ULONGLONG deadline_tick = 0;
    DWORD error = ERROR_SUCCESS;

    if (
        !cmd || index != 0u || cmd->op_count != 6u || !cmd->unit_handle ||
        !extra_results || !extra_result_count
    ) {
        return ERROR_INVALID_DATA;
    }
    main_op = &cmd->ops[0];
    for (uint32_t descriptor_index = 0; descriptor_index < 5u; ++descriptor_index) {
        descriptors[descriptor_index] = &cmd->ops[descriptor_index + 1u];
        descriptors[descriptor_index]->result = 0;
        descriptors[descriptor_index]->last_error = 0;
        if (descriptors[descriptor_index]->kind != WAR3_NATIVE_OP_JASS_MULTI_ARG) {
            return ERROR_INVALID_DATA;
        }
    }

    ability = main_op->arg0;
    flags = (uint32_t)main_op->arg1;
    mode = flags & 1u;
    success_limit = flags >> 16;
    affected_capacity = success_limit ? success_limit : 100000u;
    vtable_offset = descriptors[4]->rawcode;
    timeout_ms = (uint32_t)descriptors[4]->arg0;
    if (
        !ability || !war3_valid_rawcode(main_op->rawcode) ||
        (mode != 0u && mode != 1u) ||
        (vtable_offset != 0xa70u && vtable_offset != 0xa58u) ||
        timeout_ms < 1000u || timeout_ms > 110000u
    ) {
        return ERROR_INVALID_PARAMETER;
    }
    deadline_tick = GetTickCount64() + timeout_ms;
    if (
        !war3_executable_pointer(main_op->handler) ||
        !war3_executable_pointer(descriptors[0]->handler) ||
        !war3_executable_pointer(descriptors[0]->arg0) ||
        !war3_executable_pointer(descriptors[0]->arg1) ||
        !war3_executable_pointer(descriptors[1]->handler) ||
        !war3_executable_pointer(descriptors[1]->arg0) ||
        !war3_executable_pointer(descriptors[1]->arg1) ||
        !war3_executable_pointer(descriptors[2]->handler) ||
        !war3_executable_pointer(descriptors[2]->arg0) ||
        !war3_executable_pointer(descriptors[2]->arg1) ||
        !war3_executable_pointer(descriptors[3]->handler) ||
        !war3_executable_pointer(descriptors[3]->arg0) ||
        !war3_executable_pointer(descriptors[3]->arg1) ||
        !war3_executable_pointer(descriptors[4]->handler)
    ) {
        return ERROR_INVALID_ADDRESS;
    }

    get_owning_player = (JassGetOwningPlayerFn)(uintptr_t)descriptors[0]->handler;
    create_group = (JassNoArgU64Fn)(uintptr_t)descriptors[0]->arg0;
    enum_units = (JassGroupEnumUnitsOfPlayerFn)(uintptr_t)descriptors[0]->arg1;
    first_of_group = (JassFirstOfGroupFn)(uintptr_t)descriptors[1]->handler;
    group_remove_unit = (JassGroupRemoveUnitFn)(uintptr_t)descriptors[1]->arg0;
    destroy_group = (JassDestroyGroupFn)(uintptr_t)descriptors[1]->arg1;
    player_fn = (JassPlayerFn)(uintptr_t)descriptors[2]->handler;
    get_unit_type_id = (JassGetUnitTypeIdFn)(uintptr_t)descriptors[2]->arg0;
    get_widget_life = (JassUnitRealQueryFn)(uintptr_t)descriptors[2]->arg1;
    get_unit_x = (JassUnitRealQueryFn)(uintptr_t)descriptors[3]->handler;
    get_unit_y = (JassUnitRealQueryFn)(uintptr_t)descriptors[3]->arg0;
    is_player_enemy = (JassIsPlayerEnemyFn)(uintptr_t)descriptors[3]->arg1;
    resolve_unit = (JassUnitHandleResolveFn)(uintptr_t)descriptors[4]->handler;
    if (affected_capacity > 100000u) {
        affected_capacity = 100000u;
    }
    affected_units = (uint64_t *)HeapAlloc(
        GetProcessHeap(),
        0,
        (SIZE_T)affected_capacity * sizeof(uint64_t)
    );
    if (!affected_units) {
        return ERROR_OUTOFMEMORY;
    }

    __try {
        vtable = *(uint64_t *)(uintptr_t)ability;
        expected_handler = *(uint64_t *)(uintptr_t)(vtable + vtable_offset);
        if (
            expected_handler != main_op->handler ||
            *(uint32_t *)(uintptr_t)(ability + 0x70u) != main_op->rawcode ||
            *(uint64_t *)(uintptr_t)(ability + 0x68u) == 0
        ) {
            error = ERROR_INVALID_DATA;
            __leave;
        }
        source_owner = get_owning_player(cmd->unit_handle);
        group = create_group();
        if (!source_owner || !group) {
            error = ERROR_NOT_FOUND;
            __leave;
        }
        for (int32_t player_id = 0; player_id < 24 && !error; ++player_id) {
            if (GetTickCount64() >= deadline_tick) {
                error = ERROR_TIMEOUT;
                break;
            }
            uint64_t player = player_fn(player_id);
            if (!player) {
                continue;
            }
            enum_units(group, player, 0);
            for (;;) {
                uint64_t unit = first_of_group(group);
                uint64_t target_owner;
                float life;
                if (GetTickCount64() >= deadline_tick) {
                    error = ERROR_TIMEOUT;
                    break;
                }
                if (!unit || (success_limit && successes >= success_limit)) {
                    break;
                }
                group_remove_unit(group, unit);
                if (++scanned > 100000u) {
                    error = ERROR_BUFFER_OVERFLOW;
                    break;
                }
                if (!get_unit_type_id(unit)) {
                    continue;
                }
                life = war3_real_from_bits(get_widget_life(unit));
                if (!(life > 0.405f)) {
                    continue;
                }
                target_owner = get_owning_player(unit);
                if (!target_owner || !is_player_enemy(source_owner, target_owner)) {
                    continue;
                }
                ++attempts;
                if (mode == 0u) {
                    uint64_t target_unit = resolve_unit(unit);
                    if (!target_unit) {
                        continue;
                    }
                    ((DirectAbilityTargetFn)(uintptr_t)main_op->handler)(ability, target_unit);
                } else {
                    float x = war3_real_from_bits(get_unit_x(unit));
                    float y = war3_real_from_bits(get_unit_y(unit));
                    if (
                        !(x == x) || !(y == y) ||
                        x < -1000000.0f || x > 1000000.0f ||
                        y < -1000000.0f || y > 1000000.0f
                    ) {
                        continue;
                    }
                    ((DirectAbilityPointFn)(uintptr_t)main_op->handler)(ability, &x, &y);
                }
                affected_units[successes] = unit;
                ++successes;
            }
            if (success_limit && successes >= success_limit) {
                break;
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
        if (!error) {
            error = GetExceptionCode();
        }
    }
    main_op->result = ((uint64_t)attempts << 32) | successes;
    if (successes) {
        size_t old_count = *extra_result_count;
        size_t new_count = old_count + successes;
        uint64_t *resized = *extra_results
            ? (uint64_t *)HeapReAlloc(
                GetProcessHeap(),
                0,
                *extra_results,
                new_count * sizeof(uint64_t)
            )
            : (uint64_t *)HeapAlloc(
                GetProcessHeap(),
                0,
                new_count * sizeof(uint64_t)
            );
        if (!resized) {
            if (!error) {
                error = ERROR_OUTOFMEMORY;
            }
        } else {
            *extra_results = resized;
            memcpy(*extra_results + old_count, affected_units, successes * sizeof(uint64_t));
            *extra_result_count = (uint32_t)new_count;
        }
    }
    HeapFree(GetProcessHeap(), 0, affected_units);
    return error;
}

static DWORD war3_cast_ability(NativeCommand *cmd, uint32_t index) {
    NativeOp *main_op;
    NativeOp *descriptors[7];
    JassGetOwningPlayerFn get_owning_player;
    JassNoArgU64Fn create_group;
    JassGroupEnumUnitsOfPlayerFn enum_units;
    JassFirstOfGroupFn first_of_group;
    JassGroupRemoveUnitFn group_remove_unit;
    JassDestroyGroupFn destroy_group;
    JassPlayerFn player_fn;
    JassGetUnitTypeIdFn get_unit_type_id;
    JassUnitRealQueryFn get_widget_life;
    JassUnitRealQueryFn get_unit_x;
    JassUnitRealQueryFn get_unit_y;
    JassCreateUnitFn create_unit;
    JassUnitAddAbilityFn unit_add_ability;
    JassSetUnitAbilityLevelFn set_unit_ability_level;
    JassSetUnitStateFn set_unit_state;
    JassIssueImmediateOrderByIdFn issue_immediate_order;
    JassUnitApplyTimedLifeFn unit_apply_timed_life;
    JassUnitVoidFn remove_unit;
    JassIsPlayerEnemyFn is_player_enemy;
    JassUnitRemoveAbilityFn unit_remove_ability;
    JassUnitIntVoidFn set_unit_max_mana;
    uint32_t flags;
    uint32_t cast_type;
    uint32_t geometry;
    uint32_t passes;
    uint32_t success_limit;
    uint32_t prepare_limit;
    uint32_t ability_level;
    uint32_t order_id;
    uint32_t dummy_rawcode;
    float mana;
    float duration;
    uint64_t *targets = NULL;
    uint32_t target_count = 0;
    uint32_t target_capacity = 0;
    uint64_t group = 0;
    uint64_t global_owner = 0;
    DWORD error = ERROR_SUCCESS;
    static const uint32_t aloc_rawcode = 0x416c6f63u;
    static const uint32_t btlf_rawcode = 0x42544c46u;
    float safety_duration = 30.0f;

    if (!cmd || index != 0u || cmd->op_count != 8u) {
        return ERROR_INVALID_DATA;
    }
    if (g_cast_pending.active) {
        if (!war3_cast_signature_matches(cmd)) {
            war3_release_cast_pending(1);
            return ERROR_INVALID_DATA;
        }
        if (GetTickCount64() < g_cast_pending.ready_tick) {
            return ERROR_IO_PENDING;
        }
        return war3_finish_cast_pending(cmd);
    }

    main_op = &cmd->ops[0];
    for (uint32_t descriptor_index = 0; descriptor_index < 7u; ++descriptor_index) {
        descriptors[descriptor_index] = &cmd->ops[descriptor_index + 1u];
        descriptors[descriptor_index]->result = 0;
        descriptors[descriptor_index]->last_error = 0;
        if (descriptors[descriptor_index]->kind != WAR3_NATIVE_OP_JASS_MULTI_ARG) {
            descriptors[descriptor_index]->last_error = ERROR_INVALID_DATA;
            return ERROR_INVALID_DATA;
        }
    }

    flags = descriptors[0]->rawcode;
    cast_type = flags & 3u;
    geometry = (flags >> 6) & 3u;
    passes = (flags >> 8) & 0xffu;
    success_limit = flags >> 16;
    prepare_limit = success_limit;
    if (cast_type == 1u && success_limit) {
        uint64_t expanded_limit = (uint64_t)success_limit * 32u;
        prepare_limit = expanded_limit > 100000u ? 100000u : (uint32_t)expanded_limit;
    }
    ability_level = descriptors[3]->rawcode;
    order_id = descriptors[1]->rawcode;
    dummy_rawcode = descriptors[2]->rawcode;
    memcpy(&mana, &descriptors[4]->rawcode, sizeof(mana));
    memcpy(&duration, &descriptors[5]->rawcode, sizeof(duration));
    if (passes == 0u) {
        passes = 1u;
    }
    if (
        !cmd->unit_handle || !war3_valid_rawcode(main_op->rawcode) ||
        !war3_valid_rawcode(dummy_rawcode) || main_op->rawcode == aloc_rawcode ||
        order_id == 0u || order_id > 0x7fffffffu ||
        ability_level == 0u || ability_level > 255u ||
        cast_type == 3u || geometry == 3u ||
        ((flags & (1u << 4)) && cast_type != 2u) ||
        ((flags & (1u << 2)) && (flags & (1u << 4))) ||
        ((flags & (1u << 2)) && (flags & (1u << 3))) ||
        !(mana == mana) || mana <= 0.0f || mana > 100000000.0f ||
        !(duration == duration) || duration < 0.05f || duration > 120.0f
    ) {
        return ERROR_INVALID_PARAMETER;
    }
    if (
        !war3_executable_pointer(main_op->handler) ||
        !war3_executable_pointer(main_op->arg0) ||
        !war3_executable_pointer(main_op->arg1) ||
        !war3_executable_pointer(descriptors[0]->handler) ||
        !war3_executable_pointer(descriptors[0]->arg0) ||
        !war3_executable_pointer(descriptors[0]->arg1) ||
        !war3_executable_pointer(descriptors[1]->handler) ||
        !war3_executable_pointer(descriptors[1]->arg0) ||
        !war3_executable_pointer(descriptors[1]->arg1) ||
        !war3_executable_pointer(descriptors[2]->handler) ||
        !war3_executable_pointer(descriptors[2]->arg0) ||
        !war3_executable_pointer(descriptors[2]->arg1) ||
        !war3_executable_pointer(descriptors[3]->handler) ||
        !war3_executable_pointer(descriptors[3]->arg0) ||
        !war3_executable_pointer(descriptors[3]->arg1) ||
        !war3_executable_pointer(descriptors[4]->handler) ||
        !war3_executable_pointer(descriptors[4]->arg0) ||
        !war3_executable_pointer(descriptors[4]->arg1) ||
        !war3_executable_pointer(descriptors[5]->handler) ||
        !war3_executable_pointer(descriptors[5]->arg0) ||
        !war3_executable_pointer(descriptors[5]->arg1) ||
        !war3_executable_pointer(descriptors[6]->handler) ||
        !war3_executable_pointer(descriptors[6]->arg0)
    ) {
        return ERROR_INVALID_ADDRESS;
    }

    get_owning_player = (JassGetOwningPlayerFn)(uintptr_t)main_op->handler;
    create_group = (JassNoArgU64Fn)(uintptr_t)main_op->arg0;
    enum_units = (JassGroupEnumUnitsOfPlayerFn)(uintptr_t)main_op->arg1;
    first_of_group = (JassFirstOfGroupFn)(uintptr_t)descriptors[0]->handler;
    group_remove_unit = (JassGroupRemoveUnitFn)(uintptr_t)descriptors[0]->arg0;
    destroy_group = (JassDestroyGroupFn)(uintptr_t)descriptors[0]->arg1;
    player_fn = (JassPlayerFn)(uintptr_t)descriptors[1]->handler;
    get_unit_type_id = (JassGetUnitTypeIdFn)(uintptr_t)descriptors[1]->arg0;
    get_widget_life = (JassUnitRealQueryFn)(uintptr_t)descriptors[1]->arg1;
    get_unit_x = (JassUnitRealQueryFn)(uintptr_t)descriptors[2]->handler;
    get_unit_y = (JassUnitRealQueryFn)(uintptr_t)descriptors[2]->arg0;
    create_unit = (JassCreateUnitFn)(uintptr_t)descriptors[2]->arg1;
    unit_add_ability = (JassUnitAddAbilityFn)(uintptr_t)descriptors[3]->handler;
    set_unit_ability_level = (JassSetUnitAbilityLevelFn)(uintptr_t)descriptors[3]->arg0;
    set_unit_state = (JassSetUnitStateFn)(uintptr_t)descriptors[3]->arg1;
    issue_immediate_order = (JassIssueImmediateOrderByIdFn)(uintptr_t)descriptors[4]->arg1;
    unit_apply_timed_life = (JassUnitApplyTimedLifeFn)(uintptr_t)descriptors[5]->handler;
    remove_unit = (JassUnitVoidFn)(uintptr_t)descriptors[5]->arg0;
    is_player_enemy = (JassIsPlayerEnemyFn)(uintptr_t)descriptors[5]->arg1;
    unit_remove_ability = (JassUnitRemoveAbilityFn)(uintptr_t)descriptors[6]->handler;
    set_unit_max_mana = (JassUnitIntVoidFn)(uintptr_t)descriptors[6]->arg0;

    if (flags & (1u << 4)) {
        uint32_t attempts = 0;
        uint32_t successes = 0;
        __try {
            if (
                !get_unit_type_id(cmd->unit_handle) ||
                !(war3_real_from_bits(get_widget_life(cmd->unit_handle)) > 0.405f)
            ) {
                main_op->result = 0;
                return ERROR_SUCCESS;
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            return GetExceptionCode();
        }
        for (uint32_t pass = 0; pass < passes; ++pass) {
            uint32_t newly_added = 0;
            uint32_t issued = 0;
            if (success_limit && successes >= success_limit) {
                break;
            }
            ++attempts;
            __try {
                uint32_t level_result = 0;
                newly_added = unit_add_ability(cmd->unit_handle, main_op->rawcode) ? 1u : 0u;
                __try {
                    level_result = set_unit_ability_level(
                        cmd->unit_handle, main_op->rawcode, (int32_t)ability_level
                    );
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    DWORD exception = GetExceptionCode();
                    if (exception != EXCEPTION_INT_DIVIDE_BY_ZERO) {
                        error = exception;
                    } else {
                        level_result = ability_level;
                    }
                }
                if (!error && level_result) {
                    issued = issue_immediate_order(
                        cmd->unit_handle, (int32_t)order_id
                    ) ? 1u : 0u;
                    if (issued && newly_added && (flags & (1u << 5))) {
                        unit_remove_ability(cmd->unit_handle, main_op->rawcode);
                    }
                }
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                error = GetExceptionCode();
            }
            if (issued) {
                ++successes;
            }
            if (error) {
                break;
            }
        }
        main_op->result = ((uint64_t)attempts << 32) | successes;
        return error;
    }

    __try {
        global_owner = get_owning_player(cmd->unit_handle);
        if (!global_owner) {
            error = ERROR_NOT_FOUND;
            __leave;
        }
        if (flags & (1u << 2)) {
            uint32_t scanned = 0;
            group = create_group();
            if (!group) {
                error = ERROR_NOT_FOUND;
                __leave;
            }
            for (int32_t player_id = 0; player_id < 24 && !error; ++player_id) {
                uint64_t player = player_fn(player_id);
                if (!player) {
                    continue;
                }
                enum_units(group, player, 0);
                for (;;) {
                    uint64_t unit = first_of_group(group);
                    uint64_t *resized;
                    float life;
                    if (!unit) {
                        break;
                    }
                    group_remove_unit(group, unit);
                    if (++scanned > 100000u) {
                        error = ERROR_BUFFER_OVERFLOW;
                        break;
                    }
                    if (!get_unit_type_id(unit)) {
                        continue;
                    }
                    life = war3_real_from_bits(get_widget_life(unit));
                    if (!(life > 0.405f)) {
                        continue;
                    }
                    if (cast_type == 1u) {
                        uint64_t target_owner = get_owning_player(unit);
                        if (!target_owner || !is_player_enemy(global_owner, target_owner)) {
                            continue;
                        }
                    }
                    if (target_count == target_capacity) {
                        uint32_t new_capacity = target_capacity ? target_capacity * 2u : 256u;
                        if (prepare_limit && new_capacity > prepare_limit) {
                            new_capacity = prepare_limit;
                        }
                        if (new_capacity > 100000u) {
                            new_capacity = 100000u;
                        }
                        if (new_capacity <= target_capacity) {
                            error = ERROR_BUFFER_OVERFLOW;
                            break;
                        }
                        resized = targets
                            ? (uint64_t *)HeapReAlloc(
                                GetProcessHeap(), 0, targets,
                                (SIZE_T)new_capacity * sizeof(uint64_t)
                            )
                            : (uint64_t *)HeapAlloc(
                                GetProcessHeap(), 0,
                                (SIZE_T)new_capacity * sizeof(uint64_t)
                            );
                        if (!resized) {
                            error = ERROR_OUTOFMEMORY;
                            break;
                        }
                        targets = resized;
                        target_capacity = new_capacity;
                    }
                    targets[target_count++] = unit;
                    if (prepare_limit && target_count >= prepare_limit) {
                        break;
                    }
                }
                if (prepare_limit && target_count >= prepare_limit) {
                    break;
                }
            }
        } else {
            float life;
            if (get_unit_type_id(cmd->unit_handle)) {
                life = war3_real_from_bits(get_widget_life(cmd->unit_handle));
                if (life > 0.405f) {
                    targets = (uint64_t *)HeapAlloc(
                        GetProcessHeap(), 0, sizeof(uint64_t)
                    );
                    if (!targets) {
                        error = ERROR_OUTOFMEMORY;
                        __leave;
                    }
                    targets[0] = cmd->unit_handle;
                    target_count = 1u;
                    target_capacity = 1u;
                }
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        error = GetExceptionCode();
    }
    __try {
        if (group) {
            destroy_group(group);
            group = 0;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        if (!error) {
            error = GetExceptionCode();
        }
    }
    if (error || target_count == 0u) {
        if (targets) {
            HeapFree(GetProcessHeap(), 0, targets);
        }
        return error;
    }

    {
        uint64_t planned = (uint64_t)target_count * passes;
        if (prepare_limit && planned > prepare_limit) {
            planned = prepare_limit;
        }
        if (planned == 0u || planned > 100000u) {
            HeapFree(GetProcessHeap(), 0, targets);
            return ERROR_BUFFER_OVERFLOW;
        }
        ZeroMemory(&g_cast_pending, sizeof(g_cast_pending));
        g_cast_pending.entries = (War3CastPendingEntry *)HeapAlloc(
            GetProcessHeap(), HEAP_ZERO_MEMORY,
            (SIZE_T)planned * sizeof(War3CastPendingEntry)
        );
        if (!g_cast_pending.entries) {
            HeapFree(GetProcessHeap(), 0, targets);
            return ERROR_OUTOFMEMORY;
        }
        g_cast_pending.active = 1;
        g_cast_pending.unit_handle = cmd->unit_handle;
        memcpy(g_cast_pending.signature, cmd->ops, sizeof(g_cast_pending.signature));
        g_cast_pending.cast_type = cast_type;
        g_cast_pending.order_id = order_id;
        g_cast_pending.success_limit = success_limit;
        g_cast_pending.duration = duration;
        g_cast_pending.ready_tick = GetTickCount64() + 250u;
        g_cast_pending.issue_point_order = descriptors[4]->handler;
        g_cast_pending.issue_target_order = descriptors[4]->arg0;
        g_cast_pending.issue_immediate_order = descriptors[4]->arg1;
        g_cast_pending.unit_apply_timed_life = descriptors[5]->handler;
        g_cast_pending.remove_unit = descriptors[5]->arg0;
    }

    for (uint32_t pass = 0; pass < passes && !error; ++pass) {
        for (uint32_t target_index = 0; target_index < target_count && !error; ++target_index) {
            uint64_t target = targets[target_index];
            uint64_t dummy = 0;
            uint64_t dummy_owner = global_owner;
            float target_x;
            float target_y;
            float dummy_x;
            float order_x;
            float facing = 0.0f;
            uint32_t level_result = 0;
            if (prepare_limit && g_cast_pending.entry_count >= prepare_limit) {
                break;
            }
            __try {
                uint64_t target_owner;
                if (!get_unit_type_id(target)) {
                    continue;
                }
                if (!(war3_real_from_bits(get_widget_life(target)) > 0.405f)) {
                    continue;
                }
                target_owner = get_owning_player(target);
                if (!target_owner) {
                    continue;
                }
                if (!(flags & (1u << 2))) {
                    dummy_owner = target_owner;
                    if (flags & (1u << 3)) {
                        dummy_owner = 0;
                        for (int32_t player_id = 0; player_id < 24; ++player_id) {
                            uint64_t candidate = player_fn(player_id);
                            if (candidate && is_player_enemy(candidate, target_owner)) {
                                dummy_owner = candidate;
                                break;
                            }
                        }
                        if (!dummy_owner) {
                            continue;
                        }
                    }
                }
                target_x = war3_real_from_bits(get_unit_x(target));
                target_y = war3_real_from_bits(get_unit_y(target));
                if (
                    !(target_x == target_x) || !(target_y == target_y) ||
                    target_x < -1000000.0f || target_x > 1000000.0f ||
                    target_y < -1000000.0f || target_y > 1000000.0f
                ) {
                    continue;
                }
                dummy_x = target_x;
                order_x = target_x;
                if (geometry == 1u) {
                    dummy_x -= 128.0f;
                    order_x += 128.0f;
                } else if (geometry == 2u) {
                    dummy_x += 96.0f;
                }
                dummy = create_unit(
                    dummy_owner, dummy_rawcode, &dummy_x, &target_y, &facing
                );
                if (!dummy) {
                    continue;
                }
                if (!unit_add_ability(dummy, main_op->rawcode)) {
                    __leave;
                }
                __try {
                    level_result = set_unit_ability_level(
                        dummy, main_op->rawcode, (int32_t)ability_level
                    );
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    DWORD exception = GetExceptionCode();
                    if (exception != EXCEPTION_INT_DIVIDE_BY_ZERO) {
                        error = exception;
                    } else {
                        level_result = ability_level;
                    }
                }
                if (error || !level_result) {
                    __leave;
                }
                set_unit_max_mana(dummy, (int32_t)mana);
                set_unit_state(dummy, 1, &mana);
                unit_apply_timed_life(dummy, btlf_rawcode, &safety_duration);
                g_cast_pending.entries[g_cast_pending.entry_count].dummy = dummy;
                g_cast_pending.entries[g_cast_pending.entry_count].target = target;
                g_cast_pending.entries[g_cast_pending.entry_count].order_x = order_x;
                g_cast_pending.entries[g_cast_pending.entry_count].order_y = target_y;
                ++g_cast_pending.entry_count;
                dummy = 0;
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                error = GetExceptionCode();
            }
            __try {
                if (dummy) {
                    remove_unit(dummy);
                }
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                if (!error) {
                    error = GetExceptionCode();
                }
            }
        }
    }
    HeapFree(GetProcessHeap(), 0, targets);
    if (error) {
        DWORD cleanup_error = war3_release_cast_pending(1);
        return error ? error : cleanup_error;
    }
    if (g_cast_pending.entry_count == 0u) {
        war3_release_cast_pending(0);
        main_op->result = 0;
        return ERROR_SUCCESS;
    }
    return ERROR_IO_PENDING;
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
    DWORD extra_wrote = 0;
    DWORD status = WAR3_NATIVE_STATUS_FAILED;
    DWORD last_error = 0;
    uint64_t *extra_results = NULL;
    uint32_t extra_result_count = 0;

    ZeroMemory(&cmd, sizeof(cmd));
    command_path(path, MAX_PATH);
    if (!path[0]) {
        return;
    }

    HANDLE file = CreateFileW(
        path,
        GENERIC_READ | GENERIC_WRITE,
        0,
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
        if (op->handler == 0 && op->kind != WAR3_NATIVE_OP_QUERY_WORLD_POINT) {
            op->last_error = ERROR_INVALID_DATA;
            last_error = ERROR_INVALID_DATA;
            goto finish;
        }
        switch (op->kind) {
            case WAR3_NATIVE_OP_INTERNAL_ABILITY_BEGIN:
            case WAR3_NATIVE_OP_INTERNAL_ABILITY_END:
            case WAR3_NATIVE_OP_INTERNAL_ABILITY_REFRESH: {
                InternalAbilityUnitFn fn = (InternalAbilityUnitFn)(uintptr_t)op->handler;
                if (cmd.unit_handle == 0) {
                    op->last_error = ERROR_INVALID_ADDRESS;
                    last_error = ERROR_INVALID_ADDRESS;
                    goto finish;
                }
                __try {
                    fn(cmd.unit_handle);
                    op->result = 1;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_INTERNAL_ABILITY_FIND: {
                InternalAbilityFindFn fn = (InternalAbilityFindFn)(uintptr_t)op->handler;
                if (cmd.unit_handle == 0) {
                    op->last_error = ERROR_INVALID_ADDRESS;
                    last_error = ERROR_INVALID_ADDRESS;
                    goto finish;
                }
                __try {
                    op->result = fn(cmd.unit_handle, op->rawcode, 0, 1, 1, 1, 0);
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_INTERNAL_ABILITY_ADD: {
                InternalAbilityAddFn fn = (InternalAbilityAddFn)(uintptr_t)op->handler;
                if (cmd.unit_handle == 0) {
                    op->last_error = ERROR_INVALID_ADDRESS;
                    last_error = ERROR_INVALID_ADDRESS;
                    goto finish;
                }
                __try {
                    op->result = fn(cmd.unit_handle, op->rawcode, 0, 0, 0, 0);
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_INTERNAL_ABILITY_REMOVE: {
                InternalAbilityRemoveFn fn = (InternalAbilityRemoveFn)(uintptr_t)op->handler;
                InternalAbilityFindFn find_fn = (InternalAbilityFindFn)(uintptr_t)op->arg1;
                DWORD remove_error = ERROR_SUCCESS;
                if (cmd.unit_handle == 0) {
                    op->last_error = ERROR_INVALID_ADDRESS;
                    last_error = ERROR_INVALID_ADDRESS;
                    goto finish;
                }
                if (
                    !op->rawcode || !op->arg0 || !find_fn ||
                    !war3_executable_pointer(op->handler) ||
                    !war3_executable_pointer(op->arg1)
                ) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = op->last_error;
                    goto finish;
                }
                __try {
                    uint64_t current = find_fn(
                        cmd.unit_handle,
                        op->rawcode,
                        0,
                        1,
                        1,
                        1,
                        0
                    );
                    if (current != op->arg0) {
                        remove_error = current ? ERROR_INVALID_DATA : ERROR_NOT_FOUND;
                        __leave;
                    }
                    fn(cmd.unit_handle, op->arg0);
                    op->result = 1;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    remove_error = GetExceptionCode();
                }
                if (remove_error != ERROR_SUCCESS) {
                    op->last_error = remove_error;
                    last_error = remove_error;
                    goto finish;
                }
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
            case WAR3_NATIVE_OP_REMOVE_ITEM_SLOT: {
                InternalUnitItemInSlotFn unit_item_in_slot =
                    (InternalUnitItemInSlotFn)(uintptr_t)op->handler;
                InternalUnitRemoveItemFn remove_item =
                    (InternalUnitRemoveItemFn)(uintptr_t)op->arg0;
                int32_t slot = (int32_t)op->rawcode;
                uint64_t item = 0;
                if (cmd.unit_handle == 0 || remove_item == 0) {
                    op->last_error = ERROR_INVALID_ADDRESS;
                    last_error = ERROR_INVALID_ADDRESS;
                    goto finish;
                }
                __try {
                    item = unit_item_in_slot(cmd.unit_handle, slot);
                    op->result = item;
                    if (item != 0) {
                        uint64_t vtable = 0;
                        InternalItemPreRemoveFn pre_remove = NULL;
                        InternalItemRemoveFn remove_world_item = NULL;
                        op->arg1 = remove_item(cmd.unit_handle, item);
                        vtable = *(uint64_t *)(uintptr_t)item;
                        pre_remove = (InternalItemPreRemoveFn)(uintptr_t)(
                            *(uint64_t *)(uintptr_t)(vtable + 0x108u)
                        );
                        remove_world_item = (InternalItemRemoveFn)(uintptr_t)(
                            *(uint64_t *)(uintptr_t)(vtable + 0x268u)
                        );
                        if (pre_remove) {
                            pre_remove(item);
                        }
                        if (remove_world_item) {
                            remove_world_item(item, g_item_remove_reason);
                        }
                    }
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_ADD_ITEM_TO_SLOT_BY_ID: {
                InternalCreateItemFn create_item = (InternalCreateItemFn)(uintptr_t)op->handler;
                InternalUnitAddItemToSlotFn unit_add_item_to_slot =
                    (InternalUnitAddItemToSlotFn)(uintptr_t)op->arg0;
                int32_t slot = (int32_t)op->arg0;
                float x = 0.0f;
                float y = 0.0f;
                uint64_t item = 0;
                if (cmd.unit_handle == 0 || unit_add_item_to_slot == 0) {
                    op->last_error = ERROR_INVALID_ADDRESS;
                    last_error = ERROR_INVALID_ADDRESS;
                    goto finish;
                }
                __try {
                    slot = (int32_t)op->arg1;
                    item = create_item(op->rawcode, &x, &y, 0);
                    op->result = item;
                    if (item == 0) {
                        op->last_error = ERROR_NOT_FOUND;
                        last_error = ERROR_NOT_FOUND;
                        goto finish;
                    }
                    op->arg1 = unit_add_item_to_slot(cmd.unit_handle, item, slot, 1);
                    if (!op->arg1) {
                        op->last_error = ERROR_CAN_NOT_COMPLETE;
                        last_error = ERROR_CAN_NOT_COMPLETE;
                        goto finish;
                    }
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_GET_ITEM_TYPE_IN_SLOT: {
                InternalUnitItemInSlotFn unit_item_in_slot =
                    (InternalUnitItemInSlotFn)(uintptr_t)op->handler;
                int32_t slot = (int32_t)op->rawcode;
                uint64_t item = 0;
                if (cmd.unit_handle == 0) {
                    op->last_error = ERROR_INVALID_ADDRESS;
                    last_error = ERROR_INVALID_ADDRESS;
                    goto finish;
                }
                __try {
                    item = unit_item_in_slot(cmd.unit_handle, slot);
                    op->arg1 = item;
                    op->result = item ? *(uint32_t *)(uintptr_t)(item + 0x70u) : 0;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
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
            case WAR3_NATIVE_OP_REMOVE_ITEM_HANDLES: {
                uint32_t descriptor_count =
                    op->rawcode > 2u ? (op->rawcode - 2u + 2u) / 3u : 0u;
                last_error = war3_remove_item_handles(&cmd, i);
                if (last_error) {
                    op->last_error = last_error;
                    goto finish;
                }
                i += descriptor_count;
                break;
            }
            case WAR3_NATIVE_OP_REMOVE_ITEM_HANDLES_ARG:
                break;
            case WAR3_NATIVE_OP_JASS_LOCAL_PLAYER_QUERY: {
                JassNoArgU64Fn get_local_player = (JassNoArgU64Fn)(uintptr_t)op->handler;
                JassGetPlayerIdFn get_player_id = (JassGetPlayerIdFn)(uintptr_t)op->arg0;
                JassGetPlayerStateFn get_player_state = (JassGetPlayerStateFn)(uintptr_t)op->arg1;
                uint64_t player = 0;
                if (!get_local_player || !get_player_id || !get_player_state) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = ERROR_INVALID_DATA;
                    goto finish;
                }
                __try {
                    player = get_local_player();
                    if (!player) {
                        op->last_error = ERROR_NOT_FOUND;
                        last_error = ERROR_NOT_FOUND;
                        goto finish;
                    }
                    if (op->rawcode == UINT32_MAX) {
                        op->result = (uint32_t)get_player_id(player);
                    } else {
                        op->result = (uint32_t)get_player_state(player, op->rawcode);
                    }
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_LOCAL_PLAYER_SET: {
                JassNoArgU64Fn get_local_player = (JassNoArgU64Fn)(uintptr_t)op->handler;
                JassSetPlayerStateFn set_player_state = (JassSetPlayerStateFn)(uintptr_t)op->arg0;
                uint64_t player = 0;
                if (!get_local_player || !set_player_state) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = ERROR_INVALID_DATA;
                    goto finish;
                }
                __try {
                    player = get_local_player();
                    if (!player) {
                        op->last_error = ERROR_NOT_FOUND;
                        last_error = ERROR_NOT_FOUND;
                        goto finish;
                    }
                    set_player_state(player, op->rawcode, (int32_t)op->arg1);
                    op->result = (uint32_t)op->arg1;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_UNIT_VOID: {
                JassUnitVoidFn fn = (JassUnitVoidFn)(uintptr_t)op->handler;
                if (!cmd.unit_handle) {
                    op->last_error = ERROR_INVALID_HANDLE;
                    last_error = ERROR_INVALID_HANDLE;
                    goto finish;
                }
                __try {
                    fn(cmd.unit_handle);
                    op->result = 1;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_UNIT_BOOL: {
                JassUnitBoolFn fn = (JassUnitBoolFn)(uintptr_t)op->handler;
                if (!cmd.unit_handle) {
                    op->last_error = ERROR_INVALID_HANDLE;
                    last_error = ERROR_INVALID_HANDLE;
                    goto finish;
                }
                __try {
                    fn(cmd.unit_handle, op->rawcode ? 1u : 0u);
                    op->result = op->rawcode ? 1u : 0u;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_UNIT_INT_BOOL: {
                JassUnitIntBoolFn fn = (JassUnitIntBoolFn)(uintptr_t)op->handler;
                if (!cmd.unit_handle) {
                    op->last_error = ERROR_INVALID_HANDLE;
                    last_error = ERROR_INVALID_HANDLE;
                    goto finish;
                }
                __try {
                    fn(cmd.unit_handle, (int32_t)op->rawcode, op->arg0 ? 1u : 0u);
                    op->result = op->rawcode;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_UNIT_RAWCODE: {
                JassUnitRawcodeFn fn = (JassUnitRawcodeFn)(uintptr_t)op->handler;
                if (!cmd.unit_handle || !op->rawcode) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = ERROR_INVALID_DATA;
                    goto finish;
                }
                __try {
                    op->result = fn(cmd.unit_handle, op->rawcode);
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_UNIT_RAWCODE_LEVEL: {
                JassUnitRawcodeLevelFn fn = (JassUnitRawcodeLevelFn)(uintptr_t)op->handler;
                if (!cmd.unit_handle || !op->rawcode) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = ERROR_INVALID_DATA;
                    goto finish;
                }
                __try {
                    op->result = fn(cmd.unit_handle, op->rawcode, (int32_t)op->arg0);
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    DWORD exception = GetExceptionCode();
                    if (exception != EXCEPTION_INT_DIVIDE_BY_ZERO) {
                        op->last_error = exception;
                        last_error = exception;
                        goto finish;
                    }
                    op->result = (uint32_t)op->arg0;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_UNIT_SCALE: {
                JassUnitScaleFn fn = (JassUnitScaleFn)(uintptr_t)op->handler;
                float scale = 0.0f;
                memcpy(&scale, &op->rawcode, sizeof(scale));
                if (!cmd.unit_handle || !(scale > 0.0f) || scale > 100.0f) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = ERROR_INVALID_PARAMETER;
                    goto finish;
                }
                __try {
                    float x = scale;
                    float y = scale;
                    float z = scale;
                    fn(cmd.unit_handle, &x, &y, &z);
                    op->result = op->rawcode;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_WORLD_BOOL: {
                JassBoolFn fn = (JassBoolFn)(uintptr_t)op->handler;
                __try {
                    fn(op->rawcode ? 1u : 0u);
                    op->result = op->rawcode ? 1u : 0u;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_UNIT_INT_QUERY: {
                JassUnitIntQueryFn fn = (JassUnitIntQueryFn)(uintptr_t)op->handler;
                if (!cmd.unit_handle) {
                    op->last_error = ERROR_INVALID_HANDLE;
                    last_error = ERROR_INVALID_HANDLE;
                    goto finish;
                }
                __try {
                    op->result = (uint32_t)fn(cmd.unit_handle);
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_EXPLODE_UNIT: {
                JassUnitBoolFn set_exploded = (JassUnitBoolFn)(uintptr_t)op->handler;
                JassUnitVoidFn kill_unit = (JassUnitVoidFn)(uintptr_t)op->arg0;
                if (!cmd.unit_handle || !kill_unit) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = ERROR_INVALID_DATA;
                    goto finish;
                }
                __try {
                    set_exploded(cmd.unit_handle, 1u);
                    kill_unit(cmd.unit_handle);
                    op->result = 1;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_TAKE_OWNERSHIP: {
                JassNoArgU64Fn get_local_player = (JassNoArgU64Fn)(uintptr_t)op->handler;
                JassSetUnitOwnerFn set_unit_owner = (JassSetUnitOwnerFn)(uintptr_t)op->arg0;
                uint64_t player = 0;
                if (!cmd.unit_handle || !set_unit_owner) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = ERROR_INVALID_DATA;
                    goto finish;
                }
                __try {
                    player = get_local_player();
                    if (!player) {
                        op->last_error = ERROR_NOT_FOUND;
                        last_error = ERROR_NOT_FOUND;
                        goto finish;
                    }
                    set_unit_owner(cmd.unit_handle, player, 1u);
                    op->result = player;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_CREATE_LOCAL_UNIT: {
                JassNoArgU64Fn get_local_player = (JassNoArgU64Fn)(uintptr_t)op->handler;
                JassCreateUnitFn create_unit = (JassCreateUnitFn)(uintptr_t)op->arg0;
                uint64_t player = 0;
                float coordinates[2] = {0.0f, 0.0f};
                float facing = 0.0f;
                memcpy(coordinates, &op->arg1, sizeof(coordinates));
                if (!op->rawcode || !create_unit) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = ERROR_INVALID_DATA;
                    goto finish;
                }
                __try {
                    player = get_local_player();
                    if (!player) {
                        op->last_error = ERROR_NOT_FOUND;
                        last_error = ERROR_NOT_FOUND;
                        goto finish;
                    }
                    op->result = create_unit(
                        player,
                        op->rawcode,
                        &coordinates[0],
                        &coordinates[1],
                        &facing
                    );
                    if (!op->result) {
                        op->last_error = ERROR_NOT_FOUND;
                        last_error = ERROR_NOT_FOUND;
                        goto finish;
                    }
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_CLEAR_INVENTORY: {
                JassUnitItemInSlotFn unit_item_in_slot =
                    (JassUnitItemInSlotFn)(uintptr_t)op->handler;
                JassRemoveItemFn remove_item = (JassRemoveItemFn)(uintptr_t)op->arg0;
                uint32_t removed = 0;
                if (!cmd.unit_handle || !remove_item) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = ERROR_INVALID_DATA;
                    goto finish;
                }
                __try {
                    for (int32_t slot = 0; slot < 6; ++slot) {
                        uint64_t item = unit_item_in_slot(cmd.unit_handle, slot);
                        if (item) {
                            remove_item(item);
                            ++removed;
                        }
                    }
                    op->result = removed;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_SET_INVENTORY_CHARGES: {
                JassUnitItemInSlotFn unit_item_in_slot =
                    (JassUnitItemInSlotFn)(uintptr_t)op->handler;
                JassSetItemChargesFn set_item_charges =
                    (JassSetItemChargesFn)(uintptr_t)op->arg0;
                uint32_t changed = 0;
                if (!cmd.unit_handle || !unit_item_in_slot || !set_item_charges) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = ERROR_INVALID_DATA;
                    goto finish;
                }
                __try {
                    for (int32_t slot = 0; slot < 6; ++slot) {
                        uint64_t item = unit_item_in_slot(cmd.unit_handle, slot);
                        if (!item) {
                            continue;
                        }
                        set_item_charges(item, (int32_t)op->rawcode);
                        ++changed;
                    }
                    op->result = changed;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_DUPLICATE_INVENTORY: {
                JassUnitItemInSlotFn unit_item_in_slot =
                    (JassUnitItemInSlotFn)(uintptr_t)op->handler;
                JassGetItemTypeIdFn get_item_type_id =
                    (JassGetItemTypeIdFn)(uintptr_t)op->arg0;
                JassUnitRawcodeFn unit_add_item_by_id =
                    (JassUnitRawcodeFn)(uintptr_t)op->arg1;
                uint32_t item_ids[6] = {0};
                uint32_t duplicated = 0;
                if (
                    !cmd.unit_handle || !unit_item_in_slot ||
                    !get_item_type_id || !unit_add_item_by_id
                ) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = ERROR_INVALID_DATA;
                    goto finish;
                }
                __try {
                    for (int32_t slot = 0; slot < 6; ++slot) {
                        uint64_t item = unit_item_in_slot(cmd.unit_handle, slot);
                        if (item) {
                            item_ids[slot] = get_item_type_id(item);
                        }
                    }
                    for (int32_t slot = 0; slot < 6; ++slot) {
                        if (item_ids[slot] && unit_add_item_by_id(cmd.unit_handle, item_ids[slot])) {
                            ++duplicated;
                        }
                    }
                    op->result = duplicated;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_DROP_INVENTORY: {
                JassUnitItemInSlotFn unit_item_in_slot =
                    (JassUnitItemInSlotFn)(uintptr_t)op->handler;
                JassUnitRemoveItemFn unit_remove_item =
                    (JassUnitRemoveItemFn)(uintptr_t)op->arg0;
                uint32_t dropped = 0;
                if (!cmd.unit_handle || !unit_item_in_slot || !unit_remove_item) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = ERROR_INVALID_DATA;
                    goto finish;
                }
                __try {
                    for (int32_t slot = 0; slot < 6; ++slot) {
                        uint64_t item = unit_item_in_slot(cmd.unit_handle, slot);
                        if (!item) {
                            continue;
                        }
                        unit_remove_item(cmd.unit_handle, item);
                        ++dropped;
                    }
                    op->result = dropped;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_REMOVE_ALL_ABILITIES: {
                JassGetUnitAbilityByIndexFn get_ability_by_index =
                    (JassGetUnitAbilityByIndexFn)(uintptr_t)op->handler;
                JassGetAbilityIdFn get_ability_id =
                    (JassGetAbilityIdFn)(uintptr_t)op->arg0;
                JassUnitRawcodeFn remove_ability =
                    (JassUnitRawcodeFn)(uintptr_t)op->arg1;
                uint32_t ability_ids[1024] = {0};
                uint32_t ability_count = 0;
                uint32_t removed = 0;
                if (
                    !cmd.unit_handle || !get_ability_by_index ||
                    !get_ability_id || !remove_ability
                ) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = ERROR_INVALID_DATA;
                    goto finish;
                }
                __try {
                    for (int32_t index = 0; index < 1024; ++index) {
                        uint64_t ability = get_ability_by_index(cmd.unit_handle, index);
                        if (!ability) {
                            break;
                        }
                        uint32_t ability_id = get_ability_id(ability);
                        if (!war3_is_essential_ability(ability_id)) {
                            ability_ids[ability_count++] = ability_id;
                        }
                    }
                    while (ability_count) {
                        uint32_t ability_id = ability_ids[--ability_count];
                        if (ability_id && remove_ability(cmd.unit_handle, ability_id)) {
                            ++removed;
                        }
                    }
                    op->result = removed;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_QUERY_WORLD_POINT: {
                DWORD query_error = war3_query_world_point(&op->result);
                if (query_error != ERROR_SUCCESS) {
                    op->last_error = query_error;
                    last_error = query_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_CREATE_ALL_ITEMS: {
                if (extra_results) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = ERROR_INVALID_DATA;
                    goto finish;
                }
                DWORD create_error = war3_create_all_loaded_items(
                    (const uint8_t *)(uintptr_t)op->handler,
                    (JassCreateItemFn)(uintptr_t)op->arg0,
                    op->rawcode & 0x7fffffffu,
                    (op->rawcode & 0x80000000u) != 0,
                    &op->result,
                    &extra_results,
                    &extra_result_count
                );
                if (create_error != ERROR_SUCCESS) {
                    op->last_error = create_error;
                    last_error = create_error;
                    goto finish;
                }
                op->arg1 = extra_result_count ? extra_results[extra_result_count - 1] : 0;
                break;
            }
            case WAR3_NATIVE_OP_JASS_SET_UNIT_POSITION: {
                JassSetUnitPositionFn set_unit_position =
                    (JassSetUnitPositionFn)(uintptr_t)op->handler;
                uint32_t x_bits = op->rawcode;
                uint32_t y_bits = (uint32_t)op->arg0;
                float x = 0.0f;
                float y = 0.0f;
                memcpy(&x, &x_bits, sizeof(x));
                memcpy(&y, &y_bits, sizeof(y));
                if (
                    !cmd.unit_handle || !set_unit_position ||
                    !(x == x) || !(y == y) ||
                    x < -1000000.0f || x > 1000000.0f ||
                    y < -1000000.0f || y > 1000000.0f
                ) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = ERROR_INVALID_PARAMETER;
                    goto finish;
                }
                __try {
                    set_unit_position(cmd.unit_handle, &x, &y);
                    op->result = (uint64_t)x_bits | ((uint64_t)y_bits << 32);
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_SET_LOCAL_TECH: {
                JassNoArgU64Fn get_local_player = (JassNoArgU64Fn)(uintptr_t)op->handler;
                JassSetPlayerTechFn set_player_tech = (JassSetPlayerTechFn)(uintptr_t)op->arg0;
                uint64_t player = 0;
                if (!op->rawcode || !set_player_tech || (int64_t)op->arg1 < 0) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = ERROR_INVALID_PARAMETER;
                    goto finish;
                }
                __try {
                    player = get_local_player();
                    if (!player) {
                        op->last_error = ERROR_NOT_FOUND;
                        last_error = ERROR_NOT_FOUND;
                        goto finish;
                    }
                    set_player_tech(player, op->rawcode, (int32_t)op->arg1);
                    op->result = (uint32_t)op->arg1;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_SET_LOCAL_XP_RATE: {
                JassNoArgU64Fn get_local_player = (JassNoArgU64Fn)(uintptr_t)op->handler;
                JassSetPlayerRealFn set_player_rate = (JassSetPlayerRealFn)(uintptr_t)op->arg0;
                uint64_t player = 0;
                float rate = 0.0f;
                memcpy(&rate, &op->rawcode, sizeof(rate));
                if (!set_player_rate || !(rate >= 0.0f) || rate > 10000.0f) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = ERROR_INVALID_PARAMETER;
                    goto finish;
                }
                __try {
                    player = get_local_player();
                    if (!player) {
                        op->last_error = ERROR_NOT_FOUND;
                        last_error = ERROR_NOT_FOUND;
                        goto finish;
                    }
                    set_player_rate(player, &rate);
                    op->result = op->rawcode;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_KILL_OWNER_UNITS: {
                NativeOp *iter_op = NULL;
                NativeOp *cleanup_op = NULL;
                JassGetOwningPlayerFn get_owning_player =
                    (JassGetOwningPlayerFn)(uintptr_t)op->handler;
                JassNoArgU64Fn create_group = (JassNoArgU64Fn)(uintptr_t)op->arg0;
                JassGroupEnumUnitsOfPlayerFn enum_units =
                    (JassGroupEnumUnitsOfPlayerFn)(uintptr_t)op->arg1;
                uint64_t player = 0;
                uint64_t group = 0;
                uint32_t killed = 0;
                if (!cmd.unit_handle || i + 2 >= cmd.op_count) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = ERROR_INVALID_DATA;
                    goto finish;
                }
                iter_op = &cmd.ops[i + 1];
                cleanup_op = &cmd.ops[i + 2];
                JassFirstOfGroupFn first_of_group =
                    (JassFirstOfGroupFn)(uintptr_t)iter_op->handler;
                JassGroupRemoveUnitFn group_remove_unit =
                    (JassGroupRemoveUnitFn)(uintptr_t)iter_op->arg0;
                JassUnitVoidFn kill_unit = (JassUnitVoidFn)(uintptr_t)iter_op->arg1;
                JassDestroyGroupFn destroy_group =
                    (JassDestroyGroupFn)(uintptr_t)cleanup_op->handler;
                iter_op->result = 0;
                iter_op->last_error = 0;
                cleanup_op->result = 0;
                cleanup_op->last_error = 0;
                if (
                    !create_group || !enum_units || !first_of_group ||
                    !group_remove_unit || !kill_unit || !destroy_group
                ) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = ERROR_INVALID_DATA;
                    goto finish;
                }
                __try {
                    player = get_owning_player(cmd.unit_handle);
                    group = create_group();
                    if (!player || !group) {
                        op->last_error = ERROR_NOT_FOUND;
                        last_error = ERROR_NOT_FOUND;
                    } else {
                        enum_units(group, player, 0);
                        while (killed < 100000u) {
                            uint64_t unit = first_of_group(group);
                            if (!unit) {
                                break;
                            }
                            group_remove_unit(group, unit);
                            kill_unit(unit);
                            ++killed;
                        }
                    }
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                }
                __try {
                    if (group) {
                        destroy_group(group);
                    }
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    if (!last_error) {
                        op->last_error = GetExceptionCode();
                        last_error = op->last_error;
                    }
                }
                op->result = killed;
                iter_op->result = player;
                cleanup_op->result = group;
                if (last_error) {
                    goto finish;
                }
                i += 2;
                break;
            }
            case WAR3_NATIVE_OP_CAST_ABILITY: {
                op->last_error = ERROR_NOT_SUPPORTED;
                last_error = ERROR_NOT_SUPPORTED;
                goto finish;
            }
            case WAR3_NATIVE_OP_DIRECT_ABILITY_TARGET: {
                uint64_t ability = op->arg0;
                uint64_t target_unit = op->arg1 ? op->arg1 : cmd.unit_handle;
                uint64_t vtable = 0;
                uint64_t expected_handler = 0;
                if (!ability || !target_unit || !op->rawcode) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = op->last_error;
                    goto finish;
                }
                __try {
                    vtable = *(uint64_t *)(uintptr_t)ability;
                    expected_handler = *(uint64_t *)(uintptr_t)(vtable + 0xa70u);
                    if (
                        expected_handler != op->handler ||
                        *(uint32_t *)(uintptr_t)(ability + 0x70u) != op->rawcode ||
                        *(uint64_t *)(uintptr_t)(ability + 0x68u) == 0
                    ) {
                        op->last_error = ERROR_INVALID_DATA;
                        last_error = op->last_error;
                        goto finish;
                    }
                    ((DirectAbilityTargetFn)(uintptr_t)op->handler)(ability, target_unit);
                    op->result = 1;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_DIRECT_ABILITY_IMMEDIATE: {
                uint64_t ability = op->arg0;
                uint64_t vtable = 0;
                uint64_t expected_handler = 0;
                if (!ability || !op->rawcode) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = op->last_error;
                    goto finish;
                }
                __try {
                    vtable = *(uint64_t *)(uintptr_t)ability;
                    expected_handler = *(uint64_t *)(uintptr_t)(vtable + 0x998u);
                    if (
                        expected_handler != op->handler ||
                        *(uint32_t *)(uintptr_t)(ability + 0x70u) != op->rawcode ||
                        *(uint64_t *)(uintptr_t)(ability + 0x68u) == 0
                    ) {
                        op->last_error = ERROR_INVALID_DATA;
                        last_error = op->last_error;
                        goto finish;
                    }
                    ((DirectAbilityImmediateFn)(uintptr_t)op->handler)(ability);
                    op->result = 1;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_DIRECT_ABILITY_POINT: {
                uint64_t ability = op->arg0;
                uint64_t vtable = 0;
                uint64_t expected_handler = 0;
                uint32_t x_bits = (uint32_t)op->arg1;
                uint32_t y_bits = (uint32_t)(op->arg1 >> 32);
                float x = war3_real_from_bits(x_bits);
                float y = war3_real_from_bits(y_bits);
                if (
                    !ability || !op->rawcode || !(x == x) || !(y == y) ||
                    x < -1000000.0f || x > 1000000.0f ||
                    y < -1000000.0f || y > 1000000.0f
                ) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = op->last_error;
                    goto finish;
                }
                __try {
                    vtable = *(uint64_t *)(uintptr_t)ability;
                    expected_handler = *(uint64_t *)(uintptr_t)(vtable + 0xa58u);
                    if (
                        expected_handler != op->handler ||
                        *(uint32_t *)(uintptr_t)(ability + 0x70u) != op->rawcode ||
                        *(uint64_t *)(uintptr_t)(ability + 0x68u) == 0
                    ) {
                        op->last_error = ERROR_INVALID_DATA;
                        last_error = op->last_error;
                        goto finish;
                    }
                    ((DirectAbilityPointFn)(uintptr_t)op->handler)(ability, &x, &y);
                    op->result = 1;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_DIRECT_ABILITY_NOARG_DERIVED: {
                uint64_t ability = op->arg0;
                uint64_t vtable = 0;
                uint64_t expected_handler = 0;
                if (!ability || !op->rawcode) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = op->last_error;
                    goto finish;
                }
                __try {
                    vtable = *(uint64_t *)(uintptr_t)ability;
                    expected_handler = *(uint64_t *)(uintptr_t)(vtable + 0xa78u);
                    if (
                        expected_handler != op->handler ||
                        *(uint32_t *)(uintptr_t)(ability + 0x70u) != op->rawcode ||
                        *(uint64_t *)(uintptr_t)(ability + 0x68u) == 0
                    ) {
                        op->last_error = ERROR_INVALID_DATA;
                        last_error = op->last_error;
                        goto finish;
                    }
                    ((DirectAbilityImmediateFn)(uintptr_t)op->handler)(ability);
                    op->result = 1;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_DIRECT_ABILITY_BUFF: {
                uint64_t ability = op->arg0;
                uint64_t target_unit = cmd.unit_handle;
                uint64_t vtable = 0;
                uint64_t expected_handler = 0;
                War3BuffData buff_data;
                float duration;
                War3BuffDataConstructFn construct_buff =
                    (War3BuffDataConstructFn)(uintptr_t)op->arg1;
                if (
                    !ability || !target_unit || !op->rawcode ||
                    !war3_executable_pointer(op->handler) ||
                    !war3_executable_pointer(op->arg1)
                ) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = op->last_error;
                    goto finish;
                }
                __try {
                    vtable = *(uint64_t *)(uintptr_t)ability;
                    expected_handler = *(uint64_t *)(uintptr_t)(vtable + 0xa00u);
                    if (
                        expected_handler != op->handler ||
                        *(uint32_t *)(uintptr_t)(ability + 0x70u) != op->rawcode ||
                        *(uint64_t *)(uintptr_t)(ability + 0x68u) == 0
                    ) {
                        op->last_error = ERROR_INVALID_DATA;
                        last_error = op->last_error;
                        goto finish;
                    }
                    ZeroMemory(&buff_data, sizeof(buff_data));
                    construct_buff(&buff_data, ability, 0u);
                    duration = buff_data.duration;
                    if (buff_data.hero_duration > duration) {
                        duration = buff_data.hero_duration;
                    }
                    if (!(duration == duration) || duration < 0.05f) {
                        duration = 10.0f;
                    } else if (duration > 3600.0f) {
                        duration = 3600.0f;
                    }
                    ((DirectAbilityBuffFn)(uintptr_t)op->handler)(
                        ability,
                        target_unit,
                        &buff_data,
                        &duration
                    );
                    op->result = 1;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_DIRECT_ABILITY_ENUM: {
                DWORD error = war3_direct_ability_enum(
                    &cmd,
                    i,
                    &extra_results,
                    &extra_result_count
                );
                if (error != ERROR_SUCCESS) {
                    op->last_error = error;
                    last_error = error;
                    goto finish;
                }
                i += 5;
                break;
            }
            case WAR3_NATIVE_OP_JASS_ABILITY_REAL_LEVEL_FIELD_SET: {
                JassAbilityRealLevelFieldSetFn fn =
                    (JassAbilityRealLevelFieldSetFn)(uintptr_t)op->handler;
                float value = war3_real_from_bits((uint32_t)op->arg1);
                if (
                    !cmd.unit_handle || !op->rawcode ||
                    !(value == value) || value < -100000000.0f || value > 100000000.0f
                ) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = op->last_error;
                    goto finish;
                }
                __try {
                    op->result = fn(
                        cmd.unit_handle,
                        op->rawcode,
                        (int32_t)op->arg0,
                        &value
                    );
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_UNIT_RESOLVE: {
                JassUnitHandleResolveFn fn =
                    (JassUnitHandleResolveFn)(uintptr_t)op->handler;
                if (!cmd.unit_handle) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = op->last_error;
                    goto finish;
                }
                __try {
                    op->result = fn(cmd.unit_handle);
                    if (!op->result) {
                        op->last_error = ERROR_NOT_FOUND;
                        last_error = op->last_error;
                        goto finish;
                    }
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_MULTI_ARG:
                break;
            case WAR3_NATIVE_OP_JASS_PEACE_MODE: {
                JassPlayerFn player_fn = (JassPlayerFn)(uintptr_t)op->handler;
                JassSetPlayerAllianceFn set_alliance =
                    (JassSetPlayerAllianceFn)(uintptr_t)op->arg0;
                uint32_t changed = 0;
                if (!set_alliance) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = ERROR_INVALID_DATA;
                    goto finish;
                }
                __try {
                    for (int32_t source_id = 0; source_id < 24; ++source_id) {
                        uint64_t source = player_fn(source_id);
                        if (!source) {
                            continue;
                        }
                        for (int32_t other_id = 0; other_id < 24; ++other_id) {
                            uint64_t other = 0;
                            if (source_id == other_id) {
                                continue;
                            }
                            other = player_fn(other_id);
                            if (!other) {
                                continue;
                            }
                            set_alliance(source, other, 0, op->rawcode ? 1u : 0u);
                            ++changed;
                        }
                    }
                    op->result = changed;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_WORLD_INT_QUERY: {
                JassNoArgIntFn fn = (JassNoArgIntFn)(uintptr_t)op->handler;
                __try {
                    op->result = (uint32_t)fn();
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_FOG_BOOL: {
                JassBoolFn fn = (JassBoolFn)(uintptr_t)op->handler;
                __try {
                    fn(op->rawcode ? 1u : 0u);
                    op->result = op->rawcode ? 1u : 0u;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    DWORD exception = GetExceptionCode();
                    if (exception != EXCEPTION_INT_DIVIDE_BY_ZERO) {
                        op->last_error = exception;
                        last_error = exception;
                        goto finish;
                    }
                    op->result = op->rawcode ? 1u : 0u;
                }
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
    cmd.status = WAR3_NATIVE_STATUS_PENDING;
    cmd.last_error = last_error;
    cmd.reserved = extra_result_count;
    SetFilePointer(file, 0, NULL, FILE_BEGIN);
    WriteFile(file, &cmd, sizeof(cmd), &wrote, NULL);
    if (extra_results && extra_result_count) {
        WriteFile(
            file,
            extra_results,
            extra_result_count * (DWORD)sizeof(uint64_t),
            &extra_wrote,
            NULL
        );
    }
    SetEndOfFile(file);
    FlushFileBuffers(file);
    cmd.status = status;
    SetFilePointer(file, 0, NULL, FILE_BEGIN);
    WriteFile(file, &cmd, sizeof(cmd), &wrote, NULL);
    FlushFileBuffers(file);
    if (extra_results) {
        HeapFree(GetProcessHeap(), 0, extra_results);
    }
    CloseHandle(file);
}

static DWORD war3_remove_item_handles(NativeCommand *cmd, uint32_t index) {
    NativeOp *main_op = &cmd->ops[index];
    JassRemoveItemFn remove_item = (JassRemoveItemFn)(uintptr_t)main_op->handler;
    uint32_t count = main_op->rawcode;
    uint32_t available = 2u + (cmd->op_count - index - 1u) * 3u;
    uint32_t removed = 0;
    if (!remove_item || count == 0 || count > available || count > 47u) {
        return ERROR_INVALID_DATA;
    }
    __try {
        for (uint32_t handle_index = 0; handle_index < count; ++handle_index) {
            uint64_t handle = 0;
            if (handle_index == 0) {
                handle = main_op->arg0;
            } else if (handle_index == 1) {
                handle = main_op->arg1;
            } else {
                uint32_t descriptor_index = (handle_index - 2u) / 3u;
                uint32_t descriptor_slot = (handle_index - 2u) % 3u;
                NativeOp *descriptor = &cmd->ops[index + 1u + descriptor_index];
                if (descriptor->kind != WAR3_NATIVE_OP_REMOVE_ITEM_HANDLES_ARG) {
                    return ERROR_INVALID_DATA;
                }
                if (descriptor_slot == 0) {
                    handle = descriptor->handler;
                } else if (descriptor_slot == 1) {
                    handle = descriptor->arg0;
                } else {
                    handle = descriptor->arg1;
                }
            }
            if (!handle) {
                return ERROR_INVALID_HANDLE;
            }
            remove_item(handle);
            ++removed;
        }
        main_op->result = removed;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return GetExceptionCode();
    }
    return ERROR_SUCCESS;
}

__declspec(dllexport) LRESULT CALLBACK War3HookProc(int code, WPARAM w_param, LPARAM l_param) {
    if (code >= 0) {
        if (InterlockedCompareExchange(&g_processing, 1, 0) == 0) {
            __try {
                run_command();
            } __finally {
                InterlockedExchange(&g_processing, 0);
            }
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
