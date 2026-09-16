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

/* Reforged's fog setters may raise the known post-call divide-by-zero fault
   after applying the requested state. The persistent helper already treats
   that fault as an acknowledged call; keep the current-engine route aligned. */
static DWORD BridgeFogCall(void (*fn)(uint32_t), uint32_t value) {
    if (!fn) return ERROR_INVALID_PARAMETER;
    __try {
        fn(value);
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        DWORD exception = GetExceptionCode();
        if (exception != EXCEPTION_INT_DIVIDE_BY_ZERO) return exception;
    }
    return ERROR_SUCCESS;
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
            w->after0=w->is_fog_enabled()?1u:0u;
            w->after1=w->is_fog_mask_enabled()?1u:0u;
        } else if (w->action==WORLD_SET_FOG) {
            enabled=w->value?0u:1u;
            DWORD fog_error=BridgeFogCall(w->fog_enable,enabled);
            if (!fog_error) fog_error=BridgeFogCall(w->fog_mask_enable,enabled);
            if (fog_error) {w->error=fog_error;return 0;}
            w->after0=w->is_fog_enabled()?1u:0u;
            w->after1=w->is_fog_mask_enabled()?1u:0u;
            if (w->after0!=enabled || w->after1!=enabled) {w->error=83;return 0;}
            w->changed=1;
        } else if (w->action==WORLD_SET_GAME_PAUSED) {
            w->pause_game(w->value);w->after0=w->value;w->changed=1;
        } else {
            w->end_game(w->value);w->after0=w->value;w->changed=1;
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) {w->error=84;return 0;}
    w->completed=1;return 1;
}
