"""Real dispatcher: hero level/skill transactions and XP-state restoration."""
import ctypes
import faulthandler
import os
from pathlib import Path
import shutil
import subprocess
import threading
from unittest.mock import Mock

import pytest
import war3_reforged_trainer as module
from test_native_identity_guard import HARNESS
from test_native_unit_field_dispatch import FIELDS_HARNESS
from test_native_selected_context import trainer


PROGRESS = r'''
static unsigned p_fault,p_sets,p_strips,p_adds,p_off,p_on;
static int32_t p_level,p_xp;
static void p_check(uint64_t unit) {if(unit!=7) ++bad_arguments;}
static void p_recycle(void) {*(uint64_t *)(object+0x18)+=1ULL<<32;}
static int32_t p_get_level(uint64_t u) {
    p_check(u);if(p_fault==19) p_recycle();return p_fault==1?0:p_level;
}
static int32_t p_get_xp(uint64_t u) {
    p_check(u);if(p_fault==5) p_recycle();
    if(p_fault==23 && p_off) RaiseException(0xe0000002,0,0,NULL);
    return p_xp;
}
static void p_suspend(uint64_t u,uint32_t value) {
    p_check(u);if(value>1) ++bad_arguments;
    if(value) {
        ++p_on;if(p_fault!=10) p_xp=1;
        if(p_fault==11) p_recycle();
        if(p_fault==12) ++p_level;
        if(p_fault==21) RaiseException(0xe0000001,0,0,NULL);
    } else {
        ++p_off;if(p_fault!=20) p_xp=0;
        if(p_fault==6) p_recycle();
        if(p_fault==7) RaiseException(0xe0000001,0,0,NULL);
    }
}
static void p_set_level(uint64_t u,int32_t value,uint32_t visual) {
    p_check(u);if(visual!=1 || p_xp) ++bad_arguments;
    ++p_sets;p_level=value;
    if(p_fault==8) p_recycle();
    if(p_fault==9) RaiseException(0xe0000001,0,0,NULL);
}
static int32_t p_strip(uint64_t u,int32_t delta) {
    p_check(u);if(delta<=0) ++bad_arguments;++p_strips;
    if(p_fault==13) return 0;
    if(p_fault!=14) p_level-=delta;
    return 1;
}
static int32_t p_add(uint64_t u,int32_t delta) {
    p_check(u);if(delta<=0) ++bad_arguments;++p_adds;
    if(p_fault==15) return 0;
    if(p_fault!=16) *(int32_t *)(field_data[1]+0x104)+=delta;
    if(p_fault==17) *(uint64_t *)(field_data[1]+0x18)+=1;
    if(p_fault==18) RaiseException(0xe0000001,0,0,NULL);
    return 1;
}
__declspec(dllexport) DWORD progress_test(const wchar_t *directory,unsigned kind,unsigned failure,
    unsigned target,int32_t initial,int32_t xp,int32_t points,int32_t *out) {
    DWORD error=field_snapshot(directory,15,0),bytes;HANDLE file;wchar_t path[MAX_PATH];NativeCommand cmd={0};
    if(error) return error;
    command_path(path,MAX_PATH);DeleteFileW(path);
    field_fault=field_unit_calls=bad_arguments=0;p_fault=failure;
    p_level=initial;p_xp=xp;p_sets=p_strips=p_adds=p_off=p_on=0;
    *(int32_t *)(field_data[1]+0x104)=points;
    for(unsigned n=0;n<sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]);++n) {
        const char *name=g_persistent_native_names[n];
        if(!strcmp(name,"GetHeroLevel")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)p_get_level;
        if(!strcmp(name,"SetHeroLevel")) g_persistent_natives[n].handler=failure==2?0:(uint64_t)(uintptr_t)p_set_level;
        if(!strcmp(name,"UnitStripHeroLevel")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)p_strip;
        if(!strcmp(name,"SuspendHeroXP")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)p_suspend;
        if(!strcmp(name,"IsSuspendedXP")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)p_get_xp;
        if(!strcmp(name,"UnitModifySkillPoints")) g_persistent_natives[n].handler=failure==2?0:(uint64_t)(uintptr_t)p_add;
    }
    cmd.magic=WAR3_NATIVE_MAGIC;cmd.version=WAR3_NATIVE_VERSION;cmd.status=WAR3_NATIVE_STATUS_PENDING;
    cmd.op_count=2;cmd.unit_handle=7;
    cmd.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;cmd.ops[0].handler=(uint64_t)(uintptr_t)object;
    cmd.ops[0].arg0=full;cmd.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    cmd.ops[1].kind=kind;cmd.ops[1].rawcode=target;
    if(failure==3) ++cmd.ops[0].arg0;
    if(failure==4) *(uint64_t *)(field_wrappers[1]+0x50)=0;
    if(failure==22) cmd.ops[1].arg1=1;
    command_path(path,MAX_PATH);file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();
    BOOL ok=WriteFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);
    if(!ok || bytes!=sizeof(cmd)) return ERROR_WRITE_FAULT;
    run_command();out[0]=p_sets;out[1]=p_strips;out[2]=p_adds;out[3]=p_off;out[4]=p_on;
    out[5]=p_level;out[6]=p_xp;out[7]=*(int32_t *)(field_data[1]+0x104);out[8]=bad_arguments;
    return 0;
}
'''


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler:pytest.skip('clang required')
    root=tmp_path_factory.mktemp('hero-progress');source=root/'test.c';library=root/'test.dll'
    source.write_text(HARNESS.replace('static uint8_t object[0x20]','static uint8_t object[0x600]')
        .replace('HELPER_SOURCE',(Path(__file__).parent/'tools/war3_native_helper.c').as_posix())+FIELDS_HARNESS+PROGRESS,encoding='utf8')
    subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(library),
                    '-luser32','-lkernel32'],check=True,capture_output=True,timeout=60)
    lib=ctypes.CDLL(str(library))
    lib.progress_test.argtypes=[ctypes.c_wchar_p,ctypes.c_uint,ctypes.c_uint,ctypes.c_uint,
                               ctypes.c_int32,ctypes.c_int32,ctypes.c_int32,ctypes.POINTER(ctypes.c_int32)]
    lib.progress_test.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)


