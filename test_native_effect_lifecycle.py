"""Persistent effect lifecycle tests use the actual C command dispatcher."""
import ctypes
import faulthandler
import shutil
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import war3_reforged_trainer as module
from test_native_identity_guard import HARNESS
from test_native_ability_actions import ACTIONS
from test_native_direct_transaction import DIRECT
from test_native_snapshot_binding import make_candidate, make_snapshot


LIFECYCLE = r'''
static uint32_t life_area,life_sets,life_stops,life_hidden,life_fault,life_order;
static uint64_t life_get(uint64_t ability,uint32_t field,int32_t level) {
    if(ability!=100 || field!=0x61617265u || level!=(int32_t)action_levels[0]-1) ++bad_arguments;
    return life_area;
}
static uint64_t life_set(uint64_t ability,uint32_t field,int32_t level,float *value) {
    life_get(ability,field,level);++life_sets;
    uint32_t bits;memcpy(&bits,value,4);
    if(life_fault==2 && life_sets==1) return 0;
    life_area=bits;
    if(life_fault==3 && life_sets==1) RaiseException(0xe0000001,0,0,NULL);
    if(life_fault==4 && life_sets==1) ++*(uint64_t *)(object+0x18);
    if(life_fault==5 && life_sets==1) {++*(uint64_t *)(action_data[0]+0x18);++*(uint64_t *)(action_wrappers[0]+0x20);}
    return 1;
}
static void life_hide(uint64_t unit,int32_t id,uint32_t flag) {
    action_check(unit);if((uint32_t)id!=action_ids[0] || flag!=1) ++bad_arguments;++life_hidden;
}
static uint32_t life_stop(uint64_t unit,int32_t order) {
    action_check(unit);if(order!=851972) ++bad_arguments;++life_stops;
    if(life_fault==6) return 0;
    if(life_fault==7) ++*(uint64_t *)(object+0x18);
    if(life_fault==8) life_area=0x44000000u;
    return 1;
}
static int32_t life_current(uint64_t unit) {action_check(unit);return life_order;}
static uint32_t life_x(uint64_t unit) {action_check(unit);return 0x41400000u;}
static uint32_t life_y(uint64_t unit) {action_check(unit);return 0xc0800000u;}
static void life_effect(uint64_t ability) {
    direct_effect(ability);
    if(life_fault==9) RaiseException(0xe0000001,0,0,NULL);
    if(life_fault==10) ++*(uint64_t *)(object+0x18);
    if(life_fault==11) ++action_levels[0];
}
static void life_point(uint64_t ability,float *x,float *y) {
    if(*x!=12 || *y!=-4) ++bad_arguments;life_effect(ability);
}
static DWORD life_submit(NativeCommand *cmd) {
    wchar_t path[MAX_PATH];DWORD bytes;command_path(path,MAX_PATH);
    HANDLE file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_ALWAYS,0,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();
    BOOL ok=WriteFile(file,cmd,sizeof(*cmd),&bytes,NULL);CloseHandle(file);if(!ok) return ERROR_WRITE_FAULT;
    run_command();file=CreateFileW(path,GENERIC_READ,0,NULL,OPEN_EXISTING,0,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();
    ok=ReadFile(file,cmd,sizeof(*cmd),&bytes,NULL);CloseHandle(file);return ok?0:ERROR_READ_FAULT;
}
__declspec(dllexport) DWORD lifecycle_test(const wchar_t *directory,unsigned initial,unsigned mode,unsigned flags,unsigned passes,unsigned failure,uint64_t *out) {
    unsigned ignored[5];DWORD error=direct_test(directory,2,1,0,ignored);if(error) return error;
    ZeroMemory(g_ability_effects,sizeof(g_ability_effects));
    action_present[0]=initial;action_adds=action_removes=direct_calls=bad_arguments=action_lookups=0;
    action_fault=direct_fault=0;life_area=0x43800000u;life_sets=life_stops=life_hidden=0;life_fault=failure;life_order=852000;
    direct_vtable[0x998/8]=direct_vtable[0xa78/8]=(uint64_t)(uintptr_t)life_effect;
    direct_vtable[0xa58/8]=(uint64_t)(uintptr_t)life_point;
    for(unsigned n=0;n<sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]);++n) {
        const char *name=g_persistent_natives[n].name;
        if(!strcmp(name,"BlzGetAbilityRealLevelField")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)life_get;
        if(!strcmp(name,"BlzSetAbilityRealLevelField")) g_persistent_natives[n].handler=failure==1?0:(uint64_t)(uintptr_t)life_set;
        if(!strcmp(name,"BlzUnitHideAbility")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)life_hide;
        if(!strcmp(name,"IssueImmediateOrderById")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)life_stop;
        if(!strcmp(name,"GetUnitCurrentOrder")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)life_current;
        if(!strcmp(name,"GetUnitX")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)life_x;
        if(!strcmp(name,"GetUnitY")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)life_y;
    }
    NativeCommand cmd={0},start;
    cmd.magic=WAR3_NATIVE_MAGIC;cmd.version=WAR3_NATIVE_VERSION;cmd.status=WAR3_NATIVE_STATUS_PENDING;cmd.op_count=3;cmd.unit_handle=7;
    cmd.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;cmd.ops[0].handler=(uint64_t)(uintptr_t)object;
    cmd.ops[0].arg0=full;cmd.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    cmd.ops[1].kind=WAR3_NATIVE_OP_START_ABILITY_EFFECT;cmd.ops[1].rawcode=action_ids[0];cmd.ops[1].handler=mode;cmd.ops[1].arg0=passes;
    if(mode==3 && !(flags&4)) cmd.ops[1].arg1=0xc080000041400000ULL;
    cmd.ops[2].kind=WAR3_NATIVE_OP_ABILITY_EFFECT_OPTIONS;cmd.ops[2].rawcode=flags;
    cmd.ops[2].arg0=(flags&1)?0x47c35000u:0;
    if(failure==12) cmd.ops[2].arg0=0x7fc00000u;
    start=cmd;error=life_submit(&cmd);if(error) return error;
    out[0]=cmd.status;out[1]=cmd.last_error;out[2]=cmd.ops[1].result;out[3]=cmd.ops[1].arg0;out[4]=cmd.ops[1].reserved;
    out[5]=action_present[0];out[6]=life_area;
    uint64_t token=cmd.ops[1].result;
    if(cmd.status==WAR3_NATIVE_STATUS_OK && token) {
        if(failure==13) ++*(uint64_t *)(object+0x18);
        if(failure==14) {++*(uint64_t *)(action_data[0]+0x18);++*(uint64_t *)(action_wrappers[0]+0x20);}
        if(failure==15) ++life_order;
        if(failure==16) life_area=0x44000000u;
        if(failure==17) {
            NativeCommand duplicate=start;error=life_submit(&duplicate);if(error) return error;out[15]=duplicate.last_error;
        }
        cmd=start;cmd.op_count=2;cmd.ops[1]=(NativeOp){0};cmd.ops[1].kind=WAR3_NATIVE_OP_FINISH_ABILITY_EFFECT;
        cmd.ops[1].handler=failure==18?token+1:token;
        error=life_submit(&cmd);if(error) return error;
        out[7]=cmd.status;out[8]=cmd.last_error;
        if(failure==19) {cmd.status=WAR3_NATIVE_STATUS_PENDING;error=life_submit(&cmd);if(error) return error;out[15]=cmd.last_error;}
    }
    out[9]=action_adds;out[10]=action_removes;out[11]=life_sets;out[12]=life_stops;out[13]=direct_calls;out[14]=bad_arguments;
    out[16]=action_present[0];out[17]=life_area;out[18]=life_hidden;
    return 0;
}
'''


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler: pytest.skip('clang required')
    root=tmp_path_factory.mktemp('effect_lifecycle');source=root/'test.c';dll=root/'test.dll'
    source.write_text(HARNESS.replace('HELPER_SOURCE',(Path(__file__).parent/'tools/war3_native_helper.c').as_posix())+ACTIONS+DIRECT+LIFECYCLE,encoding='utf8')
    build=subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(dll),'-luser32','-lkernel32'],capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    lib=ctypes.CDLL(str(dll));lib.lifecycle_test.argtypes=[ctypes.c_wchar_p]+[ctypes.c_uint]*5+[ctypes.POINTER(ctypes.c_uint64)]
    lib.lifecycle_test.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)


