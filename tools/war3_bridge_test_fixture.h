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
    ++item_create_calls;if(item_case==1)return 0;
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
    if (slot<0 || slot>=item_sizes[i] || item_slots[i][slot] || index>=144 || item_case==7) return 0;
    ++item_create_calls;h=0x300000+(uint64_t)index*16;item_new_type[index]=type;item_new_charges[index]=1;item_slots[i][slot]=h;return 1;
}
__declspec(dllexport) uint64_t BridgeItemTestRun(ItemWork *w,int count,int scenario) {
    static BridgeCommand cmd;int i,j;
    if(count<0||count>24)return 0;
    fixture_count=count;fixture_scenario=0;fixture_type_calls=0;item_case=scenario;
    item_create_calls=item_set_calls=item_remove_calls=item_created_count=0;
    for(i=0;i<24;++i){
        fixture_levels[i]=i%3==0 ? 1 : 0;item_sizes[i]=scenario==5 ? 6 : i%3==0 ? 6 : 0;
        for(j=0;j<6;++j){item_original_charges[i][j]=1;item_slots[i][j]=item_sizes[i] && (j==0||scenario==5) ? 0x200000+i*16+j : 0;}
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
    return BridgeItemQuery();
}
__declspec(dllexport) int BridgeItemTestStat(int kind) {return kind==0 ? item_create_calls : kind==1 ? item_set_calls : item_remove_calls;}

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

static int spawn_case, spawn_create_calls, spawn_remove_calls;
static uint32_t spawn_requested, spawn_actual, spawn_x_bits, spawn_y_bits, spawn_facing_bits;
static uint64_t spawn_create(uint64_t player, uint32_t rawcode, float x, float y, float facing) {
    union { float value; uint32_t bits; } xb, yb, fb;
    (void)player;
    xb.value = x; yb.value = y; fb.value = facing;
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

static int32_t fixture_screen_x, fixture_screen_y;
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
