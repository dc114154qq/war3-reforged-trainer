"""Exercise internal ability ABI and identity guards in the production dispatcher."""
import ctypes
from pathlib import Path
import shutil
import subprocess
from unittest.mock import Mock

import pytest
import war3_reforged_trainer as module
from test_native_identity_guard import HARNESS
from test_native_snapshot_binding import make_candidate, make_snapshot


INTERNAL_HARNESS = r'''
static unsigned internal_fault;
static void mutate_unit(unsigned stage) {
    ++writes;
    if (internal_fault == stage) *(uint64_t *)(object+0x18) += 1;
}
static void internal_begin(uint64_t unit) {
    if(unit!=(uint64_t)(uintptr_t)object) ++bad_arguments;
    mutate_unit(2);
}
static uint64_t internal_add(uint64_t unit,uint32_t id,uint32_t a,uint32_t b,uint32_t c,uint32_t d) {
    if(unit!=(uint64_t)(uintptr_t)object || id!=0x41303031u || a || b || c || d) ++bad_arguments;
    mutate_unit(3); return (uint64_t)(uintptr_t)ability_data;
}
static void internal_end(uint64_t unit) {
    if(unit!=(uint64_t)(uintptr_t)object) ++bad_arguments;
    mutate_unit(4);
}
static uint64_t internal_find(uint64_t unit,uint32_t id,uint32_t a,uint8_t b,uint8_t c,uint8_t d,uint8_t e) {
    if(unit!=(uint64_t)(uintptr_t)object || id!=0x41303031u || a || b!=1 || c!=1 || d!=1 || e)
        ++bad_arguments;
    return internal_fault == 6 ? 0 : (uint64_t)(uintptr_t)ability_data;
}
static void internal_remove(uint64_t unit,uint64_t data) {
    if(unit!=(uint64_t)(uintptr_t)object || data!=(uint64_t)(uintptr_t)ability_data) ++bad_arguments;
    mutate_unit(5);
}
static void internal_refresh(uint64_t unit) {
    if(unit!=(uint64_t)(uintptr_t)object) ++bad_arguments;
    mutate_unit(7);
}
__declspec(dllexport) DWORD internal_test(const wchar_t *directory,unsigned failure,unsigned *out) {
    unsigned initial[4]; DWORD error=execute(directory,30,initial),bytes;
    NativeCommand cmd={0}; wchar_t path[MAX_PATH]; HANDLE file;
    if(error) return error;
    internal_fault=failure; writes=bad_arguments=0;
    cmd.magic=WAR3_NATIVE_MAGIC; cmd.version=WAR3_NATIVE_VERSION;
    cmd.status=WAR3_NATIVE_STATUS_PENDING;cmd.unit_handle=7;cmd.op_count=7;
    cmd.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;
    cmd.ops[0].handler=(uint64_t)(uintptr_t)object;cmd.ops[0].arg0=full;
    cmd.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    cmd.ops[1].kind=WAR3_NATIVE_OP_INTERNAL_ABILITY_BEGIN;cmd.ops[1].handler=(uint64_t)(uintptr_t)internal_begin;
    cmd.ops[2].kind=WAR3_NATIVE_OP_INTERNAL_ABILITY_ADD;cmd.ops[2].handler=(uint64_t)(uintptr_t)internal_add;
    cmd.ops[2].rawcode=0x41303031u;
    cmd.ops[3].kind=WAR3_NATIVE_OP_INTERNAL_ABILITY_END;cmd.ops[3].handler=(uint64_t)(uintptr_t)internal_end;
    cmd.ops[4].kind=WAR3_NATIVE_OP_INTERNAL_ABILITY_FIND;cmd.ops[4].handler=(uint64_t)(uintptr_t)internal_find;
    cmd.ops[4].rawcode=0x41303031u;
    cmd.ops[5].kind=WAR3_NATIVE_OP_INTERNAL_ABILITY_REMOVE;cmd.ops[5].handler=(uint64_t)(uintptr_t)internal_remove;
    cmd.ops[5].rawcode=0x41303031u;cmd.ops[5].arg0=(uint64_t)(uintptr_t)ability_data;
    cmd.ops[5].arg1=(uint64_t)(uintptr_t)internal_find;
    cmd.ops[6].kind=WAR3_NATIVE_OP_INTERNAL_ABILITY_REFRESH;cmd.ops[6].handler=(uint64_t)(uintptr_t)internal_refresh;
    if(failure==1) *(uint64_t *)(object+0x18)+=1;
    if(failure==8) cmd.ops[1].handler=(uint64_t)(uintptr_t)object; /* data, not code */
    command_path(path,MAX_PATH);
    file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();
    BOOL ok=WriteFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);
    if(!ok || bytes!=sizeof(cmd)) return ERROR_WRITE_FAULT;
    run_command();
    file=CreateFileW(path,GENERIC_READ,0,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();
    ok=ReadFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);DeleteFileW(path);
    if(!ok || bytes!=sizeof(cmd)) return ERROR_READ_FAULT;
    if(!failure && (cmd.ops[2].result!=(uint64_t)(uintptr_t)ability_data ||
                   cmd.ops[4].result!=(uint64_t)(uintptr_t)ability_data || cmd.ops[5].result!=1))
        ++bad_arguments;
    out[0]=cmd.status;out[1]=cmd.last_error;out[2]=writes;out[3]=bad_arguments;
    return 0;
}
'''


@pytest.fixture(scope='module')
def internal(tmp_path_factory):
    compiler = shutil.which('clang')
    if not compiler:
        pytest.skip('clang required')
    root = tmp_path_factory.mktemp('internal-ability')
    source, library = root/'test.c', root/'test.dll'
    source.write_text(HARNESS.replace('HELPER_SOURCE', (Path(__file__).parent/'analysis/fixtures/legacy-native-helper.c').as_posix())
                      + INTERNAL_HARNESS, encoding='utf8')
    subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(library),
                    '-luser32','-lkernel32'],check=True,capture_output=True,timeout=60)
    lib = ctypes.CDLL(str(library))
    lib.internal_test.argtypes = [ctypes.c_wchar_p,ctypes.c_uint,ctypes.POINTER(ctypes.c_uint)]
    lib.internal_test.restype = ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)


@pytest.mark.parametrize('failure,writes', [(0,5),(1,0),(2,1),(3,2),(4,3),(5,4),(6,3),(7,5),(8,0)])
def test_internal_abi_and_recycled_unit_stop_remaining_ops(internal,tmp_path,failure,writes):
    out = (ctypes.c_uint*4)()
    assert internal.internal_test(str(tmp_path)+'\\',failure,out) == 0
    assert out[0] == (3 if failure else 2)
    assert bool(out[1]) == bool(failure)
    assert tuple(out)[2:] == (writes,0)


def test_internal_wrapper_uses_jass_handle_with_full_identity_and_strips_guard_result():
    trainer = module.War3Trainer.__new__(module.War3Trainer)
    candidate = make_candidate(make_snapshot())
    result = module.NativeHelperOpResult(31,0x200000)
    trainer._run_native_helper_ops = Mock(return_value=[module.NativeHelperOpResult(136,1),result])
    ops = ((31,0x41303031,0x100000,0,0),)
    assert trainer._run_internal_ability_ops(candidate,iter(ops)) == [result]
    trainer._run_native_helper_ops.assert_called_once_with(candidate.native_snapshot.handle, (
        (136,0,candidate.unit_address,candidate.handle,candidate.owner_address), *ops))
