/* Current-build 24268 batch for global game and local-player operations. */
#define WORLD_SET_TECH 1u
#define WORLD_SET_XP_RATE 2u
#define WORLD_QUERY_FOG 3u
#define WORLD_SET_FOG 4u
#define WORLD_SET_GAME_PAUSED 5u
#define WORLD_END_GAME 6u

typedef struct WorldWork {
    uint64_t (*get_local_player)(void);
    void (*set_tech_max)(uint64_t,uint32_t,uint32_t);
    void (*set_tech_researched)(uint64_t,uint32_t,uint32_t);
    void (*set_xp_rate)(uint64_t,float);
    void (*fog_enable)(uint32_t);
    void (*fog_mask_enable)(uint32_t);
    uint8_t (*is_fog_enabled)(void);
    uint8_t (*is_fog_mask_enabled)(void);
    void (*pause_game)(uint32_t);
    void (*end_game)(uint32_t);
    void *expected_tls;
    uint32_t action,rawcode,value,changed,error,completed,after0,after1,reserved0,reserved1;
} WorldWork;
_Static_assert(sizeof(WorldWork)==128,"WorldWork ABI");
__declspec(dllexport) const uint32_t world_batch_abi[3]={0x24268017u,216u,128u};

static float WorldReal(uint32_t bits) {
    union {uint32_t bits;float value;} value;value.bits=bits;return value.value;
}

/* Reforged's fog setters may raise a tail fault after applying their state.
   Execute both setters independently and accept only a verified final state. */
static int BridgeFogExceptionFilter(
    EXCEPTION_POINTERS *info, WorldWork *w, uint32_t phase,
    uint32_t *value, DWORD *error
) {
    uint64_t address=(uint64_t)(uintptr_t)info->ExceptionRecord->ExceptionAddress;
    *error=info->ExceptionRecord->ExceptionCode;
    if (value) *value=(uint32_t)(info->ContextRecord->Rax&1u);
    if (w) {
        w->rawcode=phase;
        w->reserved0=(uint32_t)address;
        w->reserved1=(uint32_t)(address>>32);
        if (phase==1u) {
            w->get_local_player=(uint64_t (*)(void))(uintptr_t)address;
            w->set_tech_researched=(void (*)(uint64_t,uint32_t,uint32_t))
                (uintptr_t)(info->ExceptionRecord->NumberParameters>=1?
                    info->ExceptionRecord->ExceptionInformation[0]:~0ULL);
            w->set_xp_rate=(void (*)(uint64_t,float))
                (uintptr_t)(info->ExceptionRecord->NumberParameters>=2?
                    info->ExceptionRecord->ExceptionInformation[1]:~0ULL);
        } else if (phase==2u) {
            w->set_tech_max=(void (*)(uint64_t,uint32_t,uint32_t))(uintptr_t)address;
            w->fog_enable=(void (*)(uint32_t))
                (uintptr_t)(info->ExceptionRecord->NumberParameters>=1?
                    info->ExceptionRecord->ExceptionInformation[0]:~0ULL);
            w->fog_mask_enable=(void (*)(uint32_t))
                (uintptr_t)(info->ExceptionRecord->NumberParameters>=2?
                    info->ExceptionRecord->ExceptionInformation[1]:~0ULL);
        } else if (phase==3u) {
            w->get_local_player=(uint64_t (*)(void))(uintptr_t)address;
        } else if (phase==4u) {
            w->set_tech_max=(void (*)(uint64_t,uint32_t,uint32_t))(uintptr_t)address;
            w->set_tech_researched=(void (*)(uint64_t,uint32_t,uint32_t))(uintptr_t)info->ContextRecord->Rsp;
            w->set_xp_rate=(void (*)(uint64_t,float))(uintptr_t)info->ContextRecord->Rbx;
            w->fog_enable=(void (*)(uint32_t))(uintptr_t)info->ContextRecord->Rax;
            w->fog_mask_enable=(void (*)(uint32_t))(uintptr_t)info->ContextRecord->Rcx;
            w->is_fog_enabled=(uint8_t (*)(void))(uintptr_t)info->ContextRecord->Rdx;
            w->is_fog_mask_enabled=(uint8_t (*)(void))(uintptr_t)info->ContextRecord->R8;
        }
    }
    return EXCEPTION_EXECUTE_HANDLER;
}

