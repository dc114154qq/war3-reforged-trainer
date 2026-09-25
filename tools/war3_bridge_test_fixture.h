/* Compiled only with BRIDGE_TEST; never included in the product DLL. */
#include "war3_talent_icon_predicate.h"
__declspec(dllexport) uint32_t BridgeTalentIconPredicateTest(uint32_t scenario){
    uint64_t owner_buffer[32]={0},unit_buffer[32]={0};
    uint64_t wrappers[2][32]={0},abilities[2][32]={0};
    uint64_t owner=(uint64_t)(uintptr_t)owner_buffer,unit=(uint64_t)(uintptr_t)unit_buffer;
    uint32_t choice=0x55543161u; /* UT1a */
    owner_buffer[0x90/8]=unit;owner_buffer[0x20/8]=0x123400001234ull;
    unit_buffer[0x18/8]=owner_buffer[0x20/8];
    owner_buffer[0xd8/8]=(uint64_t)(uintptr_t)wrappers[0]+0x38;
    for(uint32_t index=0;index<2;++index){
        uint64_t wrapper=(uint64_t)(uintptr_t)wrappers[index];
        uint64_t data=(uint64_t)(uintptr_t)abilities[index];
        wrappers[index][0x38/8]=index?(uint64_t)(uintptr_t)wrappers[0]+0x38:owner+0xd0;
        wrappers[index][0x40/8]=index?0:(uint64_t)(uintptr_t)wrappers[1]+0x38;
        wrappers[index][0x50/8]=owner;wrappers[index][0x90/8]=data;
        wrappers[index][0x20/8]=0x223400002234ull+index;
        abilities[index][0x18/8]=wrappers[index][0x20/8];
        abilities[index][0x68/8]=unit;
        *(uint32_t *)(uintptr_t)(data+0x70)=choice;
        *(uint32_t *)(uintptr_t)(data+0x78)=choice;
        *(uint32_t *)(uintptr_t)(data+0x38)=index?0x06000010u:0x18u;
    }
    /* A retired node before a live node must not hide the learned choice. */
    if(scenario==0)return TalentIconShouldEnable(0,owner,unit,choice)?0:1;
    if(scenario==1)return TalentIconShouldEnable(0,owner,unit,choice+1)?2:0;
    if(scenario==2){abilities[1][0x38/8]|=8;return TalentIconShouldEnable(0,owner,unit,choice)?3:0;}
    if(scenario==3){wrappers[1][0x50/8]=owner+8;return TalentIconShouldEnable(0,owner,unit,choice)?4:0;}
    if(scenario==4){unit_buffer[0x18/8]++;return TalentIconShouldEnable(0,owner,unit,choice)?5:0;}
    if(scenario==5)return TalentIconShouldEnable(1,0,0,choice)?0:6;
    if(scenario==6){wrappers[1][0x40/8]=(uint64_t)(uintptr_t)wrappers[0]+0x38;return TalentIconShouldEnable(0,owner,unit,choice)?7:0;}
    if(scenario==7){wrappers[1][0x20/8]++;return TalentIconShouldEnable(0,owner,unit,choice)?8:0;}
    return 99;
}
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
static uint8_t fixture_strip(uint64_t u,int32_t delta) {
    ++fixture_writes;
    if (fixture_scenario==1 || delta<0 || fixture_levels[u-0x100000]<delta) return 0;
    fixture_levels[u-0x100000]-=delta;
    return 1;
}
static void fixture_suspend(uint64_t u,uint32_t value) {(void)u;(void)value;}
static uint8_t fixture_is_suspended(uint64_t u) {(void)u;return 0;}
__declspec(dllexport) uint64_t BridgeTestRun(HeroWork *w,int count,int scenario) {
    static BridgeCommand cmd;
    int i;
    if (count<0 || count>24) return 0;
    fixture_count=count;fixture_scenario=scenario;fixture_writes=0;fixture_type_calls=0;
    for (i=0;i<24;++i) fixture_levels[i]=(scenario!=4 && i%3==0) ? (scenario==7 ? 3 : 1) : 0;
    cmd.work=w;cmd.tls_value=w->expected_tls;g_dispatch=&cmd;
    w->selection.local_player=fixture_player;w->selection.create_group=fixture_group;
    w->selection.enum_selected=fixture_enum;w->selection.first_of_group=fixture_first;
    w->selection.remove_from_group=fixture_remove;w->selection.destroy_group=fixture_destroy;
    w->selection.unit_type_id=fixture_type;w->selection.hero_level=fixture_level;w->set_level=fixture_set;
    w->strip_level=fixture_strip;w->suspend_xp=fixture_suspend;w->is_suspended_xp=fixture_is_suspended;
    return BridgeHeroQuery();
}
__declspec(dllexport) int BridgeTestWrites(void) {return fixture_writes;}

static int32_t fixture_attributes[24][3];
static int fixture_attribute_case, fixture_attribute_writes;
static int fixture_attribute_index(uint64_t unit) { return (int)(unit - 0x100000); }
static int32_t fixture_get_strength(uint64_t unit, uint32_t bonuses) {
    (void)bonuses; return fixture_attributes[fixture_attribute_index(unit)][0];
}
static int32_t fixture_get_agility(uint64_t unit, uint32_t bonuses) {
    (void)bonuses; return fixture_attributes[fixture_attribute_index(unit)][1];
}
static int32_t fixture_get_intelligence(uint64_t unit, uint32_t bonuses) {
    (void)bonuses; return fixture_attributes[fixture_attribute_index(unit)][2];
}
static void fixture_set_strength(uint64_t unit, int32_t value, uint32_t permanent) {
    (void)permanent; ++fixture_attribute_writes;
    fixture_attributes[fixture_attribute_index(unit)][0] = value;
}
static void fixture_set_agility(uint64_t unit, int32_t value, uint32_t permanent) {
    (void)permanent; ++fixture_attribute_writes;
    fixture_attributes[fixture_attribute_index(unit)][1] = value;
}
static void fixture_set_intelligence(uint64_t unit, int32_t value, uint32_t permanent) {
    (void)permanent; ++fixture_attribute_writes;
    if (fixture_attribute_case != 1)
        fixture_attributes[fixture_attribute_index(unit)][2] = value;
}
__declspec(dllexport) uint64_t BridgeHeroAttributesTestRun(
    HeroAttributesWork *w, int count, int scenario
) {
    static BridgeCommand cmd;
    int i;
    if (count < 0 || count > 24) return 0;
    fixture_count = count; fixture_index = 0; fixture_type_calls = 0;
    fixture_scenario = scenario == 2 ? 2 : 0;
    fixture_attribute_case = scenario; fixture_attribute_writes = 0;
    for (i = 0; i < 24; ++i) {
        fixture_levels[i] = i % 3 == 0 ? 1 : 0;
        fixture_attributes[i][0] = 10 + i;
        fixture_attributes[i][1] = 20 + i;
        fixture_attributes[i][2] = 30 + i;
    }
    cmd.work = w; cmd.tls_value = w->expected_tls; g_dispatch = &cmd;
    w->selection.local_player = fixture_player; w->selection.create_group = fixture_group;
    w->selection.enum_selected = fixture_enum; w->selection.first_of_group = fixture_first;
    w->selection.remove_from_group = fixture_remove; w->selection.destroy_group = fixture_destroy;
    w->selection.unit_type_id = fixture_type; w->selection.hero_level = fixture_level;
    w->get_strength = fixture_get_strength; w->get_agility = fixture_get_agility;
    w->get_intelligence = fixture_get_intelligence;
    w->set_strength = fixture_set_strength; w->set_agility = fixture_set_agility;
    w->set_intelligence = fixture_set_intelligence;
    return BridgeHeroAttributesQuery();
}
__declspec(dllexport) int BridgeHeroAttributesTestStat(int kind, int index) {
    if (kind == 0) return fixture_attribute_writes;
    if (kind >= 1 && kind <= 3 && index >= 0 && index < 24)
        return fixture_attributes[index][kind - 1];
    return -1;
}

