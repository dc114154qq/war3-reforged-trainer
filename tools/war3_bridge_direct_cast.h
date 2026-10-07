/* Hold the game-owned instance across phases, never a pointer into this DLL. */
typedef struct DirectCastWork {
    WorldCastWork cast;
    uint64_t module_base;
    EffectUnitResolveFn resolve_unit;
    uint32_t (*get_level)(uint64_t,uint32_t);
    uint64_t unit_full, ability_full, ability_data;
    uint32_t mode, passes, level_index, cleanup_error;
} DirectCastWork;
_Static_assert(sizeof(DirectCastWork)==824,"Direct cast ABI");
__declspec(dllexport) const uint32_t direct_cast_abi[3]={0x24268050u,216u,824u};

static int BridgeDirectCastIdentity(DirectCastWork *d) {
    WorldCastWork *w=&d->cast;
    uint64_t object=d->resolve_unit(w->source);
    if(!BridgeEffectReadable(object,0x20) ||
       *(uint64_t *)(uintptr_t)(object+bridge_profile.object_handle)!=d->unit_full ||
       w->get_ability(w->source,w->rawcode)!=w->ability_handle ||
       w->get_ability_id(w->ability_handle)!=w->rawcode) return 0;
    uint64_t data=BridgeEffectFindAbilityDataByFullHandle(
        (EffectResolveFn)(uintptr_t)d->module_base,d->unit_full,w->rawcode,0);
    return data==d->ability_data && BridgeEffectReadable(data,0x80) &&
        *(uint64_t *)(uintptr_t)(data+bridge_profile.ability_handle)==d->ability_full &&
        *(uint64_t *)(uintptr_t)(data+bridge_profile.ability_owner)==object &&
        d->get_level(w->source,w->rawcode)==d->level_index+1u;
}

static DWORD BridgeDirectCastFinish(DirectCastWork *d) {
    WorldCastWork *w=&d->cast;
    union {uint32_t bits;float value;} prior;
    if(!BridgeDirectCastIdentity(d))return ERROR_INVALID_HANDLE;
    if(w->get_order(w->source)==(uint32_t)w->target){
        if(!w->issue_immediate(w->source,851972u))return ERROR_INVALID_DATA;
        if(!BridgeDirectCastIdentity(d))return ERROR_INVALID_HANDLE;
    }
    prior.bits=w->prior_area;
    if(!w->set_area(w->ability_handle,EFFECT_AREA_FIELD,(int32_t)d->level_index,&prior.value) ||
       (uint32_t)w->get_area(w->ability_handle,EFFECT_AREA_FIELD,(int32_t)d->level_index)!=prior.bits)
        return ERROR_INVALID_DATA;
    if(!BridgeDirectCastIdentity(d))return ERROR_INVALID_HANDLE;
    if(w->added && (!w->remove_ability(w->source,w->rawcode) || w->get_ability(w->source,w->rawcode)))
        return ERROR_INVALID_DATA;
    return ERROR_SUCCESS;
}

