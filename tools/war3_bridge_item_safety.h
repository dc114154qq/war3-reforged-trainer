/* Temporary item is never given to a unit, so pickup triggers cannot run. */
typedef struct ItemSafetyWork {
    SelectionWork selection;
    uint32_t (*x)(uint64_t), (*y)(uint64_t);
    uint64_t (*create)(uint32_t,float *,float *);
    uint32_t (*item_id)(uint64_t);
    uint64_t (*equipment_type)(uint64_t), (*item_class)(uint64_t);
    uint8_t (*boolean_field)(uint64_t,uint32_t);
    void (*remove)(uint64_t);
    void *expected_tls;
    uint64_t target;
    uint32_t rawcode,error,completed,skipped,equipment,droppable;
    uint64_t temporary;
    uint32_t removed_verified,original_class;
} ItemSafetyWork;
_Static_assert(sizeof(ItemSafetyWork)==600,"ItemSafetyWork ABI");
__declspec(dllexport) const uint32_t item_safety_abi[3]={0x24268056u,216u,600u};
__declspec(dllexport) uint64_t BridgeItemSafetyQuery(void){
    ItemSafetyWork *w=(ItemSafetyWork *)g_dispatch->work;
    if(!w || w->expected_tls!=g_dispatch->tls_value || !w->rawcode || w->original_class)return 0;
    uint32_t count=(uint32_t)BridgeSelect(),matches=0;
    for(uint32_t i=0;i<count;++i)if(w->selection.rows[i].unit==w->target)++matches;
    if(w->selection.error || !w->selection.destroyed || matches!=1){w->error=410;return count;}
    __try {
        union {uint32_t bits;float value;} x,y;
        x.bits=w->x(w->target);y.bits=w->y(w->target);
        if((x.bits&0x7f800000u)==0x7f800000u || (y.bits&0x7f800000u)==0x7f800000u){w->error=415;return count;}
        w->temporary=w->create(w->rawcode,&x.value,&y.value);
        if(!w->temporary){w->error=411;return count;}
        __try {
            if(w->item_id(w->temporary)!=w->rawcode){w->error=412;return count;}
            w->equipment=(uint32_t)w->equipment_type(w->temporary);
            w->droppable=!!w->boolean_field(w->temporary,0x6964726fu);
            w->original_class=(uint32_t)w->item_class(w->temporary);
            if(w->original_class>8){w->error=416;return count;}
            if(w->equipment>9){w->error=413;return count;}
            w->skipped=!w->equipment && !w->droppable;
        } __finally {
            w->remove(w->temporary);
            w->removed_verified=!w->item_id(w->temporary);
            if(!w->removed_verified)w->error=414;
        }
        if(!w->error)w->completed=1;
    } __except(EXCEPTION_EXECUTE_HANDLER){w->error=GetExceptionCode();}
    return count;
}
