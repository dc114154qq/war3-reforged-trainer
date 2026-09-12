#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define WAR3_NATIVE_MAGIC 0x33524757u
#define WAR3_NATIVE_VERSION 68u
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
#define WAR3_NATIVE_OP_JASS_UNIT_RESOLVE_ARG 120u
#define WAR3_NATIVE_OP_JASS_ABILITY_FIELD_GET 110u
#define WAR3_NATIVE_OP_JASS_ABILITY_LEVEL_FIELD_GET 111u
#define WAR3_NATIVE_OP_JASS_ABILITY_SCALAR_FIELD_SET 112u
#define WAR3_NATIVE_OP_JASS_ABILITY_REAL_FIELD_SET 113u
#define WAR3_NATIVE_OP_JASS_ABILITY_SCALAR_LEVEL_FIELD_SET 114u
#define WAR3_NATIVE_OP_JASS_ITEM_FIELD_GET 115u
#define WAR3_NATIVE_OP_JASS_ITEM_FIELD_SET 116u
#define WAR3_NATIVE_OP_JASS_HEAL_LOCAL_UNITS 117u
#define WAR3_NATIVE_OP_JASS_CLONE_SELECTED_UNIT 118u
#define WAR3_NATIVE_OP_JASS_SELECTED_UNITS 119u
#define WAR3_NATIVE_OP_JASS_RESET_LOCAL_COOLDOWNS 121u
#define WAR3_NATIVE_OP_PERSISTENT_REGISTER_NATIVE 130u
#define WAR3_NATIVE_OP_PERSISTENT_SELECTED_SNAPSHOT 131u
#define WAR3_NATIVE_OP_MOVE_SELECTED_GROUP_TO_MOUSE 132u
#define WAR3_NATIVE_OP_PERSISTENT_UNIT_SNAPSHOT 133u
#define WAR3_NATIVE_OP_JASS_SET_UNIT_STATE 134u
#define WAR3_NATIVE_OP_JASS_SET_UNIT_INT 135u
#define WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY 136u
#define WAR3_NATIVE_OP_SET_BOUND_ITEM_CHARGES 137u
#define WAR3_NATIVE_OP_BOUND_ITEM_IDENTITY 138u
#define WAR3_NATIVE_OP_BOOTSTRAP_NATIVE_TABLE 139u
#define WAR3_NATIVE_OP_QUERY_NATIVE_TABLE 140u
#define WAR3_NATIVE_OP_BOUND_ABILITY_METADATA 141u
#define WAR3_NATIVE_OP_BOUND_ABILITY_IDENTITY 142u
#define WAR3_NATIVE_OP_BOUND_ABILITY_CONTEXT 143u
#define WAR3_NATIVE_OP_BOUND_INVENTORY_ITEM 144u
#define WAR3_NATIVE_OP_BOUND_ITEM_TYPE 145u
#define WAR3_NATIVE_OP_BOUND_ABILITY_LIST 146u
#define WAR3_NATIVE_OP_BOUND_UNIT_FIELDS 147u
#define WAR3_NATIVE_OP_SET_UNIT_REGEN 148u
#define WAR3_NATIVE_OP_BOUND_INVENTORY 149u
#define WAR3_NATIVE_OP_REPLACE_INVENTORY_ITEM 150u
#define WAR3_NATIVE_OP_REPLACE_INVENTORY_CONTEXT 151u
#define WAR3_NATIVE_OP_WRITE_COMPONENT_FIELDS 152u
#define WAR3_NATIVE_OP_SET_BOUND_HERO_INT 153u
#define WAR3_NATIVE_OP_REPLACE_HERO_SKILL 154u
#define WAR3_NATIVE_OP_IDENTITY_UNIT_SNAPSHOT 155u
#define WAR3_NATIVE_OP_MANAGE_BOUND_ABILITY 156u
#define WAR3_NATIVE_OP_BOUND_DIRECT_ABILITY 157u
#define WAR3_NATIVE_OP_START_ABILITY_EFFECT 158u
#define WAR3_NATIVE_OP_ABILITY_EFFECT_OPTIONS 159u
#define WAR3_NATIVE_OP_FINISH_ABILITY_EFFECT 160u
#define WAR3_NATIVE_OP_ENABLE_BOUND_TOGGLE 161u
#define WAR3_NATIVE_OP_BOUND_WORLD_EFFECT 162u
#define WAR3_NATIVE_OP_SET_BOUND_HERO_BASE 163u
#define WAR3_NATIVE_OP_SET_BOUND_HERO_ATTRIBUTES 164u
#define WAR3_NATIVE_OP_SET_BOUND_HERO_LEVEL 165u
#define WAR3_NATIVE_OP_ADD_BOUND_HERO_SKILL_POINTS 166u
#define WAR3_NATIVE_OP_BOUND_INVENTORY_BATCH 167u
#define WAR3_NATIVE_OP_BOUND_ITEM_CREATE 168u
#define WAR3_NATIVE_OP_BOUND_OWNER_KILL 169u
#define WAR3_BOUND_INVENTORY_QWORDS 49u
#define WAR3_BOUND_UNIT_FIELD_QWORDS (15u + 36u + 121u + 121u + WAR3_BOUND_INVENTORY_QWORDS + 4u)
#define WAR3_CLONE_FLAG_HERO 0x01u
#define WAR3_CLONE_FLAG_INVENTORY 0x02u
#define WAR3_CLONE_FLAG_PRESERVE_OWNER 0x04u
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
    uint8_t notify,
    uint8_t check_mode
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
typedef int32_t (__fastcall *JassGetItemChargesFn)(uint64_t item);
typedef void (__fastcall *JassUnitRemoveItemFn)(uint64_t unit, uint64_t item);
typedef uint64_t (__fastcall *JassGetUnitAbilityByIndexFn)(uint64_t unit, int32_t index);
typedef uint32_t (__fastcall *JassGetAbilityIdFn)(uint64_t ability);
typedef int32_t (__fastcall *JassGetUnitAbilityLevelFn)(uint64_t unit, uint32_t rawcode);
typedef void (__fastcall *JassSetPlayerTechFn)(uint64_t player, uint32_t rawcode, int32_t level);
typedef void (__fastcall *JassSetPlayerRealFn)(uint64_t player, float *value);
typedef uint64_t (__fastcall *JassGetOwningPlayerFn)(uint64_t unit);
typedef void (__fastcall *JassGroupEnumUnitsOfPlayerFn)(uint64_t group, uint64_t player, uint64_t filter);
typedef void (__fastcall *JassGroupRemoveUnitFn)(uint64_t group, uint64_t unit);
typedef uint64_t (__fastcall *JassPlayerFn)(int32_t player_id);
typedef uint32_t (__fastcall *JassGetUnitTypeIdFn)(uint64_t unit);
typedef uint32_t (__fastcall *JassUnitRealQueryFn)(uint64_t unit);
typedef void (__fastcall *JassSetWidgetLifeFn)(uint64_t widget, float *life);
typedef int32_t (__fastcall *JassUnitIntFn)(uint64_t unit);
typedef void (__fastcall *JassUnitSetIntFn)(uint64_t unit, int32_t value);
typedef uint32_t (__fastcall *JassUnitStateQueryFn)(uint64_t unit, int32_t state);
typedef int32_t (__fastcall *JassGetHeroStatFn)(uint64_t unit, uint32_t include_bonuses);
typedef void (__fastcall *JassSetHeroStatFn)(
    uint64_t unit,
    int32_t value,
    uint32_t permanent
);
typedef void (__fastcall *JassSetHeroLevelFn)(
    uint64_t unit,
    int32_t level,
    uint32_t show_eye_candy
);
typedef void (__fastcall *JassSetHeroXPFn)(
    uint64_t unit,
    int32_t xp,
    uint32_t show_eye_candy
);
typedef uint32_t (__fastcall *JassUnitModifySkillPointsFn)(uint64_t unit, int32_t delta);
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
typedef uint64_t (__fastcall *JassAbilityFieldGetFn)(
    uint64_t ability,
    uint32_t field
);
typedef uint64_t (__fastcall *JassAbilityLevelFieldGetFn)(
    uint64_t ability,
    uint32_t field,
    int32_t level
);
typedef uint32_t (__fastcall *JassAbilityScalarFieldSetFn)(
    uint64_t ability,
    uint32_t field,
    uint32_t value
);
typedef uint32_t (__fastcall *JassAbilityRealFieldSetFn)(
    uint64_t ability,
    uint32_t field,
    float *value
);
typedef uint32_t (__fastcall *JassAbilityScalarLevelFieldSetFn)(
    uint64_t ability,
    uint32_t field,
    int32_t level,
    uint32_t value
);
typedef uint64_t (__fastcall *JassItemFieldGetFn)(uint64_t item, uint32_t field);
typedef uint32_t (__fastcall *JassItemScalarFieldSetFn)(
    uint64_t item,
    uint32_t field,
    uint32_t value
);
typedef uint32_t (__fastcall *JassItemRealFieldSetFn)(
    uint64_t item,
    uint32_t field,
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
static volatile LONG g_persistent_ready = 0;

#define WAR3_PERSISTENT_MAX_ABILITIES 48u
typedef struct War3PersistentNative {
    const char *name;
    uint64_t handler;
} War3PersistentNative;

static const char *g_persistent_native_names[] = {
    "UnitAddAbility",
    "UnitRemoveAbility",
    "SetUnitAbilityLevel",
    "BlzGetUnitAbility",
    "CreateGroup",
    "GetLocalPlayer",
    "GroupEnumUnitsSelected",
    "FirstOfGroup",
    "GroupRemoveUnit",
    "DestroyGroup",
    "GetHandleId",
    "GetOwningPlayer",
    "GetPlayerId",
    "GetUnitTypeId",
    "GetUnitState",
    "GetUnitX",
    "GetUnitY",
    "GetUnitMoveSpeed",
    "GetHeroLevel",
    "SetHeroLevel",
    "UnitStripHeroLevel",
    "SuspendHeroXP",
    "IsSuspendedXP",
    "UnitModifySkillPoints",
    "GetHeroXP",
    "GetHeroStr",
    "GetHeroAgi",
    "GetHeroInt",
    "SetHeroInt",
    "SetHeroStr",
    "SetHeroAgi",
    "UnitItemInSlot",
    "UnitInventorySize",
    "CreateItem",
    "UnitAddItemById",
    "RemoveItem",
    "UnitRemoveItem",
    "IsItemOwned",
    "GetItemTypeId",
    "GetItemCharges",
    "BlzGetUnitAbilityByIndex",
    "BlzGetAbilityId",
    "GetUnitAbilityLevel",
    "SetUnitPosition",
    "SetUnitState",
    "SetItemCharges",
    "BlzGetAbilityRealLevelField",
    "BlzSetAbilityRealLevelField",
    "BlzUnitHideAbility",
    "IssueImmediateOrderById",
    "GetUnitCurrentOrder",
    "GroupEnumUnitsOfPlayer",
    "Player",
    "GetWidgetLife",
    "IsPlayerEnemy",
};

static War3PersistentNative g_persistent_natives[
    sizeof(g_persistent_native_names) / sizeof(g_persistent_native_names[0])
] = {0};
static uint64_t g_persistent_unit_resolver = 0;
static uint64_t g_persistent_item_resolver = 0;
static uint64_t g_persistent_agent_resolver = 0;
static uint64_t g_persistent_ability_resolver = 0;
typedef uint64_t (__fastcall *War3AgentResolveFn)(uint32_t slot, uint32_t serial);
static uint64_t war3_persistent_native_handler(const char *name);

#define WAR3_PERSISTENT_SNAPSHOT_MAX_ITEMS 6u
#define WAR3_PERSISTENT_SNAPSHOT_MAX_ABILITIES 48u
#define WAR3_PERSISTENT_SNAPSHOT_ENUM_LIMIT 4096u
#define WAR3_PERSISTENT_SNAPSHOT_QWORDS \
    (32u + (WAR3_PERSISTENT_SNAPSHOT_MAX_ITEMS * 4u) + 1u + \
     (WAR3_PERSISTENT_SNAPSHOT_MAX_ABILITIES * 2u))

typedef struct War3PersistentSnapshot {
    uint64_t handle;
    uint64_t unit_address;
    uint64_t owner;
    uint64_t owner_id;
    uint64_t type_id;
    uint64_t hp_bits;
    uint64_t hp_max_bits;
    uint64_t mp_bits;
    uint64_t mp_max_bits;
    uint64_t x_bits;
    uint64_t y_bits;
    uint64_t move_speed_bits;
    uint64_t hero_level;
    uint64_t hero_xp;
    uint64_t strength;
    uint64_t agility;
    uint64_t intelligence;
    uint64_t item_ids[WAR3_PERSISTENT_SNAPSHOT_MAX_ITEMS];
    uint64_t item_charges[WAR3_PERSISTENT_SNAPSHOT_MAX_ITEMS];
    uint64_t item_handles[WAR3_PERSISTENT_SNAPSHOT_MAX_ITEMS];
    uint64_t item_addresses[WAR3_PERSISTENT_SNAPSHOT_MAX_ITEMS];
    uint64_t ability_count;
    uint64_t ability_ids[WAR3_PERSISTENT_SNAPSHOT_MAX_ABILITIES];
    uint64_t ability_levels[WAR3_PERSISTENT_SNAPSHOT_MAX_ABILITIES];
    uint64_t full_handle;
    uint64_t owner_address;
    uint64_t base_strength;
    uint64_t base_agility;
    uint64_t base_intelligence;
    uint64_t item_full_handles[WAR3_PERSISTENT_SNAPSHOT_MAX_ITEMS];
    uint64_t hp_property;
    uint64_t mp_property;
    uint64_t hp_regen_bits;
    uint64_t mp_regen_bits;
    uint64_t component_mask;
} War3PersistentSnapshot;

/* Protocol 26 keeps the fixed headers and appends pairs beyond the first
   48 abilities, grouped in the same order as the selected-unit headers. */
typedef struct War3SnapshotExtra {
    uint64_t *values;
    uint32_t count;
    uint32_t capacity;
} War3SnapshotExtra;

static DWORD war3_snapshot_append_ability(War3SnapshotExtra *extra, uint64_t id, uint64_t level) {
    const uint32_t limit = 12u * 2u *
        (WAR3_PERSISTENT_SNAPSHOT_ENUM_LIMIT - WAR3_PERSISTENT_SNAPSHOT_MAX_ABILITIES);
    if (extra->count > limit - 2u) {
        return ERROR_MORE_DATA;
    }
    if (extra->count + 2u > extra->capacity) {
        uint32_t capacity = extra->capacity ? extra->capacity * 2u : 64u;
        uint64_t *resized;
        if (capacity > limit) {
            capacity = limit;
        }
        resized = extra->values
            ? (uint64_t *)HeapReAlloc(GetProcessHeap(), 0, extra->values, capacity * sizeof(uint64_t))
            : (uint64_t *)HeapAlloc(GetProcessHeap(), 0, capacity * sizeof(uint64_t));
        if (!resized) {
            return ERROR_OUTOFMEMORY;
        }
        extra->values = resized;
        extra->capacity = capacity;
    }
    extra->values[extra->count++] = id;
    extra->values[extra->count++] = level;
    return ERROR_SUCCESS;
}

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

#include "war3_native_bootstrap.h"

static DWORD war3_persistent_resolve_natives(uint32_t *resolved_count) {
    uint32_t count = 0;
    if (!resolved_count) {
        return ERROR_INVALID_PARAMETER;
    }
    for (size_t index = 0; index < sizeof(g_persistent_natives) / sizeof(g_persistent_natives[0]); ++index) {
        if (!g_persistent_natives[index].name) {
            g_persistent_natives[index].name = g_persistent_native_names[index];
        }
    }
    if (g_persistent_ready) {
        for (size_t index = 0; index < sizeof(g_persistent_natives) / sizeof(g_persistent_natives[0]); ++index) {
            if (g_persistent_natives[index].handler) {
                ++count;
            }
        }
        *resolved_count = count;
        return ERROR_SUCCESS;
    }
    for (size_t index = 0; index < sizeof(g_persistent_natives) / sizeof(g_persistent_natives[0]); ++index) {
        if (g_persistent_natives[index].handler) {
            ++count;
        }
    }
    if (count < 10u) {
        *resolved_count = count;
        return ERROR_NOT_FOUND;
    }
    InterlockedExchange(&g_persistent_ready, 1);
    *resolved_count = count;
    return ERROR_SUCCESS;
}

static uint64_t war3_persistent_native_handler(const char *name) {
    for (size_t index = 0; index < sizeof(g_persistent_natives) / sizeof(g_persistent_natives[0]); ++index) {
        if (strcmp(g_persistent_natives[index].name, name) == 0) {
            return g_persistent_natives[index].handler;
        }
    }
    return 0;
}

static int war3_readable_span(uint64_t address, size_t length);

/* Guard a pinned unit in the same game-thread callback as its mutations.
   The JASS handle and the full engine object handle are deliberately separate. */
static DWORD war3_validate_unit_identity(const NativeCommand *cmd, const NativeOp *guard) {
    uint64_t object, owner;
    if (!cmd->unit_handle || !guard->handler || !guard->arg0 || !guard->arg1) {
        return ERROR_INVALID_HANDLE;
    }
    if (!war3_executable_pointer(g_persistent_unit_resolver) ||
        !war3_executable_pointer(g_persistent_agent_resolver)) {
        return ERROR_PROC_NOT_FOUND;
    }
    __try {
        object = ((JassUnitHandleResolveFn)(uintptr_t)g_persistent_unit_resolver)(cmd->unit_handle);
        owner = ((War3AgentResolveFn)(uintptr_t)g_persistent_agent_resolver)(
            (uint32_t)guard->arg0, (uint32_t)(guard->arg0 >> 32));
        if (!object || !owner || object != guard->handler || owner != guard->arg1 ||
            !war3_readable_span(object,0x20) || !war3_readable_span(owner,0x98) ||
            *(uint64_t *)(uintptr_t)(object + 0x18) != guard->arg0 ||
            *(uint64_t *)(uintptr_t)(owner + 0x18) != 0x2b7733752b61676cULL ||
            *(uint64_t *)(uintptr_t)(owner + 0x20) != guard->arg0 ||
            *(uint64_t *)(uintptr_t)(owner + 0x90) != object) {
            return ERROR_INVALID_HANDLE;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return GetExceptionCode();
    }
    return ERROR_SUCCESS;
}

static int war3_is_internal_ability_op(uint32_t kind) {
    return kind >= WAR3_NATIVE_OP_INTERNAL_ABILITY_BEGIN && kind <= WAR3_NATIVE_OP_INTERNAL_ABILITY_REMOVE;
}
static int war3_is_internal_item_op(uint32_t kind) {
    return kind >= WAR3_NATIVE_OP_REMOVE_ITEM_SLOT && kind <= WAR3_NATIVE_OP_GET_ITEM_TYPE_IN_SLOT;
}

static int war3_readable_span(uint64_t address, size_t length) {
    uint64_t end;
    if (address < 0x10000u || address > 0x00007fffffffffffULL ||
        length > 0x00007fffffffffffULL - address) return 0;
    end = address + length;
    while (address < end) {
        MEMORY_BASIC_INFORMATION region;
        uint64_t next;
        if (VirtualQuery((void *)(uintptr_t)address, &region, sizeof(region)) != sizeof(region) ||
            region.State != MEM_COMMIT || (region.Protect & (PAGE_NOACCESS | PAGE_GUARD))) return 0;
        next = (uint64_t)(uintptr_t)region.BaseAddress + region.RegionSize;
        if (next <= address) return 0;
        address = next;
    }
    return 1;
}

/* Exact 23745 FirstOfGroup body. Only its three rel32 operands vary. Its
   tail call converts a validated unit object to a JASS handle with flag 1,
   just as the selection snapshot does. Never execute scanned byte hits. */
static const uint8_t war3_first_group_code[51]={
    0x48,0x83,0xec,0x28,0xe8,0x07,0x7a,0xdc,0xff,0x48,0x85,0xc0,0x74,0x1e,
    0x48,0x8d,0x48,0x58,0x33,0xd2,0xe8,0x57,0x97,0x13,0x00,0x48,0x85,0xc0,
    0x74,0x0e,0xb2,0x01,0x48,0x8b,0xc8,0x48,0x83,0xc4,0x28,0xe9,0x14,0x08,
    0x02,0x00,0x33,0xc0,0x48,0x83,0xc4,0x28,0xc3
};

static DWORD war3_identity_unit_handle(NativeCommand *cmd,NativeOp *op) {
    typedef uint64_t (__fastcall *ObjectHandleFn)(uint64_t,uint8_t);
    uint64_t first=war3_persistent_native_handler("FirstOfGroup"),owner,target;
    DWORD error=ERROR_SUCCESS;
    if(cmd->op_count!=1 || cmd->unit_handle || !op->handler || !op->arg0 || !op->arg1)
        return ERROR_INVALID_PARAMETER;
    if(!war3_executable_pointer(first) || !war3_executable_pointer(g_persistent_agent_resolver) ||
       !war3_executable_pointer(g_persistent_unit_resolver)) return ERROR_PROC_NOT_FOUND;
    __try {
        if(!war3_readable_span(first,sizeof(war3_first_group_code))) {error=ERROR_INVALID_ADDRESS;__leave;}
        for(unsigned n=0;n<sizeof(war3_first_group_code);++n) {
            if((n>=5 && n<9) || (n>=21 && n<25) || (n>=40 && n<44)) continue;
            if(*(uint8_t *)(uintptr_t)(first+n)!=war3_first_group_code[n]) {error=ERROR_BAD_FORMAT;__leave;}
        }
        if(error) __leave;
        target=first+44+(int64_t)*(int32_t *)(uintptr_t)(first+40);
        if(!war3_executable_pointer(target)) {error=ERROR_INVALID_ADDRESS;__leave;}
        owner=((War3AgentResolveFn)(uintptr_t)g_persistent_agent_resolver)((uint32_t)op->arg0,(uint32_t)(op->arg0>>32));
        if(owner!=op->arg1 || !war3_readable_span(owner,0x98) || !war3_readable_span(op->handler,0x20) ||
           *(uint64_t *)(uintptr_t)(owner+0x18)!=0x2b7733752b61676cULL ||
           *(uint64_t *)(uintptr_t)(owner+0x20)!=op->arg0 ||
           *(uint64_t *)(uintptr_t)(owner+0x90)!=op->handler ||
           *(uint64_t *)(uintptr_t)(op->handler+0x18)!=op->arg0) {error=ERROR_INVALID_HANDLE;__leave;}
        cmd->unit_handle=((ObjectHandleFn)(uintptr_t)target)(op->handler,1);
        error=war3_validate_unit_identity(cmd,op);
    } __except(EXCEPTION_EXECUTE_HANDLER) {error=GetExceptionCode();}
    return error;
}

typedef struct War3RegenProperties {
    uint64_t address[2];
    uint64_t identity[2];
    uint32_t bits[2];
} War3RegenProperties;

/* Traverse only this owner's bounded lists. Reject ambiguous or recycled
   properties instead of guessing a list size or reusing a cached address. */
static DWORD war3_regen_properties(uint64_t owner, War3RegenProperties *out) {
    uint64_t lists[2], lengths[2], entries[2][128] = {{0}};
    War3AgentResolveFn resolve = (War3AgentResolveFn)(uintptr_t)g_persistent_agent_resolver;
    if (!war3_readable_span(owner, 0xc0) || !war3_executable_pointer(g_persistent_agent_resolver))
        return ERROR_INVALID_ADDRESS;
    ZeroMemory(out, sizeof(*out));
    for (unsigned list = 0; list < 2; ++list) {
        lists[list] = *(uint64_t *)(uintptr_t)(owner + 0xa0 + list*0x10);
        lengths[list] = *(uint64_t *)(uintptr_t)(owner + 0xa8 + list*0x10);
        if (!lengths[list]) continue;
        if (lengths[list] > 0x400 || (lengths[list] & 7u) ||
            !war3_readable_span(lists[list], (size_t)lengths[list])) return ERROR_INVALID_DATA;
        memcpy(entries[list], (void *)(uintptr_t)lists[list], (size_t)lengths[list]);
        for (unsigned n = 0; n < lengths[list]/8; ++n) {
            uint64_t prop = entries[list][n], kind, full;
            unsigned index;
            if (!prop) continue;
            if (!war3_readable_span(prop, 0x80)) return ERROR_INVALID_ADDRESS;
            if (*(uint64_t *)(uintptr_t)(prop + 0x18) != 0x6072656c5e70726fULL) continue;
            kind = *(uint64_t *)(uintptr_t)(prop + 0x78) >> 32;
            if (kind != 1 && kind != 2) continue;
            index = (unsigned)kind - 1;
            if (!war3_readable_span(prop, 0xd8)) return ERROR_INVALID_ADDRESS;
            full = *(uint64_t *)(uintptr_t)(prop + 0x20);
            if (!full || *(uint64_t *)(uintptr_t)(prop + 0x50) != owner ||
                resolve((uint32_t)full, (uint32_t)(full >> 32)) != prop ||
                (out->address[index] && out->address[index] != prop)) return ERROR_INVALID_HANDLE;
            out->address[index] = prop; out->identity[index] = full;
            out->bits[index] = *(uint32_t *)(uintptr_t)(prop + 0xd4);
        }
    }
    for (unsigned list = 0; list < 2; ++list) {
        if (*(uint64_t *)(uintptr_t)(owner + 0xa0 + list*0x10) != lists[list] ||
            *(uint64_t *)(uintptr_t)(owner + 0xa8 + list*0x10) != lengths[list] ||
            (lengths[list] && memcmp(entries[list], (void *)(uintptr_t)lists[list], (size_t)lengths[list])))
            return ERROR_INVALID_HANDLE;
    }
    for (unsigned k = 0; k < 2; ++k) {
        uint64_t prop = out->address[k], full = out->identity[k];
        if (prop && (resolve((uint32_t)full, (uint32_t)(full >> 32)) != prop ||
            *(uint64_t *)(uintptr_t)(prop + 0x20) != full ||
            *(uint64_t *)(uintptr_t)(prop + 0x50) != owner ||
            *(uint64_t *)(uintptr_t)(prop + 0x18) != 0x6072656c5e70726fULL ||
            (*(uint64_t *)(uintptr_t)(prop + 0x78) >> 32) != k+1)) return ERROR_INVALID_HANDLE;
    }
    return ERROR_SUCCESS;
}

/* 2.0.4.23745 component fields, copied once on the game thread. The unit's
   fixed component slots are cross-checked against the engine object table;
   no wrapper search, address-range vtable guess, or cached membership. */
/* A compact component identity read for a whole selection snapshot. No field
   buffers, inventory calls, heap walks or additional IPC requests are needed. */
static DWORD war3_snapshot_component_mask(uint64_t handle,uint64_t unit,uint64_t owner,
                                           uint64_t full,uint64_t *mask) {
    static const uint32_t offsets[4]={0x5a0,0x5a8,0x5b0,0x5c0};
    static const uint64_t tags[4]={0x41496e762b61676cULL,0x414865722b61676cULL,
                                  0x416d6f762b61676cULL,0x4161746b2b61676cULL};
    uint64_t data[4]={0},wrappers[4]={0},ids[4]={0},result=0;
    NativeCommand guard={0};DWORD error;
    guard.unit_handle=handle;guard.ops[0].handler=unit;guard.ops[0].arg0=full;guard.ops[0].arg1=owner;
    error=war3_validate_unit_identity(&guard,&guard.ops[0]);if(error) return error;
    if(!war3_readable_span(unit,0x5c8)) return ERROR_INVALID_ADDRESS;
    for(unsigned k=0;k<4;++k) {
        data[k]=*(uint64_t *)(uintptr_t)(unit+offsets[k]);
        if(!data[k]) continue;
        if(!war3_readable_span(data[k],0x70)) return ERROR_INVALID_ADDRESS;
        ids[k]=*(uint64_t *)(uintptr_t)(data[k]+0x18);
        if(!ids[k]) return ERROR_INVALID_HANDLE;
        wrappers[k]=((War3AgentResolveFn)(uintptr_t)g_persistent_agent_resolver)((uint32_t)ids[k],(uint32_t)(ids[k]>>32));
        result|=1u<<k;
    }
    error=war3_validate_unit_identity(&guard,&guard.ops[0]);if(error) return error;
    /* This final pass runs without callbacks, including checks for components
       added to a previously empty slot while resolving a different component. */
    if(!war3_readable_span(unit,0x5c8)) return ERROR_INVALID_ADDRESS;
    for(unsigned k=0;k<4;++k) {
        if(*(uint64_t *)(uintptr_t)(unit+offsets[k])!=data[k]) return ERROR_INVALID_HANDLE;
        if(!data[k]) continue;
        if(!war3_readable_span(data[k],0x70) || !war3_readable_span(wrappers[k],0x98)) return ERROR_INVALID_ADDRESS;
        if(*(uint64_t *)(uintptr_t)(data[k]+0x18)!=ids[k] ||
           *(uint64_t *)(uintptr_t)(data[k]+0x68)!=unit ||
           *(uint64_t *)(uintptr_t)(wrappers[k]+0x18)!=tags[k] ||
           *(uint64_t *)(uintptr_t)(wrappers[k]+0x20)!=ids[k] ||
           *(uint64_t *)(uintptr_t)(wrappers[k]+0x50)!=owner ||
           *(uint64_t *)(uintptr_t)(wrappers[k]+0x90)!=data[k]) return ERROR_INVALID_HANDLE;
    }
    *mask=result;return ERROR_SUCCESS;
}

static DWORD war3_bound_inventory(const NativeCommand *cmd, uint64_t *values);
static DWORD war3_bound_unit_fields(const NativeCommand *cmd, uint64_t *values) {
    static const uint32_t offsets[4] = {0x5a0, 0x5a8, 0x5b0, 0x5c0};
    static const uint64_t tags[4] = {0x41496e762b61676cULL, 0x414865722b61676cULL,
                                    0x416d6f762b61676cULL, 0x4161746b2b61676cULL};
    uint64_t data[4] = {0}, wrappers[4] = {0}, identities[4] = {0};
    uint64_t unit = cmd->ops[0].handler, owner = cmd->ops[0].arg1;
    War3AgentResolveFn resolve = (War3AgentResolveFn)(uintptr_t)g_persistent_agent_resolver;
    DWORD error = war3_validate_unit_identity(cmd, &cmd->ops[0]);
    if (error) return error;
    if (!war3_readable_span(unit, 0x5c8)) return ERROR_INVALID_ADDRESS;
    __try {
        values[0] = unit; values[1] = cmd->ops[0].arg0; values[2] = owner;
        memcpy(values + 4, (void *)(uintptr_t)(unit + 0x2e8), 16);
        for (unsigned k = 0; k < 4; ++k) {
            data[k] = *(uint64_t *)(uintptr_t)(unit + offsets[k]);
            if (!data[k]) continue;
            if (!war3_readable_span(data[k], k == 3 ? 0x3c8 : k == 1 ? 0x220 : 0x70)) {
                error = ERROR_INVALID_ADDRESS; __leave;
            }
            identities[k] = *(uint64_t *)(uintptr_t)(data[k] + 0x18);
            wrappers[k] = resolve((uint32_t)identities[k], (uint32_t)(identities[k] >> 32));
            if (!war3_readable_span(wrappers[k], 0x98)) { error = ERROR_INVALID_ADDRESS; __leave; }
            if (!identities[k] || !wrappers[k] ||
                *(uint64_t *)(uintptr_t)(data[k] + 0x68) != unit ||
                *(uint64_t *)(uintptr_t)(wrappers[k] + 0x18) != tags[k] ||
                *(uint64_t *)(uintptr_t)(wrappers[k] + 0x20) != identities[k] ||
                *(uint64_t *)(uintptr_t)(wrappers[k] + 0x50) != owner ||
                *(uint64_t *)(uintptr_t)(wrappers[k] + 0x90) != data[k]) {
                error = ERROR_INVALID_HANDLE; __leave;
            }
            values[3] |= 1u << k;
            values[6 + k*2] = data[k]; values[7 + k*2] = wrappers[k];
            values[342+k] = identities[k];
        }
        if (data[1]) memcpy(values + 15, (void *)(uintptr_t)(data[1] + 0x100), 0x120);
        if (data[3]) {
            uint64_t second = data[3] + 0x638;
            uint64_t second_vtable = war3_readable_span(second, 12)
                ? *(uint64_t *)(uintptr_t)second : 0;
            memcpy(values + 51, (void *)(uintptr_t)data[3], 0x3c8);
            if (war3_readable_span(second_vtable, 8) &&
                war3_executable_pointer(*(uint64_t *)(uintptr_t)second_vtable) &&
                *(uint32_t *)(uintptr_t)(second + 8) == *(uint32_t *)(uintptr_t)(data[3] + 8)) {
                if (!war3_readable_span(second, 0x3c8)) { error = ERROR_INVALID_ADDRESS; __leave; }
                values[14] = 1;
                memcpy(values + 172, (void *)(uintptr_t)second, 0x3c8);
            }
        }
        error = war3_validate_unit_identity(cmd, &cmd->ops[0]);
        if (error) __leave;
        for (unsigned k = 0; k < 4; ++k) {
            if (*(uint64_t *)(uintptr_t)(unit + offsets[k]) != data[k] || (data[k] && (
                resolve((uint32_t)identities[k], (uint32_t)(identities[k] >> 32)) != wrappers[k] ||
                *(uint64_t *)(uintptr_t)(data[k] + 0x18) != identities[k] ||
                *(uint64_t *)(uintptr_t)(data[k] + 0x68) != unit ||
                *(uint64_t *)(uintptr_t)(wrappers[k] + 0x18) != tags[k] ||
                *(uint64_t *)(uintptr_t)(wrappers[k] + 0x20) != identities[k] ||
                *(uint64_t *)(uintptr_t)(wrappers[k] + 0x50) != owner ||
                *(uint64_t *)(uintptr_t)(wrappers[k] + 0x90) != data[k]))) {
                error = ERROR_INVALID_HANDLE; __leave;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { error = ERROR_INVALID_ADDRESS; }
    return error ? error : war3_bound_inventory(cmd, values + 293);
}

/* Return one ability's metadata while its owning unit is pinned by op 136.
   Object-table cross-links replace the old wrapper-neighborhood search. */
static DWORD war3_bound_ability_metadata(const NativeCommand *cmd, const NativeOp *op, uint64_t *values) {
    JassUnitRawcodeFn lookup=(JassUnitRawcodeFn)(uintptr_t)op->handler;
    JassUnitIntQueryFn get_id=(JassUnitIntQueryFn)(uintptr_t)op->arg0;
    JassGetUnitAbilityLevelFn get_level=(JassGetUnitAbilityLevelFn)(uintptr_t)war3_persistent_native_handler("GetUnitAbilityLevel");
    JassUnitHandleResolveFn resolve=(JassUnitHandleResolveFn)(uintptr_t)g_persistent_ability_resolver;
    DWORD error;
    uint64_t handle,data,wrapper,full,tag;uint32_t actual_id,level;
    uint32_t argument=op->arg1?(uint32_t)(op->arg1-1u):op->rawcode;
    if(cmd->ops[0].kind!=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY || !op->rawcode ||
       op->arg1>WAR3_PERSISTENT_SNAPSHOT_ENUM_LIMIT || !war3_executable_pointer(op->handler) ||
       !war3_executable_pointer(op->arg0) || !war3_executable_pointer((uint64_t)(uintptr_t)get_level) ||
       !war3_executable_pointer(g_persistent_ability_resolver)) return ERROR_INVALID_PARAMETER;
#define ABILITY_UNIT_CHECK() do { error=war3_validate_unit_identity(cmd,&cmd->ops[0]);if(error) return error; } while(0)
    __try {
        ABILITY_UNIT_CHECK();
        handle=lookup(cmd->unit_handle,argument);ABILITY_UNIT_CHECK();
        if(!handle) return ERROR_NOT_FOUND;
        data=resolve(handle);ABILITY_UNIT_CHECK();
        if(!war3_readable_span(data,0xa8)) return ERROR_INVALID_ADDRESS;
        full=*(uint64_t *)(uintptr_t)(data+0x18);
        if(!full) return ERROR_INVALID_HANDLE;
        wrapper=((War3AgentResolveFn)(uintptr_t)g_persistent_agent_resolver)((uint32_t)full,(uint32_t)(full>>32));
        ABILITY_UNIT_CHECK();
        actual_id=(uint32_t)get_id(handle);ABILITY_UNIT_CHECK();
        if(actual_id!=op->rawcode) return ERROR_INVALID_DATA;
        level=(uint32_t)get_level(cmd->unit_handle,op->rawcode);ABILITY_UNIT_CHECK();
        if(lookup(cmd->unit_handle,argument)!=handle) return ERROR_INVALID_HANDLE;
        ABILITY_UNIT_CHECK();
        if(resolve(handle)!=data) return ERROR_INVALID_HANDLE;
        ABILITY_UNIT_CHECK();
        if(!war3_readable_span(data,0xa8) || !war3_readable_span(wrapper,0x98)) return ERROR_INVALID_ADDRESS;
        if(*(uint64_t *)(uintptr_t)(data+0x18)!=full ||
           *(uint64_t *)(uintptr_t)(wrapper+0x20)!=full ||
           *(uint64_t *)(uintptr_t)(wrapper+0x50)!=cmd->ops[0].arg1 ||
           *(uint64_t *)(uintptr_t)(wrapper+0x90)!=data ||
           *(uint64_t *)(uintptr_t)(data+0x68)!=cmd->ops[0].handler ||
           *(uint32_t *)(uintptr_t)(data+0x70)!=op->rawcode ||
           *(uint32_t *)(uintptr_t)(data+0x78)!=op->rawcode) return ERROR_INVALID_HANDLE;
        tag=*(uint64_t *)(uintptr_t)(wrapper+0x18);
        if(!(tag>>32)) return ERROR_INVALID_DATA;
        values[0]=handle;values[1]=data;values[2]=wrapper;values[3]=full;values[4]=tag;
        values[5]=*(uint64_t *)(uintptr_t)wrapper;values[6]=*(uint64_t *)(uintptr_t)data;
        values[7]=op->rawcode;values[8]=level;values[9]=*(uint64_t *)(uintptr_t)(data+0xa0);
    } __except(EXCEPTION_EXECUTE_HANDLER) { return GetExceptionCode(); }
#undef ABILITY_UNIT_CHECK
    return ERROR_SUCCESS;
}

#include "war3_native_ability_actions.h"

/* No engine callbacks between this check and a direct call or cleanup. */
static DWORD war3_direct_identity_memory(const NativeCommand *cmd,uint32_t id,const uint64_t *v) {
    uint64_t unit=cmd->ops[0].handler,owner=cmd->ops[0].arg1,data=v[1],wrapper=v[2];
    if(!v[0] || !v[3] || !war3_readable_span(unit,0x20) || !war3_readable_span(owner,0x98) ||
       !war3_readable_span(data,0xa8) || !war3_readable_span(wrapper,0x98)) return ERROR_INVALID_ADDRESS;
    if(*(uint64_t *)(uintptr_t)(unit+0x18)!=cmd->ops[0].arg0 ||
       *(uint64_t *)(uintptr_t)(owner+0x18)!=0x2b7733752b61676cULL ||
       *(uint64_t *)(uintptr_t)(owner+0x20)!=cmd->ops[0].arg0 ||
       *(uint64_t *)(uintptr_t)(owner+0x90)!=unit ||
       *(uint64_t *)(uintptr_t)(data+0x18)!=v[3] ||
       *(uint64_t *)(uintptr_t)(data+0x68)!=unit ||
       *(uint32_t *)(uintptr_t)(data+0x70)!=id || *(uint32_t *)(uintptr_t)(data+0x78)!=id ||
       *(uint64_t *)(uintptr_t)(wrapper+0x18)!=v[4] ||
       *(uint64_t *)(uintptr_t)(wrapper+0x20)!=v[3] ||
       *(uint64_t *)(uintptr_t)(wrapper+0x50)!=owner ||
       *(uint64_t *)(uintptr_t)(wrapper+0x90)!=data) return ERROR_INVALID_HANDLE;
    return ERROR_SUCCESS;
}

#include "war3_native_buff.h"

/* Execute one direct ability effect while the unit and ability generations
   remain pinned inside the game-thread callback. The controller supplies no
   ability object or callback address. */
static DWORD war3_bound_direct_ability(NativeCommand *cmd, NativeOp *op) {
    JassUnitRawcodeFn lookup=(JassUnitRawcodeFn)(uintptr_t)war3_persistent_native_handler("BlzGetUnitAbility");
    JassGetAbilityIdFn get_id=(JassGetAbilityIdFn)(uintptr_t)war3_persistent_native_handler("BlzGetAbilityId");
    JassUnitAddAbilityFn add=(JassUnitAddAbilityFn)(uintptr_t)war3_persistent_native_handler("UnitAddAbility");
    JassUnitRemoveAbilityFn remove=(JassUnitRemoveAbilityFn)(uintptr_t)war3_persistent_native_handler("UnitRemoveAbility");
    uint64_t values[10],after[10],ability,vtable,callback;
    uint32_t offset,added=0,captured=0,creation_attempted=0,creation_returned=0;
    DWORD error=ERROR_SUCCESS,cleanup=ERROR_SUCCESS;
    float x=war3_real_from_bits((uint32_t)op->arg0),y=war3_real_from_bits((uint32_t)op->arg1);
    if(cmd->op_count!=2 || cmd->ops[0].kind!=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY ||
       !op->rawcode || op->handler<1 || op->handler>5 ||
       !war3_executable_pointer((uint64_t)(uintptr_t)lookup) ||
       !war3_executable_pointer((uint64_t)(uintptr_t)get_id) ||
       !war3_executable_pointer((uint64_t)(uintptr_t)add) ||
       !war3_executable_pointer((uint64_t)(uintptr_t)remove)) return ERROR_INVALID_PARAMETER;
    if(op->handler==3) {
        if(op->arg0>UINT32_MAX || op->arg1>UINT32_MAX || !(x==x) || !(y==y) ||
           x < -1000000.0f || x > 1000000.0f || y < -1000000.0f || y > 1000000.0f)
            return ERROR_INVALID_PARAMETER;
    } else if(op->arg0 || op->arg1) return ERROR_INVALID_PARAMETER;
    offset=op->handler==1?0xa70u:op->handler==2?0x998u:op->handler==3?0xa58u:op->handler==4?0xa78u:0xa00u;
    op->result=0;op->reserved=0;
    ZeroMemory(values,sizeof(values));ZeroMemory(after,sizeof(after));
    __try {
        error=war3_validate_unit_identity(cmd,&cmd->ops[0]);if(error) __leave;
        error=war3_action_ability_state(cmd,op->rawcode,values);if(error) __leave;
        if(!values[0]) {
            creation_attempted=1;
            added=add(cmd->unit_handle,op->rawcode);
            creation_returned=1;
            error=war3_action_ability_state(cmd,op->rawcode,values);if(error) __leave;
            if(!added || !values[0]) {error=ERROR_INVALID_DATA;__leave;}
        }
        captured=1;
        error=war3_validate_unit_identity(cmd,&cmd->ops[0]);if(error) __leave;
        error=war3_direct_identity_memory(cmd,op->rawcode,values);if(error) __leave;
        ability=values[1];
        if(!war3_readable_span(ability,0xa8)) {error=ERROR_INVALID_ADDRESS;__leave;}
        vtable=*(uint64_t *)(uintptr_t)ability;
        if(!war3_readable_span(vtable,(size_t)offset+8u)) {error=ERROR_INVALID_ADDRESS;__leave;}
        callback=*(uint64_t *)(uintptr_t)(vtable+offset);
        if(!war3_executable_pointer(callback)) {error=ERROR_INVALID_ADDRESS;__leave;}
        if(op->handler==5) {
            uint64_t constructor=0;
            error=war3_buff_constructor((uint64_t)(uintptr_t)g_bootstrap_module,
                                       *(uint64_t *)(uintptr_t)(vtable+0x998),&constructor);
            if(error) __leave;
            error=war3_invoke_bound_buff(cmd,op->rawcode,values,constructor,callback);
            if(error) __leave;
        } else if(op->handler==1) {
            ((DirectAbilityTargetFn)(uintptr_t)callback)(ability,cmd->ops[0].handler);
        } else if(op->handler==3) {
            ((DirectAbilityPointFn)(uintptr_t)callback)(ability,&x,&y);
        } else ((DirectAbilityImmediateFn)(uintptr_t)callback)(ability);
        error=war3_validate_unit_identity(cmd,&cmd->ops[0]);if(error) __leave;
        error=war3_action_ability_state(cmd,op->rawcode,after);if(error) __leave;
        if(!war3_action_same_ability(values,after)) {error=ERROR_INVALID_HANDLE;__leave;}
        op->result=1;
    } __except(EXCEPTION_EXECUTE_HANDLER) {error=GetExceptionCode();}
    if(added && captured) {
        __try {
            cleanup=war3_validate_unit_identity(cmd,&cmd->ops[0]);
            if(!cleanup) cleanup=war3_action_ability_state(cmd,op->rawcode,after);
            if(!cleanup && after[0]) {
                if(!war3_action_same_ability(values,after) || after[8]!=values[8]) cleanup=ERROR_INVALID_HANDLE;
                if(!cleanup) cleanup=war3_direct_identity_memory(cmd,op->rawcode,values);
                if(!cleanup && !remove(cmd->unit_handle,op->rawcode)) cleanup=ERROR_INVALID_DATA;
                if(!cleanup) { cleanup=war3_action_ability_state(cmd,op->rawcode,after); if(!cleanup && after[0]) cleanup=ERROR_INVALID_DATA; }
            }
        } __except(EXCEPTION_EXECUTE_HANDLER) {cleanup=GetExceptionCode();}
    }
    if(creation_attempted && (!creation_returned || (added && !captured) || (!added && values[0])))
        cleanup=ERROR_INVALID_DATA; /* Creation ownership could not be proven. */
    op->reserved=cleanup;
    return error ? error : cleanup;
}

#include "war3_native_effect_lifecycle.h"
#include "war3_native_toggle.h"
#include "war3_native_world_effect.h"
#include "war3_native_owner_kill.h"

/* Six slots plus the engine's usable slot count. Slot membership, item
   generation and object-table backlinks replace external inventory records. */
static DWORD war3_bound_inventory(const NativeCommand *cmd, uint64_t *values) {
    JassUnitItemInSlotFn slot_fn = (JassUnitItemInSlotFn)(uintptr_t)war3_persistent_native_handler("UnitItemInSlot");
    JassUnitIntQueryFn capacity_fn = (JassUnitIntQueryFn)(uintptr_t)war3_persistent_native_handler("UnitInventorySize");
    JassUnitIntQueryFn type_fn = (JassUnitIntQueryFn)(uintptr_t)war3_persistent_native_handler("GetItemTypeId");
    JassUnitIntQueryFn charges_fn = (JassUnitIntQueryFn)(uintptr_t)war3_persistent_native_handler("GetItemCharges");
    JassUnitHandleResolveFn resolve = (JassUnitHandleResolveFn)(uintptr_t)g_persistent_item_resolver;
    War3AgentResolveFn agent = (War3AgentResolveFn)(uintptr_t)g_persistent_agent_resolver;
    int32_t capacity;
    DWORD error = war3_validate_unit_identity(cmd, &cmd->ops[0]);
    if (error) return error;
    if (!war3_executable_pointer((uint64_t)(uintptr_t)slot_fn) ||
        !war3_executable_pointer((uint64_t)(uintptr_t)capacity_fn) ||
        !war3_executable_pointer((uint64_t)(uintptr_t)type_fn) ||
        !war3_executable_pointer((uint64_t)(uintptr_t)charges_fn) ||
        !war3_executable_pointer(g_persistent_item_resolver)) return ERROR_PROC_NOT_FOUND;
    capacity = capacity_fn(cmd->unit_handle);
    if (capacity < 0 || capacity > 6) return ERROR_INVALID_DATA;
    values[0] = (uint64_t)capacity;
    for (unsigned slot=0; slot<6; ++slot) {
        uint64_t *row = values + 1 + slot*8;
        uint64_t item = slot_fn(cmd->unit_handle, (int32_t)slot), object, full, wrapper;
        if (!item) continue;
        if (slot >= (unsigned)capacity) return ERROR_INVALID_DATA;
        object = resolve(item);
        if (!war3_readable_span(object, 0x1bc)) return ERROR_INVALID_ADDRESS;
        full = *(uint64_t *)(uintptr_t)(object+0x18);
        wrapper = agent((uint32_t)full, (uint32_t)(full>>32));
        if (!full || !war3_readable_span(wrapper, 0x98) ||
            *(uint64_t *)(uintptr_t)(wrapper+0x18) != 0x6974656d2b61676cULL ||
            *(uint64_t *)(uintptr_t)(wrapper+0x20) != full ||
            *(uint64_t *)(uintptr_t)(wrapper+0x90) != object) return ERROR_INVALID_HANDLE;
        row[0]=item; row[1]=full; row[2]=object; row[3]=(uint32_t)type_fn(item);
        if (!row[3] || *(uint32_t *)(uintptr_t)(object+0x70) != row[3]) return ERROR_INVALID_DATA;
        row[4]=(uint64_t)(int64_t)(int32_t)charges_fn(item);
        row[5]=*(uint32_t *)(uintptr_t)(object+0x178);
        row[6]=*(uint32_t *)(uintptr_t)(object+0x1b8);
        row[7]=wrapper;
        for (unsigned prior=0; prior<slot; ++prior) {
            uint64_t *old = values+1+prior*8;
            if (old[0]==item || (old[0] && (old[1]==full || old[2]==object))) return ERROR_INVALID_DATA;
        }
    }
    if (capacity_fn(cmd->unit_handle) != capacity) return ERROR_INVALID_HANDLE;
    for (unsigned slot=0; slot<6; ++slot) {
        uint64_t *row=values+1+slot*8;
        if (slot_fn(cmd->unit_handle,(int32_t)slot) != row[0]) return ERROR_INVALID_HANDLE;
        if (row[0] && (resolve(row[0]) != row[2] ||
            agent((uint32_t)row[1],(uint32_t)(row[1]>>32)) != row[7] ||
            *(uint64_t *)(uintptr_t)(row[2]+0x18) != row[1] ||
            *(uint32_t *)(uintptr_t)(row[2]+0x70) != row[3] ||
            (uint32_t)type_fn(row[0]) != row[3] ||
            *(uint64_t *)(uintptr_t)(row[7]+0x18) != 0x6974656d2b61676cULL ||
            *(uint64_t *)(uintptr_t)(row[7]+0x20) != row[1] ||
            *(uint64_t *)(uintptr_t)(row[7]+0x90) != row[2])) return ERROR_INVALID_HANDLE;
    }
    return war3_validate_unit_identity(cmd, &cmd->ops[0]);
}

#include "war3_native_inventory_batch.h"

typedef struct War3ItemIdentity {
    uint64_t handle, object, full;
    uint32_t rawcode;
} War3ItemIdentity;

static DWORD war3_item_identity(const War3ItemIdentity *item) {
    JassUnitHandleResolveFn resolve=(JassUnitHandleResolveFn)(uintptr_t)g_persistent_item_resolver;
    War3AgentResolveFn agent=(War3AgentResolveFn)(uintptr_t)g_persistent_agent_resolver;
    JassGetItemTypeIdFn type=(JassGetItemTypeIdFn)(uintptr_t)war3_persistent_native_handler("GetItemTypeId");
    uint64_t wrapper;
    if (!item->handle || !item->full || !war3_readable_span(item->object,0x78) ||
        resolve(item->handle)!=item->object || *(uint64_t *)(uintptr_t)(item->object+0x18)!=item->full ||
        *(uint32_t *)(uintptr_t)(item->object+0x70)!=item->rawcode || type(item->handle)!=item->rawcode)
        return ERROR_INVALID_HANDLE;
    wrapper=agent((uint32_t)item->full,(uint32_t)(item->full>>32));
    if (!war3_readable_span(wrapper,0x98) ||
        *(uint64_t *)(uintptr_t)(wrapper+0x18)!=0x6974656d2b61676cULL ||
        *(uint64_t *)(uintptr_t)(wrapper+0x20)!=item->full ||
        *(uint64_t *)(uintptr_t)(wrapper+0x90)!=item->object) return ERROR_INVALID_HANDLE;
    return ERROR_SUCCESS;
}

#include "war3_native_item_create.h"

static DWORD war3_same_inventory(const NativeCommand *cmd,const uint64_t *before,unsigned slot,
                                  const War3ItemIdentity *expected) {
    uint64_t now[WAR3_BOUND_INVENTORY_QWORDS]={0};
    DWORD error=war3_bound_inventory(cmd,now);
    if(error) return error;
    if(now[0]!=before[0]) return ERROR_INVALID_HANDLE;
    for(unsigned n=0;n<6;++n) {
        const uint64_t *row=now+1+n*8,*old=before+1+n*8;
        if(n==slot) {
            if(row[0]!=expected->handle || row[1]!=expected->full || row[2]!=expected->object || row[3]!=expected->rawcode)
                return ERROR_INVALID_HANDLE;
        } else if(memcmp(row,old,4*sizeof(uint64_t))) return ERROR_INVALID_HANDLE;
    }
    return ERROR_SUCCESS;
}

#include "war3_native_slot_resolver.h"

/* Return success only after the new object occupies the exact slot. Retain
   the old object until then; never restore into a slot claimed by a trigger. */
static DWORD war3_replace_inventory_item(NativeCommand *cmd) {
    NativeOp *op=&cmd->ops[1],*context=&cmd->ops[2];
    InternalUnitAddItemToSlotFn add=(InternalUnitAddItemToSlotFn)(uintptr_t)op->handler;
    JassCreateItemFn create=(JassCreateItemFn)(uintptr_t)war3_persistent_native_handler("CreateItem");
    JassRemoveItemFn destroy=(JassRemoveItemFn)(uintptr_t)war3_persistent_native_handler("RemoveItem");
    JassUnitRemoveItemFn detach=(JassUnitRemoveItemFn)(uintptr_t)war3_persistent_native_handler("UnitRemoveItem");
    JassUnitIntQueryFn owned=(JassUnitIntQueryFn)(uintptr_t)war3_persistent_native_handler("IsItemOwned");
    JassUnitRealQueryFn get_x=(JassUnitRealQueryFn)(uintptr_t)war3_persistent_native_handler("GetUnitX");
    JassUnitRealQueryFn get_y=(JassUnitRealQueryFn)(uintptr_t)war3_persistent_native_handler("GetUnitY");
    JassUnitItemInSlotFn slot_fn=(JassUnitItemInSlotFn)(uintptr_t)war3_persistent_native_handler("UnitItemInSlot");
    JassUnitHandleResolveFn resolve=(JassUnitHandleResolveFn)(uintptr_t)g_persistent_item_resolver;
    War3ItemIdentity old={op->arg0,context->handler,op->arg1,(uint32_t)context->arg0}, fresh={0}, empty={0};
    uint64_t before[WAR3_BOUND_INVENTORY_QWORDS]={0},unit=cmd->ops[0].handler;
    unsigned slot=context->rawcode;
    DWORD error=ERROR_SUCCESS,recovery=ERROR_SUCCESS;
    int committed=0;
    float x,y;
    if(cmd->op_count!=3 || cmd->ops[0].kind!=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY ||
       context->kind!=WAR3_NATIVE_OP_REPLACE_INVENTORY_CONTEXT || slot>=6 || !op->rawcode ||
       context->arg0>UINT32_MAX) return ERROR_INVALID_PARAMETER;
    if(!op->handler) {
        uint64_t resolved=0;
        error=war3_resolve_slot_add(&resolved);if(error) return error;
        add=(InternalUnitAddItemToSlotFn)(uintptr_t)resolved;
    } else if(!war3_executable_pointer(op->handler)) return ERROR_INVALID_PARAMETER;
    const uint64_t functions[]={ (uint64_t)(uintptr_t)create,(uint64_t)(uintptr_t)destroy,
        (uint64_t)(uintptr_t)detach,(uint64_t)(uintptr_t)owned,(uint64_t)(uintptr_t)get_x,(uint64_t)(uintptr_t)get_y };
    for(unsigned n=0;n<sizeof(functions)/sizeof(functions[0]);++n)
        if(!war3_executable_pointer(functions[n])) return ERROR_PROC_NOT_FOUND;
    __try {
        error=war3_bound_inventory(cmd,before);if(error) __leave;
        if(slot>=before[0]) { error=ERROR_INVALID_PARAMETER;__leave; }
        error=war3_same_inventory(cmd,before,slot,&old);if(error) __leave;
        x=war3_real_from_bits(get_x(cmd->unit_handle));y=war3_real_from_bits(get_y(cmd->unit_handle));
        fresh.handle=create(op->rawcode,&x,&y);
        if(!fresh.handle) { error=ERROR_NOT_FOUND;__leave; }
        fresh.object=resolve(fresh.handle);
        if(!war3_readable_span(fresh.object,0x78)) { error=ERROR_INVALID_ADDRESS;__leave; }
        fresh.full=*(uint64_t *)(uintptr_t)(fresh.object+0x18);
        fresh.rawcode=*(uint32_t *)(uintptr_t)(fresh.object+0x70);
        error=war3_item_identity(&fresh);if(error) __leave;
        if(fresh.rawcode!=op->rawcode) { error=ERROR_INVALID_DATA;__leave; }
        if(owned(fresh.handle)) { error=ERROR_INVALID_HANDLE;__leave; }
        error=war3_same_inventory(cmd,before,slot,&old);if(error) __leave;
        if(old.handle) detach(cmd->unit_handle,old.handle);
        error=war3_same_inventory(cmd,before,slot,&empty);if(error) __leave;
        error=war3_item_identity(&fresh);if(error) __leave;
        if(owned(fresh.handle)) { error=ERROR_INVALID_HANDLE;__leave; }
        if(!add(unit,fresh.object,(int32_t)slot,1,0)) { error=ERROR_CAN_NOT_COMPLETE;__leave; }
        error=war3_same_inventory(cmd,before,slot,&fresh);if(error) __leave;
        if(old.handle) {
            error=war3_item_identity(&old);if(error) __leave;
            if(owned(old.handle)) { error=ERROR_INVALID_HANDLE;__leave; }
            committed=1;
            destroy(old.handle);
        }
        error=war3_same_inventory(cmd,before,slot,&fresh);if(error) __leave;
        op->result=fresh.object;context->result=fresh.rawcode;
    } __except(EXCEPTION_EXECUTE_HANDLER) { error=GetExceptionCode(); }
    if(committed && error) context->result=ERROR_CAN_NOT_COMPLETE;
    if(!error || !fresh.handle || committed) return error;
    __try {
        /* Recovery must not touch a recycled unit, recycled item, or another
           item's slot. If a map trigger took ownership, leave that item alone. */
        recovery=war3_validate_unit_identity(cmd,&cmd->ops[0]);
        if(!recovery) {
            uint64_t current=slot_fn(cmd->unit_handle,(int32_t)slot);
            if(current==fresh.handle && !war3_item_identity(&fresh)) {
                detach(cmd->unit_handle,fresh.handle);
                recovery=war3_validate_unit_identity(cmd,&cmd->ops[0]);
            }
            if(!recovery && slot_fn(cmd->unit_handle,(int32_t)slot) &&
                slot_fn(cmd->unit_handle,(int32_t)slot)!=old.handle) recovery=ERROR_INVALID_HANDLE;
            if(!recovery && old.handle && !slot_fn(cmd->unit_handle,(int32_t)slot)) {
                recovery=war3_item_identity(&old);
                if(!recovery && !owned(old.handle)) {
                    if(!add(unit,old.object,(int32_t)slot,1,0)) recovery=ERROR_CAN_NOT_COMPLETE;
                    if(!recovery) recovery=war3_same_inventory(cmd,before,slot,&old);
                } else if(!recovery) recovery=ERROR_INVALID_HANDLE;
            }
        }
        context->arg1=war3_item_identity(&fresh);
        if(!context->arg1) {
            if(owned(fresh.handle)) context->arg1=ERROR_BUSY;
            else destroy(fresh.handle);
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) { recovery=GetExceptionCode(); }
    context->result=recovery; /* original failure remains cmd.last_error */
    return error;
}

/* Fixed field IDs for this build. Client addresses only pin identity; they
   never select an arbitrary offset. component: 0 unit, 1 hero, 2 move, 3/4 attacks. */
static DWORD war3_component_field_address(const NativeCommand *cmd,const NativeOp *op,uint64_t *address) {
    static const uint32_t attack_offsets[17]={0xf8,0xfc,0x100,0x104,0x108,0x10c,0x110,0x114,
        0x118,0x16c,0x178,0x200,0x228,0x370,0x398,0x3a8,0x3c0};
    static const uint32_t base_offsets[10]={0x2e8,0x2f0,0x104,0x188,0x198,0x1a8,0x100,0x108,0x130,0xd8};
    uint32_t id=op->rawcode,component,offset,real;
    uint64_t unit=cmd->ops[0].handler,data=unit,wrapper=0,tag=0;
    if(op->kind!=WAR3_NATIVE_OP_WRITE_COMPONENT_FIELDS || op->arg1>UINT32_MAX) return ERROR_INVALID_PARAMETER;
    if(id<10) {
        if(id==7 || id==8) return ERROR_INVALID_PARAMETER; /* use bound stat setters */
        component=id<2?0:id==9?2:1;offset=base_offsets[id];
        real=id==0 || (id>=3 && id<=5) || id==9;
    } else if((id>=16 && id<33) || (id>=48 && id<65)) {
        unsigned index=id>=48?id-48:id-16;
        component=id>=48?4:3;offset=attack_offsets[index];real=index>=11;
    } else if(id>=80 && id<90) {
        component=1;offset=id<85?0x1d4+(id-80)*4:0x1ec+(id-85)*4;real=0;
    } else return ERROR_INVALID_PARAMETER;
    if(real && ((uint32_t)op->arg1&0x7f800000u)==0x7f800000u) return ERROR_INVALID_PARAMETER;
    if(component) {
        uint32_t slot=component==1?0x5a8:component==2?0x5b0:0x5c0;
        tag=component==1?0x414865722b61676cULL:component==2?0x416d6f762b61676cULL:0x4161746b2b61676cULL;
        if(!war3_readable_span(unit+slot,8)) return ERROR_INVALID_ADDRESS;
        data=*(uint64_t *)(uintptr_t)(unit+slot);
        if(data!=op->handler || !op->arg0 || !war3_readable_span(data,0x70) ||
            *(uint64_t *)(uintptr_t)(data+0x18)!=op->arg0 ||
            *(uint64_t *)(uintptr_t)(data+0x68)!=unit) return ERROR_INVALID_HANDLE;
        wrapper=((War3AgentResolveFn)(uintptr_t)g_persistent_agent_resolver)((uint32_t)op->arg0,(uint32_t)(op->arg0>>32));
        if(!war3_readable_span(wrapper,0x98) || *(uint64_t *)(uintptr_t)(wrapper+0x18)!=tag ||
            *(uint64_t *)(uintptr_t)(wrapper+0x20)!=op->arg0 ||
            *(uint64_t *)(uintptr_t)(wrapper+0x50)!=cmd->ops[0].arg1 ||
            *(uint64_t *)(uintptr_t)(wrapper+0x90)!=data) return ERROR_INVALID_HANDLE;
        if(component==4) {
            uint64_t second=data+0x638,vtable;
            if(!war3_readable_span(second,12)) return ERROR_INVALID_ADDRESS;
            vtable=*(uint64_t *)(uintptr_t)second;
            if(!war3_readable_span(vtable,8) || !war3_executable_pointer(*(uint64_t *)(uintptr_t)vtable) ||
                *(uint32_t *)(uintptr_t)(second+8)!=*(uint32_t *)(uintptr_t)(data+8)) return ERROR_INVALID_DATA;
            offset+=0x638;
        }
    } else if(op->handler!=unit || op->arg0!=cmd->ops[0].arg0) return ERROR_INVALID_HANDLE;
    *address=data+offset;
    if(!war3_readable_span(*address,4)) return ERROR_INVALID_ADDRESS;
    MEMORY_BASIC_INFORMATION region;
    if(VirtualQuery((void *)(uintptr_t)*address,&region,sizeof(region))!=sizeof(region) ||
        !(region.Protect&(PAGE_READWRITE|PAGE_WRITECOPY|PAGE_EXECUTE_READWRITE|PAGE_EXECUTE_WRITECOPY)))
        return ERROR_ACCESS_DENIED;
    return ERROR_SUCCESS;
}

static DWORD war3_write_component_fields(NativeCommand *cmd) {
    uint64_t addresses[WAR3_NATIVE_MAX_OPS]={0};
    DWORD error=ERROR_SUCCESS;
    if(cmd->op_count<2 || cmd->op_count>WAR3_NATIVE_MAX_OPS || cmd->ops[0].kind!=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY)
        return ERROR_INVALID_PARAMETER;
    __try {
        error=war3_validate_unit_identity(cmd,&cmd->ops[0]);if(error) __leave;
        for(unsigned n=1;n<cmd->op_count;++n) {
            error=war3_component_field_address(cmd,&cmd->ops[n],&addresses[n]);
            if(error) { cmd->ops[n].last_error=error;__leave; }
            for(unsigned prior=1;prior<n;++prior) if(addresses[prior]==addresses[n]) {
                error=ERROR_INVALID_PARAMETER;__leave;
            }
            if(error) __leave;
        }
        if(error) __leave;
        error=war3_validate_unit_identity(cmd,&cmd->ops[0]);if(error) __leave;
        /* All requested locations and values are valid before the first store.
           No engine callbacks run between these stores and their readback. */
        for(unsigned n=1;n<cmd->op_count;++n) {
            uint64_t address=0;
            error=war3_component_field_address(cmd,&cmd->ops[n],&address);
            if(error || address!=addresses[n]) { if(!error) error=ERROR_INVALID_HANDLE;__leave; }
        }
        if(error) __leave;
        if(*(uint64_t *)(uintptr_t)(cmd->ops[0].handler+0x18)!=cmd->ops[0].arg0 ||
           *(uint64_t *)(uintptr_t)(cmd->ops[0].arg1+0x20)!=cmd->ops[0].arg0 ||
           *(uint64_t *)(uintptr_t)(cmd->ops[0].arg1+0x90)!=cmd->ops[0].handler) {
            error=ERROR_INVALID_HANDLE;__leave;
        }
        for(unsigned n=1;n<cmd->op_count;++n)
            *(uint32_t *)(uintptr_t)addresses[n]=(uint32_t)cmd->ops[n].arg1;
        for(unsigned n=1;n<cmd->op_count;++n)
            cmd->ops[n].result=*(uint32_t *)(uintptr_t)addresses[n];
    } __except(EXCEPTION_EXECUTE_HANDLER) { error=GetExceptionCode(); }
    return error;
}

static DWORD war3_validate_hero_component(const NativeCommand *cmd,const NativeOp *op) {
    uint64_t unit=cmd->ops[0].handler,data=op->handler,wrapper;
    DWORD error=war3_validate_unit_identity(cmd,&cmd->ops[0]);
    if(error) return error;
    if(!op->arg0 || !war3_readable_span(unit+0x5a8,8) ||
        *(uint64_t *)(uintptr_t)(unit+0x5a8)!=data || !war3_readable_span(data,0x70) ||
        *(uint64_t *)(uintptr_t)(data+0x18)!=op->arg0 ||
        *(uint64_t *)(uintptr_t)(data+0x68)!=unit) return ERROR_INVALID_HANDLE;
    wrapper=((War3AgentResolveFn)(uintptr_t)g_persistent_agent_resolver)((uint32_t)op->arg0,(uint32_t)(op->arg0>>32));
    if(!war3_readable_span(wrapper,0x98) || *(uint64_t *)(uintptr_t)(wrapper+0x18)!=0x414865722b61676cULL ||
        *(uint64_t *)(uintptr_t)(wrapper+0x20)!=op->arg0 ||
        *(uint64_t *)(uintptr_t)(wrapper+0x50)!=cmd->ops[0].arg1 ||
        *(uint64_t *)(uintptr_t)(wrapper+0x90)!=data) return ERROR_INVALID_HANDLE;
    return ERROR_SUCCESS;
}

static DWORD war3_set_bound_hero_int(NativeCommand *cmd,NativeOp *op) {
    JassGetHeroStatFn get=(JassGetHeroStatFn)(uintptr_t)war3_persistent_native_handler("GetHeroInt");
    JassSetHeroStatFn set=(JassSetHeroStatFn)(uintptr_t)war3_persistent_native_handler("SetHeroInt");
    JassUnitIntQueryFn level=(JassUnitIntQueryFn)(uintptr_t)war3_persistent_native_handler("GetHeroLevel");
    int32_t base,total;
    DWORD error=ERROR_SUCCESS;
    if(cmd->op_count!=2 || cmd->ops[0].kind!=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY || op->rawcode>1000000u)
        return ERROR_INVALID_PARAMETER;
    if(!war3_executable_pointer((uint64_t)(uintptr_t)get) || !war3_executable_pointer((uint64_t)(uintptr_t)set) ||
        !war3_executable_pointer((uint64_t)(uintptr_t)level)) return ERROR_PROC_NOT_FOUND;
    __try {
        error=war3_validate_hero_component(cmd,op);if(error) __leave;
        if(level(cmd->unit_handle)<=0) { error=ERROR_INVALID_PARAMETER;__leave; }
        error=war3_validate_hero_component(cmd,op);if(error) __leave;
        base=get(cmd->unit_handle,0);
        error=war3_validate_hero_component(cmd,op);if(error) __leave;
        total=get(cmd->unit_handle,1);
        error=war3_validate_hero_component(cmd,op);if(error) __leave;
        /* At most one correction, using the latest base/total pair, always
           on the same unit and hero component. No delayed external retry. */
        for(unsigned attempt=0;attempt<2;++attempt) {
            int64_t target_base=(int64_t)base+(int64_t)op->rawcode-(int64_t)total;
            if(target_base<0 || target_base>INT32_MAX) { error=ERROR_INVALID_PARAMETER;__leave; }
            set(cmd->unit_handle,(int32_t)target_base,1);
            error=war3_validate_hero_component(cmd,op);if(error) __leave;
            base=get(cmd->unit_handle,0);
            error=war3_validate_hero_component(cmd,op);if(error) __leave;
            total=get(cmd->unit_handle,1);
            error=war3_validate_hero_component(cmd,op);if(error) __leave;
            if(total==(int32_t)op->rawcode) { op->result=(uint32_t)total;op->arg1=(uint32_t)base;__leave; }
        }
        if(!error && total!=(int32_t)op->rawcode) error=ERROR_CAN_NOT_COMPLETE;
    } __except(EXCEPTION_EXECUTE_HANDLER) { error=GetExceptionCode(); }
    return error;
}

#include "war3_native_hero_skill.h"
#include "war3_native_hero_base.h"
#include "war3_native_hero_progress.h"

static int war3_is_ability_field_op(uint32_t kind) {
    return kind == WAR3_NATIVE_OP_JASS_ABILITY_FIELD_GET ||
        kind == WAR3_NATIVE_OP_JASS_ABILITY_LEVEL_FIELD_GET ||
        kind == WAR3_NATIVE_OP_JASS_ABILITY_SCALAR_FIELD_SET ||
        kind == WAR3_NATIVE_OP_JASS_ABILITY_REAL_FIELD_SET ||
        kind == WAR3_NATIVE_OP_JASS_ABILITY_SCALAR_LEVEL_FIELD_SET ||
        kind == WAR3_NATIVE_OP_JASS_ABILITY_REAL_LEVEL_FIELD_SET;
}

static DWORD war3_validate_bound_ability(const NativeCommand *cmd, uint64_t *handle) {
    uint64_t values[10];
    NativeOp query = {0};
    DWORD error;
    const NativeOp *identity = &cmd->ops[1], *context = &cmd->ops[2];
    if (cmd->op_count < 4 || cmd->ops[0].kind != WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY ||
        identity->kind != WAR3_NATIVE_OP_BOUND_ABILITY_IDENTITY ||
        context->kind != WAR3_NATIVE_OP_BOUND_ABILITY_CONTEXT ||
        !identity->handler || !identity->arg0 || !identity->arg1) return ERROR_INVALID_DATA;
    query.rawcode = identity->rawcode;
    query.handler = context->handler;
    query.arg0 = context->arg0;
    error = war3_bound_ability_metadata(cmd, &query, values);
    if (error) return error;
    if (values[0] != identity->handler || values[1] != identity->arg0 || values[3] != identity->arg1 ||
        (uint32_t)(values[4] >> 32) != context->rawcode || values[8] != context->arg1)
        return ERROR_INVALID_HANDLE;
    *handle = values[0];
    return ERROR_SUCCESS;
}

static int war3_is_item_field_op(uint32_t kind) {
    return kind == WAR3_NATIVE_OP_JASS_ITEM_FIELD_GET || kind == WAR3_NATIVE_OP_JASS_ITEM_FIELD_SET;
}

static DWORD war3_validate_bound_item(const NativeCommand *cmd, uint64_t *handle) {
    const NativeOp *identity = &cmd->ops[1], *type = &cmd->ops[2];
    JassUnitItemInSlotFn slot_fn = (JassUnitItemInSlotFn)(uintptr_t)war3_persistent_native_handler("UnitItemInSlot");
    JassGetItemTypeIdFn id_fn = (JassGetItemTypeIdFn)(uintptr_t)war3_persistent_native_handler("GetItemTypeId");
    JassUnitHandleResolveFn resolve = (JassUnitHandleResolveFn)(uintptr_t)g_persistent_item_resolver;
    DWORD error;
    uint64_t item, object;
    if (cmd->op_count < 4 || cmd->ops[0].kind != WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY ||
        identity->kind != WAR3_NATIVE_OP_BOUND_INVENTORY_ITEM || type->kind != WAR3_NATIVE_OP_BOUND_ITEM_TYPE ||
        identity->rawcode >= 6 || !identity->handler || !identity->arg0 || !identity->arg1 || !type->rawcode)
        return ERROR_INVALID_DATA;
    error = war3_validate_unit_identity(cmd, &cmd->ops[0]);
    if (error) return error;
    if (!war3_executable_pointer((uint64_t)(uintptr_t)slot_fn) ||
        !war3_executable_pointer((uint64_t)(uintptr_t)id_fn) || !war3_executable_pointer(g_persistent_item_resolver))
        return ERROR_PROC_NOT_FOUND;
    __try {
        item = slot_fn(cmd->unit_handle, (int32_t)identity->rawcode);
        object = item ? resolve(item) : 0;
        if (item != identity->handler || object != identity->arg0 ||
            *(uint64_t *)(uintptr_t)(object + 0x18) != identity->arg1 || id_fn(item) != type->rawcode)
            return ERROR_INVALID_HANDLE;
        *handle = item;
    } __except (EXCEPTION_EXECUTE_HANDLER) { return ERROR_INVALID_ADDRESS; }
    return ERROR_SUCCESS;
}

static DWORD war3_persistent_selected_snapshot(
    NativeCommand *cmd,
    NativeOp *op,
    uint64_t **extra_results,
    uint32_t *extra_result_count
) {
    typedef uint64_t (__fastcall *GetLocalPlayerFn)(void);
    typedef void (__fastcall *GroupEnumSelectedFn)(uint64_t, uint64_t, uint64_t);
    typedef uint64_t (__fastcall *FirstOfGroupFn)(uint64_t);
    typedef void (__fastcall *GroupRemoveUnitFn)(uint64_t, uint64_t);
    typedef uint64_t (__fastcall *GetOwningPlayerFn)(uint64_t);
    typedef int32_t (__fastcall *GetPlayerIdFn)(uint64_t);
    typedef uint32_t (__fastcall *GetUnitTypeIdFn)(uint64_t);
    typedef uint32_t (__fastcall *GetUnitStateFn)(uint64_t, int32_t);
    typedef uint32_t (__fastcall *GetUnitRealFn)(uint64_t);
    typedef int32_t (__fastcall *GetHeroIntFn)(uint64_t, uint32_t);
    typedef uint64_t (__fastcall *GetAbilityByIndexFn)(uint64_t, int32_t);
    typedef uint32_t (__fastcall *GetAbilityIdFn)(uint64_t);
    typedef int32_t (__fastcall *GetAbilityLevelFn)(uint64_t, uint32_t);
    typedef uint64_t (__fastcall *UnitItemInSlotFn)(uint64_t, int32_t);
    typedef uint32_t (__fastcall *GetItemTypeIdFn)(uint64_t);
    typedef int32_t (__fastcall *GetItemChargesFn)(uint64_t);
    uint32_t resolved = 0;
    int targeted = op && (op->kind == WAR3_NATIVE_OP_PERSISTENT_UNIT_SNAPSHOT ||
                          op->kind == WAR3_NATIVE_OP_IDENTITY_UNIT_SNAPSHOT);
    uint64_t group = 0;
    uint64_t player = 0;
    uint64_t *buffer = NULL;
    War3SnapshotExtra extra = {0};
    uint32_t count = 0;
    DWORD error = ERROR_SUCCESS;
    GetLocalPlayerFn get_local_player;
    GroupEnumSelectedFn enum_selected;
    FirstOfGroupFn first_of_group;
    GroupRemoveUnitFn remove_unit;
    JassDestroyGroupFn destroy_group;
    GetOwningPlayerFn get_owning_player;
    GetPlayerIdFn get_player_id;
    GetUnitTypeIdFn get_unit_type_id;
    GetUnitStateFn get_unit_state;
    GetUnitRealFn get_unit_x;
    GetUnitRealFn get_unit_y;
    GetUnitRealFn get_move_speed;
    JassUnitHandleResolveFn resolve_unit;
    JassUnitHandleResolveFn resolve_item;
    JassGetHeroStatFn get_hero_str;
    JassGetHeroStatFn get_hero_agi;
    GetHeroIntFn get_hero_int;
    GetAbilityByIndexFn get_ability_by_index;
    GetAbilityIdFn get_ability_id;
    GetAbilityLevelFn get_ability_level;
    UnitItemInSlotFn item_in_slot;
    GetItemTypeIdFn get_item_type_id;
    GetItemChargesFn get_item_charges;

    if (
        !cmd || !op || !extra_results || !extra_result_count ||
        cmd->op_count != 1u
    ) {
        return ERROR_INVALID_DATA;
    }
    if (targeted && (!cmd->unit_handle || !op->handler || !op->arg0 || !op->arg1)) {
        return ERROR_INVALID_DATA;
    }
    error = war3_persistent_resolve_natives(&resolved);
    if (error != ERROR_SUCCESS) {
        return error;
    }
    get_local_player = (GetLocalPlayerFn)(uintptr_t)war3_persistent_native_handler("GetLocalPlayer");
    enum_selected = (GroupEnumSelectedFn)(uintptr_t)war3_persistent_native_handler("GroupEnumUnitsSelected");
    first_of_group = (FirstOfGroupFn)(uintptr_t)war3_persistent_native_handler("FirstOfGroup");
    remove_unit = (GroupRemoveUnitFn)(uintptr_t)war3_persistent_native_handler("GroupRemoveUnit");
    destroy_group = (JassDestroyGroupFn)(uintptr_t)war3_persistent_native_handler("DestroyGroup");
    get_owning_player = (GetOwningPlayerFn)(uintptr_t)war3_persistent_native_handler("GetOwningPlayer");
    get_player_id = (GetPlayerIdFn)(uintptr_t)war3_persistent_native_handler("GetPlayerId");
    get_unit_type_id = (GetUnitTypeIdFn)(uintptr_t)war3_persistent_native_handler("GetUnitTypeId");
    get_unit_state = (GetUnitStateFn)(uintptr_t)war3_persistent_native_handler("GetUnitState");
    get_unit_x = (GetUnitRealFn)(uintptr_t)war3_persistent_native_handler("GetUnitX");
    get_unit_y = (GetUnitRealFn)(uintptr_t)war3_persistent_native_handler("GetUnitY");
    get_move_speed = (GetUnitRealFn)(uintptr_t)war3_persistent_native_handler("GetUnitMoveSpeed");
    resolve_unit = (JassUnitHandleResolveFn)(uintptr_t)g_persistent_unit_resolver;
    resolve_item = (JassUnitHandleResolveFn)(uintptr_t)g_persistent_item_resolver;
    get_hero_str = (JassGetHeroStatFn)(uintptr_t)war3_persistent_native_handler("GetHeroStr");
    get_hero_agi = (JassGetHeroStatFn)(uintptr_t)war3_persistent_native_handler("GetHeroAgi");
    get_hero_int = (GetHeroIntFn)(uintptr_t)war3_persistent_native_handler("GetHeroInt");
    get_ability_by_index = (GetAbilityByIndexFn)(uintptr_t)war3_persistent_native_handler("BlzGetUnitAbilityByIndex");
    get_ability_id = (GetAbilityIdFn)(uintptr_t)war3_persistent_native_handler("BlzGetAbilityId");
    get_ability_level = (GetAbilityLevelFn)(uintptr_t)war3_persistent_native_handler("GetUnitAbilityLevel");
    item_in_slot = (UnitItemInSlotFn)(uintptr_t)war3_persistent_native_handler("UnitItemInSlot");
    get_item_type_id = (GetItemTypeIdFn)(uintptr_t)war3_persistent_native_handler("GetItemTypeId");
    get_item_charges = (GetItemChargesFn)(uintptr_t)war3_persistent_native_handler("GetItemCharges");
    if (
        !get_local_player || !enum_selected || !first_of_group || !remove_unit ||
        !destroy_group || !get_owning_player || !get_player_id || !get_unit_type_id ||
        !get_unit_state || !get_unit_x || !get_unit_y || !get_move_speed ||
        !get_hero_str || !get_hero_agi || !get_hero_int ||
        !get_ability_by_index || !get_ability_id || !get_ability_level ||
        !item_in_slot || !get_item_type_id || !get_item_charges ||
        !war3_persistent_native_handler("GetHeroLevel") ||
        !war3_persistent_native_handler("GetHeroXP")
    ) {
        return ERROR_PROC_NOT_FOUND;
    }
    if (!resolve_unit || !g_persistent_agent_resolver) {
        /* The Python side must never map a native selection by scanning the
           process.  Both resolvers are required for a direct object-table
           identity (handle, unit object, and owner object). */
        return ERROR_PROC_NOT_FOUND;
    }
    buffer = (uint64_t *)HeapAlloc(
        GetProcessHeap(),
        HEAP_ZERO_MEMORY,
        12u * sizeof(War3PersistentSnapshot)
    );
    if (!buffer) {
        return ERROR_OUTOFMEMORY;
    }
    __try {
        if (!targeted) {
            group = ((JassNoArgU64Fn)(uintptr_t)war3_persistent_native_handler("CreateGroup"))();
            player = get_local_player();
            if (!group || !player) {
                error = ERROR_NOT_FOUND;
                __leave;
            }
            enum_selected(group, player, 0);
        }
        while (count < 12u) {
            uint64_t unit = targeted ? (count ? 0 : cmd->unit_handle) : first_of_group(group);
            War3PersistentSnapshot *snapshot;
            if (!unit) {
                break;
            }
            if (targeted) {
                /* op.handler is the expected unit object, arg0 the complete
                   object handle, arg1 the expected owner. Validate before any
                   field native runs; never follow the current selection. */
                error = war3_validate_unit_identity(cmd, op);
                if (error) {
                    __leave;
                }
            } else {
                remove_unit(group, unit);
            }
            snapshot = &((War3PersistentSnapshot *)buffer)[count];
            snapshot->handle = unit;
            /* Pin the generation before any field native executes. Capturing
               it after HP/position queries can label old values with the
               identity of a replacement that reused the same JASS handle. */
            snapshot->unit_address = resolve_unit(unit);
            if (!war3_readable_span(snapshot->unit_address, 0x20)) {
                error = ERROR_INVALID_HANDLE; __leave;
            }
            snapshot->full_handle = *(uint64_t *)(uintptr_t)(snapshot->unit_address + 0x18);
            snapshot->owner_address = ((War3AgentResolveFn)(uintptr_t)g_persistent_agent_resolver)(
                (uint32_t)snapshot->full_handle, (uint32_t)(snapshot->full_handle >> 32));
            if (!snapshot->full_handle || !war3_readable_span(snapshot->owner_address, 0x98) ||
                *(uint64_t *)(uintptr_t)(snapshot->owner_address + 0x18) != 0x2b7733752b61676cULL ||
                *(uint64_t *)(uintptr_t)(snapshot->owner_address + 0x20) != snapshot->full_handle ||
                *(uint64_t *)(uintptr_t)(snapshot->owner_address + 0x90) != snapshot->unit_address ||
                (targeted && (snapshot->unit_address != op->handler ||
                              snapshot->full_handle != op->arg0 || snapshot->owner_address != op->arg1))) {
                error = ERROR_INVALID_HANDLE; __leave;
            }
            snapshot->owner = get_owning_player(unit);
            snapshot->type_id = get_unit_type_id(unit);
            snapshot->hp_bits = get_unit_state(unit, 0);
            snapshot->hp_max_bits = get_unit_state(unit, 1);
            snapshot->mp_bits = get_unit_state(unit, 2);
            snapshot->mp_max_bits = get_unit_state(unit, 3);
            snapshot->x_bits = get_unit_x(unit);
            snapshot->y_bits = get_unit_y(unit);
            if (get_move_speed) {
                snapshot->move_speed_bits = get_move_speed(unit);
            }
            snapshot->hero_level = war3_persistent_native_handler("GetHeroLevel")
                ? (uint64_t)(int64_t)((JassUnitIntQueryFn)(uintptr_t)war3_persistent_native_handler("GetHeroLevel"))(unit)
                : 0;
            if (snapshot->hero_level > 0) {
                if (war3_persistent_native_handler("GetHeroXP")) {
                    snapshot->hero_xp = (uint64_t)(int64_t)((JassUnitIntQueryFn)(uintptr_t)war3_persistent_native_handler("GetHeroXP"))(unit);
                }
                if (get_hero_str) {
                    snapshot->strength = (uint64_t)(int64_t)get_hero_str(unit, 1);
                    snapshot->base_strength = (uint64_t)(int64_t)get_hero_str(unit, 0);
                }
                if (get_hero_agi) {
                    snapshot->agility = (uint64_t)(int64_t)get_hero_agi(unit, 1);
                    snapshot->base_agility = (uint64_t)(int64_t)get_hero_agi(unit, 0);
                }
                if (get_hero_int) {
                    snapshot->intelligence = (uint64_t)(int64_t)get_hero_int(unit, 1);
                    snapshot->base_intelligence = (uint64_t)(int64_t)get_hero_int(unit, 0);
                }
            }
            if (snapshot->owner && get_player_id) {
                snapshot->owner_id = (uint64_t)(int64_t)get_player_id(snapshot->owner);
            }
            if (item_in_slot && get_item_type_id && get_item_charges) {
                for (uint32_t slot = 0; slot < WAR3_PERSISTENT_SNAPSHOT_MAX_ITEMS; ++slot) {
                    uint64_t item = item_in_slot(unit, (int32_t)slot);
                    if (item) {
                        snapshot->item_handles[slot] = item;
                        if (resolve_item) {
                            snapshot->item_addresses[slot] = resolve_item(item);
                            if (snapshot->item_addresses[slot]) {
                                snapshot->item_full_handles[slot] = *(uint64_t *)(uintptr_t)(snapshot->item_addresses[slot] + 0x18);
                            }
                        }
                        snapshot->item_ids[slot] = get_item_type_id(item);
                        snapshot->item_charges[slot] = (uint64_t)(int64_t)get_item_charges(item);
                    }
                }
            }
            if (get_ability_by_index && get_ability_id && get_ability_level) {
                for (int32_t index = 0; index <= WAR3_PERSISTENT_SNAPSHOT_ENUM_LIMIT; ++index) {
                    uint64_t ability = get_ability_by_index(unit, index);
                    uint32_t rawcode;
                    uint64_t level;
                    if (!ability) {
                        /* Preserve the old sparse-index probe range. Beyond
                           it, stop at the native's end-of-list sentinel. */
                        if (index >= 256) {
                            break;
                        }
                        continue;
                    }
                    if (index == WAR3_PERSISTENT_SNAPSHOT_ENUM_LIMIT) {
                        error = ERROR_MORE_DATA;
                        break;
                    }
                    rawcode = get_ability_id(ability);
                    if (!rawcode) {
                        continue;
                    }
                    level = (uint64_t)(int64_t)get_ability_level(unit, rawcode);
                    if (snapshot->ability_count < WAR3_PERSISTENT_SNAPSHOT_MAX_ABILITIES) {
                        snapshot->ability_ids[snapshot->ability_count] = rawcode;
                        snapshot->ability_levels[snapshot->ability_count] = level;
                    } else {
                        error = war3_snapshot_append_ability(&extra, rawcode, level);
                        if (error) {
                            break;
                        }
                    }
                    ++snapshot->ability_count;
                }
                if (error) {
                    __leave;
                }
            }
            {
                War3RegenProperties properties;
                uint64_t object = snapshot->unit_address, owner = snapshot->owner_address, full = snapshot->full_handle;
                if (!object || !owner || !full || resolve_unit(unit) != object ||
                    ((War3AgentResolveFn)(uintptr_t)g_persistent_agent_resolver)((uint32_t)full, (uint32_t)(full >> 32)) != owner ||
                    !war3_readable_span(object, 0x20) || !war3_readable_span(owner, 0x98) ||
                    *(uint64_t *)(uintptr_t)(object + 0x18) != full ||
                    *(uint64_t *)(uintptr_t)(owner + 0x18) != 0x2b7733752b61676cULL ||
                    *(uint64_t *)(uintptr_t)(owner + 0x20) != full ||
                    *(uint64_t *)(uintptr_t)(owner + 0x90) != object) {
                    error = ERROR_INVALID_HANDLE; __leave;
                }
                error = war3_regen_properties(owner, &properties);
                if (error) __leave;
                snapshot->hp_property = properties.address[0]; snapshot->mp_property = properties.address[1];
                snapshot->hp_regen_bits = properties.bits[0]; snapshot->mp_regen_bits = properties.bits[1];
                error=war3_snapshot_component_mask(unit,object,owner,full,&snapshot->component_mask);
                if(error) __leave;
            }
            ++count;
        }
        if (!targeted && count == 12u && first_of_group(group) != 0) {
            error = ERROR_MORE_DATA;
            __leave;
        }
        op->result = count;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        error = GetExceptionCode();
    }
    if (group && destroy_group) {
        __try {
            destroy_group(group);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            if (!error) {
                error = GetExceptionCode();
            }
        }
    }
    if (!error && count) {
        uint32_t fixed_count = count * (sizeof(War3PersistentSnapshot) / sizeof(uint64_t));
        if (extra.count) {
            uint64_t *resized = (uint64_t *)HeapReAlloc(GetProcessHeap(), 0, buffer,
                (fixed_count + extra.count) * sizeof(uint64_t));
            if (!resized) {
                error = ERROR_OUTOFMEMORY;
            } else {
                buffer = resized;
                memcpy(buffer + fixed_count, extra.values, extra.count * sizeof(uint64_t));
            }
        }
        if (!error) {
            *extra_results = buffer;
            *extra_result_count = fixed_count + extra.count;
            buffer = NULL;
        }
    }
    if (extra.values) {
        HeapFree(GetProcessHeap(), 0, extra.values);
    }
    if (buffer) {
        HeapFree(GetProcessHeap(), 0, buffer);
    }
    return error;
}

/* Runs entirely inside one hook callback. Collect the group before changing
   any position so overflow or an empty selection cannot cause a partial move. */
static DWORD war3_move_selected_group_at_point(NativeOp *op, uint64_t point) {
    typedef void (__fastcall *GroupRemoveUnitFn)(uint64_t, uint64_t);
    uint32_t resolved = 0;
    DWORD error = war3_persistent_resolve_natives(&resolved);
    uint64_t group = 0;
    uint64_t units[12] = {0};
    uint32_t count = 0;
    float x = war3_real_from_bits((uint32_t)point);
    float y = war3_real_from_bits((uint32_t)(point >> 32));
    JassNoArgU64Fn create_group = (JassNoArgU64Fn)(uintptr_t)war3_persistent_native_handler("CreateGroup");
    JassNoArgU64Fn local_player = (JassNoArgU64Fn)(uintptr_t)war3_persistent_native_handler("GetLocalPlayer");
    JassGroupEnumUnitsSelectedFn enumerate = (JassGroupEnumUnitsSelectedFn)(uintptr_t)war3_persistent_native_handler("GroupEnumUnitsSelected");
    JassFirstOfGroupFn first = (JassFirstOfGroupFn)(uintptr_t)war3_persistent_native_handler("FirstOfGroup");
    GroupRemoveUnitFn remove = (GroupRemoveUnitFn)(uintptr_t)war3_persistent_native_handler("GroupRemoveUnit");
    JassDestroyGroupFn destroy = (JassDestroyGroupFn)(uintptr_t)war3_persistent_native_handler("DestroyGroup");
    JassSetUnitPositionFn move = (JassSetUnitPositionFn)(uintptr_t)op->handler;
    if (error) {
        return error;
    }
    if (!create_group || !local_player || !enumerate || !first || !remove || !destroy || !move) {
        return ERROR_PROC_NOT_FOUND;
    }
    if (!(x == x) || !(y == y) || x < -1000000.0f || x > 1000000.0f ||
        y < -1000000.0f || y > 1000000.0f) {
        return ERROR_INVALID_PARAMETER;
    }
    op->result = 0;
    op->arg0 = point;
    __try {
        uint64_t player = local_player();
        if (!player) {
            error = ERROR_NOT_READY;
            __leave;
        }
        group = create_group();
        if (!group) {
            error = ERROR_OUTOFMEMORY;
            __leave;
        }
        enumerate(group, player, 0);
        while (count < 12u) {
            uint64_t unit = first(group);
            if (!unit) {
                break;
            }
            units[count++] = unit;
            remove(group, unit);
        }
        if (!count) {
            error = ERROR_NOT_FOUND;
            __leave;
        }
        if (count == 12u && first(group)) {
            error = ERROR_MORE_DATA;
            __leave;
        }
        for (uint32_t index = 0; index < count; ++index) {
            move(units[index], &x, &y);
            ++op->result;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        error = GetExceptionCode();
    }
    if (group) {
        __try {
            destroy(group);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            if (!error) {
                error = GetExceptionCode();
            }
        }
    }
    return error;
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

#include "war3_native_clone_guard.h"

static int war3_copy_item_instance_fields(
    War3CloneGuard *clone_guard,
    uint64_t source_item,
    uint64_t target_item,
    JassItemFieldGetFn get_integer,
    JassItemScalarFieldSetFn set_integer,
    JassItemFieldGetFn get_real,
    JassItemRealFieldSetFn set_real,
    JassItemFieldGetFn get_boolean,
    JassItemScalarFieldSetFn set_boolean
) {
    static const uint32_t integer_fields[] = {
        0x696c6576u, /* ilev */
        0x69757365u, /* iuse */
        0x69636964u, /* icid */
        0x69687470u, /* ihtp */
        0x69687063u, /* ihpc */
        0x69707269u, /* ipri */
        0x6961726du, /* iarm */
        0x69636c72u, /* iclr */
        0x69636c67u, /* iclg */
        0x69636c62u, /* iclb */
        0x6963616cu, /* ical */
    };
    static const uint32_t real_fields[] = {
        0x69736361u, /* isca */
    };
    static const uint32_t boolean_fields[] = {
        0x69647270u, /* idrp */
        0x6964726fu, /* idro */
        0x69706572u, /* iper */
        0x6970726eu, /* iprn */
        0x69706f77u, /* ipow */
        0x69706177u, /* ipaw */
        0x69757361u, /* iusa */
    };

    for (
        size_t index = 0;
        index < sizeof(integer_fields) / sizeof(integer_fields[0]);
        ++index
    ) {
        uint32_t source_value =
            (uint32_t)WAR3_CLONE_VALUE(clone_guard, get_integer(source_item, integer_fields[index]));
        uint32_t target_value =
            (uint32_t)WAR3_CLONE_VALUE(clone_guard, get_integer(target_item, integer_fields[index]));
        if (target_value != source_value) {
            if (!WAR3_CLONE_VALUE(clone_guard, set_integer(target_item, integer_fields[index], source_value))) {
                return 0;
            }
            if (
                (uint32_t)WAR3_CLONE_VALUE(clone_guard, get_integer(target_item, integer_fields[index])) !=
                source_value
            ) {
                return 0;
            }
        }
    }
    for (
        size_t index = 0;
        index < sizeof(real_fields) / sizeof(real_fields[0]);
        ++index
    ) {
        uint32_t source_bits =
            (uint32_t)WAR3_CLONE_VALUE(clone_guard, get_real(source_item, real_fields[index]));
        uint32_t target_bits =
            (uint32_t)WAR3_CLONE_VALUE(clone_guard, get_real(target_item, real_fields[index]));
        float source_value = war3_real_from_bits(source_bits);
        float target_value = war3_real_from_bits(target_bits);
        float delta = target_value - source_value;
        if (delta < 0.0f) {
            delta = -delta;
        }
        if (!(source_value == source_value) || !(target_value == target_value)) {
            return 0;
        }
        if (delta > 0.0001f) {
            if (!WAR3_CLONE_VALUE(clone_guard, set_real(target_item, real_fields[index], &source_value))) {
                return 0;
            }
            target_bits = (uint32_t)WAR3_CLONE_VALUE(clone_guard, get_real(target_item, real_fields[index]));
            target_value = war3_real_from_bits(target_bits);
            delta = target_value - source_value;
            if (delta < 0.0f) {
                delta = -delta;
            }
            if (!(target_value == target_value) || delta > 0.0001f) {
                return 0;
            }
        }
    }
    for (
        size_t index = 0;
        index < sizeof(boolean_fields) / sizeof(boolean_fields[0]);
        ++index
    ) {
        uint32_t source_value =
            (uint32_t)WAR3_CLONE_VALUE(clone_guard, get_boolean(source_item, boolean_fields[index])) & 1u;
        uint32_t target_value =
            (uint32_t)WAR3_CLONE_VALUE(clone_guard, get_boolean(target_item, boolean_fields[index])) & 1u;
        if (target_value != source_value) {
            if (!WAR3_CLONE_VALUE(clone_guard, set_boolean(target_item, boolean_fields[index], source_value))) {
                return 0;
            }
            if (
                ((uint32_t)WAR3_CLONE_VALUE(clone_guard, get_boolean(target_item, boolean_fields[index])) & 1u) !=
                source_value
            ) {
                return 0;
            }
        }
    }
    return 1;
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

static DWORD run_jass_selected_units(
    NativeCommand *cmd,
    uint32_t index,
    uint64_t **extra_results,
    uint32_t *extra_result_count
) {
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
    JassGroupRemoveUnitFn group_remove_unit =
        (JassGroupRemoveUnitFn)(uintptr_t)cleanup_op->arg1;
    uint64_t player_override = cleanup_op->arg0;
    uint64_t group = 0;
    uint64_t player = 0;
    uint64_t unit = 0;
    uint64_t selected_units[12];
    uint32_t selected_count = 0;
    uint32_t handle_id = 0;
    DWORD error = 0;

    if (
        !create_group || !get_local_player || !group_enum_selected ||
        !first_of_group || !get_handle_id || !group_remove_unit ||
        !extra_results || !extra_result_count
    ) {
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
        while (selected_count < 12u) {
            uint64_t current = first_of_group(group);
            uint8_t duplicate = 0;
            if (!current) {
                break;
            }
            group_remove_unit(group, current);
            for (uint32_t existing = 0; existing < selected_count; ++existing) {
                if (selected_units[existing] == current) {
                    duplicate = 1;
                    break;
                }
            }
            if (duplicate) {
                continue;
            }
            selected_units[selected_count++] = current;
            if (!unit) {
                unit = current;
                handle_id = get_handle_id(current);
            }
        }
        if (selected_count) {
            uint64_t *resized = *extra_results
                ? (uint64_t *)HeapReAlloc(
                    GetProcessHeap(),
                    HEAP_ZERO_MEMORY,
                    *extra_results,
                    (*extra_result_count + selected_count) * sizeof(uint64_t)
                )
                : (uint64_t *)HeapAlloc(
                    GetProcessHeap(),
                    HEAP_ZERO_MEMORY,
                    selected_count * sizeof(uint64_t)
                );
            if (!resized) {
                error = ERROR_OUTOFMEMORY;
                __leave;
            }
            memcpy(
                resized + *extra_result_count,
                selected_units,
                selected_count * sizeof(uint64_t)
            );
            *extra_results = resized;
            *extra_result_count += selected_count;
            main_op->result = 6;
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

    if (g_bootstrap_module && cmd.op_count && cmd.ops[0].kind != WAR3_NATIVE_OP_BOOTSTRAP_NATIVE_TABLE) {
        last_error = war3_bootstrap_refresh();
        if (last_error) { cmd.ops[0].last_error = last_error; goto finish; }
    }
    for (uint32_t i = 0; i < cmd.op_count; ++i) {
        NativeOp *op = &cmd.ops[i];
        uint64_t ability_field_handle = 0;
        uint64_t item_field_handle = 0;
        uint64_t internal_unit = cmd.ops[0].kind == WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY
            ? cmd.ops[0].handler : cmd.unit_handle;
        op->result = 0;
        op->last_error = 0;
        if (i > 0 && cmd.ops[0].kind == WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY) {
            /* A setter can run triggers which destroy/recycle the unit. Check
               again before each subsequent setter, not only once per batch. */
            if (op->kind != WAR3_NATIVE_OP_JASS_SET_UNIT_STATE &&
                op->kind != WAR3_NATIVE_OP_JASS_UNIT_BOOL &&
                op->kind != WAR3_NATIVE_OP_JASS_UNIT_VOID &&
                op->kind != WAR3_NATIVE_OP_JASS_UNIT_INT_QUERY &&
                op->kind != WAR3_NATIVE_OP_JASS_CLONE_SELECTED_UNIT &&
                op->kind != WAR3_NATIVE_OP_JASS_UNIT_SCALE &&
                op->kind != WAR3_NATIVE_OP_JASS_TAKE_OWNERSHIP &&
                op->kind != WAR3_NATIVE_OP_JASS_SET_UNIT_INT &&
                op->kind != WAR3_NATIVE_OP_JASS_SET_UNIT_POSITION &&
                op->kind != WAR3_NATIVE_OP_SET_BOUND_ITEM_CHARGES &&
                op->kind != WAR3_NATIVE_OP_BOUND_ABILITY_METADATA &&
                op->kind != WAR3_NATIVE_OP_BOUND_ABILITY_LIST &&
                op->kind != WAR3_NATIVE_OP_BOUND_UNIT_FIELDS &&
                op->kind != WAR3_NATIVE_OP_SET_UNIT_REGEN &&
                op->kind != WAR3_NATIVE_OP_BOUND_INVENTORY &&
                op->kind != WAR3_NATIVE_OP_REPLACE_INVENTORY_ITEM &&
                op->kind != WAR3_NATIVE_OP_WRITE_COMPONENT_FIELDS &&
                op->kind != WAR3_NATIVE_OP_SET_BOUND_HERO_INT &&
                op->kind != WAR3_NATIVE_OP_REPLACE_HERO_SKILL &&
                op->kind != WAR3_NATIVE_OP_MANAGE_BOUND_ABILITY &&
                op->kind != WAR3_NATIVE_OP_BOUND_DIRECT_ABILITY &&
                op->kind != WAR3_NATIVE_OP_START_ABILITY_EFFECT &&
                op->kind != WAR3_NATIVE_OP_FINISH_ABILITY_EFFECT &&
                op->kind != WAR3_NATIVE_OP_ENABLE_BOUND_TOGGLE &&
                op->kind != WAR3_NATIVE_OP_BOUND_WORLD_EFFECT &&
                op->kind != WAR3_NATIVE_OP_SET_BOUND_HERO_BASE &&
                op->kind != WAR3_NATIVE_OP_SET_BOUND_HERO_ATTRIBUTES &&
                op->kind != WAR3_NATIVE_OP_SET_BOUND_HERO_LEVEL &&
                op->kind != WAR3_NATIVE_OP_ADD_BOUND_HERO_SKILL_POINTS &&
                op->kind != WAR3_NATIVE_OP_BOUND_INVENTORY_BATCH &&
                op->kind != WAR3_NATIVE_OP_BOUND_ITEM_CREATE &&
                op->kind != WAR3_NATIVE_OP_BOUND_OWNER_KILL &&
                op->kind != WAR3_NATIVE_OP_BOUND_ABILITY_IDENTITY &&
                op->kind != WAR3_NATIVE_OP_BOUND_INVENTORY_ITEM &&
                !war3_is_internal_ability_op(op->kind) &&
                !war3_is_internal_item_op(op->kind) &&
                !war3_is_item_field_op(op->kind) &&
                !war3_is_ability_field_op(op->kind)) {
                last_error = ERROR_INVALID_DATA;
            } else {
                last_error = war3_validate_unit_identity(&cmd, &cmd.ops[0]);
            }
            if (last_error) {
                op->last_error = last_error;
                goto finish;
            }
            if (op->kind == WAR3_NATIVE_OP_JASS_UNIT_BOOL || op->kind == WAR3_NATIVE_OP_JASS_UNIT_VOID ||
                op->kind == WAR3_NATIVE_OP_JASS_UNIT_INT_QUERY) {
                if (op->arg0 || op->arg1 || op->rawcode > (op->kind == WAR3_NATIVE_OP_JASS_UNIT_BOOL ? 1u : 0u) ||
                    !war3_executable_pointer(op->handler)) {
                    last_error = op->last_error = ERROR_INVALID_PARAMETER;
                    goto finish;
                }
            }
            if (op->kind == WAR3_NATIVE_OP_JASS_UNIT_SCALE || op->kind == WAR3_NATIVE_OP_JASS_SET_UNIT_POSITION ||
                op->kind == WAR3_NATIVE_OP_JASS_TAKE_OWNERSHIP) {
                int bad=!war3_executable_pointer(op->handler);
                if(op->kind==WAR3_NATIVE_OP_JASS_TAKE_OWNERSHIP)
                    bad|=op->rawcode!=0 || !war3_executable_pointer(op->arg0) || !war3_executable_pointer(op->arg1);
                else bad|=op->arg1!=0 || (op->kind==WAR3_NATIVE_OP_JASS_UNIT_SCALE?op->arg0!=0:op->arg0>UINT32_MAX);
                if(bad) {last_error=op->last_error=ERROR_INVALID_PARAMETER;goto finish;}
            }
        }
        if (war3_is_ability_field_op(op->kind)) {
            last_error = i < 3 ? ERROR_INVALID_DATA : war3_validate_bound_ability(&cmd, &ability_field_handle);
            if (last_error) { op->last_error = last_error; goto finish; }
        }
        if (war3_is_internal_ability_op(op->kind) && !war3_executable_pointer(op->handler)) {
            last_error = op->last_error = ERROR_INVALID_PARAMETER;
            goto finish;
        }
        if (war3_is_internal_item_op(op->kind) &&
            (cmd.ops[0].kind == WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY) &&
            (op->kind == WAR3_NATIVE_OP_REMOVE_ITEM_SLOT || op->kind == WAR3_NATIVE_OP_GET_ITEM_TYPE_IN_SLOT) &&
            !war3_executable_pointer(op->handler)) {
            op->last_error = ERROR_INVALID_PARAMETER; last_error = op->last_error; goto finish;
        }
        if (war3_is_item_field_op(op->kind)) {
            last_error = i < 3 ? ERROR_INVALID_DATA : war3_validate_bound_item(&cmd, &item_field_handle);
            if (last_error) { op->last_error = last_error; goto finish; }
        }
        if (
            op->handler == 0 &&
            op->kind != WAR3_NATIVE_OP_QUERY_WORLD_POINT &&
            op->kind != WAR3_NATIVE_OP_BOOTSTRAP_NATIVE_TABLE &&
            op->kind != WAR3_NATIVE_OP_QUERY_NATIVE_TABLE &&
            op->kind != WAR3_NATIVE_OP_BOUND_ABILITY_LIST &&
            op->kind != WAR3_NATIVE_OP_BOUND_UNIT_FIELDS &&
            op->kind != WAR3_NATIVE_OP_SET_UNIT_REGEN &&
            op->kind != WAR3_NATIVE_OP_BOUND_INVENTORY &&
            op->kind != WAR3_NATIVE_OP_SET_BOUND_HERO_ATTRIBUTES &&
            op->kind != WAR3_NATIVE_OP_SET_BOUND_HERO_LEVEL &&
            op->kind != WAR3_NATIVE_OP_ADD_BOUND_HERO_SKILL_POINTS &&
            op->kind != WAR3_NATIVE_OP_BOUND_INVENTORY_BATCH &&
            op->kind != WAR3_NATIVE_OP_BOUND_ITEM_CREATE &&
            op->kind != WAR3_NATIVE_OP_REPLACE_INVENTORY_ITEM &&
            op->kind != WAR3_NATIVE_OP_PERSISTENT_SELECTED_SNAPSHOT
        ) {
            op->last_error = ERROR_INVALID_DATA;
            last_error = ERROR_INVALID_DATA;
            goto finish;
        }
        switch (op->kind) {
            case WAR3_NATIVE_OP_MANAGE_BOUND_ABILITY: {
                last_error=i?war3_manage_bound_ability(&cmd,op):ERROR_INVALID_PARAMETER;
                if(last_error) {op->last_error=last_error;goto finish;}
                break;
            }
            case WAR3_NATIVE_OP_BOUND_DIRECT_ABILITY: {
                last_error=i==1?war3_bound_direct_ability(&cmd,op):ERROR_INVALID_PARAMETER;
                if(last_error) {op->last_error=last_error;goto finish;}
                break;
            }
            case WAR3_NATIVE_OP_START_ABILITY_EFFECT: {
                last_error=i==1?war3_start_ability_effect(&cmd,op):ERROR_INVALID_PARAMETER;
                if(last_error) {op->last_error=last_error;goto finish;}
                ++i;
                break;
            }
            case WAR3_NATIVE_OP_ENABLE_BOUND_TOGGLE: {
                last_error=i==1?war3_enable_bound_toggle(&cmd,op):ERROR_INVALID_PARAMETER;
                if(last_error) {op->last_error=last_error;goto finish;}
                break;
            }
            case WAR3_NATIVE_OP_BOUND_WORLD_EFFECT: {
                last_error=i==1?war3_bound_world_effect(&cmd,op):ERROR_INVALID_PARAMETER;
                if(last_error) {op->last_error=last_error;goto finish;}
                break;
            }
            case WAR3_NATIVE_OP_FINISH_ABILITY_EFFECT: {
                last_error=i==1?war3_finish_ability_effect(&cmd,op):ERROR_INVALID_PARAMETER;
                if(last_error) {op->last_error=last_error;goto finish;}
                break;
            }
            case WAR3_NATIVE_OP_REPLACE_HERO_SKILL: {
                last_error=i==1?war3_replace_hero_skill(&cmd,op):ERROR_INVALID_PARAMETER;
                if(last_error) { op->last_error=last_error;goto finish; }
                break;
            }
            case WAR3_NATIVE_OP_SET_BOUND_HERO_INT: {
                last_error=i==1?war3_set_bound_hero_int(&cmd,op):ERROR_INVALID_PARAMETER;
                if(last_error) { op->last_error=last_error;goto finish; }
                break;
            }
            case WAR3_NATIVE_OP_SET_BOUND_HERO_BASE: {
                last_error=i==1?war3_set_bound_hero_base(&cmd):ERROR_INVALID_PARAMETER;
                if(last_error) {op->last_error=last_error;goto finish;}
                i=cmd.op_count-1;
                break;
            }
            case WAR3_NATIVE_OP_SET_BOUND_HERO_ATTRIBUTES: {
                last_error=i==1?war3_set_bound_hero_attributes(&cmd,op):ERROR_INVALID_PARAMETER;
                if(last_error) {op->last_error=last_error;goto finish;}
                break;
            }
            case WAR3_NATIVE_OP_SET_BOUND_HERO_LEVEL: {
                last_error=i==1?war3_set_bound_hero_level(&cmd,op):ERROR_INVALID_PARAMETER;
                if(last_error) {op->last_error=last_error;goto finish;}
                break;
            }
            case WAR3_NATIVE_OP_ADD_BOUND_HERO_SKILL_POINTS: {
                last_error=i==1?war3_add_bound_hero_skill_points(&cmd,op):ERROR_INVALID_PARAMETER;
                if(last_error) {op->last_error=last_error;goto finish;}
                break;
            }
            case WAR3_NATIVE_OP_BOUND_INVENTORY_BATCH: {
                last_error=i==1?war3_bound_inventory_batch(&cmd,op):ERROR_INVALID_PARAMETER;
                if(last_error) {op->last_error=last_error;goto finish;}
                break;
            }
            case WAR3_NATIVE_OP_BOUND_ITEM_CREATE: {
                last_error=i==1?war3_bound_item_create(&cmd,op):ERROR_INVALID_PARAMETER;
                if(last_error) {op->last_error=last_error;goto finish;}
                break;
            }
            case WAR3_NATIVE_OP_BOUND_OWNER_KILL: {
                last_error=i==1?war3_bound_owner_kill(&cmd,op):ERROR_INVALID_PARAMETER;
                if(last_error) {op->last_error=last_error;goto finish;}
                break;
            }
            case WAR3_NATIVE_OP_WRITE_COMPONENT_FIELDS: {
                last_error=i==1?war3_write_component_fields(&cmd):ERROR_INVALID_PARAMETER;
                if(last_error) { op->last_error=last_error;goto finish; }
                i=cmd.op_count-1;
                break;
            }
            case WAR3_NATIVE_OP_REPLACE_INVENTORY_ITEM: {
                last_error=(i==1 && cmd.op_count==3) ? war3_replace_inventory_item(&cmd) : ERROR_INVALID_DATA;
                if(last_error) { op->last_error=last_error;goto finish; }
                ++i;
                break;
            }
            case WAR3_NATIVE_OP_BOUND_INVENTORY: {
                if (i != 1 || cmd.op_count != 2 || cmd.ops[0].kind != WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY) {
                    last_error = ERROR_INVALID_DATA;
                } else {
                    extra_results = (uint64_t *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY,
                        WAR3_BOUND_INVENTORY_QWORDS*sizeof(uint64_t));
                    last_error = extra_results ? war3_bound_inventory(&cmd, extra_results) : ERROR_OUTOFMEMORY;
                }
                if (last_error) { op->last_error=last_error; goto finish; }
                extra_result_count=WAR3_BOUND_INVENTORY_QWORDS;op->result=6;
                break;
            }
            case WAR3_NATIVE_OP_SET_UNIT_REGEN: {
                War3RegenProperties properties;
                uint32_t bits[2] = {(uint32_t)op->arg0, (uint32_t)op->arg1};
                if (cmd.ops[0].kind != WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY ||
                    !op->rawcode || op->rawcode > 3 || op->arg0 > UINT32_MAX || op->arg1 > UINT32_MAX) {
                    last_error = ERROR_INVALID_PARAMETER;
                } else {
                    last_error = war3_regen_properties(cmd.ops[0].arg1, &properties);
                }
                /* Validate both requested fields before changing either. */
                for (unsigned k=0; !last_error && k<2; ++k) {
                    if (!(op->rawcode & (1u<<k))) continue;
                    MEMORY_BASIC_INFORMATION region;
                    uint64_t address = properties.address[k] + 0xd4;
                    if (!properties.address[k]) last_error = ERROR_NOT_FOUND;
                    else if ((bits[k] & 0x7f800000u) == 0x7f800000u) last_error = ERROR_INVALID_PARAMETER;
                    else if (VirtualQuery((void *)(uintptr_t)address, &region, sizeof(region)) != sizeof(region) ||
                        !(region.Protect & (PAGE_READWRITE | PAGE_WRITECOPY | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY)))
                        last_error = ERROR_ACCESS_DENIED;
                }
                if (!last_error) last_error = war3_validate_unit_identity(&cmd, &cmd.ops[0]);
                if (last_error) { op->last_error = last_error; goto finish; }
                for (unsigned k=0; k<2; ++k)
                    if (op->rawcode & (1u<<k)) *(uint32_t *)(uintptr_t)(properties.address[k]+0xd4) = bits[k];
                op->result = op->rawcode;
                break;
            }
            case WAR3_NATIVE_OP_BOUND_UNIT_FIELDS: {
                if (i != 1 || cmd.op_count != 2 || cmd.ops[0].kind != WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY) {
                    last_error = ERROR_INVALID_DATA;
                } else {
                    extra_results = (uint64_t *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY,
                        WAR3_BOUND_UNIT_FIELD_QWORDS * sizeof(uint64_t));
                    last_error = extra_results ? war3_bound_unit_fields(&cmd, extra_results) : ERROR_OUTOFMEMORY;
                }
                if (last_error) { op->last_error = last_error; goto finish; }
                extra_result_count = WAR3_BOUND_UNIT_FIELD_QWORDS;
                op->result = extra_result_count;
                break;
            }
            case WAR3_NATIVE_OP_SET_BOUND_ITEM_CHARGES: {
                JassUnitItemInSlotFn slot_fn = (JassUnitItemInSlotFn)(uintptr_t)war3_persistent_native_handler("UnitItemInSlot");
                JassSetItemChargesFn setter = (JassSetItemChargesFn)(uintptr_t)war3_persistent_native_handler("SetItemCharges");
                JassGetItemChargesFn getter = (JassGetItemChargesFn)(uintptr_t)war3_persistent_native_handler("GetItemCharges");
                JassUnitHandleResolveFn resolver = (JassUnitHandleResolveFn)(uintptr_t)g_persistent_item_resolver;
                uint64_t item, object, full;
                const NativeOp *identity = i + 1 < cmd.op_count ? &cmd.ops[i + 1] : NULL;
                int32_t actual;
                if (cmd.ops[0].kind != WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY ||
                    !identity || identity->kind != WAR3_NATIVE_OP_BOUND_ITEM_IDENTITY || !identity->handler ||
                    op->rawcode >= 6u || !op->arg0 || !op->handler || op->arg1 > 0x7fffffffu) {
                    last_error = ERROR_INVALID_PARAMETER;
                } else if (!war3_executable_pointer((uint64_t)(uintptr_t)slot_fn) ||
                           !war3_executable_pointer((uint64_t)(uintptr_t)setter) ||
                           !war3_executable_pointer((uint64_t)(uintptr_t)getter) ||
                           !war3_executable_pointer(g_persistent_item_resolver)) {
                    last_error = ERROR_PROC_NOT_FOUND;
                } else {
                    __try {
                        item = slot_fn(cmd.unit_handle, (int32_t)op->rawcode);
                        object = item ? resolver(item) : 0;
                        if (item != op->arg0 || object != op->handler ||
                            *(uint64_t *)(uintptr_t)(object + 0x18) != identity->handler) {
                            last_error = ERROR_INVALID_HANDLE;
                        } else {
                            full = *(uint64_t *)(uintptr_t)(object + 0x18);
                            setter(item, (int32_t)op->arg1);
                            last_error = war3_validate_unit_identity(&cmd, &cmd.ops[0]);
                            if (!last_error && (slot_fn(cmd.unit_handle, (int32_t)op->rawcode) != item ||
                                resolver(item) != object || *(uint64_t *)(uintptr_t)(object + 0x18) != full)) {
                                last_error = ERROR_INVALID_HANDLE;
                            }
                            if (!last_error) {
                                actual = getter(item);
                                op->result = (uint32_t)actual;
                                if (actual != (int32_t)op->arg1) last_error = ERROR_INVALID_DATA;
                            }
                        }
                    } __except (EXCEPTION_EXECUTE_HANDLER) {
                        last_error = GetExceptionCode();
                    }
                }
                if (last_error) {
                    op->last_error = last_error;
                    goto finish;
                }
                ++i; /* Consume the immutable item-generation descriptor. */
                break;
            }
            case WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY: {
                last_error = (i != 0 || cmd.op_count < 2)
                    ? ERROR_INVALID_DATA : war3_validate_unit_identity(&cmd, op);
                if (last_error) {
                    op->last_error = last_error;
                    goto finish;
                }
                op->result = 1;
                break;
            }
            case WAR3_NATIVE_OP_BOUND_INVENTORY_ITEM: {
                last_error = i != 1 ? ERROR_INVALID_DATA : war3_validate_bound_item(&cmd, &item_field_handle);
                if (last_error) { op->last_error = last_error; goto finish; }
                op->result = item_field_handle;
                ++i;
                break;
            }
            case WAR3_NATIVE_OP_BOUND_ABILITY_IDENTITY: {
                last_error = i != 1 ? ERROR_INVALID_DATA : war3_validate_bound_ability(&cmd, &ability_field_handle);
                if (last_error) { op->last_error = last_error; goto finish; }
                op->result = ability_field_handle;
                ++i; /* Context is a descriptor, never a separately executable op. */
                break;
            }
            case WAR3_NATIVE_OP_BOUND_ABILITY_LIST: {
                NativeOp query = {0};
                uint32_t count = 0;
                uint64_t handle = 0;
                JassGetUnitAbilityByIndexFn by_index = (JassGetUnitAbilityByIndexFn)(uintptr_t)war3_persistent_native_handler("BlzGetUnitAbilityByIndex");
                JassUnitIntQueryFn get_id = (JassUnitIntQueryFn)(uintptr_t)war3_persistent_native_handler("BlzGetAbilityId");
                if (i != 1 || cmd.op_count != 2 || cmd.ops[0].kind != WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY ||
                    !war3_executable_pointer((uint64_t)(uintptr_t)by_index) ||
                    !war3_executable_pointer((uint64_t)(uintptr_t)get_id)) {
                    last_error = ERROR_INVALID_PARAMETER;
                } else {
                    extra_results = (uint64_t *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY,
                        WAR3_PERSISTENT_SNAPSHOT_ENUM_LIMIT * 10u * sizeof(uint64_t));
                    if (!extra_results) last_error = ERROR_OUTOFMEMORY;
                }
                if (last_error) { op->last_error = last_error; goto finish; }
                query.kind = WAR3_NATIVE_OP_BOUND_ABILITY_METADATA;
                query.handler = (uint64_t)(uintptr_t)by_index;
                query.arg0 = (uint64_t)(uintptr_t)get_id;
                __try {
                    for (; count < WAR3_PERSISTENT_SNAPSHOT_ENUM_LIMIT; ++count) {
                        handle = by_index(cmd.unit_handle, (int32_t)count);
                        if (!handle) break;
                        query.rawcode = (uint32_t)get_id(handle);
                        query.arg1 = count + 1u;
                        last_error = war3_bound_ability_metadata(&cmd, &query, extra_results + count*10u);
                        if (last_error) break;
                        if (extra_results[count*10u] != handle) { last_error = ERROR_INVALID_HANDLE; break; }
                    }
                    if (!last_error && count == WAR3_PERSISTENT_SNAPSHOT_ENUM_LIMIT && by_index(cmd.unit_handle, (int32_t)count))
                        last_error = ERROR_MORE_DATA;
                    if (!last_error) last_error = war3_validate_unit_identity(&cmd, &cmd.ops[0]);
                } __except (EXCEPTION_EXECUTE_HANDLER) { last_error = ERROR_INVALID_ADDRESS; }
                if (last_error) { op->last_error = last_error; goto finish; }
                extra_result_count = count*10u;
                op->result = count;
                break;
            }
            case WAR3_NATIVE_OP_BOUND_ABILITY_METADATA: {
                if (i != 1 || cmd.op_count != 2 || cmd.ops[0].kind != WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY) {
                    last_error = ERROR_INVALID_DATA;
                } else {
                    extra_results = (uint64_t *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, 10u*sizeof(uint64_t));
                    last_error = extra_results ? war3_bound_ability_metadata(&cmd, op, extra_results) : ERROR_OUTOFMEMORY;
                }
                if (last_error) { op->last_error = last_error; goto finish; }
                extra_result_count = 10;
                op->result = extra_results[0];
                break;
            }
            case WAR3_NATIVE_OP_BOOTSTRAP_NATIVE_TABLE: {
                size_t count = sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]);
                if (cmd.op_count != 1 || op->rawcode != WAR3_BOOTSTRAP_PROFILE_ID) {
                    last_error = ERROR_REVISION_MISMATCH;
                } else {
                    extra_results = (uint64_t *)HeapAlloc(GetProcessHeap(), 0, (count + 3u)*sizeof(uint64_t));
                    last_error = extra_results ? war3_bootstrap_refresh() : ERROR_OUTOFMEMORY;
                }
                if (last_error) { op->last_error = last_error; goto finish; }
                extra_results[0] = g_persistent_unit_resolver;
                extra_results[1] = g_persistent_item_resolver;
                extra_results[2] = g_persistent_agent_resolver;
                for (size_t n = 0; n < count; ++n) extra_results[n+3] = g_persistent_natives[n].handler;
                extra_result_count = (uint32_t)count + 3u;
                op->result = count;
                break;
            }
            case WAR3_NATIVE_OP_QUERY_NATIVE_TABLE: {
                uint8_t *image, *table;
                last_error = op->arg0 != WAR3_BOOTSTRAP_PROFILE_ID ? ERROR_REVISION_MISMATCH :
                    war3_bootstrap_context(&image, &table);
                if (!last_error) last_error = war3_bootstrap_query(image, table, op->rawcode, &op->result);
                if (last_error) { op->last_error = last_error; goto finish; }
                break;
            }
            case WAR3_NATIVE_OP_PERSISTENT_REGISTER_NATIVE: {
                size_t native_count =
                    sizeof(g_persistent_natives) / sizeof(g_persistent_natives[0]);
                if (op->rawcode >= native_count || !war3_executable_pointer(op->handler)) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = op->last_error;
                    goto finish;
                }
                g_persistent_natives[op->rawcode].name =
                    g_persistent_native_names[op->rawcode];
                g_persistent_natives[op->rawcode].handler = op->handler;
                if (op->rawcode == 0u && op->arg0) {
                    if (!war3_executable_pointer(op->arg0)) {
                        op->last_error = ERROR_INVALID_PARAMETER;
                        last_error = op->last_error;
                        goto finish;
                    }
                    g_persistent_unit_resolver = op->arg0;
                }
                if (op->rawcode == 0u && op->arg1) {
                    if (!war3_executable_pointer(op->arg1)) {
                        op->last_error = ERROR_INVALID_PARAMETER;
                        last_error = op->last_error;
                        goto finish;
                    }
                    g_persistent_item_resolver = op->arg1;
                }
                if (op->rawcode == 1u && op->arg0) {
                    if (!war3_executable_pointer(op->arg0)) {
                        op->last_error = ERROR_INVALID_PARAMETER;
                        last_error = op->last_error;
                        goto finish;
                    }
                    g_persistent_agent_resolver = op->arg0;
                }
                InterlockedExchange(&g_persistent_ready, 0);
                op->result = op->handler;
                break;
            }
            case WAR3_NATIVE_OP_IDENTITY_UNIT_SNAPSHOT:
            case WAR3_NATIVE_OP_PERSISTENT_UNIT_SNAPSHOT:
            case WAR3_NATIVE_OP_PERSISTENT_SELECTED_SNAPSHOT: {
                if(op->kind==WAR3_NATIVE_OP_IDENTITY_UNIT_SNAPSHOT) {
                    last_error=war3_identity_unit_handle(&cmd,op);
                    if(last_error) {op->last_error=last_error;goto finish;}
                }
                last_error = war3_persistent_selected_snapshot(
                    &cmd,
                    op,
                    &extra_results,
                    &extra_result_count
                );
                if (last_error) {
                    op->last_error = last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_INTERNAL_ABILITY_BEGIN:
            case WAR3_NATIVE_OP_INTERNAL_ABILITY_END:
            case WAR3_NATIVE_OP_INTERNAL_ABILITY_REFRESH: {
                InternalAbilityUnitFn fn = (InternalAbilityUnitFn)(uintptr_t)op->handler;
                if (internal_unit == 0) {
                    op->last_error = ERROR_INVALID_ADDRESS;
                    last_error = ERROR_INVALID_ADDRESS;
                    goto finish;
                }
                __try {
                    fn(internal_unit);
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
                if (internal_unit == 0) {
                    op->last_error = ERROR_INVALID_ADDRESS;
                    last_error = ERROR_INVALID_ADDRESS;
                    goto finish;
                }
                __try {
                    op->result = fn(internal_unit, op->rawcode, 0, 1, 1, 1, 0);
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_INTERNAL_ABILITY_ADD: {
                InternalAbilityAddFn fn = (InternalAbilityAddFn)(uintptr_t)op->handler;
                if (internal_unit == 0) {
                    op->last_error = ERROR_INVALID_ADDRESS;
                    last_error = ERROR_INVALID_ADDRESS;
                    goto finish;
                }
                __try {
                    op->result = fn(internal_unit, op->rawcode, 0, 0, 0, 0);
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
                if (internal_unit == 0) {
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
                        internal_unit,
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
                    fn(internal_unit, op->arg0);
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
                if (internal_unit == 0 || remove_item == 0) {
                    op->last_error = ERROR_INVALID_ADDRESS;
                    last_error = ERROR_INVALID_ADDRESS;
                    goto finish;
                }
                __try {
                    item = unit_item_in_slot(internal_unit, slot);
                    op->result = item;
                    if (item != 0) {
                        uint64_t vtable = 0;
                        InternalItemPreRemoveFn pre_remove = NULL;
                        InternalItemRemoveFn remove_world_item = NULL;
                        op->arg1 = remove_item(internal_unit, item);
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
                int32_t slot = (int32_t)op->arg1;
                float x = 0.0f;
                float y = 0.0f;
                uint64_t item = 0;
                if (internal_unit == 0 || unit_add_item_to_slot == 0) {
                    op->last_error = ERROR_INVALID_ADDRESS;
                    last_error = ERROR_INVALID_ADDRESS;
                    goto finish;
                }
                if (op->arg1 >= 6u) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = op->last_error;
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
                    /* Match UnitAddItemToSlotById: the fifth stack argument is
                       read by the inventory eligibility check. Never omit it. */
                    op->arg1 = unit_add_item_to_slot(internal_unit, item, slot, 1, 0);
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
                if (internal_unit == 0) {
                    op->last_error = ERROR_INVALID_ADDRESS;
                    last_error = ERROR_INVALID_ADDRESS;
                    goto finish;
                }
                __try {
                    item = unit_item_in_slot(internal_unit, slot);
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
            case WAR3_NATIVE_OP_JASS_SELECTED_UNITS: {
                last_error = run_jass_selected_units(
                    &cmd,
                    i,
                    &extra_results,
                    &extra_result_count
                );
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
                if (!cmd.unit_handle || !(scale > 0.0f) || scale > 100.0f ||
                    (cmd.ops[0].kind==WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY && scale<0.01f)) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = ERROR_INVALID_PARAMETER;
                    goto finish;
                }
                __try {
                    float x = scale;
                    float y = scale;
                    float z = scale;
                    fn(cmd.unit_handle, &x, &y, &z);
                    if(cmd.ops[0].kind==WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY) {
                        last_error=war3_validate_unit_identity(&cmd,&cmd.ops[0]);
                        if(last_error) {op->last_error=last_error;goto finish;}
                    }
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
                    if (cmd.ops[0].kind == WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY) {
                        last_error = war3_validate_unit_identity(&cmd, &cmd.ops[0]);
                        if (last_error) { op->last_error = last_error; goto finish; }
                    }
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
                    if(cmd.ops[0].kind==WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY) {
                        last_error=war3_validate_unit_identity(&cmd,&cmd.ops[0]);
                        if(last_error) {op->last_error=last_error;goto finish;}
                    }
                    if (!player) {
                        op->last_error = ERROR_NOT_FOUND;
                        last_error = ERROR_NOT_FOUND;
                        goto finish;
                    }
                    set_unit_owner(cmd.unit_handle, player, 1u);
                    if(cmd.ops[0].kind==WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY) {
                        last_error=war3_validate_unit_identity(&cmd,&cmd.ops[0]);
                        if(last_error) {op->last_error=last_error;goto finish;}
                        uint64_t actual=((JassGetOwningPlayerFn)(uintptr_t)op->arg1)(cmd.unit_handle);
                        last_error=war3_validate_unit_identity(&cmd,&cmd.ops[0]);
                        if(!last_error && actual!=player) last_error=ERROR_CAN_NOT_COMPLETE;
                        if(last_error) {op->last_error=last_error;goto finish;}
                    }
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
            case WAR3_NATIVE_OP_JASS_CLONE_SELECTED_UNIT: {
                NativeOp *d1;
                NativeOp *d2;
                NativeOp *d3;
                NativeOp *d4;
                NativeOp *d5;
                NativeOp *d6;
                NativeOp *d7;
                NativeOp *d8;
                NativeOp *d9;
                NativeOp *d10;
                NativeOp *d11;
                NativeOp *d12;
                NativeOp *d13;
                JassNoArgU64Fn get_local_player;
                JassGetOwningPlayerFn get_owning_player;
                JassCreateUnitFn create_unit;
                JassUnitRealQueryFn get_unit_facing;
                JassUnitIntFn get_hero_level;
                JassSetHeroLevelFn set_hero_level;
                JassUnitIntFn get_hero_xp;
                JassSetHeroXPFn set_hero_xp;
                JassGetHeroStatFn get_hero_str;
                JassSetHeroStatFn set_hero_str;
                JassGetHeroStatFn get_hero_agi;
                JassSetHeroStatFn set_hero_agi;
                JassGetHeroStatFn get_hero_int;
                JassSetHeroStatFn set_hero_int;
                JassUnitIntFn get_hero_skill_points;
                JassUnitModifySkillPointsFn modify_skill_points;
                JassUnitIntFn get_unit_max_hp;
                JassUnitSetIntFn set_unit_max_hp;
                JassUnitRealQueryFn get_widget_life;
                JassSetWidgetLifeFn set_widget_life;
                JassUnitIntFn get_unit_max_mana;
                JassUnitSetIntFn set_unit_max_mana;
                JassUnitStateQueryFn get_unit_state;
                JassSetUnitStateFn set_unit_state;
                JassUnitItemInSlotFn unit_item_in_slot;
                JassGetItemTypeIdFn get_item_type_id;
                JassUnitRawcodeFn unit_add_item_by_id;
                JassGetItemChargesFn get_item_charges;
                JassSetItemChargesFn set_item_charges;
                JassItemFieldGetFn get_item_integer_field;
                JassItemScalarFieldSetFn set_item_integer_field;
                JassItemFieldGetFn get_item_real_field;
                JassItemRealFieldSetFn set_item_real_field;
                JassItemFieldGetFn get_item_boolean_field;
                JassItemScalarFieldSetFn set_item_boolean_field;
                JassGetUnitAbilityByIndexFn get_ability_by_index;
                JassGetAbilityIdFn get_ability_id;
                JassGetUnitAbilityLevelFn get_ability_level;
                JassUnitAddAbilityFn add_ability;
                JassSetUnitAbilityLevelFn set_ability_level;
                JassGetUnitTypeIdFn get_unit_type_id;
                JassUnitVoidFn remove_unit;
                uint64_t player = 0;
                uint64_t target = 0;
                float coordinates[2] = {0.0f, 0.0f};
                float facing = 0.0f;
                uint32_t copied_items = 0;
                uint32_t copied_abilities = 0;
                uint32_t clone_flags;
                DWORD clone_error = ERROR_SUCCESS;
                uint64_t clone_phase = 0;
                War3CloneGuard clone_guard={0};
                clone_guard.source=i==1?&cmd:NULL;

                if (
                    !((i==0 && cmd.op_count==14) ||
                      (i==1 && cmd.op_count==15 && cmd.ops[0].kind==WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY)) || !cmd.unit_handle ||
                    !op->rawcode || i + 13 >= cmd.op_count
                ) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = op->last_error;
                    goto finish;
                }
                d1 = &cmd.ops[i + 1];
                d2 = &cmd.ops[i + 2];
                d3 = &cmd.ops[i + 3];
                d4 = &cmd.ops[i + 4];
                d5 = &cmd.ops[i + 5];
                d6 = &cmd.ops[i + 6];
                d7 = &cmd.ops[i + 7];
                d8 = &cmd.ops[i + 8];
                d9 = &cmd.ops[i + 9];
                d10 = &cmd.ops[i + 10];
                d11 = &cmd.ops[i + 11];
                d12 = &cmd.ops[i + 12];
                d13 = &cmd.ops[i + 13];
                clone_flags = d1->rawcode;
                if (
                    clone_flags & ~(
                        WAR3_CLONE_FLAG_HERO |
                        WAR3_CLONE_FLAG_INVENTORY |
                        WAR3_CLONE_FLAG_PRESERVE_OWNER
                    )
                ) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = op->last_error;
                    goto finish;
                }
                for (uint32_t descriptor = 1; descriptor <= 13; ++descriptor) {
                    NativeOp *descriptor_op = &cmd.ops[i + descriptor];
                    if (descriptor_op->kind != WAR3_NATIVE_OP_JASS_MULTI_ARG) {
                        op->last_error = ERROR_INVALID_DATA;
                        last_error = op->last_error;
                        goto finish;
                    }
                }

                get_local_player = (JassNoArgU64Fn)(uintptr_t)op->handler;
                get_owning_player = (JassGetOwningPlayerFn)(uintptr_t)op->handler;
                create_unit = (JassCreateUnitFn)(uintptr_t)op->arg0;
                get_unit_facing = (JassUnitRealQueryFn)(uintptr_t)d1->handler;
                get_hero_level = (JassUnitIntFn)(uintptr_t)d1->arg0;
                set_hero_level = (JassSetHeroLevelFn)(uintptr_t)d1->arg1;
                get_hero_xp = (JassUnitIntFn)(uintptr_t)d2->handler;
                set_hero_xp = (JassSetHeroXPFn)(uintptr_t)d2->arg0;
                get_hero_str = (JassGetHeroStatFn)(uintptr_t)d2->arg1;
                set_hero_str = (JassSetHeroStatFn)(uintptr_t)d3->handler;
                get_hero_agi = (JassGetHeroStatFn)(uintptr_t)d3->arg0;
                set_hero_agi = (JassSetHeroStatFn)(uintptr_t)d3->arg1;
                get_hero_int = (JassGetHeroStatFn)(uintptr_t)d4->handler;
                set_hero_int = (JassSetHeroStatFn)(uintptr_t)d4->arg0;
                get_hero_skill_points = (JassUnitIntFn)(uintptr_t)d4->arg1;
                modify_skill_points = (JassUnitModifySkillPointsFn)(uintptr_t)d5->handler;
                get_unit_max_hp = (JassUnitIntFn)(uintptr_t)d5->arg0;
                set_unit_max_hp = (JassUnitSetIntFn)(uintptr_t)d5->arg1;
                get_widget_life = (JassUnitRealQueryFn)(uintptr_t)d6->handler;
                set_widget_life = (JassSetWidgetLifeFn)(uintptr_t)d6->arg0;
                get_unit_max_mana = (JassUnitIntFn)(uintptr_t)d6->arg1;
                set_unit_max_mana = (JassUnitSetIntFn)(uintptr_t)d7->handler;
                get_unit_state = (JassUnitStateQueryFn)(uintptr_t)d7->arg0;
                set_unit_state = (JassSetUnitStateFn)(uintptr_t)d7->arg1;
                unit_item_in_slot = (JassUnitItemInSlotFn)(uintptr_t)d8->handler;
                get_item_type_id = (JassGetItemTypeIdFn)(uintptr_t)d8->arg0;
                unit_add_item_by_id = (JassUnitRawcodeFn)(uintptr_t)d8->arg1;
                get_item_charges = (JassGetItemChargesFn)(uintptr_t)d9->handler;
                set_item_charges = (JassSetItemChargesFn)(uintptr_t)d9->arg0;
                get_item_integer_field = (JassItemFieldGetFn)(uintptr_t)d9->arg1;
                set_item_integer_field = (JassItemScalarFieldSetFn)(uintptr_t)d10->handler;
                get_item_real_field = (JassItemFieldGetFn)(uintptr_t)d10->arg0;
                set_item_real_field = (JassItemRealFieldSetFn)(uintptr_t)d10->arg1;
                get_item_boolean_field = (JassItemFieldGetFn)(uintptr_t)d11->handler;
                set_item_boolean_field = (JassItemScalarFieldSetFn)(uintptr_t)d11->arg0;
                get_ability_by_index = (JassGetUnitAbilityByIndexFn)(uintptr_t)d11->arg1;
                get_ability_id = (JassGetAbilityIdFn)(uintptr_t)d12->handler;
                get_ability_level = (JassGetUnitAbilityLevelFn)(uintptr_t)d12->arg0;
                add_ability = (JassUnitAddAbilityFn)(uintptr_t)d12->arg1;
                set_ability_level = (JassSetUnitAbilityLevelFn)(uintptr_t)d13->handler;
                get_unit_type_id = (JassGetUnitTypeIdFn)(uintptr_t)d13->arg0;
                remove_unit = (JassUnitVoidFn)(uintptr_t)d13->arg1;

                if (
                    !war3_executable_pointer(op->handler) ||
                    !war3_executable_pointer(op->arg0) ||
                    !war3_executable_pointer(d1->handler) ||
                    !war3_executable_pointer(d5->arg0) ||
                    !war3_executable_pointer(d5->arg1) ||
                    !war3_executable_pointer(d6->handler) ||
                    !war3_executable_pointer(d6->arg0) ||
                    !war3_executable_pointer(d6->arg1) ||
                    !war3_executable_pointer(d7->handler) ||
                    !war3_executable_pointer(d7->arg0) ||
                    !war3_executable_pointer(d7->arg1) ||
                    !war3_executable_pointer(d11->arg1) ||
                    !war3_executable_pointer(d12->handler) ||
                    !war3_executable_pointer(d12->arg0) ||
                    !war3_executable_pointer(d12->arg1) ||
                    !war3_executable_pointer(d13->handler) ||
                    !war3_executable_pointer(d13->arg0) ||
                    !war3_executable_pointer(d13->arg1)
                ) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = op->last_error;
                    goto finish;
                }
                if (
                    (clone_flags & WAR3_CLONE_FLAG_HERO) &&
                    (
                        !war3_executable_pointer(d1->arg0) ||
                        !war3_executable_pointer(d1->arg1) ||
                        !war3_executable_pointer(d2->handler) ||
                        !war3_executable_pointer(d2->arg0) ||
                        !war3_executable_pointer(d2->arg1) ||
                        !war3_executable_pointer(d3->handler) ||
                        !war3_executable_pointer(d3->arg0) ||
                        !war3_executable_pointer(d3->arg1) ||
                        !war3_executable_pointer(d4->handler) ||
                        !war3_executable_pointer(d4->arg0) ||
                        !war3_executable_pointer(d4->arg1) ||
                        !war3_executable_pointer(d5->handler)
                    )
                ) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = op->last_error;
                    goto finish;
                }
                if (
                    (clone_flags & WAR3_CLONE_FLAG_INVENTORY) &&
                    (
                        !war3_executable_pointer(d8->handler) ||
                        !war3_executable_pointer(d8->arg0) ||
                        !war3_executable_pointer(d8->arg1) ||
                        !war3_executable_pointer(d9->handler) ||
                        !war3_executable_pointer(d9->arg0) ||
                        !war3_executable_pointer(d9->arg1) ||
                        !war3_executable_pointer(d10->handler) ||
                        !war3_executable_pointer(d10->arg0) ||
                        !war3_executable_pointer(d10->arg1) ||
                        !war3_executable_pointer(d11->handler) ||
                        !war3_executable_pointer(d11->arg0)
                    )
                ) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = op->last_error;
                    goto finish;
                }

                memcpy(coordinates, &op->arg1, sizeof(coordinates));
                __try {
                    int32_t source_level;
                    war3_clone_check(&clone_guard);
                    if(!(coordinates[0]>=-1000000.0f && coordinates[0]<=1000000.0f &&
                         coordinates[1]>=-1000000.0f && coordinates[1]<=1000000.0f)) {
                        clone_error=ERROR_INVALID_PARAMETER;__leave;
                    }
                    if (WAR3_CLONE_VALUE(&clone_guard, get_unit_type_id(cmd.unit_handle)) != op->rawcode) {
                        clone_error = ERROR_INVALID_DATA;
                        __leave;
                    }
                    player = (
                        clone_flags & WAR3_CLONE_FLAG_PRESERVE_OWNER
                        ? WAR3_CLONE_VALUE(&clone_guard, get_owning_player(cmd.unit_handle))
                        : WAR3_CLONE_VALUE(&clone_guard, get_local_player())
                    );
                    facing = war3_real_from_bits(WAR3_CLONE_VALUE(&clone_guard, get_unit_facing(cmd.unit_handle)));
                    if (!player || !(facing == facing)) {
                        clone_error = ERROR_NOT_FOUND;
                        __leave;
                    }
                    if(clone_flags & WAR3_CLONE_FLAG_INVENTORY) {
                        op->result=clone_phase=0x100u;
                        war3_clone_prepare_items(&clone_guard,unit_item_in_slot);
                    }
                    op->result=clone_phase=0x200u;
                    target = create_unit(
                        player,
                        op->rawcode,
                        &coordinates[0],
                        &coordinates[1],
                        &facing
                    );
                    if (!target) {
                        clone_error = ERROR_NOT_FOUND;
                        __leave;
                    }

                    clone_error=war3_clone_capture_target(&clone_guard,target);
                    if(clone_error) __leave;
                    op->result=clone_phase=0x300u;
                    war3_clone_check(&clone_guard);
                    war3_clone_check_saved_items(&clone_guard);

                    source_level = (clone_flags & WAR3_CLONE_FLAG_HERO)
                        ? WAR3_CLONE_VALUE(&clone_guard, get_hero_level(cmd.unit_handle))
                        : 0;
                    if (
                        (clone_flags & WAR3_CLONE_FLAG_HERO) &&
                        source_level > 0
                    ) {
                        int32_t source_xp = WAR3_CLONE_VALUE(&clone_guard, get_hero_xp(cmd.unit_handle));
                        int32_t source_points;
                        int32_t target_points;
                        WAR3_CLONE_VOID(&clone_guard, set_hero_xp(target, source_xp, 0));
                        if (WAR3_CLONE_VALUE(&clone_guard, get_hero_level(target)) != source_level) {
                            WAR3_CLONE_VOID(&clone_guard, set_hero_level(target, source_level, 0));
                        }
                        if (WAR3_CLONE_VALUE(&clone_guard, get_hero_xp(target)) != source_xp) {
                            WAR3_CLONE_VOID(&clone_guard, set_hero_xp(target, source_xp, 0));
                        }
                        WAR3_CLONE_VOID(&clone_guard, set_hero_str(target, WAR3_CLONE_VALUE(&clone_guard, get_hero_str(cmd.unit_handle, 0)), 1));
                        WAR3_CLONE_VOID(&clone_guard, set_hero_agi(target, WAR3_CLONE_VALUE(&clone_guard, get_hero_agi(cmd.unit_handle, 0)), 1));
                        WAR3_CLONE_VOID(&clone_guard, set_hero_int(target, WAR3_CLONE_VALUE(&clone_guard, get_hero_int(cmd.unit_handle, 0)), 1));
                        source_points = WAR3_CLONE_VALUE(&clone_guard, get_hero_skill_points(cmd.unit_handle));
                        target_points = WAR3_CLONE_VALUE(&clone_guard, get_hero_skill_points(target));
                        if (source_points != target_points) {
                            if (!WAR3_CLONE_VALUE(&clone_guard, modify_skill_points(
                                target,
                                source_points - target_points
                            ))) {
                                clone_error = ERROR_WRITE_FAULT;
                                __leave;
                            }
                        }
                        if (
                            WAR3_CLONE_VALUE(&clone_guard, get_hero_level(target)) != source_level ||
                            WAR3_CLONE_VALUE(&clone_guard, get_hero_xp(target)) != source_xp ||
                            WAR3_CLONE_VALUE(&clone_guard, get_hero_str(target, 0)) !=
                                WAR3_CLONE_VALUE(&clone_guard, get_hero_str(cmd.unit_handle, 0)) ||
                            WAR3_CLONE_VALUE(&clone_guard, get_hero_agi(target, 0)) !=
                                WAR3_CLONE_VALUE(&clone_guard, get_hero_agi(cmd.unit_handle, 0)) ||
                            WAR3_CLONE_VALUE(&clone_guard, get_hero_int(target, 0)) !=
                                WAR3_CLONE_VALUE(&clone_guard, get_hero_int(cmd.unit_handle, 0)) ||
                            WAR3_CLONE_VALUE(&clone_guard, get_hero_skill_points(target)) != source_points
                        ) {
                            clone_error = ERROR_WRITE_FAULT;
                            __leave;
                        }
                    }

                    if (clone_flags & WAR3_CLONE_FLAG_INVENTORY) {
                    for (int32_t slot = 0; slot < 6; ++slot) {
                        op->result=clone_phase=0x500u+(uint32_t)slot;
                        war3_clone_begin_item(&clone_guard,(unsigned)slot);
                        uint64_t source_item = WAR3_CLONE_VALUE(&clone_guard, unit_item_in_slot(cmd.unit_handle, slot));
                        uint32_t item_id;
                        uint64_t target_item;
                        if (!source_item) {
                            continue;
                        }
                        item_id = WAR3_CLONE_VALUE(&clone_guard, get_item_type_id(source_item));
                        if(clone_guard.inventory_captured && item_id!=clone_guard.source_items[slot].rawcode)
                            RaiseException(ERROR_INVALID_DATA,0,0,NULL);
                        if (!item_id) {
                            continue;
                        }
                        target_item = WAR3_CLONE_VALUE(&clone_guard, unit_add_item_by_id(target, item_id));
                        if (!target_item) {
                            clone_error = ERROR_NOT_FOUND;
                            __leave;
                        }
                        war3_clone_track_item(&clone_guard,(unsigned)slot,target_item,item_id);
                        if (!war3_copy_item_instance_fields(
                            &clone_guard,
                            source_item,
                            target_item,
                            get_item_integer_field,
                            set_item_integer_field,
                            get_item_real_field,
                            set_item_real_field,
                            get_item_boolean_field,
                            set_item_boolean_field
                        )) {
                            clone_error = ERROR_WRITE_FAULT;
                            __leave;
                        }
                        {
                            int32_t charges = WAR3_CLONE_VALUE(&clone_guard, get_item_charges(source_item));
                            WAR3_CLONE_VOID(&clone_guard, set_item_charges(target_item, charges));
                            if (WAR3_CLONE_VALUE(&clone_guard, get_item_charges(target_item)) != charges) {
                                clone_error = ERROR_WRITE_FAULT;
                                __leave;
                            }
                        }
                        ++copied_items;
                    }
                    clone_guard.active_items[0]=clone_guard.active_items[1]=NULL;
                    }

                    for (int32_t index = 0; index < 256; ++index) {
                        op->result=clone_phase=0x600u+(uint32_t)index;
                        __try {
                        op->result=clone_phase=0x800u+(uint32_t)index;
                        uint64_t source_ability =
                            WAR3_CLONE_VALUE(&clone_guard, get_ability_by_index(cmd.unit_handle, index));
                        uint32_t ability_id;
                        int32_t source_ability_level;
                        int32_t target_ability_level;
                        if (!source_ability) {
                            break;
                        }
                        op->result=clone_phase=0x900u+(uint32_t)index;
                        ability_id = WAR3_CLONE_VALUE(&clone_guard, get_ability_id(source_ability));
                        if (!ability_id || war3_is_essential_ability(ability_id)) {
                            continue;
                        }
                        op->result=clone_phase=0xa00u+(uint32_t)index;
                        source_ability_level =
                            WAR3_CLONE_VALUE(&clone_guard, get_ability_level(cmd.unit_handle, ability_id));
                        if (source_ability_level <= 0) {
                            continue;
                        }
                        op->result=clone_phase=0xb00u+(uint32_t)index;
                        int target_query_error=0;
                        __try {
                            target_ability_level = WAR3_CLONE_VALUE(&clone_guard, get_ability_level(target, ability_id));
                        } __except (EXCEPTION_EXECUTE_HANDLER) {
                            DWORD target_exception=GetExceptionCode();
                            if(target_exception==0xc0000094u) target_query_error=1;
                            else { clone_error=target_exception; __leave; }
                        }
                        if (target_query_error) { continue; }
                        int add_query_error=0;
                        int add_result=1;
                        if (target_ability_level <= 0) {
                            op->result=clone_phase=0xc00u+(uint32_t)index;
                            __try {
                                add_result=WAR3_CLONE_VALUE(&clone_guard, add_ability(target, ability_id));
                            } __except (EXCEPTION_EXECUTE_HANDLER) {
                                DWORD target_exception=GetExceptionCode();
                                if(target_exception==0xc0000094u) add_query_error=1;
                                else { clone_error=target_exception; __leave; }
                            }
                        }
                        if (add_query_error || (target_ability_level <= 0 && !add_result)) {
                            /* Some map-provided abilities cannot be attached
                             * to a newly created instance; leave that one out
                             * without calling another unsafe native. */
                            continue;
                        }
                        op->result=clone_phase=0xd00u+(uint32_t)index;
                        int target_level_query_error=0;
                        int target_level_value=0;
                        __try {
                            target_level_value=WAR3_CLONE_VALUE(&clone_guard, get_ability_level(target, ability_id));
                        } __except (EXCEPTION_EXECUTE_HANDLER) {
                            DWORD target_exception=GetExceptionCode();
                            if(target_exception==0xc0000094u) target_level_query_error=1;
                            else { clone_error=target_exception; __leave; }
                        }
                        if(target_level_query_error) { continue; }
                        if (target_level_value != source_ability_level) {
                            int target_level_write_error=0;
                            int target_level_readback=0;
                            __try {
                                WAR3_CLONE_VALUE(&clone_guard, set_ability_level(target, ability_id, source_ability_level));
                                target_level_readback=WAR3_CLONE_VALUE(&clone_guard, get_ability_level(target, ability_id));
                            } __except (EXCEPTION_EXECUTE_HANDLER) {
                                DWORD target_exception=GetExceptionCode();
                                if(target_exception==0xc0000094u) target_level_write_error=1;
                                else { clone_error=target_exception; __leave; }
                            }
                            if (target_level_write_error) { continue; }
                            if (target_level_readback != source_ability_level) {
                                clone_error = ERROR_WRITE_FAULT;
                                __leave;
                            }
                        }
                        ++copied_abilities;
                        } __except (EXCEPTION_EXECUTE_HANDLER) {
                            if(clone_guard.source) {clone_error=GetExceptionCode();break;}
                            continue;
                        }
                        if(clone_error) break;
                    }
                    if(clone_error) __leave;

                    {
                        op->result=clone_phase=0x700u;
                        int32_t max_hp = WAR3_CLONE_VALUE(&clone_guard, get_unit_max_hp(cmd.unit_handle));
                        float life = war3_real_from_bits(WAR3_CLONE_VALUE(&clone_guard, get_widget_life(cmd.unit_handle)));
                        int32_t max_mana = WAR3_CLONE_VALUE(&clone_guard, get_unit_max_mana(cmd.unit_handle));
                        float mana = war3_real_from_bits(
                            WAR3_CLONE_VALUE(&clone_guard, get_unit_state(cmd.unit_handle, 2))
                        );
                        if (max_hp > 0) {
                            WAR3_CLONE_VOID(&clone_guard, set_unit_max_hp(target, max_hp));
                        }
                        if (max_mana >= 0) {
                            WAR3_CLONE_VOID(&clone_guard, set_unit_max_mana(target, max_mana));
                        }
                        if (life == life) {
                            WAR3_CLONE_VOID(&clone_guard, set_widget_life(target, &life));
                        }
                        if (mana == mana) {
                            WAR3_CLONE_VOID(&clone_guard, set_unit_state(target, 2, &mana));
                        }
                        {
                            float actual_life =
                                war3_real_from_bits(WAR3_CLONE_VALUE(&clone_guard, get_widget_life(target)));
                            float actual_mana =
                                war3_real_from_bits(WAR3_CLONE_VALUE(&clone_guard, get_unit_state(target, 2)));
                            float life_delta = actual_life - life;
                            float mana_delta = actual_mana - mana;
                            if (life_delta < 0.0f) {
                                life_delta = -life_delta;
                            }
                            if (mana_delta < 0.0f) {
                                mana_delta = -mana_delta;
                            }
                            if (
                                WAR3_CLONE_VALUE(&clone_guard, get_unit_max_hp(target)) != max_hp ||
                                WAR3_CLONE_VALUE(&clone_guard, get_unit_max_mana(target)) != max_mana ||
                                !(actual_life == actual_life) ||
                                !(actual_mana == actual_mana) ||
                                life_delta > 0.51f ||
                                mana_delta > 0.51f
                            ) {
                                clone_error = ERROR_WRITE_FAULT;
                                __leave;
                            }
                        }
                    }
                    war3_clone_check_saved_items(&clone_guard);
                    op->result = target;
                    d8->result = copied_items;
                    d12->result = copied_abilities;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    clone_error = GetExceptionCode();
                }
                if (clone_error != ERROR_SUCCESS) {
                    DWORD rollback_error = ERROR_SUCCESS;
                    __try {
                        if (target) {
                            if(clone_guard.source) {
                                rollback_error=clone_guard.target_captured?
                                    war3_validate_unit_identity(&clone_guard.target,&clone_guard.target.ops[0]):ERROR_INVALID_HANDLE;
                            }
                            if(!rollback_error) remove_unit(target);
                        }
                    } __except (EXCEPTION_EXECUTE_HANDLER) {
                        rollback_error = GetExceptionCode();
                    }
                    op->result = clone_phase;
                    op->last_error = clone_error;
                    d13->last_error = rollback_error;
                    last_error = (
                        rollback_error != ERROR_SUCCESS
                        ? rollback_error
                        : clone_error
                    );
                    goto finish;
                }
                i += 13;
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
            case WAR3_NATIVE_OP_MOVE_SELECTED_GROUP_TO_MOUSE: {
                uint64_t point = 0;
                if (cmd.op_count != 1u || !war3_executable_pointer(op->handler)) {
                    last_error = ERROR_INVALID_PARAMETER;
                } else {
                    last_error = war3_query_world_point(&point);
                    if (!last_error) {
                        last_error = war3_move_selected_group_at_point(op, point);
                    }
                }
                if (last_error) {
                    op->last_error = last_error;
                    goto finish;
                }
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
                    if(cmd.ops[0].kind==WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY) {
                        last_error=war3_validate_unit_identity(&cmd,&cmd.ops[0]);
                        if(last_error) {op->last_error=last_error;goto finish;}
                    }
                    op->result = (uint64_t)x_bits | ((uint64_t)y_bits << 32);
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_SET_UNIT_STATE: {
                JassSetUnitStateFn set_unit_state =
                    (JassSetUnitStateFn)(uintptr_t)op->handler;
                uint32_t value_bits = (uint32_t)op->arg0;
                float value = 0.0f;
                memcpy(&value, &value_bits, sizeof(value));
                if (cmd.ops[0].kind != WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY ||
                    !cmd.unit_handle || !war3_executable_pointer(op->handler) ||
                    (op->rawcode != 0u && op->rawcode != 2u) ||
                    !(value == value) || value < -100000000.0f || value > 100000000.0f) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = ERROR_INVALID_PARAMETER;
                    goto finish;
                }
                __try {
                    set_unit_state(cmd.unit_handle, (int32_t)op->rawcode, &value);
                    op->result = value_bits;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_SET_UNIT_INT: {
                JassUnitSetIntFn set_unit_int =
                    (JassUnitSetIntFn)(uintptr_t)op->handler;
                if (cmd.ops[0].kind != WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY ||
                    !cmd.unit_handle || !war3_executable_pointer(op->handler) || op->arg0 > 1000000000u) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = ERROR_INVALID_PARAMETER;
                    goto finish;
                }
                __try {
                    set_unit_int(cmd.unit_handle, (int32_t)op->arg0);
                    op->result = op->arg0;
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
            case WAR3_NATIVE_OP_JASS_HEAL_LOCAL_UNITS: {
                NativeOp *iter_op = NULL;
                NativeOp *heal_op = NULL;
                JassNoArgU64Fn get_local_player =
                    (JassNoArgU64Fn)(uintptr_t)op->handler;
                JassNoArgU64Fn create_group =
                    (JassNoArgU64Fn)(uintptr_t)op->arg0;
                JassGroupEnumUnitsOfPlayerFn enum_units =
                    (JassGroupEnumUnitsOfPlayerFn)(uintptr_t)op->arg1;
                uint64_t player = 0;
                uint64_t group = 0;
                uint32_t healed = 0;
                uint32_t processed = 0;
                uint64_t previous_unit = 0;
                if (
                    i != 0 || cmd.op_count != 3 || i + 2 >= cmd.op_count
                ) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = op->last_error;
                    goto finish;
                }
                iter_op = &cmd.ops[i + 1];
                heal_op = &cmd.ops[i + 2];
                if (
                    iter_op->kind != WAR3_NATIVE_OP_JASS_MULTI_ARG ||
                    heal_op->kind != WAR3_NATIVE_OP_JASS_MULTI_ARG ||
                    !war3_executable_pointer(op->handler) ||
                    !war3_executable_pointer(op->arg0) ||
                    !war3_executable_pointer(op->arg1) ||
                    !war3_executable_pointer(iter_op->handler) ||
                    !war3_executable_pointer(iter_op->arg0) ||
                    !war3_executable_pointer(iter_op->arg1) ||
                    !war3_executable_pointer(heal_op->handler) ||
                    !war3_executable_pointer(heal_op->arg0) ||
                    !war3_executable_pointer(heal_op->arg1)
                ) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = op->last_error;
                    goto finish;
                }
                JassFirstOfGroupFn first_of_group =
                    (JassFirstOfGroupFn)(uintptr_t)iter_op->handler;
                JassGroupRemoveUnitFn group_remove_unit =
                    (JassGroupRemoveUnitFn)(uintptr_t)iter_op->arg0;
                JassUnitRealQueryFn get_widget_life =
                    (JassUnitRealQueryFn)(uintptr_t)iter_op->arg1;
                JassUnitIntFn get_unit_max_hp =
                    (JassUnitIntFn)(uintptr_t)heal_op->handler;
                JassSetWidgetLifeFn set_widget_life =
                    (JassSetWidgetLifeFn)(uintptr_t)heal_op->arg0;
                JassDestroyGroupFn destroy_group =
                    (JassDestroyGroupFn)(uintptr_t)heal_op->arg1;
                iter_op->result = 0;
                iter_op->last_error = 0;
                heal_op->result = 0;
                heal_op->last_error = 0;
                if (
                    !get_local_player || !create_group || !enum_units ||
                    !first_of_group || !group_remove_unit || !get_widget_life ||
                    !get_unit_max_hp || !set_widget_life || !destroy_group
                ) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = op->last_error;
                    goto finish;
                }
                __try {
                    player = get_local_player();
                    group = create_group();
                    if (!player || !group) {
                        op->last_error = ERROR_NOT_FOUND;
                        last_error = op->last_error;
                    } else {
                        enum_units(group, player, 0);
                        while (processed < 100000u) {
                            uint64_t unit = first_of_group(group);
                            float life;
                            int32_t max_hp;
                            if (!unit) {
                                break;
                            }
                            ++processed;
                            if (unit == previous_unit) {
                                op->last_error = ERROR_INVALID_DATA;
                                last_error = op->last_error;
                                break;
                            }
                            previous_unit = unit;
                            group_remove_unit(group, unit);
                            life = war3_real_from_bits(get_widget_life(unit));
                            if (!(life > 0.405f)) {
                                continue;
                            }
                            max_hp = get_unit_max_hp(unit);
                            if (max_hp > 0 && life < (float)max_hp) {
                                float target_life = (float)max_hp;
                                set_widget_life(unit, &target_life);
                                ++healed;
                            }
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
                op->result = healed;
                iter_op->result = player;
                heal_op->result = group;
                if (last_error) {
                    goto finish;
                }
                i += 2;
                break;
            }
            case WAR3_NATIVE_OP_JASS_RESET_LOCAL_COOLDOWNS: {
                NativeOp *iter_op = NULL;
                NativeOp *cleanup_op = NULL;
                JassNoArgU64Fn get_local_player =
                    (JassNoArgU64Fn)(uintptr_t)op->handler;
                JassNoArgU64Fn create_group =
                    (JassNoArgU64Fn)(uintptr_t)op->arg0;
                JassGroupEnumUnitsOfPlayerFn enum_units =
                    (JassGroupEnumUnitsOfPlayerFn)(uintptr_t)op->arg1;
                uint64_t player = 0;
                uint64_t group = 0;
                uint32_t reset_count = 0;
                uint32_t processed = 0;
                uint64_t previous_unit = 0;
                if (
                    i != 0 || cmd.op_count != 3 || i + 2 >= cmd.op_count
                ) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = op->last_error;
                    goto finish;
                }
                iter_op = &cmd.ops[i + 1];
                cleanup_op = &cmd.ops[i + 2];
                if (
                    iter_op->kind != WAR3_NATIVE_OP_JASS_MULTI_ARG ||
                    cleanup_op->kind != WAR3_NATIVE_OP_JASS_MULTI_ARG ||
                    !war3_executable_pointer(op->handler) ||
                    !war3_executable_pointer(op->arg0) ||
                    !war3_executable_pointer(op->arg1) ||
                    !war3_executable_pointer(iter_op->handler) ||
                    !war3_executable_pointer(iter_op->arg0) ||
                    !war3_executable_pointer(iter_op->arg1) ||
                    !war3_executable_pointer(cleanup_op->handler)
                ) {
                    op->last_error = ERROR_INVALID_DATA;
                    last_error = op->last_error;
                    goto finish;
                }
                JassFirstOfGroupFn first_of_group =
                    (JassFirstOfGroupFn)(uintptr_t)iter_op->handler;
                JassGroupRemoveUnitFn group_remove_unit =
                    (JassGroupRemoveUnitFn)(uintptr_t)iter_op->arg0;
                JassUnitVoidFn reset_cooldown =
                    (JassUnitVoidFn)(uintptr_t)iter_op->arg1;
                JassDestroyGroupFn destroy_group =
                    (JassDestroyGroupFn)(uintptr_t)cleanup_op->handler;
                iter_op->result = 0;
                iter_op->last_error = 0;
                cleanup_op->result = 0;
                cleanup_op->last_error = 0;
                __try {
                    player = get_local_player();
                    group = create_group();
                    if (!player || !group) {
                        op->last_error = ERROR_NOT_FOUND;
                        last_error = op->last_error;
                    } else {
                        enum_units(group, player, 0);
                        while (processed < 100000u) {
                            uint64_t unit = first_of_group(group);
                            if (!unit) {
                                break;
                            }
                            ++processed;
                            if (unit == previous_unit) {
                                op->last_error = ERROR_INVALID_DATA;
                                last_error = op->last_error;
                                break;
                            }
                            previous_unit = unit;
                            group_remove_unit(group, unit);
                            reset_cooldown(unit);
                            ++reset_count;
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
                op->result = reset_count;
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
                    !ability_field_handle || !op->rawcode ||
                    !(value == value) || value < -100000000.0f || value > 100000000.0f
                ) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = op->last_error;
                    goto finish;
                }
                __try {
                    op->result = fn(
                        ability_field_handle,
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
            case WAR3_NATIVE_OP_JASS_ABILITY_FIELD_GET: {
                JassAbilityFieldGetFn fn =
                    (JassAbilityFieldGetFn)(uintptr_t)op->handler;
                if (!ability_field_handle || !op->rawcode) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = op->last_error;
                    goto finish;
                }
                __try {
                    op->result = fn(ability_field_handle, op->rawcode);
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_ABILITY_LEVEL_FIELD_GET: {
                JassAbilityLevelFieldGetFn fn =
                    (JassAbilityLevelFieldGetFn)(uintptr_t)op->handler;
                if (!ability_field_handle || !op->rawcode || op->arg0 > 1000u) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = op->last_error;
                    goto finish;
                }
                __try {
                    op->result = fn(
                        ability_field_handle,
                        op->rawcode,
                        (int32_t)op->arg0
                    );
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_ABILITY_SCALAR_FIELD_SET: {
                JassAbilityScalarFieldSetFn fn =
                    (JassAbilityScalarFieldSetFn)(uintptr_t)op->handler;
                if (!ability_field_handle || !op->rawcode) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = op->last_error;
                    goto finish;
                }
                __try {
                    op->result = fn(
                        ability_field_handle,
                        op->rawcode,
                        (uint32_t)op->arg0
                    );
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_ABILITY_REAL_FIELD_SET: {
                JassAbilityRealFieldSetFn fn =
                    (JassAbilityRealFieldSetFn)(uintptr_t)op->handler;
                float value = war3_real_from_bits((uint32_t)op->arg0);
                if (
                    !ability_field_handle || !op->rawcode ||
                    !(value == value) || value < -100000000.0f || value > 100000000.0f
                ) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = op->last_error;
                    goto finish;
                }
                __try {
                    op->result = fn(ability_field_handle, op->rawcode, &value);
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_ABILITY_SCALAR_LEVEL_FIELD_SET: {
                JassAbilityScalarLevelFieldSetFn fn =
                    (JassAbilityScalarLevelFieldSetFn)(uintptr_t)op->handler;
                if (!ability_field_handle || !op->rawcode || op->arg0 > 1000u) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = op->last_error;
                    goto finish;
                }
                __try {
                    op->result = fn(
                        ability_field_handle,
                        op->rawcode,
                        (int32_t)op->arg0,
                        (uint32_t)op->arg1
                    );
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_ITEM_FIELD_GET: {
                JassItemFieldGetFn fn =
                    (JassItemFieldGetFn)(uintptr_t)op->handler;
                if (!item_field_handle || !op->rawcode) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = op->last_error;
                    goto finish;
                }
                __try {
                    op->result = fn(item_field_handle, op->rawcode);
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    op->last_error = GetExceptionCode();
                    last_error = op->last_error;
                    goto finish;
                }
                break;
            }
            case WAR3_NATIVE_OP_JASS_ITEM_FIELD_SET: {
                if (!item_field_handle || !op->rawcode) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = op->last_error;
                    goto finish;
                }
                __try {
                    if (op->arg1 == 2u) {
                        JassItemRealFieldSetFn fn =
                            (JassItemRealFieldSetFn)(uintptr_t)op->handler;
                        float value = war3_real_from_bits((uint32_t)op->arg0);
                        if (
                            !(value == value) ||
                            value < -100000000.0f ||
                            value > 100000000.0f
                        ) {
                            op->last_error = ERROR_INVALID_PARAMETER;
                            last_error = op->last_error;
                            goto finish;
                        }
                        op->result = fn(item_field_handle, op->rawcode, &value);
                    } else {
                        JassItemScalarFieldSetFn fn =
                            (JassItemScalarFieldSetFn)(uintptr_t)op->handler;
                        op->result = fn(
                            item_field_handle,
                            op->rawcode,
                            (uint32_t)op->arg0
                        );
                    }
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
            case WAR3_NATIVE_OP_JASS_UNIT_RESOLVE_ARG: {
                JassUnitHandleResolveFn fn =
                    (JassUnitHandleResolveFn)(uintptr_t)op->handler;
                if (!op->arg0) {
                    op->last_error = ERROR_INVALID_PARAMETER;
                    last_error = ERROR_INVALID_PARAMETER;
                    goto finish;
                }
                __try {
                    op->result = fn(op->arg0);
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
        if (war3_is_ability_field_op(op->kind)) {
            last_error = war3_validate_bound_ability(&cmd, &ability_field_handle);
            if (last_error) { op->last_error = last_error; goto finish; }
        }
        if (war3_is_item_field_op(op->kind)) {
            last_error = war3_validate_bound_item(&cmd, &item_field_handle);
            if (last_error) { op->last_error = last_error; goto finish; }
        }
        if (war3_is_internal_ability_op(op->kind) &&
            cmd.ops[0].kind == WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY) {
            last_error = war3_validate_unit_identity(&cmd, &cmd.ops[0]);
            if (last_error) { op->last_error = last_error; goto finish; }
        }
        if (war3_is_internal_item_op(op->kind) && cmd.ops[0].kind == WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY) {
            last_error = war3_validate_unit_identity(&cmd, &cmd.ops[0]);
            if (last_error) { op->last_error = last_error; goto finish; }
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
