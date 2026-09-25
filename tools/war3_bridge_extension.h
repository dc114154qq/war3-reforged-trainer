/* Warcraft III 3.0 expanded bag, equipment, and talent inspection. */
#ifdef BRIDGE_DIAGNOSTIC
static void ExtensionProbeCopy(uint8_t *out,const uint8_t *in,uint32_t size){for(uint32_t i=0;i<size;++i)out[i]=in[i];}
#endif
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
    uint32_t (*set_item_integer)(uint64_t,uint32_t,uint32_t);
    uint64_t (*get_unit_ability)(uint64_t,uint32_t);
    uint32_t (*get_ability_id)(uint64_t);
    uint32_t (*get_handle_id)(uint64_t);
    uint64_t resolver_base;
    void *expected_tls;
    uint64_t target_unit;
    uint64_t item_handle;
    uint32_t action,slot,item_rawcode,ability_count,error,completed,changed,bag_size;
    uint32_t removed_rawcode,reserved;
    uint32_t ability_rawcodes[24];
    int32_t ability_levels[24];
    ExtensionItemRow bag[30],equipment[9];
} ExtensionWork;
_Static_assert(sizeof(ExtensionWork)==1848,"ExtensionWork ABI");
__declspec(dllexport) const uint32_t extension_batch_abi[3]={0x2426803Au,216u,1848u};

static uint64_t ExtensionResolveHandle(ExtensionWork *w, uint32_t low) {
    uint64_t root, table, owner, slot;
    uint32_t index, offset, count;
    if (!w->resolver_base || !low) return 0;
    index = low & 0x7fffffffu;
    offset = (low & 0x80000000u) ? 0x50u : 0x18u;
    __try {
        root = *(uint64_t *)(uintptr_t)(w->resolver_base + 0x2f807f0u);
        if (!root) return 0;
        table = *(uint64_t *)(uintptr_t)(root + offset);
        count = *(uint32_t *)(uintptr_t)(root + offset + 0x18u);
        if (!table || index >= count || count > 0x10000000u) return 0;
        slot = table + (uint64_t)index * 16u;
        if (*(uint32_t *)(uintptr_t)slot != 0xfffffffeu) return 0;
        owner = *(uint64_t *)(uintptr_t)(slot + 8u);
        if (!owner) return 0;
        return owner;
    } __except(EXCEPTION_EXECUTE_HANDLER) { return 0; }
}