def dispatch(native,path,kind=165,failure=0,target=10,initial=5,xp=1,points=9):
    out=(ctypes.c_int32*9)();enabled=faulthandler.is_enabled()
    if failure in (7,9,18,21,23) and enabled:faulthandler.disable()
    try:assert native.progress_test(str(path)+'\\',kind,failure,target,initial,xp,points,out)==0
    finally:
        if failure in (7,9,18,21,23) and enabled:faulthandler.enable()
    assert out[8]==0
    return out,(path/f'war3_reforged_native_{os.getpid()}.bin').read_bytes()


def parse(payload):return module.War3Trainer.__new__(module.War3Trainer)._parse_native_helper_results(payload,2)


@pytest.mark.parametrize('initial,target',[(5,10),(10,5),(5,5),(5,1),(5,100000)])
@pytest.mark.parametrize('xp',[0,1])
def test_level_raise_lower_noop_and_xp_restore(native,tmp_path,initial,target,xp):
    out,payload=dispatch(native,tmp_path,initial=initial,target=target,xp=xp)
    assert parse(payload)[1].result==target
    assert out[5]==target and out[6]==xp
    assert list(out[:3])==[int(target>initial),int(target<initial),0]
    assert list(out[3:5])==[int(target>initial and xp)]*2


@pytest.mark.parametrize('failure',[1,2,3,4,5,6,7,8,9,10,11,12,19,20,21,22,23])
def test_level_failures_restore_only_original_valid_hero(native,tmp_path,failure):
    out,payload=dispatch(native,tmp_path,failure=failure)
    with pytest.raises(RuntimeError) as raised:parse(payload)
    assert out[0]==int(failure in (8,9,10,11,12,21))
    if failure in (7,9,12,20):assert out[6]==1
    if failure in (6,8):
        assert out[4]==0 # never restore onto invalid/recycled unit
        assert 'xp_restore_error=6' in str(raised.value)
    if failure==7:assert out[4]==1 # unpause changed state then raised
    if failure==10:assert out[6]==0 and 'xp_restore_error=1003' in str(raised.value)
    if failure in (1,2,3,4,5,19,22):assert list(out[:5])==[0]*5


