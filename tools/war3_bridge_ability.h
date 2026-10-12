/* Operates on current selected handles only; never searches for a donor skill. */
typedef struct BridgeAbilityWitness {uint64_t before_handle,after_handle;uint32_t add_return,activation;} BridgeAbilityWitness;
typedef struct AbilityWork {
    SelectionWork selection;
    uint8_t (*add)(uint64_t,uint32_t), (*remove)(uint64_t,uint32_t);
    int32_t (*set_level)(uint64_t,uint32_t,int32_t), (*get_level)(uint64_t,uint32_t);
    void *expected_tls;
    uint32_t rawcode,action,target,changed,error,completed;
    struct {int32_t before,after;} rows[24];
    int32_t intermediate[24];
    uint64_t target_unit;
    uint64_t (*get_ability)(uint64_t,uint32_t);
    uint32_t (*ability_id)(uint64_t);
    uint64_t (*ability_index)(uint64_t,int32_t);
    BridgeAbilityWitness witness[24];
    BridgeNativeJournal journal;
} AbilityWork;
_Static_assert(sizeof(AbilityWork)==58856,"AbilityWork ABI");
__declspec(dllexport) const uint32_t ability_batch_abi[3]={0x2426806cu,216u,58856u};
/* Profile-bound evidence: 24268+0x4bc / 24323+0x4dc read a null address
   AFTER its level mutation. R15 is not stable at handler entry, so it is not
   part of the gate. Do not patch the game or resume at a guessed RIP. Unwind
   only that exact tail fault, then require native readback == target. */
static int BridgeKnownAbilityTail(uint64_t handler,uint32_t code,uint32_t flags,
                                 uint32_t parameters,uint64_t instruction,
                                 uint64_t access,uint64_t address,uint64_t r15) {
    (void)r15;
    uint32_t tail=bridge_profile.ability_level_tail;
    return tail>0 && tail<0x10000 && handler>=0x10000 && handler<0x800000000000ULL-tail &&
        code==EXCEPTION_ACCESS_VIOLATION && !(flags&EXCEPTION_NONCONTINUABLE) && parameters>=2 &&
        instruction==handler+tail && access==0 && address==0;
}
static int BridgeAbilityTailOpcode(uint64_t instruction) {
    __try {
        /* Both verified sites: movzx eax, byte ptr [r15]. */
        return *(volatile uint32_t *)(uintptr_t)instruction==0x07b60f41u;
    } __except(EXCEPTION_EXECUTE_HANDLER) { return 0; }
}
static LONG BridgeAbilityNativeTailFilter(EXCEPTION_POINTERS *info,uint64_t setter) {
    EXCEPTION_RECORD *e=info->ExceptionRecord;
    if (BridgeKnownAbilityTail(setter,e->ExceptionCode,e->ExceptionFlags,
        e->NumberParameters,(uint64_t)(uintptr_t)e->ExceptionAddress,
        e->ExceptionInformation[0],e->ExceptionInformation[1],info->ContextRecord->R15) &&
        BridgeAbilityTailOpcode((uint64_t)(uintptr_t)e->ExceptionAddress)) {
        BridgeExceptionFilter(info);
        return EXCEPTION_EXECUTE_HANDLER;
    }
    return EXCEPTION_CONTINUE_SEARCH;
}
static int32_t BridgeAcceptAbilityTailReadback(int32_t actual,int32_t target) {
    if (actual==target && target>0) {++bridge_recovered_faults;return actual;}
    return -1;
}
typedef int32_t (*BridgeAbilityLevelSetFn)(uint64_t,uint32_t,int32_t);
typedef int32_t (*BridgeAbilityLevelGetFn)(uint64_t,uint32_t);
static int32_t BridgeNativeSetAbilityLevelChecked(BridgeAbilityLevelSetFn setter,
        BridgeAbilityLevelGetFn getter,uint64_t unit,uint32_t rawcode,int32_t level) {
    uint32_t index=BridgeJournalBegin(6,unit,rawcode,(uint64_t)(int64_t)level,0);
    __try {
        int32_t value=setter(unit,rawcode,level);
        BridgeJournalEnd(index,(uint64_t)(int64_t)value);return value;
    }
    __except(BridgeAbilityNativeTailFilter(GetExceptionInformation(),(uint64_t)(uintptr_t)setter)) {
        int32_t actual=getter(unit,rawcode);
        int32_t value=BridgeAcceptAbilityTailReadback(actual,level);
        /* Mark the setter observation before logging the recovery getter. */
        BridgeNativeJournal*j=bridge_native_journal;
        if(j && j->enabled && index<BRIDGE_JOURNAL_CAPACITY){
            j->events[index].flags|=4u;
            j->events[index].result=(uint64_t)(int64_t)value;
            j->events[index].flags|=2u;
        }
        BridgeJournalEnd(index,(uint64_t)(int64_t)value);
        if(j && j->enabled)j->last.flags|=4u;
        return value;
    }
}
static int32_t BridgeSetAbilityLevelChecked(AbilityWork *w,uint64_t unit,int32_t level) {
    return BridgeNativeSetAbilityLevelChecked(w->set_level,w->get_level,unit,w->rawcode,level);
}
/* Level zero is not evidence that no ability instance exists. In particular,
   dormant hero/item abilities must be activated, not added a second time.
   A false add result is followed by an exact instance/level readback; it never
   causes another UnitAddAbility call. Bits: add called, accepted, dormant,
   activated, false return with independently confirmed active instance. */
