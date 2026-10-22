/* Resource-bearing units are discovered and written in one game-thread callback. */
#define GOLD_MINE_LIMIT 4096u
#define GOLD_MINE_VALUE_MAX 100000000u
typedef struct GoldMineRow {
    uint64_t unit;
    uint32_t rawcode;
    int32_t owner,before,after;
    uint32_t kind,status,error,x,y,reserved;
} GoldMineRow;
_Static_assert(sizeof(GoldMineRow)==48,"Gold mine row ABI");
typedef struct GoldMineWork {
    SelectionWork selection;
    uint64_t (*player)(int32_t);
    void (*enum_player)(uint64_t,uint64_t,uint64_t);
    int32_t (*get_amount)(uint64_t);
    void (*set_amount)(uint64_t,int32_t);
    int32_t (*ability_level)(uint64_t,uint32_t);
    uint32_t (*life)(uint64_t),(*unit_x)(uint64_t),(*unit_y)(uint64_t);
    uint64_t (*owner)(uint64_t);
    int32_t (*player_id)(uint64_t);
    void *expected_tls;
    uint32_t action,scope,target,limit;
    uint32_t count,visited,ignored,changed,unchanged,failed,error,completed,created,destroyed,truncated,uncertain;
    GoldMineRow rows[GOLD_MINE_LIMIT];
} GoldMineWork;
_Static_assert(sizeof(GoldMineWork)==197240,"Gold mine work ABI");
__declspec(dllexport) const uint32_t gold_mine_abi[3]={0x24268078u,216u,197240u};

static uint32_t GoldMineKind(GoldMineWork*w,uint64_t unit,int32_t amount) {
    uint32_t kind=0;
    if(w->ability_level(unit,0x41676c64u)>0)kind|=1u; /* Agld */
    if(w->ability_level(unit,0x4162676du)>0)kind|=2u; /* Abgm */
    if(w->ability_level(unit,0x4165676du)>0)kind|=4u; /* Aegm */
    return kind?kind:amount>0?8u:0u;
}
static void GoldMineCollect(GoldMineWork*w,uint64_t unit) {
    uint32_t raw=w->selection.unit_type_id(unit);
    if(!raw){++w->ignored;return;}
    union{uint32_t bits;float value;} hp;hp.bits=w->life(unit);
    if(!(hp.value>0.405f)){++w->ignored;return;}
    int32_t amount=w->get_amount(unit);
    uint32_t kind=GoldMineKind(w,unit,amount);
    if(!kind){++w->ignored;return;}
    for(uint32_t n=0;n<w->count;++n)if(w->rows[n].unit==unit)return;
    if(w->count>=w->limit){w->truncated=1;w->error=481;return;}
    GoldMineRow*r=&w->rows[w->count++];
    r->unit=unit;r->rawcode=raw;r->owner=w->player_id(w->owner(unit));
    r->before=r->after=amount;r->kind=kind;
    r->x=w->unit_x(unit);r->y=w->unit_y(unit);
    if(amount<0){r->status=3;r->error=482;++w->failed;}
}
static void GoldMineApply(GoldMineWork*w,GoldMineRow*r) {
    if(r->status==3)return;
    uint32_t attempted=0;
    __try {
        if(w->selection.unit_type_id(r->unit)!=r->rawcode ||
           w->player_id(w->owner(r->unit))!=r->owner){r->status=4;r->error=483;__leave;}
        int32_t current=w->get_amount(r->unit);
        /* A hidden original mine and its transformed shell may share resources.
           An earlier row already setting the same amount is a verified no-op. */
        if(current==(int32_t)w->target){r->after=current;r->status=2;++w->unchanged;return;}
        if(current!=r->before || !GoldMineKind(w,r->unit,current)){r->status=4;r->error=484;__leave;}
        attempted=1;
        w->set_amount(r->unit,(int32_t)w->target);
        r->after=w->get_amount(r->unit);
        uint32_t after_type=w->selection.unit_type_id(r->unit);
        if((after_type!=r->rawcode && !(w->target==0 && after_type==0)) ||
           (after_type && w->player_id(w->owner(r->unit))!=r->owner) ||
           r->after!=(int32_t)w->target){r->status=3;r->error=485;__leave;}
        r->status=1;++w->changed;return;
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        r->error=GetExceptionCode();r->status=attempted?5u:3u;
        if(attempted){r->after=-1;++w->uncertain;}
    }
    ++w->failed;
}
__declspec(dllexport) uint64_t BridgeGoldMineQuery(void) {
    GoldMineWork*w=(GoldMineWork*)g_dispatch->work;
    if(!w || w->expected_tls!=g_dispatch->tls_value || w->action>1 || w->scope>1 ||
       w->target>GOLD_MINE_VALUE_MAX || (!w->action && w->target) || w->limit!=GOLD_MINE_LIMIT ||
       !w->player || !w->enum_player || !w->get_amount || !w->set_amount || !w->ability_level ||
       !w->life || !w->unit_x || !w->unit_y || !w->owner || !w->player_id) {
        if(w)w->error=480;return 0;
    }
    __try {
        if(!w->scope) {
            uint32_t count=(uint32_t)BridgeSelect();
            if(w->selection.error || !w->selection.destroyed || count!=w->selection.count){w->error=486;return 0;}
            w->created=w->destroyed=1;
            for(uint32_t i=0;i<count;++i){++w->visited;GoldMineCollect(w,w->selection.rows[i].unit);}
        } else {
            for(int32_t player=0;player<28 && !w->error;++player) {
                uint64_t owner=w->player(player);if(!owner)continue;
                uint64_t group=w->selection.create_group();
                if(!group){w->error=487;break;}
                ++w->created;
                __try {
                    w->enum_player(group,owner,0);
                    uint64_t unit;
                    while(!w->error && (unit=w->selection.first_of_group(group))!=0) {
                        if(++w->visited>100000u){w->error=488;break;}
                        w->selection.remove_from_group(group,unit);
                        if(w->selection.first_of_group(group)==unit){w->error=489;break;}
                        GoldMineCollect(w,unit);
                    }
                } __finally {w->selection.destroy_group(group);++w->destroyed;}
            }
        }
        /* Complete collection and bounds checks before the first mutation. */
        if(w->error || w->created!=w->destroyed)return 0;
        if(w->action)for(uint32_t n=0;n<w->count;++n)GoldMineApply(w,&w->rows[n]);
        w->completed=1;
    } __except(EXCEPTION_EXECUTE_HANDLER){w->error=GetExceptionCode();}
    return w->completed;
}
