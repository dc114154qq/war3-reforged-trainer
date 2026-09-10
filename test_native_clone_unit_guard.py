"""Run production clone dispatch with same-type recycled source/target units."""
import ctypes
import faulthandler
import os
from pathlib import Path
import shutil
import subprocess
import pytest
import war3_reforged_trainer as module
from test_native_identity_guard import HARNESS

HARNESS=HARNESS.replace('#include "HELPER_SOURCE"',r'''
static LONG clone_allocations;
static unsigned clone_fail_alloc;
static LPVOID clone_heap_alloc(HANDLE heap,DWORD flags,SIZE_T size) {
    if(clone_fail_alloc) return NULL;
    LPVOID memory=HeapAlloc(heap,flags,size);
    if(memory) InterlockedIncrement(&clone_allocations);
    return memory;
}
static BOOL clone_heap_free(HANDLE heap,DWORD flags,LPVOID memory) {
    BOOL ok=HeapFree(heap,flags,memory);
    if(ok && memory) InterlockedDecrement(&clone_allocations);
    return ok;
}
#define HeapAlloc clone_heap_alloc
#define HeapFree clone_heap_free
#include "HELPER_SOURCE"
#undef HeapAlloc
#undef HeapFree
''')

CLONE=r'''
static uint8_t clone_owner[0x98];
static unsigned clone_calls,clone_at,clone_fault,clone_created,clone_removed,clone_present;
static int32_t clone_level,clone_xp,clone_stats[3],clone_points,clone_hp,clone_mana;
static float clone_life,clone_mp;
static unsigned clone_features;
static int32_t clone_item_charges[6],clone_ability_rank;
static uint32_t clone_item_values[6][256];
static uint8_t clone_item_storage[12][0x78],clone_item_wrappers[12][0x98];
static uint8_t *clone_item_objects[12];
static unsigned clone_item_present[12],clone_item_ready,clone_fault_applied,clone_creating,clone_item_call,clone_reverse_slots;
static uint64_t clone_item_full[12];
static uint8_t clone_ab_storage[2][257][0x80],clone_ab_wrappers[2][257][0x98];
static uint8_t *clone_ab_objects[2][257];
static uint64_t clone_ab_full[2][257];
static unsigned clone_ab_count,clone_ab_present[2][257],clone_ab_ready[2],clone_ab_adds,clone_ab_call;
static int32_t clone_ab_levels[257];
static const uint64_t clone_full=0xabcde00000008ULL;
static uint64_t clone_resolve(uint64_t h) {return h==8?(clone_present?(uint64_t)(uintptr_t)other:0):fake_unit(h);}
static uint64_t clone_resolve_item(uint64_t h) {
    return h>=70 && h<76?(uint64_t)(uintptr_t)clone_item_objects[h-70]:
           h>=80 && h<86?(uint64_t)(uintptr_t)clone_item_objects[h-80+6]:0;
}
static uint64_t clone_resolve_ability(uint64_t h) {
    unsigned side=h>=0x3000,idx=(unsigned)(h-(side?0x3000:0x2000));
    return idx<257?(uint64_t)(uintptr_t)clone_ab_objects[side][idx]:0;
}
static uint64_t clone_agent(uint32_t lo,uint32_t hi) {
    uint64_t id=((uint64_t)hi<<32)|lo;
    for(unsigned side=0;side<2;++side) for(unsigned n=0;n<clone_ab_count;++n)
        if(id==*(uint64_t *)(clone_ab_wrappers[side][n]+0x20)) return (uint64_t)(uintptr_t)clone_ab_wrappers[side][n];
    for(unsigned n=0;n<12;++n)
        if(id==*(uint64_t *)(clone_item_wrappers[n]+0x20)) return (uint64_t)(uintptr_t)clone_item_wrappers[n];
    if(id==*(uint64_t *)(clone_owner+0x20)) return (uint64_t)(uintptr_t)clone_owner;
    return fake_agent(lo,hi);
}
static void clone_step(uint64_t h) {
    if(h==7 && *(uint64_t *)(object+0x18)!=full) ++bad_arguments;
    if(h==8 && (!clone_present || *(uint64_t *)(other+0x18)!=clone_full)) ++bad_arguments;
    ++clone_calls;
    if(clone_calls!=clone_at) return;
    if(clone_fault==1) {clone_fault_applied=1;*(uint64_t *)(object+0x18)+=1;*(uint64_t *)(owner+0x20)+=1;}
    if(clone_fault==2 && clone_present && !clone_creating) {clone_fault_applied=1;*(uint64_t *)(other+0x18)+=1;*(uint64_t *)(clone_owner+0x20)+=1;}
    if(clone_fault>=9 && clone_fault<=14) {
        unsigned n=((clone_fault-9)&1)?6:0;
        if((n && !clone_item_ready) || (!n && !clone_created)) return;
        /* UnitItemInSlot itself cannot execute map triggers. Membership
           changes are injected in copying/creation callbacks, not guard reads. */
        if((clone_fault==11 || clone_fault==12) && !clone_item_call && !clone_creating) return;
        clone_fault_applied=1;
        if(clone_fault<=10) {*(uint64_t *)(clone_item_objects[n]+0x18)+=1;*(uint64_t *)(clone_item_wrappers[n]+0x20)+=1;}
        else if(clone_fault<=12) clone_item_present[n]=0;
        else *(uint64_t *)(clone_item_wrappers[n]+0x18)=0;
    }
    if(clone_fault>=25 && clone_fault<=32) {
        unsigned side=(clone_fault-25)&1;
        if(!clone_ab_ready[side]) return;
        if(clone_fault>=31 && !clone_ab_call && !clone_item_call && !clone_creating) return;
        clone_fault_applied=1;
        if(clone_fault<=26) {*(uint64_t *)(clone_ab_objects[side][0]+0x18)+=1;*(uint64_t *)(clone_ab_wrappers[side][0]+0x20)+=1;}
        else if(clone_fault<=28) *(uint64_t *)(clone_ab_objects[side][0]+0x68)=0;
        else if(clone_fault<=30) *(uint64_t *)(clone_ab_wrappers[side][0]+0x18)=0;
        else clone_ab_present[side][0]=0;
    }
}
static void clone_item_step(uint64_t h) {
    unsigned n=h>=80?(unsigned)(h-80+6):(unsigned)(h-70);
    if(n>=12 || !clone_item_present[n] ||
       *(uint64_t *)(clone_item_objects[n]+0x18)!=clone_item_full[n] ||
       *(uint64_t *)(clone_item_wrappers[n]+0x18)!=0x6974656d2b61676cULL) ++bad_arguments;
    clone_item_call=1;clone_step(n>=6?8:7);clone_item_call=0;
    if((clone_fault==23 || clone_fault==24) && clone_item_ready && !clone_fault_applied) {
        DWORD old;unsigned target=clone_fault==24?6:0;
        if(!VirtualProtect(clone_item_objects[target],0x1000,PAGE_NOACCESS,&old)) ++bad_arguments;
        clone_fault_applied=1;
    }
}
static uint32_t clone_type(uint64_t h) {clone_step(h);return clone_fault==5?0x6870616c:0x68666f6f;}
static uint64_t clone_player(void) {clone_step(7);return 2;}
static uint64_t clone_owning(uint64_t h) {clone_step(h);return 2;}
static uint32_t clone_facing(uint64_t h) {clone_step(h);return 0;}
static uint64_t clone_create(uint64_t p,uint32_t id,float *x,float *y,float *f) {
    if(p!=2 || id!=0x68666f6f || *x!=12 || *y!=-4 || *f) ++bad_arguments;
    if(clone_fault==6) {clone_step(7);return 7;}
    ++clone_created;clone_present=1;
    *(uint64_t *)(other+0x18)=*(uint64_t *)(clone_owner+0x20)=clone_full;
    *(uint64_t *)(clone_owner+0x18)=0x2b7733752b61676cULL;
    *(uint64_t *)(clone_owner+0x90)=(uint64_t)(uintptr_t)other;
    if(clone_fault==7) *(uint64_t *)(clone_owner+0x90)=0;
    if(clone_fault==37) {clone_ab_present[1][0]=1;clone_ab_levels[0]=1;}
    if(clone_fault==44) clone_ab_present[0][clone_ab_count]=1;
    clone_creating=1;clone_step(7);clone_creating=0;return 8;
}
static int32_t clone_get_level(uint64_t h) {clone_step(h);return h==7?5:clone_level;}
static int32_t clone_get_xp(uint64_t h) {clone_step(h);return h==7?500:clone_xp;}
static void clone_set_level(uint64_t h,int32_t v,uint32_t eye) {clone_level=v;clone_step(h);}
static void clone_set_xp(uint64_t h,int32_t v,uint32_t eye) {clone_xp=v;clone_step(h);}
static int32_t clone_str(uint64_t h,uint32_t bonus) {clone_step(h);return h==7?10:clone_stats[0];}
static int32_t clone_agi(uint64_t h,uint32_t bonus) {clone_step(h);return h==7?20:clone_stats[1];}
static int32_t clone_int(uint64_t h,uint32_t bonus) {clone_step(h);return h==7?30:clone_stats[2];}
static void clone_set_str(uint64_t h,int32_t v,uint32_t permanent) {clone_stats[0]=v;clone_step(h);}
static void clone_set_agi(uint64_t h,int32_t v,uint32_t permanent) {clone_stats[1]=v;clone_step(h);}
static void clone_set_int(uint64_t h,int32_t v,uint32_t permanent) {clone_stats[2]=v;clone_step(h);}
static int32_t clone_get_points(uint64_t h) {clone_step(h);return h==7?9:clone_points;}
static uint32_t clone_modify_points(uint64_t h,int32_t n) {clone_points+=n;clone_step(h);return 1;}
static int32_t clone_max_hp(uint64_t h) {clone_step(h);return h==7?200:clone_hp;}
static int32_t clone_max_mp(uint64_t h) {clone_step(h);return h==7?100:clone_mana;}
static void clone_set_hp(uint64_t h,int32_t n) {clone_hp=n;clone_step(h);}
static void clone_set_mp(uint64_t h,int32_t n) {clone_mana=n;clone_step(h);}
static uint32_t clone_get_life(uint64_t h) {clone_step(h);float f=h==7?150:clone_life;uint32_t b;memcpy(&b,&f,4);return b;}
static uint32_t clone_get_state(uint64_t h,int32_t n) {clone_step(h);float f=h==7?75:clone_mp;uint32_t b;memcpy(&b,&f,4);return b;}
static void clone_set_life(uint64_t h,float *f) {clone_life=*f;clone_step(h);}
static void clone_set_state(uint64_t h,int32_t n,float *f) {
    clone_mp=*f;
    if(clone_fault==40) *(uint64_t *)(clone_ab_objects[1][0]+0x18)+=1;
    clone_step(h);
}
static void clone_ability_step(unsigned side,unsigned idx) {
    if(!clone_ab_present[side][idx] ||
       *(uint64_t *)(clone_ab_objects[side][idx]+0x18)!=clone_ab_full[side][idx] ||
       *(uint64_t *)(clone_ab_objects[side][idx]+0x68)!=(uint64_t)(uintptr_t)(side?other:object) ||
       *(uint64_t *)(clone_ab_wrappers[side][idx]+0x18)!=0x414d67632b61676cULL) ++bad_arguments;
    clone_ab_call=1;clone_step(side?8:7);clone_ab_call=0;
    if((clone_fault==47 || clone_fault==48) && clone_ab_ready[clone_fault==48] && !clone_fault_applied) {
        DWORD old;
        if(!VirtualProtect(clone_ab_objects[clone_fault==48][0],0x1000,PAGE_NOACCESS,&old)) ++bad_arguments;
        clone_fault_applied=1;
    }
}
static uint64_t clone_ability(uint64_t h,int32_t n) {
    clone_step(h);
    if(clone_fault==42 && h==7 && n==1) return 0x2000;
    return n<257 && clone_ab_present[h==8][n]?(h==8?0x3000:0x2000)+n:0;
}
static uint32_t clone_ability_id(uint64_t h) {
    unsigned side=h>=0x3000,n=(unsigned)(h-(side?0x3000:0x2000));
    if(n>=257) {++bad_arguments;return 0;}
    uint32_t id=*(uint32_t *)(clone_ab_objects[side][n]+0x70);
    clone_ab_ready[side]=1;clone_ability_step(side,n);return clone_fault==36?id+1:id;
}
static int clone_ability_index(uint64_t h,uint32_t id) {
    for(unsigned n=0;n<clone_ab_count;++n)
        if(clone_ab_present[h==8][n] && *(uint32_t *)(clone_ab_objects[h==8][n]+0x70)==id) return (int)n;
    return -1;
}
static uint64_t clone_ability_lookup(uint64_t h,uint32_t id) {
    int n=clone_ability_index(h,id);clone_step(h);
    if(clone_fault==38 && h==8) return 0x2000;
    return n<0?0:(h==8?0x3000:0x2000)+n;
}
static int32_t clone_ability_level(uint64_t h,uint32_t id) {
    int n=clone_ability_index(h,id);
    if(n<0) {clone_step(h);return 0;}
    clone_ab_ready[h==8]=1;clone_ability_step(h==8,(unsigned)n);
    return h==7?3:clone_ab_levels[n];
}
static uint32_t clone_add_ability(uint64_t h,uint32_t id) {
    unsigned n=0;++clone_ab_adds;
    for(;n<clone_ab_count;++n) if(*(uint32_t *)(clone_ab_objects[0][n]+0x70)==id) break;
    if(n>=clone_ab_count || h!=8) {++bad_arguments;return 0;}
    if(clone_fault!=33 && clone_fault!=34) {clone_ab_present[1][n]=1;clone_ab_levels[n]=1;}
    clone_ab_call=1;clone_step(h);clone_ab_call=0;return clone_fault==33 || clone_fault==35?0:1;
}
static int32_t clone_set_ability(uint64_t h,uint32_t id,int32_t n) {
    int idx=clone_ability_index(h,id);
    if(idx<0) {++bad_arguments;return 0;}
    clone_ability_rank=clone_ab_levels[idx]=clone_fault==8 || clone_fault==39?1:n;
    if(clone_fault==22) clone_item_present[6]=0;
    clone_ability_step(h==8,(unsigned)idx);return clone_ability_rank;
}
static uint64_t clone_slot(uint64_t h,int32_t n) {
    clone_step(h);
    if(clone_fault==19 && h==7 && n==1) return 70;
    if(clone_fault==20 && h==8 && n==1 && clone_item_present[6]) return 80;
    return clone_item_present[(h==8?6:0)+n]?(h==8?80:70)+n:0;
}
static uint32_t clone_item_type(uint64_t h) {clone_item_step(h);return 0x49303031;}
static uint64_t clone_item_add(uint64_t h,uint32_t id) {
    if(id!=0x49303031) ++bad_arguments;
    unsigned slot=6;
    for(unsigned n=0;n<6;++n) {unsigned candidate=clone_reverse_slots?5-n:n;if(!clone_item_present[6+candidate]) {slot=candidate;break;}}
    if(slot==6) {++bad_arguments;return 0;}
    clone_item_present[6+slot]=clone_fault==16?0:1;
    if(clone_fault==17) *(uint32_t *)(clone_item_objects[6+slot]+0x70)=0x49303032;
    if(clone_fault==21) clone_item_present[1]=1;
    clone_step(h);return clone_fault==15?70:80+slot;
}
static int32_t clone_charges(uint64_t h) {clone_item_step(h);return h<80?4:clone_item_charges[h-80];}
static void clone_charges_set(uint64_t h,int32_t n) {clone_item_charges[h-80]=n;clone_item_step(h);}
static uint64_t clone_item_get(uint64_t h,uint32_t field) {
    clone_item_ready=1;clone_item_step(h);
    return h<80?(field==0x69736361?0x3fc00000u:1):clone_item_values[h-80][field&255];
}
static uint64_t clone_item_set(uint64_t h,uint32_t field,uint32_t n) {clone_item_values[h-80][field&255]=n;clone_item_step(h);return 1;}
static uint64_t clone_item_real_set(uint64_t h,uint32_t field,float *n) {memcpy(&clone_item_values[h-80][field&255],n,4);clone_item_step(h);return 1;}
static void clone_remove(uint64_t h) {
    if(h!=8 || !clone_present || *(uint64_t *)(other+0x18)!=clone_full) ++bad_arguments;
    ++clone_removed;clone_present=0;
}
__declspec(dllexport) DWORD clone_test(const wchar_t *directory,unsigned hero,unsigned at,unsigned failure,unsigned *out) {
    NativeCommand cmd={0};wchar_t path[MAX_PATH];DWORD bytes;
    if(wcslen(directory)>=MAX_PATH-1) return ERROR_INVALID_PARAMETER;
    wcscpy(test_directory,directory);ZeroMemory(object,sizeof(object));ZeroMemory(owner,sizeof(owner));
    ZeroMemory(other,sizeof(other));ZeroMemory(clone_owner,sizeof(clone_owner));
    *(uint64_t *)(object+0x18)=full;*(uint64_t *)(owner+0x18)=0x2b7733752b61676cULL;
    *(uint64_t *)(owner+0x20)=full;*(uint64_t *)(owner+0x90)=(uint64_t)(uintptr_t)object;
    fault=bad_arguments=clone_calls=clone_created=clone_removed=clone_present=0;clone_at=at;clone_fault=failure;
    clone_fail_alloc=failure==49;
    clone_features=hero&2;clone_ability_rank=0;ZeroMemory(clone_item_values,sizeof(clone_item_values));ZeroMemory(clone_item_charges,sizeof(clone_item_charges));
    clone_ab_count=hero&128?256:hero&(64|256)?3:clone_features?1:0;
    if(failure==41) clone_ab_count=257;
    if(failure==42 || failure==43) clone_ab_count=2;
    ZeroMemory(clone_ab_storage,sizeof(clone_ab_storage));ZeroMemory(clone_ab_wrappers,sizeof(clone_ab_wrappers));
    ZeroMemory(clone_ab_present,sizeof(clone_ab_present));ZeroMemory(clone_ab_levels,sizeof(clone_ab_levels));
    clone_ab_ready[0]=clone_ab_ready[1]=clone_ab_adds=clone_ab_call=0;
    for(unsigned side=0;side<2;++side) for(unsigned n=0;n<257;++n) {
        clone_ab_objects[side][n]=clone_ab_storage[side][n];
        if(n==0 && ((failure==47 && side==0) || (failure==48 && side==1))) {
            clone_ab_objects[side][n]=VirtualAlloc(NULL,0x1000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
            if(!clone_ab_objects[side][n]) return GetLastError();
        }
        clone_ab_full[side][n]=((uint64_t)(side+1)<<48)+0x2000+n;
        uint32_t id=0x41303031+(failure==43?0:n);
        if(hero&256) id=n==0?0x416d6f76:n==1?0x4161746b:0x41303031;
        *(uint64_t *)(clone_ab_objects[side][n]+0x18)=*(uint64_t *)(clone_ab_wrappers[side][n]+0x20)=clone_ab_full[side][n];
        *(uint64_t *)(clone_ab_objects[side][n]+0x68)=(uint64_t)(uintptr_t)(side?other:object);
        *(uint32_t *)(clone_ab_objects[side][n]+0x70)=*(uint32_t *)(clone_ab_objects[side][n]+0x78)=id;
        *(uint64_t *)(clone_ab_wrappers[side][n]+0x18)=0x414d67632b61676cULL;
        *(uint64_t *)(clone_ab_wrappers[side][n]+0x50)=(uint64_t)(uintptr_t)(side?clone_owner:owner);
        *(uint64_t *)(clone_ab_wrappers[side][n]+0x90)=(uint64_t)(uintptr_t)clone_ab_objects[side][n];
        clone_ab_present[side][n]=side==0 && n<clone_ab_count;
    }
    ZeroMemory(clone_item_present,sizeof(clone_item_present));
    unsigned source_mask=hero&8?63:hero&16?0x22:1;
    for(unsigned n=0;n<6;++n) clone_item_present[n]=clone_features && (source_mask&(1u<<n));
    clone_reverse_slots=(hero&32)!=0;clone_item_ready=clone_fault_applied=clone_creating=clone_item_call=0;
    ZeroMemory(clone_item_storage,sizeof(clone_item_storage));ZeroMemory(clone_item_wrappers,sizeof(clone_item_wrappers));
    for(unsigned n=0;n<12;++n) clone_item_objects[n]=clone_item_storage[n];
    if(failure==23 || failure==24) {
        unsigned n=failure==24?6:0;
        clone_item_objects[n]=VirtualAlloc(NULL,0x1000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
        if(!clone_item_objects[n]) return GetLastError();
    }
    for(unsigned n=0;n<12;++n) {
        clone_item_full[n]=0xaaa000000070ULL+n;
        *(uint64_t *)(clone_item_objects[n]+0x18)=*(uint64_t *)(clone_item_wrappers[n]+0x20)=clone_item_full[n];
        *(uint32_t *)(clone_item_objects[n]+0x70)=0x49303031;
        *(uint64_t *)(clone_item_wrappers[n]+0x18)=0x6974656d2b61676cULL;
        *(uint64_t *)(clone_item_wrappers[n]+0x90)=(uint64_t)(uintptr_t)clone_item_objects[n];
    }
    clone_level=1;clone_xp=clone_points=clone_stats[0]=clone_stats[1]=clone_stats[2]=0;
    clone_hp=100;clone_mana=50;clone_life=100;clone_mp=50;
    g_persistent_unit_resolver=(uint64_t)(uintptr_t)clone_resolve;g_persistent_agent_resolver=(uint64_t)(uintptr_t)clone_agent;
    g_persistent_item_resolver=(uint64_t)(uintptr_t)clone_resolve_item;
    if(failure==18) g_persistent_item_resolver=0;
    g_persistent_ability_resolver=failure==45?0:(uint64_t)(uintptr_t)clone_resolve_ability;
    for(unsigned n=0;n<sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]);++n) {
        g_persistent_natives[n].name=g_persistent_native_names[n];
        if(!strcmp(g_persistent_natives[n].name,"BlzGetUnitAbility"))
            g_persistent_natives[n].handler=failure==46?0:(uint64_t)(uintptr_t)clone_ability_lookup;
    }
    cmd.magic=WAR3_NATIVE_MAGIC;cmd.version=WAR3_NATIVE_VERSION;cmd.status=WAR3_NATIVE_STATUS_PENDING;
    cmd.op_count=15;cmd.unit_handle=7;cmd.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;
    cmd.ops[0].handler=(uint64_t)(uintptr_t)object;cmd.ops[0].arg0=full;cmd.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    NativeOp *op=&cmd.ops[1];op->kind=WAR3_NATIVE_OP_JASS_CLONE_SELECTED_UNIT;op->rawcode=0x68666f6f;
    op->handler=(uint64_t)(uintptr_t)(hero&4?clone_owning:clone_player);op->arg0=(uint64_t)(uintptr_t)clone_create;op->arg1=0xc080000041400000ULL;
    for(unsigned n=2;n<15;++n) cmd.ops[n].kind=WAR3_NATIVE_OP_JASS_MULTI_ARG;
#define D(n,a,b,c) cmd.ops[1+n].handler=(uint64_t)(uintptr_t)a;cmd.ops[1+n].arg0=(uint64_t)(uintptr_t)b;cmd.ops[1+n].arg1=(uint64_t)(uintptr_t)c
    D(1,clone_facing,clone_get_level,clone_set_level);cmd.ops[2].rawcode=(hero&1?WAR3_CLONE_FLAG_HERO:0)|(clone_features?WAR3_CLONE_FLAG_INVENTORY:0)|(hero&4?WAR3_CLONE_FLAG_PRESERVE_OWNER:0);
    D(2,clone_get_xp,clone_set_xp,clone_str);D(3,clone_set_str,clone_agi,clone_set_agi);
    D(4,clone_int,clone_set_int,clone_get_points);D(5,clone_modify_points,clone_max_hp,clone_set_hp);
    D(6,clone_get_life,clone_set_life,clone_max_mp);D(7,clone_set_mp,clone_get_state,clone_set_state);
    D(8,clone_slot,clone_item_type,clone_item_add);D(9,clone_charges,clone_charges_set,clone_item_get);
    D(10,clone_item_set,clone_item_get,clone_item_real_set);
    D(11,clone_item_get,clone_item_set,clone_ability);D(12,clone_ability_id,clone_ability_level,clone_add_ability);
    D(13,clone_set_ability,clone_type,clone_remove);
#undef D
    if(failure==3) cmd.ops[0].arg0+=1;
    if(failure==4) op->arg1=0x7fc000007fc00000ULL;
    command_path(path,MAX_PATH);HANDLE file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_NEW,0,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();BOOL ok=WriteFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);
    if(!ok || bytes!=sizeof(cmd)) return ERROR_WRITE_FAULT;
    run_command();
    if(failure==23 || failure==24) VirtualFree(clone_item_objects[failure==24?6:0],0,MEM_RELEASE);
    if(failure==47 || failure==48) VirtualFree(clone_ab_objects[failure==48][0],0,MEM_RELEASE);
    out[0]=bad_arguments;out[1]=clone_calls;out[2]=clone_created;out[3]=clone_removed;out[4]=clone_present;
    out[5]=clone_level;out[6]=clone_xp;out[7]=clone_points;out[8]=0;out[11]=0;
    for(unsigned n=0;n<6;++n) {out[8]+=clone_item_charges[n];if(clone_item_present[n+6]) out[11]|=1u<<n;}
    out[9]=clone_ability_rank;out[10]=clone_fault_applied;out[12]=clone_ab_adds;out[13]=(unsigned)clone_allocations;return 0;
}
'''