__declspec(dllexport) uint64_t BridgeDirectCastQuery(void) {
    DirectCastWork *d=(DirectCastWork *)g_dispatch->work;
    WorldCastWork *w=d?&d->cast:0;
    uint32_t area_touched=0,captured=0,count=0;
    union {uint32_t bits;float value;} area,x,y;
    if(!w || w->expected_tls!=g_dispatch->tls_value || !d->module_base ||
       !d->resolve_unit || !d->get_level || !w->get_ability || !w->get_ability_id ||
       !w->add_ability || !w->remove_ability || !w->get_area || !w->set_area ||
       !w->get_x || !w->get_y || !w->get_order || !w->issue_immediate ||
       !w->get_mana || !w->get_cooldown || w->action<1 || w->action>3 ||
       !w->rawcode || d->mode<2 || d->mode>4 || !d->passes || d->passes>255){
        if(w)w->error=340;return 0;
    }
    __try {
        if(w->action==1){
            count=(uint32_t)BridgeSelect();
            if(!count || w->selection.error || !w->selection.destroyed){w->error=341;__leave;}
            uint64_t player=w->selection.local_player();
            for(uint32_t i=0;i<count;++i){
                SelectionRow *r=&w->selection.rows[i];
                if(r->level>0 && w->get_owner(r->unit)==player && BridgeWorldCastLive(w,r->unit)){
                    w->source=r->unit;break;
                }
            }
            if(!w->source){w->error=342;__leave;}
            uint64_t object=d->resolve_unit(w->source);
            if(!BridgeEffectReadable(object,0x20)){w->error=343;__leave;}
            d->unit_full=*(uint64_t *)(uintptr_t)(object+bridge_profile.object_handle);
            w->ability_handle=w->get_ability(w->source,w->rawcode);
            if(!w->ability_handle){
                if(!w->add_ability(w->source,w->rawcode)){w->error=344;__leave;}
                w->added=1;w->ability_handle=w->get_ability(w->source,w->rawcode);
            }
            d->ability_data=BridgeEffectFindAbilityDataByFullHandle(
                (EffectResolveFn)(uintptr_t)d->module_base,d->unit_full,w->rawcode,0);
            if(!w->ability_handle || !BridgeEffectReadable(d->ability_data,0x80)){w->error=345;__leave;}
            d->ability_full=*(uint64_t *)(uintptr_t)(d->ability_data+bridge_profile.ability_handle);
            uint32_t level=d->get_level(w->source,w->rawcode);
            if(!level){w->error=346;__leave;}
            d->level_index=level-1;captured=1;
            if(!BridgeDirectCastIdentity(d)){w->error=347;__leave;}
            area.bits=w->area_bits;
            if(!(area.value>=1.0f && area.value<=100000.0f)){w->error=348;__leave;}
            w->prior_area=(uint32_t)w->get_area(w->ability_handle,EFFECT_AREA_FIELD,(int32_t)d->level_index);
            area_touched=1;
            if(!w->set_area(w->ability_handle,EFFECT_AREA_FIELD,(int32_t)d->level_index,&area.value) ||
               (uint32_t)w->get_area(w->ability_handle,EFFECT_AREA_FIELD,(int32_t)d->level_index)!=area.bits){w->error=349;__leave;}
            w->target_x=w->get_x(w->source);w->target_y=w->get_y(w->source);
            x.bits=w->target_x;y.bits=w->target_y;
            if(!(x.value==x.value && y.value==y.value)){w->error=350;__leave;}
            w->mana_before=w->get_mana(w->source,2u);
            for(uint32_t pass=0;pass<d->passes;++pass){
                if(!BridgeDirectCastIdentity(d)){w->error=351;__leave;}
                /* Old effect slots are getters/no-ops in this build. Dispatch
                   through the game's typed order handlers instead. */
                if(w->rawcode==0x414e6d6fu)
                    w->issued=w->issue_point(w->source,852591u,&x.value,&y.value)?1u:0u;
                else if(w->rawcode==0x41487463u)
                    w->issued=w->issue_immediate(w->source,852096u)?1u:0u;
                else if(w->rawcode==0x414f7773u)
                    w->issued=w->issue_immediate(w->source,852127u)?1u:0u;
                else if(w->rawcode==0x41457362u)
                    w->issued=w->issue_immediate(w->source,852183u)?1u:0u;
                else if(w->rawcode==0x4145666bu)
                    w->issued=w->issue_immediate(w->source,852526u)?1u:0u;
                else {w->error=ERROR_NOT_SUPPORTED;__leave;}
                if(!w->issued){w->error=353;__leave;}
            }
            w->order_after=w->get_order(w->source);
        }else{
            if(!BridgeDirectCastIdentity(d)){w->error=354;__leave;}
            if(w->action==2){
                d->cleanup_error=BridgeDirectCastFinish(d);
                if(d->cleanup_error)__leave;
            }else{
                w->mana_after=w->get_mana(w->source,2u);
                w->cooldown_after=w->get_cooldown(w->source,w->rawcode);
                w->order_after=w->get_order(w->source);
            }
        }
        w->completed=1;
    } __except(EXCEPTION_EXECUTE_HANDLER){w->error=GetExceptionCode();}
    if(w->action==1 && w->error){
        __try {
            if(captured && area_touched)d->cleanup_error=BridgeDirectCastFinish(d);
            else if(w->added)d->cleanup_error=ERROR_INVALID_DATA;
        } __except(EXCEPTION_EXECUTE_HANDLER){d->cleanup_error=GetExceptionCode();}
    }
    return w->completed;
}
