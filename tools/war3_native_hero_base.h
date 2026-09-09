/* Base strength/agility use the same getters as the displayed values.
   op.rawcode: 0 strength, 1 agility; handler/arg0: hero data/full identity;
   arg1: target base value. At most two distinct stats in a single callback. */
static DWORD war3_set_bound_hero_base(NativeCommand *cmd) {
    JassGetHeroStatFn getters[2]={0};
    JassSetHeroStatFn setters[2]={0};
    JassUnitIntQueryFn level=(JassUnitIntQueryFn)(uintptr_t)war3_persistent_native_handler("GetHeroLevel");
    const char *get_names[2]={"GetHeroStr","GetHeroAgi"},*set_names[2]={"SetHeroStr","SetHeroAgi"};
    DWORD error=ERROR_SUCCESS;
    unsigned seen=0;
    if(cmd->op_count<2 || cmd->op_count>3 || cmd->ops[0].kind!=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY)
        return ERROR_INVALID_PARAMETER;
    if(!war3_executable_pointer((uint64_t)(uintptr_t)level)) return ERROR_PROC_NOT_FOUND;
    __try {
        /* Validate the entire request, including all required functions, before
           any setter. One missing second setter must not partially apply it. */
        for(unsigned n=1;n<cmd->op_count;++n) {
            NativeOp *op=&cmd->ops[n];unsigned stat=op->rawcode;
            if(op->kind!=WAR3_NATIVE_OP_SET_BOUND_HERO_BASE || stat>1 || op->arg1>1000000u ||
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
        /* The second setter can invoke map/engine effects affecting the first
           stat. Do not report both successful without checking both again. */
        if(cmd->op_count==3) for(unsigned n=1;n<cmd->op_count;++n) {
            NativeOp *op=&cmd->ops[n];
            int32_t actual=getters[op->rawcode](cmd->unit_handle,0);
            error=war3_validate_hero_component(cmd,op);if(error) __leave;
            if(actual!=(int32_t)op->arg1) {error=ERROR_CAN_NOT_COMPLETE;__leave;}
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) {error=GetExceptionCode();}
    return error;
}
