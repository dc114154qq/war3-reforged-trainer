/* All access is serialized by the existing game-thread dispatcher. Tokens
   describe a particular effect instance, never a currently selected unit. */
typedef struct War3AbilityEffect {
    uint64_t token,identity[10];
    NativeCommand bound;
    uint32_t id,added,captured,area_touched,original_area,requested_area;
    uint32_t hold,invoked,order,order_known,level,executed;
} War3AbilityEffect;
static War3AbilityEffect g_ability_effects[16];
static uint64_t g_ability_effect_serial;

static DWORD war3_effect_check(War3AbilityEffect *s) {
    uint64_t current[10];DWORD error=war3_action_ability_state(&s->bound,s->id,current);
    if(error) return error;
    if(!s->captured || !war3_action_same_ability(s->identity,current) || current[8]!=s->identity[8])
        return ERROR_INVALID_HANDLE;
    return war3_direct_identity_memory(&s->bound,s->id,s->identity);
}

static DWORD war3_effect_area(War3AbilityEffect *s,uint32_t *bits) {
    JassAbilityLevelFieldGetFn get=(JassAbilityLevelFieldGetFn)(uintptr_t)war3_persistent_native_handler("BlzGetAbilityRealLevelField");
    DWORD error=war3_effect_check(s);if(error) return error;
    *bits=(uint32_t)get(s->identity[0],0x61617265u,(int32_t)s->level);
    return war3_effect_check(s);
}

static DWORD war3_effect_store_area(War3AbilityEffect *s,uint32_t bits) {
    JassAbilityRealLevelFieldSetFn set=(JassAbilityRealLevelFieldSetFn)(uintptr_t)war3_persistent_native_handler("BlzSetAbilityRealLevelField");
    DWORD error=war3_effect_check(s);uint32_t actual;float value=war3_real_from_bits(bits);
    if(error) return error;
    uint32_t ok=(uint32_t)set(s->identity[0],0x61617265u,(int32_t)s->level,&value);
    error=war3_effect_area(s,&actual);if(error) return error;
    return ok && actual==bits?ERROR_SUCCESS:ERROR_INVALID_DATA;
}

/* Retain the record on cleanup failure so a caller holding its token can
   retry. Never restore a field overwritten by a trigger with a third value. */
static DWORD war3_effect_cleanup(War3AbilityEffect *s) {
    DWORD error;uint32_t bits;
    if(!s->captured) return ERROR_INVALID_DATA;
    error=war3_effect_check(s);if(error) return error;
    if(s->hold && s->invoked) {
        JassUnitIntQueryFn current=(JassUnitIntQueryFn)(uintptr_t)war3_persistent_native_handler("GetUnitCurrentOrder");
        JassIssueImmediateOrderByIdFn stop=(JassIssueImmediateOrderByIdFn)(uintptr_t)war3_persistent_native_handler("IssueImmediateOrderById");
        if(!s->order_known) return ERROR_INVALID_DATA;
        uint32_t order=(uint32_t)current(s->bound.unit_handle);
        error=war3_effect_check(s);if(error) return error;
        if(order!=s->order) return ERROR_INVALID_DATA;
        uint32_t stopped=stop(s->bound.unit_handle,851972);
        error=war3_effect_check(s);if(error) return error;
        if(!stopped) return ERROR_INVALID_DATA;
        s->invoked=0;
    }
    if(s->area_touched) {
        error=war3_effect_area(s,&bits);if(error) return error;
        if(bits!=s->original_area && bits!=s->requested_area) return ERROR_INVALID_DATA;
        if(bits!=s->original_area) {error=war3_effect_store_area(s,s->original_area);if(error) return error;}
        s->area_touched=0;
    }
    if(s->added) {
        JassUnitRemoveAbilityFn remove=(JassUnitRemoveAbilityFn)(uintptr_t)war3_persistent_native_handler("UnitRemoveAbility");
        uint64_t after[10];error=war3_effect_check(s);if(error) return error;
        uint32_t removed=remove(s->bound.unit_handle,s->id);
        error=war3_action_ability_state(&s->bound,s->id,after);if(error) return error;
        if(!removed || after[0]) return ERROR_INVALID_DATA;
    }
    ZeroMemory(s,sizeof(*s));return ERROR_SUCCESS;
}