static uint8_t fixture_attack_speed_unit[0x800];
static uint8_t fixture_attack_speed_component[0x400];
static uint8_t fixture_attack_speed_owner[0x100];
static uint8_t fixture_attack_speed_root[0x80];
static uint8_t fixture_attack_speed_table[0x30 * 16];
static uint64_t fixture_attack_speed_root_pointer;
static float fixture_attack_speed_base, fixture_attack_speed_factor;
static uint32_t fixture_attack_speed_rawcode;
static uint64_t fixture_attack_speed_resolve_unit(uint64_t unit) {
    return unit == 0x100000 ? (uint64_t)(uintptr_t)fixture_attack_speed_unit : 0;
}
static uint32_t fixture_attack_speed_get_cooldown(uint64_t unit, int32_t weapon) {
    (void)unit; (void)weapon; return AttackSpeedBits(fixture_attack_speed_base);
}
static void fixture_attack_speed_set_cooldown(
    uint64_t unit, float *value, int32_t weapon
) {
    (void)unit; (void)weapon; fixture_attack_speed_base = *value;
}
static void *fixture_attack_speed_get_factor(
    void *attack, float *value, uint32_t include, int32_t weapon
) {
    (void)attack; (void)include; (void)weapon;
    *value = fixture_attack_speed_factor; return value;
}
static void *fixture_attack_speed_get_effective(
    void *attack, float *value, int32_t weapon
) {
    (void)attack; (void)weapon;
    *value = fixture_attack_speed_base / fixture_attack_speed_factor; return value;
}
__declspec(dllexport) uint64_t BridgeAttackSpeedTestRun(AttackSpeedWork *w) {
    static BridgeCommand cmd;
    uint64_t unit = (uint64_t)(uintptr_t)fixture_attack_speed_unit;
    uint64_t attack = (uint64_t)(uintptr_t)fixture_attack_speed_component;
    uint64_t owner = (uint64_t)(uintptr_t)fixture_attack_speed_owner;
    uint64_t root = (uint64_t)(uintptr_t)fixture_attack_speed_root;
    uint64_t table = (uint64_t)(uintptr_t)fixture_attack_speed_table;
    uint64_t full_handle = 0x97550000002fu;
    uint64_t module_base = (uint64_t)(uintptr_t)&fixture_attack_speed_root_pointer - 0x2f807f0ull;
    memset(fixture_attack_speed_unit, 0, sizeof(fixture_attack_speed_unit));
    memset(fixture_attack_speed_component, 0, sizeof(fixture_attack_speed_component));
    memset(fixture_attack_speed_owner, 0, sizeof(fixture_attack_speed_owner));
    memset(fixture_attack_speed_root, 0, sizeof(fixture_attack_speed_root));
    memset(fixture_attack_speed_table, 0, sizeof(fixture_attack_speed_table));
    fixture_attack_speed_base = 2.2f;
    fixture_attack_speed_factor = 1.5f;
    fixture_attack_speed_rawcode = 0x68666f6fu;
    *(uint64_t *)(fixture_attack_speed_unit + 0x18) = full_handle;
    *(uint32_t *)(fixture_attack_speed_unit + 0x70) = fixture_attack_speed_rawcode;
    *(uint64_t *)(fixture_attack_speed_unit + 0x760) = attack;
    *(uint64_t *)(fixture_attack_speed_owner + 0x20) = full_handle;
    *(uint64_t *)(fixture_attack_speed_owner + 0x90) = unit;
    *(uint64_t *)(fixture_attack_speed_root + 0x18) = table;
    *(uint32_t *)(fixture_attack_speed_root + 0x30) = 0x30u;
    *(uint32_t *)(fixture_attack_speed_table + 0x2f * 16) = 0xfffffffeu;
    *(uint64_t *)(fixture_attack_speed_table + 0x2f * 16 + 8) = owner;
    fixture_attack_speed_root_pointer = root;
    cmd.work = w; cmd.tls_value = w->expected_tls; g_dispatch = &cmd;
    fixture_count = 1; fixture_index = 0; fixture_scenario = 0;
    fixture_levels[0] = 0;
    w->selection.local_player = fixture_player; w->selection.create_group = fixture_group;
    w->selection.enum_selected = fixture_enum; w->selection.first_of_group = fixture_first;
    w->selection.remove_from_group = fixture_remove; w->selection.destroy_group = fixture_destroy;
    w->selection.unit_type_id = fixture_type; w->selection.hero_level = fixture_level;
    w->resolve_unit = fixture_attack_speed_resolve_unit;
    w->get_cooldown = fixture_attack_speed_get_cooldown;
    w->set_cooldown = fixture_attack_speed_set_cooldown;
    w->get_factor = fixture_attack_speed_get_factor;
    w->get_effective = fixture_attack_speed_get_effective;
    w->module_base = module_base;
    w->unit_object = unit;
    w->attack = attack;
    w->full_handle = full_handle;
    w->rawcode = fixture_attack_speed_rawcode;
    return BridgeAttackSpeedQuery();
}
__declspec(dllexport) uint32_t BridgeAttackSpeedTestBase(void) {
    return AttackSpeedBits(fixture_attack_speed_base);
}

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

static uint32_t ability_field_values[24][32][4];
static int ability_field_case, ability_field_sets, ability_field_gets;
static int ability_field_index(uint64_t value) {
    if (value >= 0x100000 && value < 0x100018) return (int)(value - 0x100000);
    if (value >= 0x700000 && value < 0x700018) return (int)(value - 0x700000);
    return 0;
}
static uint32_t ability_field_key(uint32_t field, int32_t level) {
    return (field ^ (field >> 7) ^ (uint32_t)(level * 7)) & 31u;
}
static uint64_t fixture_field_get_ability(uint64_t unit, uint32_t rawcode) {
    (void)rawcode;
    if (ability_field_case == 3 && ability_field_index(unit) == 2) return 0;
    return 0x700000 + (uint64_t)ability_field_index(unit);
}
static uint32_t fixture_field_get_id(uint64_t ability) {
    (void)ability;
    return 0x41487664;
}
static int32_t fixture_field_get_unit_level(uint64_t unit, uint32_t rawcode) {
    (void)unit;(void)rawcode;
    return 3;
}
static uint64_t fixture_field_get(uint64_t ability, uint32_t field, int32_t level) {
    ++ability_field_gets;
    return ability_field_values[ability_field_index(ability)][ability_field_key(field, level)][level < 0 ? 0 : level & 3];
}
static uint32_t fixture_field_set(uint64_t ability, uint32_t field, uint32_t value, int32_t level) {
    ++ability_field_sets;
    if (ability_field_case == 1) return 0;
    if (ability_field_case == 2) return 1;
    ability_field_values[ability_field_index(ability)][ability_field_key(field, level)][level < 0 ? 0 : level & 3] = value;
    return 1;
}
static uint64_t fixture_field_get_field(uint64_t ability, uint32_t field) {return fixture_field_get(ability, field, 0);}
static uint64_t fixture_field_get_level_field(uint64_t ability, uint32_t field, int32_t level) {return fixture_field_get(ability, field, level);}
static uint32_t fixture_field_set_field(uint64_t ability, uint32_t field, uint32_t value) {return fixture_field_set(ability, field, value, 0);}
static uint32_t fixture_field_set_level(uint64_t ability, uint32_t field, int32_t level, uint32_t value) {return fixture_field_set(ability, field, value, level);}
static uint32_t fixture_field_set_real_field(uint64_t ability, uint32_t field, float *value) {
    union {float value;uint32_t bits;} v;v.value=*value;return fixture_field_set_field(ability,field,v.bits);
}
static uint32_t fixture_field_set_real_level(uint64_t ability, uint32_t field, int32_t level, float *value) {
    union {float value;uint32_t bits;} v;v.value=*value;return fixture_field_set_level(ability,field,level,v.bits);
}
__declspec(dllexport) uint64_t BridgeAbilityFieldTestRun(AbilityFieldWork *w,int count,int scenario) {
    static BridgeCommand cmd;int i,j,k;
    if (count < 0 || count > 24) return 0;
    fixture_count=count;fixture_scenario=0;fixture_type_calls=0;
    ability_field_case=scenario;ability_field_sets=ability_field_gets=0;
    for (i=0;i<24;++i) for (j=0;j<32;++j) for (k=0;k<4;++k)
        ability_field_values[i][j][k]=(uint32_t)(1000+i*100+j*10+k);
    cmd.work=w;cmd.tls_value=w->expected_tls;g_dispatch=&cmd;
    w->selection.local_player=fixture_player;w->selection.create_group=fixture_group;
    w->selection.enum_selected=fixture_enum;w->selection.first_of_group=fixture_first;
    w->selection.remove_from_group=fixture_remove;w->selection.destroy_group=fixture_destroy;
    w->selection.unit_type_id=fixture_type;w->selection.hero_level=fixture_level;
    w->get_ability=fixture_field_get_ability;w->get_ability_id=fixture_field_get_id;
    w->get_ability_level=fixture_field_get_unit_level;
    w->get_boolean_field=fixture_field_get_field;w->get_integer_field=fixture_field_get_field;
    w->get_real_field=fixture_field_get_field;w->get_boolean_level_field=fixture_field_get_level_field;
    w->get_integer_level_field=fixture_field_get_level_field;w->get_real_level_field=fixture_field_get_level_field;
    w->set_boolean_field=fixture_field_set_field;w->set_integer_field=fixture_field_set_field;
    w->set_real_field=fixture_field_set_real_field;w->set_boolean_level_field=fixture_field_set_level;
    w->set_integer_level_field=fixture_field_set_level;w->set_real_level_field=fixture_field_set_real_level;
    return BridgeAbilityFieldQuery();
}
__declspec(dllexport) int BridgeAbilityFieldTestStat(int kind) {
    return kind == 0 ? ability_field_sets : ability_field_gets;
}

__declspec(dllexport) int BridgeTestKnownAbilityTail(uint64_t handler,uint32_t code,uint32_t flags,
    uint32_t parameters,uint64_t instruction,uint64_t access,uint64_t address,uint64_t r15) {
    return BridgeKnownAbilityTail(handler,code,flags,parameters,instruction,access,address,r15);
}