static int BridgeKnownFogGate(
    uint64_t fn,uint32_t phase,uint32_t code,uint32_t flags,uint32_t parameters,
    uint64_t instruction,uint64_t access,uint64_t address,uint32_t *length
) {
    uint64_t offset;
    if (phase==1u) {offset=0x519u;*length=5u;}
    else if (phase==2u) {offset=0x3c9u;*length=5u;}
    else if (phase==3u || phase==4u) {offset=0x3d2u;*length=3u;}
    else return 0;
    return fn>=0x10000u && fn<0x800000000000ULL-offset &&
        code==EXCEPTION_ACCESS_VIOLATION && !(flags&EXCEPTION_NONCONTINUABLE) &&
        parameters>=2u && instruction==fn+offset && access==0u && address==0u;
}

static int BridgeKnownFogTail(
    uint64_t fn,uint32_t phase,uint32_t code,uint32_t flags,uint32_t parameters,
    uint64_t instruction,uint64_t access,uint64_t address
) {
    uint64_t offset;
    if (phase==1u) offset=0xb58u;
    else if (phase==2u) offset=0x8a8u;
    else return 0;
    return fn>=0x10000u && fn<0x800000000000ULL-offset &&
        code==EXCEPTION_ACCESS_VIOLATION && !(flags&EXCEPTION_NONCONTINUABLE) &&
        parameters>=2u && instruction==fn+offset && access==0u && address==0u;
}

static int BridgeFogControlFlowFilter(
    EXCEPTION_POINTERS *info,WorldWork *w,uint32_t phase,void *fn,
    uint32_t *resumed,uint32_t *value,DWORD *error
) {
    EXCEPTION_RECORD *e=info->ExceptionRecord;
    uint32_t length=0;
    if (!*resumed && BridgeKnownFogGate(
        (uint64_t)(uintptr_t)fn,phase,e->ExceptionCode,e->ExceptionFlags,
        e->NumberParameters,(uint64_t)(uintptr_t)e->ExceptionAddress,
        e->ExceptionInformation[0],e->ExceptionInformation[1],&length
    )) {
        *resumed=1u;
        info->ContextRecord->Rip+=length;
        ++bridge_recovered_faults;
        return EXCEPTION_CONTINUE_EXECUTION;
    }
    if (BridgeKnownFogTail(
        (uint64_t)(uintptr_t)fn,phase,e->ExceptionCode,e->ExceptionFlags,
        e->NumberParameters,(uint64_t)(uintptr_t)e->ExceptionAddress,
        e->ExceptionInformation[0],e->ExceptionInformation[1]
    )) {
        *error=e->ExceptionCode;
        ++bridge_recovered_faults;
        return EXCEPTION_EXECUTE_HANDLER;
    }
    return BridgeFogExceptionFilter(info,w,phase,value,error);
}

static DWORD BridgeFogCall(
    void (*fn)(uint32_t), uint32_t value, WorldWork *w, uint32_t phase
) {
    DWORD error=ERROR_SUCCESS;
    uint32_t resumed=0;
    if (!fn) return ERROR_INVALID_PARAMETER;
    __try {
        fn(value);
    } __except(BridgeFogControlFlowFilter(
        GetExceptionInformation(),w,phase,(void *)fn,&resumed,0,&error
    )) {}
    return error;
}

