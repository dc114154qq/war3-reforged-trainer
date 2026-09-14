"""Execute owner-group capture and mutation through the production dispatcher."""
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
from test_native_selected_context import trainer

KILL=r'''
static uint8_t k_objects[3][0x20],k_wrappers[3][0x98];
static unsigned k_fault,k_index,k_calls,k_mask,k_destroyed,k_owner_changed;
static uint64_t k_queue[5];
static uint64_t k_resolve(uint64_t h) {
    if(h>=20 && h<23) return (uint64_t)(uintptr_t)k_objects[h-20];
    return fake_unit(h);
}
static uint64_t k_agent(uint32_t lo,uint32_t hi) {
    uint64_t id=((uint64_t)hi<<32)|lo;
    for(unsigned n=0;n<3;++n) if(id==*(uint64_t *)(k_objects[n]+0x18)) return (uint64_t)(uintptr_t)k_wrappers[n];
    return fake_agent(lo,hi);
}
static uint64_t k_owner(uint64_t h) {
    if(h==7) return k_fault==9 && k_destroyed?14:13;
    if(h<20 || h>=23) {++bad_arguments;return 0;}
    if(k_fault==10 && h==21 && k_destroyed) {
        ++*(uint64_t *)(k_objects[1]+0x18);++*(uint64_t *)(k_wrappers[1]+0x20);
    }
    return h==21 && k_owner_changed?14:13;
}
static uint64_t k_create(void) {return k_fault==1?0:77;}
static void k_enum(uint64_t group,uint64_t player,uint64_t filter) {
    if(group!=77 || player!=13 || filter) ++bad_arguments;
    k_queue[0]=7;k_queue[1]=20;k_queue[2]=21;k_queue[3]=20;k_queue[4]=0;
    if(k_fault==2) k_queue[0]=0;
    if(k_fault==3 || k_fault==16) ++*(uint64_t *)(object+0x18);
    if(k_fault==15) RaiseException(0xe0123456,0,0,NULL);
}
static uint64_t k_first(uint64_t group) {
    if(group!=77) ++bad_arguments;
    return k_queue[k_index];
}
static void k_remove(uint64_t group,uint64_t h) {
    if(group!=77 || h!=k_queue[k_index]) ++bad_arguments;
    if(k_fault==13 && k_index==2) {
        ++*(uint64_t *)(k_objects[0]+0x18);++*(uint64_t *)(k_wrappers[0]+0x20);
    }
    if(k_fault!=14) ++k_index;
}
static void k_destroy(uint64_t group) {
    if(group!=77 || k_destroyed) ++bad_arguments;
    ++k_destroyed;
    if(k_fault==4 || k_fault==16) RaiseException(0xe0123456,0,0,NULL);
}
static void k_kill(uint64_t h) {
    if(k_destroyed!=1 || (h!=7 && h!=20 && h!=21)) ++bad_arguments;
    ++k_calls;k_mask|=h==7?1:h==20?2:4;
    if(h==7) fault=1; /* intentional destruction of source must not stop others */
    if(k_calls==1) {
        if(k_fault==5) {++*(uint64_t *)(k_objects[1]+0x18);++*(uint64_t *)(k_wrappers[1]+0x20);}
        if(k_fault==6) k_owner_changed=1;
        if(k_fault==7) k_queue[4]=22; /* spawned target must not extend frozen list */
        if(k_fault==8) RaiseException(0xe0123456,0,0,NULL);
    }
}
__declspec(dllexport) DWORD kill_test(const wchar_t *directory,unsigned failure,unsigned *out) {
    NativeCommand cmd={0};DWORD bytes;wchar_t path[MAX_PATH];
    if(wcslen(directory)>=MAX_PATH-1) return ERROR_INVALID_PARAMETER;
    wcscpy(test_directory,directory);ZeroMemory(object,sizeof(object));ZeroMemory(owner,sizeof(owner));
    *(uint64_t *)(object+0x18)=full;*(uint64_t *)(owner+0x18)=0x2b7733752b61676cULL;
    *(uint64_t *)(owner+0x20)=full;*(uint64_t *)(owner+0x90)=(uint64_t)(uintptr_t)object;
    fault=bad_arguments=k_index=k_calls=k_mask=k_destroyed=k_owner_changed=0;k_fault=failure;
    for(unsigned n=0;n<3;++n) {
        ZeroMemory(k_objects[n],0x20);ZeroMemory(k_wrappers[n],0x98);
        *(uint64_t *)(k_objects[n]+0x18)=*(uint64_t *)(k_wrappers[n]+0x20)=0x445500000001ULL+n;
        *(uint64_t *)(k_wrappers[n]+0x18)=0x2b7733752b61676cULL;
        *(uint64_t *)(k_wrappers[n]+0x90)=(uint64_t)(uintptr_t)k_objects[n];
    }
    g_persistent_unit_resolver=(uint64_t)(uintptr_t)k_resolve;g_persistent_agent_resolver=(uint64_t)(uintptr_t)k_agent;
    for(unsigned n=0;n<sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]);++n) {
        const char *name=g_persistent_native_names[n];g_persistent_natives[n].name=name;g_persistent_natives[n].handler=0;
#define BIND(s,f) if(!strcmp(name,s)) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)f;
        BIND("GetOwningPlayer",k_owner) BIND("CreateGroup",k_create) BIND("DestroyGroup",k_destroy)
        BIND("GroupEnumUnitsOfPlayer",k_enum) BIND("FirstOfGroup",k_first) BIND("GroupRemoveUnit",k_remove)
#undef BIND
        if(failure==11 && !strcmp(name,"DestroyGroup")) g_persistent_natives[n].handler=0;
    }
    cmd.magic=WAR3_NATIVE_MAGIC;cmd.version=WAR3_NATIVE_VERSION;cmd.status=WAR3_NATIVE_STATUS_PENDING;
    cmd.unit_handle=7;cmd.op_count=2;cmd.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;
    cmd.ops[0].handler=(uint64_t)(uintptr_t)object;cmd.ops[0].arg0=full;cmd.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    cmd.ops[1].kind=WAR3_NATIVE_OP_BOUND_OWNER_KILL;cmd.ops[1].handler=(uint64_t)(uintptr_t)k_kill;
    if(failure==12) cmd.ops[1].handler=(uint64_t)(uintptr_t)object;
    if(failure==17) cmd.ops[0].arg0+=1;
    if(failure==18) cmd.ops[1].arg0=1;
    command_path(path,MAX_PATH);HANDLE file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_NEW,0,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();
    BOOL ok=WriteFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);
    if(!ok || bytes!=sizeof(cmd)) return ERROR_WRITE_FAULT;
    run_command();out[0]=bad_arguments;out[1]=k_calls;out[2]=k_mask;out[3]=k_destroyed;out[4]=k_index;
    return 0;
}
'''

