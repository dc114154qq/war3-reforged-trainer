/* The 3.0 loadout slots are 0..8 in shipped common.j; ordinary slots remain 0..5. */
typedef struct EquipmentWork {
    SelectionWork selection;
    uint64_t (*create)(uint32_t,float *,float *);
    uint32_t (*type)(uint64_t);
    uint64_t (*equipment_type)(uint64_t),(*slot_enum)(int32_t);
    uint64_t (*in_equipment)(uint64_t,uint64_t);
    uint8_t (*equip)(uint64_t,uint64_t);
    void (*unequip)(uint64_t,uint64_t),(*remove)(uint64_t);
    uint64_t (*in_inventory)(uint64_t,int32_t);
    int32_t (*inventory_size)(uint64_t);
    void *expected_tls;
    uint64_t target,expected_created;
    uint32_t rawcode,action,error,completed,kind,changed,rollback_error,reserved;
    uint64_t created,replaced,before[9],after[9],inventory_before[6],inventory_after[6];
} EquipmentWork;
_Static_assert(sizeof(EquipmentWork)==872,"EquipmentWork ABI");
__declspec(dllexport) const uint32_t equipment_batch_abi[3]={0x2426802Eu,216u,872u};
static int EquipmentSnapshot(EquipmentWork *w,uint64_t *eq,uint64_t *inv) {
    int32_t size=w->inventory_size(w->target);
    if(size<0 || size>6)return 0;
    for(int32_t i=0;i<9;++i)eq[i]=w->in_equipment(w->target,w->slot_enum(i));
    for(int32_t i=0;i<6;++i)inv[i]=i<size ? w->in_inventory(w->target,i) : 0;
    return 1;
}
static int EquipmentSame(const uint64_t *a,const uint64_t *b,uint32_t n) {
    for(uint32_t i=0;i<n;++i)if(a[i]!=b[i])return 0;return 1;
}
__declspec(dllexport) uint64_t BridgeEquipmentQuery(void) {
    EquipmentWork *w=(EquipmentWork *)g_dispatch->work;uint32_t count,matches=0;
    uint64_t item=0;int slot=-1,snapshot_ok=0;float x=0,y=0;
    if(!w || w->expected_tls!=g_dispatch->tls_value)return 0;
    count=(uint32_t)BridgeSelect();
    if(w->selection.error || !w->selection.destroyed || w->action>2){w->error=201;return count;}
    for(uint32_t i=0;i<count;++i)if(w->selection.rows[i].unit==w->target)++matches;
    if(w->action && matches!=1){w->error=202;return count;}
    __try {
        if(w->action!=2){
            item=w->create(w->rawcode,&x,&y);
            if(!item || w->type(item)!=w->rawcode){w->error=203;}
            else w->kind=(uint32_t)w->equipment_type(item);
            if(!w->action){if(item)w->remove(item);w->completed=!w->error;return count;}
            if(w->error || w->kind<1 || w->kind>8){if(item)w->remove(item);w->error=204;return count;}
            w->created=item;
        }
        if(!EquipmentSnapshot(w,w->before,w->inventory_before)){w->error=205;}
        else if(w->action==1){
            snapshot_ok=1;
            static const int slots[9]={-1,0,1,2,3,4,6,7,8};
            int desired=slots[w->kind];
            if(w->kind==5 && w->before[4] && !w->before[5])desired=5;
            w->replaced=w->before[desired];
            if(w->replaced)w->unequip(w->target,w->replaced);
            w->equip(w->target,item);
            if(!EquipmentSnapshot(w,w->after,w->inventory_after)){w->error=206;}
            else {
                for(int i=0;i<9;++i)if(w->after[i]==item){if(slot!=-1)w->error=207;slot=i;}
                if(slot<0)w->error=208;
                else {
                    w->replaced=w->before[slot];
                    for(int i=0;i<9;++i)if(i!=slot && w->before[i]!=w->after[i])w->error=209;
                }
                if(!EquipmentSame(w->inventory_before,w->inventory_after,6))w->error=210;
            }
        } else {
            for(int i=0;i<9;++i)if(w->before[i]==w->expected_created)slot=i;
            if(slot<0){w->error=211;return count;}
            w->unequip(w->target,w->expected_created);
            if(w->replaced)w->equip(w->target,w->replaced);
            if(!EquipmentSnapshot(w,w->after,w->inventory_after) || w->after[slot]!=w->replaced)
                w->error=212;
            else {
                for(int i=0;i<9;++i)if(i!=slot && w->before[i]!=w->after[i])w->error=213;
                if(!EquipmentSame(w->inventory_before,w->inventory_after,6))w->error=214;
            }
            if(!w->error)w->remove(w->expected_created);
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) {w->error=GetExceptionCode();}
    if(w->error && w->action==1 && item){
        __try {
            if(snapshot_ok){
                w->unequip(w->target,item);
                for(int i=0;i<9;++i)if(w->before[i] && w->in_equipment(w->target,w->slot_enum(i))!=w->before[i])
                    w->equip(w->target,w->before[i]);
            }
            w->remove(item);
            if(snapshot_ok && (!EquipmentSnapshot(w,w->after,w->inventory_after) || !EquipmentSame(w->before,w->after,9) ||
               !EquipmentSame(w->inventory_before,w->inventory_after,6)))w->rollback_error=1;
        } __except(EXCEPTION_EXECUTE_HANDLER) {w->rollback_error=GetExceptionCode();}
    }
    if(!w->error){w->changed=1;w->completed=1;}
    return count;
}
