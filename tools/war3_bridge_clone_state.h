/* Stateful clone extension. Every item is owned by the new unit and verified
   in its original inventory area; talent references are remapped to new skills. */
#define CLONE_STATE_ITEMS 45u
#define CLONE_STATE_ABILITIES 128u
typedef struct CloneStateItem {
    uint64_t source,clone;
    uint32_t rawcode;int32_t charges;
    uint32_t equipment_type,verified;
} CloneStateItem;
typedef struct CloneStateAbility {
    uint64_t full;
    uint32_t rawcode,kind;
    int32_t level;
    uint32_t item_owned;
} CloneStateAbility;
typedef struct CloneStateRow {
    uint32_t classic_size,bag_size,ability_count,talent_code;
    uint32_t talent_tiers,talent_points,stage,verified;
    uint32_t inventory_code,equipment_code;
    uint64_t controller_data;
    uint64_t talent_records[6];
    uint32_t talent_codes[6],talent_flags[6];
    CloneStateItem items[45];
    CloneStateAbility abilities[128];
} CloneStateRow;
_Static_assert(sizeof(CloneStateItem)==32,"CloneStateItem ABI");
_Static_assert(sizeof(CloneStateAbility)==24,"CloneStateAbility ABI");
_Static_assert(sizeof(CloneStateRow)==4656,"CloneStateRow ABI");
typedef struct CloneStateWork {
    CloneBoundWork bound;
    int32_t (*inventory_size)(uint64_t),(*bag_size)(uint64_t);
    uint64_t (*bag_item)(uint64_t,int32_t),(*slot_enum)(int32_t),(*equipped)(uint64_t,uint64_t);
    uint8_t (*add_existing)(uint64_t,uint64_t),(*move_slot)(uint64_t,uint64_t,int32_t);
    uint8_t (*equip)(uint64_t,uint64_t);
    uint64_t (*unequip)(uint64_t,uint64_t);
    uint64_t (*ability)(uint64_t,uint32_t);
    uint32_t (*handle_id)(uint64_t);
    uint64_t (*item_kind)(uint64_t);
    uint32_t definition_class,definition_levels,talent_points,talent_flags;
    uint32_t completed,reserved;
    CloneStateRow rows[24];
} CloneStateWork;
_Static_assert(sizeof(CloneStateWork)==175992,"CloneStateWork ABI");
__declspec(dllexport) const uint32_t clone_state_abi[3]={0x2426807cu,216u,175992u};

