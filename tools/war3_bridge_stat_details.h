/* Warcraft III 3.0 aggregated stat-details read/write bridge. */
#define STAT_DETAIL_COUNT 14u
#define STAT_PRESENT_MAX 64u

typedef struct StatDetailsWork {
    SelectionWork selection;
    AbilityLookupFn get_ability;
    AbilityIdFn get_ability_id;
    uint64_t (*convert_real_level_field)(uint32_t);
    uint64_t (*convert_boolean_level_field)(uint32_t);
    AbilityLevelFieldGetFn get_real_level;
    AbilityLevelFieldGetFn get_boolean_level;
    AbilityLevelFieldRealSetFn set_real_level;
    AbilityLevelFieldScalarSetFn set_boolean_level;
    uint8_t (*add_ability)(uint64_t,uint32_t);
    uint8_t (*remove_ability)(uint64_t,uint32_t);
    void (*hide_ability)(uint64_t,uint32_t,uint8_t);
    void *expected_tls;
    uint64_t target_unit;
    uint32_t action,stat_index,target_bits,controller_rawcode;
    uint32_t changed,error,completed,present_count;
    uint32_t before[STAT_DETAIL_COUNT],after[STAT_DETAIL_COUNT];
    uint32_t present[STAT_PRESENT_MAX];
    uint64_t diagnostic_ability,diagnostic_exception_address;
    uint32_t diagnostic_field,diagnostic_stage;
    uint64_t diagnostic_converted_field;
    uint64_t target_full_handle,resolver_base;
} StatDetailsWork;
_Static_assert(sizeof(StatDetailsWork)==1032,"StatDetailsWork ABI");
__declspec(dllexport) const uint32_t stat_details_batch_abi[3]={0x2426803Eu,216u,1032u};

enum { STAT_AI_XR=1,STAT_AI_SC,STAT_AI_CR,STAT_AI_AP,STAT_AI_VX,STAT_AI_SV,STAT_AI_LV,STAT_AI_SS };

static uint32_t StatDetailsKind(uint32_t id) {
    switch(id) {
    case 0x41497872u: case 0x41435371u: case 0x41435365u: case 0x41435372u:
    case 0x41435379u: case 0x416c6870u: case 0x41435375u: case 0x4143536fu:
    case 0x41435364u: case 0x41435367u: case 0x41636772u: case 0x4143536au:
    case 0x4143537au: case 0x41543561u: case 0x41435871u: case 0x41435877u:
    case 0x41435865u: case 0x41435872u: case 0x41435378u: case 0x41435874u:
    case 0x41617872u: case 0x41435363u: case 0x41435376u: case 0x41435879u:
    case 0x41435875u: case 0x41435362u: case 0x4143536eu: case 0x41435869u:
    case 0x4143586fu: return STAT_AI_XR;
    case 0x41497363u: case 0x41543562u: case 0x41617363u: case 0x41534371u:
    case 0x41534471u: case 0x41534377u: case 0x41534365u: case 0x41534372u:
    case 0x41534374u: case 0x41487735u: case 0x41534477u: case 0x41534379u:
    case 0x41534375u: case 0x41534338u: case 0x41534373u: return STAT_AI_SC;
    case 0x41496372u: case 0x41546372u: case 0x41434471u: case 0x41434477u:
    case 0x41434474u: case 0x41434479u: case 0x41434475u: case 0x41434469u:
    case 0x4143446fu: case 0x41434470u: case 0x55543662u: case 0x41434461u:
    case 0x41487739u: case 0x41434464u: case 0x41434466u: case 0x41726472u:
        return STAT_AI_CR;
    case 0x41496170u: case 0x41415071u: case 0x41415077u: case 0x41415065u:
    case 0x41415072u: case 0x41414471u: case 0x41414477u: case 0x41415074u:
    case 0x41415079u: case 0x41414465u: case 0x41415075u: case 0x41414472u:
    case 0x41415069u: case 0x4141506fu: case 0x55543562u: case 0x41543663u:
    case 0x41415070u: case 0x41415061u: case 0x41415073u: case 0x41414474u:
    case 0x41414479u: case 0x41414475u: case 0x41414469u: case 0x41415078u:
    case 0x4141446fu: return STAT_AI_AP;
    case 0x41497678u: case 0x414c7331u: case 0x414c7334u: case 0x414c7335u:
    case 0x414c7333u: case 0x414c7338u: case 0x414c3130u: return STAT_AI_VX;
    case 0x41497376u: case 0x41535671u: case 0x41535677u: case 0x41535665u:
    case 0x41535672u: case 0x41535674u: case 0x41535679u: case 0x41535675u:
    case 0x41535669u: case 0x41477376u: return STAT_AI_SV;
    case 0x41496c76u: case 0x41495271u: case 0x41495277u: case 0x41495279u:
    case 0x42543562u: case 0x41495275u: case 0x4149526fu: case 0x41495270u:
    case 0x41495235u: return STAT_AI_LV;
    case 0x41497373u: case 0x41535271u: case 0x41535277u: case 0x41535265u:
    case 0x41535274u: case 0x41535279u: case 0x41535275u: case 0x42543662u:
    case 0x41535269u: case 0x4153526fu: case 0x41535270u: return STAT_AI_SS;
    default:return 0;
    }
}

