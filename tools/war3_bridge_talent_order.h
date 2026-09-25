typedef struct TalentOrderWork {
    SelectionWork selection;
    uint8_t (*order)(uint64_t,uint32_t);
    uint32_t (*level)(uint64_t,uint32_t);
    void *expected_tls;
    uint64_t target;
    uint32_t controller,order_id,choice,before,after,accepted,error,completed;
} TalentOrderWork;
_Static_assert(sizeof(TalentOrderWork)==544,"TalentOrderWork ABI");
__declspec(dllexport) const uint32_t talent_order_abi[3]={0x24268041u,216u,544u};
__declspec(dllexport) uint64_t BridgeTalentOrderQuery(void) {
    TalentOrderWork *w=(TalentOrderWork *)g_dispatch->work;uint32_t count,matches=0;
    if(!w || w->expected_tls!=g_dispatch->tls_value || !w->order || !w->level ||
       !w->target || !w->controller || !w->choice || w->order_id<0xd0311u || w->order_id>0xd0322u){
        if(w)w->error=285;return 0;
    }
    count=(uint32_t)BridgeSelect();
    if(w->selection.error || !w->selection.destroyed){w->error=286;return count;}
    for(uint32_t i=0;i<count;++i)if(w->selection.rows[i].unit==w->target)++matches;
    if(matches!=1){w->error=287;return count;}
    __try {
        if(!w->level(w->target,w->controller)){w->error=288;return count;}
        w->before=w->level(w->target,w->choice);
        if(!w->before)w->accepted=w->order(w->target,w->order_id)?1:0;
        w->after=w->level(w->target,w->choice);
        if(!w->after || (!w->before && !w->accepted)){w->error=289;return count;}
        w->completed=1;
    } __except(EXCEPTION_EXECUTE_HANDLER){w->error=GetExceptionCode();}
    return count;
}
