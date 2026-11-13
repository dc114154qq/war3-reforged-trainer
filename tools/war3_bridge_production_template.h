typedef struct ProductionField {uint32_t id,kind,weapon,bits;} ProductionField;
typedef struct ProductionAbility {uint32_t rawcode,level;} ProductionAbility;
typedef struct ProductionTemplateWork {
    SelectionWork selection;
    uintptr_t handlers[25]; void *expected_tls;
    uint64_t building,owner,group,result_q;
    uint32_t unit_rawcode,building_rawcode,action,radius_bits,stock_current,stock_max,field_count,ability_count;
    ProductionField fields[32];
    ProductionAbility abilities[16];
    uint64_t targets[32];
    uint64_t rows[128];
} ProductionTemplateWork;
_Static_assert(sizeof(ProductionTemplateWork)==2672,"ProductionTemplateWork ABI");
__declspec(dllexport) const uint32_t production_template_abi[3]={0x24268120u,216u,2672u};

enum { PT_BIND=1u,PT_SCAN=2u,PT_APPLY=3u,PT_REMOVE_STOCK=4u,PT_BIND_BUILDINGS=5u,PT_PROBE_BUILDINGS=6u };
static void PTResult(ProductionTemplateWork *w,uint32_t error,uint32_t count){w->result_q=((uint64_t)count<<32)|error;}
static uint32_t PTFieldRead(ProductionTemplateWork *w,uint64_t unit,ProductionField *f){
    uintptr_t h=w->handlers[13u+f->kind+(f->weapon?3u:0u)];uint64_t r;
    if(f->weapon)r=((uint64_t (*)(uint64_t,uint32_t,int32_t))h)(unit,f->id,(int32_t)f->weapon-1);
    else r=((uint64_t (*)(uint64_t,uint32_t))h)(unit,f->id);
    return f->kind==0u?(uint32_t)(uint8_t)r:(uint32_t)r;
}
static uint8_t PTFieldWrite(ProductionTemplateWork *w,uint64_t unit,ProductionField *f){
    uintptr_t h=w->handlers[19u+f->kind+(f->weapon?3u:0u)];union{uint32_t bits;float real;}v;v.bits=f->bits;
    if(f->weapon){
        if(f->kind==2u)return ((uint8_t (*)(uint64_t,uint32_t,int32_t,float *))h)(unit,f->id,(int32_t)f->weapon-1,&v.real);
        return ((uint8_t (*)(uint64_t,uint32_t,int32_t,uint32_t))h)(unit,f->id,(int32_t)f->weapon-1,f->bits);
    }
    if(f->kind==2u)return ((uint8_t (*)(uint64_t,uint32_t,float *))h)(unit,f->id,&v.real);
    return ((uint8_t (*)(uint64_t,uint32_t,uint32_t))h)(unit,f->id,f->bits);
}
static uint64_t PTSelectedBuilding(ProductionTemplateWork *w){
    uint32_t count=(uint32_t)BridgeSelect();
    if(count!=1u || w->selection.error || !w->selection.destroyed){PTResult(w,1u,0u);return 0;}
    return w->selection.rows[0].unit;
}
__declspec(dllexport) uint64_t BridgeProductionTemplateQuery(void){
    ProductionTemplateWork *w=(ProductionTemplateWork *)g_dispatch->work;uint64_t building,player,group,unit;uint32_t i,j,count=0;union{uint32_t bits;float real;}radius,bx,by,ux,uy;
    if(!w || w->expected_tls!=g_dispatch->tls_value || !w->unit_rawcode || w->field_count>32u || w->ability_count>16u){if(w)PTResult(w,9u,0u);return 0;}
    if(w->action==PT_BIND || w->action==PT_REMOVE_STOCK){
        building=PTSelectedBuilding(w);if(!building)return 0;
        w->building=building;w->building_rawcode=((uint32_t (*)(uint64_t))w->handlers[8])(building);
        if(!w->building_rawcode){PTResult(w,2u,0u);return 0;}
        if(!((uint8_t (*)(uint64_t,uint32_t))w->handlers[13])(building,0x75626467u)){PTResult(w,10u,0u);return 0;}
        w->owner=((uint64_t (*)(uint64_t))w->handlers[2])(building);
        if(w->action==PT_BIND)((void (*)(uint64_t,uint32_t,uint32_t,uint32_t))w->handlers[0])(building,w->unit_rawcode,w->stock_current,w->stock_max);
        else ((void (*)(uint64_t,uint32_t))w->handlers[1])(building,w->unit_rawcode);
        PTResult(w,0u,1u);return 1;
    }
    if(w->action==PT_BIND_BUILDINGS){
        count=(uint32_t)BridgeSelect();
        if(!count || w->selection.error || !w->selection.destroyed){PTResult(w,11u,0u);return 0;}
        for(i=0;i<count;++i)w->rows[i]=w->selection.rows[i].unit;
        w->building=w->selection.rows[0].unit;w->building_rawcode=w->selection.rows[0].rawcode;
        PTResult(w,0u,count);return count;
    }
    if(w->action==PT_PROBE_BUILDINGS){
        for(i=0;i<32u && w->targets[i];++i){unit=w->targets[i];
            if(((uint32_t (*)(uint64_t))w->handlers[8])(unit)==w->unit_rawcode)w->rows[count++]=unit;
        }
        PTResult(w,0u,count);return count;
    }
    building=w->building;
    if(w->action==PT_SCAN && (!building || ((uint32_t (*)(uint64_t))w->handlers[8])(building)!=w->building_rawcode)){PTResult(w,2u,0u);return 0;}
    if(w->action==PT_SCAN){
        player=((uint64_t (*)(uint64_t))w->handlers[2])(building);w->owner=player;
        group=((uint64_t (*)(void))w->handlers[3])();w->group=group;if(!group){PTResult(w,3u,0u);return 0;}
        radius.bits=w->radius_bits;bx.bits=((uint32_t (*)(uint64_t))w->handlers[9])(building);by.bits=((uint32_t (*)(uint64_t))w->handlers[10])(building);
        __try{
            ((void (*)(uint64_t,uint64_t,uint64_t))w->handlers[4])(group,player,0);
            for(;;){
                unit=((uint64_t (*)(uint64_t))w->handlers[5])(group);if(!unit)break;
                ((uint8_t (*)(uint64_t,uint64_t))w->handlers[6])(group,unit);
                if(((uint32_t (*)(uint64_t))w->handlers[8])(unit)!=w->unit_rawcode)continue;
                ux.bits=((uint32_t (*)(uint64_t))w->handlers[9])(unit);uy.bits=((uint32_t (*)(uint64_t))w->handlers[10])(unit);
                if((ux.real-bx.real)*(ux.real-bx.real)+(uy.real-by.real)*(uy.real-by.real)>radius.real*radius.real)continue;
                if(count>=128u){PTResult(w,4u,count);return count;}w->rows[count++]=unit;
            }
        }__finally{((void (*)(uint64_t))w->handlers[7])(group);w->group=0;}
        PTResult(w,0u,count);return count;
    }
    if(w->action==PT_APPLY){
        for(i=0;i<32u && w->targets[i];++i){unit=w->targets[i];
            if(((uint32_t (*)(uint64_t))w->handlers[8])(unit)!=w->unit_rawcode){PTResult(w,5u,count);return count;}
            for(j=0;j<w->field_count;++j){ProductionField *f=&w->fields[j];
                if(!PTFieldWrite(w,unit,f)){PTResult(w,6u,count);return count;}
                if(PTFieldRead(w,unit,f)!=f->bits){PTResult(w,7u,count);return count;}
            }
            for(j=0;j<w->ability_count;++j){ProductionAbility *a=&w->abilities[j];
                if(!((uint8_t (*)(uint64_t,uint32_t))w->handlers[11])(unit,a->rawcode)){/* already present is allowed */}
                if(((int32_t (*)(uint64_t,uint32_t,uint32_t))w->handlers[12])(unit,a->rawcode,a->level)<=0){PTResult(w,8u,count);return count;}
            }
            w->rows[count++]=unit;
        }
        PTResult(w,0u,count);return count;
    }
    PTResult(w,9u,0u);return 0;
}
