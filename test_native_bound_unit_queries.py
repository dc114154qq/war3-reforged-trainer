"""Production query dispatch rejects identity changes before publishing values."""
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


QUERIES = r'''
static unsigned query_fault,query_calls;
static uint32_t query_values[2];
static int32_t query_value(uint64_t unit) {
    if(unit!=7) ++bad_arguments;
    unsigned index=query_calls++;
    if(index>=2) {++bad_arguments;return 0;}
    if((query_fault==3 && index==0) || (query_fault==4 && index==1)) {
        *(uint64_t *)(object+0x18)+=1ULL<<32;
        *(uint64_t *)(owner+0x20)=*(uint64_t *)(object+0x18);
    }
    if((query_fault==5 && index==0) || (query_fault==6 && index==1)) RaiseException(0xe0000001,0,0,NULL);
    if(query_fault==10 && index==0) *(uint64_t *)(owner+0x90)=0;
    if(query_fault==11 && index==0) fault=1;
    return (int32_t)query_values[index];
}
__declspec(dllexport) DWORD query_test(const wchar_t *directory,unsigned failure,unsigned first,unsigned second,unsigned *out) {
    NativeCommand cmd={0};DWORD bytes;HANDLE file;wchar_t path[MAX_PATH];
    if(wcslen(directory)>=MAX_PATH-1) return ERROR_INVALID_PARAMETER;
    wcscpy(test_directory,directory);ZeroMemory(object,sizeof(object));ZeroMemory(owner,sizeof(owner));
    *(uint64_t *)(object+0x18)=full;*(uint64_t *)(owner+0x18)=0x2b7733752b61676cULL;
    *(uint64_t *)(owner+0x20)=full;*(uint64_t *)(owner+0x90)=(uint64_t)(uintptr_t)object;
    query_fault=failure;query_calls=bad_arguments=0;query_values[0]=first;query_values[1]=second;
    fault=failure==2?2:0;
    g_persistent_unit_resolver=(uint64_t)(uintptr_t)fake_unit;
    g_persistent_agent_resolver=(uint64_t)(uintptr_t)fake_agent;
    cmd.magic=WAR3_NATIVE_MAGIC;cmd.version=WAR3_NATIVE_VERSION;cmd.status=WAR3_NATIVE_STATUS_PENDING;
    cmd.op_count=3;cmd.unit_handle=7;
    cmd.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;cmd.ops[0].handler=(uint64_t)(uintptr_t)object;
    cmd.ops[0].arg0=full;cmd.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    for(unsigned n=1;n<3;++n) {cmd.ops[n].kind=WAR3_NATIVE_OP_JASS_UNIT_INT_QUERY;cmd.ops[n].handler=(uint64_t)(uintptr_t)query_value;}
    if(failure==1) ++cmd.ops[0].arg0;
    if(failure==7) cmd.ops[1].handler=(uint64_t)(uintptr_t)object;
    if(failure==8) cmd.ops[1].rawcode=1;
    if(failure==9) cmd.ops[2].handler=(uint64_t)(uintptr_t)object;
    command_path(path,MAX_PATH);
    file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();
    BOOL ok=WriteFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);
    if(!ok || bytes!=sizeof(cmd)) return ERROR_WRITE_FAULT;
    run_command();out[0]=query_calls;out[1]=bad_arguments;return 0;
}
'''


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler:pytest.skip('clang required')
    root=tmp_path_factory.mktemp('bound-queries');source=root/'test.c';library=root/'test.dll'
    source.write_text(HARNESS.replace('HELPER_SOURCE',(Path(__file__).parent/'analysis/fixtures/legacy-native-helper.c').as_posix())+QUERIES,encoding='utf8')
    subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(library),
                    '-luser32','-lkernel32'],check=True,capture_output=True,timeout=60)
    lib=ctypes.CDLL(str(library))
    lib.query_test.argtypes=[ctypes.c_wchar_p,ctypes.c_uint,ctypes.c_uint,ctypes.c_uint,ctypes.POINTER(ctypes.c_uint)]
    lib.query_test.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)


