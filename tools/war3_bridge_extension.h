/* Warcraft III 3.0 expanded bag, equipment, and talent inspection. */
typedef struct ExtensionItemRow {
    uint64_t handle;
    uint32_t rawcode;
    int32_t charges;
    uint32_t equipment_type;
    uint32_t reserved;
} ExtensionItemRow;
typedef struct ExtensionWork {
    SelectionWork selection;
    int32_t (*bag_size_fn)(uint64_t);
    uint64_t (*bag_item)(uint64_t,int32_t);
    uint64_t (*slot_enum)(int32_t);
    uint64_t (*equipment_item)(uint64_t,uint64_t);
    uint64_t (*unequip_slot)(uint64_t,uint64_t);
    uint32_t (*item_type)(uint64_t);
    int32_t (*item_charges)(uint64_t);
    int32_t (*ability_level)(uint64_t,uint32_t);
    uint64_t (*add_item_by_id)(uint64_t,uint32_t);
    uint8_t (*add_item)(uint64_t,uint64_t);
    uint8_t (*equip_item)(uint64_t,uint64_t);
    void (*set_item_charges)(uint64_t,int32_t);
    void (*unit_remove_item)(uint64_t,uint64_t);
    uint32_t (*unit_x)(uint64_t);
    uint32_t (*unit_y)(uint64_t);
    uint64_t (*item_equipment_type)(uint64_t);
    void (*remove_item)(uint64_t);
    void *expected_tls;
    uint64_t target_unit;
    uint64_t item_handle;
    uint32_t action,slot,item_rawcode,ability_count,error,completed,changed,bag_size;
    uint32_t removed_rawcode,reserved;
    uint32_t ability_rawcodes[24];
    int32_t ability_levels[24];
    ExtensionItemRow bag[30],equipment[9];
} ExtensionWork;
_Static_assert(sizeof(ExtensionWork)==1808,"ExtensionWork ABI");
__declspec(dllexport) const uint32_t extension_batch_abi[3]={0x24268039u,216u,1808u};

static int ExtensionSnapshot(ExtensionWork *w) {
    int32_t i,size=w->bag_size_fn(w->target_unit);
    if(size<0 || size>30)return 0;
    w->bag_size=(uint32_t)size;
    for(i=0;i<30;++i){
        uint64_t item=i<size ? w->bag_item(w->target_unit,i) : 0;
        w->bag[i].handle=item;
        if(item){w->bag[i].rawcode=w->item_type(item);w->bag[i].charges=w->item_charges(item);
                 w->bag[i].equipment_type=(uint32_t)w->item_equipment_type(item);}
    }
    for(i=0;i<9;++i){
        uint64_t item=w->equipment_item(w->target_unit,w->slot_enum(i));
        w->equipment[i].handle=item;
        if(item){w->equipment[i].rawcode=w->item_type(item);w->equipment[i].charges=w->item_charges(item);
                 w->equipment[i].equipment_type=(uint32_t)w->item_equipment_type(item);}
    }
    for(i=0;i<(int32_t)w->ability_count;++i)
        w->ability_levels[i]=w->ability_level(w->target_unit,w->ability_rawcodes[i]);
    return 1;
}