@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler:pytest.skip('clang required')
    root=tmp_path_factory.mktemp('owner-kill');source=root/'test.c';library=root/'test.dll'
    source.write_text(HARNESS.replace('HELPER_SOURCE',(Path(__file__).parent/'analysis/fixtures/legacy-native-helper.c').as_posix())+KILL,encoding='utf8')
    subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(library),'-luser32','-lkernel32'],check=True,capture_output=True,timeout=60)
    lib=ctypes.CDLL(str(library));lib.kill_test.argtypes=[ctypes.c_wchar_p,ctypes.c_uint,ctypes.POINTER(ctypes.c_uint)]
    lib.kill_test.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)

def dispatch(native,path,failure=0):
    out=(ctypes.c_uint*5)();enabled=faulthandler.is_enabled()
    if failure in (4,8,15,16) and enabled:faulthandler.disable()
    try:assert native.kill_test(str(path)+'\\',failure,out)==0
    finally:
        if failure in (4,8,15,16) and enabled:faulthandler.enable()
    assert out[0]==0
    return out,(path/f'war3_reforged_native_{os.getpid()}.bin').read_bytes()

def parse(payload):return module.War3Trainer.__new__(module.War3Trainer)._parse_native_helper_results(payload,2)

@pytest.mark.parametrize('failure,count,mask,skipped',[(0,3,7,0),(2,0,0,0),(5,2,3,1),(6,2,3,1),(7,3,7,0),(10,2,3,1)])
def test_frozen_targets_deduplicate_skip_replacements_and_allow_source_death(native,tmp_path,failure,count,mask,skipped):
    out,payload=dispatch(native,tmp_path,failure);result=parse(payload)[1]
    assert result.result==out[1]==count and out[2]==mask and out[3]==1 and result.arg0==skipped

@pytest.mark.parametrize('failure',[1,3,4,8,9,11,12,13,14,15,16,17,18])
def test_failures_stop_mutation_and_release_group_once(native,tmp_path,failure):
    out,payload=dispatch(native,tmp_path,failure)
    with pytest.raises(RuntimeError,match='owner_kill_callbacks=0') as raised:parse(payload)
    assert out[1]==int(failure==8)
    assert out[3]==int(failure not in (1,11,12,17,18))
    if failure in (4,16):assert f'owner_kill_cleanup_error={0xe0123456}' in str(raised.value)

def test_public_owner_group_uses_bound_selection_and_one_command(trainer):
    trainer._query_native_table_handlers=Mock(return_value={'KillUnit':module.NativeHandler('KillUnit',0,0x200000)})
    trainer._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(169,3)])
    assert trainer.kill_selected_owner_units()==3
    snapshot=trainer.persistent_native_selected_snapshots.return_value[0]
    ops=((136,0,snapshot.unit_address,snapshot.full_handle,snapshot.owner_address),(169,0,0x200000,0,0))
    trainer._run_native_helper_ops.assert_called_once_with(snapshot.handle,ops,timeout_ms=120000)
    trainer._query_native_table_handlers.assert_called_once_with(('KillUnit',));trainer._process_memory.assert_not_called()
    trainer._native_helper_command_path=Mock(return_value='offline-command');trainer._write_native_helper_command=Mock()
    trainer._native_helper_batch_hook=1;trainer._native_helper_batch_thread_id=threading.get_ident();trainer._wait_native_helper_result=Mock(return_value=[])
    trainer._run_native_helper_ops_locked(snapshot.handle,ops)
    payload=trainer._write_native_helper_command.call_args.args[1];base=trainer.NATIVE_HELPER_HEADER_STRUCT.size;size=trainer.NATIVE_HELPER_OP_STRUCT.size
    assert [trainer.NATIVE_HELPER_OP_STRUCT.unpack_from(payload,base+n*size)[:5] for n in range(2)]==list(ops)

@pytest.mark.parametrize('result',[[],[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(84,1)],
    [module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(169,100001)]])
def test_bad_group_ack_is_rejected(trainer,result):
    trainer._query_native_table_handlers=Mock(return_value={'KillUnit':module.NativeHandler('KillUnit',0,0x200000)})
    trainer._run_native_helper_ops=Mock(return_value=result)
    with pytest.raises(RuntimeError):trainer.kill_selected_owner_units()