@pytest.mark.parametrize('failure',[13,14])
def test_strip_refusal_or_wrong_level_cannot_report_success(native,tmp_path,failure):
    out,payload=dispatch(native,tmp_path,failure=failure,target=2)
    with pytest.raises(RuntimeError):parse(payload)
    assert list(out[:5])==[0,1,0,0,0] and out[6]==1


@pytest.mark.parametrize('delta,points',[(1,0),(1000000,9),(1,2147483646)])
def test_skill_delta_is_verified_from_bound_component(native,tmp_path,delta,points):
    out,payload=dispatch(native,tmp_path,kind=166,target=delta,points=points)
    result=parse(payload)[1]
    assert result.result==delta and result.arg0==points+delta and out[7]==points+delta
    assert list(out[:5])==[0,0,1,0,0]


@pytest.mark.parametrize('failure',[1,2,3,4,15,16,17,18,19,22])
def test_skill_refusal_identity_change_and_wrong_count_fail(native,tmp_path,failure):
    out,payload=dispatch(native,tmp_path,kind=166,failure=failure,target=3)
    with pytest.raises(RuntimeError):parse(payload)
    assert out[2]==int(failure in (15,16,17,18))
    assert out[0]==out[1]==out[3]==out[4]==0


@pytest.mark.parametrize('kind,target,points',[(165,0,9),(165,100001,9),(166,0,9),(166,1000001,9),(166,1,2147483647)])
def test_invalid_target_or_skill_overflow_has_no_mutation(native,tmp_path,kind,target,points):
    out,payload=dispatch(native,tmp_path,kind=kind,target=target,points=points)
    with pytest.raises(RuntimeError):parse(payload)
    assert list(out[:5])==[0]*5 and out[7]==points


@pytest.mark.parametrize('method,kind,value',[('set_selected_hero_level',165,10),('add_selected_hero_skill_points',166,3)])
def test_public_actions_use_bound_native_context_and_one_command(trainer,method,kind,value):
    trainer._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(kind,value)])
    assert getattr(trainer,method)(value)==value
    snapshot=trainer.persistent_native_selected_snapshots.return_value[0]
    ops=((136,0,snapshot.unit_address,snapshot.full_handle,snapshot.owner_address),(kind,value,0,0,0))
    trainer._run_native_helper_ops.assert_called_once_with(snapshot.handle,ops)
    trainer._process_memory.assert_not_called()
    trainer._native_helper_command_path=Mock(return_value='offline-command');trainer._write_native_helper_command=Mock()
    trainer._native_helper_batch_hook=1;trainer._native_helper_batch_thread_id=threading.get_ident()
    trainer._wait_native_helper_result=Mock(return_value=[]);trainer._run_native_helper_ops_locked(snapshot.handle,ops)
    payload=trainer._write_native_helper_command.call_args.args[1]
    base=trainer.NATIVE_HELPER_HEADER_STRUCT.size;size=trainer.NATIVE_HELPER_OP_STRUCT.size
    assert [trainer.NATIVE_HELPER_OP_STRUCT.unpack_from(payload,base+i*size)[:5] for i in range(2)]==list(ops)


def test_batch_override_does_not_reread_current_selection(trainer):
    candidate,handle=trainer._direct_selected_context()
    trainer.persistent_native_selected_snapshots.side_effect=AssertionError('Do not requery selection')
    trainer._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(165,10)])
    with trainer._bound_elephant_selection(candidate,handle):assert trainer.set_selected_hero_level(10)==10
    assert trainer._run_native_helper_ops.call_args.args[1][0][2:]==(candidate.unit_address,candidate.handle,candidate.owner_address)


@pytest.mark.parametrize('method,value',[('set_selected_hero_level',0),('set_selected_hero_level',100001),
                                       ('add_selected_hero_skill_points',0),('add_selected_hero_skill_points',1000001)])
def test_invalid_input_precedes_selection(trainer,method,value):
    with pytest.raises(ValueError):getattr(trainer,method)(value)
    trainer.persistent_native_selected_snapshots.assert_not_called()


@pytest.mark.parametrize('kind,returned',[ (165,[]),(166,[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(166,2)]),
    (165,[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(72,3)])])
def test_incomplete_or_wrong_ack_fails(trainer,kind,returned):
    trainer._run_native_helper_ops=Mock(return_value=returned)
    with pytest.raises(RuntimeError):trainer._run_bound_hero_progress(kind,3)
