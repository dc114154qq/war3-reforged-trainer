/* Freeze full unit identities and retire the group before any KillUnit call.
   The selected unit may itself be killed: after collection, the operation is
   bound to the captured player and targets, not to the source staying alive. */
static DWORD war3_bound_owner_kill(NativeCommand *cmd,NativeOp *op) {
    const uint32_t capacity=100000,hash_size=262144;
    War3WorldTarget *targets=NULL;uint32_t *seen=NULL,count=0,scanned=0;
    uint64_t group=0,player=0,deadline=GetTickCount64()+110000;
    DWORD error=ERROR_SUCCESS,cleanup=ERROR_SUCCESS;
    JassGetOwningPlayerFn owner=(JassGetOwningPlayerFn)(uintptr_t)war3_persistent_native_handler("GetOwningPlayer");
    JassNoArgU64Fn create=(JassNoArgU64Fn)(uintptr_t)war3_persistent_native_handler("CreateGroup");
    JassDestroyGroupFn destroy=(JassDestroyGroupFn)(uintptr_t)war3_persistent_native_handler("DestroyGroup");
    JassGroupEnumUnitsOfPlayerFn enumerate=(JassGroupEnumUnitsOfPlayerFn)(uintptr_t)war3_persistent_native_handler("GroupEnumUnitsOfPlayer");
    JassFirstOfGroupFn first=(JassFirstOfGroupFn)(uintptr_t)war3_persistent_native_handler("FirstOfGroup");
    JassGroupRemoveUnitFn remove=(JassGroupRemoveUnitFn)(uintptr_t)war3_persistent_native_handler("GroupRemoveUnit");
    JassUnitVoidFn kill=(JassUnitVoidFn)(uintptr_t)op->handler;
    if(cmd->op_count!=2 || cmd->ops[0].kind!=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY ||
       op->rawcode || op->arg0 || op->arg1 || !war3_executable_pointer(op->handler)) return ERROR_INVALID_PARAMETER;
    const char *names[]={"GetOwningPlayer","CreateGroup","DestroyGroup","GroupEnumUnitsOfPlayer","FirstOfGroup","GroupRemoveUnit"};
    for(unsigned n=0;n<sizeof(names)/sizeof(names[0]);++n)
        if(!war3_executable_pointer(war3_persistent_native_handler(names[n]))) return ERROR_PROC_NOT_FOUND;
    targets=(War3WorldTarget *)HeapAlloc(GetProcessHeap(),0,capacity*sizeof(*targets));
    seen=(uint32_t *)HeapAlloc(GetProcessHeap(),HEAP_ZERO_MEMORY,hash_size*sizeof(*seen));
    if(!targets || !seen) {error=ERROR_OUTOFMEMORY;goto finish;}
#define OWNER_SOURCE() do {error=war3_validate_unit_identity(cmd,&cmd->ops[0]);if(error) __leave;} while(0)
    __try {
        OWNER_SOURCE();player=owner(cmd->unit_handle);OWNER_SOURCE();
        if(!player) {error=ERROR_NOT_FOUND;__leave;}
        group=create();OWNER_SOURCE();if(!group) {error=ERROR_NOT_FOUND;__leave;}
        enumerate(group,player,0);OWNER_SOURCE();
        for(;;) {
            uint64_t handle=first(group);OWNER_SOURCE();if(!handle) break;
            if(++scanned>capacity || GetTickCount64()>=deadline)
                {error=scanned>capacity?ERROR_BUFFER_OVERFLOW:ERROR_TIMEOUT;__leave;}
            War3WorldTarget target;DWORD captured=war3_capture_world_target(handle,&target);OWNER_SOURCE();
            remove(group,handle);OWNER_SOURCE();
            if(captured==ERROR_INVALID_HANDLE) {++op->arg0;continue;}
            if(captured) {error=captured;__leave;}
            uint32_t slot=(uint32_t)((handle^(handle>>32))*2654435761u)&(hash_size-1);
            while(seen[slot] && targets[seen[slot]-1].jass!=handle) slot=(slot+1)&(hash_size-1);
            if(seen[slot]) {
                War3WorldTarget *old=&targets[seen[slot]-1];
                if(old->full!=target.full || old->object!=target.object || old->owner!=target.owner)
                    {error=ERROR_INVALID_HANDLE;__leave;}
                continue;
            }
            targets[count]=target;seen[slot]=++count;
        }
        {uint64_t retiring=group;group=0;
         __try {destroy(retiring);} __except(EXCEPTION_EXECUTE_HANDLER) {cleanup=GetExceptionCode();}}
        if(cleanup) {error=cleanup;__leave;}
        OWNER_SOURCE();uint64_t current=owner(cmd->unit_handle);OWNER_SOURCE();
        if(current!=player) {error=ERROR_INVALID_HANDLE;__leave;}
        for(unsigned n=0;n<count;++n) {
            if(GetTickCount64()>=deadline) {error=ERROR_TIMEOUT;__leave;}
            NativeCommand target_cmd;war3_world_target_command(&targets[n],&target_cmd);
            DWORD valid=war3_validate_unit_identity(&target_cmd,&target_cmd.ops[0]);
            if(valid==ERROR_INVALID_HANDLE) {++op->arg0;continue;}
            if(valid) {error=valid;__leave;}
            current=owner(targets[n].jass);
            valid=war3_validate_unit_identity(&target_cmd,&target_cmd.ops[0]);
            if(valid==ERROR_INVALID_HANDLE) {++op->arg0;continue;}
            if(valid) {error=valid;__leave;}
            if(current!=player) {++op->arg0;continue;}
            kill(targets[n].jass);++op->result;
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) {error=GetExceptionCode();}
#undef OWNER_SOURCE
finish:
    if(group) {__try {destroy(group);} __except(EXCEPTION_EXECUTE_HANDLER) {cleanup=GetExceptionCode();}}
    if(targets) HeapFree(GetProcessHeap(),0,targets);
    if(seen) HeapFree(GetProcessHeap(),0,seen);
    op->reserved=cleanup;
    return error?error:cleanup;
}
