/* Current-engine items. Existing slots are snapshotted before any mutation. */
typedef struct ItemSlot {uint64_t handle;uint32_t rawcode;int32_t charges;} ItemSlot;
typedef struct ItemUnitRow {
    ItemSlot before[6],after[6];
    uint64_t created;
    uint32_t created_type;
    int32_t created_charges;
    uint32_t inventory_size,status,created_slot,reserved;
} ItemUnitRow;
_Static_assert(sizeof(ItemUnitRow)==224,"ItemUnitRow ABI");
typedef struct ItemWork {
    SelectionWork selection;
    uint64_t (*create)(uint64_t,uint32_t),(*in_slot)(uint64_t,int32_t);
    int32_t (*size)(uint64_t);
    uint32_t (*type)(uint64_t);
    int32_t (*charges)(uint64_t);
    void (*set_charges)(uint64_t,int32_t),(*remove)(uint64_t),(*detach)(uint64_t,uint64_t);
    void *expected_tls;
    uint32_t rawcode,action;
    int32_t target;
    uint32_t changed,error,completed,skipped,reserved;
    ItemUnitRow rows[24];
} ItemWork;
_Static_assert(sizeof(ItemWork)==5960,"ItemWork ABI");
__declspec(dllexport) const uint32_t item_batch_abi[3]={0x24268014u,216u,5960u};
static int BridgeItemSnapshot(ItemWork *w,uint64_t unit,uint32_t size,ItemSlot *out) {
    uint32_t i;
    for (i=0;i<6;++i) {
        uint64_t item=i<size ? w->in_slot(unit,(int32_t)i) : 0;
        out[i].handle=item;out[i].rawcode=item ? w->type(item) : 0;out[i].charges=item ? w->charges(item) : 0;
        if (item && (!out[i].rawcode || out[i].charges<0)) return 0;
    }
    return 1;
}
static int BridgeItemSame(const ItemSlot *a,const ItemSlot *b) {
    uint32_t i;for (i=0;i<6;++i)
        if (a[i].handle!=b[i].handle || a[i].rawcode!=b[i].rawcode || a[i].charges!=b[i].charges) return 0;
    return 1;
}
static int BridgeItemWasOriginal(ItemWork *w,uint64_t item,uint32_t count) {
    uint32_t i,j;for (i=0;i<count;++i) for (j=0;j<6;++j)
        if (item && w->rows[i].before[j].handle==item) return 1;
    return 0;
}
static int BridgeItemSourcesMatch(ItemWork *w,uint64_t unit,ItemUnitRow *r) {
    uint32_t j;
    for (j=0;j<6;++j) if (r->before[j].handle) {
        uint64_t item=w->in_slot(unit,(int32_t)j);
        if (item!=r->before[j].handle || w->type(item)!=r->before[j].rawcode ||
            w->charges(item)!=r->before[j].charges) return 0;
    }
    return 1;
}
static int BridgeItemCreatedSeen(const uint64_t *created,uint32_t count,uint64_t item) {
    uint32_t i;for (i=0;i<count;++i) if (created[i]==item) return 1;return 0;
}
__declspec(dllexport) uint64_t BridgeItemQuery(void) {
    ItemWork *w=(ItemWork *)g_dispatch->work;
    uint32_t i,j,count;
    if (!w) return 0;
    if (w->expected_tls!=g_dispatch->tls_value || w->action>6 ||
        ((w->action==1 || w->action==3) && !w->rawcode) || w->target>1000000000 ||
        w->target< -1 ||
        ((w->action==0 || w->action==2 || w->action==4 || w->action==5 || w->action==6) && w->rawcode) ||
        ((w->action==2 || w->action==3) && w->target<1) ||
        (((w->action==0 || w->action==4 || w->action==5 || w->action==6) && w->target!=-1)) ||
        !w->create || !w->in_slot || !w->size ||
        !w->type || !w->charges || !w->set_charges || !w->remove || !w->detach) {w->error=40;return 0;}
    count=(uint32_t)BridgeSelect();
    if (!count || w->selection.error || !w->selection.destroyed || count!=w->selection.count) {w->error=41;return count;}
    for (i=0;i<count;++i) {
        uint64_t unit=w->selection.rows[i].unit;
        int32_t size=w->size(unit);
        if (size<0 || size>6 || w->selection.unit_type_id(unit)!=w->selection.rows[i].rawcode) {w->error=42;return count;}
        w->rows[i].inventory_size=(uint32_t)size;
        if (!BridgeItemSnapshot(w,unit,(uint32_t)size,w->rows[i].before)) {w->error=43;return count;}
    }
    for (i=0;i<count;++i) {
        ItemUnitRow *r=&w->rows[i];
        uint64_t unit=w->selection.rows[i].unit;
        int free_slot=0,duplicate=0;
        if (w->selection.unit_type_id(unit)!=w->selection.rows[i].rawcode || w->size(unit)!=(int32_t)r->inventory_size ||
            !BridgeItemSnapshot(w,unit,r->inventory_size,r->after) || !BridgeItemSame(r->before,r->after)) {w->error=44;return count;}
        r->created_slot=0xffffffffu;
        r->reserved=0;
        for (j=0;j<r->inventory_size;++j) {if (!r->before[j].handle) free_slot=1;if(r->before[j].rawcode==w->rawcode)duplicate=1;}
        if (w->action==0) {r->status=1;++w->completed;continue;}
        if (w->action==3 && (!free_slot || duplicate)) {r->status=6;++w->skipped;++w->completed;continue;}
        if (w->action==2) {
            for (j=0;j<6;++j) if (r->before[j].handle) {
                uint64_t item=r->before[j].handle;
                if (w->in_slot(unit,(int32_t)j)!=item || w->type(item)!=r->before[j].rawcode || w->charges(item)!=r->before[j].charges) {w->error=45;return count;}
                if (r->before[j].charges!=w->target) {
                    w->error=400+i;w->set_charges(item,w->target);w->error=0;
                    if (w->charges(item)!=w->target) {w->error=46;return count;}
                    ++w->changed;
                }
            }
            r->status=4;
        } else if (w->action==4 || w->action==6) {
            for (j=0;j<r->inventory_size;++j) if (r->before[j].handle) {
                uint64_t item=r->before[j].handle;
                if (w->in_slot(unit,(int32_t)j)!=item || w->type(item)!=r->before[j].rawcode ||
                    w->charges(item)!=r->before[j].charges) {w->error=55;return count;}
                if (w->action==4) {w->detach(unit,item);w->remove(item);}
                else w->detach(unit,item);
                ++w->changed;
            }
            r->status=w->action==4 ? 7 : 8;
        } else if (w->action==5) {
            uint64_t created[6]={0};uint32_t created_count=0;int had_original=0;
            __try {
                for (j=0;j<r->inventory_size;++j) if (r->before[j].handle) {
                    uint64_t created_item;uint32_t created_type;int32_t created_charges;
                    had_original=1;
                    if (!BridgeItemSourcesMatch(w,unit,r)) {w->error=56;return count;}
                    w->error=100+i;created_item=w->create(unit,r->before[j].rawcode);w->error=0;
                    if (!created_item || BridgeItemWasOriginal(w,created_item,count) ||
                        BridgeItemCreatedSeen(created,created_count,created_item)) {w->error=57;return count;}
                    created_type=w->type(created_item);created_charges=w->charges(created_item);
                    if (!created_type || created_type!=r->before[j].rawcode || created_charges<0) {w->error=58;return count;}
                    if (!BridgeItemSourcesMatch(w,unit,r)) {w->error=59;return count;}
                    created[created_count++]=created_item;
                    if (!r->created) {r->created=created_item;r->created_type=created_type;r->created_charges=created_charges;}
                    r->reserved=created_count;++w->changed;
                }
            } __except(EXCEPTION_EXECUTE_HANDLER) {w->error=60;return count;}
            if (!had_original) {r->status=6;++w->skipped;++w->completed;continue;}
            r->status=9;
        } else {
            int keep=0,original=0;
            w->error=100+i;r->created=w->create(unit,w->rawcode);w->error=0;
            original=BridgeItemWasOriginal(w,r->created,count);
            if (!r->created || original) {w->error=47;return count;}
            __try {
                r->created_type=w->type(r->created);
                if (r->created_type!=w->rawcode) {w->error=48;return count;}
                if (w->target>=0 && w->charges(r->created)!=w->target) {
                    w->error=200+i;w->set_charges(r->created,w->target);w->error=0;
                }
                r->created_charges=w->charges(r->created);
                if (w->target>=0 && r->created_charges!=w->target) {w->error=49;return count;}
                if (!BridgeItemSnapshot(w,unit,r->inventory_size,r->after)) {w->error=50;return count;}
                for (j=0;j<6;++j) {
                    if (r->after[j].handle==r->created) r->created_slot=j;
                    if (r->before[j].handle && (r->before[j].handle!=r->after[j].handle || r->before[j].rawcode!=r->after[j].rawcode || r->before[j].charges!=r->after[j].charges)) {w->error=51;return count;}
                }
                if (w->action==3 && r->created_slot==0xffffffffu) {w->error=52;return count;}
                keep=w->action==1;
                r->status=keep ? (r->created_slot<6 ? 2 : 3) : 5;
                ++w->changed;
            } __finally {
                if (!keep) {
                    w->detach(unit,r->created);w->remove(r->created);
                    r->reserved=w->type(r->created);
                    BridgeItemSnapshot(w,unit,r->inventory_size,r->after);
                    if (!BridgeItemSame(r->before,r->after)) w->error=53;
                }
            }
        }
        if (!BridgeItemSnapshot(w,unit,r->inventory_size,r->after)) {w->error=54;return count;}
        if (w->error) return count;
        ++w->completed;
    }
    return count;
}