typedef uint64_t (*BridgeAbilityLookupFn)(uint64_t,uint32_t);
typedef uint32_t (*BridgeAbilityIdFn)(uint64_t);
typedef uint8_t (*BridgeAbilityAddFn)(uint64_t,uint32_t);
typedef uint64_t (*BridgeAbilityIndexFn)(uint64_t,int32_t);
/* Both unit and item lookup must distinguish a missing direct-query result
   from a missing instance. Only one matching instance is accepted. */
static int BridgeMatchEnumeratedAbility(uint64_t candidate,uint32_t code,
        uint32_t rawcode,uint64_t *found) {
    if(!candidate || !code)return 0;
    if(code!=rawcode)return 1;
    if(*found)return 0;
    *found=candidate;return 1;
}
static uint64_t BridgeFindUnitAbility(BridgeAbilityLookupFn lookup,BridgeAbilityIndexFn indexed,BridgeAbilityIdFn id,
        uint64_t unit,uint32_t rawcode,int *error) {
    uint64_t handle=BridgeObservedUnitAbility(lookup,unit,rawcode),found=0;
    *error=0;
    if(handle){if(BridgeObservedAbilityId(id,handle)!=rawcode)*error=34;return *error?0:handle;}
    for(int32_t i=0;i<256;++i){
        uint64_t candidate=BridgeObservedUnitAbilityIndex(indexed,unit,i);
        if(!candidate)return found;
        uint32_t code=BridgeObservedAbilityId(id,candidate);
        if(!code){*error=34;return 0;}
        if(!BridgeMatchEnumeratedAbility(candidate,code,rawcode,&found)){*error=37;return 0;}
    }
    *error=37;return 0;
}
static int BridgeEnsureUnitAbilityNative(BridgeAbilityLookupFn lookup,BridgeAbilityIndexFn indexed,BridgeAbilityIdFn id,
        BridgeAbilityAddFn add,BridgeAbilityLevelGetFn getter,BridgeAbilityLevelSetFn setter,
        uint64_t unit,uint32_t rawcode,int32_t desired,BridgeAbilityWitness *witness) {
    int lookup_error=0;
    uint64_t handle=BridgeFindUnitAbility(lookup,indexed,id,unit,rawcode,&lookup_error);
    if(lookup_error)return lookup_error;
    int32_t level=BridgeObservedLevel(getter,unit,rawcode);
    if(handle && BridgeObservedAbilityId(id,handle)!=rawcode)return 34;
    if(!handle && level>0){
        /* Retain the published positive-level behaviour for an engine that
           omits this active ability from both reflection natives. */
        witness->activation|=32u;
        if(desired>0 && desired!=level){
            if(BridgeNativeSetAbilityLevelChecked(setter,getter,unit,rawcode,desired)!=desired ||
               BridgeObservedLevel(getter,unit,rawcode)!=desired)return 35;
            witness->activation|=8u;
        }
        return 0;
    }
    if(!handle){
        witness->activation|=1u;
        witness->add_return=BridgeObservedAddAbility(add,unit,rawcode)?1u:0u;
        if(witness->add_return)witness->activation|=2u;
        handle=BridgeFindUnitAbility(lookup,indexed,id,unit,rawcode,&lookup_error);level=BridgeObservedLevel(getter,unit,rawcode);
        if(lookup_error)return lookup_error;
        if(!handle)return witness->add_return?36:25;
        if(BridgeObservedAbilityId(id,handle)!=rawcode)return 34;
        if(!witness->add_return && level>0)witness->activation|=16u;
    }else if(!level)witness->activation|=4u;
    witness->after_handle=handle;
    if(level<0)return 34;
    if(!level || (desired>0 && level!=desired)){
        int32_t requested=desired>0?desired:1;
        if(BridgeNativeSetAbilityLevelChecked(setter,getter,unit,rawcode,requested)!=requested ||
           BridgeObservedLevel(getter,unit,rawcode)!=requested)return 35;
        if(BridgeFindUnitAbility(lookup,indexed,id,unit,rawcode,&lookup_error)!=handle ||
           lookup_error || BridgeObservedAbilityId(id,handle)!=rawcode)return 34;
        witness->activation|=8u;
    }
    witness->after_handle=handle;
    return 0;
}
static int BridgeEnsureUnitAbility(AbilityWork*w,uint64_t unit,uint32_t index,int32_t desired) {
    return BridgeEnsureUnitAbilityNative(w->get_ability,w->ability_index,w->ability_id,w->add,w->get_level,w->set_level,
        unit,w->rawcode,desired,&w->witness[index]);
}
static uint64_t BridgeAbilityQueryBody(void) {
    AbilityWork *w=(AbilityWork *)g_dispatch->work;
    uint64_t count,unit;
    uint32_t i;
    if (!w) return 0;
    if (g_dispatch->tls_value!=w->expected_tls || !w->rawcode || w->action>5 || w->target>100000 ||
        ((w->action==3 || w->action==4) && !w->target) ||
        ((w->action==0 || w->action==2 || w->action==5) && w->target) ||
        !w->add || !w->remove || !w->set_level || !w->get_level || !w->get_ability || !w->ability_id || !w->ability_index) {
        w->error=20;return 0;
    }
    count=BridgeSelect();
    if (w->selection.error || !w->selection.destroyed || count!=w->selection.count || !count) {w->error=21;return count;}
    if(w->target_unit){
        uint32_t matches=0;
        for(i=0;i<count;++i)if(w->selection.rows[i].unit==w->target_unit)++matches;
        if(matches!=1){w->error=32;return count;}
    }
    for (i=0;i<count;++i) {
        BridgeJournalPhase(1);
        unit=w->selection.rows[i].unit;
        if (BridgeObservedUnitType(w->selection.unit_type_id,unit)!=w->selection.rows[i].rawcode) {w->error=22;return count;}
        w->rows[i].before=BridgeObservedLevel(w->get_level,unit,w->rawcode);
        int lookup_error=0;
        w->witness[i].before_handle=BridgeFindUnitAbility(w->get_ability,w->ability_index,w->ability_id,unit,w->rawcode,&lookup_error);
        if(lookup_error){w->error=(uint32_t)lookup_error;return count;}
        if (w->rows[i].before<0 || (w->witness[i].before_handle && BridgeObservedAbilityId(w->ability_id,w->witness[i].before_handle)!=w->rawcode) ||
            (w->action==3 && !w->witness[i].before_handle && !w->rows[i].before &&
             (!w->target_unit || unit==w->target_unit))) {w->error=23;return count;}
    }
    for (i=0;i<count;++i) {
        BridgeJournalPhase(2);
        int32_t before=w->rows[i].before;
        int lookup_error=0;
        uint64_t captured=0;
        unit=w->selection.rows[i].unit;
        if(w->target_unit && unit!=w->target_unit){
            w->rows[i].after=BridgeObservedLevel(w->get_level,unit,w->rawcode);w->intermediate[i]=w->rows[i].after;
            w->witness[i].after_handle=BridgeFindUnitAbility(w->get_ability,w->ability_index,w->ability_id,unit,w->rawcode,&lookup_error);
            if(w->rows[i].after!=before){w->error=33;return count;}
            ++w->completed;continue;
        }
        if (BridgeObservedUnitType(w->selection.unit_type_id,unit)!=w->selection.rows[i].rawcode || BridgeObservedLevel(w->get_level,unit,w->rawcode)!=before ||
            BridgeFindUnitAbility(w->get_ability,w->ability_index,w->ability_id,unit,w->rawcode,&lookup_error)!=w->witness[i].before_handle ||
            lookup_error) {w->error=24;return count;}
        __try {
            if (w->action==1 || w->action==4) {
                BridgeJournalPhase(3);
                w->error=100+i;
                int error=BridgeEnsureUnitAbility(w,unit,i,w->action==4 && before>0 ? before : (int32_t)w->target);
                captured=w->witness[i].after_handle;
                if(error){w->error=(uint32_t)error;return count;}
                w->error=0;
                if(!before || (w->target && before!=(int32_t)w->target && w->action==1))++w->changed;
            }
            if (w->action==3) {
                BridgeJournalPhase(3);
                int32_t current;
                w->error=200+i;current=BridgeObservedLevel(w->get_level,unit,w->rawcode);w->error=0;
                if (current!=(int32_t)w->target) {
                    w->error=300+i;
                    if (BridgeSetAbilityLevelChecked(w,unit,(int32_t)w->target)!=(int32_t)w->target) {w->error=26;return count;}
                    w->error=0;
                    if (before>0) ++w->changed;
                }
            }
            if (w->action==2 && (w->witness[i].before_handle || before>0)) {
                BridgeJournalPhase(4);
                if (!BridgeObservedRemoveAbility(w->remove,unit,w->rawcode)) {w->error=27;return count;}
                ++w->changed;
            }
            if (w->action==5) {
                BridgeJournalPhase(4);
                if (w->witness[i].before_handle || before>0) {
                    w->error=400+i;
                    if (!BridgeObservedRemoveAbility(w->remove,unit,w->rawcode) || BridgeObservedLevel(w->get_level,unit,w->rawcode)!=0) {w->error=30;return count;}
                    w->error=0;
                }
                w->error=500+i;
                int error=BridgeEnsureUnitAbility(w,unit,i,1);
                if(error){w->error=(uint32_t)error;return count;}
                w->error=0;++w->changed;
            }
            w->intermediate[i]=BridgeObservedLevel(w->get_level,unit,w->rawcode);
        } __finally {
            BridgeJournalPhase(5);
            /* Preserve the actual post-call level even when the setter faults. */
            if (w->error>=300 && w->error<324) w->intermediate[i]=BridgeObservedLevel(w->get_level,unit,w->rawcode);
            /* Diagnostic action restores only an ability that was absent. */
            uint64_t current=BridgeFindUnitAbility(w->get_ability,w->ability_index,w->ability_id,unit,w->rawcode,&lookup_error);
            if (w->action==4 && !before && current) {
                if(w->witness[i].before_handle){
                    if(lookup_error || current!=w->witness[i].before_handle ||
                       (BridgeSetAbilityLevelChecked(w,unit,0),BridgeObservedLevel(w->get_level,unit,w->rawcode)!=0))w->error=28;
                }else if(lookup_error || !captured || current!=captured ||
                         BridgeObservedUnitType(w->selection.unit_type_id,unit)!=w->selection.rows[i].rawcode ||
                        !BridgeObservedRemoveAbility(w->remove,unit,w->rawcode))w->error=28;
            }
            w->rows[i].after=BridgeObservedLevel(w->get_level,unit,w->rawcode);
            w->witness[i].after_handle=BridgeFindUnitAbility(w->get_ability,w->ability_index,w->ability_id,unit,w->rawcode,&lookup_error);
            if(lookup_error && !w->error)w->error=(uint32_t)lookup_error;
        }
        if ((w->action==0 && w->rows[i].after!=before) ||
            (w->action==1 && w->rows[i].after!=(w->target ? (int32_t)w->target : before ? before : 1)) ||
            (w->action==2 && w->rows[i].after!=0) ||
            (w->action==3 && w->rows[i].after!=(int32_t)w->target) ||
            (w->action==4 && (w->rows[i].after!=before || (!before && w->intermediate[i]!=(int32_t)w->target))) ||
            (w->action==5 && w->rows[i].after<=0)) {
            w->error=29;return count;
        }
        if (w->error) return count;
        ++w->completed;
    }
    return count;
}

__declspec(dllexport) uint64_t BridgeAbilityQuery(void) {
    AbilityWork*w=(AbilityWork*)g_dispatch->work;
    BridgeNativeJournal*previous=bridge_native_journal;
    bridge_native_journal=w?&w->journal:0;
    __try {return BridgeAbilityQueryBody();}
    __finally {bridge_native_journal=previous;}
}
