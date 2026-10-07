/* Per-instance native equipment classification; no template/global mutation. */
typedef struct EquipmentEffectWork {
    SelectionWork selection;
    uint32_t (*item_id)(uint64_t);
    uint64_t (*equipment_type)(uint64_t),(*item_class)(uint64_t);
    uint8_t (*equip)(uint64_t,uint64_t);
    uint64_t (*unequip)(uint64_t,uint64_t),(*slot_enum)(int32_t);
    uint64_t (*equipped)(uint64_t,uint64_t),(*bagged)(uint64_t,int32_t);
    int32_t (*bag_size)(uint64_t);
    uint64_t (*item_ability)(uint64_t,int32_t);
    uint32_t (*ability_id)(uint64_t);
    void *expected_tls;
    uint64_t base,target,unit_full,item,item_full,equipment;
    uint32_t flag_offset,class_offset,type_offset,count_offset,records_offset,
             capacity_offset,ability_owner_offset,mirror_offset;
    uint32_t action,slot,rawcode,original_class,expected_flags,expected_class,expected_type,reserved;
    uint32_t error,completed,changed,cleanup,flags_before,class_before,type_before,
             flags_after,class_after,type_after,ability_count,actual_slot;
    uint64_t eq_before[9],eq_after[9],bag_before[30],bag_after[30];
    uint32_t ability_ids[32];
    void (*remove_from_unit)(uint64_t,uint64_t);
    uint8_t (*add_to_unit)(uint64_t,uint64_t);
    uint64_t (*classic_item)(uint64_t,int32_t);
    uint64_t classic_inventory;
    uint8_t (*item_boolean)(uint64_t,uint32_t);
    void (*set_droppable)(uint64_t,int32_t);
    uint32_t droppable_before,droppable_after,rollback_verified,skip_code;
    uint64_t classic_before[6],classic_after[6];
} EquipmentEffectWork;
_Static_assert(sizeof(EquipmentEffectWork)==1648,"EquipmentEffectWork ABI");
__declspec(dllexport) const uint32_t equipment_effect_abi[3]={0x24268054u,216u,1648u};

static int EquipmentEffectSnapshot(EquipmentEffectWork *w,uint64_t *eq,uint64_t *bag){
    if(w->bag_size(w->target)!=30)return 0;
    for(int i=0;i<9;++i)eq[i]=w->equipped(w->target,w->slot_enum(i));
    for(int i=0;i<30;++i)bag[i]=w->bagged(w->target,i);
    return 1;
}

static void EquipmentClassicSnapshot(EquipmentEffectWork *w,uint64_t *slots){
    for(int i=0;i<6;++i)slots[i]=w->classic_item(w->target,i);
}

static int EquipmentEffectRestore(EquipmentEffectWork *w,uint64_t item){
    uint32_t equipped_count=0,bag_count=0,classic_count=0,equipped_slot=0;
    for(int i=0;i<9;++i)if(w->equipped(w->target,w->slot_enum(i))==w->item)
        {++equipped_count;equipped_slot=(uint32_t)i;}
    if(equipped_count>1)return 0;
    if(equipped_count && w->unequip(w->target,w->slot_enum(equipped_slot))!=w->item)return 0;
    for(int i=0;i<30;++i)if(w->bagged(w->target,i)==w->item)++bag_count;
    for(int i=0;i<6;++i)if(w->classic_item(w->target,i)==w->item)++classic_count;
    if(bag_count>1 || classic_count>1 || (bag_count && classic_count))return 0;
    if(!bag_count){
        /* Recover only an instance still owned by this unit. An unknown
           destination is quarantined rather than blindly re-added. */
        if(classic_count!=1 || w->item_id(w->item)!=w->rawcode)return 0;
        w->remove_from_unit(w->target,w->item);
        *(uint32_t *)(uintptr_t)(item+w->flag_offset)|=0x4000u;
        *(uint32_t *)(uintptr_t)(item+w->class_offset)=7;
        *(uint32_t *)(uintptr_t)(item+w->type_offset)=9;
        if(!w->add_to_unit(w->target,w->item))return 0;
    }
    *(uint32_t *)(uintptr_t)(item+w->flag_offset)=
        (*(uint32_t *)(uintptr_t)(item+w->flag_offset)&~0x4000u)|(w->flags_before&0x4000u);
    *(uint32_t *)(uintptr_t)(item+w->class_offset)=w->class_before;
    *(uint32_t *)(uintptr_t)(item+w->type_offset)=w->type_before;
    return 1;
}