__declspec(dllexport) int32_t BridgeTestTailReadback(int32_t actual,int32_t target) {
    return BridgeAcceptAbilityTailReadback(actual,target);
}

static uint64_t item_slots[24][6];
static int item_sizes[24],item_case,item_create_calls,item_set_calls,item_remove_calls,item_created_count;
static int32_t item_original_charges[24][6],item_new_charges[144];
static uint32_t item_new_type[144];
static int fixture_item_index(uint64_t h) {return (int)((h-0x300000)/16);}
static uint64_t fixture_item_slot(uint64_t u,int32_t slot) {
    int i=(int)(u-0x100000);return slot>=0 && slot<item_sizes[i] ? item_slots[i][slot] : 0;
}
static int32_t fixture_item_size(uint64_t u) {return item_sizes[u-0x100000];}
static uint32_t fixture_item_type(uint64_t h) {
    if (h>=0x300000 && h<0x300900) return item_new_type[fixture_item_index(h)];
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
    int i=(int)(u-0x100000),j,index;uint64_t h;
    ++item_create_calls;if(item_case==1 || item_case==8)return 0;
    if(item_case==6)return item_slots[i][0];
    index=item_created_count++;if(index>=144)return 0;
    h=0x300000+(uint64_t)index*16;
    item_new_type[index]=item_case==3 ? 0x62616421 : type;item_new_charges[index]=1;
    for(j=0;j<item_sizes[i];++j)if(!item_slots[i][j]){item_slots[i][j]=h;break;}
    return h;
}
static void fixture_item_detach(uint64_t u,uint64_t h) {
    int i=(int)(u-0x100000),j;for(j=0;j<6;++j)if(item_slots[i][j]==h)item_slots[i][j]=0;
}
static void fixture_item_remove(uint64_t h) {
    ++item_remove_calls;if(h>=0x300000 && item_case!=4)item_new_type[fixture_item_index(h)]=0;
}
static uint8_t fixture_item_add_slot(uint64_t u,uint32_t type,int32_t slot) {
    int i=(int)(u-0x100000),index=item_created_count++;uint64_t h;
    if (slot<0 || slot>=item_sizes[i] || item_slots[i][slot] || index>=144 || item_case==7 || item_case==8 || item_case==9) return 0;
    ++item_create_calls;h=0x300000+(uint64_t)index*16;item_new_type[index]=type;item_new_charges[index]=1;item_slots[i][slot]=h;return 1;
}
static uint64_t fixture_item_create_ground(uint32_t type,float *x,float *y) {
    int index;uint64_t h;(void)x;(void)y;++item_create_calls;
    if(item_case==1 || item_case==8)return 0;
    index=item_created_count++;if(index>=144)return 0;
    h=0x300000+(uint64_t)index*16;
    item_new_type[index]=type;item_new_charges[index]=1;return h;
}
static uint8_t fixture_item_add_existing(uint64_t unit,uint64_t item) {
    int i=(int)(unit-0x100000),j;
    if(item_case==10 && item>=0x300000)return 0;
    for(j=0;j<item_sizes[i];++j)if(!item_slots[i][j]){item_slots[i][j]=item;return 1;}
    return 0;
}
static uint8_t fixture_item_move_slot(uint64_t unit,uint64_t item,int32_t slot) {
    int i=(int)(unit-0x100000),j;
    if(slot<0 || slot>=item_sizes[i])return 0;
    for(j=0;j<item_sizes[i];++j)if(item_slots[i][j]==item){
        item_slots[i][j]=item_slots[i][slot];item_slots[i][slot]=item;return 1;
    }
    return 0;
}
__declspec(dllexport) uint64_t BridgeItemTestRun(ItemWork *w,int count,int scenario) {
    static BridgeCommand cmd;int i,j;
    if(count<0||count>24)return 0;
    fixture_count=count;fixture_scenario=0;fixture_type_calls=0;item_case=scenario;
    item_create_calls=item_set_calls=item_remove_calls=item_created_count=0;
    for(i=0;i<24;++i){
        fixture_levels[i]=i%3==0 ? 1 : 0;item_sizes[i]=(scenario==5 || scenario==9) ? 6 : i%3==0 ? 6 : 0;
        for(j=0;j<6;++j){item_original_charges[i][j]=1;item_slots[i][j]=item_sizes[i] && (j==0||scenario==5||scenario==9) ? 0x200000+i*16+j : 0;}
    }
    for(i=0;i<144;++i){item_new_type[i]=0;item_new_charges[i]=0;}
    cmd.work=w;cmd.tls_value=w->expected_tls;g_dispatch=&cmd;
    w->selection.local_player=fixture_player;w->selection.create_group=fixture_group;
    w->selection.enum_selected=fixture_enum;w->selection.first_of_group=fixture_first;
    w->selection.remove_from_group=fixture_remove;w->selection.destroy_group=fixture_destroy;
    w->selection.unit_type_id=fixture_type;w->selection.hero_level=fixture_level;
    w->create=fixture_item_create;w->add_slot=fixture_item_add_slot;w->in_slot=fixture_item_slot;w->size=fixture_item_size;
    w->type=fixture_item_type;w->charges=fixture_item_charges;w->set_charges=fixture_item_set;
    w->remove=fixture_item_remove;w->detach=fixture_item_detach;
    w->create_ground=fixture_item_create_ground;w->add_existing=fixture_item_add_existing;
    w->move_slot=fixture_item_move_slot;
    return BridgeItemQuery();
}
__declspec(dllexport) int BridgeItemTestStat(int kind) {return kind==0 ? item_create_calls : kind==1 ? item_set_calls : item_remove_calls;}

static uint64_t equipment_fixture_slots[9];
static uint32_t equipment_fixture_code;static int equipment_fixture_case;
static uint64_t equipment_fixture_create(uint32_t code,float *x,float *y) {
    (void)x;(void)y;equipment_fixture_code=code;return 0xA00000;
}
static uint32_t equipment_fixture_type(uint64_t item) {return item==0xA00000 ? equipment_fixture_code : 0x65656831;}
static uint64_t equipment_fixture_kind(uint64_t item) {(void)item;return 1;}
static uint64_t equipment_fixture_slot(int32_t i){return (uint64_t)i;}
static uint64_t equipment_fixture_in(uint64_t unit,uint64_t slot){(void)unit;return equipment_fixture_slots[slot];}
static uint8_t equipment_fixture_equip(uint64_t unit,uint64_t item){
    (void)unit;if(item==0xA00000 && equipment_fixture_case==1)return 0;
    if(equipment_fixture_slots[0])return 0;equipment_fixture_slots[0]=item;return 1;
}
static void equipment_fixture_unequip(uint64_t unit,uint64_t item){
    (void)unit;for(int i=0;i<9;++i)if(equipment_fixture_slots[i]==item)equipment_fixture_slots[i]=0;
}
static void equipment_fixture_remove(uint64_t item){(void)item;}
static uint64_t equipment_fixture_inventory(uint64_t unit,int32_t slot){(void)unit;return 0xB00000+(uint64_t)slot;}
static int32_t equipment_fixture_size(uint64_t unit){(void)unit;return 6;}
__declspec(dllexport) uint64_t BridgeEquipmentTestRun(EquipmentWork *w,int scenario){
    static BridgeCommand cmd;fixture_count=1;fixture_scenario=0;fixture_type_calls=0;fixture_levels[0]=1;
    equipment_fixture_case=scenario;
    for(int i=0;i<9;++i)equipment_fixture_slots[i]=0xC00000+(uint64_t)i;
    if(w->action==2)equipment_fixture_slots[0]=w->expected_created;
    cmd.work=w;cmd.tls_value=w->expected_tls;g_dispatch=&cmd;
    w->selection.local_player=fixture_player;w->selection.create_group=fixture_group;
    w->selection.enum_selected=fixture_enum;w->selection.first_of_group=fixture_first;
    w->selection.remove_from_group=fixture_remove;w->selection.destroy_group=fixture_destroy;
    w->selection.unit_type_id=fixture_type;w->selection.hero_level=fixture_level;
    w->create=equipment_fixture_create;w->type=equipment_fixture_type;w->equipment_type=equipment_fixture_kind;
    w->slot_enum=equipment_fixture_slot;w->in_equipment=equipment_fixture_in;w->equip=equipment_fixture_equip;
    w->unequip=equipment_fixture_unequip;w->remove=equipment_fixture_remove;
    w->in_inventory=equipment_fixture_inventory;w->inventory_size=equipment_fixture_size;
    return BridgeEquipmentQuery();
}

