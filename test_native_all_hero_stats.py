"""All-attribute action uses a single guarded production DLL transaction."""
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


ALL_STATS_HARNESS = r'''
static int32_t all_storage[3],all_offset[3]={3,-7,9};
static unsigned all_fault,all_sets[3],all_gets;
static int32_t all_level(uint64_t unit) {if(unit!=7) ++bad_arguments;return all_fault==1?0:5;}
static int32_t all_get(unsigned stat,uint64_t unit,uint32_t bonus) {
    if(unit!=7 || bonus) ++bad_arguments;
    ++all_gets;
    if(all_fault==6 && stat==2) *(uint64_t *)(object+0x18)+=1;
    if(all_fault==16 && all_gets==9) *(uint64_t *)(field_data[1]+0x18)+=1;
    return all_storage[stat]+all_offset[stat];
}
static void all_set(unsigned stat,uint64_t unit,int32_t value,uint32_t permanent) {
    if(unit!=7 || permanent!=1 || *(uint64_t *)(object+0x18)!=full) ++bad_arguments;
    ++all_sets[stat];all_storage[stat]=value-all_offset[stat];
    if(all_fault==7 && stat==0) *(uint64_t *)(object+0x18)+=1;
    if(all_fault==8 && stat==1) *(uint64_t *)(field_data[1]+0x18)+=1;
    if(all_fault==9 && stat==2) *(uint64_t *)(object+0x5a8)=0;
    if(all_fault==10 && stat==0) --all_storage[0];
    if(all_fault==11 && stat==2) --all_storage[0];
    if(all_fault==12 && stat==2) RaiseException(0xe0000001,0,0,NULL);
}
static int32_t all_get_str(uint64_t u,uint32_t b) {return all_get(0,u,b);}
static int32_t all_get_agi(uint64_t u,uint32_t b) {return all_get(1,u,b);}
static int32_t all_get_int(uint64_t u,uint32_t b) {return all_get(2,u,b);}
static void all_set_str(uint64_t u,int32_t v,uint32_t p) {all_set(0,u,v,p);}
static void all_set_agi(uint64_t u,int32_t v,uint32_t p) {all_set(1,u,v,p);}
static void all_set_int(uint64_t u,int32_t v,uint32_t p) {all_set(2,u,v,p);}
__declspec(dllexport) DWORD all_stats_test(const wchar_t *directory,unsigned fault,unsigned target,int32_t *out) {
    DWORD error=field_snapshot(directory,15,0),bytes;HANDLE file;wchar_t path[MAX_PATH];NativeCommand cmd={0};
    if(error) return error;
    command_path(path,MAX_PATH);DeleteFileW(path);
    field_fault=field_unit_calls=all_gets=bad_arguments=0;all_fault=fault;
    for(unsigned stat=0;stat<3;++stat) {all_storage[stat]=10+stat;all_sets[stat]=0;}
    for(unsigned n=0;n<sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]);++n) {
        const char *name=g_persistent_native_names[n];
        if(!strcmp(name,"GetHeroStr")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)all_get_str;
        if(!strcmp(name,"GetHeroAgi")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)all_get_agi;
        if(!strcmp(name,"GetHeroInt")) g_persistent_natives[n].handler=fault==2?0:(uint64_t)(uintptr_t)all_get_int;
        if(!strcmp(name,"SetHeroStr")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)all_set_str;
        if(!strcmp(name,"SetHeroAgi")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)all_set_agi;
        if(!strcmp(name,"SetHeroInt")) g_persistent_natives[n].handler=fault==3?0:(uint64_t)(uintptr_t)all_set_int;
        if(!strcmp(name,"GetHeroLevel")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)all_level;
    }
    cmd.magic=WAR3_NATIVE_MAGIC;cmd.version=WAR3_NATIVE_VERSION;cmd.status=WAR3_NATIVE_STATUS_PENDING;
    cmd.op_count=2;cmd.unit_handle=7;
    cmd.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;cmd.ops[0].handler=(uint64_t)(uintptr_t)object;
    cmd.ops[0].arg0=full;cmd.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    cmd.ops[1].kind=WAR3_NATIVE_OP_SET_BOUND_HERO_ATTRIBUTES;cmd.ops[1].rawcode=target;
    if(fault==4) ++cmd.ops[0].arg0;
    if(fault==5) *(uint64_t *)(field_wrappers[1]+0x50)=0;
    if(fault==13) *(uint64_t *)(object+0x5a8)=1;
    if(fault==14) cmd.ops[1].arg0=1;
    if(fault==15) *(uint64_t *)(object+0x5a8)=0;
    file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();
    BOOL ok=WriteFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);
    if(!ok || bytes!=sizeof(cmd)) return ERROR_WRITE_FAULT;
    run_command();
    for(unsigned stat=0;stat<3;++stat) {out[stat]=all_sets[stat];out[5+stat]=all_storage[stat];}
    out[3]=all_gets;out[4]=bad_arguments;return 0;
}
'''


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler:pytest.skip('clang required')
    root=tmp_path_factory.mktemp('all-hero-stats');source=root/'test.c';library=root/'test.dll'
    source.write_text(HARNESS.replace('static uint8_t object[0x20]','static uint8_t object[0x600]')
        .replace('HELPER_SOURCE',(Path(__file__).parent/'analysis/fixtures/legacy-native-helper.c').as_posix())
        +FIELDS_HARNESS+ALL_STATS_HARNESS,encoding='utf8')
    subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(library),
                    '-luser32','-lkernel32'],check=True,capture_output=True,timeout=60)
    lib=ctypes.CDLL(str(library))
    lib.all_stats_test.argtypes=[ctypes.c_wchar_p,ctypes.c_uint,ctypes.c_uint,ctypes.POINTER(ctypes.c_int32)]
    lib.all_stats_test.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)