static int ExtensionSnapshot(ExtensionWork *w) {
    int32_t i,size=w->bag_size_fn(w->target_unit);
    if(size<0 || size>30)return 0;
    w->bag_size=(uint32_t)size;
    for(i=0;i<30;++i){
        uint64_t item=i<size ? w->bag_item(w->target_unit,i) : 0;
        w->bag[i].rawcode=0;w->bag[i].charges=0;
        w->bag[i].equipment_type=0;w->bag[i].reserved=0;
        w->bag[i].handle=item;
        if(item){w->bag[i].rawcode=w->item_type(item);w->bag[i].charges=w->item_charges(item);
                 w->bag[i].equipment_type=(uint32_t)w->item_equipment_type(item);}
    }
    for(i=0;i<9;++i){
        uint64_t item=w->equipment_item(w->target_unit,w->slot_enum(i));
        w->equipment[i].rawcode=0;w->equipment[i].charges=0;
        w->equipment[i].equipment_type=0;w->equipment[i].reserved=0;
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
    uint32_t count,matches=0,i;
    if(!w || w->expected_tls!=g_dispatch->tls_value || w->action>12 ||
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
            uint64_t item;
            if(w->ability_count!=1){w->error=238;return count;}
            item=w->add_item_by_id(w->target_unit,w->item_rawcode);
            if(!item){w->error=241;return count;}
            w->changed=1;
        }else if(w->action==8){
            uint32_t found=0;
            if(!ExtensionSnapshot(w)){w->error=226;return count;}
            for(i=0;i<30;++i)if(w->bag[i].handle==w->item_handle && w->bag[i].rawcode==w->item_rawcode)++found;
            if(found!=1){w->error=242;return count;}
            w->remove_item(w->item_handle);w->changed=1;
        }else if(w->action==9){
            uint32_t found=0,old_type;
            if(w->slot>9 || !ExtensionSnapshot(w)){w->error=244;return count;}
            for(i=0;i<30;++i)if(w->bag[i].handle==w->item_handle && w->bag[i].rawcode==w->item_rawcode)++found;
            for(i=0;i<9;++i)if(w->equipment[i].handle==w->item_handle && w->equipment[i].rawcode==w->item_rawcode)++found;
            if(found!=1){w->error=245;return count;}
            old_type=(uint32_t)w->item_equipment_type(w->item_handle);
            w->removed_rawcode=old_type;
            /* This setter updates the editor/profile field, not the runtime
               equipment classifier consumed by UnitEquipItem. A live
               CreateItem comparison confirms no item-object bytes change.
               Refuse the obsolete path; do not advertise a false mutation. */
            w->error=273;return count;
        }else if(w->action==10){
            uint64_t data, unit_object;
            uint64_t vtable, callback, record;
            uint32_t controller, tier = w->slot;
            if (w->ability_count != 1 || tier >= 6 || !w->resolver_base || !w->item_handle) {w->error=250;return count;}
            controller = w->ability_rawcodes[0];
            __try {
                /* Python supplies objects already validated by the native
                   ability enumerator and the selected-unit identity path. */
                data = w->item_handle;
                unit_object = w->resolver_base;
                if (!data || !unit_object || *(uint32_t *)(uintptr_t)(data + 0x70u) != controller ||
                    *(uint64_t *)(uintptr_t)(data + 0x68u) != unit_object) {w->error=254;return count;}
                /* ATal stores the six records after the count at +0xd0. */
                record = data + 0xd4u + (uint64_t)tier * 12u;
                vtable = *(uint64_t *)(uintptr_t)data;
                callback = *(uint64_t *)(uintptr_t)(vtable + 0x120u);
                if (!callback || !record) {w->error=255;return count;}
                /* The callback's second argument is not proven to be the
                   unit object for this build. Refuse this path until the
                   exact engine service object is identified. */
                w->error=257;return count;
            } __except(EXCEPTION_EXECUTE_HANDLER) {w->error=GetExceptionCode();return count;}
            w->changed=1;
#ifdef BRIDGE_DIAGNOSTIC
        }else if(w->action==11){
            uint32_t found=0,old_type=0,equipped=0,bag_found=0;int32_t slot=-1;
            uint64_t before_bag[30],before_eq[9];
            if(!w->item_handle || !w->item_rawcode || w->slot<1 || w->slot>8 ||
               !ExtensionSnapshot(w)){w->error=258;return count;}
            for(i=0;i<30;++i){before_bag[i]=w->bag[i].handle;if(w->bag[i].handle==w->item_handle && w->bag[i].rawcode==w->item_rawcode)++found;}
            for(i=0;i<9;++i)before_eq[i]=w->equipment[i].handle;
            if(found!=1){w->error=259;return count;}
            old_type=(uint32_t)w->item_equipment_type(w->item_handle);
#ifdef BRIDGE_DIAGNOSTIC
            uint64_t *debug_identity=(uint64_t *)((uint8_t *)w+sizeof(*w));
            uint8_t *debug_bytes=(uint8_t *)(debug_identity+2);
            uint64_t item_object=debug_identity[0],full=debug_identity[1];
            uint64_t item_owner=BridgeEffectResolveObjectTable(w->resolver_base,full);
            if(!item_owner){w->error=268;return count;}
            if(*(uint64_t *)(uintptr_t)(item_owner+0x90u)!=item_object){w->error=269;return count;}
            if(*(uint64_t *)(uintptr_t)(item_object+0x18u)!=full){w->error=270;return count;}
            if(*(uint32_t *)(uintptr_t)(item_object+0x70u)!=w->item_rawcode){w->error=271;return count;}
            if(*(uint32_t *)(uintptr_t)(item_object+0x178u)!=w->item_rawcode){w->error=272;return count;}
            ExtensionProbeCopy(debug_bytes,(const uint8_t *)(uintptr_t)item_object,0x280u);
            uint32_t field_before=((uint32_t (__fastcall *)(uint64_t,uint32_t))w->get_handle_id)(w->item_handle,0x69657175u);
#endif
            uint32_t setter_result=w->set_item_integer(w->item_handle,0x69657175u,w->slot);
            if(!setter_result){w->error=260;return count;}
            w->removed_rawcode=old_type;
#ifdef BRIDGE_DIAGNOSTIC
            ExtensionProbeCopy(debug_bytes+0x280u,(const uint8_t *)(uintptr_t)item_object,0x280u);
            uint32_t field_after=((uint32_t (__fastcall *)(uint64_t,uint32_t))w->get_handle_id)(w->item_handle,0x69657175u);
#endif
            uint32_t type_after=(uint32_t)w->item_equipment_type(w->item_handle);
            uint8_t equip_result=w->equip_item(w->target_unit,w->item_handle);
#ifdef BRIDGE_DIAGNOSTIC
            ExtensionProbeCopy(debug_bytes+0x500u,(const uint8_t *)(uintptr_t)item_object,0x280u);
#endif
            if(!ExtensionSnapshot(w)){w->error=261;return count;}
            for(i=0;i<9;++i)if(w->equipment[i].handle==w->item_handle){slot=(int32_t)i;++equipped;}
            for(i=0;i<30;++i)if(w->bag[i].handle==w->item_handle)++bag_found;
            w->ability_rawcodes[0]=type_after;w->ability_levels[0]=(int32_t)equip_result;
            w->ability_rawcodes[1]=(uint32_t)(slot+1);w->ability_levels[1]=(int32_t)bag_found;
            w->ability_count=2;
            if(equipped==1){
                uint64_t removed=w->unequip_slot(w->target_unit,w->slot_enum(slot));
                if(removed!=w->item_handle){w->error=262;return count;}
            }
            if(!w->set_item_integer(w->item_handle,0x69657175u,old_type)){w->error=263;return count;}
            if(!ExtensionSnapshot(w)){w->error=264;return count;}
            for(i=0;i<30;++i)if(w->bag[i].handle!=before_bag[i])w->error=265;
            for(i=0;i<9;++i)if(w->equipment[i].handle!=before_eq[i])w->error=266;
            if((uint32_t)w->item_equipment_type(w->item_handle)!=old_type)w->error=267;
            if(w->error)return count;
            uint32_t *probe_result=(uint32_t *)((uint8_t *)w+sizeof(*w)+16u+0x780u);
            probe_result[0]=type_after;probe_result[1]=(uint32_t)equip_result;
            probe_result[2]=(uint32_t)(slot+1);probe_result[3]=bag_found;
            probe_result[4]=equipped;
            probe_result[5]=field_before;probe_result[6]=setter_result;
            probe_result[7]=field_after;
            w->changed=1;
#endif
        }else if(w->action==12){
            /* Diagnostic only: move one bag item through the native equip
               path, then redirect the authoritative AEqu record to a chosen
               loadout slot.  The operation is reverted on any readback
               mismatch; no external process-memory write is used. */
            uint64_t ah=0,aw=0,adata=0,ih=0,iw=0,idata=0;
            uint64_t records=0,item_full=0,saved[9];
            uint32_t slot=w->slot,found=0;
            if(slot>=9 || w->ability_count!=1 || !w->item_handle ||
               !w->item_rawcode || !w->resolver_base || !ExtensionSnapshot(w))
                {w->error=274;return count;}
            for(i=0;i<30;++i)if(w->bag[i].handle==w->item_handle &&
                                w->bag[i].rawcode==w->item_rawcode)++found;
            if(found!=1){w->error=275;return count;}
            ah=w->get_unit_ability(w->target_unit,w->ability_rawcodes[0]);
            if(!ah){w->error=2761;return count;}
            aw=ExtensionResolveHandle(w,(uint32_t)w->get_handle_id(ah));
            adata=aw?*(uint64_t *)(uintptr_t)(aw+0x90u):0;
            if(!adata){w->error=2762;return count;}
            iw=ExtensionResolveHandle(w,(uint32_t)w->get_handle_id(w->item_handle));
            idata=iw?*(uint64_t *)(uintptr_t)(iw+0x90u):0;
            if(!idata){w->error=2763;return count;}
            if(*(uint32_t *)(uintptr_t)(adata+0x70u)!=w->ability_rawcodes[0]){w->error=2765;return count;}
            if(*(uint32_t *)(uintptr_t)(idata+0x70u)!=w->item_rawcode){w->error=2767;return count;}
            records=*(uint64_t *)(uintptr_t)(adata+0xd8u);
            item_full=*(uint64_t *)(uintptr_t)(idata+0x18u);
            if(!records || !item_full){w->error=277;return count;}
            for(i=0;i<9;++i)saved[i]=*(uint64_t *)(uintptr_t)(records+(uint64_t)i*12u);
            if(!w->equip_item(w->target_unit,w->item_handle)){w->error=278;return count;}
            *(uint64_t *)(uintptr_t)(records+(uint64_t)slot*12u)=item_full;
            *(uint32_t *)(uintptr_t)(records+(uint64_t)slot*12u+8u)=0;
            if(!ExtensionSnapshot(w)){w->error=279;goto directed_rollback;}
            for(i=0;i<9;++i)if(w->equipment[i].handle==w->item_handle)++found;
            if(found!=1 || w->equipment[slot].handle!=w->item_handle){w->error=280;goto directed_rollback;}
            w->changed=1;w->removed_rawcode=(uint32_t)item_full;w->ability_levels[0]=(int32_t)slot;
            goto directed_done;
directed_rollback:
            for(i=0;i<9;++i){*(uint64_t *)(uintptr_t)(records+(uint64_t)i*12u)=saved[i];*(uint32_t *)(uintptr_t)(records+(uint64_t)i*12u+8u)=0;}
            w->unequip_slot(w->target_unit,w->slot_enum(0));
            w->error=w->error?w->error:281;
directed_done:;
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
        if(w->action==8){
            for(i=0;i<30;++i)if(w->bag[i].handle==w->item_handle){w->error=243;return count;}
        }
        if(w->action==9){
            uint32_t found=0;
            for(i=0;i<30;++i)if(w->bag[i].handle==w->item_handle && w->bag[i].equipment_type==w->slot)++found;
            for(i=0;i<9;++i)if(w->equipment[i].handle==w->item_handle && w->equipment[i].equipment_type==w->slot)++found;
            if(found!=1){
                /* A successful field setter is not proof that the cached
                   equipment classifier changed. Restore before failing. */
                w->set_item_integer(w->item_handle,0x69657175u,w->removed_rawcode);
                w->changed=0;w->error=248;return count;
            }
        }
        w->completed=1;
    } __except(EXCEPTION_EXECUTE_HANDLER) {w->error=GetExceptionCode();}
    return count;
}

#ifdef BRIDGE_DIAGNOSTIC
__declspec(dllexport) const uint32_t equipment_probe_abi[3]={0x24268043u,216u,3816u};
__declspec(dllexport) uint64_t BridgeEquipmentProbeQuery(void){return BridgeExtensionQuery();}
#endif