def run(native,tmp_path,initial=0,mode=2,flags=3,passes=3,fault=0):
    out=(ctypes.c_uint64*19)();enabled=faulthandler.is_enabled()
    if enabled: faulthandler.disable()
    try: assert native.lifecycle_test(str(tmp_path)+'\\',initial,mode,flags,passes,fault,out)==0
    finally:
        if enabled: faulthandler.enable()
    assert out[14]==0,'stale handle or wrong callback arguments'
    return list(out)


@pytest.mark.parametrize('initial',[0,1])
@pytest.mark.parametrize('mode,flags',[(2,0),(2,1),(2,2),(2,3),(3,3),(3,7),(4,1)])
def test_effect_start_hold_finish_restores_exact_area(native,tmp_path,initial,mode,flags):
    out=run(native,tmp_path,initial,mode,flags)
    assert out[0]==2 and out[1]==0 and out[3]==3 and out[4]==0
    assert bool(out[2])==bool(flags&2)
    if flags&2: assert out[5]==1 and out[7]==2 and out[8]==0
    assert out[9:14]==[1-initial,1-initial,2 if flags&1 else 0,1 if flags&2 else 0,3]
    assert out[16:]==[initial,0x43800000,1 if flags&2 and not initial else 0]


@pytest.mark.parametrize('fault',[1,2,3,4,5,9,10,11,12])
def test_start_failures_do_not_continue_effect_passes(native,tmp_path,fault):
    out=run(native,tmp_path,fault=fault)
    assert out[0]==3 and out[1]!=0
    assert out[13]<=1
    if fault in (1,12): assert out[9:14]==[0,0,0,0,0]
    if fault in (2,3): assert out[16]==0 and out[17]==0x43800000
    if fault in (4,5,9,10,11): assert out[4]!=0 and out[2]!=0