static uint64_t clone_state_data(CloneStateWork*s,uint64_t native,uint32_t code,int ability) {
    uint64_t owner=BridgeProfileResolveOwner(s->bound.base,s->handle_id(native),0);
    uint64_t data=owner?*(uint64_t *)(uintptr_t)(owner+bridge_profile.owner_data):0;
    uint32_t offset=ability?bridge_profile.ability_rawcode:bridge_profile.object_rawcode;
    if(!data || *(uint32_t *)(uintptr_t)(data+offset)!=code)return 0;
    uint64_t full=*(uint64_t *)(uintptr_t)(data+bridge_profile.object_handle);
    if(BridgeProfileResolveOwner(s->bound.base,full,1)!=owner)return 0;
    return data;
}
static uint32_t clone_state_class(CloneStateWork*s,uint64_t data,uint32_t code) {
    uint64_t cache=*(uint64_t *)(uintptr_t)(data+bridge_profile.ability_cache);
    uint64_t override=*(uint64_t *)(uintptr_t)(data+bridge_profile.ability_cache+8);
    cache=override?override:cache;
    if(!cache)return 0;
    /* Definition class and level-count offsets are supplied by the adapter. */
    if(*(uint32_t *)(uintptr_t)(cache+s->definition_class+4)!=code)return 0;
    return *(uint32_t *)(uintptr_t)(cache+s->definition_class);
}
static uint64_t clone_state_item_at(CloneStateWork*s,uint64_t unit,uint32_t index) {
    CloneWork*w=&s->bound.clone;
    if(index<6)return w->item_in_slot(unit,(int32_t)index);
    if(index<36)return index-6<(uint32_t)s->bag_size(unit)?s->bag_item(unit,(int32_t)index-6):0;
    return s->equipped(unit,s->slot_enum((int32_t)index-36));
}
static int clone_state_prepare(CloneStateWork*s,uint32_t count) {
    CloneWork*w=&s->bound.clone;
    if(!s->inventory_size || !s->bag_size || !s->bag_item || !s->slot_enum || !s->equipped ||
       !s->add_existing || !s->move_slot || !s->equip || !s->unequip || !s->ability ||
       !s->handle_id || !s->item_kind || !s->definition_class || !s->definition_levels ||
       !s->talent_points || s->talent_flags>=bridge_profile.talent_record_stride ||
       s->completed || s->reserved){w->error=780;return 0;}
    for(uint32_t i=0;i<count;++i){
        CloneStateRow*r=&s->rows[i];uint64_t source=w->selection.rows[i].unit;
        int32_t classic=s->inventory_size(source),bag=s->bag_size(source);
        r->stage=1;
        if(classic<0 || classic>6 || bag<0 || bag>30){w->error=781;return 0;}
        r->classic_size=classic;r->bag_size=bag;
        for(uint32_t j=0;j<45;++j){
            CloneStateItem*item=&r->items[j];item->source=clone_state_item_at(s,source,j);
            if(!item->source)continue;
            for(uint32_t k=0;k<j;++k)if(r->items[k].source==item->source){w->error=782;return 0;}
            item->rawcode=w->item_type(item->source);item->charges=w->item_charges(item->source);
            item->equipment_type=(uint32_t)s->item_kind(item->source);
            if(!item->rawcode || item->charges<0){w->error=782;return 0;}
        }
        uint32_t j;
        for(j=0;j<128;++j){
            uint64_t ability=w->ability_by_index(source,j);if(!ability)break;
            CloneStateAbility*a=&r->abilities[r->ability_count++];
            a->rawcode=w->ability_id(ability);a->level=w->ability_level(source,a->rawcode);
            uint64_t data=clone_state_data(s,ability,a->rawcode,1);
            if(!data || *(uint64_t *)(uintptr_t)(data+bridge_profile.ability_owner)!=s->bound.sources[i].object){w->error=783;return 0;}
            a->full=*(uint64_t *)(uintptr_t)(data+bridge_profile.ability_handle);
            a->kind=clone_state_class(s,data,a->rawcode);
            if(a->kind==0x41496e78u)r->inventory_code=a->rawcode;
            if(a->kind==0x41457175u)r->equipment_code=a->rawcode;
            if(a->kind==0x4154616cu){ /* ATal */
                if(r->talent_code){w->error=784;return 0;}
                r->talent_code=a->rawcode;r->controller_data=data;
                uint64_t cache=*(uint64_t *)(uintptr_t)(data+bridge_profile.ability_cache+8);
                if(!cache)cache=*(uint64_t *)(uintptr_t)(data+bridge_profile.ability_cache);
                r->talent_tiers=*(uint32_t *)(uintptr_t)(cache+s->definition_levels);
                r->talent_points=*(uint32_t *)(uintptr_t)(data+s->talent_points);
                if(!r->talent_tiers || r->talent_tiers>6 || r->talent_points>18){w->error=784;return 0;}
                for(uint32_t tier=0;tier<r->talent_tiers;++tier){
                    uint64_t record=data+bridge_profile.talent_records+(uint64_t)tier*bridge_profile.talent_record_stride;
                    uint64_t full=*(uint64_t *)(uintptr_t)record;r->talent_records[tier]=full;
                    r->talent_flags[tier]=*(uint32_t *)(uintptr_t)(record+s->talent_flags);
                    if(full==UINT64_MAX)continue;
                    uint64_t owner=BridgeProfileResolveOwner(s->bound.base,full,1);
                    uint64_t selected=owner?*(uint64_t *)(uintptr_t)(owner+bridge_profile.owner_data):0;
                    if(!selected || *(uint64_t *)(uintptr_t)(selected+bridge_profile.ability_owner)!=s->bound.sources[i].object){w->error=784;return 0;}
                    r->talent_codes[tier]=*(uint32_t *)(uintptr_t)(selected+bridge_profile.ability_rawcode);
                }
            }
        }
        if(j==128 && w->ability_by_index(source,128)){w->error=75;return 0;}
        /* Item effects, including the carrier's AIni/AEqu/ATal components,
           must be supplied by that item rather than attached a second time. */
        for(uint32_t item=0;item<45;++item){
            if(!r->items[item].source)continue;
            uint32_t k;
            for(k=0;k<128;++k){
                uint64_t ability=w->item_ability_by_index(r->items[item].source,k);if(!ability)break;
                uint32_t code=w->ability_id(ability);
                for(uint32_t n=0;n<r->ability_count;++n)if(r->abilities[n].rawcode==code)r->abilities[n].item_owned=1;
            }
            if(k==128 && w->item_ability_by_index(r->items[item].source,128)){w->error=75;return 0;}
        }
    }
    return 1;
}
static int clone_state_item_valid(CloneStateWork*s,uint32_t row,uint32_t index) {
    CloneWork*w=&s->bound.clone;CloneStateRow*r=&s->rows[row];CloneStateItem*item=&r->items[index];
    uint64_t source=w->selection.rows[row].unit;
    return clone_state_item_at(s,source,index)==item->source && (!item->source ||
        (w->item_type(item->source)==item->rawcode && w->item_charges(item->source)==item->charges));
}
static int clone_state_make_item(CloneStateWork*s,uint32_t row,uint32_t index) {
    CloneWork*w=&s->bound.clone;CloneRow*copy=&w->rows[row];CloneStateItem*item=&s->rows[row].items[index];
    if(!item->source)return 1;
    if(!clone_state_item_valid(s,row,index)){w->error=785;return 0;}
    uint64_t created=w->add_item(copy->clone,item->rawcode);
    /* Do not claim or delete a source item returned by campaign triggers. */
    for(uint32_t r=0;r<w->selection.count;++r)for(uint32_t k=0;k<45;++k)
        if(created && created==s->rows[r].items[k].source){w->error=786;return 0;}
    if(!created){w->error=68;return 0;}
    for(uint32_t r=0;r<=row;++r)for(uint32_t k=0;k<45;++k)
        if(created==s->rows[r].items[k].clone){w->error=786;return 0;}
    item->clone=created;++copy->created_items;
    if(w->item_type(created)!=item->rawcode){w->error=68;return 0;}
    if(w->item_charges(created)!=item->charges)w->set_item_charges(created,item->charges);
    if(w->item_charges(created)!=item->charges){w->error=69;return 0;}
    return 1;
}
static int clone_state_classic(CloneStateWork*s,uint32_t row) {
    CloneWork*w=&s->bound.clone;CloneStateRow*r=&s->rows[row];uint64_t unit=w->rows[row].clone;r->stage=2;
    if(s->inventory_size(unit)!=(int32_t)r->classic_size){w->error=787;return 0;}
    /* Creation triggers may give an item; preserve it and report a conflict. */
    for(uint32_t j=0;j<45;++j)if(clone_state_item_at(s,unit,j)){w->error=788;return 0;}
    for(uint32_t j=0;j<6;++j){
        if(!clone_state_make_item(s,row,j))return 0;
        CloneStateItem*item=&r->items[j];if(!item->source)continue;
        if(w->item_in_slot(unit,j)!=item->clone)s->move_slot(unit,item->clone,j);
        if(w->item_in_slot(unit,j)!=item->clone){w->error=789;return 0;}
        item->verified=1;++w->rows[row].item_count;
    }
    return 1;
}
static int clone_state_abilities(CloneStateWork*s,uint32_t row) {
    CloneWork*w=&s->bound.clone;CloneStateRow*r=&s->rows[row];CloneRow*copy=&w->rows[row];r->stage=3;
    for(uint32_t j=0;j<r->ability_count;++j){
        CloneStateAbility*a=&r->abilities[j];uint32_t code=a->rawcode;copy->reserved=code;
        /* Buff-class identity also covers renamed buffs whose code lacks B. */
        if(a->item_owned || clone_is_noncopyable_ability(code) || (a->kind>>24)=='B') {copy->reserved=0;continue;}
        int32_t actual=w->ability_level(copy->clone,code);
        if(!actual && a->level>0 && !s->ability(copy->clone,code)){
            w->add_ability(copy->clone,code);actual=w->ability_level(copy->clone,code);
        }
        if(a->level<=0){
            if(clone_has_ability(w,copy->clone,code)){copy->reserved=0;continue;}
            if(clone_ability_issue(w,copy,code,0,actual,65))continue;
            return 0;
        }
        if(actual<=0){if(clone_ability_issue(w,copy,code,a->level,actual,66))continue;return 0;}
        if(a->kind!=0x4154616cu && actual!=a->level && !clone_set_ability_level(w,copy->clone,code,a->level)){
            actual=w->ability_level(copy->clone,code);
            if(clone_ability_issue(w,copy,code,a->level,actual,67))continue;return 0;
        }
        ++copy->ability_count;copy->reserved=0;
    }
    return 1;
}
static int clone_state_extended(CloneStateWork*s,uint32_t row) {
    CloneWork*w=&s->bound.clone;CloneStateRow*r=&s->rows[row];uint64_t unit=w->rows[row].clone;r->stage=4;
    if(s->bag_size(unit)!=(int32_t)r->bag_size){w->error=790;return 0;}
    /* Equip in weapon-first order, then accessories, mirroring loadout restore. */
    static const uint32_t order[45]={0,1,2,3,4,5,42,43,36,37,38,39,40,41,44,
        6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35};
    for(uint32_t n=6;n<45;++n){
        uint32_t j=order[n];CloneStateItem*item=&r->items[j];if(!item->source)continue;
        if(!clone_state_make_item(s,row,j))return 0;
        uint32_t in_classic=0,in_bag=0;
        for(uint32_t k=0;k<6;++k)if(w->item_in_slot(unit,k)==item->clone)++in_classic;
        for(uint32_t k=0;k<r->bag_size;++k)if(s->bag_item(unit,k)==item->clone)++in_bag;
        if(!in_bag){
            uint64_t data=clone_state_data(s,item->clone,item->rawcode,0);
            if(!data){w->error=792;return 0;}
            if(in_classic)w->detach_item(unit,item->clone);
            uint32_t old_flags=*(uint32_t *)(uintptr_t)(data+bridge_profile.item_flags);
            uint32_t old_class=*(uint32_t *)(uintptr_t)(data+bridge_profile.item_class);
            uint32_t old_type=*(uint32_t *)(uintptr_t)(data+bridge_profile.item_equipment_type);
            __try {
                *(uint32_t *)(uintptr_t)(data+bridge_profile.item_flags)=old_flags|bridge_profile.item_equipment_mask;
                *(uint32_t *)(uintptr_t)(data+bridge_profile.item_class)=7;
                *(uint32_t *)(uintptr_t)(data+bridge_profile.item_equipment_type)=9;
                s->add_existing(unit,item->clone);
            }__finally {
                *(uint32_t *)(uintptr_t)(data+bridge_profile.item_flags)=
                    (*(uint32_t *)(uintptr_t)(data+bridge_profile.item_flags)&~bridge_profile.item_equipment_mask)|(old_flags&bridge_profile.item_equipment_mask);
                *(uint32_t *)(uintptr_t)(data+bridge_profile.item_class)=old_class;
                *(uint32_t *)(uintptr_t)(data+bridge_profile.item_equipment_type)=old_type;
            }
            in_bag=0;for(uint32_t k=0;k<r->bag_size;++k)if(s->bag_item(unit,k)==item->clone)++in_bag;
            if(in_bag!=1){w->error=792;return 0;}
        }
        if(j>=36){
            uint64_t native=s->ability(unit,r->equipment_code);
            uint64_t data=native?clone_state_data(s,native,r->equipment_code,1):0;
            uint64_t records=data?*(uint64_t *)(uintptr_t)(data+bridge_profile.equipment_records):0;
            if(!records || *(uint64_t *)(uintptr_t)(data+bridge_profile.equipment_count)!=9 ||
               *(uint64_t *)(uintptr_t)(data+bridge_profile.equipment_capacity)<9){w->error=791;return 0;}
            uint64_t saved[9];uint32_t flags[9];
            for(uint32_t k=0;k<9;++k){
                uint64_t address=records+(uint64_t)k*bridge_profile.equipment_record_stride;
                saved[k]=*(uint64_t *)(uintptr_t)address;
                flags[k]=*(uint32_t *)(uintptr_t)(address+bridge_profile.equipment_record_state);
                *(uint64_t *)(uintptr_t)address=UINT64_MAX;
                *(uint32_t *)(uintptr_t)(address+bridge_profile.equipment_record_state)=0;
            }
            uint32_t equipped=s->equip(unit,item->clone),found=0;
            for(uint32_t k=0;k<9;++k)if(s->equipped(unit,s->slot_enum(k))==item->clone)++found;
            uint64_t item_data=clone_state_data(s,item->clone,item->rawcode,0);
            for(uint32_t k=0;k<9;++k){
                uint64_t address=records+(uint64_t)k*bridge_profile.equipment_record_stride;
                *(uint64_t *)(uintptr_t)address=saved[k];
                *(uint32_t *)(uintptr_t)(address+bridge_profile.equipment_record_state)=flags[k];
            }
            if(!equipped || found!=1 || !item_data || saved[j-36]!=UINT64_MAX){w->error=791;return 0;}
            uint64_t address=records+(uint64_t)(j-36)*bridge_profile.equipment_record_stride;
            *(uint64_t *)(uintptr_t)address=*(uint64_t *)(uintptr_t)(item_data+bridge_profile.object_handle);
            *(uint32_t *)(uintptr_t)(address+bridge_profile.equipment_record_state)=0;
            if(s->equipped(unit,s->slot_enum(j-36))!=item->clone){w->error=791;return 0;}
        }else{
            /* Keep exact bag positions, including holes, using the existing
               AInx inventory-record adapter rather than sharing source IDs. */
            if(s->bag_item(unit,j-6)!=item->clone){
                uint64_t native=s->ability(unit,r->inventory_code);
                uint64_t data=native?clone_state_data(s,native,r->inventory_code,1):0;
                uint64_t records=data?*(uint64_t *)(uintptr_t)(data+bridge_profile.equipment_records):0;
                if(!records || *(uint64_t *)(uintptr_t)(data+bridge_profile.equipment_count)!=r->bag_size){w->error=792;return 0;}
                uint32_t actual=30;for(uint32_t k=0;k<r->bag_size;++k)if(s->bag_item(unit,k)==item->clone)actual=k;
                uint64_t target=records+(uint64_t)(j-6)*bridge_profile.equipment_record_stride;
                if(actual==30 || *(uint64_t *)(uintptr_t)target!=UINT64_MAX){w->error=792;return 0;}
                uint64_t old=records+(uint64_t)actual*bridge_profile.equipment_record_stride;
                *(uint64_t *)(uintptr_t)target=*(uint64_t *)(uintptr_t)old;
                *(uint32_t *)(uintptr_t)(target+bridge_profile.equipment_record_state)=*(uint32_t *)(uintptr_t)(old+bridge_profile.equipment_record_state);
                *(uint64_t *)(uintptr_t)old=UINT64_MAX;*(uint32_t *)(uintptr_t)(old+bridge_profile.equipment_record_state)=0;
                if(s->bag_item(unit,j-6)!=item->clone){w->error=792;return 0;}
            }
        }
        item->verified=1;++w->rows[row].item_count;
    }
    return 1;
}
static int clone_state_talents(CloneStateWork*s,uint32_t row) {
    CloneWork*w=&s->bound.clone;CloneStateRow*r=&s->rows[row];uint64_t unit=w->rows[row].clone;r->stage=5;
    if(!r->talent_code)return 1;
    uint64_t native=s->ability(unit,r->talent_code);
    uint64_t data=native?clone_state_data(s,native,r->talent_code,1):0;
    if(!data || clone_state_class(s,data,r->talent_code)!=0x4154616cu ||
       *(uint64_t *)(uintptr_t)(data+bridge_profile.ability_owner)!=s->bound.resolve_unit(unit)){w->error=793;return 0;}
    /* The level setter can reinitialize controller state. Set it first, then
       remap the records and copy the remaining-point counter. */
    for(uint32_t j=0;j<r->ability_count;++j)if(r->abilities[j].rawcode==r->talent_code){
        int32_t wanted=r->abilities[j].level;
        if(w->ability_level(unit,r->talent_code)!=wanted && !clone_set_ability_level(w,unit,r->talent_code,wanted)){
            if(!clone_ability_issue(w,&w->rows[row],r->talent_code,wanted,w->ability_level(unit,r->talent_code),67))return 0;
        }
    }
    if(clone_state_data(s,s->ability(unit,r->talent_code),r->talent_code,1)!=data){w->error=793;return 0;}
    for(uint32_t tier=0;tier<r->talent_tiers;++tier){
        uint64_t record=data+bridge_profile.talent_records+(uint64_t)tier*bridge_profile.talent_record_stride;
        uint64_t mapped=UINT64_MAX;
        if(r->talent_codes[tier]){
            uint64_t skill=s->ability(unit,r->talent_codes[tier]);
            uint64_t selected=skill?clone_state_data(s,skill,r->talent_codes[tier],1):0;
            if(!selected || *(uint64_t *)(uintptr_t)(selected+bridge_profile.ability_owner)!=s->bound.resolve_unit(unit)){w->error=794;return 0;}
            mapped=*(uint64_t *)(uintptr_t)(selected+bridge_profile.ability_handle);
            if(mapped==r->talent_records[tier]){w->error=794;return 0;}
        }
        *(uint64_t *)(uintptr_t)record=mapped;
        *(uint32_t *)(uintptr_t)(record+s->talent_flags)=r->talent_flags[tier];
        if(*(uint64_t *)(uintptr_t)record!=mapped || *(uint32_t *)(uintptr_t)(record+s->talent_flags)!=r->talent_flags[tier]){w->error=795;return 0;}
    }
    *(uint32_t *)(uintptr_t)(data+s->talent_points)=r->talent_points;
    if(*(uint32_t *)(uintptr_t)(data+s->talent_points)!=r->talent_points){w->error=795;return 0;}
    return 1;
}
static int clone_state_verify(CloneStateWork*s,uint32_t row) {
    CloneWork*w=&s->bound.clone;CloneStateRow*r=&s->rows[row];uint64_t unit=w->rows[row].clone;r->stage=6;
    for(uint32_t j=0;j<45;++j){
        CloneStateItem*item=&r->items[j];
        if(!clone_state_item_valid(s,row,j) || clone_state_item_at(s,unit,j)!=item->clone ||
           (item->clone && (w->item_type(item->clone)!=item->rawcode || w->item_charges(item->clone)!=item->charges))){w->error=796;return 0;}
    }
    /* Source talent records remain owned by the original unit throughout. */
    if(r->talent_code){
        if(*(uint32_t *)(uintptr_t)(r->controller_data+s->talent_points)!=r->talent_points){w->error=795;return 0;}
        for(uint32_t tier=0;tier<r->talent_tiers;++tier){
            uint64_t record=r->controller_data+bridge_profile.talent_records+(uint64_t)tier*bridge_profile.talent_record_stride;
            if(*(uint64_t *)(uintptr_t)record!=r->talent_records[tier] ||
               *(uint32_t *)(uintptr_t)(record+s->talent_flags)!=r->talent_flags[tier]){w->error=795;return 0;}
        }
    }
    r->verified=1;++s->completed;return 1;
}
static int clone_state_discard(CloneStateWork*s,uint32_t row) {
    CloneWork*w=&s->bound.clone;CloneRow*copy=&w->rows[row];int cleaned=1;
    for(uint32_t j=0;j<45;++j){
        uint64_t item=s->rows[row].items[j].clone;if(!item)continue;
        __try {
            if(w->item_type(item))w->remove_item(item);
            if(w->item_type(item))cleaned=0;
        }__except(BridgeExceptionFilter(GetExceptionInformation())) {cleaned=0;copy->pad=GetExceptionCode();}
    }
    /* Item cleanup already ran; the ordinary cleanup owns unit removal. */
    uint32_t count=copy->created_items;copy->created_items=0;
    if(!clone_discard_row(w,copy,0))cleaned=0;
    copy->created_items=count;if(!cleaned)copy->status=3;
    return cleaned;
}
