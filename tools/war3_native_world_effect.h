typedef struct War3WorldTarget {uint64_t jass,object,full,owner;} War3WorldTarget;

static void war3_world_target_command(const War3WorldTarget *t,NativeCommand *cmd) {
    ZeroMemory(cmd,sizeof(*cmd));cmd->unit_handle=t->jass;
    cmd->ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;
    cmd->ops[0].handler=t->object;cmd->ops[0].arg0=t->full;cmd->ops[0].arg1=t->owner;
}

static DWORD war3_capture_world_target(uint64_t handle,War3WorldTarget *t) {
    NativeCommand cmd;uint64_t object=((JassUnitHandleResolveFn)(uintptr_t)g_persistent_unit_resolver)(handle);
    if(!war3_readable_span(object,0x20)) return ERROR_INVALID_HANDLE;
    t->jass=handle;t->object=object;t->full=*(uint64_t *)(uintptr_t)(object+0x18);
    t->owner=((War3AgentResolveFn)(uintptr_t)g_persistent_agent_resolver)((uint32_t)t->full,(uint32_t)(t->full>>32));
    war3_world_target_command(t,&cmd);return war3_validate_unit_identity(&cmd,&cmd.ops[0]);
}

/* Capture a bounded target set before invoking effects. The engine group is
   destroyed before mutation; newly spawned units cannot extend this batch. */
