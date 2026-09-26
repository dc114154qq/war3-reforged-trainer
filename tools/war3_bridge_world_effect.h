/* Current-build 24268 bounded enemy enumeration for direct ability effects. */
#define WORLD_EFFECT_TARGET 1u
#define WORLD_EFFECT_IMMEDIATE 2u
#define WORLD_EFFECT_POINT 3u

typedef uint64_t (*WorldEffectLocalPlayerFn)(void);
typedef uint64_t (*WorldEffectCreateGroupFn)(void);
typedef void (*WorldEffectEnumUnitsFn)(uint64_t,uint64_t,uint64_t);
typedef uint64_t (*WorldEffectFirstFn)(uint64_t);
typedef void (*WorldEffectRemoveGroupUnitFn)(uint64_t,uint64_t);
typedef void (*WorldEffectDestroyGroupFn)(uint64_t);
typedef uint64_t (*WorldEffectOwnerFn)(uint64_t);
typedef uint64_t (*WorldEffectPlayerFn)(int32_t);
typedef uint8_t (*WorldEffectEnemyFn)(uint64_t,uint64_t);
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
#ifdef BRIDGE_DIAGNOSTIC
#pragma pack(push, 1)
typedef struct WorldEffectProbeRow {
    uint64_t unit;
    uint32_t life, x, y;
} WorldEffectProbeRow;
#pragma pack(pop)
_Static_assert(sizeof(WorldEffectProbeRow) == 20, "World effect probe row ABI");
#endif
_Static_assert(sizeof(WorldEffectWork) == 656, "WorldEffectWork ABI");
__declspec(dllexport) const uint32_t world_effect_batch_abi[3] = {0x24268028u,216u,656u};

static uint64_t BridgeWorldEffectUnitObject(WorldEffectWork *w, uint64_t unit) {
    uint64_t owner = BridgeEffectResolveObjectTable((uint64_t)(uintptr_t)w->resolve_agent, unit);
    if (!BridgeEffectReadable(owner, 0xe0)) return 0;
    return *(uint64_t *)(uintptr_t)(owner + 0x90);
}

static int BridgeWorldEffectLive(uint32_t bits) {
    union { uint32_t bits; float value; } value;
    value.bits = bits;
    return value.value > 0.405f && value.value == value.value;
}

/* Pick one live local-player unit as the caster and drain the temporary group
   before reusing it for enemy enumeration. This route does not need the
   optional GroupEnumUnitsSelected native. */
static uint64_t BridgeWorldEffectFindSource(WorldEffectWork *w, uint64_t group, uint64_t player) {
    uint64_t source = 0;
    for (;;) {
        uint64_t candidate = w->first_of_group(group);
        if (!candidate) break;
        w->remove_from_group(group, candidate);
        if (!source && BridgeWorldEffectLive(w->get_life(candidate)) &&
            w->get_owner(candidate) == player) {
            source = candidate;
        }
    }
    return source;
}

