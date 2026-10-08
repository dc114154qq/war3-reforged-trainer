/* Diagnostic only: disposable unit/item, no UI selection or user-item writes. */
typedef struct InheritedProbeWork {
    EquipmentEffectWork effect;
    uint64_t (*player)(int32_t);
    uint64_t (*create_unit)(uint64_t,uint32_t,float *,float *,float *);
    void (*remove_unit)(uint64_t);
    uint8_t (*add_ability)(uint64_t,uint32_t);
    uint8_t (*group_add)(uint64_t,uint64_t);
    uint32_t (*unit_x)(uint64_t),(*unit_y)(uint64_t);
    uint64_t (*create_item)(uint32_t,float *,float *);
    EffectUnitResolveFn resolve_unit;
    void (*enum_player)(uint64_t,uint64_t,uint64_t);
    uint8_t (*in_group)(uint64_t,uint64_t);
    uint32_t error,stage,unit_removed,item_removed,transfer_verified,equip_verified,
             inherited_unequip_verified,drop_verified,pickup_verified,bag_repair_verified;
    uint64_t disposable_unit,disposable_item;
} InheritedProbeWork;
_Static_assert(sizeof(InheritedProbeWork)==1816,"InheritedProbeWork ABI");
__declspec(dllexport) const uint32_t inherited_probe_abi[3]={0x2426805au,216u,1816u};
static InheritedProbeWork *inherited_probe_current;
static void (*inherited_probe_observe)(InheritedProbeWork *,uint32_t);
static uint32_t inherited_probe_plain_transfer;

static uint32_t InheritedProbeDisposeItem(InheritedProbeWork *p){
    EquipmentEffectWork *w=&p->effect;
    if(!p->disposable_item)return 1;
    /* Unhook owned equipment passives before destroying a diagnostic item.
       These calls only touch the newly created disposable unit/instance. */
    for(int i=0;i<9;++i)
        if(w->equipped(p->disposable_unit,w->slot_enum(i))==p->disposable_item)
            if(w->unequip(p->disposable_unit,w->slot_enum(i))!=p->disposable_item)return 0;
    if(w->item_id(p->disposable_item)){
        w->remove_from_unit(p->disposable_unit,p->disposable_item);
        w->remove_item(p->disposable_item);
    }
    return !w->item_id(p->disposable_item);
}