static DWORD BridgeFogQuery(
    uint8_t (*fn)(void),uint32_t *value,WorldWork *w,uint32_t phase
) {
    DWORD error=ERROR_SUCCESS;
    uint32_t resumed=0;
    if (!fn || !value) return ERROR_INVALID_PARAMETER;
    __try {
        *value=fn()?1u:0u;
    } __except(BridgeFogControlFlowFilter(
        GetExceptionInformation(),w,phase,(void *)fn,&resumed,value,&error
    )) {}
    return error;
}

__declspec(dllexport) uint64_t BridgeWorldQuery(void) {
    WorldWork *w=(WorldWork *)g_dispatch->work;
    uint64_t player;
    float rate;
    uint32_t enabled;
    if (!w || w->expected_tls!=g_dispatch->tls_value || w->action<WORLD_SET_TECH || w->action>WORLD_END_GAME ||
        (w->action==WORLD_SET_TECH ? (!w->rawcode || w->value>100000) :
         w->action==WORLD_SET_XP_RATE ? (w->rawcode || (rate=WorldReal(w->value),rate!=rate || rate<0.0f || rate>10000.0f)) :
         w->action==WORLD_QUERY_FOG ? (w->rawcode || w->value) : (w->rawcode || w->value>1))) {
        if (w) w->error=80;return 0;
    }
    if (!w->get_local_player || !w->set_tech_max || !w->set_tech_researched || !w->set_xp_rate ||
        !w->fog_enable || !w->fog_mask_enable || !w->is_fog_enabled || !w->is_fog_mask_enabled ||
        !w->pause_game || !w->end_game) {w->error=81;return 0;}
    __try {
        if (w->action==WORLD_SET_TECH || w->action==WORLD_SET_XP_RATE) {
            player=w->get_local_player();
            if (!player) {w->error=82;return 0;}
            if (w->action==WORLD_SET_TECH) {
                w->set_tech_max(player,w->rawcode,w->value);
                w->set_tech_researched(player,w->rawcode,w->value);
                w->after0=w->value;
            } else {
                w->set_xp_rate(player,WorldReal(w->value));
                w->after0=w->value;
            }
            w->changed=1;
        } else if (w->action==WORLD_QUERY_FOG) {
            DWORD fog_query_error=BridgeFogQuery(w->is_fog_enabled,&w->after0,w,3u);
            DWORD mask_query_error=BridgeFogQuery(w->is_fog_mask_enabled,&w->after1,w,4u);
            if ((fog_query_error && fog_query_error!=EXCEPTION_ACCESS_VIOLATION) ||
                (mask_query_error && mask_query_error!=EXCEPTION_ACCESS_VIOLATION)) {
                w->error=fog_query_error ? fog_query_error : mask_query_error;
                return 0;
            }
        } else if (w->action==WORLD_SET_FOG) {
            DWORD fog_error,mask_error,fog_query_error,mask_query_error;
            enabled=w->value?0u:1u;
            fog_error=BridgeFogCall(w->fog_enable,enabled,w,1u);
            mask_error=BridgeFogCall(w->fog_mask_enable,enabled,w,2u);
            fog_query_error=BridgeFogQuery(w->is_fog_enabled,&w->after0,w,3u);
            mask_query_error=BridgeFogQuery(w->is_fog_mask_enabled,&w->after1,w,4u);
            if ((fog_query_error && fog_query_error!=EXCEPTION_ACCESS_VIOLATION) ||
                (mask_query_error && mask_query_error!=EXCEPTION_ACCESS_VIOLATION)) {
                w->error=fog_query_error ? fog_query_error : mask_query_error;
                return 0;
            }
            if (w->after0!=enabled || w->after1!=enabled) {
                w->error=fog_error ? fog_error : (mask_error ? mask_error : 83u);
                return 0;
            }
            w->changed=1;
        } else if (w->action==WORLD_SET_GAME_PAUSED) {
            w->pause_game(w->value);w->after0=w->value;w->changed=1;
        } else {
            w->end_game(w->value);w->after0=w->value;w->changed=1;
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) {w->error=84;return 0;}
    w->completed=1;return 1;
}
