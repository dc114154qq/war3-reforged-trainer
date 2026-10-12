/* Hold the game-owned instance across phases, never a pointer into this DLL. */
typedef struct DirectCastWork {
    WorldCastWork cast;
    uint64_t module_base;
    EffectUnitResolveFn resolve_unit;
    uint32_t (*get_level)(uint64_t,uint32_t);
    uint64_t unit_full, ability_full, ability_data;
    uint32_t mode, passes, level_index, cleanup_error;
    BridgeAbilityLevelSetFn set_level;
    int32_t (*get_cost)(uint64_t,uint32_t,int32_t);
    uint8_t (*set_cost)(uint64_t,uint32_t,int32_t,int32_t);
    void (*end_cooldown)(uint64_t,uint32_t);
    void (*start_cooldown)(uint64_t,uint32_t,float*);
    uint64_t (*create_timer)(void);
    void (*timer_start)(uint64_t,float*,uint32_t,uint64_t);
    uint32_t (*timer_elapsed)(uint64_t);
    void (*destroy_timer)(uint64_t);
    BridgeAbilityIndexFn ability_index;
    uint64_t cooldown_timer;
    uint32_t prior_cost,prior_cooldown_field,prior_cooldown_remaining,original_level;
    uint32_t touched,activation,cast_order,expected_level;
    BridgeNativeJournal journal;
} DirectCastWork;
_Static_assert(sizeof(DirectCastWork)==58360,"Direct cast ABI");
__declspec(dllexport) const uint32_t direct_cast_abi[3]={0x2426806du,216u,58360u};
static uint64_t BridgeDirectCastLookup(DirectCastWork*d) {
    int error=0;
    return BridgeFindUnitAbility(d->cast.get_ability,d->ability_index,d->cast.get_ability_id,
        d->cast.source,d->cast.rawcode,&error);
}

static int BridgeDirectCastIdentity(DirectCastWork *d) {
    WorldCastWork *w=&d->cast;
    uint64_t object=d->resolve_unit(w->source);
    if(!BridgeEffectReadable(object,0x20) ||
       *(uint64_t *)(uintptr_t)(object+bridge_profile.object_handle)!=d->unit_full ||
       BridgeDirectCastLookup(d)!=w->ability_handle ||
       BridgeObservedAbilityId(w->get_ability_id,w->ability_handle)!=w->rawcode) return 0;
    uint64_t data=BridgeEffectFindAbilityDataByFullHandle(
        (EffectResolveFn)(uintptr_t)d->module_base,d->unit_full,w->rawcode,0);
    return data==d->ability_data && BridgeEffectReadable(data,0x80) &&
        *(uint64_t *)(uintptr_t)(data+bridge_profile.ability_handle)==d->ability_full &&
        *(uint64_t *)(uintptr_t)(data+bridge_profile.ability_owner)==object &&
        BridgeObservedUnsignedLevel(d->get_level,w->source,w->rawcode)==d->expected_level;
}

