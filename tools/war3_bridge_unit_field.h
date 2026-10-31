/* Unit/weapon field enum handles are FourCC scalars, like ability fields. */
typedef struct UnitFieldSpec {uint32_t id,kind,weapon,target;} UnitFieldSpec;
typedef struct UnitFieldWork {
    SelectionWork selection;uintptr_t handlers[12];void *expected_tls;
    uint64_t target_unit;
    uint32_t rawcode,action,count,completed,error,changed;UnitFieldSpec fields[32];
    uint32_t statuses[24],before[24*32],after[24*32];
} UnitFieldWork;
_Static_assert(sizeof(UnitFieldWork)==7368,"UnitFieldWork ABI");
__declspec(dllexport) const uint32_t unit_field_abi[3]={0x24268082u,216u,7368u};
static uint32_t UnitFieldRead(UnitFieldWork *w,uint64_t unit,UnitFieldSpec *f) {
    uintptr_t h=w->handlers[f->kind+(f->weapon?3u:0u)];uint64_t r;
    if(f->weapon)r=((uint64_t (*)(uint64_t,uint32_t,int32_t))h)(unit,f->id,(int32_t)f->weapon-1);
    else r=((uint64_t (*)(uint64_t,uint32_t))h)(unit,f->id);
    return f->kind==0u?(uint32_t)(uint8_t)r:(uint32_t)r;
}
static uint8_t UnitFieldWrite(UnitFieldWork *w,uint64_t unit,UnitFieldSpec *f,uint32_t bits) {
    uintptr_t h=w->handlers[6u+f->kind+(f->weapon?3u:0u)];union {uint32_t bits;float real;}v;v.bits=bits;
    if(f->id==0x75613172u && f->kind==2u && f->weapon){
        /* The wrapper subtracts getter(index), but passes index to an
           underlying bit-mask adder. Index 1 updates weapon 0 while it
           subtracts weapon 1. Compensate BOTH ranges, including nonzero
           secondary weapons; the commonly published delta-only workaround
           is sufficient only when the secondary range is zero. */
        union {uint32_t bits;float real;} current,secondary;
        current.bits=UnitFieldRead(w,unit,f);
        if(f->weapon!=1u)return 0;
        secondary.bits=(uint32_t)((uint64_t (*)(uint64_t,uint32_t,int32_t))w->handlers[5])(unit,f->id,1);
        if((secondary.bits&0x7f800000u)==0x7f800000u)return 0;
        v.real=v.real-current.real+secondary.real;
        return ((uint8_t (*)(uint64_t,uint32_t,int32_t,float *))h)(unit,f->id,1,&v.real);
    }
    if(f->weapon){
        if(f->kind==2u)return ((uint8_t (*)(uint64_t,uint32_t,int32_t,float *))h)(unit,f->id,(int32_t)f->weapon-1,&v.real);
        return ((uint8_t (*)(uint64_t,uint32_t,int32_t,uint32_t))h)(unit,f->id,(int32_t)f->weapon-1,bits);
    }
    if(f->kind==2u)return ((uint8_t (*)(uint64_t,uint32_t,float *))h)(unit,f->id,&v.real);
    return ((uint8_t (*)(uint64_t,uint32_t,uint32_t))h)(unit,f->id,bits);
}
__declspec(dllexport) uint64_t BridgeUnitFieldQuery(void) {
    UnitFieldWork *w=(UnitFieldWork *)g_dispatch->work;uint32_t count,i,j,matched=0;
    if(!w || w->expected_tls!=g_dispatch->tls_value || w->action>1u || !w->count || w->count>32u ||
       (!!w->target_unit!=!!w->rawcode) || (w->action && (!w->target_unit || w->count!=1u))){if(w)w->error=910;return 0;}
    for(j=0;j<w->count;++j){UnitFieldSpec *f=&w->fields[j];
        if(!f->id || f->kind>2u || f->weapon>2u || !w->handlers[f->kind+(f->weapon?3u:0u)] ||
           (w->action && !w->handlers[6u+f->kind+(f->weapon?3u:0u)])){w->error=911;return 0;}}
    count=(uint32_t)BridgeSelect();
    if(!count || w->selection.error || !w->selection.destroyed || count!=w->selection.count){w->error=912;return count;}
    for(i=0;i<count;++i){SelectionRow *row=&w->selection.rows[i];
        if(w->target_unit && row->unit!=w->target_unit){w->statuses[i]=2u;++w->completed;continue;}++matched;
        if(w->selection.unit_type_id(row->unit)!=row->rawcode || (w->rawcode && row->rawcode!=w->rawcode)){w->error=913;return count;}
        for(j=0;j<w->count;++j){UnitFieldSpec *f=&w->fields[j];uint32_t k=i*32u+j;
            w->before[k]=UnitFieldRead(w,row->unit,f);w->after[k]=w->before[k];if(w->error)return count;
            if(w->action){uint8_t accepted;
                if(f->kind==2u && ((w->before[k]&0x7f800000u)==0x7f800000u || (f->target&0x7f800000u)==0x7f800000u)){w->error=915;return count;}
                if(w->selection.unit_type_id(row->unit)!=row->rawcode){w->error=913;return count;}
                accepted=UnitFieldWrite(w,row->unit,f,f->target);w->after[k]=UnitFieldRead(w,row->unit,f);if(w->error)return count;
                if(w->selection.unit_type_id(row->unit)!=row->rawcode){w->error=913;return count;}
                if(!accepted || w->after[k]!=f->target){
                    if(w->after[k]==w->before[k])w->error=accepted?917u:916u;
                    else {UnitFieldWrite(w,row->unit,f,w->before[k]);w->after[k]=UnitFieldRead(w,row->unit,f);w->error=w->after[k]==w->before[k]?917u:918u;}
                    return count;}
                if(w->after[k]!=w->before[k])++w->changed;
            }
        }w->statuses[i]=1u;++w->completed;
    }if(w->target_unit && matched!=1u)w->error=914;return count;
}
#ifdef BRIDGE_TEST
__declspec(dllexport) uint64_t BridgeUnitFieldTestRun(UnitFieldWork *work) {
    BridgeCommand command;BridgeCommand *previous=g_dispatch;uint64_t result;
    memset(&command,0,sizeof(command));command.work=work;command.tls_value=work->expected_tls;
    g_dispatch=&command;result=BridgeUnitFieldQuery();g_dispatch=previous;return result;
}
#endif
