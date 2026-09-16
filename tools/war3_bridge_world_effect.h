/* Current-build 24268 bounded enemy enumeration for direct ability effects. */
#define WORLD_EFFECT_TARGET 1u
#define WORLD_EFFECT_POINT 3u

typedef uint64_t (*WorldEffectLocalPlayerFn)(void);
typedef uint64_t (*WorldEffectCreateGroupFn)(void);
typedef void (*WorldEffectEnumUnitsFn)(uint64_t,uint64_t,uint64_t);
typedef uint64_t (*WorldEffectFirstFn)(uint64_t);
typedef void (*WorldEffectRemoveGroupUnitFn)(uint64_t,uint64_t);
typedef void (*WorldEffectDestroyGroupFn)(uint64_t);
typedef uint64_t (*WorldEffectOwnerFn)(uint64_t);
typedef uint64_t (*WorldEffectPlayerFn)(int32_t);
typedef uint32_t (*WorldEffectEnemyFn)(uint64_t,uint64_t);
typedef uint32_t (*WorldEffectLifeFn)(uint64_t);
typedef uint32_t (*WorldEffectPositionFn)(uint64_t);

typedef struct WorldEffectWork {
    SelectionWork selection;
    EffectAbilityLookupFn get_ability;
    EffectResolveFn resolve_agent;
    EffectAbilityIdFn get_ability_id;
    EffectUnitAddFn add_ability;
    EffectUnitRemoveFn remove_ability;
    WorldEffectLocalPlayerFn get_local_player;
    WorldEffectCreateGroupFn create_group;
    WorldEffectEnumUnitsFn enum_units;
    WorldEffectFirstFn first_of_group;
    WorldEffectRemoveGroupUnitFn remove_from_group;
    WorldEffectDestroyGroupFn destroy_group;
    WorldEffectOwnerFn get_owner;
    WorldEffectPlayerFn player;
    WorldEffectEnemyFn is_enemy;
    WorldEffectLifeFn get_life;
    WorldEffectPositionFn get_x;
    WorldEffectPositionFn get_y;
    void *expected_tls;
    uint32_t rawcode, action, success_limit, attempts;
    uint32_t error, successes, completed, reserved;
} WorldEffectWork;
_Static_assert(sizeof(WorldEffectWork) == 656, "WorldEffectWork ABI");
__declspec(dllexport) const uint32_t world_effect_batch_abi[3] = {0x24268028u,216u,656u};

static uint64_t BridgeWorldEffectUnitObject(uint64_t owner) {
    if (!BridgeEffectReadable(owner, 0xe0)) return 0;
    return *(uint64_t *)(uintptr_t)(owner + 0x90);
}

static int BridgeWorldEffectLive(uint32_t bits) {
    union { uint32_t bits; float value; } value;
    value.bits = bits;
    return value.value > 0.405f && value.value == value.value;
}