static float StatDetailsReal(StatDetailsWork *w,uint64_t ability,uint32_t field) {
    union { uint32_t bits; float value; } result;
    w->diagnostic_ability=ability;w->diagnostic_field=field;w->diagnostic_stage=1;
    uint64_t converted=w->convert_real_level_field(field);
    w->diagnostic_converted_field=converted;
    w->diagnostic_stage=2;
    result.bits=(uint32_t)w->get_real_level(ability,converted,0);return result.value;
}
static uint32_t StatDetailsBool(StatDetailsWork *w,uint64_t ability,uint32_t field) {
    w->diagnostic_ability=ability;w->diagnostic_field=field;w->diagnostic_stage=3;
#ifdef BRIDGE_TEST
    if(!w->resolver_base && !w->target_full_handle) {
    uint64_t converted=w->convert_boolean_level_field(field);
    w->diagnostic_converted_field=converted;
    w->diagnostic_stage=4;
    return (uint32_t)w->get_boolean_level(ability,converted,0)&1u;
    }
#endif
    /* These four 3.0 classes keep DataB as a real-valued cache entry,
       while the public boolean getter faults on that entry. Read the
       engine's initialized boolean instead, never infer it from rawcode.
       Verified paired DataB=0/1 instances and class initialization methods
       both place this byte at +0x128. Removed nodes remain owner-linked. */
    uint32_t id=w->get_ability_id(ability),class_id=0,vtable_rva=0;
    if(field==0x49637232u){class_id=0x41496372u;vtable_rva=0x23a50c8u;}
    else if(field==0x49736132u){class_id=0x41496170u;vtable_rva=0x23a5a78u;}
    else if(field==0x49737632u){class_id=0x41497376u;vtable_rva=0x23a6408u;}
    else if(field==0x496c7632u){class_id=0x41496c76u;vtable_rva=0x23a6d98u;}
    uint64_t owner=BridgeEffectResolveObjectTable(w->resolver_base,w->target_full_handle);
    uint64_t unit=owner?*(uint64_t *)(uintptr_t)(owner+0x90):0;
    uint32_t target_type=0,found=0,value=0;
    for(uint32_t i=0;i<w->selection.count;++i)
        if(w->selection.rows[i].unit==w->target_unit)target_type=w->selection.rows[i].rawcode;
    if(!class_id || !unit || !target_type || *(uint32_t *)(uintptr_t)(unit+0x70)!=target_type)
        {w->error=274;return 0;}
    uint64_t node=*(uint64_t *)(uintptr_t)(owner+0xd8),previous=owner+0xd0;
    for(uint32_t i=0;node && i<4096u;++i){
        uint64_t wrapper=node-0x38,data=*(uint64_t *)(uintptr_t)(wrapper+0x90);
        if(*(uint64_t *)(uintptr_t)(wrapper+0x38)!=previous ||
           *(uint64_t *)(uintptr_t)(wrapper+0x50)!=owner){w->error=274;return 0;}
        if(data && *(uint32_t *)(uintptr_t)(data+0x70)==id &&
           *(uint32_t *)(uintptr_t)(data+0x78)==id &&
           (*(uint32_t *)(uintptr_t)(data+0x38)&0x148u)==0x100u){
            uint64_t full=*(uint64_t *)(uintptr_t)(data+0x18);
            if(*(uint64_t *)(uintptr_t)(data+0x68)!=unit ||
               *(uint64_t *)(uintptr_t)data!=w->resolver_base+vtable_rva ||
               (uint32_t)(*(uint64_t *)(uintptr_t)(wrapper+0x18)>>32)!=class_id ||
               BridgeEffectResolveObjectTable(w->resolver_base,full)!=wrapper)
                {w->error=274;return 0;}
            uint32_t current=*(uint8_t *)(uintptr_t)(data+0x128);
            if(current>1 || (found && current!=value)){w->error=274;return 0;}
            value=current;++found;
        }
        previous=node;node=*(uint64_t *)(uintptr_t)(wrapper+0x40);
    }
    if(node || !found){w->error=274;return 0;}
    w->diagnostic_stage=5;
    return value;
}
static int StatDetailsAggregate(StatDetailsWork *w,uint64_t unit,float *out,
                                uint64_t *controller,uint32_t *controller_kind) {
    uint32_t i,kind,id;
    uint8_t critical_seen[2]={0,0};
    for(i=0;i<STAT_DETAIL_COUNT;++i)out[i]=0.0f;
    *controller=0;*controller_kind=0;
    w->present_count=0;
    for(i=0;i<4096u;++i) {
        uint64_t ability=w->get_ability(unit,i);
        float value;
        if(!ability)break;
        id=w->get_ability_id(ability);kind=StatDetailsKind(id);
        if(!kind)continue;
        if(w->present_count<STAT_PRESENT_MAX)w->present[w->present_count++]=id;
        if(id==w->controller_rawcode && !*controller){*controller=ability;*controller_kind=kind;}
        /* A single-field write must not depend on unrelated field getters.
           Keep enumerating identities, but read only the requested statistic
           and its discriminator. Full snapshots still read all statistics. */
        if(kind==STAT_AI_XR){
            float chance=0.0f;
            if(!w->action || w->stat_index==0 || w->stat_index==1)
                chance=StatDetailsReal(w,ability,0x4f637231u);
            if(!w->action || w->stat_index==0)out[0]+=chance;
            if((!w->action || w->stat_index==1) && chance>0.0f){
                value=StatDetailsReal(w,ability,0x49787232u);
                if(!critical_seen[0] || value>out[1])out[1]=value;
                critical_seen[0]=1;
            }
        }else if(kind==STAT_AI_SC){
            float chance=0.0f;
            if(!w->action || w->stat_index==2 || w->stat_index==3)
                chance=StatDetailsReal(w,ability,0x4f637231u);
            if(!w->action || w->stat_index==2)out[2]+=chance;
            if((!w->action || w->stat_index==3) && chance>0.0f){
                value=StatDetailsReal(w,ability,0x49787232u);
                if(!critical_seen[1] || value>out[3])out[3]=value;
                critical_seen[1]=1;
            }
        }else if(kind==STAT_AI_CR && (!w->action || w->stat_index==4 || w->stat_index==5)){
            value=StatDetailsReal(w,ability,0x49637231u);out[StatDetailsBool(w,ability,0x49637232u)?4:5]+=value;
        }else if(kind==STAT_AI_AP && (!w->action || w->stat_index==6 || w->stat_index==7)){
            value=StatDetailsReal(w,ability,0x49736131u);out[StatDetailsBool(w,ability,0x49736132u)?6:7]+=value;
        }else if(kind==STAT_AI_VX && (!w->action || w->stat_index==8))out[8]+=StatDetailsReal(w,ability,0x4976616du);
        else if(kind==STAT_AI_SV && (!w->action || w->stat_index==9 || w->stat_index==10)){
            value=StatDetailsReal(w,ability,0x49737631u);out[StatDetailsBool(w,ability,0x49737632u)?9:10]+=value;
        }else if(kind==STAT_AI_LV && (!w->action || w->stat_index==11 || w->stat_index==12)){
            value=StatDetailsReal(w,ability,0x496c7631u);out[StatDetailsBool(w,ability,0x496c7632u)?11:12]+=value;
        }else if(kind==STAT_AI_SS && (!w->action || w->stat_index==13))out[13]+=StatDetailsReal(w,ability,0x69737232u);
    }
    return !w->error && i<4096u && w->present_count<=STAT_PRESENT_MAX;
}