def dispatch(native,path,fault=0,target=100):
    out=(ctypes.c_int32*8)();enabled=faulthandler.is_enabled()
    if fault==12 and enabled:faulthandler.disable()
    try:assert native.all_stats_test(str(path)+'\\',fault,target,out)==0
    finally:
        if fault==12 and enabled:faulthandler.enable()
    assert out[4]==0
    return out,(path/f'war3_reforged_native_{os.getpid()}.bin').read_bytes()


@pytest.mark.parametrize('target',[0,100,20000,1000000000])
def test_all_three_base_values_are_verified_in_one_command(native,tmp_path,target):
    out,payload=dispatch(native,tmp_path,target=target)
    results=module.War3Trainer.__new__(module.War3Trainer)._parse_native_helper_results(payload,2)
    assert results[1].kind==164 and results[1].result==target
    assert list(out[:4])==[1,1,1,9]
    assert [out[5]+3,out[6]-7,out[7]+9]==[target]*3


@pytest.mark.parametrize('fault',range(1,17))
def test_errors_stop_at_first_failed_identity_or_readback(native,tmp_path,fault):
    out,payload=dispatch(native,tmp_path,fault=fault)
    with pytest.raises(RuntimeError):module.War3Trainer.__new__(module.War3Trainer)._parse_native_helper_results(payload,2)
    count={7:1,8:2,9:3,10:1,11:3,12:3,16:3}.get(fault,0)
    assert sum(out[:3])==count
    if not count:assert list(out[5:])==[10,11,12]
    if fault in (7,8,9,12):assert out[3]==3+count-1 # no reads after invalidating callback


def test_out_of_range_target_does_not_mutate(native,tmp_path):
    out,payload=dispatch(native,tmp_path,target=1000000001)
    with pytest.raises(RuntimeError):module.War3Trainer.__new__(module.War3Trainer)._parse_native_helper_results(payload,2)
    assert list(out[:3])==[0,0,0]


def test_public_action_binds_current_unit_without_memory_backend(trainer):
    trainer._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(164,20000)])
    assert trainer.set_selected_hero_attributes(20000)==20000
    snapshot=trainer.persistent_native_selected_snapshots.return_value[0]
    ops=((136,0,snapshot.unit_address,snapshot.full_handle,snapshot.owner_address),(164,20000,0,0,0))
    trainer._run_native_helper_ops.assert_called_once_with(snapshot.handle,ops)
    trainer._process_memory.assert_not_called()
    trainer._native_helper_command_path=Mock(return_value='offline-command')
    trainer._write_native_helper_command=Mock()
    trainer._native_helper_batch_hook=1;trainer._native_helper_batch_thread_id=threading.get_ident()
    trainer._wait_native_helper_result=Mock(return_value=[])
    trainer._run_native_helper_ops_locked(snapshot.handle,ops)
    payload=trainer._write_native_helper_command.call_args.args[1]
    base=trainer.NATIVE_HELPER_HEADER_STRUCT.size;size=trainer.NATIVE_HELPER_OP_STRUCT.size
    assert [trainer.NATIVE_HELPER_OP_STRUCT.unpack_from(payload,base+i*size)[:5] for i in range(2)]==list(ops)


def test_selection_change_cannot_override_bound_batch_target(trainer):
    candidate,handle=trainer._direct_selected_context()
    trainer.persistent_native_selected_snapshots.side_effect=AssertionError('Batch must not requery selection')
    trainer._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(164,100)])
    with trainer._bound_elephant_selection(candidate,handle):
        assert trainer.set_selected_hero_attributes(100)==100
    assert trainer._run_native_helper_ops.call_args.args[0]==handle
    assert trainer._run_native_helper_ops.call_args.args[1][0][2:]==(candidate.unit_address,candidate.handle,candidate.owner_address)


@pytest.mark.parametrize('bad_result',[[],[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(164,99)],
                                    [module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(72,100)]])
def test_incomplete_or_wrong_result_is_not_success(trainer,bad_result):
    trainer._run_native_helper_ops=Mock(return_value=bad_result)
    with pytest.raises(RuntimeError):trainer.set_selected_hero_attributes(100)


@pytest.mark.parametrize('value',[-1,1000000001])
def test_invalid_target_fails_before_selection_or_mutation(trainer,value):
    with pytest.raises(ValueError):trainer.set_selected_hero_attributes(value)
    trainer.persistent_native_selected_snapshots.assert_not_called()
