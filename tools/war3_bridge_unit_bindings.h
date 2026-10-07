/* Exact conversion between selected native handles and full object identities. */
typedef struct UnitBindingRef {uint64_t full,object;uint32_t rawcode,reserved;} UnitBindingRef;
typedef struct UnitBindingsWork {
    SelectionWork selection;
    uint64_t base;
    uint64_t (*resolve_unit)(uint64_t);
    uint32_t expected_count,strict_selection,error,completed;
    UnitBindingRef refs[24];
    uint64_t native_handles[24];
} UnitBindingsWork;
_Static_assert(sizeof(UnitBindingsWork)==1280,"Unit binding ABI");
__declspec(dllexport) const uint32_t unit_bindings_abi[3]={0x24268065u,216u,1280u};
__declspec(dllexport) uint64_t BridgeUnitBindingsQuery(void){
    UnitBindingsWork *w=(UnitBindingsWork *)g_dispatch->work;
    if(!w || !w->base || !w->resolve_unit || !w->expected_count || w->expected_count>24 || w->strict_selection>1)return 0;
    uint64_t count=0;
    __try {
        count=BridgeSelect();
        if(w->selection.error || !w->selection.destroyed){w->error=2;return count;}
        if(w->strict_selection && count!=w->expected_count){w->error=3;return count;}
        for(uint32_t i=0;i<w->expected_count;++i){
            UnitBindingRef *ref=&w->refs[i];uint32_t found=0;
            if(!ref->full || !ref->object || !ref->rawcode || ref->reserved){w->error=1;return count;}
            uint64_t owner=BridgeEffectResolveObjectTable(w->base,ref->full);
            if(!owner || *(uint64_t *)(uintptr_t)(owner+bridge_profile.owner_data)!=ref->object ||
               *(uint64_t *)(uintptr_t)(ref->object+bridge_profile.object_handle)!=ref->full ||
               *(uint32_t *)(uintptr_t)(ref->object+bridge_profile.object_rawcode)!=ref->rawcode){w->error=4;return count;}
            for(uint32_t j=0;j<count;++j){
                SelectionRow *row=&w->selection.rows[j];
                if(row->rawcode==ref->rawcode && w->resolve_unit(row->unit)==ref->object){
                    w->native_handles[i]=row->unit;++found;
                }
            }
            if(found!=1){w->error=4;return count;}
            for(uint32_t prior=0;prior<i;++prior)if(w->native_handles[prior]==w->native_handles[i]){w->error=4;return count;}
            ++w->completed;
        }
    } __except(BridgeExceptionFilter(GetExceptionInformation())) {w->error=5;}
    return count;
}