static DWORD BridgeDirectCastFinish(DirectCastWork *d) {
    BridgeJournalPhase(26);
    WorldCastWork *w=&d->cast;
    union {uint32_t bits;float value;} prior,elapsed,remaining,observed;
    DWORD error=ERROR_SUCCESS;
    __try {
        if(!BridgeDirectCastIdentity(d)){error=ERROR_INVALID_HANDLE;__leave;}
        if(d->cast_order && BridgeObservedOrder(w->get_order,w->source)==d->cast_order){
            if(!BridgeObservedImmediateOrder(w->issue_immediate,w->source,851972u)){error=ERROR_INVALID_DATA;__leave;}
            if(!BridgeDirectCastIdentity(d)){error=ERROR_INVALID_HANDLE;__leave;}
        }
        if(d->touched&1u){
            prior.bits=w->prior_area;
            if(!BridgeObservedSetRealField(w->set_area,w->ability_handle,EFFECT_AREA_FIELD,(int32_t)d->level_index,&prior.value) ||
               (uint32_t)BridgeObservedRealField(w->get_area,w->ability_handle,EFFECT_AREA_FIELD,(int32_t)d->level_index)!=prior.bits){
                error=ERROR_INVALID_DATA;__leave;
            }
        }
        if(d->touched&2u){
            if(!BridgeObservedSetIntegerField(d->set_cost,w->ability_handle,0x616d6373u,(int32_t)d->level_index,(int32_t)d->prior_cost) ||
               BridgeObservedIntegerField(d->get_cost,w->ability_handle,0x616d6373u,(int32_t)d->level_index)!=(int32_t)d->prior_cost){
                error=ERROR_INVALID_DATA;__leave;
            }
        }
        if(d->touched&4u){
            prior.bits=d->prior_cooldown_field;
            if(!BridgeObservedSetRealField(w->set_area,w->ability_handle,0x6163646eu,(int32_t)d->level_index,&prior.value) ||
               (uint32_t)BridgeObservedRealField(w->get_area,w->ability_handle,0x6163646eu,(int32_t)d->level_index)!=prior.bits){
                error=ERROR_INVALID_DATA;__leave;
            }
        }
        if(d->touched&8u){
            remaining.bits=d->prior_cooldown_remaining;
            elapsed.bits=d->cooldown_timer?BridgeObservedTimerElapsed(d->timer_elapsed,d->cooldown_timer):0;
            if(!(elapsed.value>=0.0f && elapsed.value<=86400.0f)){error=ERROR_INVALID_DATA;__leave;}
            remaining.value=remaining.value>elapsed.value?remaining.value-elapsed.value:0.0f;
            BridgeObservedStartCooldown(d->start_cooldown,w->source,w->rawcode,&remaining.value);
            observed.bits=BridgeObservedCooldown(w->get_cooldown,w->source,w->rawcode);
            if(!(observed.value>=0.0f && observed.value<=remaining.value+0.05f &&
                 observed.value+0.05f>=remaining.value)){error=ERROR_INVALID_DATA;__leave;}
        }
        if(!BridgeDirectCastIdentity(d)){error=ERROR_INVALID_HANDLE;__leave;}
        if(w->added){
            if(!BridgeObservedRemoveAbility(w->remove_ability,w->source,w->rawcode) || BridgeDirectCastLookup(d))error=ERROR_INVALID_DATA;
        }else if(d->original_level==0 && d->expected_level>0){
            BridgeNativeSetAbilityLevelChecked(d->set_level,(BridgeAbilityLevelGetFn)d->get_level,w->source,w->rawcode,0);
            if(BridgeObservedUnsignedLevel(d->get_level,w->source,w->rawcode)!=0 ||
               BridgeDirectCastLookup(d)!=w->ability_handle)error=ERROR_INVALID_DATA;
        }
    } __finally {
        if(d->cooldown_timer){BridgeObservedDestroyTimer(d->destroy_timer,d->cooldown_timer);d->cooldown_timer=0;}
    }
    return error;
}