static void InheritedProbeEnum(uint64_t group,uint64_t player,uint64_t filter){
    (void)player;(void)filter;
    inherited_probe_current->group_add(group,inherited_probe_current->disposable_unit);
}
static void InheritedProbeReset(EquipmentEffectWork *w,uint32_t action){
    uint8_t *p=(uint8_t *)w;
    memset(p+64,0,416);memset(p+688,0,800);memset(p+1536,0,112);memset(p+1656,0,16);
    w->action=action;w->slot=0;
}
static uint64_t InheritedProbeAbility(uint64_t owner,uint64_t unit,uint32_t rawcode){
    uint64_t node=*(uint64_t *)(uintptr_t)(owner+0xd8u);
    for(uint32_t i=0;node && i<512u;++i){
        uint64_t wrapper=node-0x38u,data=*(uint64_t *)(uintptr_t)(wrapper+0x90u);
        if(data && *(uint64_t *)(uintptr_t)(data+0x68u)==unit &&
           *(uint32_t *)(uintptr_t)(data+0x70u)==rawcode)return data;
        node=*(uint64_t *)(uintptr_t)(wrapper+0x40u);
    }return 0;
}
static int InheritedProbeRun(EquipmentEffectWork *w,uint64_t object,uint32_t action){
    InheritedProbeReset(w,action);
    w->expected_flags=*(uint32_t *)(uintptr_t)(object+w->flag_offset);
    w->expected_class=*(uint32_t *)(uintptr_t)(object+w->class_offset);
    w->expected_type=*(uint32_t *)(uintptr_t)(object+w->type_offset);
    BridgeEquipmentEffectQuery();return !w->error && w->completed==1 && !w->cleanup && w->changed==1;
}
__declspec(dllexport) uint64_t BridgeInheritedProbeQuery(void){
    InheritedProbeWork *p=(InheritedProbeWork *)g_dispatch->work;
    EquipmentEffectWork *w=&p->effect;
    if(!p || p->bag_repair_verified || !p->resolve_unit || !p->player || !p->create_unit ||
       !p->remove_unit || !p->add_ability || !p->group_add || !p->create_item ||
       !p->unit_x || !p->unit_y || !p->enum_player || !p->in_group || w->expected_tls!=g_dispatch->tls_value)return 0;
    uint64_t source=w->target,unit_object=0,item_object=0,owner=0,inventory=0;
    void *original_work=g_dispatch->work;
    __try {
        __try {
            p->stage=1;
            uint32_t matches=0,count=(uint32_t)BridgeSelect();
            for(uint32_t i=0;i<count;++i)if(w->selection.rows[i].unit==source)++matches;
            if(w->selection.error || !w->selection.destroyed || matches!=1){p->error=501;return 0;}
            union{uint32_t bits;float value;} x,y;
            x.bits=p->unit_x(source);y.bits=p->unit_y(source);float facing=0;
            p->disposable_unit=p->create_unit(p->player(15),0x4870616cu,&x.value,&y.value,&facing);
            if(!p->disposable_unit){p->error=502;return 0;}
            w->target=p->disposable_unit;
            p->stage=2;
            p->add_ability(w->target,0x41496e76u);
            p->add_ability(w->target,0x41496e69u);
            p->add_ability(w->target,0x41457175u);
            if(w->bag_size(w->target)!=30){p->error=503;return 0;}
            unit_object=p->resolve_unit(w->target);
            if(!unit_object){p->error=504;return 0;}
            w->unit_full=*(uint64_t *)(uintptr_t)(unit_object+bridge_profile.object_handle);
            owner=BridgeEffectResolveObjectTable(w->base,w->unit_full);
            w->equipment=InheritedProbeAbility(owner,unit_object,0x41457175u);
            inventory=InheritedProbeAbility(owner,unit_object,0x41496e76u);
            if(!w->equipment || !inventory){p->error=505;return 0;}
            if(inherited_probe_observe)inherited_probe_observe(p,0);
            p->stage=3;
            p->disposable_item=p->create_item(w->rawcode,&x.value,&y.value);
            if(!p->disposable_item || !w->add_to_unit(w->target,p->disposable_item) ||
               w->classic_item(w->target,0)!=p->disposable_item){p->error=506;return 0;}
            if(inherited_probe_observe)inherited_probe_observe(p,1);
            w->item=p->disposable_item;
            uint64_t records=*(uint64_t *)(uintptr_t)(inventory+w->records_offset);
            w->item_full=*(uint64_t *)(uintptr_t)records;
            owner=BridgeEffectResolveObjectTable(w->base,w->item_full);
            item_object=owner?*(uint64_t *)(uintptr_t)(owner+bridge_profile.owner_data):0;
            if(!item_object || *(uint32_t *)(uintptr_t)(item_object+bridge_profile.object_rawcode)!=w->rawcode){p->error=507;return 0;}
            w->original_class=*(uint32_t *)(uintptr_t)(item_object+w->class_offset);
            inherited_probe_current=p;w->selection.enum_selected=InheritedProbeEnum;
            g_dispatch->work=w;w->classic_inventory=inventory;
            p->stage=4;
            if(!InheritedProbeRun(w,item_object,3)){p->error=508;return 0;}p->transfer_verified=1;
            if(inherited_probe_observe)inherited_probe_observe(p,2);
            w->classic_inventory=0;
            p->stage=5;
            if(!InheritedProbeRun(w,item_object,1)){p->error=509;return 0;}p->equip_verified=1;
            if(inherited_probe_observe)inherited_probe_observe(p,3);
            /* Simulate the observed chapter restoration only on this new item. */
            if(!inherited_probe_plain_transfer){
                *(uint32_t *)(uintptr_t)(item_object+w->class_offset)=w->original_class;
                *(uint32_t *)(uintptr_t)(item_object+w->type_offset)=0;
            }
            p->stage=6;
            if(!InheritedProbeRun(w,item_object,2) || w->equipped(w->target,w->slot_enum(0)) ||
               w->bagged(w->target,0)!=w->item || w->flags_after&0x4000u ||
               w->class_after!=w->original_class || w->type_after){p->error=510;return 0;}
            p->inherited_unequip_verified=1;
            if(inherited_probe_observe)inherited_probe_observe(p,4);
            /* Simulate an item already moved into AIni by the old raw-record path. */
            if(!inherited_probe_plain_transfer){
                *(uint32_t *)(uintptr_t)(item_object+w->flag_offset)|=0x4000u;
                if(!InheritedProbeRun(w,item_object,6)){p->error=513;return 0;}
                p->bag_repair_verified=1;
            }
            p->stage=7;
            w->remove_from_unit(w->target,w->item);
            if(w->bagged(w->target,0) || w->classic_item(w->target,0) || !w->item_id(w->item)){
                p->error=511;return 0;}
            p->drop_verified=1;
            if(inherited_probe_observe)inherited_probe_observe(p,5);
            p->stage=8;
            if(!w->add_to_unit(w->target,w->item) || w->classic_item(w->target,0)!=w->item){p->error=512;return 0;}
            p->pickup_verified=1;
            if(inherited_probe_observe)inherited_probe_observe(p,6);
        } __finally {
            g_dispatch->work=original_work;inherited_probe_current=0;
            if(p->disposable_item)p->item_removed=InheritedProbeDisposeItem(p);
            if(p->disposable_unit){
                p->remove_unit(p->disposable_unit);
                uint64_t group=w->selection.create_group();
                if(group){
                    __try {
                        p->enum_player(group,p->player(15),0);
                        p->unit_removed=!p->in_group(p->disposable_unit,group);
                    } __finally {w->selection.destroy_group(group);}
                }
            }
        }
    } __except(BridgeExceptionFilter(GetExceptionInformation())){p->error=GetExceptionCode();}
    return p->inherited_unequip_verified;
}