__declspec(dllexport) uint64_t BridgeExtensionQuery(void) {
    ExtensionWork *w=(ExtensionWork *)g_dispatch->work;
    uint32_t count,matches=0,i,before_level=0;
    if(!w || w->expected_tls!=g_dispatch->tls_value || w->action>8 ||
       w->ability_count>24 || (w->action==1 && !w->item_rawcode) ||
       (w->action==2 && w->slot>=9)){if(w)w->error=220;return 0;}
    count=(uint32_t)BridgeSelect();
    if(w->selection.error || !w->selection.destroyed || !count){w->error=221;return count;}
    if(!w->target_unit)w->target_unit=w->selection.rows[0].unit;
    for(i=0;i<count;++i)if(w->selection.rows[i].unit==w->target_unit)++matches;
    if(matches!=1){w->error=222;return count;}
    __try {
        if(w->action==1){
            uint64_t item=w->add_item_by_id(w->target_unit,w->item_rawcode);
            if(!item){w->error=223;return count;}
            w->changed=1;
        }else if(w->action==2){
            uint32_t occupied=0;
            int32_t bag_size=w->bag_size_fn(w->target_unit);
            uint64_t before=w->equipment_item(w->target_unit,w->slot_enum((int32_t)w->slot));
            uint64_t removed;
            if(bag_size<0 || bag_size>30){w->error=232;return count;}
            for(i=0;i<(uint32_t)bag_size;++i)if(w->bag_item(w->target_unit,(int32_t)i))++occupied;
            if(occupied>=(uint32_t)bag_size){w->error=233;return count;}
            if(!before){w->error=224;return count;}
            w->removed_rawcode=w->item_type(before);
            removed=w->unequip_slot(w->target_unit,w->slot_enum((int32_t)w->slot));
            if(removed!=before || w->equipment_item(w->target_unit,w->slot_enum((int32_t)w->slot))==before){
                w->error=225;return count;
            }
            w->changed=1;
        }else if(w->action==3){
            if(!w->item_handle || w->item_type(w->item_handle)!=w->item_rawcode){w->error=227;return count;}
            if(!w->add_item(w->target_unit,w->item_handle)){w->error=228;return count;}
            w->changed=1;
        }else if(w->action==4){
            uint32_t found=0;
            if(!w->item_handle || w->item_type(w->item_handle)!=w->item_rawcode){w->error=230;return count;}
            if(!ExtensionSnapshot(w)){w->error=226;return count;}
            for(i=0;i<30;++i)if(w->bag[i].handle==w->item_handle)++found;
            if(found!=1){w->error=234;return count;}
            w->equip_item(w->target_unit,w->item_handle);
            w->changed=1;
        }else if(w->action==5){
            uint32_t found=0;
            if(!ExtensionSnapshot(w)){w->error=226;return count;}
            for(i=0;i<30;++i)if(w->bag[i].handle==w->item_handle && w->bag[i].rawcode==w->item_rawcode)++found;
            if(found!=1){w->error=235;return count;}
            w->unit_remove_item(w->target_unit,w->item_handle);
            w->changed=1;
        }else if(w->action==6){
            uint32_t found=0;
            if(!ExtensionSnapshot(w)){w->error=226;return count;}
            for(i=0;i<30;++i)if(w->bag[i].handle==w->item_handle && w->bag[i].rawcode==w->item_rawcode)++found;
            if(found!=1){w->error=237;return count;}
            w->set_item_charges(w->item_handle,(int32_t)w->slot);w->changed=1;
        }else if(w->action==7){
            if(w->ability_count!=1){w->error=238;return count;}
            before_level=(uint32_t)w->ability_level(w->target_unit,w->ability_rawcodes[0]);
            w->add_item_by_id(w->target_unit,w->item_rawcode);w->changed=1;
        }else if(w->action==8){
            uint32_t found=0;
            if(!ExtensionSnapshot(w)){w->error=226;return count;}
            for(i=0;i<30;++i)if(w->bag[i].handle==w->item_handle && w->bag[i].rawcode==w->item_rawcode)++found;
            if(found!=1){w->error=242;return count;}
            w->remove_item(w->item_handle);w->changed=1;
        }
        if(!ExtensionSnapshot(w)){w->error=226;return count;}
        if(w->action==3){
            uint32_t found=0;
            for(i=0;i<30;++i)if(w->bag[i].handle==w->item_handle)++found;
            for(i=0;i<9;++i)if(w->equipment[i].handle==w->item_handle)++found;
            if(found!=1){w->error=229;return count;}
        }
        if(w->action==4){
            uint32_t found=0;
            for(i=0;i<9;++i)if(w->equipment[i].handle==w->item_handle)++found;
            if(found!=1){w->error=231;return count;}
        }
        if(w->action==5){
            for(i=0;i<30;++i)if(w->bag[i].handle==w->item_handle){w->error=239;return count;}
        }
        if(w->action==6){
            uint32_t found=0;
            for(i=0;i<30;++i)if(w->bag[i].handle==w->item_handle && w->bag[i].charges==(int32_t)w->slot)++found;
            if(found!=1){w->error=240;return count;}
        }
        if(w->action==7 && w->ability_levels[0]!=(int32_t)(before_level+1)){w->error=241;return count;}
        if(w->action==8){
            for(i=0;i<30;++i)if(w->bag[i].handle==w->item_handle){w->error=243;return count;}
        }
        w->completed=1;
    } __except(EXCEPTION_EXECUTE_HANDLER) {w->error=GetExceptionCode();}
    return count;
}