@pytest.mark.parametrize('fault',[6,7,8,13,14,15,16,18])
def test_finish_refuses_changed_objects_orders_or_fields(native,tmp_path,fault):
    out=run(native,tmp_path,fault=fault)
    assert out[0]==2 and out[7]==3 and out[8]!=0
    assert out[10]==0 and out[11]==1
    if fault in (13,14,15,18): assert out[12]==0


@pytest.mark.parametrize('fault',[17,19])
def test_duplicate_start_and_replayed_finish_do_not_repeat_effect(native,tmp_path,fault):
    out=run(native,tmp_path,fault=fault)
    assert out[0]==2 and out[7]==2 and out[15]!=0
    assert out[13]==3 and out[10]==1 and out[12]==1


@pytest.fixture
def trainer():
    t=module.War3Trainer.__new__(module.War3Trainer);c=make_candidate(make_snapshot())
    t._direct_selected_context=Mock(return_value=(c,c.native_snapshot.handle))
    t._process_memory=Mock(side_effect=AssertionError('external memory'))
    t.get_selected_unit_position=Mock(side_effect=AssertionError('separate selection read'))
    return t,c


def test_python_waits_only_requested_duration_then_finishes_original_token(trainer):
    t,c=trainer
    t._run_native_helper_ops=Mock(side_effect=[
        [module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(158,42,arg0=3),module.NativeHelperOpResult(159,0)],
        [module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(160,1)],
    ])
    with patch.object(module.time,'sleep') as wait:
        assert t._run_selected_ability_effect_locked('A001','point',passes=3,area=100000,hold_seconds=12)==(3,3)
    wait.assert_called_once_with(12)
    start,finish=t._run_native_helper_ops.call_args_list
    assert start.args==(c.native_snapshot.handle,((136,0,c.unit_address,c.handle,c.owner_address),
                                                (158,0x41303031,3,3,0),(159,7,0,0x47c35000,0)))
    assert finish.args==(start.args[0],(start.args[1][0],(160,0,42,0,0)))
    t._direct_selected_context.assert_called_once()


def test_interrupted_wait_still_finishes_bound_effect(trainer):
    t,c=trainer
    t._run_native_helper_ops=Mock(side_effect=[
        [module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(158,42,arg0=1),module.NativeHelperOpResult(159,0)],
        [module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(160,1)],
    ])
    with patch.object(module.time,'sleep',side_effect=KeyboardInterrupt),pytest.raises(KeyboardInterrupt):
        t._run_selected_ability_effect_locked('A001','immediate',hold_seconds=12)
    assert t._run_native_helper_ops.call_count==2
