/* Base stats use the same getters as displayed values. The field editor
   accepts strength/agility only; the all-attributes wrapper adds intelligence.
   rawcode: stat index; handler/arg0: hero data/full; arg1: target base value. */
static DWORD war3_set_bound_hero_base_impl(NativeCommand *cmd,unsigned stat_count,uint32_t maximum) {
    JassGetHeroStatFn getters[3]={0};
    JassSetHeroStatFn setters[3]={0};
    JassUnitIntQueryFn level=(JassUnitIntQueryFn)(uintptr_t)war3_persistent_native_handler("GetHeroLevel");
    const char *get_names[3]={"GetHeroStr","GetHeroAgi","GetHeroInt"};
    const char *set_names[3]={"SetHeroStr","SetHeroAgi","SetHeroInt"};
    DWORD error=ERROR_SUCCESS;
    unsigned seen=0;
    if(stat_count<1 || stat_count>3 || cmd->op_count<2 || cmd->op_count>stat_count+1 ||
       cmd->ops[0].kind!=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY)
        return ERROR_INVALID_PARAMETER;
    if(!war3_executable_pointer((uint64_t)(uintptr_t)level)) return ERROR_PROC_NOT_FOUND;
    __try {
        /* Validate the entire request, including all required functions, before
           any setter. One missing second setter must not partially apply it. */
        for(unsigned n=1;n<cmd->op_count;++n) {
            NativeOp *op=&cmd->ops[n];unsigned stat=op->rawcode;
            if(op->kind!=WAR3_NATIVE_OP_SET_BOUND_HERO_BASE || stat>=stat_count || op->arg1>maximum ||
               (seen&(1u<<stat)) || op->handler!=cmd->ops[1].handler || op->arg0!=cmd->ops[1].arg0) {
                error=ERROR_INVALID_PARAMETER;__leave;
            }
            seen|=1u<<stat;
            getters[stat]=(JassGetHeroStatFn)(uintptr_t)war3_persistent_native_handler(get_names[stat]);
            setters[stat]=(JassSetHeroStatFn)(uintptr_t)war3_persistent_native_handler(set_names[stat]);
            if(!war3_executable_pointer((uint64_t)(uintptr_t)getters[stat]) ||
               !war3_executable_pointer((uint64_t)(uintptr_t)setters[stat])) {
                error=ERROR_PROC_NOT_FOUND;__leave;
            }
            error=war3_validate_hero_component(cmd,op);if(error) __leave;
        }
        if(error) __leave;
        if(level(cmd->unit_handle)<=0) {error=ERROR_INVALID_PARAMETER;__leave;}
        error=war3_validate_hero_component(cmd,&cmd->ops[1]);if(error) __leave;
        for(unsigned n=1;n<cmd->op_count;++n) {
            NativeOp *op=&cmd->ops[n];unsigned stat=op->rawcode;
            /* Validate the display query before mutations, even for the second
               stat. Subsequent checks use this same query, never raw stores. */
            getters[stat](cmd->unit_handle,0);
            error=war3_validate_hero_component(cmd,op);if(error) __leave;
        }
        if(error) __leave;
        for(unsigned n=1;n<cmd->op_count;++n) {
            NativeOp *op=&cmd->ops[n];unsigned stat=op->rawcode;
            error=war3_validate_hero_component(cmd,op);if(error) __leave;
            setters[stat](cmd->unit_handle,(int32_t)op->arg1,1);
            error=war3_validate_hero_component(cmd,op);if(error) __leave;
            int32_t actual=getters[stat](cmd->unit_handle,0);
            error=war3_validate_hero_component(cmd,op);if(error) __leave;
            if(actual!=(int32_t)op->arg1) {error=ERROR_CAN_NOT_COMPLETE;__leave;}
            op->result=(uint32_t)actual;
        }
        if(error) __leave;
        /* Later setters can affect earlier stats. Check all again before
           reporting success for a multi-stat request. */
        if(cmd->op_count>2) for(unsigned n=1;n<cmd->op_count;++n) {
            NativeOp *op=&cmd->ops[n];
            int32_t actual=getters[op->rawcode](cmd->unit_handle,0);
            error=war3_validate_hero_component(cmd,op);if(error) __leave;
            if(actual!=(int32_t)op->arg1) {error=ERROR_CAN_NOT_COMPLETE;__leave;}
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) {error=GetExceptionCode();}
    return error;
}

static DWORD war3_set_bound_hero_base(NativeCommand *cmd) {
    return war3_set_bound_hero_base_impl(cmd,2,1000000u);
}

/* The all-attributes action already sets all three BASE values. Capture its
   hero component in this same callback; do not query a new selection or accept
   a controller-supplied component address without full identity validation. */
static DWORD war3_set_bound_hero_attributes(NativeCommand *cmd,NativeOp *op) {
    NativeCommand batch={0};
    uint64_t unit=cmd->ops[0].handler,data,full;
    DWORD error;
    if(cmd->op_count!=2 || cmd->ops[0].kind!=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY ||
       op->rawcode>1000000000u || op->handler || op->arg0 || op->arg1)
        return ERROR_INVALID_PARAMETER;
    __try {
        error=war3_validate_unit_identity(cmd,&cmd->ops[0]);if(error) __leave;
        if(!war3_readable_span(unit+0x5a8,8)) {error=ERROR_INVALID_HANDLE;__leave;}
        data=*(uint64_t *)(uintptr_t)(unit+0x5a8);
        if(!war3_readable_span(data,0x70)) {error=ERROR_INVALID_HANDLE;__leave;}
        full=*(uint64_t *)(uintptr_t)(data+0x18);
        batch.op_count=4;batch.unit_handle=cmd->unit_handle;batch.ops[0]=cmd->ops[0];
        for(unsigned stat=0;stat<3;++stat) {
            NativeOp *request=&batch.ops[stat+1];
            request->kind=WAR3_NATIVE_OP_SET_BOUND_HERO_BASE;request->rawcode=stat;
            request->handler=data;request->arg0=full;request->arg1=op->rawcode;
        }
        error=war3_set_bound_hero_base_impl(&batch,3,1000000000u);
        if(!error) op->result=op->rawcode;
    } __except(EXCEPTION_EXECUTE_HANDLER) {error=GetExceptionCode();}
    return error;
}
