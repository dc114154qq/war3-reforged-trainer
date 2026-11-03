/* Only the exact 24342 unit-editor route opts in to this callback.
   Existing scalar field callback and normal unit panel stay unchanged. */
typedef struct UnitFieldHeroIntTrace {
    uint32_t magic,version,stage,setter_called,rollback_called,rollback_verified;
    int32_t base_before,total_before,base_first,total_first,base_final,total_final,target_base;
    uint32_t field_id,target;
    uint32_t correction_called;
    int32_t base_corrected,total_corrected;
} UnitFieldHeroIntTrace;
_Static_assert(sizeof(UnitFieldHeroIntTrace)==72,"UnitFieldHeroIntTrace ABI");
__declspec(dllexport) const uint32_t unit_field_hero_int_abi[3]={0x24268090u,216u,7368u};
static int UnitFieldHeroIntId(uint32_t id) {
    return id==0x75696e63u || id==0x75696e6du || id==0x75696e62u;
}
__declspec(dllexport) uint64_t BridgeUnitFieldHeroIntQuery(void) {
    UnitFieldWork *w=(UnitFieldWork *)g_dispatch->work;
    UnitFieldHeroIntTrace *t;
    uint32_t count,i,j,matched=0;
    int32_t (*get)(uint64_t,uint32_t);
    void (*set)(uint64_t,int32_t,uint32_t);
    if(!w)return 0;
    t=(UnitFieldHeroIntTrace *)&w->fields[8];t->magic=0x494e5431u;t->version=1;t->stage=1;
    if(w->expected_tls!=g_dispatch->tls_value || w->action>1u || !w->count || w->count>3u ||
       !w->target_unit || !w->rawcode || (w->action && w->count!=1u) || !w->handlers[1] ||
       (w->action && !w->handlers[7])){w->error=910;return 0;}
    for(j=0;j<w->count;++j)if(!UnitFieldHeroIntId(w->fields[j].id) || w->fields[j].kind!=1u ||
        w->fields[j].weapon || w->fields[j].target>1000000u){w->error=911;return 0;}
    get=(int32_t (*)(uint64_t,uint32_t))w->handlers[1];set=(void (*)(uint64_t,int32_t,uint32_t))w->handlers[7];
    count=(uint32_t)BridgeSelect();
    if(!count || w->selection.error || !w->selection.destroyed || count!=w->selection.count){w->error=912;return count;}
    for(i=0;i<count;++i){
        SelectionRow *row=&w->selection.rows[i];int32_t before_base,before_total;int64_t bonus,target_base;
        if(row->unit!=w->target_unit){w->statuses[i]=2u;++w->completed;continue;}++matched;
        if(w->selection.unit_type_id(row->unit)!=w->rawcode || row->rawcode!=w->rawcode ||
           w->selection.hero_level(row->unit)!=row->level){w->error=913;return count;}
        if(row->level<=0){
            if(w->action){w->error=921;return count;}
            t->base_before=t->total_before=t->base_final=t->total_final=-1;t->stage=5;
            w->statuses[i]=1;++w->completed;continue;
        }
        before_base=get(row->unit,0);before_total=get(row->unit,1);
        if(before_base<0 || before_total<0){w->error=911;return count;}
        t->stage=2;t->base_before=t->base_first=t->base_final=before_base;
        t->total_before=t->total_first=t->total_final=before_total;
        bonus=(int64_t)before_total-before_base;
        for(j=0;j<w->count;++j){uint32_t k=i*32u+j;
            w->before[k]=w->after[k]=(uint32_t)(w->fields[j].id==0x75696e62u?before_total:before_base);}
        if(w->action){
            UnitFieldSpec *f=&w->fields[0];uint32_t k=i*32u;
            target_base=(int64_t)f->target-(f->id==0x75696e62u?bonus:0);
            t->field_id=f->id;t->target=f->target;
            if(target_base<0 || target_base>1000000LL){w->error=920;return count;}
            t->target_base=(int32_t)target_base;
            if(w->selection.unit_type_id(row->unit)!=row->rawcode || w->selection.hero_level(row->unit)!=row->level){w->error=913;return count;}
            if(before_base!=(int32_t)target_base){t->setter_called=1;t->stage=3;set(row->unit,(int32_t)target_base,1);}
            t->base_first=t->base_final=get(row->unit,0);t->total_first=t->total_final=get(row->unit,1);
            w->after[k]=(uint32_t)(f->id==0x75696e62u?t->total_first:t->base_first);
            if(w->selection.unit_type_id(row->unit)!=row->rawcode || w->selection.hero_level(row->unit)!=row->level){w->error=913;return count;}
            /* A successful base update may recalculate percentage bonuses.
               Correct the total once only after proving that base setter took
               effect; never replay an ignored or clamped setter. */
            if(f->id==0x75696e62u && t->base_first==(int32_t)target_base && t->total_first!=(int32_t)f->target){
                int64_t corrected=(int64_t)t->base_first+(int64_t)f->target-t->total_first;
                if(corrected>=0 && corrected<=1000000LL && corrected!=target_base){
                    target_base=corrected;t->target_base=(int32_t)corrected;t->correction_called=1;++t->setter_called;
                    set(row->unit,(int32_t)corrected,1);
                    t->base_corrected=t->base_final=get(row->unit,0);t->total_corrected=t->total_final=get(row->unit,1);
                    w->after[k]=(uint32_t)t->total_final;
                    if(w->selection.unit_type_id(row->unit)!=row->rawcode || w->selection.hero_level(row->unit)!=row->level){w->error=913;return count;}
                }
            }
            if(w->after[k]!=f->target || t->base_final!=(int32_t)target_base){
                if(t->base_final!=before_base){t->rollback_called=1;t->stage=4;set(row->unit,before_base,1);}
                t->base_final=get(row->unit,0);t->total_final=get(row->unit,1);
                t->rollback_verified=(uint32_t)(t->base_final==before_base && t->total_final==before_total);
                w->after[k]=(uint32_t)(f->id==0x75696e62u?t->total_final:t->base_final);
                w->error=t->rollback_verified?917u:918u;return count;
            }
            if(w->after[k]!=w->before[k])++w->changed;
        }
        t->stage=5;w->statuses[i]=1;++w->completed;
    }
    if(matched!=1u)w->error=914;
    return count;
}
#ifdef BRIDGE_TEST
__declspec(dllexport) uint64_t BridgeUnitFieldHeroIntTestRun(UnitFieldWork *work) {
    BridgeCommand command;BridgeCommand *previous=g_dispatch;uint64_t result;
    memset(&command,0,sizeof(command));command.work=work;command.tls_value=work->expected_tls;
    g_dispatch=&command;result=BridgeUnitFieldHeroIntQuery();g_dispatch=previous;return result;
}
#endif
