"""Run direct effects through the production C dispatcher, without a game."""
import ctypes
import faulthandler
import os
from pathlib import Path
import shutil
import subprocess

import pytest
import war3_reforged_trainer as module
from test_native_identity_guard import HARNESS
from test_native_ability_actions import ACTIONS


DIRECT = r'''
static uint64_t direct_vtable[0xa80/8];
static unsigned direct_calls,direct_fault;
static void direct_effect(uint64_t data) {
    if(data!=(uint64_t)(uintptr_t)action_data[0] || !action_present[0]) ++bad_arguments;
    ++direct_calls;
    if(direct_fault==100) RaiseException(0xe0000001,0,0,NULL);
    if(direct_fault==101) {
        ++*(uint64_t *)(action_data[0]+0x18);++*(uint64_t *)(action_wrappers[0]+0x20);
    }
    if(direct_fault==102) ++*(uint64_t *)(object+0x18);
    if(direct_fault==103) ++action_levels[0];
    if(direct_fault==104) action_present[0]=0;
    if(direct_fault==105) *(uint64_t *)(action_wrappers[0]+0x50)=0;
}
static void direct_target(uint64_t data,uint64_t target) {
    if(target!=(uint64_t)(uintptr_t)object) ++bad_arguments;
    direct_effect(data);
}
static void direct_point(uint64_t data,float *x,float *y) {
    if(*x!=12.0f || *y!=-4.0f) ++bad_arguments;
    direct_effect(data);
}
__declspec(dllexport) DWORD direct_test(const wchar_t *directory,unsigned effect,unsigned initial,unsigned failure,unsigned *out) {
    unsigned ignored[7];DWORD error,bytes;HANDLE file;wchar_t path[MAX_PATH];NativeCommand cmd={0};
    /* Reuse the fake native table and object-table fixture, then reset all
       mutation counters before submitting the direct-effect command. */
    error=action_test(directory,1,0,1,0,0,ignored);if(error) return error;
    action_present[0]=initial;action_adds=action_removes=action_lookups=bad_arguments=direct_calls=0;
    action_fault=failure<30?failure:0;direct_fault=failure;
    ZeroMemory(direct_vtable,sizeof(direct_vtable));
    direct_vtable[0xa70/8]=(uint64_t)(uintptr_t)direct_target;
    direct_vtable[0x998/8]=direct_vtable[0xa78/8]=(uint64_t)(uintptr_t)direct_effect;
    direct_vtable[0xa58/8]=(uint64_t)(uintptr_t)direct_point;
    direct_vtable[0xa00/8]=(uint64_t)(uintptr_t)direct_effect;
    *(uint64_t *)action_data[0]=(uint64_t)(uintptr_t)direct_vtable;
    if(failure==106) direct_vtable[0x998/8]=0;
    if(failure==107) *(uint64_t *)action_data[0]=1;
    if(failure==1) ++*(uint64_t *)(object+0x18);
    if(failure==18) *(uint64_t *)(action_wrappers[0]+0x50)=0;
    if(failure==108) *(uint64_t *)(action_wrappers[0]+0x18)=0x41496e762b61676cULL;
    if(failure==109) {
        for(unsigned n=0;n<sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]);++n)
            if(!strcmp(g_persistent_natives[n].name,"UnitRemoveAbility")) g_persistent_natives[n].handler=0;
    }
    cmd.magic=WAR3_NATIVE_MAGIC;cmd.version=WAR3_NATIVE_VERSION;cmd.status=WAR3_NATIVE_STATUS_PENDING;
    cmd.op_count=2;cmd.unit_handle=7;
    cmd.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;cmd.ops[0].handler=(uint64_t)(uintptr_t)object;
    cmd.ops[0].arg0=full;cmd.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    cmd.ops[1].kind=WAR3_NATIVE_OP_BOUND_DIRECT_ABILITY;cmd.ops[1].handler=effect;
    cmd.ops[1].rawcode=failure==110?0:action_ids[0];
    if(effect==3) {cmd.ops[1].arg0=0x41400000u;cmd.ops[1].arg1=0xc0800000u;}
    if(failure==111) cmd.ops[1].arg0=0x7fc00000u;
    if(failure==112) cmd.ops[1].arg1=1ULL<<32;
    if(failure==113) {cmd.ops[0]=cmd.ops[1];cmd.op_count=1;}
    command_path(path,MAX_PATH);file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_ALWAYS,0,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();
    BOOL ok=WriteFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);
    if(!ok || bytes!=sizeof(cmd)) return ERROR_WRITE_FAULT;
    run_command();
    out[0]=action_adds;out[1]=action_removes;out[2]=direct_calls;out[3]=action_present[0];out[4]=bad_arguments;
    return 0;
}
'''


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler: pytest.skip('clang required')
    root=tmp_path_factory.mktemp('direct_effect');source=root/'test.c';library=root/'test.dll'
    source.write_text(HARNESS.replace('HELPER_SOURCE',(Path(__file__).parent/'tools/war3_native_helper.c').as_posix())+ACTIONS+DIRECT,encoding='utf8')
    build=subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(library),'-luser32','-lkernel32'],capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    lib=ctypes.CDLL(str(library));lib.direct_test.argtypes=[ctypes.c_wchar_p]+[ctypes.c_uint]*3+[ctypes.POINTER(ctypes.c_uint)]
    lib.direct_test.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)


