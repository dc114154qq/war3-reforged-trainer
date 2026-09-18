typedef struct War3CloneAbility {
    uint64_t handle, object, full, wrapper, tag;
    uint32_t rawcode;
    int32_t index;
} War3CloneAbility;

typedef struct War3CloneAbilities {
    War3CloneAbility source[256], target[256];
    War3CloneAbility *active[2];
    JassGetUnitAbilityByIndexFn by_index;
    JassUnitRawcodeFn lookup;
    unsigned count;
} War3CloneAbilities;

/* Captured pointers only, inside the caller's SEH region. Owner links bind an
   ability to this exact unit as well as its object-table generation. */
static void war3_clone_ability_object(const NativeCommand *unit,const War3CloneAbility *a) {
    if(!a || !a->handle) return;
    JassUnitHandleResolveFn resolve=(JassUnitHandleResolveFn)(uintptr_t)g_persistent_ability_resolver;
    War3AgentResolveFn agent=(War3AgentResolveFn)(uintptr_t)g_persistent_agent_resolver;
    if(resolve(a->handle)!=a->object ||
       agent((uint32_t)a->full,(uint32_t)(a->full>>32))!=a->wrapper ||
       *(uint64_t *)(uintptr_t)(a->object+0x18)!=a->full ||
       *(uint64_t *)(uintptr_t)(a->object+0x68)!=unit->ops[0].handler ||
       *(uint32_t *)(uintptr_t)(a->object+0x70)!=a->rawcode ||
       *(uint32_t *)(uintptr_t)(a->object+0x78)!=a->rawcode ||
       *(uint64_t *)(uintptr_t)(a->wrapper+0x18)!=a->tag ||
       *(uint64_t *)(uintptr_t)(a->wrapper+0x20)!=a->full ||
       *(uint64_t *)(uintptr_t)(a->wrapper+0x50)!=unit->ops[0].arg1 ||
       *(uint64_t *)(uintptr_t)(a->wrapper+0x90)!=a->object)
        RaiseException(ERROR_INVALID_HANDLE,0,0,NULL);
}

static void war3_clone_ability_state(War3CloneGuard *guard) {
    War3CloneAbilities *s=guard->abilities;
    if(!s) return;
    war3_clone_ability_object(guard->source,s->active[0]);
    war3_clone_ability_object(&guard->target,s->active[1]);
}

static void war3_clone_ability_membership(War3CloneGuard *guard) {
    War3CloneAbilities *s=guard->abilities;
    if(!s) return;
    for(unsigned n=0;n<2;++n) {
        War3CloneAbility *a=s->active[n];
        if(!a) continue;
        uint64_t current=n?s->lookup(guard->target.unit_handle,a->rawcode):
            s->by_index(guard->source->unit_handle,a->index);
        war3_clone_check_state(guard);
        if(current!=a->handle) RaiseException(ERROR_INVALID_HANDLE,0,0,NULL);
    }
}

static void war3_clone_capture_ability(War3CloneGuard *guard,const NativeCommand *unit,
                                     uint64_t handle,int32_t index,War3CloneAbility *a) {
    JassUnitHandleResolveFn resolve=(JassUnitHandleResolveFn)(uintptr_t)g_persistent_ability_resolver;
    War3AgentResolveFn agent=(War3AgentResolveFn)(uintptr_t)g_persistent_agent_resolver;
    if(!handle) RaiseException(ERROR_NOT_FOUND,0,0,NULL);
    a->handle=handle;a->index=index;a->object=resolve(handle);
    if(!war3_readable_span(a->object,0x80)) RaiseException(ERROR_INVALID_ADDRESS,0,0,NULL);
    a->full=*(uint64_t *)(uintptr_t)(a->object+0x18);
    a->rawcode=*(uint32_t *)(uintptr_t)(a->object+0x70);
    a->wrapper=agent((uint32_t)a->full,(uint32_t)(a->full>>32));
    if(!war3_readable_span(a->wrapper,0x98)) RaiseException(ERROR_INVALID_ADDRESS,0,0,NULL);
    a->tag=*(uint64_t *)(uintptr_t)(a->wrapper+0x18);
    if(!a->full || !a->rawcode || (uint32_t)a->tag!=0x2b61676cu || !(a->tag>>32))
        RaiseException(ERROR_INVALID_DATA,0,0,NULL);
    war3_clone_ability_object(unit,a);
    war3_clone_check(guard);
}

static void war3_clone_saved_ability_objects(War3CloneGuard *guard) {
    War3CloneAbilities *s=guard->abilities;
    if(!s) return;
    for(unsigned n=0;n<s->count;++n) {
        war3_clone_ability_object(guard->source,&s->source[n]);
        war3_clone_ability_object(&guard->target,&s->target[n]);
    }
}