__declspec(dllexport) uint64_t BridgeEquipmentEffectQuery(void){
    EquipmentEffectWork *w=(EquipmentEffectWork *)g_dispatch->work;
    uint32_t count,matches=0;uint64_t item_owner,unit_owner,item,unit,records;
    if(!w || w->expected_tls!=g_dispatch->tls_value || w->slot>=9 ||
       (w->action!=1 && w->action!=2 && w->action!=3) || w->reserved)return 0;
    count=(uint32_t)BridgeSelect();
    for(uint32_t i=0;i<count;++i)if(w->selection.rows[i].unit==w->target)++matches;
    if(w->selection.error || !w->selection.destroyed || matches!=1){w->error=380;return count;}
    __try {
        item_owner=BridgeEffectResolveObjectTable(w->base,w->item_full);
        unit_owner=BridgeEffectResolveObjectTable(w->base,w->unit_full);
        item=item_owner?*(uint64_t *)(uintptr_t)(item_owner+bridge_profile.owner_data):0;
        unit=unit_owner?*(uint64_t *)(uintptr_t)(unit_owner+bridge_profile.owner_data):0;
        if(!item || !unit || *(uint64_t *)(uintptr_t)(item+bridge_profile.object_handle)!=w->item_full ||
           *(uint32_t *)(uintptr_t)(item+bridge_profile.object_rawcode)!=w->rawcode ||
           *(uint32_t *)(uintptr_t)(item+w->mirror_offset)!=w->rawcode || w->item_id(w->item)!=w->rawcode ||
           *(uint64_t *)(uintptr_t)(w->equipment+w->ability_owner_offset)!=unit ||
           *(uint32_t *)(uintptr_t)(w->equipment+bridge_profile.object_rawcode)!=0x41457175u ||
           *(uint64_t *)(uintptr_t)(w->equipment+w->count_offset)!=9 ||
           *(uint64_t *)(uintptr_t)(w->equipment+w->capacity_offset)<9)
            {w->error=381;return count;}
        records=*(uint64_t *)(uintptr_t)(w->equipment+w->records_offset);
        if(!records || !EquipmentEffectSnapshot(w,w->eq_before,w->bag_before))
            {w->error=382;return count;}
        w->flags_before=*(uint32_t *)(uintptr_t)(item+w->flag_offset);
        w->class_before=*(uint32_t *)(uintptr_t)(item+w->class_offset);
        w->type_before=*(uint32_t *)(uintptr_t)(item+w->type_offset);
        if(w->flags_before!=w->expected_flags || w->class_before!=w->expected_class ||
           w->type_before!=w->expected_type){w->error=383;return count;}
        for(int i=0;i<32;++i){
            uint64_t ability=w->item_ability(w->item,i);
            if(!ability)break;
            w->ability_ids[w->ability_count++]=w->ability_id(ability);
        }
        if(w->ability_count==32 && w->item_ability(w->item,32)){w->error=384;return count;}
        EquipmentClassicSnapshot(w,w->classic_before);
        w->droppable_before=!!w->item_boolean(w->item,0x6964726fu);
        if(!w->droppable_before){
            /* Do not fire pickup/drop events for protected legacy items. */
            for(int i=0;i<9;++i)w->eq_after[i]=w->eq_before[i];
            for(int i=0;i<30;++i)w->bag_after[i]=w->bag_before[i];
            for(int i=0;i<6;++i)w->classic_after[i]=w->classic_before[i];
            w->flags_after=w->flags_before;w->class_after=w->class_before;
            w->type_after=w->type_before;w->droppable_after=w->droppable_before;
            w->skip_code=1;w->completed=1;return count;
        }
        __try {
        if(w->action==3){
            uint32_t occupied=0;
            if(w->slot>=6 || !w->remove_from_unit || !w->add_to_unit || !w->classic_item ||
               w->classic_item(w->target,(int32_t)w->slot)!=w->item)
                {w->error=392;return count;}
            uint64_t inventory=w->classic_inventory;
            if(!inventory || *(uint64_t *)(uintptr_t)(inventory+w->ability_owner_offset)!=unit ||
               *(uint64_t *)(uintptr_t)(inventory+w->count_offset)!=6 ||
               *(uint64_t *)(uintptr_t)(inventory+w->capacity_offset)!=6)
                {w->error=397;return count;}
            uint64_t classic_records=*(uint64_t *)(uintptr_t)(inventory+w->records_offset);
            if(!classic_records || *(uint64_t *)(uintptr_t)(classic_records+w->slot*12u)!=w->item_full)
                {w->error=398;return count;}
            for(int i=0;i<30;++i){if(w->bag_before[i]==w->item){w->error=393;return count;}
                if(w->bag_before[i])++occupied;}
            for(int i=0;i<9;++i)if(w->eq_before[i]==w->item){w->error=393;return count;}
            if(occupied==30){w->error=394;return count;}
            /* Remove classic-inventory passive effects through the engine,
               then classify only this newly created instance for native bag
               insertion. No template/global mutation and no duplicate create. */
            w->remove_from_unit(w->target,w->item);
            __try {
                *(uint32_t *)(uintptr_t)(item+w->flag_offset)|=0x4000u;
                *(uint32_t *)(uintptr_t)(item+w->class_offset)=7u;
                *(uint32_t *)(uintptr_t)(item+w->type_offset)=9u;
                if(!w->add_to_unit(w->target,w->item)){w->error=395;w->cleanup=1;}
            } __finally {
                *(uint32_t *)(uintptr_t)(item+w->flag_offset)=
                    (*(uint32_t *)(uintptr_t)(item+w->flag_offset)&~0x4000u)|(w->flags_before&0x4000u);
                *(uint32_t *)(uintptr_t)(item+w->class_offset)=w->class_before;
                *(uint32_t *)(uintptr_t)(item+w->type_offset)=w->type_before;
            }
            if(!w->error)w->changed=1;
        }else if(w->action==1){
            uint32_t found=0;
            for(int i=0;i<30;++i)if(w->bag_before[i]==w->item)++found;
            if(found!=1 || w->eq_before[w->slot]){w->error=385;return count;}
            static const uint32_t kinds[9]={1u,2u,3u,4u,5u,5u,6u,7u,8u};
            __try {
                *(uint32_t *)(uintptr_t)(item+w->flag_offset)=w->flags_before|0x4000u;
                *(uint32_t *)(uintptr_t)(item+w->class_offset)=7u;
                *(uint32_t *)(uintptr_t)(item+w->type_offset)=kinds[w->slot];
                if(!w->equip(w->target,w->item)){w->error=386;w->cleanup=1;}
                else {
                    uint32_t seen=0,source=0;
                    for(int i=0;i<9;++i)if(w->equipped(w->target,w->slot_enum(i))==w->item)
                        {++seen;source=(uint32_t)i;}
                    if(seen!=1){w->error=387;w->cleanup=1;}
                    else {
                        if(source!=w->slot){
                            uint8_t *from=(uint8_t *)(uintptr_t)(records+source*12u);
                            uint8_t *to=(uint8_t *)(uintptr_t)(records+w->slot*12u);
                            if(*(uint64_t *)from!=w->item_full || *(uint64_t *)to!=UINT64_MAX)
                                {w->error=388;w->cleanup=1;}
                            else {
                                *(uint64_t *)to=*(uint64_t *)from;
                                *(uint32_t *)(to+8)=*(uint32_t *)(from+8);
                                *(uint64_t *)from=UINT64_MAX;*(uint32_t *)(from+8)=0;
                            }
                        }
                        if(!w->error)w->changed=1;
                    }
                }
            } __finally { /* Transaction-wide restoration below owns rollback. */ }
        }else{
            uint32_t occupied=0;
            for(int i=0;i<30;++i)if(w->bag_before[i])++occupied;
            if(occupied==30 || w->eq_before[w->slot]!=w->item){w->error=389;return count;}
            if(w->unequip(w->target,w->slot_enum((int32_t)w->slot))!=w->item)
                {w->error=390;w->cleanup=1;return count;}
            *(uint32_t *)(uintptr_t)(item+w->flag_offset)&=~0x4000u;
            *(uint32_t *)(uintptr_t)(item+w->class_offset)=w->original_class;
            *(uint32_t *)(uintptr_t)(item+w->type_offset)=0;
            w->changed=1;
        }
        } __finally {
            if(w->error && w->action==1 && !w->changed){
                if(EquipmentEffectRestore(w,item)){
                    w->cleanup=0;w->rollback_verified=1;
                }else w->cleanup=1;
            }
            w->droppable_after=!!w->item_boolean(w->item,0x6964726fu);
            if(w->droppable_before!=w->droppable_after){w->error=400;w->cleanup=1;}
            EquipmentClassicSnapshot(w,w->classic_after);
            EquipmentEffectSnapshot(w,w->eq_after,w->bag_after);
            w->flags_after=*(uint32_t *)(uintptr_t)(item+w->flag_offset);
            w->class_after=*(uint32_t *)(uintptr_t)(item+w->class_offset);
            w->type_after=*(uint32_t *)(uintptr_t)(item+w->type_offset);
        }
        if(!EquipmentEffectSnapshot(w,w->eq_after,w->bag_after))
            {w->error=391;w->cleanup=1;return count;}
        if(w->action==3){
            for(int i=0;i<6;++i)if(w->classic_item(w->target,i)==w->item)
                {w->error=396;w->cleanup=1;return count;}
        }
        w->flags_after=*(uint32_t *)(uintptr_t)(item+w->flag_offset);
        w->class_after=*(uint32_t *)(uintptr_t)(item+w->class_offset);
        w->type_after=*(uint32_t *)(uintptr_t)(item+w->type_offset);
        w->actual_slot=w->slot;
        if(!w->error)w->completed=1;
    } __except(EXCEPTION_EXECUTE_HANDLER){w->error=GetExceptionCode();w->cleanup=1;}
    return count;
}