static int clone_case,clone_created,clone_removed,clone_abilities,clone_items;
static int32_t fixture_skill_points[24],clone_skill_points[24];
static uint32_t clone_type[24],clone_ability_level[24],clone_item_type[24];
static int32_t clone_item_charge[24];
static uint32_t clone_bits(float value) { union {float value;uint32_t bits;} v;v.value=value;return v.bits; }
static int clone_index(uint64_t unit) {
    if (unit>=0x100000 && unit<0x100018) return (int)(unit-0x100000);
    if (unit>=0x600000 && unit<0x600018) return (int)(unit-0x600000);
    return 0;
}
static uint64_t clone_owner(uint64_t unit) { (void)unit; return 0x100008; }
static uint32_t clone_type_id(uint64_t unit) {
    int index=clone_index(unit);
    if (unit>=0x600000 && unit<0x600018) return clone_type[index];
    return fixture_type(unit);
}
static uint32_t clone_x(uint64_t unit) { (void)unit; return clone_bits(100.0f); }
static uint32_t clone_y(uint64_t unit) { (void)unit; return clone_bits(200.0f); }
static uint32_t clone_facing(uint64_t unit) { (void)unit; return clone_bits(90.0f); }
static uint64_t clone_create(uint64_t owner,uint32_t rawcode,float *x,float *y,float *facing) {
    int i=clone_created;(void)owner;(void)x;(void)y;(void)facing;
    if (clone_case==1 || (clone_case==4 && i>=3) || i>=24) return 0;
    clone_type[i]=rawcode;clone_ability_level[i]=0;clone_item_type[i]=0;clone_item_charge[i]=0;clone_skill_points[i]=3;
    ++clone_created;return 0x600000+i;
}
static void clone_set_owner(uint64_t unit,uint64_t owner,uint32_t color) {(void)unit;(void)owner;(void)color;}
static void clone_remove_unit(uint64_t unit) { if (unit>=0x600000 && unit<0x600018) {clone_type[clone_index(unit)]=0;++clone_removed;} }
static int32_t clone_level(uint64_t unit) { return unit>=0x600000 ? 1 : fixture_level(unit); }
static void clone_set_hero_level_fixture(uint64_t unit,int32_t level,uint32_t eye) {(void)unit;(void)level;(void)eye;}
static int32_t clone_get_skill_points(uint64_t unit) {
    return unit>=0x600000 ? clone_skill_points[clone_index(unit)] : fixture_skill_points[clone_index(unit)];
}
static uint8_t clone_modify_skill_points(uint64_t unit,int32_t delta) {
    if (unit < 0x600000 || unit >= 0x600018) return 0;
    clone_skill_points[clone_index(unit)] += delta;
    return 1;
}
static uint64_t clone_ability_by_index(uint64_t unit,int32_t index) {
    if (clone_case==5 && unit < 0x600000 && fixture_level(unit) > 0 && index == 0)
        return 0x720000 + clone_index(unit); /* engine buff exposed as a unit ability */
    if (unit < 0x600000 && fixture_level(unit) > 0 && index == 0)
        return 0x700000 + clone_index(unit);
    if (unit < 0x600000 && fixture_level(unit) > 0 && index == 1)
        return 0x710000 + clone_index(unit); /* supplied by the source item */
    return 0;
}
static uint32_t clone_ability_id(uint64_t ability) {
    if (ability >= 0x720000 && ability < 0x720018) return 0x424e6874; /* BNht */
    return ability >= 0x710000 && ability < 0x710018 ? 0x41496d61 : 0x414f6372;
}
static int32_t clone_get_ability_level(uint64_t unit,uint32_t rawcode) {
    (void)rawcode;return unit>=0x600000 ? (int32_t)clone_ability_level[clone_index(unit)] : fixture_level(unit)>0 ? 2 : 0;
}
static uint8_t clone_add_ability(uint64_t unit,uint32_t rawcode) {
    if (clone_case==5 && rawcode==0x424e6874) return 0;
    (void)rawcode;if (clone_case==2)return 0;clone_ability_level[clone_index(unit)]=1;++clone_abilities;return 1;
}
static int32_t clone_set_ability_level_fn(uint64_t unit,uint32_t rawcode,int32_t level) {
    (void)rawcode;clone_ability_level[clone_index(unit)]=level;return level;
}
static uint64_t clone_item_slot(uint64_t unit,int32_t slot) {
    return unit<0x600000 && fixture_level(unit)>0 && slot==0 ? 0x200000+clone_index(unit) : 0;
}
static uint64_t clone_item_ability_by_index(uint64_t item,int32_t index) {
    return item >= 0x200000 && item < 0x200018 && index == 0 ? 0x710000 + (item - 0x200000) : 0;
}
static uint32_t clone_item_type_fn(uint64_t item) {
    if (item>=0x800000 && item<0x800018)return clone_item_type[item-0x800000];
    return item>=0x200000 && item<0x200018 ? 0x73747770 : 0;
}
static int32_t clone_item_charges_fn(uint64_t item) {
    return item>=0x800000 && item<0x800018 ? clone_item_charge[item-0x800000] : 1;
}
static uint64_t clone_add_item(uint64_t unit,uint32_t rawcode) {
    int i=clone_index(unit);(void)rawcode;
    if (clone_case==3)return 0;
    clone_item_type[i]=rawcode;clone_item_charge[i]=1;++clone_items;return 0x800000+i;
}
static void clone_set_item_charges(uint64_t item,int32_t value) {if (item>=0x800000 && item<0x800018)clone_item_charge[item-0x800000]=value;}
static void clone_detach_item(uint64_t unit,uint64_t item) {(void)unit;(void)item;}
static void clone_remove_item(uint64_t item) {if (item>=0x800000 && item<0x800018)clone_item_type[item-0x800000]=0;}
__declspec(dllexport) uint64_t BridgeCloneTestRun(CloneWork *w,int count,int scenario) {
    static BridgeCommand cmd;int i;
    if (count<0 || count>24)return 0;
    fixture_count=count;fixture_scenario=0;clone_case=scenario;clone_created=clone_removed=clone_abilities=clone_items=0;
    for(i=0;i<24;++i){fixture_levels[i]=i%3==0?1:0;fixture_skill_points[i]=i%3==0?0:9;clone_type[i]=0;clone_ability_level[i]=0;clone_item_type[i]=0;clone_item_charge[i]=0;clone_skill_points[i]=0;}
    cmd.work=w;cmd.tls_value=w->expected_tls;g_dispatch=&cmd;
    w->selection.local_player=fixture_player;w->selection.create_group=fixture_group;
    w->selection.enum_selected=fixture_enum;w->selection.first_of_group=fixture_first;
    w->selection.remove_from_group=fixture_remove;w->selection.destroy_group=fixture_destroy;
    w->selection.unit_type_id=fixture_type;w->selection.hero_level=fixture_level;
    w->owner=clone_owner;w->type_id=clone_type_id;w->get_x=clone_x;w->get_y=clone_y;w->get_facing=clone_facing;
    w->create=clone_create;w->set_owner=clone_set_owner;w->remove_unit=clone_remove_unit;
    w->get_level=clone_level;w->set_level=clone_set_hero_level_fixture;
    w->get_skill_points=clone_get_skill_points;w->modify_skill_points=clone_modify_skill_points;
    w->ability_by_index=clone_ability_by_index;
    w->ability_id=clone_ability_id;w->ability_level=clone_get_ability_level;w->add_ability=clone_add_ability;
    w->set_ability_level=clone_set_ability_level_fn;w->item_ability_by_index=clone_item_ability_by_index;
    w->item_in_slot=clone_item_slot;w->item_type=clone_item_type_fn;
    w->item_charges=clone_item_charges_fn;w->add_item=clone_add_item;w->set_item_charges=clone_set_item_charges;
    w->detach_item=clone_detach_item;w->remove_item=clone_remove_item;
    return BridgeCloneQuery();
}
__declspec(dllexport) int BridgeCloneTestStat(int kind) {return kind==0?clone_created:kind==1?clone_removed:kind==2?clone_abilities:kind==3?clone_items:kind==4?clone_skill_points[0]:-1;}

typedef struct CatalogFixtureNode {
    uint32_t rawcode;
    uint32_t reserved;
    uint64_t next;
} CatalogFixtureNode;
static uint32_t catalog_test_count;
static uint64_t catalog_test_root;
static int32_t catalog_test_link;
static CatalogFixtureNode catalog_test_nodes[8];
static int catalog_test_created, catalog_test_removed;
static uint64_t fixture_catalog_create(uint32_t rawcode,float *x,float *y) {
    (void)rawcode;
    (void)x;(void)y;
    ++catalog_test_created;
    return 0xa00000u + (uint64_t)catalog_test_created;
}
static void fixture_catalog_remove(uint64_t item) {
    if (item) ++catalog_test_removed;
}
static uint32_t fixture_catalog_choose(uint32_t level) {(void)level;return 0;}
__declspec(dllexport) uint64_t BridgeItemCatalogTestRun(ItemCatalogWork *w,int action,int scenario) {
    static BridgeCommand cmd;
    int count = scenario > 0 && scenario <= 8 ? scenario : 4;
    catalog_test_count = (uint32_t)count;
    catalog_test_link = 0;
    catalog_test_created = catalog_test_removed = 0;
    for (int index=0; index<count; ++index) {
        static const uint32_t codes[8] = {
            0x70686561u,0x73747770u,0x636b6e67u,0x73726567u,
            0x686f6c79u,0x706f7765u,0x736d6e74u,0x706d6e74u,
        };
        catalog_test_nodes[index].rawcode=codes[index];catalog_test_nodes[index].reserved=0;
        catalog_test_nodes[index].next=index+1<count?(uint64_t)(uintptr_t)&catalog_test_nodes[index+1]:0;
    }
    catalog_test_root=(uint64_t)(uintptr_t)&catalog_test_nodes[0];
    catalog_fixture_enabled=1;
    catalog_fixture_count_pointer=&catalog_test_count;
    catalog_fixture_root_pointer=&catalog_test_root;
    catalog_fixture_link_pointer=&catalog_test_link;
    catalog_fixture_rawcode_offset=0;
    w->action=(uint32_t)action;
    w->choose_random_item=action==1?fixture_catalog_choose:0;
    w->create_item=(action==1 || action==3)?fixture_catalog_create:0;
    w->remove_item=action==2?fixture_catalog_remove:0;
    cmd.work=w;cmd.tls_value=w->expected_tls;g_dispatch=&cmd;
    return BridgeItemCatalogQuery();
}
__declspec(dllexport) int BridgeItemCatalogTestStat(int kind) {
    return kind==0?catalog_test_created:catalog_test_removed;
}

