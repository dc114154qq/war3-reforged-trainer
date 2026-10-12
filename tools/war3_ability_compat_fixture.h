/* Isolated production-C tests. None of these exports enters a game process. */
static uint8_t compat_unit[2048],compat_ability[4096],compat_owner[512],compat_wrapper[512],compat_item[4096],compat_item_owner[512],compat_root[256],compat_table[64];
static uint64_t compat_root_pointer;
static uint32_t compat_code,compat_case,compat_order;
static int32_t compat_level,compat_cost;
static uint32_t compat_area,compat_cooldown_field,compat_remaining;
static uint32_t compat_adds,compat_sets,compat_removes,compat_orders,compat_timer_destroys;
static uint8_t compat_present,compat_timer;
static uint32_t compat_elapsed;
static uint32_t CompatBits(float value){union{float value;uint32_t bits;}v;v.value=value;return v.bits;}
static void CompatObjects(uint32_t unit_rawcode,uint32_t item_rawcode) {
    memset(compat_unit,0,sizeof(compat_unit));memset(compat_ability,0,sizeof(compat_ability));
    memset(compat_owner,0,sizeof(compat_owner));memset(compat_wrapper,0,sizeof(compat_wrapper));
    memset(compat_item,0,sizeof(compat_item));memset(compat_item_owner,0,sizeof(compat_item_owner));
    memset(compat_root,0,sizeof(compat_root));memset(compat_table,0,sizeof(compat_table));
    uint64_t unit=(uint64_t)(uintptr_t)compat_unit,ability=(uint64_t)(uintptr_t)compat_ability;
    uint64_t owner=(uint64_t)(uintptr_t)compat_owner,wrapper=(uint64_t)(uintptr_t)compat_wrapper;
    *(uint64_t*)(compat_unit+0x18)=0xabcd00000001ULL;*(uint32_t*)(compat_unit+0x70)=unit_rawcode;
    *(uint64_t*)(compat_owner+0x20)=0xabcd00000001ULL;*(uint64_t*)(compat_owner+0x90)=unit;
    *(uint64_t*)(compat_owner+0xd8)=wrapper+0x38;
    *(uint64_t*)(compat_wrapper+0x38)=owner+0xd0;*(uint64_t*)(compat_wrapper+0x40)=0;
    *(uint64_t*)(compat_wrapper+0x50)=owner;*(uint64_t*)(compat_wrapper+0x90)=ability;
    *(uint64_t*)(compat_ability+0x18)=0x987600000003ULL;
    *(uint64_t*)(compat_ability+0x68)=unit;
    *(uint32_t*)(compat_ability+0x70)=compat_code;*(uint32_t*)(compat_ability+0x78)=compat_code;
    *(uint64_t*)(compat_item+0x18)=0xdcba00000002ULL;
    *(uint32_t*)(compat_item+0x70)=item_rawcode;*(uint32_t*)(compat_item+0x178)=item_rawcode;
    *(uint64_t*)(compat_item_owner+0x20)=0xdcba00000002ULL;
    *(uint64_t*)(compat_item_owner+0x90)=(uint64_t)(uintptr_t)compat_item;
    *(uint64_t*)(compat_root+0x18)=(uint64_t)(uintptr_t)compat_table;*(uint32_t*)(compat_root+0x30)=4;
    *(uint32_t*)(compat_table+16)=0xfffffffeu;*(uint64_t*)(compat_table+24)=owner;
    *(uint32_t*)(compat_table+32)=0xfffffffeu;*(uint64_t*)(compat_table+40)=(uint64_t)(uintptr_t)compat_item_owner;
    compat_root_pointer=(uint64_t)(uintptr_t)compat_root;
}
static uint64_t CompatBase(void){return (uint64_t)(uintptr_t)&compat_root_pointer-bridge_profile.registry_root_rva;}
static uint64_t CompatResolveUnit(uint64_t unit){return unit==0x100000?(uint64_t)(uintptr_t)compat_unit:0;}
static uint64_t CompatAbility(uint64_t unit,uint32_t code){return unit==0x100000 && code==compat_code && compat_present?0x700000:0;}
static uint64_t CompatAbilityIndex(uint64_t unit,int32_t index){return unit==0x100000 && index==0 && compat_present?0x700000:0;}
static uint32_t CompatAbilityId(uint64_t ability){(void)ability;return compat_code;}
static uint8_t CompatAdd(uint64_t unit,uint32_t code){
    (void)unit;(void)code;++compat_adds;
    if(compat_case==2)return 0;
    compat_present=1;compat_level=compat_case==16?0:1;return compat_case==3?0:1;
}
static uint8_t CompatRemove(uint64_t unit,uint32_t code){(void)unit;(void)code;++compat_removes;compat_present=0;compat_level=0;return 1;}
static int32_t CompatGetLevel(uint64_t unit,uint32_t code){(void)unit;(void)code;return compat_level;}
static int32_t CompatSetLevel(uint64_t unit,uint32_t code,int32_t level){
    (void)unit;(void)code;++compat_sets;compat_level=level;
    if(compat_case==16)return *(volatile int32_t*)(uintptr_t)0x108;
    return level;
}
static uint64_t CompatGetReal(uint64_t ability,uint32_t field,int32_t index){
    (void)ability;(void)index;return field==0x61617265u?compat_area:compat_cooldown_field;
}
static uint8_t CompatSetReal(uint64_t ability,uint32_t field,int32_t index,float *value){
    (void)ability;(void)index;uint32_t bits=CompatBits(*value);
    if(field==0x61617265u)compat_area=bits;else compat_cooldown_field=bits;
    return 1;
}
static int32_t CompatGetCost(uint64_t ability,uint32_t field,int32_t index){(void)ability;(void)field;(void)index;return compat_cost;}
static uint8_t CompatSetCost(uint64_t ability,uint32_t field,int32_t index,int32_t value){
    (void)ability;(void)field;(void)index;
    if((compat_case==6 && value==0) || (compat_case==9 && value==300))return 0;
    compat_cost=value;return 1;
}
static uint64_t CompatOwner(uint64_t unit){(void)unit;return fixture_player();}
static uint32_t CompatLife(uint64_t unit){(void)unit;return CompatBits(100.0f);}
static uint32_t CompatMana(uint64_t unit,uint64_t state){(void)unit;(void)state;return CompatBits(0.0f);}
static uint32_t CompatRemaining(uint64_t unit,uint32_t code){(void)unit;(void)code;return compat_remaining;}
static uint32_t CompatOrder(uint64_t unit){(void)unit;return compat_order;}
static uint32_t CompatXY(uint64_t unit){(void)unit;return CompatBits(0.0f);}
static uint8_t CompatIssue(uint64_t unit,uint32_t order) {
    (void)unit;
    if(order==851972u){compat_order=0;return 1;}
    if(compat_case==7 || !compat_present || compat_level<1 || compat_cost || compat_remaining || compat_cooldown_field)return 0;
    compat_order=order;++compat_orders;return 1;
}
static uint8_t CompatPoint(uint64_t unit,uint32_t order,float*x,float*y){(void)x;(void)y;return CompatIssue(unit,order);}
static void CompatEndCooldown(uint64_t unit,uint32_t code){(void)unit;(void)code;compat_remaining=0;}
static void CompatStartCooldown(uint64_t unit,uint32_t code,float*value){(void)unit;(void)code;compat_remaining=CompatBits(*value);}
static uint64_t CompatCreateTimer(void){compat_timer=1;return 0x800000;}
static void CompatTimerStart(uint64_t timer,float*duration,uint32_t periodic,uint64_t callback){(void)timer;(void)duration;(void)periodic;(void)callback;}
static uint32_t CompatTimerElapsed(uint64_t timer){(void)timer;return compat_elapsed;}
static void CompatTimerDestroy(uint64_t timer){(void)timer;compat_timer=0;++compat_timer_destroys;}
static void CompatSelection(SelectionWork*w) {
    w->local_player=fixture_player;w->create_group=fixture_group;w->enum_selected=fixture_enum;
    w->first_of_group=fixture_first;w->remove_from_group=fixture_remove;w->destroy_group=fixture_destroy;
    w->unit_type_id=fixture_type;w->hero_level=fixture_level;
    fixture_count=1;fixture_scenario=0;fixture_type_calls=0;fixture_levels[0]=1;
}
__declspec(dllexport) uint64_t BridgeCompatCastTestRun(DirectCastWork*d,uint32_t scenario,uint32_t elapsed_bits) {
    static BridgeCommand cmd;WorldCastWork*w=&d->cast;
    compat_case=scenario;compat_elapsed=elapsed_bits;
    if(w->action==1){
        compat_code=w->rawcode;
        compat_present=scenario==1 || scenario==4 || scenario==10;
        compat_level=scenario==4?0:compat_present?2:0;
        compat_area=CompatBits(900.0f);compat_cost=300;compat_cooldown_field=CompatBits(100.0f);
        compat_remaining=CompatBits(scenario==10?20.0f:0.0f);compat_order=987654;
        compat_adds=compat_sets=compat_removes=compat_orders=compat_timer_destroys=0;compat_timer=0;
        CompatObjects(0x4870616cu,0x65626867u);CompatSelection(&w->selection);
    }else if(scenario==5)*(uint64_t*)(compat_ability+0x18)^=0x100000000ULL;
    cmd.work=d;cmd.tls_value=w->expected_tls;g_dispatch=&cmd;
    cmd.specific_handler=(void*)GetProcAddress(GetModuleHandleW(L"ntdll.dll"),"__C_specific_handler");
    d->module_base=CompatBase();d->resolve_unit=CompatResolveUnit;d->get_level=(uint32_t(*)(uint64_t,uint32_t))CompatGetLevel;
    d->set_level=CompatSetLevel;d->get_cost=CompatGetCost;d->set_cost=CompatSetCost;
    d->end_cooldown=CompatEndCooldown;d->start_cooldown=CompatStartCooldown;
    d->create_timer=CompatCreateTimer;d->timer_start=CompatTimerStart;d->timer_elapsed=CompatTimerElapsed;d->destroy_timer=CompatTimerDestroy;
    d->ability_index=CompatAbilityIndex;
    w->get_ability=CompatAbility;w->get_ability_id=CompatAbilityId;w->add_ability=CompatAdd;w->remove_ability=CompatRemove;
    w->get_area=CompatGetReal;w->set_area=CompatSetReal;w->issue_immediate=CompatIssue;w->issue_point=CompatPoint;
    w->get_owner=CompatOwner;w->get_life=CompatLife;w->get_mana=CompatMana;w->get_cooldown=CompatRemaining;
    w->get_order=CompatOrder;w->get_x=w->get_y=CompatXY;
    return BridgeDirectCastQuery();
}
__declspec(dllexport) uint32_t BridgeCompatCastTestStat(uint32_t key) {
    switch(key){
        case 0:return compat_adds;case 1:return compat_sets;case 2:return compat_removes;case 3:return compat_orders;
        case 4:return compat_area;case 5:return (uint32_t)compat_cost;case 6:return compat_cooldown_field;
        case 7:return compat_remaining;case 8:return compat_level;case 9:return compat_present;
        case 10:return compat_timer_destroys;case 11:return compat_timer;default:return 0;
    }
}
static uint64_t compat_item_handles[32],compat_classic[6];
static uint32_t compat_item_ids[32],compat_item_count,compat_item_adds,compat_item_code,compat_item_ability_code;
static uint64_t CompatItemSlot(uint64_t unit,int32_t slot){(void)unit;return slot>=0 && slot<6?compat_classic[slot]:0;}
static uint32_t CompatItemType(uint64_t item){return item==0x500000?compat_item_code:0x73747770u;}
static int32_t CompatItemCharges(uint64_t item){(void)item;return 1;}
static uint64_t CompatItemAbility(uint64_t item,uint32_t code){
    (void)item;
    if(compat_case==7 || compat_case==8 || compat_case==12)return 0;
    for(uint32_t i=0;i<compat_item_count;++i)if(compat_item_ids[i]==code)
        return compat_case==11?0x720000:compat_item_handles[i];
    return 0;
}
static uint64_t CompatItemAbilityIndex(uint64_t item,int32_t index){(void)item;return index>=0 && (uint32_t)index<compat_item_count?compat_item_handles[index]:0;}
static uint32_t CompatItemAbilityId(uint64_t ability){
    if(compat_case==11 && ability==0x720000)return compat_item_ability_code;
    for(uint32_t i=0;i<compat_item_count;++i)if(compat_item_handles[i]==ability)return compat_item_ids[i];
    return 0;
}
static uint8_t CompatItemAdd(uint64_t item,uint32_t code) {
    (void)item;++compat_item_adds;if(compat_case==1)return 0;
    compat_item_handles[compat_item_count]=0x710000+compat_item_count*16;compat_item_ids[compat_item_count++]=code;
    if(compat_case==3)compat_classic[1]=0;
    if(compat_case==4)compat_item_handles[0]=0x720000;
    return compat_case==6 || compat_case==12?0:1;
}
__declspec(dllexport) uint64_t BridgeCompatItemAbilityTestRun(ItemAbilityWork*w,uint32_t scenario) {
    static BridgeCommand cmd;
    compat_case=scenario;compat_item_code=w->rawcode;compat_item_ability_code=w->ability_rawcode;
    compat_code=0x41457175u;compat_item_adds=0;
    CompatObjects(0x4870616cu,w->rawcode);CompatSelection(&w->selection);
    compat_item_count=1;
    compat_item_ids[0]=(scenario==2 || scenario==7 || scenario==9 || scenario==10 || scenario==11)?
        w->ability_rawcode:0x41457175u;
    compat_item_handles[0]=0x710000;
    if(scenario==9 || scenario==10 || scenario==11){
        compat_item_count=2;compat_item_ids[1]=w->ability_rawcode;
        compat_item_handles[1]=scenario==10?0x710000:0x710010;
        if(scenario==11)compat_item_ids[0]=0x41457175u;
    }
    for(int i=0;i<6;++i)compat_classic[i]=i==0?0x500000:i==1?0x500010:0;
    cmd.work=w;cmd.tls_value=w->expected_tls;g_dispatch=&cmd;
    w->target=0x100000;w->item=0x500000;w->base=CompatBase();w->unit_full=0xabcd00000001ULL;w->item_full=0xdcba00000002ULL;
    w->in_slot=CompatItemSlot;w->item_type=CompatItemType;w->charges=CompatItemCharges;
    w->ability=CompatItemAbility;w->ability_index=CompatItemAbilityIndex;w->ability_id=CompatItemAbilityId;w->add=CompatItemAdd;
    return BridgeItemAbilityQuery();
}
__declspec(dllexport) uint32_t BridgeCompatItemAbilityTestStat(void){return compat_item_adds;}
