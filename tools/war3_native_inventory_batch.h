/* Compare fixed membership, not whichever object happens to occupy a slot
   after a map callback. For quantities, also verify all completed writes. */
static DWORD war3_inventory_batch_matches(const uint64_t *expected,const uint64_t *actual,
                                          unsigned quantity_mask,uint32_t quantity) {
    if(expected[0]!=actual[0]) return ERROR_INVALID_HANDLE;
    for(unsigned slot=0;slot<6;++slot) {
        const uint64_t *old=expected+1+slot*8,*now=actual+1+slot*8;
        if(memcmp(old,now,4*sizeof(uint64_t)) || old[7]!=now[7]) return ERROR_INVALID_HANDLE;
        if((quantity_mask&(1u<<slot)) && (int32_t)now[4]!=(int32_t)quantity)
            return ERROR_CAN_NOT_COMPLETE;
    }
    return ERROR_SUCCESS;
}

/* Modes: 0 RemoveItem (clear), 1 SetItemCharges, 2 UnitRemoveItem (drop).
   One initial snapshot plus one verification snapshot per affected item.
   All snapshots and callbacks run inside the same game-thread command. */
static DWORD war3_bound_inventory_batch(NativeCommand *cmd,NativeOp *op) {
    uint64_t expected[WAR3_BOUND_INVENTORY_QWORDS]={0},actual[WAR3_BOUND_INVENTORY_QWORDS]={0};
    unsigned quantities=0;
    DWORD error=ERROR_SUCCESS;
    JassRemoveItemFn remove=(JassRemoveItemFn)(uintptr_t)war3_persistent_native_handler("RemoveItem");
    JassSetItemChargesFn set=(JassSetItemChargesFn)(uintptr_t)war3_persistent_native_handler("SetItemCharges");
    JassUnitRemoveItemFn drop=(JassUnitRemoveItemFn)(uintptr_t)war3_persistent_native_handler("UnitRemoveItem");
    if(cmd->op_count!=2 || cmd->ops[0].kind!=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY ||
       op->rawcode>2 || op->handler || op->arg1 ||
       (op->rawcode==1 ? (!op->arg0 || op->arg0>1000000000u) : op->arg0!=0))
        return ERROR_INVALID_PARAMETER;
    uint64_t handler=op->rawcode==0?(uint64_t)(uintptr_t)remove:
                     op->rawcode==1?(uint64_t)(uintptr_t)set:(uint64_t)(uintptr_t)drop;
    if(!war3_executable_pointer(handler)) return ERROR_PROC_NOT_FOUND;
    __try {
        error=war3_bound_inventory(cmd,expected);if(error) __leave;
        for(unsigned slot=0;slot<6;++slot) {
            uint64_t *row=expected+1+slot*8,item=row[0];
            if(!item) continue;
            /* Membership and generation were verified in the immediately
               preceding snapshot; no engine callback intervenes here. */
            if(op->rawcode==0) remove(item);
            else if(op->rawcode==1) set(item,(int32_t)op->arg0);
            else drop(cmd->unit_handle,item);
            if(op->rawcode==1) quantities|=1u<<slot;
            else ZeroMemory(row,8*sizeof(uint64_t));
            ZeroMemory(actual,sizeof(actual));
            error=war3_bound_inventory(cmd,actual);if(error) __leave;
            error=war3_inventory_batch_matches(expected,actual,quantities,(uint32_t)op->arg0);
            if(error) __leave;
            ++op->result;
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) {error=GetExceptionCode();}
    return error;
}