static int unit_action_case,unit_action_calls[16];
static uint8_t unit_action_invulnerable[24],unit_action_paused[24],unit_action_pathing[24];
static uint64_t unit_action_owner[24];
static float unit_action_x[24],unit_action_y[24],unit_action_scale_values[24];
static int unit_action_index(uint64_t unit) {return unit>=0x100000 && unit<0x100018 ? (int)(unit-0x100000) : 0;}
static void unit_action_set_invulnerable(uint64_t unit,uint32_t value) {
    ++unit_action_calls[0];unit_action_invulnerable[unit_action_index(unit)]=(uint8_t)value;
}
static uint8_t unit_action_get_invulnerable(uint64_t unit) {++unit_action_calls[1];return unit_action_invulnerable[unit_action_index(unit)];}
static void unit_action_set_pathing(uint64_t unit,uint32_t value) {
    ++unit_action_calls[2];unit_action_pathing[unit_action_index(unit)]=(uint8_t)value;
}
static void unit_action_pause(uint64_t unit,uint32_t value) {
    ++unit_action_calls[3];unit_action_paused[unit_action_index(unit)]=(uint8_t)value;
}
static uint8_t unit_action_is_paused(uint64_t unit) {++unit_action_calls[4];return unit_action_paused[unit_action_index(unit)];}
static void unit_action_reset(uint64_t unit) {(void)unit;++unit_action_calls[5];}
static void unit_action_kill(uint64_t unit) {(void)unit;++unit_action_calls[6];}
static void unit_action_remove(uint64_t unit) {(void)unit;++unit_action_calls[7];}
static void unit_action_explode(uint64_t unit,uint32_t value) {(void)unit;(void)value;++unit_action_calls[8];}
static void unit_action_scale(uint64_t unit,float *x,float *y,float *z) {
    (void)y;(void)z;++unit_action_calls[9];unit_action_scale_values[unit_action_index(unit)]=*x;
}
static void unit_action_position(uint64_t unit,float *x,float *y) {
    ++unit_action_calls[10];unit_action_x[unit_action_index(unit)]=*x;unit_action_y[unit_action_index(unit)]=*y;
}
static uint32_t unit_action_get_x(uint64_t unit) {
    union { float value; uint32_t bits; } result;
    ++unit_action_calls[11];result.value=unit_action_x[unit_action_index(unit)];return result.bits;
}
static uint32_t unit_action_get_y(uint64_t unit) {
    union { float value; uint32_t bits; } result;
    ++unit_action_calls[12];result.value=unit_action_y[unit_action_index(unit)];return result.bits;
}
static void unit_action_set_owner(uint64_t unit,uint64_t owner,uint32_t color) {
    (void)color;++unit_action_calls[13];unit_action_owner[unit_action_index(unit)]=owner;
}
static uint64_t unit_action_get_owner(uint64_t unit) {++unit_action_calls[14];return unit_action_owner[unit_action_index(unit)];}
static uint8_t unit_action_modify_skill_points(uint64_t unit,uint32_t amount) {
    (void)unit;(void)amount;++unit_action_calls[15];return unit_action_case!=1;
}
__declspec(dllexport) uint64_t BridgeUnitActionTestRun(UnitActionWork *w,int count,int scenario) {
    static BridgeCommand cmd;int i;
    if (count<0 || count>24)return 0;
    fixture_count=count;fixture_scenario=0;unit_action_case=scenario;
    for(i=0;i<24;++i) {
        fixture_levels[i]=i%3==0?1:0;unit_action_invulnerable[i]=0;unit_action_paused[i]=0;
        unit_action_pathing[i]=1;unit_action_owner[i]=0x100009;unit_action_x[i]=10.0f+i;
        unit_action_y[i]=20.0f+i;unit_action_scale_values[i]=1.0f;
    }
    for(i=0;i<16;++i)unit_action_calls[i]=0;
    cmd.work=w;cmd.tls_value=w->expected_tls;g_dispatch=&cmd;
    w->selection.local_player=fixture_player;w->selection.create_group=fixture_group;
    w->selection.enum_selected=fixture_enum;w->selection.first_of_group=fixture_first;
    w->selection.remove_from_group=fixture_remove;w->selection.destroy_group=fixture_destroy;
    w->selection.unit_type_id=fixture_type;w->selection.hero_level=fixture_level;
    w->set_invulnerable=unit_action_set_invulnerable;w->get_invulnerable=unit_action_get_invulnerable;
    w->set_pathing=unit_action_set_pathing;w->pause_unit=unit_action_pause;w->is_paused=unit_action_is_paused;
    w->reset_cooldown=unit_action_reset;w->kill_unit=unit_action_kill;w->remove_unit=unit_action_remove;
    w->set_exploded=unit_action_explode;w->set_scale=unit_action_scale;w->set_position=unit_action_position;
    w->get_x=unit_action_get_x;w->get_y=unit_action_get_y;w->set_owner=unit_action_set_owner;
    w->get_owner=unit_action_get_owner;w->modify_skill_points=unit_action_modify_skill_points;
    return BridgeUnitActionQuery();
}
__declspec(dllexport) int BridgeUnitActionTestStat(int kind) {
    return kind>=0 && kind<16 ? unit_action_calls[kind] : unit_action_case;
}

static float position_x[24], position_y[24];
static int position_calls[4];
static void position_set_position(uint64_t unit, float *x, float *y) {
    ++position_calls[0]; ++position_calls[1];
    position_x[unit_action_index(unit)] = *x;
    position_y[unit_action_index(unit)] = *y;
}
static uint32_t position_get_x(uint64_t unit) {
    union { float value; uint32_t bits; } result;
    ++position_calls[2]; result.value = position_x[unit_action_index(unit)]; return result.bits;
}
static uint32_t position_get_y(uint64_t unit) {
    union { float value; uint32_t bits; } result;
    ++position_calls[3]; result.value = position_y[unit_action_index(unit)]; return result.bits;
}
__declspec(dllexport) uint64_t BridgePositionTestRun(PositionWork *w, int count) {
    static BridgeCommand cmd; int i;
    if (count < 0 || count > 24) return 0;
    fixture_count = count; fixture_scenario = 0;
    for (i = 0; i < 24; ++i) {
        fixture_levels[i] = i % 3 == 0 ? 1 : 0;
        position_x[i] = 10.0f + i; position_y[i] = 20.0f + i;
        position_calls[0] = position_calls[1] = position_calls[2] = position_calls[3] = 0;
    }
    cmd.work = w; cmd.tls_value = w->expected_tls; g_dispatch = &cmd;
    w->selection.local_player = fixture_player; w->selection.create_group = fixture_group;
    w->selection.enum_selected = fixture_enum; w->selection.first_of_group = fixture_first;
    w->selection.remove_from_group = fixture_remove; w->selection.destroy_group = fixture_destroy;
    w->selection.unit_type_id = fixture_type; w->selection.hero_level = fixture_level;
    w->set_position = position_set_position;
    w->get_x = position_get_x; w->get_y = position_get_y;
    return BridgePositionQuery();
}
__declspec(dllexport) int BridgePositionTestStat(int kind) {
    return kind >= 0 && kind < 4 ? position_calls[kind] : -1;
}
__declspec(dllexport) uint64_t BridgePositionTargetTestRun(PositionWork *w) {
    static BridgeCommand cmd; int i;
    for (i = 0; i < 24; ++i) {
        position_x[i] = 10.0f + i; position_y[i] = 20.0f + i;
    }
    position_calls[0] = position_calls[1] = position_calls[2] = position_calls[3] = 0;
    cmd.work = w; cmd.tls_value = w->expected_tls; g_dispatch = &cmd;
    w->set_position = position_set_position;
    w->get_x = position_get_x; w->get_y = position_get_y;
    return BridgePositionQuery();
}

