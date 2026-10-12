/* The item remains in its original slot and retains every existing capability. */
typedef struct ItemAbilityWork {
    SelectionWork selection;
    uint64_t (*in_slot)(uint64_t,int32_t);
    uint32_t (*item_type)(uint64_t);
    int32_t (*charges)(uint64_t);
    uint64_t (*ability)(uint64_t,uint32_t),(*ability_index)(uint64_t,int32_t);
    uint32_t (*ability_id)(uint64_t);
    uint8_t (*add)(uint64_t,uint32_t);
    void *expected_tls;
    uint64_t target,item,base,unit_full,item_full;
    uint32_t rawcode,action,slot,ability_rawcode,error,completed,changed,ability_count,add_return,reserved;
    uint64_t before_handle,after_handle,abilities[32];
    uint32_t ability_ids[32];
    ItemSlot before[6],after[6];
    BridgeNativeJournal journal;
} ItemAbilityWork;
_Static_assert(sizeof(ItemAbilityWork)==58632,"Item ability ABI");
__declspec(dllexport) const uint32_t item_ability_abi[3]={0x24268070u,216u,58632u};
static int ItemAbilityIdentity(ItemAbilityWork*w,uint32_t unit_rawcode) {
    uint64_t owner=BridgeProfileResolveOwner(w->base,w->unit_full,1);
    uint64_t item_owner=BridgeProfileResolveOwner(w->base,w->item_full,1);
    if(!owner || !item_owner)return 0;
    uint64_t unit=*(uint64_t*)(uintptr_t)(owner+bridge_profile.owner_data);
    uint64_t item=*(uint64_t*)(uintptr_t)(item_owner+bridge_profile.owner_data);
    return BridgeEffectReadable(unit,bridge_profile.object_rawcode+4u) &&
        BridgeEffectReadable(item,bridge_profile.item_rawcode_mirror+4u) &&
        *(uint64_t*)(uintptr_t)(unit+bridge_profile.object_handle)==w->unit_full &&
        *(uint32_t*)(uintptr_t)(unit+bridge_profile.object_rawcode)==unit_rawcode &&
        *(uint64_t*)(uintptr_t)(item+bridge_profile.object_handle)==w->item_full &&
        *(uint32_t*)(uintptr_t)(item+bridge_profile.object_rawcode)==w->rawcode &&
        *(uint32_t*)(uintptr_t)(item+bridge_profile.item_rawcode_mirror)==w->rawcode &&
        BridgeObservedItemSlot(w->in_slot,w->target,(int32_t)w->slot)==w->item && BridgeObservedItemType(w->item_type,w->item)==w->rawcode;
}
static int ItemAbilitySnapshot(ItemAbilityWork*w,ItemSlot*rows) {
    for(int32_t i=0;i<6;++i){
        rows[i].handle=BridgeObservedItemSlot(w->in_slot,w->target,i);
        rows[i].rawcode=rows[i].handle?BridgeObservedItemType(w->item_type,rows[i].handle):0;
        rows[i].charges=rows[i].handle?BridgeObservedCharges(w->charges,rows[i].handle):0;
        if(rows[i].handle && (!rows[i].rawcode || rows[i].charges<0))return 0;
    }
    return 1;
}
static int ItemAbilityEnumerate(ItemAbilityWork*w) {
    w->ability_count=0;
    for(int32_t i=0;i<32;++i){
        uint64_t handle=BridgeObservedItemAbilityIndex(w->ability_index,w->item,i);
        if(!handle)break;
        uint32_t code=BridgeObservedAbilityId(w->ability_id,handle);
        if(!code)return 0;
        for(uint32_t j=0;j<w->ability_count;++j)if(w->abilities[j]==handle)return 0;
        w->abilities[i]=handle;w->ability_ids[i]=code;++w->ability_count;
    }
    return w->ability_count<32 || !BridgeObservedItemAbilityIndex(w->ability_index,w->item,32);
}
static int ItemAbilityLookup(ItemAbilityWork*w,uint64_t *handle,uint32_t shift) {
    *handle=0;
    if(!w->ability_rawcode)return 1;
    uint64_t direct=BridgeObservedItemAbility(w->ability,w->item,w->ability_rawcode),indexed=0;
    if(direct && BridgeObservedAbilityId(w->ability_id,direct)!=w->ability_rawcode)return 0;
    for(uint32_t i=0;i<w->ability_count;++i)
        if(!BridgeMatchEnumeratedAbility(w->abilities[i],w->ability_ids[i],w->ability_rawcode,&indexed))return 0;
    if(direct && indexed && direct!=indexed)return 0;
    /* Reuse the legacy bound-list compatibility rule: an empty direct query
       does not justify adding an ability already on this exact item. The
       list was captured in this callback, under the full item/unit identity. */
    if(direct)w->reserved|=1u<<shift;
    if(indexed)w->reserved|=2u<<shift;
    *handle=direct?direct:indexed;
    return 1;
}
static uint64_t BridgeItemAbilityQueryBody(void) {
    ItemAbilityWork*w=(ItemAbilityWork*)g_dispatch->work;
    if(!w || w->expected_tls!=g_dispatch->tls_value || !w->target || !w->item || !w->base ||
        !w->unit_full || !w->item_full || w->action>1 || w->slot>=6 || !w->rawcode || w->reserved ||
        (w->action==1 && (!w->ability_rawcode || !w->add)) ||
        !w->in_slot || !w->item_type || !w->charges || !w->ability || !w->ability_index || !w->ability_id){
        if(w)w->error=440;return 0;
    }
    uint32_t count=(uint32_t)BridgeSelect(),matches=0,unit_rawcode=0;
    for(uint32_t i=0;i<count;++i)if(w->selection.rows[i].unit==w->target){++matches;unit_rawcode=w->selection.rows[i].rawcode;}
    if(w->selection.error || !w->selection.destroyed || matches!=1){w->error=441;return count;}
    __try {
        BridgeJournalPhase(10);
        if(!ItemAbilityIdentity(w,unit_rawcode) || !ItemAbilitySnapshot(w,w->before)){w->error=442;return count;}
        BridgeJournalPhase(11);
        if(!ItemAbilityEnumerate(w)){w->error=443;return count;}
        if(!ItemAbilityLookup(w,&w->before_handle,0)){w->error=444;return count;}
        uint64_t prior[32];uint32_t prior_ids[32],prior_count=w->ability_count;
        for(uint32_t i=0;i<prior_count;++i){prior[i]=w->abilities[i];prior_ids[i]=w->ability_ids[i];}
        if(w->action==1 && !w->before_handle){
            BridgeJournalPhase(12);
            w->add_return=BridgeObservedAddItemAbility(w->add,w->item,w->ability_rawcode)?1u:0u;
        }
        BridgeJournalPhase(13);
        if(!ItemAbilityIdentity(w,unit_rawcode) || !ItemAbilitySnapshot(w,w->after) ||
           !BridgeItemSame(w->before,w->after)){w->error=446;return count;}
        if(!ItemAbilityEnumerate(w)){w->error=443;return count;}
        BridgeJournalPhase(14);
        if(!ItemAbilityLookup(w,&w->after_handle,2)){w->error=444;return count;}
        w->changed=w->after_handle!=w->before_handle;
        for(uint32_t i=0;i<prior_count;++i){
            uint32_t found=0;
            for(uint32_t j=0;j<w->ability_count;++j)if(w->abilities[j]==prior[i] && w->ability_ids[j]==prior_ids[i])++found;
            if(found!=1){w->error=447;return count;}
        }
        if(w->action==1 && (!w->after_handle || BridgeObservedAbilityId(w->ability_id,w->after_handle)!=w->ability_rawcode)){
            w->error=445;return count;
        }
        w->completed=1;
    } __except(EXCEPTION_EXECUTE_HANDLER){w->error=GetExceptionCode();}
    return count;
}

__declspec(dllexport) uint64_t BridgeItemAbilityQuery(void) {
    ItemAbilityWork*w=(ItemAbilityWork*)g_dispatch->work;
    BridgeNativeJournal*previous=bridge_native_journal;
    bridge_native_journal=w?&w->journal:0;
    __try {return BridgeItemAbilityQueryBody();}
    __finally {bridge_native_journal=previous;}
}
