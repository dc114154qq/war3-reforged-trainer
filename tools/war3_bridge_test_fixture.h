/* Compiled only with BRIDGE_TEST; never included in the product DLL. */
static int fixture_count,fixture_index,fixture_scenario,fixture_writes,fixture_type_calls;
static int32_t fixture_levels[24];
static uint64_t fixture_player(void) {return 0x100008;}
static uint64_t fixture_group(void) {return fixture_scenario==3 ? 0 : 0x100900;}
static void fixture_enum(uint64_t g,uint64_t p,uint64_t f) {(void)g;(void)p;(void)f;fixture_index=0;}
static uint64_t fixture_first(uint64_t g) {(void)g;return fixture_index<fixture_count ? 0x100000+fixture_index : 0;}
static void fixture_remove(uint64_t g,uint64_t u) {(void)g;(void)u;++fixture_index;}
static void fixture_destroy(uint64_t g) {(void)g;}
static uint32_t fixture_type(uint64_t u) {
    ++fixture_type_calls;
    if (fixture_scenario==2 && fixture_type_calls>fixture_count) return 0;
    return fixture_levels[u-0x100000]>0 ? 0x4870616c : 0x68666f6f;
}
static int32_t fixture_level(uint64_t u) {return fixture_levels[u-0x100000];}
static void fixture_set(uint64_t u,int32_t value,uint32_t eye) {
    (void)eye;++fixture_writes;if (fixture_scenario!=1) fixture_levels[u-0x100000]=value;
}
__declspec(dllexport) uint64_t BridgeTestRun(HeroWork *w,int count,int scenario) {
    static BridgeCommand cmd;
    int i;
    if (count<0 || count>24) return 0;
    fixture_count=count;fixture_scenario=scenario;fixture_writes=0;fixture_type_calls=0;
    for (i=0;i<24;++i) fixture_levels[i]=(scenario!=4 && i%3==0) ? 1 : 0;
    cmd.work=w;cmd.tls_value=w->expected_tls;g_dispatch=&cmd;
    w->selection.local_player=fixture_player;w->selection.create_group=fixture_group;
    w->selection.enum_selected=fixture_enum;w->selection.first_of_group=fixture_first;
    w->selection.remove_from_group=fixture_remove;w->selection.destroy_group=fixture_destroy;
    w->selection.unit_type_id=fixture_type;w->selection.hero_level=fixture_level;w->set_level=fixture_set;
    return BridgeHeroQuery();
}
__declspec(dllexport) int BridgeTestWrites(void) {return fixture_writes;}

static int32_t ability_levels[24];
static int ability_scenario,ability_adds,ability_removes,ability_sets;
static uint8_t fixture_ability_add(uint64_t u,uint32_t id) {
    (void)id;++ability_adds;
    if (ability_scenario==1) return 0;
    ability_levels[u-0x100000]=1;return 1;
}
static uint8_t fixture_ability_remove(uint64_t u,uint32_t id) {
    (void)id;++ability_removes;
    if (ability_scenario==3) return 0;
    ability_levels[u-0x100000]=0;return 1;
}
static int32_t fixture_ability_set(uint64_t u,uint32_t id,int32_t level) {
    (void)id;++ability_sets;
    if (ability_scenario==2) return ability_levels[u-0x100000];
    ability_levels[u-0x100000]=level;return level;
}
static int32_t fixture_ability_get(uint64_t u,uint32_t id) {(void)id;return ability_levels[u-0x100000];}
__declspec(dllexport) uint64_t BridgeAbilityTestRun(AbilityWork *w,int count,int scenario,int initial) {
    static BridgeCommand cmd;
    int i;
    if (count<0 || count>24) return 0;
    fixture_count=count;fixture_scenario=scenario==6 ? 2 : 0;fixture_type_calls=0;
    ability_scenario=scenario;ability_adds=ability_removes=ability_sets=0;
    for (i=0;i<24;++i) {fixture_levels[i]=i%3==0 ? 1 : 0;ability_levels[i]=scenario==5 ? (i%3==0 ? 1 : 0) : initial;}
    cmd.work=w;cmd.tls_value=w->expected_tls;g_dispatch=&cmd;
    w->selection.local_player=fixture_player;w->selection.create_group=fixture_group;
    w->selection.enum_selected=fixture_enum;w->selection.first_of_group=fixture_first;
    w->selection.remove_from_group=fixture_remove;w->selection.destroy_group=fixture_destroy;
    w->selection.unit_type_id=fixture_type;w->selection.hero_level=fixture_level;
    w->add=fixture_ability_add;w->remove=fixture_ability_remove;w->set_level=fixture_ability_set;w->get_level=fixture_ability_get;
    return BridgeAbilityQuery();
}
__declspec(dllexport) int BridgeAbilityTestStat(int kind) {return kind==0 ? ability_adds : kind==1 ? ability_removes : ability_sets;}

