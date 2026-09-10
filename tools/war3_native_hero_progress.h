typedef int32_t (__fastcall *War3HeroDeltaFn)(uint64_t,int32_t);

static DWORD war3_capture_progress_hero(const NativeCommand *cmd,NativeOp *hero) {
    DWORD error=war3_validate_unit_identity(cmd,&cmd->ops[0]);
    uint64_t unit=cmd->ops[0].handler;
    if(error) return error;
    if(!war3_readable_span(unit+0x5a8,8)) return ERROR_INVALID_HANDLE;
    hero->handler=*(uint64_t *)(uintptr_t)(unit+0x5a8);
    if(!war3_readable_span(hero->handler,0x70)) return ERROR_INVALID_HANDLE;
    hero->arg0=*(uint64_t *)(uintptr_t)(hero->handler+0x18);
    return war3_validate_hero_component(cmd,hero);
}

static DWORD war3_progress_xp_state(const NativeCommand *cmd,const NativeOp *hero,
                                   JassUnitIntQueryFn query,int32_t *state) {
    DWORD error=war3_validate_hero_component(cmd,hero);
    if(error) return error;
    *state=query(cmd->unit_handle);
    error=war3_validate_hero_component(cmd,hero);
    if(error) return error;
    return *state==0 || *state==1 ? ERROR_SUCCESS : ERROR_INVALID_DATA;
}

