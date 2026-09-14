/* Operates on current selected handles only; never searches for a donor skill. */
typedef struct AbilityWork {
    SelectionWork selection;
    uint8_t (*add)(uint64_t,uint32_t), (*remove)(uint64_t,uint32_t);
    int32_t (*set_level)(uint64_t,uint32_t,int32_t), (*get_level)(uint64_t,uint32_t);
    void *expected_tls;
    uint32_t rawcode,action,target,changed,error,completed;
    struct {int32_t before,after;} rows[24];
    int32_t intermediate[24];
} AbilityWork;
_Static_assert(sizeof(AbilityWork)==832,"AbilityWork ABI");
__declspec(dllexport) const uint32_t ability_batch_abi[3]={0x24268011u,216u,832u};
__declspec(dllexport) uint64_t BridgeAbilityQuery(void) {
    AbilityWork *w=(AbilityWork *)g_dispatch->work;
    uint64_t count,unit;
    uint32_t i;
    if (!w) return 0;
    if (g_dispatch->tls_value!=w->expected_tls || !w->rawcode || w->action>4 || w->target>100000 ||
        ((w->action==3 || w->action==4) && !w->target) || !w->add || !w->remove || !w->set_level || !w->get_level) {
        w->error=20;return 0;
    }
    count=BridgeSelect();
    if (w->selection.error || !w->selection.destroyed || count!=w->selection.count || !count) {w->error=21;return count;}
    for (i=0;i<count;++i) {
        unit=w->selection.rows[i].unit;
        if (w->selection.unit_type_id(unit)!=w->selection.rows[i].rawcode) {w->error=22;return count;}
        w->rows[i].before=w->get_level(unit,w->rawcode);
        if (w->rows[i].before<0 || (w->action==3 && !w->rows[i].before)) {w->error=23;return count;}
    }
    for (i=0;i<count;++i) {
        int32_t before=w->rows[i].before;
        unit=w->selection.rows[i].unit;
        if (w->selection.unit_type_id(unit)!=w->selection.rows[i].rawcode || w->get_level(unit,w->rawcode)!=before) {w->error=24;return count;}
        __try {
            if ((w->action==1 || w->action==4) && !before) {
                w->error=100+i;
                if (!w->add(unit,w->rawcode)) {w->error=25;return count;}
                w->error=0;
                ++w->changed;
            }
            if ((w->action==1 && w->target) || w->action==3 || (w->action==4 && !before)) {
                int32_t current;
                w->error=200+i;current=w->get_level(unit,w->rawcode);w->error=0;
                if (current!=(int32_t)w->target) {
                    w->error=300+i;
                    if (w->set_level(unit,w->rawcode,(int32_t)w->target)!=(int32_t)w->target) {w->error=26;return count;}
                    w->error=0;
                    if (before>0) ++w->changed;
                }
            }
            if (w->action==2 && before) {
                if (!w->remove(unit,w->rawcode)) {w->error=27;return count;}
                ++w->changed;
            }
            w->intermediate[i]=w->get_level(unit,w->rawcode);
        } __finally {
            /* Diagnostic action restores only an ability that was absent. */
            if (w->action==4 && !before && w->get_level(unit,w->rawcode)>0) {
                if (!w->remove(unit,w->rawcode)) w->error=28;
            }
            w->rows[i].after=w->get_level(unit,w->rawcode);
        }
        if ((w->action==0 && w->rows[i].after!=before) ||
            (w->action==1 && w->rows[i].after!=(w->target ? (int32_t)w->target : before ? before : 1)) ||
            (w->action==2 && w->rows[i].after!=0) ||
            (w->action==3 && w->rows[i].after!=(int32_t)w->target) ||
            (w->action==4 && (w->rows[i].after!=before || (!before && w->intermediate[i]!=(int32_t)w->target)))) {
            w->error=29;return count;
        }
        if (w->error) return count;
        ++w->completed;
    }
    return count;
}
