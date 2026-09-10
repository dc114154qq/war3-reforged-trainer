/* Original occupied slots must retain their identities. New items can occupy
   initially empty slots or remain on the ground under UnitAddItemById semantics. */
static DWORD war3_inventory_sources_match(const uint64_t *before,const uint64_t *now) {
    if(before[0]!=now[0]) return ERROR_INVALID_HANDLE;
    for(unsigned slot=0;slot<6;++slot) {
        const uint64_t *old=before+1+slot*8,*row=now+1+slot*8;
        if(old[0] && (memcmp(old,row,4*sizeof(uint64_t)) || old[7]!=row[7]))
            return ERROR_INVALID_HANDLE;
    }
    return ERROR_SUCCESS;
}

/* rawcode != 0 adds one item; rawcode == 0 duplicates the initial inventory's
   types. result counts acknowledged calls with verified unit/source identities;
   arg0 returns the last engine handle. Map callbacks may immediately consume,
   transform or transfer a new item. Do not require it to remain alive and never
   destroy a returned handle as guessed error recovery. */
static DWORD war3_bound_item_create(NativeCommand *cmd,NativeOp *op) {
    JassUnitRawcodeFn create=(JassUnitRawcodeFn)(uintptr_t)war3_persistent_native_handler("UnitAddItemById");
    uint64_t before[WAR3_BOUND_INVENTORY_QWORDS]={0},now[WAR3_BOUND_INVENTORY_QWORDS]={0};
    DWORD error=ERROR_SUCCESS;
    unsigned count=0;
    if(cmd->op_count!=2 || cmd->ops[0].kind!=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY ||
       op->handler || op->arg0 || op->arg1) return ERROR_INVALID_PARAMETER;
    if(!war3_executable_pointer((uint64_t)(uintptr_t)create)) return ERROR_PROC_NOT_FOUND;
    __try {
        if(!op->rawcode) {error=war3_bound_inventory(cmd,before);if(error) __leave;}
        for(unsigned slot=0;slot<(op->rawcode?1u:6u);++slot) {
            uint32_t type=op->rawcode?op->rawcode:(uint32_t)before[1+slot*8+3];
            if(!type) continue;
            error=war3_validate_unit_identity(cmd,&cmd->ops[0]);if(error) __leave;
            uint64_t handle=create(cmd->unit_handle,type);
            op->arg0=handle;
            error=war3_validate_unit_identity(cmd,&cmd->ops[0]);if(error) __leave;
            if(!handle) {error=ERROR_CAN_NOT_COMPLETE;__leave;}
            if(!op->rawcode) {
                ZeroMemory(now,sizeof(now));error=war3_bound_inventory(cmd,now);if(error) __leave;
                error=war3_inventory_sources_match(before,now);if(error) __leave;
            }
            error=war3_validate_unit_identity(cmd,&cmd->ops[0]);if(error) __leave;
            ++count;op->result=count;
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) {error=GetExceptionCode();}
    return error;
}
