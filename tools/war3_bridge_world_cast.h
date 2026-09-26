/* Staged native orders for current-build temporary full-screen abilities. */
#define WORLD_CAST_IMMEDIATE 1u
#define WORLD_CAST_POINT 2u
#define WORLD_CAST_TARGET 3u

typedef uint8_t (*WorldCastIssuePointFn)(uint64_t,uint32_t,float *,float *);
typedef uint8_t (*WorldCastIssueTargetFn)(uint64_t,uint32_t,uint64_t);

typedef struct WorldCastWork {
    SelectionWork selection;
    uint64_t (*get_ability)(uint64_t,uint32_t);
    uint32_t (*get_ability_id)(uint64_t);
    uint8_t (*add_ability)(uint64_t,uint32_t);
    uint8_t (*remove_ability)(uint64_t,uint32_t);
    uint64_t (*get_area)(uint64_t,uint32_t,int32_t);
    uint8_t (*set_area)(uint64_t,uint32_t,int32_t,float *);
    uint8_t (*issue_immediate)(uint64_t,uint32_t);
    WorldCastIssuePointFn issue_point;
    WorldCastIssueTargetFn issue_target;
    uint64_t (*get_owner)(uint64_t);
    uint32_t (*get_life)(uint64_t);
    uint32_t (*get_mana)(uint64_t,uint64_t);
    uint32_t (*get_cooldown)(uint64_t,uint32_t);
    uint32_t (*get_order)(uint64_t);
    uint32_t (*get_x)(uint64_t);
    uint32_t (*get_y)(uint64_t);
    uint64_t (*create_group)(void);
    void (*enum_units)(uint64_t,uint64_t,uint64_t);
    uint64_t (*first_of_group)(uint64_t);
    void (*remove_from_group)(uint64_t,uint64_t);
    void (*destroy_group)(uint64_t);
    uint64_t (*player)(int32_t);
    uint8_t (*is_enemy)(uint64_t,uint64_t);
    void *expected_tls;
    uint64_t source,ability_handle,target;
    uint32_t action,rawcode,order_id,cast_kind,area_bits;
    uint32_t prior_area,added,issued,error,completed;
    uint32_t mana_before,mana_after,cooldown_after,order_after,target_x,target_y;
} WorldCastWork;
_Static_assert(sizeof(WorldCastWork)==760,"WorldCastWork ABI");
__declspec(dllexport) const uint32_t world_cast_abi[3]={0x24268048u,216u,760u};

static int BridgeWorldCastLive(WorldCastWork *w,uint64_t unit) {
    union {uint32_t bits;float value;} life;
    life.bits=w->get_life(unit);
    return life.value==life.value && life.value>0.405f;
}

static uint64_t BridgeWorldCastTarget(WorldCastWork *w,uint64_t source_owner) {
    uint64_t group=0,target=0;
    __try {
        group=w->create_group();
        if(!group){w->error=333;__leave;}
        for(int32_t index=0;index<24 && !target;++index){
            uint64_t candidate_player=w->player(index);
            if(!candidate_player || !w->is_enemy(source_owner,candidate_player))continue;
            w->enum_units(group,candidate_player,0);
            for(;;){
                uint64_t unit=w->first_of_group(group);
                if(!unit)break;
                w->remove_from_group(group,unit);
                if(unit!=w->source && w->get_owner(unit)==candidate_player &&
                   BridgeWorldCastLive(w,unit)){target=unit;break;}
            }
            for(;;){
                uint64_t remaining=w->first_of_group(group);
                if(!remaining)break;
                w->remove_from_group(group,remaining);
            }
        }
    } __except(EXCEPTION_EXECUTE_HANDLER){w->error=GetExceptionCode();}
    if(group){
        __try {w->destroy_group(group);}
        __except(EXCEPTION_EXECUTE_HANDLER){if(!w->error)w->error=GetExceptionCode();}
    }
    return target;
}

