/* Included after the unit/hero identity validators. All work runs in the
   existing game-thread callback; no selection changes or external writes. */
typedef struct War3SkillIdentity {
    uint64_t handle, data, wrapper, full;
    int32_t level;
} War3SkillIdentity;

typedef struct War3SkillTransaction {
    NativeCommand *cmd;
    NativeOp *op;
    uint32_t configs[5], caches[5], slot, old_id;
    JassUnitRawcodeFn lookup;
    JassGetAbilityIdFn get_id;
    JassGetUnitAbilityLevelFn get_level;
    JassUnitAddAbilityFn add;
    JassUnitRemoveAbilityFn remove;
    JassSetUnitAbilityLevelFn set_level;
} War3SkillTransaction;

static DWORD war3_skill_target(War3SkillTransaction *t) {
    DWORD error=war3_validate_hero_component(t->cmd,t->op);
    if(error) return error;
    if(!war3_readable_span(t->op->handler+0x1bc,0x5c)) return ERROR_INVALID_ADDRESS;
    if(memcmp((void *)(uintptr_t)(t->op->handler+0x204),t->configs,sizeof(t->configs)) ||
       memcmp((void *)(uintptr_t)(t->op->handler+0x1bc),t->caches,sizeof(t->caches)))
        return ERROR_INVALID_DATA;
    return ERROR_SUCCESS;
}

static DWORD war3_skill_capture(War3SkillTransaction *t,uint32_t rawcode,War3SkillIdentity *out) {
    DWORD error=war3_skill_target(t);
    uint64_t data,wrapper,full,tag;
    ZeroMemory(out,sizeof(*out));
    if(error) return error;
    out->handle=t->lookup(t->cmd->unit_handle,rawcode);
    error=war3_skill_target(t);if(error) return error;
    out->level=t->get_level(t->cmd->unit_handle,rawcode);
    error=war3_skill_target(t);if(error) return error;
    if(out->level<0) return ERROR_INVALID_DATA;
    if(!out->handle) return out->level?ERROR_INVALID_DATA:ERROR_SUCCESS;
    data=((JassUnitHandleResolveFn)(uintptr_t)g_persistent_ability_resolver)(out->handle);
    error=war3_skill_target(t);if(error) return error;
    if(!war3_readable_span(data,0x80)) return ERROR_INVALID_ADDRESS;
    full=*(uint64_t *)(uintptr_t)(data+0x18);
    wrapper=((War3AgentResolveFn)(uintptr_t)g_persistent_agent_resolver)((uint32_t)full,(uint32_t)(full>>32));
    error=war3_skill_target(t);if(error) return error;
    if(!full || !war3_readable_span(wrapper,0x98)) return ERROR_INVALID_HANDLE;
    if(t->get_id(out->handle)!=rawcode) return ERROR_INVALID_DATA;
    error=war3_skill_target(t);if(error) return error;
    if(t->lookup(t->cmd->unit_handle,rawcode)!=out->handle) return ERROR_INVALID_HANDLE;
    error=war3_skill_target(t);if(error) return error;
    if(((JassUnitHandleResolveFn)(uintptr_t)g_persistent_ability_resolver)(out->handle)!=data)
        return ERROR_INVALID_HANDLE;
    error=war3_skill_target(t);if(error) return error;
    /* Recheck spans and all backlinks after the last engine callback. */
    if(!war3_readable_span(data,0x80) || !war3_readable_span(wrapper,0x98)) return ERROR_INVALID_ADDRESS;
    tag=*(uint64_t *)(uintptr_t)(wrapper+0x18);
    if(!(tag>>32) || tag==0x414865722b61676cULL || tag==0x41496e762b61676cULL ||
       tag==0x416d6f762b61676cULL || tag==0x4161746b2b61676cULL ||
       *(uint64_t *)(uintptr_t)(data+0x18)!=full ||
       *(uint64_t *)(uintptr_t)(data+0x68)!=t->cmd->ops[0].handler ||
       *(uint32_t *)(uintptr_t)(data+0x70)!=rawcode ||
       *(uint32_t *)(uintptr_t)(data+0x78)!=rawcode ||
       *(uint64_t *)(uintptr_t)(wrapper+0x20)!=full ||
       *(uint64_t *)(uintptr_t)(wrapper+0x50)!=t->cmd->ops[0].arg1 ||
       *(uint64_t *)(uintptr_t)(wrapper+0x90)!=data ||
       (uint32_t)*(uint64_t *)(uintptr_t)(wrapper+0x18)!=0x2b61676cu)
        return ERROR_INVALID_HANDLE;
    out->data=data;out->wrapper=wrapper;out->full=full;
    return ERROR_SUCCESS;
}