__declspec(dllexport) uint64_t BridgeWorldEffectQuery(void) {
    WorldEffectWork *w = (WorldEffectWork *)g_dispatch->work;
    uint64_t source, source_owner, source_ability_handle = 0, source_ability = 0, group = 0;
    uint64_t source_object = 0, vtable = 0, callback = 0;
    uint8_t source_temporary = 0;
    uint32_t error = 0;
    uint32_t source_lookup_error = 0;
    if (!w || w->expected_tls != g_dispatch->tls_value || !w->rawcode ||
        (w->action != WORLD_EFFECT_TARGET && w->action != WORLD_EFFECT_IMMEDIATE &&
         w->action != WORLD_EFFECT_POINT) ||
        w->success_limit > 65535u || !w->get_ability || !w->resolve_agent || !w->get_ability_id ||
        !w->add_ability || !w->remove_ability || !w->get_local_player ||
        !w->create_group || !w->enum_units || !w->first_of_group ||
        !w->remove_from_group || !w->destroy_group || !w->get_owner ||
        !w->player || !w->is_enemy || !w->get_life || !w->get_x || !w->get_y) {
        if (w) w->error = 170;
        return 0;
    }
    source_owner = w->get_local_player();
    if (!source_owner) { w->error = 171; return 0; }
#ifdef BRIDGE_DIAGNOSTIC
    if(w->action==WORLD_EFFECT_TARGET && w->success_limit==65534u){
        uint64_t target=w->rawcode;
        __try {
            w->rawcode=w->get_life(target);
            *(uint64_t *)(void *)&w->selection=target;
            w->completed=1;
        } __except(EXCEPTION_EXECUTE_HANDLER){w->error=GetExceptionCode();}
        return 0;
    }
    if(w->action==WORLD_EFFECT_TARGET && w->success_limit==65535u){
        uint64_t unit=w->rawcode;
        __try {
            if(!unit || !w->get_ability(unit,0x41487463u)){error=306;__leave;}
            if(!w->remove_ability(unit,0x41487463u) ||
               w->get_ability(unit,0x41487463u)){error=307;__leave;}
            w->completed=1;
        } __except(EXCEPTION_EXECUTE_HANDLER){error=GetExceptionCode();}
        w->error=error;return 0;
    }
    if(w->action==WORLD_EFFECT_TARGET &&
       (w->rawcode==0xfffffff7u || w->rawcode==0xfffffff6u)){
        uint32_t mode=w->success_limit;
        uint8_t added=0;
        __try {
            group=w->create_group();
            if(!group){error=179;__leave;}
            w->enum_units(group,source_owner,0);
            source=BridgeWorldEffectFindSource(w,group,source_owner);
            if(!source){error=172;__leave;}
            w->destroy_group(group);group=0;
            *(uint64_t *)(void *)&w->selection=source;
            if(w->rawcode==0xfffffff6u){
                if(mode==0u)w->rawcode=((uint32_t (__fastcall *)(uint64_t,uint64_t))
                    (uintptr_t)w->resolve_agent)(source,2u);
                else if(mode==1u)w->rawcode=((uint32_t (__fastcall *)(uint64_t))
                    (uintptr_t)w->resolve_agent)(source);
                else if(mode==2u)w->rawcode=((uint32_t (__fastcall *)(uint64_t,uint32_t))
                    (uintptr_t)w->resolve_agent)(source,0x41487463u);
                else {error=308;__leave;}
            }else{
                uint64_t ability=w->get_ability(source,0x41487463u);
                if(ability){error=312;__leave;}
                if(!w->add_ability(source,0x41487463u)){error=309;__leave;}
                added=1;
                ability=w->get_ability(source,0x41487463u);
                if(!ability || w->get_ability_id(ability)!=0x41487463u){error=310;__leave;}
                if(mode){
                    union {uint32_t bits;float value;} old_area,area,verified;
                    old_area.bits=(uint32_t)((EffectAreaGetFn)(uintptr_t)w->get_x)(
                        ability,EFFECT_AREA_FIELD,0);
                    area.value=(float)mode;
                    w->attempts=old_area.bits;
                    if(!((EffectAreaSetFn)(uintptr_t)w->get_y)(
                           ability,EFFECT_AREA_FIELD,0,&area.value)){error=313;__leave;}
                    verified.bits=(uint32_t)((EffectAreaGetFn)(uintptr_t)w->get_x)(
                        ability,EFFECT_AREA_FIELD,0);
                    if(verified.bits!=area.bits){error=314;__leave;}
                }
                w->successes=((uint8_t (__fastcall *)(uint64_t,uint32_t))
                    (uintptr_t)w->resolve_agent)(source,852096u)?1u:0u;
                if(!w->successes){error=311;__leave;}
                w->rawcode=(uint32_t)source;
                w->reserved=added;
            }
            w->completed=1;
        } __except(EXCEPTION_EXECUTE_HANDLER){error=GetExceptionCode();}
        if(group){
            __try{w->destroy_group(group);}
            __except(EXCEPTION_EXECUTE_HANDLER){if(!error)error=GetExceptionCode();}
        }
        if(error && added && source){
            __try{w->remove_ability(source,0x41487463u);}
            __except(EXCEPTION_EXECUTE_HANDLER){}
        }
        w->error=error;return w->successes;
    }
    if (w->action == WORLD_EFFECT_TARGET && w->rawcode == 0xfffffffcu) {
        static const char *orders[]={"shockwave","thunderclap","monsoon",
                                     "starfall","forkedlightning"};
        if(w->success_limit>=5u){w->error=305;return 0;}
        __try {
            w->rawcode=((uint32_t (__fastcall *)(const char *))(uintptr_t)
                w->resolve_agent)(orders[w->success_limit]);
            w->completed=1;
        } __except(EXCEPTION_EXECUTE_HANDLER){w->error=GetExceptionCode();}
        return 0;
    }
    if (w->action == WORLD_EFFECT_TARGET && w->rawcode == 0xfffffffeu) {
        __try {
            uint8_t *out=(uint8_t *)(void *)&w->selection;
            const uint8_t *in=(const uint8_t *)(uintptr_t)w->add_ability;
            for(uint32_t index=0;index<128u;++index)out[index]=in[index];
            w->completed=1;
        } __except(EXCEPTION_EXECUTE_HANDLER){w->error=GetExceptionCode();}
        return 0;
    }
    if (w->action == WORLD_EFFECT_TARGET &&
        (w->rawcode == 0xffffffffu || w->rawcode == 0xfffffffdu)) {
        WorldEffectProbeRow *rows=(WorldEffectProbeRow *)(void *)&w->selection;
        uint32_t nearest=w->rawcode==0xfffffffdu;
        union {uint32_t bits;float value;} source_x,source_y;
        __try {
            group=w->create_group();
            if(!group){error=179;__leave;}
            w->enum_units(group,source_owner,0);
            source=BridgeWorldEffectFindSource(w,group,source_owner);
            if(!source){error=172;__leave;}
            source_x.bits=w->get_x(source);
            source_y.bits=w->get_y(source);
            if(nearest){
                uint32_t *source_position=(uint32_t *)((uint8_t *)(void *)&w->selection+400u);
                source_position[0]=source_x.bits;
                source_position[1]=source_y.bits;
            }
            {
                uint64_t unit_owner=w->get_owner(source);
                w->reserved=(unit_owner==source_owner?1u:0u) |
                    (w->is_enemy(source_owner,source_owner)?2u:0u) |
                    (w->is_enemy(source_owner,unit_owner)?4u:0u);
                w->rawcode=(uint32_t)source;
                w->success_limit=(uint32_t)unit_owner;
            }
            for(int32_t player_id=0;player_id<24 && !error;++player_id){
                uint64_t player=w->player(player_id);
                if(!player)continue;
                w->enum_units(group,player,0);
                for(;;){
                    uint64_t unit=w->first_of_group(group);
                    uint64_t owner;
                    if(!unit)break;
                    w->remove_from_group(group,unit);
                    if(++w->attempts>100000u){error=180;break;}
                    if(!BridgeWorldEffectLive(w->get_life(unit)))continue;
                    owner=w->get_owner(unit);
                    if(!owner || owner==source_owner || !w->is_enemy(source_owner,owner))continue;
                    if(!nearest && w->successes<24u){
                        WorldEffectProbeRow *row=&rows[w->successes];
                        row->unit=unit;row->life=w->get_life(unit);
                        row->x=w->get_x(unit);row->y=w->get_y(unit);
                    }else if(nearest){
                        union {uint32_t bits;float value;} x,y,old_x,old_y;
                        uint32_t position=w->successes;
                        x.bits=w->get_x(unit);y.bits=w->get_y(unit);
                        if(w->successes>=20u){
                            float farthest=-1.0f;
                            for(uint32_t k=0;k<20u;++k){
                                old_x.bits=rows[k].x;old_y.bits=rows[k].y;
                                float dx=old_x.value-source_x.value;
                                float dy=old_y.value-source_y.value;
                                float distance=dx*dx+dy*dy;
                                if(distance>farthest){farthest=distance;position=k;}
                            }
                            {
                                float dx=x.value-source_x.value;
                                float dy=y.value-source_y.value;
                                if(dx*dx+dy*dy>=farthest)position=20u;
                            }
                        }
                        if(position<20u){
                            WorldEffectProbeRow *row=&rows[position];
                            row->unit=unit;row->life=w->get_life(unit);
                            row->x=x.bits;row->y=y.bits;
                        }
                    }
                    ++w->successes;
                }
            }
        } __except(EXCEPTION_EXECUTE_HANDLER){error=GetExceptionCode();}
        if(group){
            __try{w->destroy_group(group);}
            __except(EXCEPTION_EXECUTE_HANDLER){if(!error)error=GetExceptionCode();}
        }
        w->error=error;
        w->completed=!error;
        return w->successes;
    }
#endif
    __try {
        group = w->create_group();
        if (!group) { error = 179; __leave; }
        w->enum_units(group, source_owner, 0);
        source = BridgeWorldEffectFindSource(w, group, source_owner);
        if (!source) { error = 172; __leave; }
#ifdef BRIDGE_DIAGNOSTIC
        *(uint64_t *)(void *)&w->selection = source;
#endif
        if (w->action != WORLD_EFFECT_IMMEDIATE) {
            source_ability_handle = w->get_ability(source, w->rawcode);
            if (!source_ability_handle) {
                if (!w->add_ability(source, w->rawcode)) { error = 174; __leave; }
                source_temporary = 1;
                source_ability_handle = w->get_ability(source, w->rawcode);
            }
            if (!source_ability_handle || w->get_ability_id(source_ability_handle) != w->rawcode) {
                error = 175; __leave;
            }
            source_ability = BridgeEffectFindAbilityDataByFullHandle(
                w->resolve_agent, source, w->rawcode, &source_lookup_error);
            if (!source_ability) { w->reserved = source_lookup_error; error = 175; __leave; }
            source_object = BridgeWorldEffectUnitObject(w, source);
            if (!source_object) { error = 176; __leave; }
            vtable = *(uint64_t *)(uintptr_t)source_ability;
            if (!BridgeEffectReadable(vtable, (w->action == WORLD_EFFECT_TARGET ? 0xa78u : 0xa60u))) {
                error = 177; __leave;
            }
            callback = *(uint64_t *)(uintptr_t)(vtable +
                (w->action == WORLD_EFFECT_TARGET ? 0xa70u : 0xa58u));
            if (!BridgeEffectExecutable(callback)) { error = 178; __leave; }
        }
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
                    if (!target_owner || target_owner == source_owner ||
                        !w->is_enemy(source_owner, target_owner)) continue;
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
                    } else if (w->action == WORLD_EFFECT_TARGET) {
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
                            if (!target_error) target_object = BridgeWorldEffectUnitObject(w, target);
                            if (!target_error) target_ability = BridgeEffectFindAbilityDataByFullHandle(
                                w->resolve_agent, target, w->rawcode, &target_error);
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
                    } else {
                        uint64_t target_ability_handle = w->get_ability(target, w->rawcode);
                        uint64_t target_ability = 0;
                        uint64_t target_vtable = 0, target_callback = 0;
                        uint8_t target_temporary = 0;
                        uint64_t target_object = 0;
                        uint32_t target_error = 0;
                        __try {
                            if (!target_ability_handle) {
                                if (!w->add_ability(target, w->rawcode)) target_error = 181;
                                else {
                                    target_temporary = 1;
                                    target_ability_handle = w->get_ability(target, w->rawcode);
                                }
                            }
                            if (!target_error && (!target_ability_handle ||
                                w->get_ability_id(target_ability_handle) != w->rawcode))
                                target_error = 182;
                            if (!target_error) target_object = BridgeWorldEffectUnitObject(w, target);
                            if (!target_error && !target_object) target_error = 183;
                            if (!target_error) target_ability = BridgeEffectFindAbilityDataByFullHandle(
                                w->resolve_agent, target, w->rawcode, &target_error);
                            if (!target_error && !target_ability) target_error = 184;
                            if (!target_error) {
                                target_vtable = *(uint64_t *)(uintptr_t)target_ability;
                                if (!BridgeEffectReadable(target_vtable, 0x9a0u)) target_error = 185;
                            }
                            if (!target_error) {
                                target_callback = *(uint64_t *)(uintptr_t)(target_vtable + 0x998u);
                                if (!BridgeEffectExecutable(target_callback)) target_error = 186;
                            }
                            if (!target_error)
                                ((EffectImmediateFn)(uintptr_t)target_callback)(target_ability);
                        } __except(EXCEPTION_EXECUTE_HANDLER) {
                            target_error = GetExceptionCode();
                        }
                        if (target_temporary) {
                            __try {
                                if (!w->remove_ability(target, w->rawcode) || w->get_ability(target, w->rawcode))
                                    if (!target_error) target_error = 187;
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
