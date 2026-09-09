/* Bound add/remove/level/reset operations for heroes and nonheroes alike.
   action is op.handler: 1 add (optional level), 2 remove, 3 level, 4 reset.
   op.arg1 may pin a previously enumerated ability's full generation. */
static DWORD war3_action_ability_state(const NativeCommand *cmd,uint32_t id,uint64_t *values) {
    NativeOp query={0};DWORD error;
    query.rawcode=id;query.handler=war3_persistent_native_handler("BlzGetUnitAbility");
    query.arg0=war3_persistent_native_handler("BlzGetAbilityId");
    ZeroMemory(values,10*sizeof(uint64_t));
    error=war3_bound_ability_metadata(cmd,&query,values);
    if(error==ERROR_NOT_FOUND) return ERROR_SUCCESS;
    if(error) return error;
    uint64_t tag=values[4];
    if((uint32_t)tag!=0x2b61676cu || tag==0x41496e762b61676cULL || tag==0x414865722b61676cULL ||
       tag==0x416d6f762b61676cULL || tag==0x4161746b2b61676cULL ||
       (int32_t)values[8]<0) return ERROR_INVALID_DATA;
    return ERROR_SUCCESS;
}

static int war3_action_same_ability(const uint64_t *a,const uint64_t *b) {
    return a[0]==b[0] && a[1]==b[1] && a[2]==b[2] && a[3]==b[3] && a[4]==b[4];
}

static DWORD war3_manage_bound_ability(NativeCommand *cmd,NativeOp *op) {
    uint64_t before[10],after[10],expected=op->arg1;
    uint32_t action=(uint32_t)op->handler,added=0,removed=0;
    DWORD error;
    JassUnitAddAbilityFn add=(JassUnitAddAbilityFn)(uintptr_t)war3_persistent_native_handler("UnitAddAbility");
    JassUnitRemoveAbilityFn remove=(JassUnitRemoveAbilityFn)(uintptr_t)war3_persistent_native_handler("UnitRemoveAbility");
    JassSetUnitAbilityLevelFn set=(JassSetUnitAbilityLevelFn)(uintptr_t)war3_persistent_native_handler("SetUnitAbilityLevel");
    if(cmd->ops[0].kind!=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY || !op->rawcode ||
       op->handler<1 || op->handler>4 || op->arg0>100000 || (action==3 && !op->arg0) ||
       ((action==2 || action==4) && op->arg0)) return ERROR_INVALID_PARAMETER;
    if(((action==1 || action==4) && !war3_executable_pointer((uint64_t)(uintptr_t)add)) ||
       ((action==2 || action==4) && !war3_executable_pointer((uint64_t)(uintptr_t)remove)) ||
       (op->arg0 && !war3_executable_pointer((uint64_t)(uintptr_t)set))) return ERROR_PROC_NOT_FOUND;
    op->arg1=0;op->reserved=0;
    __try {
        error=war3_action_ability_state(cmd,op->rawcode,before);if(error) return error;
        if(expected && (!before[0] || before[3]!=expected)) return ERROR_INVALID_HANDLE;
        if(action==2 || action==4) {
            if(before[0]) {
                removed=remove(cmd->unit_handle,op->rawcode);
                error=war3_action_ability_state(cmd,op->rawcode,after);if(error) return error;
                if(!removed || after[0]) return ERROR_INVALID_DATA;
            }
            if(action==2) {op->result=removed;return ERROR_SUCCESS;}
            ZeroMemory(before,sizeof(before));
        }
        if(action==1 || action==4) {
            if(!before[0]) {
                added=add(cmd->unit_handle,op->rawcode);
                error=war3_action_ability_state(cmd,op->rawcode,after);if(error) return error;
                if(!added && !after[0]) {op->result=0;return ERROR_SUCCESS;}
                if(!added || !after[0]) return ERROR_INVALID_DATA;
                memcpy(before,after,sizeof(before));
            }
            op->result=added;
        }
        if(op->arg0) {
            if(!before[0]) return ERROR_NOT_FOUND;
            uint32_t actual=set(cmd->unit_handle,op->rawcode,(int32_t)op->arg0);
            error=war3_action_ability_state(cmd,op->rawcode,after);if(error) return error;
            op->arg1=after[8];op->reserved=1;
            if(!war3_action_same_ability(before,after)) return ERROR_INVALID_HANDLE;
            if(actual!=op->arg0 || after[8]!=op->arg0) return ERROR_INVALID_DATA;
            if(action==3) op->result=actual;
        } else op->arg1=before[8];
    } __except(EXCEPTION_EXECUTE_HANDLER) {return GetExceptionCode();}
    return ERROR_SUCCESS;
}
