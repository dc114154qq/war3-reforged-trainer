"""Bound world effects exercise the production C dispatcher with fake groups."""
import ctypes
import faulthandler
from pathlib import Path
import shutil
import subprocess
from unittest.mock import Mock

import pytest
import war3_reforged_trainer as module
from test_native_identity_guard import HARNESS
from test_native_ability_actions import ACTIONS
from test_native_snapshot_binding import make_snapshot,make_candidate

WORLD=r'''
static uint8_t world_objects[4][0x20],world_owners[4][0x98];
static uint64_t world_vtable[0xa80/8],world_queue[6];
static unsigned world_fault,world_present[4],world_index,world_count,world_calls,world_destroyed,world_enums;
static uint64_t world_full(unsigned n) {return 0x445500000001ULL+n;}
static uint64_t world_resolve(uint64_t handle) {
    if(handle>=20 && handle<24) return world_present[handle-20]?(uint64_t)(uintptr_t)world_objects[handle-20]:0;
    return fake_unit(handle);
}
static uint64_t world_agent(uint32_t slot,uint32_t serial) {
    uint64_t full=((uint64_t)serial<<32)|slot;
    for(unsigned n=0;n<4;++n) if(full==*(uint64_t *)(world_objects[n]+0x18)) return (uint64_t)(uintptr_t)world_owners[n];
    return action_agent(slot,serial);
}
static uint64_t world_owner(uint64_t unit) {
    if(unit==7) {action_check(unit);return world_fault==8 && world_calls?9:1;}
    if(unit<20 || unit>=24) {++bad_arguments;return 0;}
    return unit==21 || (world_fault==13 && world_calls)?1:2;
}
static uint64_t world_create(void) {return world_fault==1?0:77;}
static void world_destroy(uint64_t group) {
    if(group!=77 || world_destroyed) ++bad_arguments;++world_destroyed;
    if(world_fault==2) RaiseException(0xe0000001,0,0,NULL);
}
static uint64_t world_player(int32_t id) {return 100+id;}
static void world_enum(uint64_t group,uint64_t player,uint64_t filter) {
    if(group!=77 || filter || world_index!=world_count) ++bad_arguments;++world_enums;
    world_index=0;world_count=0;
    if(player==100 && world_fault!=3) {world_queue[0]=20;world_queue[1]=21;world_queue[2]=22;world_queue[3]=23;world_queue[4]=20;world_count=5;}
    if(player==101 && world_fault!=3) {world_queue[0]=20;world_count=1;}
    if(world_fault==4) ++*(uint64_t *)(object+0x18);
}
static uint64_t world_first(uint64_t group) {if(group!=77) ++bad_arguments;return world_index<world_count?world_queue[world_index]:0;}
static void world_remove(uint64_t group,uint64_t unit) {
    if(group!=77 || world_index>=world_count || world_queue[world_index]!=unit) ++bad_arguments;++world_index;
}
static uint32_t world_type(uint64_t unit) {return unit>=20 && unit<24 && world_present[unit-20]?0x68666f6f:0;}
static uint32_t world_life(uint64_t unit) {
    if(world_fault==9 && unit==20) {++*(uint64_t *)(world_objects[0]+0x18);++*(uint64_t *)(world_owners[0]+0x20);}
    return unit==22?0:0x42c80000u;
}
static uint32_t world_enemy(uint64_t source,uint64_t target) {if(source!=1) ++bad_arguments;return target==2;}
static uint32_t world_x(uint64_t unit) {float v=(float)unit;uint32_t bits;memcpy(&bits,&v,4);return world_fault==10 && unit==20?0x7fc00000:bits;}
static uint32_t world_y(uint64_t unit) {return 0xc0800000u;}
static void world_callback(uint64_t ability,unsigned n) {
    if(ability!=(uint64_t)(uintptr_t)action_data[0] || !action_present[0] || !world_present[n] ||
       world_destroyed!=1 || (n!=0 && n!=3)) ++bad_arguments;
    ++world_calls;
    if(world_fault==5) ++*(uint64_t *)(object+0x18);
    if(world_fault==6) {++*(uint64_t *)(action_data[0]+0x18);++*(uint64_t *)(action_wrappers[0]+0x20);}
    if(world_fault==7) RaiseException(0xe0000001,0,0,NULL);
    if(world_fault==11) {++*(uint64_t *)(world_objects[3]+0x18);++*(uint64_t *)(world_owners[3]+0x20);}
    if(world_fault==12) world_present[n]=0;
}
static void world_target(uint64_t ability,uint64_t target) {
    for(unsigned n=0;n<4;++n) if(target==(uint64_t)(uintptr_t)world_objects[n]) {world_callback(ability,n);return;}
    ++bad_arguments;
}
static void world_point(uint64_t ability,float *x,float *y) {
    if(*y!=-4 || (*x!=20 && *x!=23)) {++bad_arguments;return;}
    world_callback(ability,(unsigned)*x-20);
}
__declspec(dllexport) DWORD world_test(const wchar_t *directory,unsigned mode,unsigned initial,unsigned limit,unsigned failure,uint64_t *out) {
    unsigned ignored[7];DWORD error=action_test(directory,1,0,1,0,0,ignored);if(error) return error;
    world_fault=failure;world_calls=world_destroyed=world_enums=world_index=world_count=0;
    action_present[0]=initial;action_adds=action_removes=action_lookups=bad_arguments=0;
    action_fault=failure==14?5:0;
    for(unsigned n=0;n<4;++n) {
        ZeroMemory(world_objects[n],0x20);ZeroMemory(world_owners[n],0x98);world_present[n]=1;
        *(uint64_t *)(world_objects[n]+0x18)=*(uint64_t *)(world_owners[n]+0x20)=world_full(n);
        *(uint64_t *)(world_owners[n]+0x18)=0x2b7733752b61676cULL;
        *(uint64_t *)(world_owners[n]+0x90)=(uint64_t)(uintptr_t)world_objects[n];
    }
    g_persistent_unit_resolver=(uint64_t)(uintptr_t)world_resolve;g_persistent_agent_resolver=(uint64_t)(uintptr_t)world_agent;
    ZeroMemory(world_vtable,sizeof(world_vtable));world_vtable[0xa70/8]=(uint64_t)(uintptr_t)world_target;
    world_vtable[0xa58/8]=(uint64_t)(uintptr_t)world_point;*(uint64_t *)action_data[0]=(uint64_t)(uintptr_t)world_vtable;
    for(unsigned n=0;n<sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]);++n) {
        const char *name=g_persistent_natives[n].name;
#define BIND(name_,fn_) if(!strcmp(name,name_)) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)fn_;
        BIND("GetOwningPlayer",world_owner) BIND("CreateGroup",world_create) BIND("DestroyGroup",world_destroy)
        BIND("GroupEnumUnitsOfPlayer",world_enum) BIND("FirstOfGroup",world_first) BIND("GroupRemoveUnit",world_remove)
        BIND("Player",world_player) BIND("GetUnitTypeId",world_type) BIND("GetWidgetLife",world_life)
        BIND("IsPlayerEnemy",world_enemy) BIND("GetUnitX",world_x) BIND("GetUnitY",world_y)
#undef BIND
        if(failure==15 && !strcmp(name,"IsPlayerEnemy")) g_persistent_natives[n].handler=0;
    }
    NativeCommand cmd={0};wchar_t path[MAX_PATH];DWORD bytes;
    cmd.magic=WAR3_NATIVE_MAGIC;cmd.version=WAR3_NATIVE_VERSION;cmd.status=WAR3_NATIVE_STATUS_PENDING;cmd.op_count=2;cmd.unit_handle=7;
    cmd.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;cmd.ops[0].handler=(uint64_t)(uintptr_t)object;
    cmd.ops[0].arg0=full;cmd.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    cmd.ops[1].kind=WAR3_NATIVE_OP_BOUND_WORLD_EFFECT;cmd.ops[1].handler=mode;cmd.ops[1].arg0=limit;cmd.ops[1].rawcode=failure==16?0:action_ids[0];
    command_path(path,MAX_PATH);HANDLE file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_ALWAYS,0,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();BOOL ok=WriteFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);if(!ok) return ERROR_WRITE_FAULT;
    run_command();file=CreateFileW(path,GENERIC_READ,0,NULL,OPEN_EXISTING,0,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();ok=ReadFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);if(!ok) return ERROR_READ_FAULT;
    out[0]=cmd.status;out[1]=cmd.last_error;out[2]=cmd.ops[1].result>>32;out[3]=(uint32_t)cmd.ops[1].result;out[4]=cmd.ops[1].reserved;
    out[5]=world_calls;out[6]=world_destroyed;out[7]=action_adds;out[8]=action_removes;out[9]=bad_arguments;out[10]=world_enums;
    return 0;
}
'''