static int StatDetailsSpec(uint32_t index,uint32_t *kind,uint32_t *field,
                           uint32_t *flat_field,uint32_t *flat_value) {
    *flat_field=0;*flat_value=0;
    if(index==0){*kind=STAT_AI_XR;*field=0x4f637231u;}
    else if(index==1){*kind=STAT_AI_XR;*field=0x49787232u;}
    else if(index==2){*kind=STAT_AI_SC;*field=0x4f637231u;}
    else if(index==3){*kind=STAT_AI_SC;*field=0x49787232u;}
    else if(index==4||index==5){*kind=STAT_AI_CR;*field=0x49637231u;*flat_field=0x49637232u;*flat_value=index==4;}
    else if(index==6||index==7){*kind=STAT_AI_AP;*field=0x49736131u;*flat_field=0x49736132u;*flat_value=index==6;}
    else if(index==8){*kind=STAT_AI_VX;*field=0x4976616du;}
    else if(index==9||index==10){*kind=STAT_AI_SV;*field=0x49737631u;*flat_field=0x49737632u;*flat_value=index==9;}
    else if(index==11||index==12){*kind=STAT_AI_LV;*field=0x496c7631u;*flat_field=0x496c7632u;*flat_value=index==11;}
    else if(index==13){*kind=STAT_AI_SS;*field=0x69737232u;}
    else return 0;
    return 1;
}