static int world_calls[8];
static uint32_t world_last_rawcode,world_last_level,world_last_xp;
static uint8_t world_fog,world_mask;
static uint64_t world_player(void) {return 0x100008;}
static void world_set_tech_max(uint64_t player,uint32_t rawcode,uint32_t level) {
    (void)player;++world_calls[0];world_last_rawcode=rawcode;world_last_level=level;
}
static void world_set_tech_researched(uint64_t player,uint32_t rawcode,uint32_t level) {
    (void)player;(void)rawcode;(void)level;++world_calls[1];
}
static void world_set_xp(uint64_t player,float value) {
    union {float value;uint32_t bits;} bits;(void)player;bits.value=value;
    ++world_calls[2];world_last_xp=bits.bits;
}
static void world_fog_enable(uint32_t value) {(void)++world_calls[3];world_fog=(uint8_t)value;}
static void world_mask_enable(uint32_t value) {(void)++world_calls[4];world_mask=(uint8_t)value;}
static uint8_t world_is_fog(void) {++world_calls[5];return world_fog;}
static uint8_t world_is_mask(void) {++world_calls[6];return world_mask;}
static void world_pause(uint32_t value) {(void)value;++world_calls[7];}
static void world_end(uint32_t value) {(void)value;++world_calls[7];}
__declspec(dllexport) uint64_t BridgeWorldTestRun(WorldWork *w,int action,uint32_t rawcode,uint32_t value) {
    static BridgeCommand cmd;int i;
    for(i=0;i<8;++i)world_calls[i]=0;
    world_last_rawcode=world_last_level=world_last_xp=0;world_fog=1;world_mask=1;
    cmd.work=w;cmd.tls_value=w->expected_tls;g_dispatch=&cmd;
    w->get_local_player=world_player;w->set_tech_max=world_set_tech_max;
    w->set_tech_researched=world_set_tech_researched;w->set_xp_rate=world_set_xp;
    w->fog_enable=world_fog_enable;w->fog_mask_enable=world_mask_enable;
    w->is_fog_enabled=world_is_fog;w->is_fog_mask_enabled=world_is_mask;
    w->pause_game=world_pause;w->end_game=world_end;
    w->action=(uint32_t)action;w->rawcode=rawcode;w->value=value;
    return BridgeWorldQuery();
}
__declspec(dllexport) int BridgeWorldTestStat(int kind) {
    if(kind>=0 && kind<8)return world_calls[kind];
    if(kind==8)return (int)world_last_rawcode;
    if(kind==9)return (int)world_last_level;
    if(kind==10)return (int)world_last_xp;
    if(kind==11)return world_fog;
    if(kind==12)return world_mask;
    return -1;
}

__declspec(dllexport) uint32_t BridgeFogGateTest(
    uint64_t fn,uint32_t phase,uint32_t code,uint32_t flags,uint32_t parameters,
    uint64_t instruction,uint64_t access,uint64_t address
) {
    uint32_t length=0;
    return BridgeKnownFogGate(
        fn,phase,code,flags,parameters,instruction,access,address,&length
    ) ? length : 0u;
}

__declspec(dllexport) uint32_t BridgeFogTailTest(
    uint64_t fn,uint32_t phase,uint32_t code,uint32_t flags,uint32_t parameters,
    uint64_t instruction,uint64_t access,uint64_t address
) {
    return BridgeKnownFogTail(
        fn,phase,code,flags,parameters,instruction,access,address
    ) ? 1u : 0u;
}

static int spawn_case, spawn_create_calls, spawn_remove_calls;
static uint32_t spawn_requested, spawn_actual, spawn_x_bits, spawn_y_bits, spawn_facing_bits;
static uint64_t spawn_create(uint64_t player, uint32_t rawcode, float *x, float *y, float *facing) {
    union { float value; uint32_t bits; } xb, yb, fb;
    (void)player;
    xb.value = *x; yb.value = *y; fb.value = *facing;
    ++spawn_create_calls;
    spawn_x_bits = xb.bits; spawn_y_bits = yb.bits; spawn_facing_bits = fb.bits;
    if (spawn_case == 1) return 0;
    spawn_requested = rawcode;
    spawn_actual = spawn_case == 2 ? 0x62616421u : rawcode;
    return 0x900000;
}
static uint32_t spawn_type(uint64_t unit) {
    (void)unit;
    return spawn_actual;
}
static void spawn_remove(uint64_t unit) { (void)unit; ++spawn_remove_calls; }
__declspec(dllexport) uint64_t BridgeSpawnTestRun(SpawnWork *w, uint32_t rawcode, int scenario) {
    static BridgeCommand cmd;
    spawn_case = scenario; spawn_create_calls = spawn_remove_calls = 0;
    spawn_requested = spawn_actual = spawn_x_bits = spawn_y_bits = spawn_facing_bits = 0;
    cmd.work = w; cmd.tls_value = w->expected_tls; g_dispatch = &cmd;
    w->get_local_player = world_player;
    w->create_unit = spawn_create;
    w->type_id = spawn_type;
    w->remove_unit = spawn_remove;
    w->rawcode = rawcode;
    return BridgeSpawnQuery();
}
__declspec(dllexport) int BridgeSpawnTestStat(int kind) {
    if (kind == 0) return spawn_create_calls;
    if (kind == 1) return spawn_remove_calls;
    if (kind == 2) return (int)spawn_requested;
    if (kind == 3) return (int)spawn_actual;
    if (kind == 4) return (int)spawn_x_bits;
    if (kind == 5) return (int)spawn_y_bits;
    if (kind == 6) return (int)spawn_facing_bits;
    return -1;
}

static float fixture_mouse_x, fixture_mouse_y;
static uint64_t fixture_mouse_location(void) { return 0x910000; }
static float fixture_get_location_x(uint64_t location) { (void)location; return fixture_mouse_x; }
static float fixture_get_location_y(uint64_t location) { (void)location; return fixture_mouse_y; }
static void fixture_remove_location(uint64_t location) { (void)location; }
__declspec(dllexport) uint64_t BridgeMouseTestRun(MouseWork *w, uint32_t x_bits, uint32_t y_bits, int error) {
    static BridgeCommand cmd;
    union { uint32_t bits; float value; } x, y;
    x.bits = x_bits; y.bits = y_bits;
    fixture_mouse_x = x.value; fixture_mouse_y = y.value;
    cmd.work = w; cmd.tls_value = w->expected_tls; g_dispatch = &cmd;
    w->get_mouse_position = fixture_mouse_location;
    w->get_location_x = fixture_get_location_x;
    w->get_location_y = fixture_get_location_y;
    w->remove_location = fixture_remove_location;
    w->error = (uint32_t)error;
    return BridgeMouseQuery();
}