static int war3_same_skill(const War3SkillIdentity *a,const War3SkillIdentity *b) {
    return a->handle==b->handle && a->data==b->data && a->full==b->full && a->wrapper==b->wrapper;
}

/* No callbacks: use immediately before a mutation to catch a generation or
   backlink changed by the final query/validator callback. */
static DWORD war3_skill_memory(War3SkillTransaction *t,uint32_t id,const War3SkillIdentity *s) {
    uint64_t unit=t->cmd->ops[0].handler,owner=t->cmd->ops[0].arg1,hero=t->op->handler;
    if(!war3_readable_span(unit,0x5b0) || !war3_readable_span(owner,0x98) ||
       !war3_readable_span(hero,0x218) ||
       *(uint64_t *)(uintptr_t)(unit+0x18)!=t->cmd->ops[0].arg0 ||
       *(uint64_t *)(uintptr_t)(owner+0x20)!=t->cmd->ops[0].arg0 ||
       *(uint64_t *)(uintptr_t)(owner+0x90)!=unit ||
       *(uint64_t *)(uintptr_t)(unit+0x5a8)!=hero ||
       *(uint64_t *)(uintptr_t)(hero+0x18)!=t->op->arg0 ||
       *(uint64_t *)(uintptr_t)(hero+0x68)!=unit ||
       memcmp((void *)(uintptr_t)(hero+0x204),t->configs,sizeof(t->configs)) ||
       memcmp((void *)(uintptr_t)(hero+0x1bc),t->caches,sizeof(t->caches))) return ERROR_INVALID_HANDLE;
    if(!s->handle) return ERROR_SUCCESS;
    if(!war3_readable_span(s->data,0x80) || !war3_readable_span(s->wrapper,0x98) ||
       *(uint64_t *)(uintptr_t)(s->data+0x18)!=s->full ||
       *(uint64_t *)(uintptr_t)(s->data+0x68)!=unit ||
       *(uint32_t *)(uintptr_t)(s->data+0x70)!=id ||
       *(uint32_t *)(uintptr_t)(s->data+0x78)!=id ||
       *(uint64_t *)(uintptr_t)(s->wrapper+0x20)!=s->full ||
       *(uint64_t *)(uintptr_t)(s->wrapper+0x50)!=owner ||
       *(uint64_t *)(uintptr_t)(s->wrapper+0x90)!=s->data) return ERROR_INVALID_HANDLE;
    return ERROR_SUCCESS;
}

static DWORD war3_skill_expect(War3SkillTransaction *t,uint32_t id,const War3SkillIdentity *expected) {
    War3SkillIdentity current;
    DWORD error=war3_skill_capture(t,id,&current);
    if(error) return error;
    return war3_same_skill(&current,expected) && current.level==expected->level?ERROR_SUCCESS:ERROR_INVALID_HANDLE;
}

static DWORD war3_skill_store(War3SkillTransaction *t,uint32_t config,uint32_t cache) {
    uint64_t addresses[2]={t->op->handler+0x204+t->slot*4,t->op->handler+0x1bc+t->slot*4};
    DWORD error=war3_skill_target(t);
    if(error) return error;
    for(unsigned n=0;n<2;++n) {
        MEMORY_BASIC_INFORMATION region;
        if(!war3_readable_span(addresses[n],4) ||
           VirtualQuery((void *)(uintptr_t)addresses[n],&region,sizeof(region))!=sizeof(region) ||
           !(region.Protect&(PAGE_READWRITE|PAGE_WRITECOPY|PAGE_EXECUTE_READWRITE|PAGE_EXECUTE_WRITECOPY)))
            return ERROR_ACCESS_DENIED;
    }
    *(uint32_t *)(uintptr_t)addresses[0]=config;
    *(uint32_t *)(uintptr_t)addresses[1]=cache;
    t->configs[t->slot]=config;t->caches[t->slot]=cache;
    return war3_skill_target(t);
}