__declspec(dllexport) uint64_t BridgeStatDetailsQuery(void) {
    StatDetailsWork *w=(StatDetailsWork *)g_dispatch->work;
    uint32_t count,i,matches=0,kind=0,expected_kind=0,field=0,flat_field=0,flat_value=0;
    uint32_t old_bits=0,old_flat=0;uint64_t controller=0,write_controller=0;
    uint8_t added=0,captured=0,write_attempted=0,flat_write_attempted=0;
    uint64_t critical_abilities[STAT_PRESENT_MAX]={0};
    uint32_t critical_old[STAT_PRESENT_MAX]={0},critical_chance[STAT_PRESENT_MAX]={0};
    uint32_t critical_count=0,critical_attempted=0;
    union { uint32_t bits; float value; } target,old_value,new_value;
    float before[STAT_DETAIL_COUNT],after[STAT_DETAIL_COUNT],other,diff;
    if(!w || w->expected_tls!=g_dispatch->tls_value || w->action>2 || w->stat_index>=STAT_DETAIL_COUNT ||
       !w->get_ability || !w->get_ability_id || !w->convert_real_level_field ||
       !w->convert_boolean_level_field || !w->get_real_level || !w->get_boolean_level ||
       !w->set_real_level || !w->set_boolean_level || !w->add_ability || !w->remove_ability ||
       !w->hide_ability) {
        if(w)w->error=260;return 0;
    }
    target.bits=w->target_bits;
    if(target.value!=target.value || target.value>1000000.0f || target.value< -1000000.0f){w->error=261;return 0;}
    count=(uint32_t)BridgeSelect();
    if(w->selection.error || !w->selection.destroyed || !count){w->error=262;return count;}
    if(!w->target_unit)w->target_unit=w->selection.rows[0].unit;
    for(i=0;i<count;++i)if(w->selection.rows[i].unit==w->target_unit)++matches;
    if(matches!=1){w->error=263;return count;}
    if(w->action==2){
        uint64_t ability=0;uint32_t found=0,hidden=0;
        if(!w->controller_rawcode || w->stat_index || w->target_bits){w->error=265;return count;}
        __try {
            for(i=0;i<4096u;++i){
                uint64_t current=w->get_ability(w->target_unit,i);
                if(!current)break;
                if(w->get_ability_id(current)==w->controller_rawcode){ability=current;++found;}
            }
            if(i==4096u || found!=1 || !ability){w->error=267;return count;}
            w->diagnostic_ability=ability;w->diagnostic_stage=10;
            hidden=1;w->hide_ability(w->target_unit,w->controller_rawcode,1);
            w->diagnostic_stage=11;w->hide_ability(w->target_unit,w->controller_rawcode,0);
            hidden=0;w->diagnostic_stage=12;w->changed=1;w->completed=1;
        } __except((w->diagnostic_exception_address=(uint64_t)(uintptr_t)GetExceptionInformation()->ExceptionRecord->ExceptionAddress,EXCEPTION_EXECUTE_HANDLER)) {
            w->error=GetExceptionCode();
            if(hidden){
                __try {w->hide_ability(w->target_unit,w->controller_rawcode,0);}
                __except(EXCEPTION_EXECUTE_HANDLER){w->error=273;}
            }
        }
        return count;
    }
    __try {
        if(!StatDetailsAggregate(w,w->target_unit,before,&controller,&kind)){if(!w->error)w->error=264;return count;}
        for(i=0;i<STAT_DETAIL_COUNT;++i){union{float value;uint32_t bits;}v;v.value=before[i];w->before[i]=w->after[i]=v.bits;}
        if(w->action==1) {
            if(!w->controller_rawcode || !StatDetailsSpec(w->stat_index,&expected_kind,&field,&flat_field,&flat_value) ||
               StatDetailsKind(w->controller_rawcode)!=expected_kind){w->error=265;return count;}
            if(w->stat_index==1 || w->stat_index==3){
                uint64_t converted=w->convert_real_level_field(field);
                for(i=0;i<4096u;++i){
                    uint64_t ability=w->get_ability(w->target_unit,i);
                    union {float value;uint32_t bits;} chance,damage;
                    if(!ability)break;
                    if(StatDetailsKind(w->get_ability_id(ability))!=expected_kind)continue;
                    chance.value=StatDetailsReal(w,ability,0x4f637231u);
                    if(w->error)goto rollback;
                    if((chance.bits&0x7f800000u)==0x7f800000u){w->error=277;goto rollback;}
                    if(chance.value<=0.0f)continue;
                    if(critical_count==STAT_PRESENT_MAX){w->error=276;goto rollback;}
                    damage.value=StatDetailsReal(w,ability,field);
                    if(w->error)goto rollback;
                    if((damage.bits&0x7f800000u)==0x7f800000u){w->error=277;goto rollback;}
                    critical_abilities[critical_count]=ability;
                    critical_old[critical_count]=damage.bits;
                    critical_chance[critical_count]=chance.bits;
                    ++critical_count;
                }
                if(i==4096u || !critical_count){w->error=275;goto rollback;}
                for(i=0;i<critical_count;++i){
                    critical_attempted=i+1;
                    if(!w->set_real_level(critical_abilities[i],converted,0,&target.value)){
                        w->error=269;goto rollback;
                    }
                }
                for(i=0;i<critical_count;++i){
                    union {float value;uint32_t bits;} chance,damage;
                    chance.value=StatDetailsReal(w,critical_abilities[i],0x4f637231u);
                    damage.value=StatDetailsReal(w,critical_abilities[i],field);
                    if(w->error || chance.bits!=critical_chance[i] || damage.bits!=target.bits){
                        if(!w->error)w->error=271;
                        goto rollback;
                    }
                }
                if(!StatDetailsAggregate(w,w->target_unit,after,&controller,&kind)){
                    if(!w->error)w->error=270;goto rollback;
                }
                diff=after[w->stat_index]-target.value;if(diff<0.0f)diff=-diff;
                if(diff>0.0005f){w->error=271;goto rollback;}
                for(i=0;i<STAT_DETAIL_COUNT;++i){union{float value;uint32_t bits;}v;v.value=after[i];w->after[i]=v.bits;}
                w->changed=1;w->completed=1;return count;
            }
            if(!controller) {
                if(!w->add_ability(w->target_unit,w->controller_rawcode)){w->error=266;return count;}
                added=1;
                for(i=0;i<4096u;++i){controller=w->get_ability(w->target_unit,i);if(!controller)break;
                    if(w->get_ability_id(controller)==w->controller_rawcode)break;controller=0;}
                if(!controller){w->error=267;goto rollback;}
                /* Item critical controllers ship with nonzero default
                   chance. Creating one for damage must not silently grant
                   that chance (and vice versa for a damage default). */
                if(expected_kind==STAT_AI_XR || expected_kind==STAT_AI_SC){
                    float zero=0.0f;
                    uint32_t sibling=(w->stat_index==0 || w->stat_index==2)?0x49787232u:0x4f637231u;
                    if(!w->set_real_level(controller,w->convert_real_level_field(sibling),0,&zero)){
                        w->error=272;goto rollback;
                    }
                }
            }
            /* Do not alter visibility of a pre-existing native skill. */
            if(added)w->hide_ability(w->target_unit,w->controller_rawcode,1);
            old_bits=(uint32_t)w->get_real_level(controller,w->convert_real_level_field(field),0);old_value.bits=old_bits;
            if(flat_field)old_flat=StatDetailsBool(w,controller,flat_field);
            if(w->error)goto rollback;
            write_controller=controller;captured=1;
            other=before[w->stat_index];
            if(!added && (!flat_field || old_flat==flat_value))other-=old_value.value;
            new_value.value=target.value-other;
            write_attempted=1;
            if(flat_field && old_flat!=flat_value){
                flat_write_attempted=1;
                if(!w->set_boolean_level(controller,w->convert_boolean_level_field(flat_field),0,flat_value)){w->error=268;goto rollback;}
            }
            if(!w->set_real_level(controller,w->convert_real_level_field(field),0,&new_value.value)){w->error=269;goto rollback;}
            if(!StatDetailsAggregate(w,w->target_unit,after,&controller,&kind)){if(!w->error)w->error=270;goto rollback;}
            diff=after[w->stat_index]-target.value;if(diff<0.0f)diff=-diff;
            if(diff>0.0005f){w->error=271;goto rollback;}
            for(i=0;i<STAT_DETAIL_COUNT;++i){union{float value;uint32_t bits;}v;v.value=after[i];w->after[i]=v.bits;}
            w->changed=1;
        }
        w->completed=1;return count;
rollback:
        ; /* Cleanup also runs after an exception, below the SEH boundary. */
    } __except((w->diagnostic_exception_address=(uint64_t)(uintptr_t)GetExceptionInformation()->ExceptionRecord->ExceptionAddress,EXCEPTION_EXECUTE_HANDLER)) {w->error=GetExceptionCode();}
    if(w->error && critical_attempted){
        __try {
            uint32_t restored=1;
            for(i=0;i<critical_attempted;++i){
                union {float value;uint32_t bits;} old;
                old.bits=critical_old[i];
                if(!w->set_real_level(critical_abilities[i],w->convert_real_level_field(field),0,&old.value))restored=0;
            }
            for(i=0;i<critical_attempted;++i){
                union {float value;uint32_t bits;} chance,damage;
                chance.value=StatDetailsReal(w,critical_abilities[i],0x4f637231u);
                damage.value=StatDetailsReal(w,critical_abilities[i],field);
                if(chance.bits!=critical_chance[i] || damage.bits!=critical_old[i])restored=0;
            }
            if(!restored)w->error=273;
        } __except(EXCEPTION_EXECUTE_HANDLER){w->error=273;}
        w->changed=0;w->completed=0;
    }
    if(w->error && (added || (captured && write_attempted))){
        __try {
            if(added){
                if(!w->remove_ability(w->target_unit,w->controller_rawcode))w->error=273;
            }else{
                uint32_t restored=1;
                if(flat_write_attempted)restored=w->set_boolean_level(write_controller,w->convert_boolean_level_field(flat_field),0,old_flat);
                old_value.bits=old_bits;
                if(!w->set_real_level(write_controller,w->convert_real_level_field(field),0,&old_value.value))restored=0;
                if((uint32_t)w->get_real_level(write_controller,w->convert_real_level_field(field),0)!=old_bits)restored=0;
                if(flat_field && StatDetailsBool(w,write_controller,flat_field)!=old_flat)restored=0;
                if(!restored)w->error=273;
            }
        } __except(EXCEPTION_EXECUTE_HANDLER){w->error=273;}
        w->changed=0;w->completed=0;
    }
    return count;
}
