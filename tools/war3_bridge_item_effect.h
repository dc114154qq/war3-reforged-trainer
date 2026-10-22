/* Bound item-ability fields. No template mutation, pickup, removal or item move. */
typedef struct ItemEffectAbility {uint64_t handle,full,data;uint32_t rawcode,effect_class;} ItemEffectAbility;
typedef struct ItemEffectWork {
    SelectionWork selection;
    AbilityFieldGetFn get_boolean_field,get_integer_field,get_real_field;
    AbilityLevelFieldGetFn get_boolean_level_field,get_integer_level_field,get_real_level_field;
    AbilityFieldScalarSetFn set_boolean_field,set_integer_field;
    AbilityFieldRealSetFn set_real_field;
    AbilityLevelFieldScalarSetFn set_boolean_level_field,set_integer_level_field;
    AbilityLevelFieldRealSetFn set_real_level_field;
    uint64_t (*in_slot)(uint64_t,int32_t),(*in_bag)(uint64_t,int32_t),(*equipped)(uint64_t,uint64_t),(*slot_enum)(int32_t);
    uint32_t (*item_type)(uint64_t);
    uint64_t (*ability_index)(uint64_t,int32_t);
    uint32_t (*ability_id)(uint64_t),(*handle_id)(uint64_t);
    void *expected_tls;
    uint64_t base,target,item,unit_full,item_full,container_full;
    uint32_t area,slot,index,level,action,field_count,expected_code,error,completed,changed,ability_count,effect_class;
    uint64_t expected_ability,expected_full,expected_data;
    uint32_t record_offset,record_stride,record_code,record_limit,expected_value,compare;
    AbilityFieldSpec fields[32];
    ItemEffectAbility abilities[32];
    uint32_t before[32],after[32];
} ItemEffectWork;
_Static_assert(sizeof(ItemEffectWork)==2584,"Item effect ABI");
__declspec(dllexport) const uint32_t item_effect_abi[3]={0x24268077u,216u,2584u};