static uint64_t BridgeDirectCastQueryBody(void) {
    DirectCastWork *d=(DirectCastWork *)g_dispatch->work;
    WorldCastWork *w=d?&d->cast:0;
    uint32_t captured=0,count=0;
    BridgeAbilityWitness witness={0};
    union {uint32_t bits;float value;} area,x,y;
    if(!w || w->expected_tls!=g_dispatch->tls_value || !d->module_base ||
       !d->resolve_unit || !d->get_level || !w->get_ability || !w->get_ability_id ||
       !w->add_ability || !w->remove_ability || !w->get_area || !w->set_area ||
       !w->get_x || !w->get_y || !w->get_order || !w->issue_immediate ||
       !w->get_mana || !w->get_cooldown || !d->set_level || !d->get_cost || !d->set_cost ||
       !d->end_cooldown || !d->start_cooldown || !d->create_timer || !d->timer_start ||
       !d->timer_elapsed || !d->destroy_timer || !d->ability_index || w->action<1 || w->action>3 ||
       !w->rawcode || d->mode<2 || d->mode>4 || !d->passes || d->passes>255){
        if(w)w->error=340;return 0;
    }
    __try {
        if(w->action==1){
            BridgeJournalPhase(20);
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
            w->ability_handle=BridgeDirectCastLookup(d);
            uint64_t original_handle=w->ability_handle;
            d->original_level=BridgeObservedUnsignedLevel(d->get_level,w->source,w->rawcode);
            BridgeJournalPhase(21);
            int ensure_error=BridgeEnsureUnitAbilityNative(w->get_ability,d->ability_index,w->get_ability_id,w->add_ability,
                (BridgeAbilityLevelGetFn)d->get_level,d->set_level,w->source,w->rawcode,0,&witness);
            d->activation=witness.activation;
            w->ability_handle=BridgeDirectCastLookup(d);
            w->added=!original_handle && w->ability_handle;
            if(!w->ability_handle && ensure_error){w->error=344;__leave;}
            d->ability_data=BridgeEffectFindAbilityDataByFullHandle(
                (EffectResolveFn)(uintptr_t)d->module_base,d->unit_full,w->rawcode,0);
            if(!w->ability_handle || !BridgeEffectReadable(d->ability_data,0x80)){w->error=345;__leave;}
            d->ability_full=*(uint64_t *)(uintptr_t)(d->ability_data+bridge_profile.ability_handle);
            uint32_t level=BridgeObservedUnsignedLevel(d->get_level,w->source,w->rawcode);
            d->expected_level=level;d->level_index=level?level-1u:0u;captured=1;
            if(!BridgeDirectCastIdentity(d)){w->error=347;__leave;}
            if(ensure_error){w->error=ensure_error==25?344u:346u;__leave;}
            if(!level){w->error=346;__leave;}
            area.bits=w->area_bits;
            if(!(area.value>=1.0f && area.value<=100000.0f)){w->error=348;__leave;}
            BridgeJournalPhase(22);
            w->prior_area=(uint32_t)BridgeObservedRealField(w->get_area,w->ability_handle,EFFECT_AREA_FIELD,(int32_t)d->level_index);
            d->touched|=1u;
            if(!BridgeObservedSetRealField(w->set_area,w->ability_handle,EFFECT_AREA_FIELD,(int32_t)d->level_index,&area.value) ||
               (uint32_t)BridgeObservedRealField(w->get_area,w->ability_handle,EFFECT_AREA_FIELD,(int32_t)d->level_index)!=area.bits){w->error=349;__leave;}
            /* Full-screen trainer commands must not depend on ordinary mana
               costs or an existing cooldown. Restore the same level's fields,
               and advance the prior cooldown using engine time, after the hold. */
            BridgeJournalPhase(23);
            d->prior_cost=(uint32_t)BridgeObservedIntegerField(d->get_cost,w->ability_handle,0x616d6373u,(int32_t)d->level_index);
            d->prior_cooldown_field=(uint32_t)BridgeObservedRealField(w->get_area,w->ability_handle,0x6163646eu,(int32_t)d->level_index);
            d->prior_cooldown_remaining=BridgeObservedCooldown(w->get_cooldown,w->source,w->rawcode);
            union {uint32_t bits;float value;} prior_cd;
            prior_cd.bits=d->prior_cooldown_field;
            if(d->prior_cost>1000000000u || !(prior_cd.value>=0.0f && prior_cd.value<=86400.0f)){w->error=355;__leave;}
            d->touched|=2u;
            if(!BridgeObservedSetIntegerField(d->set_cost,w->ability_handle,0x616d6373u,(int32_t)d->level_index,0) ||
               BridgeObservedIntegerField(d->get_cost,w->ability_handle,0x616d6373u,(int32_t)d->level_index)!=0){w->error=355;__leave;}
            union {uint32_t bits;float value;} zero,remaining;
            zero.value=0.0f;d->touched|=4u;
            if(!BridgeObservedSetRealField(w->set_area,w->ability_handle,0x6163646eu,(int32_t)d->level_index,&zero.value) ||
               (uint32_t)BridgeObservedRealField(w->get_area,w->ability_handle,0x6163646eu,(int32_t)d->level_index)!=0){w->error=356;__leave;}
            remaining.bits=d->prior_cooldown_remaining;
            if(!(remaining.value>=0.0f && remaining.value<=86400.0f)){w->error=357;__leave;}
            if(remaining.value>0.0f){
                float timeout=86400.0f;
                d->cooldown_timer=BridgeObservedCreateTimer(d->create_timer);
                if(!d->cooldown_timer){w->error=358;__leave;}
                BridgeObservedStartTimer(d->timer_start,d->cooldown_timer,&timeout,0,0);
                d->touched|=8u;BridgeObservedEndCooldown(d->end_cooldown,w->source,w->rawcode);
                if(BridgeObservedCooldown(w->get_cooldown,w->source,w->rawcode)!=0){w->error=359;__leave;}
            }
            w->target_x=BridgeObservedUnitX(w->get_x,w->source);w->target_y=BridgeObservedUnitY(w->get_y,w->source);
            x.bits=w->target_x;y.bits=w->target_y;
            if(!(x.value==x.value && y.value==y.value)){w->error=350;__leave;}
            w->mana_before=BridgeObservedUnitState(w->get_mana,w->source,2u);
            for(uint32_t pass=0;pass<d->passes;++pass){
                BridgeJournalPhase(24);
                if(!BridgeDirectCastIdentity(d)){w->error=351;__leave;}
                /* Old effect slots are getters/no-ops in this build. Dispatch
                   through the game's typed order handlers instead. */
                if(w->rawcode==0x414e6d6fu)
                    {d->cast_order=852591u;w->issued=BridgeObservedPointOrder(w->issue_point,w->source,d->cast_order,&x.value,&y.value)?1u:0u;}
                else if(w->rawcode==0x41487463u)
                    {d->cast_order=852096u;w->issued=BridgeObservedImmediateOrder(w->issue_immediate,w->source,d->cast_order)?1u:0u;}
                else if(w->rawcode==0x414f7773u)
                    {d->cast_order=852127u;w->issued=BridgeObservedImmediateOrder(w->issue_immediate,w->source,d->cast_order)?1u:0u;}
                else if(w->rawcode==0x41457362u)
                    {d->cast_order=852183u;w->issued=BridgeObservedImmediateOrder(w->issue_immediate,w->source,d->cast_order)?1u:0u;}
                else if(w->rawcode==0x4145666bu)
                    {d->cast_order=852526u;w->issued=BridgeObservedImmediateOrder(w->issue_immediate,w->source,d->cast_order)?1u:0u;}
                else {w->error=ERROR_NOT_SUPPORTED;__leave;}
                if(!w->issued){w->error=353;__leave;}
            }
            w->order_after=BridgeObservedOrder(w->get_order,w->source);
        }else{
            if(!BridgeDirectCastIdentity(d)){
                w->error=354;
                if(w->action==2){
                    d->cleanup_error=ERROR_INVALID_HANDLE;
                    if(d->cooldown_timer){BridgeObservedDestroyTimer(d->destroy_timer,d->cooldown_timer);d->cooldown_timer=0;}
                }
                __leave;
            }
            if(w->action==2){
                d->cleanup_error=BridgeDirectCastFinish(d);
                if(d->cleanup_error)__leave;
            }else{
                BridgeJournalPhase(25);
                w->mana_after=BridgeObservedUnitState(w->get_mana,w->source,2u);
                w->cooldown_after=BridgeObservedCooldown(w->get_cooldown,w->source,w->rawcode);
                w->order_after=BridgeObservedOrder(w->get_order,w->source);
            }
        }
        w->completed=1;
    } __except(EXCEPTION_EXECUTE_HANDLER){
        w->error=GetExceptionCode();d->activation=witness.activation;
        if(w->action==1 && !captured && witness.activation)d->cleanup_error=ERROR_INVALID_DATA;
    }
    if(w->action==1 && w->error){
        __try {
            if(captured)d->cleanup_error=BridgeDirectCastFinish(d);
            else if(w->added)d->cleanup_error=ERROR_INVALID_DATA;
        } __except(EXCEPTION_EXECUTE_HANDLER){d->cleanup_error=GetExceptionCode();}
    }
    return w->completed;
}

__declspec(dllexport) uint64_t BridgeDirectCastQuery(void) {
    DirectCastWork*w=(DirectCastWork*)g_dispatch->work;
    BridgeNativeJournal*previous=bridge_native_journal;
    bridge_native_journal=w?&w->journal:0;
    __try {return BridgeDirectCastQueryBody();}
    __finally {bridge_native_journal=previous;}
}