@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler:pytest.skip('clang required')
    root=tmp_path_factory.mktemp('world');source=root/'test.c';dll=root/'test.dll'
    source.write_text(HARNESS.replace('HELPER_SOURCE',(Path(__file__).parent/'analysis/fixtures/legacy-native-helper.c').as_posix())+ACTIONS+WORLD,encoding='utf8')
    build=subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(dll),'-luser32','-lkernel32'],capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    lib=ctypes.CDLL(str(dll));lib.world_test.argtypes=[ctypes.c_wchar_p]+[ctypes.c_uint]*4+[ctypes.POINTER(ctypes.c_uint64)];lib.world_test.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)

def run(native,tmp_path,mode=1,initial=0,limit=0,fault=0):
    out=(ctypes.c_uint64*11)();enabled=faulthandler.is_enabled()
    if enabled:faulthandler.disable()
    try:assert native.world_test(str(tmp_path)+'\\',mode,initial,limit,fault,out)==0
    finally:
        if enabled:faulthandler.enable()
    assert out[9]==0,'wrong native arguments, stale object, or group cleanup repeated'
    return list(out)

@pytest.mark.parametrize('mode',[1,3])
@pytest.mark.parametrize('initial',[0,1])
@pytest.mark.parametrize('limit',[0,1])
def test_world_effect_uses_pinned_unique_alive_enemies(native,tmp_path,mode,initial,limit):
    out=run(native,tmp_path,mode,initial,limit)
    count=limit or 2
    assert out[:9]==[2,0,count,count,0,count,1,1-initial,1-initial]
    assert out[10]==24