@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler:pytest.skip('clang required')
    root=tmp_path_factory.mktemp('clone-guard');source=root/'test.c';libpath=root/'test.dll'
    source.write_text(HARNESS.replace('HELPER_SOURCE',(Path(__file__).parent/'tools/war3_native_helper.c').as_posix())+CLONE,encoding='utf8')
    r=subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(libpath),'-luser32','-lkernel32'],capture_output=True,text=True,timeout=60)
    assert r.returncode==0,r.stderr
    lib=ctypes.CDLL(str(libpath));lib.clone_test.argtypes=[ctypes.c_wchar_p,*([ctypes.c_uint]*3),ctypes.POINTER(ctypes.c_uint)];lib.clone_test.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)

def dispatch(native,path,hero=0,at=0,failure=0):
    path.mkdir(exist_ok=True);out=(ctypes.c_uint*14)();enabled=faulthandler.is_enabled()
    if enabled:faulthandler.disable()
    try:assert native.clone_test(str(path)+'\\',hero,at,failure,out)==0
    finally:
        if enabled:faulthandler.enable()
    assert out[0]==0
    assert out[13]==0
    return out,(path/f'war3_reforged_native_{os.getpid()}.bin').read_bytes()

def parse(payload):return module.War3Trainer.__new__(module.War3Trainer)._parse_native_helper_results(payload,15)