static void war3_clone_check_saved_abilities(War3CloneGuard *guard) {
    War3CloneAbilities *s=guard->abilities;
    if(!s) return;
    for(unsigned n=0;n<s->count;++n) {
        s->active[0]=&s->source[n];
        s->active[1]=s->target[n].handle?&s->target[n]:NULL;
        war3_clone_check(guard);
    }
    uint64_t extra=s->by_index(guard->source->unit_handle,(int32_t)s->count);
    war3_clone_check(guard);
    if(extra) RaiseException(ERROR_INVALID_HANDLE,0,0,NULL);
    war3_clone_saved_ability_objects(guard);
    s->active[0]=s->active[1]=NULL;
}

static void war3_clone_prepare_abilities(War3CloneGuard *guard,JassGetUnitAbilityByIndexFn by_index,
                                       JassGetAbilityIdFn get_id) {
    if(!guard->source) return;
    uint64_t lookup=war3_persistent_native_handler("BlzGetUnitAbility");
    if(!war3_executable_pointer(lookup) || !war3_executable_pointer(g_persistent_ability_resolver))
        RaiseException(ERROR_PROC_NOT_FOUND,0,0,NULL);
    War3CloneAbilities *s=HeapAlloc(GetProcessHeap(),HEAP_ZERO_MEMORY,sizeof(*s));
    if(!s) RaiseException(ERROR_OUTOFMEMORY,0,0,NULL);
    guard->abilities=s;s->by_index=by_index;s->lookup=(JassUnitRawcodeFn)(uintptr_t)lookup;
    for(unsigned n=0;n<=256;++n) {
        uint64_t handle=WAR3_CLONE_VALUE(guard,by_index(guard->source->unit_handle,(int32_t)n));
        if(!handle) break;
        if(n==256) RaiseException(ERROR_MORE_DATA,0,0,NULL);
        War3CloneAbility *a=&s->source[n];
        war3_clone_capture_ability(guard,guard->source,handle,(int32_t)n,a);
        s->active[0]=a;
        if(WAR3_CLONE_VALUE(guard,get_id(handle))!=a->rawcode) RaiseException(ERROR_INVALID_DATA,0,0,NULL);
        for(unsigned prior=0;prior<n;++prior) {
            War3CloneAbility *old=&s->source[prior];
            if(a->handle==old->handle || a->full==old->full || a->object==old->object)
                RaiseException(ERROR_INVALID_DATA,0,0,NULL);
        }
        ++s->count;
    }
    war3_clone_check_saved_abilities(guard);
}

static uint32_t war3_clone_copy_abilities(War3CloneGuard *guard,JassGetUnitAbilityLevelFn get_level,
                                        JassUnitAddAbilityFn add,JassSetUnitAbilityLevelFn set) {
    War3CloneAbilities *s=guard->abilities;uint32_t copied=0;
    war3_clone_check_saved_abilities(guard);
    for(unsigned n=0;n<s->count;++n) {
        War3CloneAbility *a=&s->source[n],*target=&s->target[n];
        if(war3_is_essential_ability(a->rawcode)) continue;
        unsigned prior;
        /* Item-provided abilities may legitimately repeat a rawcode. The
           engine level/add APIs address that rawcode once; retain every source
           instance's identity in the frozen list, but do not add it twice. */
        for(prior=0;prior<n;++prior) if(s->source[prior].rawcode==a->rawcode) break;
        if(prior<n) continue;
        s->active[0]=a;s->active[1]=NULL;war3_clone_check(guard);
        int32_t level=WAR3_CLONE_VALUE(guard,get_level(guard->source->unit_handle,a->rawcode));
        if(level<=0) {s->active[0]=NULL;continue;}
        uint64_t handle=WAR3_CLONE_VALUE(guard,s->lookup(guard->target.unit_handle,a->rawcode));
        if(!handle) {
            WAR3_CLONE_VALUE(guard,add(guard->target.unit_handle,a->rawcode));
            handle=WAR3_CLONE_VALUE(guard,s->lookup(guard->target.unit_handle,a->rawcode));
        }
        war3_clone_capture_ability(guard,&guard->target,handle,-1,target);
        if(target->rawcode!=a->rawcode) RaiseException(ERROR_INVALID_DATA,0,0,NULL);
        s->active[1]=target;war3_clone_check(guard);
        if(WAR3_CLONE_VALUE(guard,get_level(guard->target.unit_handle,a->rawcode))!=level) {
            WAR3_CLONE_VALUE(guard,set(guard->target.unit_handle,a->rawcode,level));
            if(WAR3_CLONE_VALUE(guard,get_level(guard->target.unit_handle,a->rawcode))!=level)
                RaiseException(ERROR_WRITE_FAULT,0,0,NULL);
        }
        ++copied;s->active[0]=s->active[1]=NULL;
    }
    return copied;
}
