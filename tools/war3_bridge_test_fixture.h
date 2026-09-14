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
