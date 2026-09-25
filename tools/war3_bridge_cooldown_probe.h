typedef struct CooldownProbeWork {
    SelectionWork selection;
    uint8_t (*add)(uint64_t,uint32_t),(*remove)(uint64_t,uint32_t);
    int32_t (*set_level)(uint64_t,uint32_t,int32_t),(*get_level)(uint64_t,uint32_t);
    void (*start)(uint64_t,uint32_t,float *);
    uint32_t (*cooldown)(uint64_t,uint32_t,int32_t),(*remaining)(uint64_t,uint32_t);
    void *expected_tls;
    uint64_t target_unit;
    uint32_t ability,order,changed,error,completed,count;
    float base,remaining_before,remaining_after;
    int32_t level_before,level_after;
    uint32_t reserved[12];
} CooldownProbeWork;
_Static_assert(sizeof(CooldownProbeWork)==648,"Cooldown probe ABI");
_Static_assert(offsetof(CooldownProbeWork,reserved)==596,"Cooldown diagnostics offset");
static float CooldownProbeReal(uint32_t bits){
    union{uint32_t bits;float value;}v;v.bits=bits;return v.value;
}
__declspec(dllexport) const uint32_t cooldown_probe_abi[3]={0x24268044u,216u,648u};
__declspec(dllexport) uint64_t BridgeCooldownProbeQuery(void){
    CooldownProbeWork *w=(CooldownProbeWork*)g_dispatch->work;uint32_t n,i;uint64_t unit=0;
    if(!w||w->expected_tls!=g_dispatch->tls_value||!w->ability||!w->order||!w->add||!w->remove||!w->set_level||!w->get_level||!w->start||!w->cooldown||!w->remaining){if(w)w->error=1;return 0;}
    n=(uint32_t)BridgeSelect();w->count=n;if(w->selection.error||!w->selection.destroyed||!n){w->error=2;return n;}
    if(!w->target_unit)w->target_unit=w->selection.rows[0].unit;
    for(i=0;i<n;++i)if(w->selection.rows[i].unit==w->target_unit)unit=w->target_unit;
    if(!unit){w->error=3;return n;}
    w->reserved[1]=1; /* level read */
    __try{
        w->level_before=w->get_level(unit,w->ability);
        /* Probe only a temporary ability: never overwrite a player's timer. */
        if(w->level_before){w->error=10;return n;}
        if(!w->level_before){
            w->reserved[1]=2; /* add */
            w->reserved[0]=1;
            if(!w->add(unit,w->ability)||w->get_level(unit,w->ability)<=0){w->error=5;goto cooldown_cleanup;}
        }
        w->reserved[1]=3; /* base cooldown */
        w->level_after=w->get_level(unit,w->ability);
        w->base=CooldownProbeReal(w->cooldown(unit,w->ability,0));
        w->reserved[1]=4; /* remaining before */
        w->remaining_before=CooldownProbeReal(w->remaining(unit,w->ability));
        w->reserved[1]=5; /* start */
        __try { float duration=10.0f;w->start(unit,w->ability,&duration); }
        __except((w->reserved[2]=(uint32_t)(uintptr_t)GetExceptionInformation()->ExceptionRecord->ExceptionAddress,
                  w->error=GetExceptionCode(),EXCEPTION_EXECUTE_HANDLER)){ }
        if(w->error) goto cooldown_cleanup;
        w->reserved[1]=6; /* immediate native read; do not stall the game thread */
        w->remaining_after=CooldownProbeReal(w->remaining(unit,w->ability));
        w->changed=1;w->completed=1;
    }__except((w->reserved[2]=(uint32_t)(uintptr_t)GetExceptionInformation()->ExceptionRecord->ExceptionAddress,
              w->error=GetExceptionCode(),EXCEPTION_EXECUTE_HANDLER)){ }
cooldown_cleanup:
    __try{if(w->reserved[0]&&w->get_level(unit,w->ability)>0&&!w->remove(unit,w->ability))w->error=w->error?w->error:8;}
    __except(EXCEPTION_EXECUTE_HANDLER){w->error=w->error?w->error:9;}
    return n;
}
