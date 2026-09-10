typedef struct War3CloneItem {
    uint64_t handle, object, full, wrapper;
    uint32_t rawcode;
    int32_t slot;
} War3CloneItem;

typedef struct War3CloneGuard {
    const NativeCommand *source;
    NativeCommand target;
    int source_captured, target_captured;
    JassUnitItemInSlotFn slot_fn;
    War3CloneItem source_items[6], target_items[6];
    War3CloneItem *active_items[2];
    int inventory_captured;
    struct War3CloneAbilities *abilities;
} War3CloneGuard;

static void war3_clone_ability_state(War3CloneGuard *guard);
static void war3_clone_ability_membership(War3CloneGuard *guard);

static void war3_clone_item_object(const War3CloneItem *item) {
    if(!item || !item->handle) return;
    JassUnitHandleResolveFn resolve=(JassUnitHandleResolveFn)(uintptr_t)g_persistent_item_resolver;
    War3AgentResolveFn agent=(War3AgentResolveFn)(uintptr_t)g_persistent_agent_resolver;
    if(!item->full || !item->rawcode || resolve(item->handle)!=item->object ||
       *(uint64_t *)(uintptr_t)(item->object+0x18)!=item->full ||
       *(uint32_t *)(uintptr_t)(item->object+0x70)!=item->rawcode ||
       agent((uint32_t)item->full,(uint32_t)(item->full>>32))!=item->wrapper ||
       *(uint64_t *)(uintptr_t)(item->wrapper+0x18)!=0x6974656d2b61676cULL ||
       *(uint64_t *)(uintptr_t)(item->wrapper+0x20)!=item->full ||
       *(uint64_t *)(uintptr_t)(item->wrapper+0x90)!=item->object)
        RaiseException(ERROR_INVALID_HANDLE,0,0,NULL);
}

/* Initial capture checks readable spans and executable resolvers. All callers
   run inside the clone's SEH region. Recheck object-table links and generations
   directly on the hot path; a decommitted object raises into that same handler. */
static void war3_clone_unit_object(const NativeCommand *cmd) {
    const NativeOp *identity=&cmd->ops[0];
    JassUnitHandleResolveFn unit=(JassUnitHandleResolveFn)(uintptr_t)g_persistent_unit_resolver;
    War3AgentResolveFn agent=(War3AgentResolveFn)(uintptr_t)g_persistent_agent_resolver;
    if(unit(cmd->unit_handle)!=identity->handler ||
       agent((uint32_t)identity->arg0,(uint32_t)(identity->arg0>>32))!=identity->arg1 ||
       *(uint64_t *)(uintptr_t)(identity->handler+0x18)!=identity->arg0 ||
       *(uint64_t *)(uintptr_t)(identity->arg1+0x18)!=0x2b7733752b61676cULL ||
       *(uint64_t *)(uintptr_t)(identity->arg1+0x20)!=identity->arg0 ||
       *(uint64_t *)(uintptr_t)(identity->arg1+0x90)!=identity->handler)
        RaiseException(ERROR_INVALID_HANDLE,0,0,NULL);
}

static void war3_clone_check_state(War3CloneGuard *guard) {
    if(!guard->source) return;
    if(!guard->source_captured) {
        DWORD error=war3_validate_unit_identity(guard->source,&guard->source->ops[0]);
        if(error) RaiseException(error,0,0,NULL);
        guard->source_captured=1;
    }
    war3_clone_unit_object(guard->source);
    if(guard->target_captured) war3_clone_unit_object(&guard->target);
    war3_clone_item_object(guard->active_items[0]);
    war3_clone_item_object(guard->active_items[1]);
    war3_clone_ability_state(guard);
}

static void war3_clone_check(War3CloneGuard *guard) {
    if(!guard->source) return;
    war3_clone_check_state(guard);
    for(unsigned n=0;n<2;++n) {
        War3CloneItem *item=guard->active_items[n];
        if(!item || item->slot<0) continue;
        uint64_t unit=n?guard->target.unit_handle:guard->source->unit_handle;
        uint64_t current=guard->slot_fn(unit,item->slot);
        /* Slot queries are engine calls too. Recheck before the next query. */
        war3_clone_check_state(guard);
        if(current!=item->handle) RaiseException(ERROR_INVALID_HANDLE,0,0,NULL);
    }
    war3_clone_ability_membership(guard);
}

