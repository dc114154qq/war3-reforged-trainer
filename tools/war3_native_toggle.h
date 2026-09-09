/* Records describe abilities hidden by this helper, not whether an effect is
   currently enabled. Every request still issues the engine's enable order. */
typedef struct War3ManagedToggle {
    struct War3ManagedToggle *next;
    uint64_t unit,owner,full,identity[10];
    uint32_t id;
} War3ManagedToggle;
static War3ManagedToggle *g_managed_toggles;

static DWORD war3_enable_bound_toggle(NativeCommand *cmd,NativeOp *op) {
    War3AbilityEffect s={0};War3ManagedToggle *owned=NULL,*reserved=NULL;
    JassUnitAddAbilityFn add=(JassUnitAddAbilityFn)(uintptr_t)war3_persistent_native_handler("UnitAddAbility");
    JassUnitIntBoolFn hide=(JassUnitIntBoolFn)(uintptr_t)war3_persistent_native_handler("BlzUnitHideAbility");
    JassIssueImmediateOrderByIdFn issue=(JassIssueImmediateOrderByIdFn)(uintptr_t)war3_persistent_native_handler("IssueImmediateOrderById");
    DWORD error=ERROR_SUCCESS,cleanup=ERROR_SUCCESS;uint32_t attempted=0,returned=0,visible=0;
    if(cmd->op_count!=2 || cmd->ops[0].kind!=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY ||
       !op->rawcode || !op->handler || op->handler>INT32_MAX || op->arg0 || op->arg1) return ERROR_INVALID_PARAMETER;
    if(!war3_executable_pointer((uint64_t)(uintptr_t)add) || !war3_executable_pointer((uint64_t)(uintptr_t)hide) ||
       !war3_executable_pointer((uint64_t)(uintptr_t)issue) ||
       !war3_executable_pointer(war3_persistent_native_handler("UnitRemoveAbility"))) return ERROR_PROC_NOT_FOUND;
    s.bound=*cmd;s.id=op->rawcode;op->result=0;op->reserved=0;
    __try {
        error=war3_action_ability_state(cmd,s.id,s.identity);if(error) __leave;
        War3ManagedToggle **link=&g_managed_toggles;
        while(*link) {
            War3ManagedToggle *row=*link;
            if(row->unit==cmd->ops[0].handler) {
                if(row->full!=cmd->ops[0].arg0 || row->owner!=cmd->ops[0].arg1 ||
                   (row->id==s.id && !war3_action_same_ability(row->identity,s.identity))) {
                    *link=row->next;HeapFree(GetProcessHeap(),0,row);continue;
                }
                if(row->id==s.id) owned=row;
            }
            link=&row->next;
        }
        if(!s.identity[0]) {
            reserved=(War3ManagedToggle *)HeapAlloc(GetProcessHeap(),HEAP_ZERO_MEMORY,sizeof(*reserved));
            if(!reserved) {error=ERROR_OUTOFMEMORY;__leave;}
            attempted=1;s.added=add(cmd->unit_handle,s.id);returned=1;
            error=war3_action_ability_state(cmd,s.id,s.identity);if(error) __leave;
            if(!s.added || !s.identity[0]) {error=ERROR_INVALID_DATA;__leave;}
        }
        s.captured=1;
        if(s.added || owned) {
            error=war3_effect_check(&s);if(error) __leave;
            visible=1;hide(cmd->unit_handle,s.id,0);
            error=war3_effect_check(&s);if(error) __leave;
        }
        error=war3_effect_check(&s);if(error) __leave;
        op->result=issue(cmd->unit_handle,(int32_t)op->handler);
        error=war3_effect_check(&s);if(error) __leave;
        if(!op->result) {error=ERROR_INVALID_DATA;__leave;}
        if(s.added || owned) {
            hide(cmd->unit_handle,s.id,1);
            error=war3_effect_check(&s);if(error) __leave;
            visible=0;
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) {error=GetExceptionCode();}
    if(error) {
        __try {
            if(s.added && s.captured) cleanup=war3_effect_cleanup(&s);
            else if(visible && owned) {
                cleanup=war3_effect_check(&s);
                if(!cleanup) {hide(cmd->unit_handle,s.id,1);cleanup=war3_effect_check(&s);}
            }
            if(attempted && (!returned || (s.added && !s.captured) || (!s.added && s.identity[0])))
                cleanup=ERROR_INVALID_DATA;
        } __except(EXCEPTION_EXECUTE_HANDLER) {cleanup=GetExceptionCode();}
    }
    if(reserved) {
        if(s.captured && s.identity[0] && (!error || cleanup)) {
            reserved->unit=cmd->ops[0].handler;reserved->full=cmd->ops[0].arg0;reserved->owner=cmd->ops[0].arg1;
            reserved->id=op->rawcode;memcpy(reserved->identity,s.identity,sizeof(s.identity));
            reserved->next=g_managed_toggles;g_managed_toggles=reserved;
        } else HeapFree(GetProcessHeap(),0,reserved);
    }
    op->reserved=cleanup;return error?error:cleanup;
}
