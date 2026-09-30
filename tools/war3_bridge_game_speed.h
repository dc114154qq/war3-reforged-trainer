typedef struct GameSpeedWork {
    uint64_t (*convert)(int32_t);
    uint64_t (*get)(void);
    void (*set)(uint64_t);
    uint64_t (*convert_flag)(int32_t);
    uint8_t (*is_flag_set)(uint64_t);
    void (*set_flag)(uint64_t,uint32_t);
    void *expected_tls;
    uint32_t action,target,before,after,changed,error,completed,lock_before,lock_after,reserved[3];
} GameSpeedWork;
_Static_assert(sizeof(GameSpeedWork)==104,"Game speed ABI");
__declspec(dllexport) const uint32_t game_speed_abi[3]={0x24268051u,216u,104u};

static uint32_t BridgeGameSpeedIndex(GameSpeedWork *w,uint64_t value) {
    for(uint32_t i=0;i<5;++i)if(w->convert((int32_t)i)==value)return i;
    return 0xffffffffu;
}

__declspec(dllexport) uint64_t BridgeGameSpeedQuery(void) {
    GameSpeedWork *w=(GameSpeedWork *)g_dispatch->work;
    if(!w || w->expected_tls!=g_dispatch->tls_value || !w->convert || !w->get || !w->set ||
       !w->convert_flag || !w->is_flag_set || !w->set_flag ||
       w->action>1 || w->target>4){if(w)w->error=360;return 0;}
    uint64_t lock_flag=0;
    uint32_t lock_touched=0,lock_known=0;
    __try {
        lock_flag=w->convert_flag(16384);
        w->lock_before=!!w->is_flag_set(lock_flag);
        lock_known=1;
        w->before=BridgeGameSpeedIndex(w,w->get());
        if(w->before>4){w->error=361;__leave;}
        if(w->action==1 && w->before!=w->target) {
            if(w->lock_before) {
                lock_touched=1;
                w->set_flag(lock_flag,0);
                if(w->is_flag_set(lock_flag)){w->error=363;__leave;}
            }
            w->set(w->convert((int32_t)w->target));
        }
        w->after=BridgeGameSpeedIndex(w,w->get());
        w->changed=w->before!=w->after;
        if(w->after>4){w->error=361;__leave;}
        if(w->action==1 && w->after!=w->target){
            w->error=362;
            if(w->after!=w->before){
                w->set(w->convert((int32_t)w->before));
                w->after=BridgeGameSpeedIndex(w,w->get());
                w->changed=w->before!=w->after;
                if(w->changed)w->error=365;
            }
            __leave;
        }
    } __except(EXCEPTION_EXECUTE_HANDLER){w->error=GetExceptionCode();}
    if(lock_known) {
        __try {
            if(lock_touched)w->set_flag(lock_flag,w->lock_before);
            w->lock_after=!!w->is_flag_set(lock_flag);
            if(w->lock_after!=w->lock_before)w->error=364;
        } __except(EXCEPTION_EXECUTE_HANDLER){w->error=GetExceptionCode();}
    }
    if(!w->error)w->completed=1;
    return w->completed;
}

#ifdef BRIDGE_TEST
static uint32_t speed_test_current,speed_test_locked,speed_test_scenario,speed_test_sets;
static uint64_t speed_test_convert(int32_t value){return (uint32_t)value;}
static uint64_t speed_test_get(void){return speed_test_current;}
static void speed_test_set(uint64_t value){
    ++speed_test_sets;
    if(speed_test_scenario==1 && value>2)return;
    if(speed_test_scenario==6 && value==4){speed_test_current=1;return;}
    if(speed_test_scenario==7 && value==4){*(volatile uint32_t *)(uintptr_t)0x108=0;return;}
    if(!speed_test_locked)speed_test_current=(uint32_t)value;
}
static uint8_t speed_test_is_locked(uint64_t flag){return flag==16384?speed_test_locked:0;}
static void speed_test_lock(uint64_t flag,uint32_t value){
    if(flag!=16384)return;
    if(speed_test_scenario==3 && !value)return;
    if(speed_test_scenario==4 && value)return;
    speed_test_locked=!!value;
}
__declspec(dllexport) uint64_t BridgeGameSpeedTest(void *payload,uint32_t scenario) {
    GameSpeedWork *w=payload;
    BridgeCommand cmd;
    memset(&cmd,0,sizeof(cmd));
    speed_test_scenario=scenario;speed_test_sets=0;
    speed_test_current=scenario==5?8:2;
    speed_test_locked=scenario==2 || scenario==3 || scenario==4;
    w->convert=speed_test_convert;w->get=speed_test_get;w->set=speed_test_set;
    w->convert_flag=speed_test_convert;w->is_flag_set=speed_test_is_locked;w->set_flag=speed_test_lock;
    cmd.work=payload;cmd.tls_value=w->expected_tls;
    cmd.specific_handler=(void *)GetProcAddress(GetModuleHandleW(L"ntdll.dll"),"__C_specific_handler");
    g_dispatch=&cmd;
    uint64_t result=BridgeGameSpeedQuery();g_dispatch=NULL;
    return result;
}
__declspec(dllexport) uint32_t BridgeGameSpeedTestSetCount(void){return speed_test_sets;}
#endif