@pytest.mark.parametrize('hero',range(8))
def test_clone_completes_one_bound_command_with_hero_and_vital_values(native,tmp_path,hero):
    out,payload=dispatch(native,tmp_path,hero)
    assert parse(payload)[1].result==8 and list(out[2:5])==[1,0,1]
    if hero&1:assert list(out[5:8])==[5,500,9]
    if hero&2:assert list(out[8:10])==[4,3]

@pytest.mark.parametrize('hero',range(8))
@pytest.mark.parametrize('failure',[1,2])
def test_every_callback_stops_before_followup_on_recycled_unit(native,tmp_path,hero,failure):
    baseline,payload=dispatch(native,tmp_path/'base',hero)
    parse(payload)
    for at in range(1,baseline[1]+1):
        out,payload=dispatch(native,tmp_path/str(at),hero,at,failure)
        if not out[10]:
            parse(payload)
            continue
        with pytest.raises(RuntimeError):parse(payload)
        assert out[1]==at
        if failure==1:assert out[3]==out[2] # valid created target removed even if source lost
        else:assert out[3]==0 and out[4]==1 # never remove the replacement target

@pytest.mark.parametrize('failure',[3,4])
def test_invalid_source_or_coordinates_do_not_invoke_engine(native,tmp_path,failure):
    out,payload=dispatch(native,tmp_path,failure=failure)
    with pytest.raises(RuntimeError):parse(payload)
    assert list(out[1:5])==[0,0,0,0]


def test_wrong_source_type_does_not_create(native,tmp_path):
    out,payload=dispatch(native,tmp_path,failure=5)
    with pytest.raises(RuntimeError):parse(payload)
    assert list(out[1:5])==[1,0,0,0]


@pytest.mark.parametrize('failure',[6,7])
def test_create_returning_source_or_unverifiable_target_never_deletes_it(native,tmp_path,failure):
    out,payload=dispatch(native,tmp_path,failure=failure)
    with pytest.raises(RuntimeError):parse(payload)
    assert out[1]>=4 and out[3]==0


def test_ability_readback_failure_is_not_swallowed_and_target_is_cleaned_up(native,tmp_path):
    out,payload=dispatch(native,tmp_path,hero=3,failure=8)
    with pytest.raises(RuntimeError):parse(payload)
    assert list(out[2:5])==[1,1,0]
