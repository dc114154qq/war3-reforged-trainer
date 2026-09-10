typedef struct War3CloneGuard {
    const NativeCommand *source;
    NativeCommand target;
    int target_captured;
} War3CloneGuard;

static void war3_clone_check(War3CloneGuard *guard) {
    if(!guard->source) return;
    DWORD error=war3_validate_unit_identity(guard->source,&guard->source->ops[0]);
    if(!error && guard->target_captured)
        error=war3_validate_unit_identity(&guard->target,&guard->target.ops[0]);
    if(error) RaiseException(error,0,0,NULL);
}

static DWORD war3_clone_capture_target(War3CloneGuard *guard,uint64_t handle) {
    if(!guard->source) return ERROR_SUCCESS;
    War3WorldTarget target;
    DWORD error=war3_capture_world_target(handle,&target);
    if(error) return error;
    if(target.jass==guard->source->unit_handle || target.object==guard->source->ops[0].handler ||
       target.full==guard->source->ops[0].arg0) return ERROR_INVALID_HANDLE;
    war3_world_target_command(&target,&guard->target);
    guard->target_captured=1;
    return ERROR_SUCCESS;
}

/* clang is the helper compiler. The expression form also checks nested getter
   calls before a surrounding setter can execute. Evaluate every callback once. */
#define WAR3_CLONE_VALUE(guard,call) ({ __auto_type clone_value=(call); war3_clone_check(guard); clone_value; })
#define WAR3_CLONE_VOID(guard,call) do { (call); war3_clone_check(guard); } while(0)