__declspec(dllexport) uint64_t BridgeWorldEffectQuery(void) {
    WorldEffectWork *w = (WorldEffectWork *)g_dispatch->work;
    uint64_t source, source_owner, source_ability_handle = 0, source_ability = 0, group = 0;
    uint64_t source_object = 0, vtable = 0, callback = 0;
    uint8_t source_temporary = 0;
    uint32_t error = 0;
    if (!w || w->expected_tls != g_dispatch->tls_value || !w->rawcode ||
        (w->action != WORLD_EFFECT_TARGET && w->action != WORLD_EFFECT_POINT) ||
        w->success_limit > 65535u || !w->get_ability || !w->resolve_agent || !w->get_ability_id ||
        !w->add_ability || !w->remove_ability || !w->get_local_player ||
        !w->create_group || !w->enum_units || !w->first_of_group ||
        !w->remove_from_group || !w->destroy_group || !w->get_owner ||
        !w->player || !w->is_enemy || !w->get_life || !w->get_x || !w->get_y) {
        if (w) w->error = 170;
        return 0;
    }
    if (!w->get_local_player()) { w->error = 171; return 0; }
    if ((uint32_t)BridgeSelect() == 0 || w->selection.error ||
        !w->selection.destroyed || !w->selection.count) {
        w->error = 172;
        return w->selection.count;
    }
    source = w->selection.rows[0].unit;
    __try {
        source_owner = w->get_owner(source);
        if (!source_owner) { error = 173; __leave; }
        source_ability_handle = w->get_ability(source, w->rawcode);
        if (!source_ability_handle) {
            if (!w->add_ability(source, w->rawcode)) { error = 174; __leave; }
            source_temporary = 1;
            source_ability_handle = w->get_ability(source, w->rawcode);
        }
        if (!source_ability_handle || w->get_ability_id(source_ability_handle) != w->rawcode) {
            error = 175; __leave;
        }
        source_ability = BridgeEffectFindAbilityDataFromOwner(source_owner, 0, w->rawcode, 0);
        if (!source_ability) { error = 175; __leave; }
        source_object = BridgeWorldEffectUnitObject(source_owner);
        if (!source_object) { error = 176; __leave; }
        vtable = *(uint64_t *)(uintptr_t)source_ability;
        if (!BridgeEffectReadable(vtable, (w->action == WORLD_EFFECT_TARGET ? 0xa78u : 0xa60u))) {
            error = 177; __leave;
        }
        callback = *(uint64_t *)(uintptr_t)(vtable + (w->action == WORLD_EFFECT_TARGET ? 0xa70u : 0xa58u));
        if (!BridgeEffectExecutable(callback)) { error = 178; __leave; }
        group = w->create_group();
        if (!group) { error = 179; __leave; }
        for (int32_t player_id = 0; player_id < 24 && !error; ++player_id) {
            uint64_t player = w->player(player_id);
            if (!player) continue;
            w->enum_units(group, player, 0);
            for (;;) {
                uint64_t target = w->first_of_group(group);
                if (!target || (w->success_limit && w->successes >= w->success_limit)) break;
                w->remove_from_group(group, target);
                if (++w->attempts > 100000u) { error = 180; break; }
                if (!BridgeWorldEffectLive(w->get_life(target))) continue;
                {
                    uint64_t target_owner = w->get_owner(target);
                    if (!target_owner || !w->is_enemy(source_owner, target_owner)) continue;
                    if (w->action == WORLD_EFFECT_POINT) {
                        union { uint32_t bits; float value; } x, y;
                        x.bits = w->get_x(target); y.bits = w->get_y(target);
                        if ((x.bits & 0x7f800000u) == 0x7f800000u ||
                            (y.bits & 0x7f800000u) == 0x7f800000u) continue;
                        __try {
                            ((EffectPointFn)(uintptr_t)callback)(source_ability, &x.value, &y.value);
                        } __except(EXCEPTION_EXECUTE_HANDLER) {
                            error = GetExceptionCode();
                        }
                    } else {
                        uint64_t target_ability_handle = w->get_ability(target, w->rawcode);
                        uint64_t target_ability = 0;
                        uint8_t target_temporary = 0;
                        uint64_t target_object = 0;
                        uint32_t target_error = 0;
                        __try {
                            if (!target_ability_handle) {
                                if (!w->add_ability(target, w->rawcode)) target_error = 181;
                                else { target_temporary = 1; target_ability_handle = w->get_ability(target, w->rawcode); }
                            }
                            if (!target_error && (!target_ability_handle ||
                                w->get_ability_id(target_ability_handle) != w->rawcode))
                                target_error = 182;
                            if (!target_error) target_object = BridgeWorldEffectUnitObject(target_owner);
                            if (!target_error) target_ability = BridgeEffectFindAbilityDataFromOwner(
                                target_owner, target_object, w->rawcode, &target_error);
                            if (!target_error && !target_object) target_error = 183;
                            if (!target_error)
                                ((EffectTargetFn)(uintptr_t)callback)(source_ability, target_object);
                        } __except(EXCEPTION_EXECUTE_HANDLER) {
                            target_error = GetExceptionCode();
                        }
                        if (target_temporary) {
                            __try {
                                if (!w->remove_ability(target, w->rawcode) || w->get_ability(target, w->rawcode))
                                    if (!target_error) target_error = 184;
                            } __except(EXCEPTION_EXECUTE_HANDLER) {
                                if (!target_error) target_error = GetExceptionCode();
                            }
                        }
                        if (target_error) { error = target_error; break; }
                    }
                    if (error) break;
                    ++w->successes;
                }
            }
            if (w->success_limit && w->successes >= w->success_limit) break;
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        error = GetExceptionCode();
    }
    if (group) {
        __try { w->destroy_group(group); }
        __except(EXCEPTION_EXECUTE_HANDLER) { if (!error) error = GetExceptionCode(); }
    }
    if (source_temporary) {
        __try {
                if (!w->remove_ability(source, w->rawcode) || w->get_ability(source, w->rawcode))
                if (!error) error = 185;
        } __except(EXCEPTION_EXECUTE_HANDLER) {
            if (!error) error = GetExceptionCode();
        }
    }
    if (error) { w->error = error; return w->attempts; }
    w->completed = 1;
    return w->successes;
}