static DWORD war3_replace_hero_skill(NativeCommand *cmd,NativeOp *op) {
    War3SkillTransaction t={0};
    War3SkillIdentity old={0},fresh={0},current={0},absent={0};
    DWORD error=ERROR_SUCCESS,cleanup=ERROR_SUCCESS;
    uint32_t original_cache=0,added=0,creation_returned=0,config_written=0,committed=0;
    int32_t final_level=0;
    t.cmd=cmd;t.op=op;t.slot=(uint32_t)(op->arg1>>32);t.old_id=(uint32_t)op->arg1;
    if(cmd->op_count!=2 || cmd->ops[0].kind!=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY ||
       t.slot>=5 || !t.old_id || !op->rawcode) return ERROR_INVALID_PARAMETER;
    t.lookup=(JassUnitRawcodeFn)(uintptr_t)war3_persistent_native_handler("BlzGetUnitAbility");
    t.get_id=(JassGetAbilityIdFn)(uintptr_t)war3_persistent_native_handler("BlzGetAbilityId");
    t.get_level=(JassGetUnitAbilityLevelFn)(uintptr_t)war3_persistent_native_handler("GetUnitAbilityLevel");
    t.add=(JassUnitAddAbilityFn)(uintptr_t)war3_persistent_native_handler("UnitAddAbility");
    t.remove=(JassUnitRemoveAbilityFn)(uintptr_t)war3_persistent_native_handler("UnitRemoveAbility");
    t.set_level=(JassSetUnitAbilityLevelFn)(uintptr_t)war3_persistent_native_handler("SetUnitAbilityLevel");
    if(!war3_executable_pointer((uint64_t)(uintptr_t)t.lookup) ||
       !war3_executable_pointer((uint64_t)(uintptr_t)t.get_id) ||
       !war3_executable_pointer((uint64_t)(uintptr_t)t.get_level) ||
       !war3_executable_pointer((uint64_t)(uintptr_t)t.add) ||
       !war3_executable_pointer((uint64_t)(uintptr_t)t.remove) ||
       !war3_executable_pointer((uint64_t)(uintptr_t)t.set_level) ||
       !war3_executable_pointer(g_persistent_ability_resolver)) return ERROR_PROC_NOT_FOUND;
    __try {
        error=war3_validate_hero_component(cmd,op);if(error) __leave;
        if(!war3_readable_span(op->handler+0x1bc,0x5c)) {error=ERROR_INVALID_ADDRESS;__leave;}
        memcpy(t.configs,(void *)(uintptr_t)(op->handler+0x204),sizeof(t.configs));
        memcpy(t.caches,(void *)(uintptr_t)(op->handler+0x1bc),sizeof(t.caches));
        original_cache=t.caches[t.slot];
        if(t.configs[t.slot]!=t.old_id) {error=ERROR_INVALID_DATA;__leave;}
        for(unsigned n=0;n<5;++n) if(n!=t.slot && (t.configs[n]==t.old_id || t.configs[n]==op->rawcode)) {
            error=ERROR_ALREADY_EXISTS;__leave;
        }
        if(error) __leave;
        error=war3_skill_capture(&t,t.old_id,&old);if(error) __leave;
        if(t.old_id==op->rawcode) {final_level=old.level;committed=1;__leave;}
        error=war3_skill_expect(&t,op->rawcode,&absent);if(error) __leave;
        error=war3_skill_expect(&t,t.old_id,&old);if(error) __leave;
        error=war3_skill_memory(&t,t.old_id,&old);if(error) __leave;
        /* The engine resolves the map resource. No template unit is required. */
        op->result=1; /* phase: creation attempted, including exceptions */
        added=t.add(cmd->unit_handle,op->rawcode);
        creation_returned=1;
        error=war3_skill_capture(&t,op->rawcode,&fresh);if(error) __leave;
        if(!added || !fresh.handle || fresh.data==old.data) {error=ERROR_INVALID_DATA;__leave;}
        error=war3_skill_expect(&t,t.old_id,&old);if(error) __leave;
        if(old.handle) {
            error=war3_skill_memory(&t,op->rawcode,&fresh);if(error) __leave;
            final_level=(int32_t)t.set_level(cmd->unit_handle,op->rawcode,old.level);
            error=war3_skill_capture(&t,op->rawcode,&current);if(error) __leave;
            if(!war3_same_skill(&fresh,&current)) {error=ERROR_INVALID_HANDLE;__leave;}
            fresh=current;
            /* The engine may clamp to this resource's maximum level. */
            if(final_level!=fresh.level || final_level<0 || final_level>old.level || (old.level && !final_level)) {
                error=ERROR_INVALID_DATA;__leave;
            }
        }
        error=war3_skill_expect(&t,t.old_id,&old);if(error) __leave;
        error=war3_skill_expect(&t,op->rawcode,&fresh);if(error) __leave;
        error=war3_skill_store(&t,op->rawcode,op->rawcode);
        config_written=t.configs[t.slot]==op->rawcode;
        if(config_written) op->result=2;
        if(error) __leave;
        error=war3_skill_memory(&t,t.old_id,&old);if(error) __leave;
        error=war3_skill_memory(&t,op->rawcode,&fresh);if(error) __leave;
        /* Removal refreshes the command card after the config stores. For an
           unlearned slot the temporary new ability only validated its resource. */
        uint32_t removed=t.remove(cmd->unit_handle,old.handle?t.old_id:op->rawcode);
        op->result=3;
        error=war3_skill_target(&t);if(error) __leave;
        error=war3_skill_expect(&t,t.old_id,&absent);if(error) __leave;
        error=war3_skill_expect(&t,op->rawcode,old.handle?&fresh:&absent);if(error) __leave;
        error=war3_skill_memory(&t,op->rawcode,old.handle?&fresh:&absent);if(error) __leave;
        if(!removed) {error=ERROR_INVALID_DATA;__leave;}
        committed=1;
    } __except(EXCEPTION_EXECUTE_HANDLER) {error=GetExceptionCode();}
    if(error && added && !committed) {
        __try {
            /* Restore only while the original ability still has its exact
               identity and level. Never recreate a destructively removed old
               instance or delete a new/recycled instance claimed by a trigger. */
            cleanup=war3_skill_expect(&t,t.old_id,&old);if(cleanup) __leave;
            cleanup=war3_skill_capture(&t,op->rawcode,&current);if(cleanup) __leave;
            if(current.handle) {
                if(!fresh.handle || !war3_same_skill(&fresh,&current) || fresh.level!=current.level) {
                    cleanup=ERROR_INVALID_HANDLE;__leave;
                }
                cleanup=war3_skill_memory(&t,t.old_id,&old);if(cleanup) __leave;
                cleanup=war3_skill_memory(&t,op->rawcode,&current);if(cleanup) __leave;
                t.remove(cmd->unit_handle,op->rawcode);
                cleanup=war3_skill_expect(&t,op->rawcode,&absent);if(cleanup) __leave;
                cleanup=war3_skill_expect(&t,t.old_id,&old);if(cleanup) __leave;
            }
            if(config_written) cleanup=war3_skill_store(&t,t.old_id,original_cache);
        } __except(EXCEPTION_EXECUTE_HANDLER) {cleanup=GetExceptionCode();}
    }
    if(error && op->result==1 && !added && (!creation_returned || fresh.handle))
        cleanup=ERROR_INVALID_DATA; /* creation outcome/ownership is unproven */
    op->reserved=cleanup;
    if(!error && committed) {op->result=op->rawcode;op->arg1=(uint32_t)final_level;}
    return error;
}
