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
/* 24268 evidence: SetUnitAbilityLevel+0x4bc faults reading [r15=0]
   AFTER its level mutation. Do not patch the game or resume at a guessed RIP.
   Unwind only that exact tail fault, then require native readback == target. */
static int BridgeKnownAbilityTail(uint64_t handler,uint32_t code,uint32_t flags,
                                 uint32_t parameters,uint64_t instruction,
                                 uint64_t access,uint64_t address,uint64_t r15) {
    return handler>=0x10000 && handler<0x800000000000ULL-0x4bc &&
        code==EXCEPTION_ACCESS_VIOLATION && !(flags&EXCEPTION_NONCONTINUABLE) && parameters>=2 &&
        instruction==handler+0x4bc && access==0 && address==0 && r15==0;
}
static LONG BridgeAbilityTailFilter(EXCEPTION_POINTERS *info,AbilityWork *w) {
    EXCEPTION_RECORD *e=info->ExceptionRecord;
    if (BridgeKnownAbilityTail((uint64_t)(uintptr_t)w->set_level,e->ExceptionCode,e->ExceptionFlags,
        e->NumberParameters,(uint64_t)(uintptr_t)e->ExceptionAddress,
        e->ExceptionInformation[0],e->ExceptionInformation[1],info->ContextRecord->R15)) {
        BridgeExceptionFilter(info);
        return EXCEPTION_EXECUTE_HANDLER;
    }
    return EXCEPTION_CONTINUE_SEARCH;
}
static int32_t BridgeAcceptAbilityTailReadback(int32_t actual,int32_t target) {
    if (actual==target && target>0) {++bridge_recovered_faults;return actual;}
    return -1;
}
static int32_t BridgeSetAbilityLevelChecked(AbilityWork *w,uint64_t unit,int32_t level) {
    __try {return w->set_level(unit,w->rawcode,level);}
    __except(BridgeAbilityTailFilter(GetExceptionInformation(),w)) {
        int32_t actual=w->get_level(unit,w->rawcode);
        return BridgeAcceptAbilityTailReadback(actual,level);
    }
}
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
                    if (BridgeSetAbilityLevelChecked(w,unit,(int32_t)w->target)!=(int32_t)w->target) {w->error=26;return count;}
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
            /* Preserve the actual post-call level even when the setter faults. */
            if (w->error>=300 && w->error<324) w->intermediate[i]=w->get_level(unit,w->rawcode);
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