__declspec(dllexport) uint64_t BridgeInheritedCleanupQuery(void){
    InheritedProbeWork *p=(InheritedProbeWork *)g_dispatch->work;
    if(!p || !p->disposable_unit || !p->enum_player || !p->in_group)return 0;
    uint64_t group=p->effect.selection.create_group();
    if(!group)return 0;
    __try {
        p->enum_player(group,p->player(15),0);
        p->unit_removed=!p->in_group(p->disposable_unit,group);
    } __finally {p->effect.selection.destroy_group(group);}
    return p->unit_removed;
}

/* Read-only diagnostic: preserve the first failing native, even if DestroyGroup
   runs afterwards. The plain finally block above cannot attribute that fault. */
__declspec(dllexport) uint64_t BridgeInheritedCleanupTraceQuery(void){
    InheritedProbeWork *p=(InheritedProbeWork *)g_dispatch->work;
    if(!p || !p->disposable_unit || !p->enum_player || !p->in_group)return 0;
    uint64_t group=0;uint32_t first_stage=0;BridgeFault first_fault={0};
    __try {
        p->stage=1;group=p->effect.selection.create_group();
        if(!group){p->error=ERROR_NOT_ENOUGH_MEMORY;return 0;}
        p->stage=2;p->enum_player(group,p->player(15),0);
        p->stage=3;p->unit_removed=!p->in_group(p->disposable_unit,group);
    } __except(BridgeExceptionFilter(GetExceptionInformation())){
        p->error=GetExceptionCode();first_stage=p->stage;first_fault=bridge_fault;
    }
    if(group){
        __try {p->stage=4;p->effect.selection.destroy_group(group);}
        __except(BridgeExceptionFilter(GetExceptionInformation())){
            if(!first_stage){p->error=GetExceptionCode();first_stage=p->stage;first_fault=bridge_fault;}
        }
    }
    if(first_stage){p->stage=first_stage;bridge_fault=first_fault;}
    if(!first_stage && p->resolve_unit){
        uint64_t object=p->resolve_unit(p->disposable_unit);
        p->disposable_item=object;
        if(object){
            p->transfer_verified=*(uint32_t *)(uintptr_t)(object+bridge_profile.object_rawcode);
            p->equip_verified=*(uint32_t *)(uintptr_t)(object+0x1c8u);
        }
    }
    return p->unit_removed;
}

/* Minimal creation/removal control, without items or attribute setters. */
__declspec(dllexport) uint64_t BridgeCleanupCreationTraceQuery(void){
    InheritedProbeWork *p=(InheritedProbeWork *)g_dispatch->work;
    if(!p || p->disposable_unit || p->disposable_item || p->effect.slot>1u ||
       p->effect.expected_tls!=g_dispatch->tls_value)return 0;
    uint32_t count=(uint32_t)BridgeSelect(),matches=0,with_inventory=p->effect.slot;
    for(uint32_t i=0;i<count;++i)if(p->effect.selection.rows[i].unit==p->effect.target)++matches;
    if(matches!=1 || p->effect.selection.error || !p->effect.selection.destroyed){p->error=501;return 0;}
    __try {
        p->stage=10;union{uint32_t bits;float value;}x,y;
        x.bits=p->unit_x(p->effect.target);y.bits=p->unit_y(p->effect.target);float facing=0;
        p->disposable_unit=p->create_unit(p->player(15),0x4870616cu,&x.value,&y.value,&facing);
        if(!p->disposable_unit){p->error=502;return 0;}
        if(with_inventory){
            p->stage=11;p->add_ability(p->disposable_unit,0x41496e76u);
            p->add_ability(p->disposable_unit,0x41496e69u);p->add_ability(p->disposable_unit,0x41457175u);
        }
        p->stage=12;p->remove_unit(p->disposable_unit);
        BridgeInheritedCleanupTraceQuery();
        p->stage+=100;
    } __except(BridgeExceptionFilter(GetExceptionInformation())){p->error=GetExceptionCode();}
    return p->unit_removed;
}