static DWORD war3_bound_world_effect(NativeCommand *cmd,NativeOp *op) {
    const uint32_t capacity=100000,hash_size=262144;
    War3WorldTarget *targets=NULL;uint32_t *seen=NULL,count=0,scanned=0,attempts=0,successes=0;
    uint64_t group=0,source_owner=0,deadline=GetTickCount64()+110000;
    War3AbilityEffect s={0};DWORD error=ERROR_SUCCESS,cleanup=ERROR_SUCCESS;
    uint32_t creation_attempted=0,creation_returned=0;
    JassNoArgU64Fn create=(JassNoArgU64Fn)(uintptr_t)war3_persistent_native_handler("CreateGroup");
    JassDestroyGroupFn destroy=(JassDestroyGroupFn)(uintptr_t)war3_persistent_native_handler("DestroyGroup");
    JassGroupEnumUnitsOfPlayerFn enumerate=(JassGroupEnumUnitsOfPlayerFn)(uintptr_t)war3_persistent_native_handler("GroupEnumUnitsOfPlayer");
    JassFirstOfGroupFn first=(JassFirstOfGroupFn)(uintptr_t)war3_persistent_native_handler("FirstOfGroup");
    JassGroupRemoveUnitFn remove=(JassGroupRemoveUnitFn)(uintptr_t)war3_persistent_native_handler("GroupRemoveUnit");
    JassPlayerFn player=(JassPlayerFn)(uintptr_t)war3_persistent_native_handler("Player");
    JassGetOwningPlayerFn owner=(JassGetOwningPlayerFn)(uintptr_t)war3_persistent_native_handler("GetOwningPlayer");
    JassIsPlayerEnemyFn enemy=(JassIsPlayerEnemyFn)(uintptr_t)war3_persistent_native_handler("IsPlayerEnemy");
    JassGetUnitTypeIdFn type=(JassGetUnitTypeIdFn)(uintptr_t)war3_persistent_native_handler("GetUnitTypeId");
    JassUnitRealQueryFn life=(JassUnitRealQueryFn)(uintptr_t)war3_persistent_native_handler("GetWidgetLife");
    JassUnitRealQueryFn xfn=(JassUnitRealQueryFn)(uintptr_t)war3_persistent_native_handler("GetUnitX");
    JassUnitRealQueryFn yfn=(JassUnitRealQueryFn)(uintptr_t)war3_persistent_native_handler("GetUnitY");
    const char *names[]={"CreateGroup","DestroyGroup","GroupEnumUnitsOfPlayer","FirstOfGroup","GroupRemoveUnit",
        "Player","GetOwningPlayer","IsPlayerEnemy","GetUnitTypeId","GetWidgetLife","GetUnitX","GetUnitY","UnitAddAbility","UnitRemoveAbility"};
    if(cmd->op_count!=2 || cmd->ops[0].kind!=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY || !op->rawcode ||
       (op->handler!=1 && op->handler!=3) || op->arg0>65535 || op->arg1) return ERROR_INVALID_PARAMETER;
    for(unsigned n=0;n<sizeof(names)/sizeof(names[0]);++n)
        if(!war3_executable_pointer(war3_persistent_native_handler(names[n]))) return ERROR_PROC_NOT_FOUND;
    s.bound=*cmd;s.id=op->rawcode;op->result=0;op->reserved=0;
    targets=(War3WorldTarget *)HeapAlloc(GetProcessHeap(),0,capacity*sizeof(*targets));
    seen=(uint32_t *)HeapAlloc(GetProcessHeap(),HEAP_ZERO_MEMORY,hash_size*sizeof(*seen));
    if(!targets || !seen) {error=ERROR_OUTOFMEMORY;goto finish;}
#define WORLD_SOURCE() do {error=war3_validate_unit_identity(cmd,&cmd->ops[0]);if(error) __leave;} while(0)
    __try {
        WORLD_SOURCE();source_owner=owner(cmd->unit_handle);WORLD_SOURCE();
        if(!source_owner) {error=ERROR_NOT_FOUND;__leave;}
        group=create();WORLD_SOURCE();if(!group) {error=ERROR_NOT_FOUND;__leave;}
        for(int32_t n=0;n<24;++n) {
            uint64_t p=player(n);WORLD_SOURCE();if(!p) continue;
            enumerate(group,p,0);WORLD_SOURCE();
            for(;;) {
                War3WorldTarget target;uint64_t handle=first(group);WORLD_SOURCE();if(!handle) break;
                if(++scanned>capacity || GetTickCount64()>=deadline) {error=scanned>capacity?ERROR_BUFFER_OVERFLOW:ERROR_TIMEOUT;__leave;}
                DWORD captured=war3_capture_world_target(handle,&target);WORLD_SOURCE();
                remove(group,handle);WORLD_SOURCE();
                if(captured==ERROR_INVALID_HANDLE) continue;
                if(captured) {error=captured;__leave;}
                uint32_t slot=(uint32_t)((handle^(handle>>32))*2654435761u)&(hash_size-1);
                while(seen[slot] && targets[seen[slot]-1].jass!=handle) slot=(slot+1)&(hash_size-1);
                if(seen[slot]) {
                    War3WorldTarget *old=&targets[seen[slot]-1];
                    if(old->full!=target.full || old->object!=target.object || old->owner!=target.owner) {error=ERROR_INVALID_HANDLE;__leave;}
                    continue;
                }
                targets[count]=target;seen[slot]=++count;
            }
        }
        {uint64_t retiring=group;group=0;destroy(retiring);} WORLD_SOURCE();
        if(!count) __leave;
        error=war3_action_ability_state(cmd,s.id,s.identity);if(error) __leave;
        if(!s.identity[0]) {
            creation_attempted=1;
            s.added=((JassUnitAddAbilityFn)(uintptr_t)war3_persistent_native_handler("UnitAddAbility"))(cmd->unit_handle,s.id);
            creation_returned=1;
            error=war3_action_ability_state(cmd,s.id,s.identity);if(error) __leave;
            if(!s.added || !s.identity[0]) {error=ERROR_INVALID_DATA;__leave;}
        }
        s.captured=1;
        for(uint32_t n=0;n<count && (!op->arg0 || successes<op->arg0);++n) {
            NativeCommand target_cmd;War3WorldTarget *t=&targets[n];
            if(GetTickCount64()>=deadline) {error=ERROR_TIMEOUT;__leave;}
            error=war3_effect_check(&s);if(error) __leave;
            war3_world_target_command(t,&target_cmd);
            DWORD target_error=war3_validate_unit_identity(&target_cmd,&target_cmd.ops[0]);
            if(target_error==ERROR_INVALID_HANDLE) continue;
            if(target_error) {error=target_error;__leave;}
            uint32_t unit_type=type(t->jass);
            if(war3_validate_unit_identity(&target_cmd,&target_cmd.ops[0])) continue;
            if(!unit_type) continue;
            float hp=war3_real_from_bits(life(t->jass));
            if(war3_validate_unit_identity(&target_cmd,&target_cmd.ops[0])) continue;
            if(!(hp>0.405f)) continue;
            uint64_t target_owner=owner(t->jass);
            if(war3_validate_unit_identity(&target_cmd,&target_cmd.ops[0])) continue;
            error=war3_effect_check(&s);if(error) __leave;
            if(owner(cmd->unit_handle)!=source_owner) {error=ERROR_INVALID_HANDLE;__leave;}
            error=war3_effect_check(&s);if(error) __leave;
            uint32_t hostile=target_owner?enemy(source_owner,target_owner):0;
            if(war3_validate_unit_identity(&target_cmd,&target_cmd.ops[0])) continue;
            if(!hostile) continue;
            ++attempts;float x=0,y=0;
            if(op->handler==3) {
                x=war3_real_from_bits(xfn(t->jass));
                if(war3_validate_unit_identity(&target_cmd,&target_cmd.ops[0])) continue;
                y=war3_real_from_bits(yfn(t->jass));
                if(war3_validate_unit_identity(&target_cmd,&target_cmd.ops[0])) continue;
                if(!(x==x) || !(y==y) || x < -1000000.0f || x > 1000000.0f || y < -1000000.0f || y > 1000000.0f) continue;
            }
            error=war3_effect_check(&s);if(error) __leave;
            if(owner(t->jass)!=target_owner) continue;
            if(war3_validate_unit_identity(&target_cmd,&target_cmd.ops[0])) continue;
            error=war3_direct_identity_memory(cmd,s.id,s.identity);if(error) __leave;
            uint64_t vtable=*(uint64_t *)(uintptr_t)s.identity[1],offset=op->handler==1?0xa70:0xa58;
            if(!war3_readable_span(vtable,(size_t)offset+8)) {error=ERROR_INVALID_ADDRESS;__leave;}
            uint64_t callback=*(uint64_t *)(uintptr_t)(vtable+offset);
            if(!war3_executable_pointer(callback)) {error=ERROR_INVALID_ADDRESS;__leave;}
            if(op->handler==1) ((DirectAbilityTargetFn)(uintptr_t)callback)(s.identity[1],t->object);
            else ((DirectAbilityPointFn)(uintptr_t)callback)(s.identity[1],&x,&y);
            ++successes;
            error=war3_effect_check(&s);if(error) __leave;
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) {error=GetExceptionCode();}
#undef WORLD_SOURCE
finish:
    __try {if(group) {uint64_t retiring=group;group=0;destroy(retiring);}} __except(EXCEPTION_EXECUTE_HANDLER) {cleanup=GetExceptionCode();}
    __try {
        if(s.added && s.captured) {DWORD e=war3_effect_cleanup(&s);if(e) cleanup=e;}
        if(creation_attempted && (!creation_returned || (s.added && !s.captured) || (!s.added && s.identity[0]))) cleanup=ERROR_INVALID_DATA;
    } __except(EXCEPTION_EXECUTE_HANDLER) {cleanup=GetExceptionCode();}
    if(targets) HeapFree(GetProcessHeap(),0,targets);
    if(seen) HeapFree(GetProcessHeap(),0,seen);
    op->result=((uint64_t)attempts<<32)|successes;op->reserved=cleanup;
    return error?error:cleanup;
}