static int ItemEffectIdentity(ItemEffectWork*w,uint64_t *item_object){
    uint64_t u=BridgeProfileResolveOwner(w->base,w->unit_full,1),i=BridgeProfileResolveOwner(w->base,w->item_full,1);
    uint64_t c=BridgeProfileResolveOwner(w->base,w->container_full,1);
    if(!u || !i || !c)return 0;
    uint64_t unit=*(uint64_t*)(uintptr_t)(u+bridge_profile.owner_data),item=*(uint64_t*)(uintptr_t)(i+bridge_profile.owner_data);
    uint64_t container=*(uint64_t*)(uintptr_t)(c+bridge_profile.owner_data);
    if(!unit || !item || !container || *(uint64_t*)(uintptr_t)(unit+bridge_profile.object_handle)!=w->unit_full ||
       *(uint64_t*)(uintptr_t)(item+bridge_profile.object_handle)!=w->item_full ||
       *(uint64_t*)(uintptr_t)(container+bridge_profile.ability_owner)!=unit)return 0;
    uint32_t size=w->area==0?6u:w->area==1?30u:9u;
    if(*(uint64_t*)(uintptr_t)(container+bridge_profile.equipment_count)!=size ||
       *(uint64_t*)(uintptr_t)(container+bridge_profile.equipment_capacity)<size)return 0;
    uint64_t records=*(uint64_t*)(uintptr_t)(container+bridge_profile.equipment_records);
    if(!records || *(uint64_t*)(uintptr_t)(records+w->slot*bridge_profile.equipment_record_stride)!=w->item_full)return 0;
    uint64_t native=w->area==0?w->in_slot(w->target,(int32_t)w->slot):w->area==1?w->in_bag(w->target,(int32_t)w->slot):w->equipped(w->target,w->slot_enum((int32_t)w->slot));
    uint32_t raw=*(uint32_t*)(uintptr_t)(item+bridge_profile.object_rawcode);
    if(native!=w->item || !raw || raw!=*(uint32_t*)(uintptr_t)(item+bridge_profile.item_rawcode_mirror) || w->item_type(native)!=raw)return 0;
    *item_object=item;return 1;
}
static int ItemEffectEnumerate(ItemEffectWork*w){
    w->ability_count=0;
    for(uint32_t n=0;n<32;++n){
        uint64_t ability=w->ability_index(w->item,(int32_t)n);if(!ability)return 1;
        uint32_t raw=w->ability_id(ability);
        uint64_t item_owner=BridgeProfileResolveOwner(w->base,w->item_full,1);
        if(!raw || !item_owner || n>=w->record_limit)return 0;
        uint64_t item=*(uint64_t*)(uintptr_t)(item_owner+bridge_profile.owner_data);
        uint64_t record=item+w->record_offset+n*w->record_stride;
        uint64_t bound=*(uint64_t*)(uintptr_t)record;
        if(!bound || bound==~0ull || *(uint32_t*)(uintptr_t)(record+w->record_code)!=raw)return 0;
        uint64_t wrapper=BridgeProfileResolveOwner(w->base,bound,1);
        if(!wrapper)return 0;
        uint64_t data=*(uint64_t*)(uintptr_t)(wrapper+bridge_profile.owner_data);
        uint64_t full=*(uint64_t*)(uintptr_t)(wrapper+bridge_profile.owner_handle);
        uint32_t effect=(uint32_t)(*(uint64_t*)(uintptr_t)(wrapper+bridge_profile.component_tag)>>32);
        if(!data || !full || !effect || BridgeProfileResolveOwner(w->base,full,1)!=wrapper ||
           *(uint64_t*)(uintptr_t)(data+bridge_profile.ability_handle)!=full ||
           *(uint32_t*)(uintptr_t)(data+bridge_profile.ability_rawcode)!=raw ||
           *(uint32_t*)(uintptr_t)(data+bridge_profile.ability_mirror_rawcode)!=raw ||
           (*(uint32_t*)(uintptr_t)(data+bridge_profile.ability_flags)&8u))return 0;
        for(uint32_t j=0;j<n;++j)if(w->abilities[j].handle==ability || w->abilities[j].full==full || w->abilities[j].data==data)return 0;
        w->abilities[n]=(ItemEffectAbility){ability,full,data,raw,effect};++w->ability_count;
    }
    return !w->ability_index(w->item,32);
}
static int ItemEffectBound(ItemEffectWork*w,ItemEffectAbility*a){
    uint64_t item=0;if(!ItemEffectIdentity(w,&item) || w->ability_index(w->item,(int32_t)w->index)!=a->handle)return 0;
    uint64_t record=item+w->record_offset+w->index*w->record_stride;
    if(*(uint64_t*)(uintptr_t)record!=a->full || *(uint32_t*)(uintptr_t)(record+w->record_code)!=a->rawcode)return 0;
    uint64_t wrapper=BridgeProfileResolveOwner(w->base,a->full,1);
    return wrapper && *(uint64_t*)(uintptr_t)(wrapper+bridge_profile.owner_data)==a->data &&
        (uint32_t)(*(uint64_t*)(uintptr_t)(wrapper+bridge_profile.component_tag)>>32)==a->effect_class &&
        *(uint64_t*)(uintptr_t)(a->data+bridge_profile.ability_handle)==a->full &&
        !(*(uint32_t*)(uintptr_t)(a->data+bridge_profile.ability_flags)&8u);
}
static uint32_t ItemEffectRead(ItemEffectWork*w,uint64_t ability,AbilityFieldSpec*f){
    int32_t level=(int32_t)w->level-1;
    if(!f->scope){
        if(f->kind==0)return (uint32_t)w->get_boolean_field(ability,f->field_id);
        if(f->kind==1)return (uint32_t)w->get_integer_field(ability,f->field_id);
        return (uint32_t)w->get_real_field(ability,f->field_id);
    }
    if(f->kind==0)return (uint32_t)w->get_boolean_level_field(ability,f->field_id,level);
    if(f->kind==1)return (uint32_t)w->get_integer_level_field(ability,f->field_id,level);
    return (uint32_t)w->get_real_level_field(ability,f->field_id,level);
}
static uint32_t ItemEffectWrite(ItemEffectWork*w,uint64_t ability,AbilityFieldSpec*f,uint32_t value){
    int32_t level=(int32_t)w->level-1;
    if(f->kind==2){
        union{uint32_t bits;float real;} v;v.bits=value;
        return f->scope?w->set_real_level_field(ability,f->field_id,level,&v.real):w->set_real_field(ability,f->field_id,&v.real);
    }
    if(!f->scope)return f->kind==0?w->set_boolean_field(ability,f->field_id,value&1u):w->set_integer_field(ability,f->field_id,value);
    return f->kind==0?w->set_boolean_level_field(ability,f->field_id,level,value&1u):w->set_integer_level_field(ability,f->field_id,level,value);
}
__declspec(dllexport) uint64_t BridgeItemEffectQuery(void){
    ItemEffectWork*w=(ItemEffectWork*)g_dispatch->work;uint32_t count=0;uint64_t item_object=0;
    if(!w || w->expected_tls!=g_dispatch->tls_value || w->area>2 || w->slot>=(w->area==0?6u:w->area==1?30u:9u) ||
       !w->level || w->level>1000 || w->action>1 || w->field_count>32 || (w->action && w->field_count!=1))return 0;
    if(!w->record_offset || w->record_offset>0xffffu || w->record_stride<12u || w->record_stride>4096u ||
       w->record_code<8u || w->record_code+4u>w->record_stride || !w->record_limit || w->record_limit>128u)return 0;
    count=(uint32_t)BridgeSelect();uint32_t selected=0;
    for(uint32_t n=0;n<count;++n)if(w->selection.rows[n].unit==w->target)++selected;
    if(w->selection.error || !w->selection.destroyed || selected!=1){w->error=470;return count;}
    __try {
        if(!ItemEffectIdentity(w,&item_object)){w->error=471;return count;}
        if(!ItemEffectEnumerate(w)){w->error=472;return count;}
        if(!w->field_count){w->completed=1;return count;}
        if(w->index>=w->ability_count){w->error=473;return count;}
        ItemEffectAbility*a=&w->abilities[w->index];
        if(a->handle!=w->expected_ability || a->full!=w->expected_full || a->data!=w->expected_data || a->rawcode!=w->expected_code){w->error=474;return count;}
        w->effect_class=a->effect_class;
        for(uint32_t n=0;n<w->field_count;++n){
            if(!w->fields[n].field_id || w->fields[n].kind>2 || w->fields[n].scope>1){w->error=475;return count;}
            w->before[n]=ItemEffectRead(w,a->handle,&w->fields[n]);w->after[n]=w->before[n];
        }
        if(w->action && (!w->compare || w->before[0]!=w->expected_value)){w->error=479;return count;}
        if(w->action){
            volatile int accepted=0;w->changed=2;
            __try {
                if(!ItemEffectWrite(w,a->handle,&w->fields[0],w->fields[0].target)){w->error=476;}
                else {
                    w->after[0]=ItemEffectRead(w,a->handle,&w->fields[0]);
                    if(w->after[0]!=w->fields[0].target)w->error=477;
                    else if(!ItemEffectBound(w,a))w->error=478;
                    else {accepted=1;w->changed=1;}
                }
            } __finally {
                if(!accepted){
                    if(ItemEffectBound(w,a)){
                        uint32_t current=ItemEffectRead(w,a->handle,&w->fields[0]);
                        if(current!=w->before[0]){
                            ItemEffectWrite(w,a->handle,&w->fields[0],w->before[0]);
                            current=ItemEffectRead(w,a->handle,&w->fields[0]);
                        }
                        w->after[0]=current;
                        if(current==w->before[0] && ItemEffectBound(w,a))w->changed=0;
                    }
                }
            }
            if(w->error)return count;
        }
        if(!ItemEffectIdentity(w,&item_object)){w->error=478;return count;}
        w->completed=1;
    } __except(EXCEPTION_EXECUTE_HANDLER){w->error=GetExceptionCode();}
    return count;
}
