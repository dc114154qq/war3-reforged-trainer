typedef struct TalentIconControlWork {
    void *expected_tls;
    uint64_t image_base;
    uint32_t (*install)(void),(*remove)(void);
    BOOLEAN (WINAPI *add_table)(PRUNTIME_FUNCTION,DWORD,DWORD64);
    BOOLEAN (WINAPI *delete_table)(PRUNTIME_FUNCTION);
    PRUNTIME_FUNCTION table;
    uint8_t *config;
    uint32_t count,action,registered,error,completed,result,installed,active;
} TalentIconControlWork;
_Static_assert(sizeof(TalentIconControlWork)==96,"Talent icon control ABI");
__declspec(dllexport) const uint32_t talent_icon_control_abi[3]={0x24268046u,216u,96u};
__declspec(dllexport) uint64_t BridgeTalentIconControl(void){
    TalentIconControlWork *w=(TalentIconControlWork *)g_dispatch->work;
    if(!w || w->expected_tls!=g_dispatch->tls_value || !w->image_base || !w->install ||
       !w->remove || !w->add_table || !w->delete_table || !w->table || !w->config ||
       !w->count || w->action>1 || w->registered>1){if(w)w->error=1;return 0;}
    __try {
        if(!w->action){
            if(!w->registered){
                w->registered=w->add_table(w->table,w->count,w->image_base);
                if(!w->registered){w->error=2;w->completed=1;return 1;}
            }
            w->result=w->install();
        }else w->result=w->remove();
        w->installed=*(uint32_t *)(w->config+52);
        w->error=*(uint32_t *)(w->config+56);
        w->active=*(uint32_t *)(w->config+72);
        if(!w->installed && !w->active && w->registered){
            if(w->delete_table(w->table))w->registered=0;
            else w->error=3;
        }
        w->completed=1;
    }__except(BridgeExceptionFilter(GetExceptionInformation())){
        /* Preserve the separately mapped image and unwind table on uncertainty. */
        w->error=GetExceptionCode();w->completed=1;w->installed=1;
    }
    return 1;
}