@pytest.mark.parametrize('failure',range(12))
def test_query_sequence_has_no_successful_mixed_identity_result(native,tmp_path,failure):
    out=(ctypes.c_uint*2)();enabled=faulthandler.is_enabled()
    if failure in (5,6) and enabled:faulthandler.disable()
    try:assert native.query_test(str(tmp_path)+'\\',failure,0xc2480000,0x42490000,out)==0
    finally:
        if failure in (5,6) and enabled:faulthandler.enable()
    assert out[1]==0
    payload=(tmp_path/f'war3_reforged_native_{os.getpid()}.bin').read_bytes()
    t=module.War3Trainer.__new__(module.War3Trainer)
    if not failure:
        results=t._parse_native_helper_results(payload,3)
        assert [t._float_from_bits(r.result) for r in results[1:]]==[-50.0,50.25]
    else:
        with pytest.raises(RuntimeError):t._parse_native_helper_results(payload,3)
    assert out[0]==(2 if failure in (0,4,6) else 1 if failure in (3,5,9,10,11) else 0)


PUBLIC = [('get_selected_hero_level',('GetHeroLevel',),(17,),17),
          ('is_selected_unit_invulnerable',('BlzIsUnitInvulnerable',),(0,),False),
          ('is_selected_unit_paused',('IsUnitPaused',),(1,),True),
          ('get_selected_unit_position',('GetUnitX','GetUnitY'),(0xc2480000,0x42490000),(-50.0,50.25))]


@pytest.mark.parametrize('method,names,values,expected',PUBLIC)
def test_public_query_reads_one_identity_and_only_requested_natives(trainer,method,names,values,expected):
    trainer._query_native_table_handlers=Mock(return_value={name:module.NativeHandler(name,0,0x200000+i*0x100) for i,name in enumerate(names)})
    trainer._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(136,1)]+[module.NativeHelperOpResult(77,v) for v in values])
    assert getattr(trainer,method)()==expected
    snapshot=trainer.persistent_native_selected_snapshots.return_value[0]
    ops=((136,0,snapshot.unit_address,snapshot.full_handle,snapshot.owner_address),)+tuple((77,0,0x200000+i*0x100,0,0) for i in range(len(names)))
    trainer._query_native_table_handlers.assert_called_once_with(names)
    trainer._run_native_helper_ops.assert_called_once_with(snapshot.handle,ops)
    trainer._process_memory.assert_not_called()
    trainer._native_helper_command_path=Mock(return_value='offline-command');trainer._write_native_helper_command=Mock()
    trainer._native_helper_batch_hook=1;trainer._native_helper_batch_thread_id=threading.get_ident()
    trainer._wait_native_helper_result=Mock(return_value=[])
    trainer._run_native_helper_ops_locked(snapshot.handle,ops)
    payload=trainer._write_native_helper_command.call_args.args[1]
    base=trainer.NATIVE_HELPER_HEADER_STRUCT.size;size=trainer.NATIVE_HELPER_OP_STRUCT.size
    assert [trainer.NATIVE_HELPER_OP_STRUCT.unpack_from(payload,base+i*size)[:5] for i in range(len(ops))]==list(ops)


def test_bound_batch_query_does_not_follow_changed_selection(trainer):
    candidate,handle=trainer._direct_selected_context()
    trainer.persistent_native_selected_snapshots.side_effect=AssertionError('Do not requery selection')
    trainer._query_native_table_handlers=Mock(return_value={'GetUnitX':module.NativeHandler('GetUnitX',0,0x200000),'GetUnitY':module.NativeHandler('GetUnitY',0,0x200100)})
    trainer._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(77,0),module.NativeHelperOpResult(77,0)])
    with trainer._bound_elephant_selection(candidate,handle):assert trainer.get_selected_unit_position()==(0,0)
    assert trainer._run_native_helper_ops.call_args.args[0]==handle
    assert trainer._run_native_helper_ops.call_args.args[1][0][2:]==(candidate.unit_address,candidate.handle,candidate.owner_address)


@pytest.mark.parametrize('results',[[],[module.NativeHelperOpResult(136,1)],
                                  [module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(70,17)],
                                  [module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(77,17,last_error=6)]])
def test_bad_response_never_returns_stale_or_default_query_value(trainer,results):
    trainer._query_native_table_handlers=Mock(return_value={'GetHeroLevel':module.NativeHandler('GetHeroLevel',0,0x200000)})
    trainer._run_native_helper_ops=Mock(return_value=results)
    with pytest.raises(RuntimeError):trainer.get_selected_hero_level()