static float stat_fixture_chance,stat_fixture_damage;
static int stat_fixture_present,stat_fixture_bool_calls,stat_fixture_failure,stat_fixture_hidden;
static uint64_t stat_fixture_lookup(uint64_t unit,uint32_t index) {
    (void)unit;return index==0?0x100700:(index==1 && stat_fixture_present?0x100701:0);
}
static uint32_t stat_fixture_id(uint64_t ability) {return ability==0x100700?0x41496372u:0x41497872u;}
__declspec(dllexport) uint32_t BridgeStatRuntimeFlagTest(uint32_t scenario) {
    StatDetailsWork w={0};BridgeCommand cmd={0};
    uint64_t owner[32]={0},unit[32]={0},wr[2][32]={{0}},data[2][40]={{0}},root[16]={0},table[8]={0};
    uint8_t *base=VirtualAlloc(0,0x2f81000u,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
    uint32_t result=0;
    if(!base)return 0xffffffffu;
    w.target_full_handle=0x100000001ull;w.resolver_base=(uint64_t)(uintptr_t)base;
    w.target_unit=0x100100;w.selection.count=1;
    w.selection.rows[0].unit=w.target_unit;w.selection.rows[0].rawcode=0x48363038u;
    w.get_ability_id=stat_fixture_id;
    owner[4]=w.target_full_handle;owner[18]=(uint64_t)(uintptr_t)unit;
    *(uint32_t *)((uint8_t *)unit+0x70)=0x48363038u;
    *(uint64_t *)(base+0x2f807f0u)=(uint64_t)(uintptr_t)root;
    root[3]=(uint64_t)(uintptr_t)table;*(uint32_t *)((uint8_t *)root+0x30)=4;
    table[2]=0xfffffffeu;table[3]=(uint64_t)(uintptr_t)owner;
    owner[27]=(uint64_t)(uintptr_t)&wr[0][7];
    for(uint32_t i=0;i<2;++i){
        uint64_t full=0x100000002ull+i;
        wr[i][3]=0x414963722b61676cull;wr[i][4]=full;
        wr[i][7]=i?(uint64_t)(uintptr_t)&wr[0][7]:(uint64_t)(uintptr_t)&owner[26];
        wr[i][8]=i?0:(uint64_t)(uintptr_t)&wr[1][7];
        wr[i][10]=(uint64_t)(uintptr_t)owner;wr[i][18]=(uint64_t)(uintptr_t)data[i];
        data[i][0]=w.resolver_base+0x23a50c8u;data[i][3]=full;data[i][13]=(uint64_t)(uintptr_t)unit;
        *(uint32_t *)((uint8_t *)data[i]+0x70)=0x41496372u;
        *(uint32_t *)((uint8_t *)data[i]+0x78)=0x41496372u;
        *(uint32_t *)((uint8_t *)data[i]+0x38)=i?0x80000100u:0x80000048u;
        *((uint8_t *)data[i]+0x128)=i?1:0;
        table[(i+2)*2]=0xfffffffeu;table[(i+2)*2+1]=(uint64_t)(uintptr_t)wr[i];
    }
    if(scenario==1)*((uint8_t *)data[1]+0x128)=0;
    if(scenario==2)*(uint32_t *)((uint8_t *)data[1]+0x38)=0x80000048u;
    if(scenario==3)*(uint32_t *)((uint8_t *)data[0]+0x38)=0x80000100u;
    if(scenario==4)data[1][0]+=8;
    if(scenario==5)wr[1][10]=0;
    if(scenario==6)table[7]=0;
    cmd.specific_handler=(void *)GetProcAddress(GetModuleHandleW(L"ntdll.dll"),"__C_specific_handler");
    g_dispatch=&cmd;
    __try {result=StatDetailsBool(&w,0x100700,0x49637232u);if(w.error)result=w.error;}
    __except(EXCEPTION_EXECUTE_HANDLER){result=GetExceptionCode();}
    g_dispatch=0;VirtualFree(base,0,MEM_RELEASE);return result;
}
static uint64_t stat_fixture_convert(uint32_t field) {return field;}
static uint64_t stat_fixture_real(uint64_t ability,uint32_t field,int32_t level) {
    union{float value;uint32_t bits;}v;(void)ability;(void)level;
    v.value=field==0x4f637231u?stat_fixture_chance:stat_fixture_damage;return v.bits;
}
static uint64_t stat_fixture_boolean(uint64_t ability,uint32_t field,int32_t level) {
    (void)ability;(void)field;(void)level;++stat_fixture_bool_calls;return 0;
}
static uint32_t stat_fixture_set_real(uint64_t ability,uint32_t field,int32_t level,float *value) {
    (void)ability;(void)level;if(field==0x4f637231u)stat_fixture_chance=*value;else stat_fixture_damage=*value;
    if(stat_fixture_failure==1){stat_fixture_failure=0;RaiseException(0xe0420001u,0,0,0);}
    return 1;
}
static uint32_t stat_fixture_set_bool(uint64_t ability,uint32_t field,int32_t level,uint32_t value) {
    (void)ability;(void)field;(void)level;(void)value;++stat_fixture_bool_calls;return 0;
}
static uint8_t stat_fixture_add(uint64_t unit,uint32_t code) {
    (void)unit;(void)code;stat_fixture_present=1;stat_fixture_chance=25;stat_fixture_damage=0;return 1;
}
static uint8_t stat_fixture_remove(uint64_t unit,uint32_t code) {(void)unit;(void)code;stat_fixture_present=0;return 1;}
static void stat_fixture_hide(uint64_t unit,uint32_t code,uint8_t hide) {
    (void)unit;(void)code;stat_fixture_hidden=hide;
    if(stat_fixture_failure==2){stat_fixture_failure=0;RaiseException(0xe0420002u,0,0,0);}
}
__declspec(dllexport) uint32_t BridgeStatIsolatedWriteTest(int create_controller) {
    StatDetailsWork w={0};BridgeCommand cmd={0};union{float value;uint32_t bits;}target;
    int scenario=create_controller;
    create_controller=scenario==1 || scenario==3;
    fixture_count=1;fixture_scenario=0;fixture_type_calls=0;fixture_levels[0]=10;
    stat_fixture_present=!(create_controller || scenario==4);
    stat_fixture_chance=100;stat_fixture_damage=450;stat_fixture_bool_calls=0;
    stat_fixture_failure=scenario==2?1:scenario==3?2:0;stat_fixture_hidden=0;
    w.selection.local_player=fixture_player;w.selection.create_group=fixture_group;
    w.selection.enum_selected=fixture_enum;w.selection.first_of_group=fixture_first;
    w.selection.remove_from_group=fixture_remove;w.selection.destroy_group=fixture_destroy;
    w.selection.unit_type_id=fixture_type;w.selection.hero_level=fixture_level;
    w.get_ability=stat_fixture_lookup;w.get_ability_id=stat_fixture_id;
    w.convert_real_level_field=stat_fixture_convert;w.convert_boolean_level_field=stat_fixture_convert;
    w.get_real_level=stat_fixture_real;w.get_boolean_level=stat_fixture_boolean;
    w.set_real_level=stat_fixture_set_real;w.set_boolean_level=stat_fixture_set_bool;
    w.add_ability=stat_fixture_add;w.remove_ability=stat_fixture_remove;w.hide_ability=stat_fixture_hide;
    w.action=1;w.stat_index=create_controller?0:1;w.controller_rawcode=0x41497872u;
    target.value=create_controller?35.0f:350.0f;w.target_bits=target.bits;
    cmd.specific_handler=(void *)GetProcAddress(GetModuleHandleW(L"ntdll.dll"),"__C_specific_handler");
    if(!cmd.specific_handler)return 1014;
    cmd.work=&w;g_dispatch=&cmd;BridgeStatDetailsQuery();g_dispatch=0;
    if(scenario==2){
        if(w.error!=0xe0420001u || w.completed || w.changed)return 1010;
        if(stat_fixture_damage!=450 || stat_fixture_chance!=100 || stat_fixture_hidden)return 1011;
        return 0;
    }
    if(scenario==3){
        if(w.error!=0xe0420002u || w.completed || w.changed)return 1012;
        return stat_fixture_present?1013:0;
    }
    if(scenario==4){
        if(w.error!=275 || w.completed || w.changed || stat_fixture_present)return 1015;
        return 0;
    }
    if(w.error)return w.error;
    if(!w.completed || !w.changed || stat_fixture_damage!=(create_controller?0.0f:350.0f))return 1001;
    if(stat_fixture_bool_calls)return 1002;
    if(stat_fixture_chance!=(create_controller?35.0f:100.0f))return 1003;
    if(stat_fixture_hidden!=create_controller)return 1004;
    return 0;
}

static float critical_test_chance[2],critical_test_damage[2];
static uint32_t critical_test_ids[2],critical_test_sets,critical_test_fail;
static uint64_t critical_test_lookup(uint64_t unit,uint32_t index) {
    (void)unit;return index<2?0x100800u+index:0;
}
static uint32_t critical_test_id(uint64_t ability) {
    return critical_test_ids[(uint32_t)(ability-0x100800u)];
}
static uint64_t critical_test_real(uint64_t ability,uint32_t field,int32_t level) {
    union {float value;uint32_t bits;} result;
    uint32_t index=(uint32_t)(ability-0x100800u);
    (void)level;
    result.value=field==0x4f637231u?critical_test_chance[index]:critical_test_damage[index];
    return result.bits;
}
static uint32_t critical_test_set(uint64_t ability,uint32_t field,int32_t level,float *value) {
    uint32_t index=(uint32_t)(ability-0x100800u);
    (void)level;
    if(field!=0x49787232u)return 0;
    ++critical_test_sets;
    if(critical_test_fail==5 && critical_test_sets==3)return 0;
    critical_test_damage[index]=*value;
    if((critical_test_fail==3 || critical_test_fail==5) && critical_test_sets==2)return 0;
    return 1;
}
__declspec(dllexport) uint32_t BridgeCriticalProviderTestRun(uint32_t scenario) {
    StatDetailsWork w={0};BridgeCommand cmd={0};union {float value;uint32_t bits;} target,after;
    fixture_count=1;fixture_scenario=0;fixture_type_calls=0;fixture_levels[0]=10;
    critical_test_ids[0]=0x41497872u;critical_test_ids[1]=0x41435378u;
    if(scenario==6){critical_test_ids[0]=0x41497363u;critical_test_ids[1]=0x41534371u;}
    critical_test_chance[0]=20.0f;critical_test_chance[1]=scenario==1?0.0f:30.0f;
    if(scenario==2)critical_test_chance[0]=critical_test_chance[1]=0.0f;
    if(scenario==7){union {float value;uint32_t bits;} nan;nan.bits=0x7fc00000u;critical_test_chance[0]=nan.value;}
    critical_test_damage[0]=25.0f;critical_test_damage[1]=scenario==1?400.0f:50.0f;
    critical_test_sets=0;critical_test_fail=(scenario==3 || scenario==5)?scenario:0;
    w.selection.local_player=fixture_player;w.selection.create_group=fixture_group;
    w.selection.enum_selected=fixture_enum;w.selection.first_of_group=fixture_first;
    w.selection.remove_from_group=fixture_remove;w.selection.destroy_group=fixture_destroy;
    w.selection.unit_type_id=fixture_type;w.selection.hero_level=fixture_level;
    w.get_ability=critical_test_lookup;w.get_ability_id=critical_test_id;
    w.convert_real_level_field=stat_fixture_convert;w.convert_boolean_level_field=stat_fixture_convert;
    w.get_real_level=critical_test_real;w.get_boolean_level=stat_fixture_boolean;
    w.set_real_level=critical_test_set;w.set_boolean_level=stat_fixture_set_bool;
    w.add_ability=stat_fixture_add;w.remove_ability=stat_fixture_remove;w.hide_ability=stat_fixture_hide;
    w.action=scenario==4?0:1;w.stat_index=scenario==6?3:1;
    w.controller_rawcode=scenario==6?0x41497363u:0x41497872u;
    target.value=350.0f;w.target_bits=target.bits;
    cmd.specific_handler=(void *)GetProcAddress(GetModuleHandleW(L"ntdll.dll"),"__C_specific_handler");
    if(!cmd.specific_handler)return 1020;
    cmd.work=&w;g_dispatch=&cmd;BridgeStatDetailsQuery();g_dispatch=0;
    after.bits=w.after[w.stat_index];
    if(scenario==4)return w.error || !w.completed || w.changed || after.value!=50.0f ?1021:0;
    if(scenario==2)return w.error==275 && !w.completed && !w.changed && !critical_test_sets?0:1022;
    if(scenario==7)return w.error==277 && !w.completed && !w.changed && !critical_test_sets?0:1029;
    if(scenario==3)return w.error==269 && !w.completed && !w.changed &&
        critical_test_damage[0]==25.0f && critical_test_damage[1]==50.0f?0:1023;
    if(scenario==5)return w.error==273 && !w.completed && !w.changed &&
        critical_test_damage[0]==350.0f?0:1028;
    if(w.error || !w.completed || !w.changed || after.value!=350.0f)return 1024;
    if(critical_test_damage[0]!=350.0f)return 1025;
    if(critical_test_damage[1]!=(scenario==1?400.0f:350.0f))return 1026;
    if(critical_test_chance[0]!=20.0f || critical_test_chance[1]!=(scenario==1?0.0f:30.0f))return 1027;
    return 0;
}

static int extension_snapshot_fixture_occupied;
static int32_t extension_snapshot_fixture_size(uint64_t unit) {(void)unit;return 30;}
static uint64_t extension_snapshot_fixture_item(uint64_t unit,int32_t slot) {
    (void)unit;return extension_snapshot_fixture_occupied && slot==0 ? 0x100900 : 0;
}
static uint64_t extension_snapshot_fixture_slot(int32_t slot) {return (uint64_t)slot;}
static uint64_t extension_snapshot_fixture_equipment(uint64_t unit,uint64_t slot) {
    return extension_snapshot_fixture_item(unit,(int32_t)slot);
}
static uint32_t extension_snapshot_fixture_type(uint64_t item) {(void)item;return 0x65626f69;}
static int32_t extension_snapshot_fixture_charges(uint64_t item) {(void)item;return 7;}
static uint64_t extension_snapshot_fixture_kind(uint64_t item) {(void)item;return 4;}
__declspec(dllexport) uint32_t BridgeExtensionSnapshotReuseTest(void) {
    ExtensionWork w={0};uint32_t i;
    w.target_unit=0x100000;w.bag_size_fn=extension_snapshot_fixture_size;
    w.bag_item=extension_snapshot_fixture_item;w.slot_enum=extension_snapshot_fixture_slot;
    w.equipment_item=extension_snapshot_fixture_equipment;w.item_type=extension_snapshot_fixture_type;
    w.item_charges=extension_snapshot_fixture_charges;w.item_equipment_type=extension_snapshot_fixture_kind;
    extension_snapshot_fixture_occupied=1;
    if(!ExtensionSnapshot(&w) || w.bag[0].charges!=7 || w.equipment[0].equipment_type!=4)return 1;
    extension_snapshot_fixture_occupied=0;
    if(!ExtensionSnapshot(&w))return 2;
    for(i=0;i<30;++i)if(w.bag[i].handle || w.bag[i].rawcode || w.bag[i].charges || w.bag[i].equipment_type)return 3;
    for(i=0;i<9;++i)if(w.equipment[i].handle || w.equipment[i].rawcode || w.equipment[i].charges || w.equipment[i].equipment_type)return 4;
    return 0;
}

static int32_t fixture_screen_x, fixture_screen_y;
static HHOOK WINAPI fixture_install_fault(int kind,HOOKPROC callback,HINSTANCE module,DWORD tid){
    (void)kind;(void)callback;(void)module;(void)tid;
    RaiseException(0xe0420010u,0,0,0);return NULL;
}
static HHOOK WINAPI fixture_install_null(int kind,HOOKPROC callback,HINSTANCE module,DWORD tid){
    (void)kind;(void)callback;(void)module;(void)tid;
    SetLastError(ERROR_MOD_NOT_FOUND);return NULL;
}
__declspec(dllexport) uint32_t BridgeInstallFaultTest(void){
    BridgeCommand cmd={0};
    cmd.specific_handler=(void *)GetProcAddress(GetModuleHandleW(L"ntdll.dll"),"__C_specific_handler");
    cmd.get_error=GetLastError;cmd.set_hook=fixture_install_fault;
    cmd.hook_kind=WH_CALLWNDPROC;
    BridgeInstall(&cmd);
    if(cmd.stage!=2 || cmd.query_result!=0x105 || cmd.exception_code!=0xe0420010u ||
       bridge_fault.magic!=0x24268012u || bridge_fault.code!=0xe0420010u || !bridge_fault.instruction){
        g_dispatch=0;return 1201;
    }
    cmd.exception_code=0;cmd.set_hook=fixture_install_null;
    BridgeInstall(&cmd);g_dispatch=0;
    return cmd.stage==2 && cmd.query_result==0x106 && cmd.last_error==126 &&
        !cmd.exception_code && !bridge_fault.magic ? 0 : 1202;
}
#ifdef BRIDGE_DIAGNOSTIC
static int cooldown_test_level,cooldown_test_case,cooldown_test_starts;
static uint8_t cooldown_test_add(uint64_t unit,uint32_t code){
    (void)unit;(void)code;cooldown_test_level=1;return 1;
}
static uint8_t cooldown_test_remove(uint64_t unit,uint32_t code){
    (void)unit;(void)code;cooldown_test_level=0;return 1;
}
static int32_t cooldown_test_get(uint64_t unit,uint32_t code){
    (void)unit;(void)code;return cooldown_test_level;
}
static int32_t cooldown_test_set(uint64_t unit,uint32_t code,int32_t level){
    (void)unit;(void)code;return cooldown_test_level=level;
}
static void cooldown_test_start(uint64_t unit,uint32_t code,float *duration){
    (void)unit;(void)code;++cooldown_test_starts;
    if(cooldown_test_case==2)RaiseException(0xe0420003u,0,0,0);
    if(!duration || *duration!=10.0f)RaiseException(0xe0420004u,0,0,0);
}
static uint32_t cooldown_test_base(uint64_t unit,uint32_t code,int32_t level){
    (void)unit;(void)code;(void)level;return 0x40f00000u; /* 7.5f */
}
static uint32_t cooldown_test_remaining(uint64_t unit,uint32_t code){
    (void)unit;(void)code;return cooldown_test_starts?0x41200000u:0;
}
__declspec(dllexport) uint32_t BridgeCooldownContractTest(uint32_t scenario){
    CooldownProbeWork w={0};BridgeCommand cmd={0};
    fixture_count=1;fixture_scenario=0;fixture_type_calls=0;fixture_levels[0]=10;
    cooldown_test_case=scenario;cooldown_test_level=scenario==1;cooldown_test_starts=0;
    w.selection.local_player=fixture_player;w.selection.create_group=fixture_group;
    w.selection.enum_selected=fixture_enum;w.selection.first_of_group=fixture_first;
    w.selection.remove_from_group=fixture_remove;w.selection.destroy_group=fixture_destroy;
    w.selection.unit_type_id=fixture_type;w.selection.hero_level=fixture_level;
    w.add=cooldown_test_add;w.remove=cooldown_test_remove;w.get_level=cooldown_test_get;
    w.set_level=cooldown_test_set;w.start=cooldown_test_start;
    w.cooldown=cooldown_test_base;w.remaining=cooldown_test_remaining;
    w.ability=0x41487463;w.order=1;w.target_unit=0x100000;
    cmd.work=&w;cmd.specific_handler=(void *)GetProcAddress(GetModuleHandleW(L"ntdll.dll"),"__C_specific_handler");
    g_dispatch=&cmd;BridgeCooldownProbeQuery();g_dispatch=0;
    if(scenario==1)return w.error==10 && cooldown_test_level==1 && !cooldown_test_starts?0:1101;
    if(scenario==2)return w.error==0xe0420003u && !cooldown_test_level && w.reserved[1]==5?0:1102;
    return !w.error && w.completed==1 && w.base==7.5f && w.remaining_after==10.0f &&
        !cooldown_test_level && cooldown_test_starts==1?0:1103;
}
#endif
static int32_t fixture_get_screen_x(void) { return fixture_screen_x; }
static int32_t fixture_get_screen_y(void) { return fixture_screen_y; }
__declspec(dllexport) uint64_t BridgeScreenTestRun(ScreenMouseWork *w, int32_t x, int32_t y, int error) {
    static BridgeCommand cmd;
    fixture_screen_x = x; fixture_screen_y = y;
    cmd.work = w; cmd.tls_value = w->expected_tls; g_dispatch = &cmd;
    w->get_x = fixture_get_screen_x;
    w->get_y = fixture_get_screen_y;
    w->error = (int32_t)error;
    return BridgeScreenMouseQuery();
}