static DWORD war3_progress_restore_xp(const NativeCommand *cmd,const NativeOp *hero,
                                     JassUnitIntQueryFn query,JassUnitBoolFn suspend) {
    DWORD error=ERROR_SUCCESS;int32_t state=0;
    __try {
        error=war3_progress_xp_state(cmd,hero,query,&state);if(error) __leave;
        if(state==0) {
            suspend(cmd->unit_handle,1);
            error=war3_validate_hero_component(cmd,hero);if(error) __leave;
            error=war3_progress_xp_state(cmd,hero,query,&state);if(error) __leave;
            if(state!=1) error=ERROR_CAN_NOT_COMPLETE;
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) {error=GetExceptionCode();}
    return error;
}

static DWORD war3_set_bound_hero_level(NativeCommand *cmd,NativeOp *op) {
    JassUnitIntQueryFn get=(JassUnitIntQueryFn)(uintptr_t)war3_persistent_native_handler("GetHeroLevel");
    JassSetHeroLevelFn set=(JassSetHeroLevelFn)(uintptr_t)war3_persistent_native_handler("SetHeroLevel");
    War3HeroDeltaFn strip=(War3HeroDeltaFn)(uintptr_t)war3_persistent_native_handler("UnitStripHeroLevel");
    JassUnitIntQueryFn xp=(JassUnitIntQueryFn)(uintptr_t)war3_persistent_native_handler("IsSuspendedXP");
    JassUnitBoolFn suspend=(JassUnitBoolFn)(uintptr_t)war3_persistent_native_handler("SuspendHeroXP");
    NativeOp hero={0};DWORD error=ERROR_SUCCESS,recovery=ERROR_SUCCESS;int restore=0;
    int32_t current,state,actual;
    if(cmd->op_count!=2 || cmd->ops[0].kind!=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY ||
       !op->rawcode || op->rawcode>100000u || op->handler || op->arg0 || op->arg1)
        return ERROR_INVALID_PARAMETER;
    const uint64_t functions[]={(uint64_t)(uintptr_t)get,(uint64_t)(uintptr_t)set,
        (uint64_t)(uintptr_t)strip,(uint64_t)(uintptr_t)xp,(uint64_t)(uintptr_t)suspend};
    for(unsigned n=0;n<5;++n) if(!war3_executable_pointer(functions[n])) return ERROR_PROC_NOT_FOUND;
    __try {
        error=war3_capture_progress_hero(cmd,&hero);if(error) __leave;
        current=get(cmd->unit_handle);
        error=war3_validate_hero_component(cmd,&hero);if(error) __leave;
        if(current<=0) {error=ERROR_INVALID_PARAMETER;__leave;}
        if((int32_t)op->rawcode>current) {
            error=war3_progress_xp_state(cmd,&hero,xp,&state);if(error) __leave;
            if(state) {
                /* The callback can change the flag and then raise. Record
                   cleanup ownership before attempting the temporary change. */
                restore=1;suspend(cmd->unit_handle,0);
                error=war3_validate_hero_component(cmd,&hero);if(error) __leave;
                error=war3_progress_xp_state(cmd,&hero,xp,&state);if(error) __leave;
                if(state) {error=ERROR_CAN_NOT_COMPLETE;__leave;}
            }
            set(cmd->unit_handle,(int32_t)op->rawcode,1);
            error=war3_validate_hero_component(cmd,&hero);if(error) __leave;
        } else if((int32_t)op->rawcode<current) {
            int32_t accepted=strip(cmd->unit_handle,current-(int32_t)op->rawcode);
            error=war3_validate_hero_component(cmd,&hero);if(error) __leave;
            if(!accepted) {error=ERROR_CAN_NOT_COMPLETE;__leave;}
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) {error=GetExceptionCode();}
    if(restore) recovery=war3_progress_restore_xp(cmd,&hero,xp,suspend);
    op->arg1=recovery;
    if(error) return error;
    if(recovery) return recovery;
    __try {
        error=war3_validate_hero_component(cmd,&hero);if(error) __leave;
        actual=get(cmd->unit_handle);
        error=war3_validate_hero_component(cmd,&hero);if(error) __leave;
        op->result=(uint32_t)actual;
        if(actual!=(int32_t)op->rawcode) error=ERROR_CAN_NOT_COMPLETE;
    } __except(EXCEPTION_EXECUTE_HANDLER) {error=GetExceptionCode();}
    return error;
}

static DWORD war3_add_bound_hero_skill_points(NativeCommand *cmd,NativeOp *op) {
    JassUnitIntQueryFn level=(JassUnitIntQueryFn)(uintptr_t)war3_persistent_native_handler("GetHeroLevel");
    War3HeroDeltaFn add=(War3HeroDeltaFn)(uintptr_t)war3_persistent_native_handler("UnitModifySkillPoints");
    NativeOp hero={0};DWORD error=ERROR_SUCCESS;int32_t before,after,accepted;int64_t target;
    if(cmd->op_count!=2 || cmd->ops[0].kind!=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY ||
       !op->rawcode || op->rawcode>1000000u || op->handler || op->arg0 || op->arg1)
        return ERROR_INVALID_PARAMETER;
    if(!war3_executable_pointer((uint64_t)(uintptr_t)level) || !war3_executable_pointer((uint64_t)(uintptr_t)add))
        return ERROR_PROC_NOT_FOUND;
    __try {
        error=war3_capture_progress_hero(cmd,&hero);if(error) __leave;
        int32_t current_level=level(cmd->unit_handle);
        error=war3_validate_hero_component(cmd,&hero);if(error) __leave;
        if(current_level<=0) {error=ERROR_INVALID_PARAMETER;__leave;}
        if(!war3_readable_span(hero.handler+0x104,4)) {error=ERROR_INVALID_ADDRESS;__leave;}
        before=*(int32_t *)(uintptr_t)(hero.handler+0x104);target=(int64_t)before+op->rawcode;
        if(target>INT32_MAX) {error=ERROR_ARITHMETIC_OVERFLOW;__leave;}
        accepted=add(cmd->unit_handle,(int32_t)op->rawcode);
        error=war3_validate_hero_component(cmd,&hero);if(error) __leave;
        if(!accepted) {error=ERROR_CAN_NOT_COMPLETE;__leave;}
        if(!war3_readable_span(hero.handler+0x104,4)) {error=ERROR_INVALID_ADDRESS;__leave;}
        after=*(int32_t *)(uintptr_t)(hero.handler+0x104);
        op->arg0=(uint32_t)after;
        if((int64_t)after!=target) {error=ERROR_CAN_NOT_COMPLETE;__leave;}
        op->result=op->rawcode;
    } __except(EXCEPTION_EXECUTE_HANDLER) {error=GetExceptionCode();}
    return error;
}