static DWORD war3_finish_ability_effect(NativeCommand *cmd,NativeOp *op) {
    if(cmd->op_count!=2 || cmd->ops[0].kind!=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY ||
       !op->handler || op->rawcode || op->arg0 || op->arg1) return ERROR_INVALID_PARAMETER;
    for(unsigned n=0;n<16;++n) {
        War3AbilityEffect *s=&g_ability_effects[n];if(s->token!=op->handler) continue;
        if(cmd->unit_handle!=s->bound.unit_handle || cmd->ops[0].handler!=s->bound.ops[0].handler ||
           cmd->ops[0].arg0!=s->bound.ops[0].arg0 || cmd->ops[0].arg1!=s->bound.ops[0].arg1)
            return ERROR_INVALID_HANDLE;
        DWORD error;
        __try {error=war3_effect_cleanup(s);} __except(EXCEPTION_EXECUTE_HANDLER) {error=GetExceptionCode();}
        op->reserved=error;op->result=error?0:1;return error;
    }
    return ERROR_NOT_FOUND;
}

/* op158: rawcode=id, handler=mode(2/3/4), arg0=passes, arg1=packed XY.
   op159: rawcode=flags(area=1,hold=2,unit-position=4), arg0=area float bits. */
static DWORD war3_start_ability_effect(NativeCommand *cmd,NativeOp *op) {
    const NativeOp *options=&cmd->ops[2];uint32_t flags=options->rawcode;
    DWORD error=ERROR_SUCCESS,cleanup=ERROR_SUCCESS;War3AbilityEffect *s=NULL;
    uint64_t before[10]={0},vtable,callback;uint32_t slot,attempted=0,returned=0;
    float x=war3_real_from_bits((uint32_t)op->arg1),y=war3_real_from_bits((uint32_t)(op->arg1>>32));
    float area=war3_real_from_bits((uint32_t)options->arg0);
    const char *required[]={"UnitAddAbility","UnitRemoveAbility","BlzGetAbilityRealLevelField",
        "BlzSetAbilityRealLevelField","BlzUnitHideAbility","IssueImmediateOrderById","GetUnitCurrentOrder","GetUnitX","GetUnitY"};
    if(cmd->op_count!=3 || cmd->ops[0].kind!=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY ||
       options->kind!=WAR3_NATIVE_OP_ABILITY_EFFECT_OPTIONS || options->handler || options->arg1 ||
       flags>7 || !op->rawcode || op->handler<2 || op->handler>4 || !op->arg0 || op->arg0>255 ||
       options->arg0>UINT32_MAX || (!(flags&1) && options->arg0) ||
       ((flags&1) && (!(area==area) || area<1.0f || area>1000000.0f)) ||
       (op->handler!=3 && (op->arg1 || (flags&4))) || ((flags&4) && op->arg1) ||
       !(x==x) || !(y==y) || x < -1000000.0f || x > 1000000.0f || y < -1000000.0f || y > 1000000.0f)
        return ERROR_INVALID_PARAMETER;
    for(unsigned n=0;n<sizeof(required)/sizeof(required[0]);++n)
        if(!war3_executable_pointer(war3_persistent_native_handler(required[n]))) return ERROR_PROC_NOT_FOUND;
    for(unsigned n=0;n<16;++n) {
        War3AbilityEffect *entry=&g_ability_effects[n];
        /* Only one held effect per unit: stop orders affect the whole unit. */
        if(entry->token && entry->bound.ops[0].handler==cmd->ops[0].handler &&
           entry->bound.ops[0].arg0==cmd->ops[0].arg0) return ERROR_BUSY;
        if(!entry->token && !s) s=entry;
    }
    if(!s || g_ability_effect_serial==UINT64_MAX) return ERROR_TOO_MANY_CMDS;
    ZeroMemory(s,sizeof(*s));s->token=++g_ability_effect_serial;s->bound=*cmd;s->id=op->rawcode;s->hold=flags&2;
    slot=op->handler==2?0x998u:op->handler==3?0xa58u:0xa78u;
    __try {
        error=war3_action_ability_state(cmd,s->id,before);if(error) __leave;
        if(!before[0]) {
            attempted=1;
            s->added=((JassUnitAddAbilityFn)(uintptr_t)war3_persistent_native_handler("UnitAddAbility"))(cmd->unit_handle,s->id);
            returned=1;
            error=war3_action_ability_state(cmd,s->id,before);if(error) __leave;
            if(!s->added || !before[0]) {error=ERROR_INVALID_DATA;__leave;}
        }
        memcpy(s->identity,before,sizeof(before));s->captured=1;s->level=before[8]?((uint32_t)before[8]-1):0;
        if(flags&4) {
            error=war3_effect_check(s);if(error) __leave;
            x=war3_real_from_bits(((JassUnitRealQueryFn)(uintptr_t)war3_persistent_native_handler("GetUnitX"))(cmd->unit_handle));
            error=war3_effect_check(s);if(error) __leave;
            y=war3_real_from_bits(((JassUnitRealQueryFn)(uintptr_t)war3_persistent_native_handler("GetUnitY"))(cmd->unit_handle));
            error=war3_effect_check(s);if(error) __leave;
            if(!(x==x) || !(y==y) || x < -1000000.0f || x > 1000000.0f || y < -1000000.0f || y > 1000000.0f) {error=ERROR_INVALID_DATA;__leave;}
        }
        if(flags&1) {
            error=war3_effect_area(s,&s->original_area);if(error) __leave;
            float original=war3_real_from_bits(s->original_area);
            if(!(original==original) || original < 0 || original > 1000000.0f) {error=ERROR_INVALID_DATA;__leave;}
            s->requested_area=(uint32_t)options->arg0;s->area_touched=1;
            error=war3_effect_store_area(s,s->requested_area);if(error) __leave;
        }
        if(s->added && s->hold) {
            error=war3_effect_check(s);if(error) __leave;
            ((JassUnitIntBoolFn)(uintptr_t)war3_persistent_native_handler("BlzUnitHideAbility"))(cmd->unit_handle,s->id,1);
            error=war3_effect_check(s);if(error) __leave;
        }
        for(unsigned n=0;n<op->arg0;++n) {
            error=war3_effect_check(s);if(error) __leave;
            vtable=*(uint64_t *)(uintptr_t)s->identity[1];
            if(!war3_readable_span(vtable,slot+8)) {error=ERROR_INVALID_ADDRESS;__leave;}
            callback=*(uint64_t *)(uintptr_t)(vtable+slot);
            if(!war3_executable_pointer(callback)) {error=ERROR_INVALID_ADDRESS;__leave;}
            s->invoked=1;
            if(op->handler==3) ((DirectAbilityPointFn)(uintptr_t)callback)(s->identity[1],&x,&y);
            else ((DirectAbilityImmediateFn)(uintptr_t)callback)(s->identity[1]);
            ++s->executed;
            error=war3_effect_check(s);if(error) __leave;
        }
        if(s->hold) {
            s->order=(uint32_t)((JassUnitIntQueryFn)(uintptr_t)war3_persistent_native_handler("GetUnitCurrentOrder"))(cmd->unit_handle);
            error=war3_effect_check(s);if(error) __leave;s->order_known=1;
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) {error=GetExceptionCode();}
    op->arg0=s->executed;
    if(error || !s->hold) {
        __try {
            if(s->captured) cleanup=war3_effect_cleanup(s);
            else if(attempted && (!returned || s->added || before[0])) cleanup=ERROR_INVALID_DATA;
            else ZeroMemory(s,sizeof(*s));
        } __except(EXCEPTION_EXECUTE_HANDLER) {cleanup=GetExceptionCode();}
    }
    op->result=s->token;op->reserved=cleanup;
    return error?error:cleanup;
}