static void war3_clone_capture_item(War3CloneGuard *guard,uint64_t handle,War3CloneItem *item) {
    JassUnitHandleResolveFn resolve=(JassUnitHandleResolveFn)(uintptr_t)g_persistent_item_resolver;
    War3AgentResolveFn agent=(War3AgentResolveFn)(uintptr_t)g_persistent_agent_resolver;
    item->handle=handle;
    if(!handle) return;
    item->object=resolve(handle);
    if(!war3_readable_span(item->object,0x78)) RaiseException(ERROR_INVALID_ADDRESS,0,0,NULL);
    item->full=*(uint64_t *)(uintptr_t)(item->object+0x18);
    item->rawcode=*(uint32_t *)(uintptr_t)(item->object+0x70);
    item->wrapper=agent((uint32_t)item->full,(uint32_t)(item->full>>32));
    if(!war3_readable_span(item->wrapper,0x98)) RaiseException(ERROR_INVALID_ADDRESS,0,0,NULL);
    war3_clone_item_object(item);
    war3_clone_check(guard);
}

static int war3_clone_same_item(const War3CloneItem *a,const War3CloneItem *b) {
    return a->handle && b->handle &&
        (a->handle==b->handle || a->full==b->full || a->object==b->object);
}

static void war3_clone_saved_item_objects(War3CloneGuard *guard) {
    if(!guard->inventory_captured) return;
    for(unsigned slot=0;slot<6;++slot) {
        war3_clone_item_object(&guard->source_items[slot]);
        war3_clone_item_object(&guard->target_items[slot]);
    }
}

static void war3_clone_check_saved_items(War3CloneGuard *guard) {
    if(!guard->inventory_captured) return;
    for(unsigned slot=0;slot<6;++slot) {
        guard->active_items[0]=&guard->source_items[slot];
        guard->active_items[1]=guard->target_items[slot].handle?&guard->target_items[slot]:NULL;
        war3_clone_check(guard);
    }
    /* Later slot queries must not invalidate an already visited object. */
    war3_clone_saved_item_objects(guard);
    guard->active_items[0]=guard->active_items[1]=NULL;
}

static void war3_clone_prepare_items(War3CloneGuard *guard,JassUnitItemInSlotFn slot_fn) {
    if(!guard->source) return;
    if(!war3_executable_pointer(g_persistent_item_resolver) ||
       !war3_executable_pointer(g_persistent_agent_resolver))
        RaiseException(ERROR_PROC_NOT_FOUND,0,0,NULL);
    guard->slot_fn=slot_fn;
    for(int32_t slot=0;slot<6;++slot) {
        uint64_t item=slot_fn(guard->source->unit_handle,slot);
        war3_clone_check(guard);
        guard->source_items[slot].slot=slot;
        war3_clone_capture_item(guard,item,&guard->source_items[slot]);
        for(int32_t prior=0;prior<slot;++prior)
            if(war3_clone_same_item(&guard->source_items[slot],&guard->source_items[prior]))
                RaiseException(ERROR_INVALID_DATA,0,0,NULL);
    }
    guard->inventory_captured=1;
    war3_clone_check_saved_items(guard);
}

static void war3_clone_begin_item(War3CloneGuard *guard,unsigned slot) {
    if(!guard->inventory_captured) return;
    guard->active_items[0]=&guard->source_items[slot];
    guard->active_items[1]=NULL;
    war3_clone_check(guard);
}

static void war3_clone_track_item(War3CloneGuard *guard,unsigned source_slot,uint64_t handle,uint32_t id) {
    if(!guard->inventory_captured) return;
    War3CloneItem *item=&guard->target_items[source_slot];
    item->slot=-1;
    war3_clone_capture_item(guard,handle,item);
    if(item->rawcode!=id) RaiseException(ERROR_INVALID_DATA,0,0,NULL);
    for(unsigned n=0;n<6;++n) {
        if(war3_clone_same_item(item,&guard->source_items[n]) ||
           (n!=source_slot && war3_clone_same_item(item,&guard->target_items[n])))
            RaiseException(ERROR_INVALID_HANDLE,0,0,NULL);
    }
    guard->active_items[1]=item;
    for(int32_t slot=0;slot<6;++slot) {
        uint64_t current=guard->slot_fn(guard->target.unit_handle,slot);
        war3_clone_check(guard);
        if(current==handle) {
            if(item->slot>=0) RaiseException(ERROR_INVALID_DATA,0,0,NULL);
            item->slot=slot;
        }
    }
    if(item->slot<0) RaiseException(ERROR_INVALID_HANDLE,0,0,NULL);
    war3_clone_check(guard);
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

#include "war3_native_clone_abilities.h"

/* Finish after all callback-based membership queries. A later ability query
   must not hide an item generation change (or vice versa). These resolvers and
   identity reads perform no map mutations and add no membership callbacks. */
static void war3_clone_final_state(War3CloneGuard *guard) {
    if(!guard->source) return;
    war3_clone_check_state(guard);
    war3_clone_saved_item_objects(guard);
    war3_clone_saved_ability_objects(guard);
}