@pytest.mark.parametrize('fault',[1,2,4,5,6,7,8,14,15,16])
def test_world_failure_stops_callbacks_and_cleans_resources(native,tmp_path,fault):
    out=run(native,tmp_path,fault=fault)
    assert out[0]==3 and out[1]!=0
    assert out[5]==(1 if fault in (5,6,7,8) else 0)
    assert out[6]==(0 if fault in (1,15,16) else 1)
    if fault in (5,6):assert out[4]!=0 and out[8]==0
    if fault in (7,8):assert out[4]==0 and out[8]==1

@pytest.mark.parametrize('fault,count',[(3,0),(9,1),(11,1),(12,2),(13,1)])
def test_empty_dead_recycled_or_friendly_targets_do_not_receive_stale_effects(native,tmp_path,fault,count):
    out=run(native,tmp_path,fault=fault)
    assert out[0]==2 and out[3]==out[5]==count
    if fault==3:assert out[7]==out[8]==0

def test_invalid_point_skips_target_without_losing_attempt_count(native,tmp_path):
    out=run(native,tmp_path,mode=3,fault=10)
    assert out[0]==2 and out[2:4]==[2,1]

@pytest.mark.parametrize('mode,limit',[(0,0),(2,0),(1,65536)])
def test_invalid_native_parameters_fail_before_group_creation(native,tmp_path,mode,limit):
    out=run(native,tmp_path,mode=mode,limit=limit)
    assert out[0]==3 and out[5:9]==[0,0,0,0]

@pytest.mark.parametrize('mode,value',[('target',1),('point',3)])
def test_python_world_entry_only_sends_identity_and_effect_parameters(mode,value):
    t=module.War3Trainer.__new__(module.War3Trainer);c=make_candidate(make_snapshot())
    t._direct_selected_context=Mock(return_value=(c,c.native_snapshot.handle));t._process_memory=Mock(side_effect=AssertionError('external discovery'))
    t._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(162,(2<<32)|2)])
    assert t._run_direct_ability_over_enemy_units_locked('A001',mode,success_limit=3)==(2,2)
    assert t._run_native_helper_ops.call_args.args==(c.native_snapshot.handle,(
        (136,0,c.unit_address,c.handle,c.owner_address),(162,0x41303031,value,3,0)))
