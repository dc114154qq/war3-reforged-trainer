"""Guard shared unit actions, including the two callbacks of explode."""
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


ACTIONS = r'''
static unsigned action_fault,action_bools,action_voids,action_value;
static void action_bool(uint64_t unit,uint32_t value) {
    if(unit!=7 || value>1) ++bad_arguments;
    ++action_bools;action_value=value;
    if(action_fault==5) *(uint64_t *)(object+0x18)+=1ULL<<32;
    if(action_fault==6) *(uint64_t *)(owner+0x90)=0;
    if(action_fault==7) RaiseException(0xe0000001,0,0,NULL);
    if(action_fault==8) fault=1;
}
static void action_void(uint64_t unit) {
    if(unit!=7) ++bad_arguments;
    ++action_voids;
    /* RemoveUnit legitimately invalidates the target itself. A completed last
       callback must not be followed by an identity check reporting failure. */
    if(action_fault==8) fault=1;
}
__declspec(dllexport) DWORD action_test(const wchar_t *directory,unsigned mode,unsigned failure,unsigned *out) {
    NativeCommand cmd={0};DWORD bytes;HANDLE file;wchar_t path[MAX_PATH];
    if(wcslen(directory)>=MAX_PATH-1) return ERROR_INVALID_PARAMETER;
    wcscpy(test_directory,directory);
    ZeroMemory(object,sizeof(object));ZeroMemory(owner,sizeof(owner));
    *(uint64_t *)(object+0x18)=full;*(uint64_t *)(owner+0x18)=0x2b7733752b61676cULL;
    *(uint64_t *)(owner+0x20)=full;*(uint64_t *)(owner+0x90)=(uint64_t)(uintptr_t)object;
    fault=failure<=3?failure:0;action_fault=failure;action_bools=action_voids=action_value=bad_arguments=0;
    g_persistent_unit_resolver=(uint64_t)(uintptr_t)fake_unit;
    g_persistent_agent_resolver=(uint64_t)(uintptr_t)fake_agent;
    cmd.magic=WAR3_NATIVE_MAGIC;cmd.version=WAR3_NATIVE_VERSION;cmd.status=WAR3_NATIVE_STATUS_PENDING;
    cmd.op_count=mode==3?3:2;cmd.unit_handle=7;
    cmd.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;
    cmd.ops[0].handler=(uint64_t)(uintptr_t)object;cmd.ops[0].arg0=full;cmd.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    cmd.ops[1].kind=mode==2?WAR3_NATIVE_OP_JASS_UNIT_VOID:WAR3_NATIVE_OP_JASS_UNIT_BOOL;
    cmd.ops[1].handler=(uint64_t)(uintptr_t)(mode==2?(void *)action_void:(void *)action_bool);
    cmd.ops[1].rawcode=mode==2?0:mode==0?0:1;
    if(mode==3) {cmd.ops[2].kind=WAR3_NATIVE_OP_JASS_UNIT_VOID;cmd.ops[2].handler=(uint64_t)(uintptr_t)action_void;}
    if(failure==4) *(uint64_t *)(object+0x18)+=1ULL<<32;
    if(failure==9) cmd.ops[1].handler=(uint64_t)(uintptr_t)object;
    if(failure==10) cmd.ops[1].rawcode=2;
    if(failure==11) cmd.ops[1].arg0=1;
    if(failure==12) cmd.ops[1].kind=WAR3_NATIVE_OP_JASS_UNIT_INT_BOOL;
    command_path(path,MAX_PATH);
    file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();
    BOOL ok=WriteFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);
    if(!ok || bytes!=sizeof(cmd)) return ERROR_WRITE_FAULT;
    run_command();out[0]=action_bools;out[1]=action_voids;out[2]=action_value;out[3]=bad_arguments;
    return 0;
}
'''


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler:pytest.skip('clang required')
    root=tmp_path_factory.mktemp('simple-unit');source=root/'test.c';library=root/'test.dll'
    source.write_text(HARNESS.replace('HELPER_SOURCE',(Path(__file__).parent/'tools/war3_native_helper.c').as_posix())
                      +ACTIONS,encoding='utf8')
    subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(library),
                    '-luser32','-lkernel32'],check=True,capture_output=True,timeout=60)
    lib=ctypes.CDLL(str(library))
    lib.action_test.argtypes=[ctypes.c_wchar_p,ctypes.c_uint,ctypes.c_uint,ctypes.POINTER(ctypes.c_uint)]
    lib.action_test.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)


def dispatch(native,path,mode,failure=0):
    out=(ctypes.c_uint*4)();enabled=faulthandler.is_enabled()
    if failure==7 and enabled:faulthandler.disable()
    try:assert native.action_test(str(path)+'\\',mode,failure,out)==0
    finally:
        if failure==7 and enabled:faulthandler.enable()
    assert out[3]==0
    return out,(path/f'war3_reforged_native_{os.getpid()}.bin').read_bytes()