__declspec(dllexport) uint64_t BridgeWorldCastQuery(void) {
    WorldCastWork *w=(WorldCastWork *)g_dispatch->work;
    uint64_t player=0,ability=0;
    uint64_t requested_source=w ? w->source : 0;
    uint32_t count=0,touched=0;
    union {uint32_t bits;float value;} area,prior,x,y;
    if(!w || w->expected_tls!=g_dispatch->tls_value ||
       !w->get_ability || !w->get_ability_id || !w->add_ability ||
       !w->remove_ability || !w->get_area || !w->set_area ||
       !w->issue_immediate || !w->issue_point || !w->issue_target ||
       !w->get_owner || !w->get_life || !w->get_mana ||
       !w->get_cooldown || !w->get_order || !w->get_x || !w->get_y ||
       !w->create_group || !w->enum_units || !w->first_of_group ||
       !w->remove_from_group || !w->destroy_group || !w->player || !w->is_enemy ||
       w->action<1 || w->action>3 || !w->rawcode ||
       w->cast_kind<WORLD_CAST_IMMEDIATE || w->cast_kind>WORLD_CAST_TARGET ||
       (w->action==1 && (!w->order_id || !w->area_bits))){
        if(w)w->error=320;return 0;
    }
    __try {
        player=w->selection.local_player();
        if(!player){w->error=321;__leave;}
        if(w->action==1){
            count=(uint32_t)BridgeSelect();
            if(!count || w->selection.error || !w->selection.destroyed){w->error=322;__leave;}
            for(uint32_t i=0;i<count;++i){
                SelectionRow *row=&w->selection.rows[i];
                if(row->level<=0 || (requested_source && row->unit!=requested_source) ||
                   w->get_owner(row->unit)!=player)continue;
                if(BridgeWorldCastLive(w,row->unit)){w->source=row->unit;break;}
            }
            if(!w->source){w->error=323;__leave;}
        }else if(!w->source || !w->ability_handle || w->get_owner(w->source)!=player){
            w->error=324;__leave;
        }
        ability=w->get_ability(w->source,w->rawcode);
        if(w->action==1){
            area.bits=w->area_bits;
            if(!(area.value>=1.0f && area.value<=100000.0f)){w->error=325;__leave;}
            if(!ability){
                if(!w->add_ability(w->source,w->rawcode)){w->error=326;__leave;}
                w->added=1;ability=w->get_ability(w->source,w->rawcode);
            }
            if(!ability || w->get_ability_id(ability)!=w->rawcode){w->error=327;__leave;}
            w->ability_handle=ability;
            prior.bits=(uint32_t)w->get_area(ability,0x61617265u,0);
            w->prior_area=prior.bits;touched=1;
            if(!w->set_area(ability,0x61617265u,0,&area.value) ||
               (uint32_t)w->get_area(ability,0x61617265u,0)!=area.bits){w->error=328;__leave;}
            if(w->cast_kind!=WORLD_CAST_IMMEDIATE){
                w->target=BridgeWorldCastTarget(w,player);
                if(w->error)__leave;
                if(!w->target){w->error=334;__leave;}
                w->target_x=w->get_x(w->target);w->target_y=w->get_y(w->target);
            }
            w->mana_before=w->get_mana(w->source,2u);
            if(w->cast_kind==WORLD_CAST_IMMEDIATE)
                w->issued=w->issue_immediate(w->source,w->order_id)?1u:0u;
            else if(w->cast_kind==WORLD_CAST_POINT){
                x.bits=w->target_x;y.bits=w->target_y;
                w->issued=w->issue_point(w->source,w->order_id,&x.value,&y.value)?1u:0u;
            }else w->issued=w->issue_target(w->source,w->order_id,w->target)?1u:0u;
            if(!w->issued){w->error=329;__leave;}
        }else{
            if(!ability || ability!=w->ability_handle ||
               w->get_ability_id(ability)!=w->rawcode){w->error=330;__leave;}
            if(w->action==2){
                if(w->added){
                    if(!w->remove_ability(w->source,w->rawcode) ||
                       w->get_ability(w->source,w->rawcode)){w->error=331;__leave;}
                }else{
                    prior.bits=w->prior_area;
                    if(!w->set_area(ability,0x61617265u,0,&prior.value) ||
                       (uint32_t)w->get_area(ability,0x61617265u,0)!=prior.bits){w->error=332;__leave;}
                }
            }else{
                w->mana_after=w->get_mana(w->source,2u);
                w->cooldown_after=w->get_cooldown(w->source,w->rawcode);
                w->order_after=w->get_order(w->source);
            }
        }
        w->completed=1;
    } __except(EXCEPTION_EXECUTE_HANDLER){w->error=GetExceptionCode();}
    if(w->error && w->action==1){
        __try {
            if(w->added)w->remove_ability(w->source,w->rawcode);
            else if(touched && ability){prior.bits=w->prior_area;w->set_area(ability,0x61617265u,0,&prior.value);}
        } __except(EXCEPTION_EXECUTE_HANDLER){}
    }
    return w->completed;
}
