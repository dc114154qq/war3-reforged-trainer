/* Diagnostic only: never writes the selected source; removes its temporary unit. */
typedef struct LifecycleWork {
    uint64_t (*owner)(uint64_t);
    uint32_t (*type_id)(uint64_t);
    uint32_t (*get_x)(uint64_t), (*get_y)(uint64_t);
    uint64_t (*create)(uint64_t,uint32_t,float *,float *,float *);
    void (*remove)(uint64_t);
    int32_t (*get_level)(uint64_t);
    void (*set_level)(uint64_t,int32_t,uint32_t);
    uint64_t source;
    uint32_t source_type;
    int32_t target;
    void *expected_tls;
    uint64_t created;
    uint32_t phase,error,removed;
    int32_t before,after;
    uint32_t removed_type,created_type,reserved;
} LifecycleWork;
_Static_assert(sizeof(LifecycleWork)==128,"LifecycleWork ABI");
__declspec(dllexport) const uint32_t probe_lifecycle_abi[3]={0x24268004u,216u,128u};
__declspec(dllexport) uint64_t ProbeUnitLifecycleQuery(void) {
    LifecycleWork *w=(LifecycleWork *)g_dispatch->work;
    union { uint32_t bits; float value; } x,y;
    float facing=0.0f;
    uint64_t owner;
    if (!w) return 0;
    w->phase=1;
    if (g_dispatch->tls_value!=w->expected_tls || !w->source || w->source>0xffffffffu ||
        w->target<2 || w->target>10 || !w->owner || !w->type_id || !w->get_x ||
        !w->get_y || !w->create || !w->remove || !w->get_level || !w->set_level) {
        w->error=1; return 0;
    }
    if (w->type_id(w->source)!=w->source_type || w->get_level(w->source)<=0) {
        w->error=2;return 0;
    }
    owner=w->owner(w->source);
    x.bits=w->get_x(w->source);y.bits=w->get_y(w->source);
    if (!owner || (x.bits&0x7f800000u)==0x7f800000u || (y.bits&0x7f800000u)==0x7f800000u) {
        w->error=3;return 0;
    }
    x.value+=128.0f;
    w->phase=2;
    w->created=w->create(owner,w->source_type,&x.value,&y.value,&facing);
    if (!w->created || w->created==w->source) { w->error=4;return 0; }
    __try {
        w->phase=3;
        w->created_type=w->type_id(w->created);
        w->before=w->get_level(w->created);
        if (w->created_type!=w->source_type || w->before<=0 || w->before>=w->target) {
            w->error=5;return 0;
        }
        w->phase=4;
        w->set_level(w->created,w->target,0);
        w->after=w->get_level(w->created);
        if (w->after!=w->target) w->error=6;
        w->phase=5;
    } __finally {
        w->remove(w->created);
        w->removed=1;
        w->removed_type=w->type_id(w->created);
    }
    return w->error==0 && w->removed_type==0;
}

typedef struct MembershipWork {
    uint64_t (*create_group)(void), (*owner)(uint64_t);
    void (*enumerate)(uint64_t,uint64_t,uint64_t);
    uint8_t (*contains)(uint64_t,uint64_t);
    void (*destroy)(uint64_t);
    uint64_t unit;
    void *expected_tls;
    uint64_t group,player;
    uint32_t member,destroyed;
} MembershipWork;
_Static_assert(sizeof(MembershipWork)==80,"MembershipWork ABI");
__declspec(dllexport) const uint32_t probe_membership_abi[3]={0x24268005u,216u,80u};
__declspec(dllexport) uint64_t ProbeMembershipQuery(void) {
    MembershipWork *w=(MembershipWork *)g_dispatch->work;
    if (!w || !w->create_group || !w->owner || !w->enumerate || !w->contains || !w->destroy ||
        g_dispatch->tls_value!=w->expected_tls || !w->unit || w->unit>0xffffffffu) return 2;
    w->player=w->owner(w->unit);
    if (!w->player) return 2;
    w->group=w->create_group();
    if (!w->group) return 2;
    __try {
        w->enumerate(w->group,w->player,0);
        w->member=w->contains(w->unit,w->group);
    } __finally {
        w->destroy(w->group);w->destroyed=1;
    }
    return w->member;
}