@pytest.mark.parametrize('mode',[0,1,2,3])
def test_shared_actions_use_jass_abi_and_acknowledge_callbacks(native,tmp_path,mode):
    out,payload=dispatch(native,tmp_path,mode)
    results=module.War3Trainer.__new__(module.War3Trainer)._parse_native_helper_results(payload,3 if mode==3 else 2)
    assert list(out[:2])==([0,1] if mode==2 else [1,1] if mode==3 else [1,0])
    assert results[1].result==(0 if mode==0 else 1)


@pytest.mark.parametrize('failure',[1,2,3,4,9,10,11,12])
def test_invalid_initial_identity_or_command_has_no_callbacks(native,tmp_path,failure):
    out,payload=dispatch(native,tmp_path,3,failure)
    with pytest.raises(RuntimeError):module.War3Trainer.__new__(module.War3Trainer)._parse_native_helper_results(payload,3)
    assert list(out[:2])==[0,0]


@pytest.mark.parametrize('failure',[5,6,7,8])
def test_explode_does_not_kill_replacement_after_first_callback(native,tmp_path,failure):
    out,payload=dispatch(native,tmp_path,3,failure)
    with pytest.raises(RuntimeError):module.War3Trainer.__new__(module.War3Trainer)._parse_native_helper_results(payload,3)
    assert list(out[:2])==[1,0]


def test_intentional_final_removal_is_success(native,tmp_path):
    out,payload=dispatch(native,tmp_path,2,8)
    results=module.War3Trainer.__new__(module.War3Trainer)._parse_native_helper_results(payload,2)
    assert list(out[:2])==[0,1] and results[1].result==1


PUBLIC = [
    ('set_selected_unit_invulnerable',(True,),(('SetUnitInvulnerable',True),)),
    ('set_selected_unit_invulnerable',(False,),(('SetUnitInvulnerable',False),)),
    ('set_selected_unit_pathing',(False,),(('SetUnitPathing',False),)),
    ('set_selected_unit_paused',(True,),(('PauseUnit',True),)),
    ('reset_selected_unit_cooldown',(),(('UnitResetCooldown',None),)),
    ('kill_selected_unit',(),(('KillUnit',None),)),
    ('remove_selected_unit',(),(('RemoveUnit',None),)),
    ('explode_selected_unit',(),(('SetUnitExploded',True),('KillUnit',None))),
]


def configure(trainer):
    requests=[]
    def query(names):
        names=tuple(names);requests.append(names)
        return {name:module.NativeHandler(name,0,0x200000+n*0x100) for n,name in enumerate(names)}
    trainer._query_native_table_handlers=Mock(side_effect=query)
    trainer._run_native_helper_ops=Mock(side_effect=lambda handle,ops:[module.NativeHelperOpResult(136,1)]+
        [module.NativeHelperOpResult(op[0],1 if op[0]==70 else op[1]) for op in ops[1:]])
    return requests


@pytest.mark.parametrize('method,args,actions',PUBLIC)
def test_public_routes_only_query_needed_functions_and_use_one_guarded_batch(trainer,method,args,actions):
    requests=configure(trainer)
    getattr(trainer,method)(*args)
    snapshot=trainer.persistent_native_selected_snapshots.return_value[0]
    assert requests==[tuple(name for name,value in actions)]
    ops=((136,0,snapshot.unit_address,snapshot.full_handle,snapshot.owner_address),)+tuple(
        (70 if value is None else 71,0 if value is None else int(value),0x200000+n*0x100,0,0)
        for n,(name,value) in enumerate(actions))
    trainer._run_native_helper_ops.assert_called_once_with(snapshot.handle,ops)
    trainer._process_memory.assert_not_called()
    trainer._native_helper_command_path=Mock(return_value='offline-command')
    trainer._write_native_helper_command=Mock();trainer._native_helper_batch_hook=1
    trainer._native_helper_batch_thread_id=threading.get_ident();trainer._wait_native_helper_result=Mock(return_value=[])
    trainer._run_native_helper_ops_locked(snapshot.handle,ops)
    payload=trainer._write_native_helper_command.call_args.args[1]
    base=trainer.NATIVE_HELPER_HEADER_STRUCT.size;size=trainer.NATIVE_HELPER_OP_STRUCT.size
    assert [trainer.NATIVE_HELPER_OP_STRUCT.unpack_from(payload,base+i*size)[:5] for i in range(len(ops))]==list(ops)


def test_bound_target_survives_selection_change_during_handler_lookup(trainer):
    configure(trainer);candidate,handle=trainer._direct_selected_context()
    trainer.persistent_native_selected_snapshots.side_effect=AssertionError('Must keep batch target')
    with trainer._bound_elephant_selection(candidate,handle):trainer.explode_selected_unit()
    assert trainer._run_native_helper_ops.call_args.args[0]==handle
    assert trainer._run_native_helper_ops.call_args.args[1][0][2:]==(candidate.unit_address,candidate.handle,candidate.owner_address)


@pytest.mark.parametrize('failure',[[],[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(70,1)],
                                  [module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(71,0)]])
def test_bool_action_rejects_incomplete_wrong_kind_or_wrong_ack(trainer,failure):
    configure(trainer);trainer._run_native_helper_ops.side_effect=None;trainer._run_native_helper_ops.return_value=failure
    with pytest.raises(RuntimeError):trainer.set_selected_unit_invulnerable(True)
