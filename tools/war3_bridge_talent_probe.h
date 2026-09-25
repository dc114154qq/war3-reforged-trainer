/* Diagnostic only: native talent orders on a temporary standard hero. */
typedef struct TalentProbeWork {
    SelectionWork selection;
    uint64_t (*create)(uint64_t,uint32_t,float *,float *,float *);
    uint32_t (*type)(uint64_t);
    void (*remove)(uint64_t);
    uint32_t (*x)(uint64_t),(*y)(uint64_t);
    uint64_t (*add_item)(uint64_t,uint32_t);
    void (*remove_item)(uint64_t);
    void (*select)(uint64_t,uint32_t);
    uint32_t (*order)(uint64_t,uint32_t);
    uint32_t (*level)(uint64_t,uint32_t);
    void *expected_tls;
    uint64_t target;
    uint32_t action,order_id,rawcode,controller;
    uint64_t created,saved[24];
    uint32_t saved_count,error,completed,accepted,choice_level,reserved;
    uint64_t item;
} TalentProbeWork;
_Static_assert(sizeof(TalentProbeWork)==824,"TalentProbeWork ABI");
__declspec(dllexport) const uint32_t talent_probe_abi[3]={0x24268040u,216u,824u};

__declspec(dllexport) uint64_t BridgeTalentProbeQuery(void) {
    TalentProbeWork *w=(TalentProbeWork *)g_dispatch->work;
    uint32_t count=0;
    if(!w || w->expected_tls!=g_dispatch->tls_value || w->action>2 || w->saved_count>24){if(w)w->error=280;return 0;}
    __try {
        if(w->action==2){
            /* Cleanup uses the exact handle returned by this probe. */
            if(w->type(w->target)==w->rawcode){w->select(w->target,0);w->remove(w->target);}
            if(w->item)w->remove_item(w->item);
            for(uint32_t i=0;i<w->saved_count;++i)if(w->type(w->saved[i]))w->select(w->saved[i],1);
            w->completed=1;return 1;
        }
        count=(uint32_t)BridgeSelect();
        if(!count || w->selection.error || !w->selection.destroyed){w->error=281;return count;}
        if(w->action==0){
            w->saved_count=count;
            for(uint32_t i=0;i<count;++i)w->saved[i]=w->selection.rows[i].unit;
            union{uint32_t bits;float value;}x,y;x.bits=w->x(w->saved[0]);y.bits=w->y(w->saved[0]);
            float facing=0;
            w->created=w->create(w->selection.local_player(),w->rawcode,&x.value,&y.value,&facing);
            if(!w->created || w->type(w->created)!=w->rawcode){w->error=282;return count;}
            w->item=w->add_item(w->created,0x65627567u);
            if(!w->item || !w->level(w->created,w->controller)){w->error=283;return count;}
            w->add_item(w->created,0x7474616cu);
            for(uint32_t i=0;i<count;++i)w->select(w->saved[i],0);
            w->select(w->created,1);w->completed=1;
        }else{
            if(count!=1 || w->selection.rows[0].unit!=w->target || w->type(w->target)!=w->rawcode ||
               w->order_id<0xd0311u || w->order_id>0xd0322u){w->error=284;return count;}
            w->accepted=w->order(w->target,w->order_id);
            w->choice_level=w->level(w->target,0x55543161u);
            w->completed=1;
        }
    } __except(EXCEPTION_EXECUTE_HANDLER){w->error=GetExceptionCode();}
    return count;
}