__declspec(dllexport) int BridgeTestKnownAbilityTail(uint64_t handler,uint32_t code,uint32_t flags,
    uint32_t parameters,uint64_t instruction,uint64_t access,uint64_t address,uint64_t r15) {
    return BridgeKnownAbilityTail(handler,code,flags,parameters,instruction,access,address,r15);
}

__declspec(dllexport) int32_t BridgeTestTailReadback(int32_t actual,int32_t target) {
    return BridgeAcceptAbilityTailReadback(actual,target);
}

static uint64_t item_slots[24][6];
static int item_sizes[24],item_case,item_create_calls,item_set_calls,item_remove_calls;
static int32_t item_original_charges[24][6],item_new_charges[24];
static uint32_t item_new_type[24];
static int fixture_item_index(uint64_t h) {return (int)((h-0x300000)/16);}
static uint64_t fixture_item_slot(uint64_t u,int32_t slot) {
    int i=(int)(u-0x100000);return slot>=0 && slot<item_sizes[i] ? item_slots[i][slot] : 0;
}
static int32_t fixture_item_size(uint64_t u) {return item_sizes[u-0x100000];}
static uint32_t fixture_item_type(uint64_t h) {
    if (h>=0x300000 && h<0x300180) return item_new_type[fixture_item_index(h)];
    return h>=0x200000 && h<0x200180 ? 0x73747770 : 0;
}
static int32_t fixture_item_charges(uint64_t h) {
    if (h>=0x300000) return item_new_charges[fixture_item_index(h)];
    return item_original_charges[(h-0x200000)/16][(h-0x200000)%16];
}
static void fixture_item_set(uint64_t h,int32_t value) {
    ++item_set_calls;if(item_case==2)return;
    if(h>=0x300000)item_new_charges[fixture_item_index(h)]=value;
    else item_original_charges[(h-0x200000)/16][(h-0x200000)%16]=value;
}
static uint64_t fixture_item_create(uint64_t u,uint32_t type) {
    int i=(int)(u-0x100000),j;uint64_t h=0x300000+i*16;
    ++item_create_calls;if(item_case==1)return 0;
    if(item_case==6)return item_slots[i][0];
    item_new_type[i]=item_case==3 ? 0x62616421 : type;item_new_charges[i]=1;
    for(j=0;j<item_sizes[i];++j)if(!item_slots[i][j]){item_slots[i][j]=h;break;}
    return h;
}
static void fixture_item_detach(uint64_t u,uint64_t h) {
    int i=(int)(u-0x100000),j;for(j=0;j<6;++j)if(item_slots[i][j]==h)item_slots[i][j]=0;
}
static void fixture_item_remove(uint64_t h) {
    ++item_remove_calls;if(item_case!=4)item_new_type[fixture_item_index(h)]=0;
}
__declspec(dllexport) uint64_t BridgeItemTestRun(ItemWork *w,int count,int scenario) {
    static BridgeCommand cmd;int i,j;
    if(count<0||count>24)return 0;
    fixture_count=count;fixture_scenario=0;fixture_type_calls=0;item_case=scenario;
    item_create_calls=item_set_calls=item_remove_calls=0;
    for(i=0;i<24;++i){
        fixture_levels[i]=i%3==0 ? 1 : 0;item_sizes[i]=scenario==5 ? 6 : i%3==0 ? 6 : 0;
        item_new_type[i]=0;item_new_charges[i]=0;
        for(j=0;j<6;++j){item_original_charges[i][j]=1;item_slots[i][j]=item_sizes[i] && (j==0||scenario==5) ? 0x200000+i*16+j : 0;}
    }
    cmd.work=w;cmd.tls_value=w->expected_tls;g_dispatch=&cmd;
    w->selection.local_player=fixture_player;w->selection.create_group=fixture_group;
    w->selection.enum_selected=fixture_enum;w->selection.first_of_group=fixture_first;
    w->selection.remove_from_group=fixture_remove;w->selection.destroy_group=fixture_destroy;
    w->selection.unit_type_id=fixture_type;w->selection.hero_level=fixture_level;
    w->create=fixture_item_create;w->in_slot=fixture_item_slot;w->size=fixture_item_size;
    w->type=fixture_item_type;w->charges=fixture_item_charges;w->set_charges=fixture_item_set;
    w->remove=fixture_item_remove;w->detach=fixture_item_detach;
    return BridgeItemQuery();
}
__declspec(dllexport) int BridgeItemTestStat(int kind) {return kind==0 ? item_create_calls : kind==1 ? item_set_calls : item_remove_calls;}
