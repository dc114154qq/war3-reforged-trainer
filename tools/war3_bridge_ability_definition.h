/* A definition lookup loads the current map's data through the engine. */
typedef struct AbilityDefinitionRow { uint32_t rawcode,level; int32_t cost; uint32_t reserved; } AbilityDefinitionRow;
typedef struct AbilityDefinitionWork {
    int32_t (*cost)(uint32_t,int32_t);
    void *expected_tls;
    uint32_t count,error,completed,reserved;
    AbilityDefinitionRow rows[64];
} AbilityDefinitionWork;
_Static_assert(sizeof(AbilityDefinitionWork)==1056,"Ability definition ABI");
__declspec(dllexport) const uint32_t ability_definition_abi[3]={0x242680a1u,216u,1056u};
__declspec(dllexport) uint64_t BridgeAbilityDefinitionQuery(void) {
    AbilityDefinitionWork *w=(AbilityDefinitionWork *)g_dispatch->work;
    if(!w || !w->cost || w->expected_tls!=g_dispatch->tls_value || !w->count || w->count>64 || w->reserved) {
        if(w)w->error=710;return 0;
    }
    for(uint32_t i=0;i<w->count;++i) {
        if(!w->rows[i].rawcode || w->rows[i].level || w->rows[i].reserved){w->error=711;return 0;}
    }
    for(uint32_t i=0;i<w->count;++i) {
        w->rows[i].cost=w->cost(w->rows[i].rawcode,0);
        ++w->completed;
    }
    return w->completed;
}
#ifdef BRIDGE_TEST
__declspec(dllexport) uint64_t BridgeAbilityDefinitionTest(void *payload) {
    AbilityDefinitionWork *w=payload;
    BridgeCommand command;
    memset(&command,0,sizeof(command));
    command.work=payload;command.tls_value=w->expected_tls;
    g_dispatch=&command;
    uint64_t result=BridgeAbilityDefinitionQuery();
    g_dispatch=NULL;
    return result;
}
#endif