def execute(native,tmp_path,effect,initial,fault):
    out=(ctypes.c_uint*5)();enabled=faulthandler.is_enabled()
    if enabled: faulthandler.disable()
    try: assert native.direct_test(str(tmp_path)+'\\',effect,initial,fault,out)==0
    finally:
        if enabled: faulthandler.enable()
    payload=(tmp_path/f'war3_reforged_native_{os.getpid()}.bin').read_bytes()
    assert out[4]==0,'wrong pointer/handle or mutation after unit recycle'
    return list(out),payload


@pytest.mark.parametrize('effect',[1,2,3,4])
@pytest.mark.parametrize('initial',[0,1])
def test_effect_lifecycle_with_existing_or_resource_created_ability(native,tmp_path,effect,initial):
    out,payload=execute(native,tmp_path,effect,initial,0)
    result=module.War3Trainer.__new__(module.War3Trainer)._parse_native_helper_results(payload,2)
    assert result[1].result==1
    assert out==[1-initial,1-initial,1,initial,0]


@pytest.mark.parametrize('effect,initial,fault,counts',[
    (2,0,100,[1,1,1,0]),(2,1,100,[0,0,1,1]),
    (2,0,101,[1,0,1,1]),(2,0,102,[1,0,1,1]),(2,0,103,[1,0,1,1]),
    (2,0,104,[1,0,1,0]),(2,0,105,[1,0,1,1]),
    (2,0,106,[1,1,0,0]),(2,0,107,[1,1,0,0]),
    (2,1,108,[0,0,0,1]),(2,0,109,[0,0,0,0]),(2,0,110,[0,0,0,0]),
    (3,0,111,[0,0,0,0]),(3,0,112,[0,0,0,0]),(2,0,113,[0,0,0,0]),
    (2,0,1,[0,0,0,0]),(2,1,18,[0,0,0,1]),(2,1,26,[0,0,0,1]),
    (2,0,5,[1,0,0,0]),(2,0,6,[1,0,0,1]),(2,0,7,[1,0,0,1]),(2,0,8,[1,0,0,1]),
    (2,0,9,[1,1,1,1]),(2,0,10,[1,1,1,0]),(2,0,11,[1,1,1,1]),(2,0,12,[1,1,1,0]),
    (5,0,0,[1,1,0,0]),(5,1,0,[0,0,0,1]), # unknown buff effect ABI is never invoked
])
def test_failures_preserve_identity_and_report_cleanup(native,tmp_path,effect,initial,fault,counts):
    out,payload=execute(native,tmp_path,effect,initial,fault)
    assert out[:4]==counts
    trainer=module.War3Trainer.__new__(module.War3Trainer)
    with pytest.raises(RuntimeError): trainer._parse_native_helper_results(payload,1 if fault==113 else 2)
    operation=trainer.NATIVE_HELPER_OP_STRUCT.unpack_from(payload,trainer.NATIVE_HELPER_HEADER_STRUCT.size+trainer.NATIVE_HELPER_OP_STRUCT.size)
    if fault in (6,7,8,101,102,103,105,9,10,11,12): assert operation[7]!=0
    if fault in (100,104,106,107): assert operation[7]==0
