"""Real native snapshot and regeneration dispatcher in an isolated fake game."""
import ctypes
from dataclasses import replace
import math
import os
from pathlib import Path
import shutil
import subprocess
from unittest.mock import Mock

import pytest
import war3_reforged_trainer as module
from test_native_snapshot_payload import HARNESS
from test_native_snapshot_binding import make_snapshot, make_candidate, snapshot_result
from test_native_basic_writes import context


TEMP_PATH = r'''
static wchar_t regen_directory[MAX_PATH];
static DWORD regen_temp(DWORD count,wchar_t *path) {
    size_t n=wcslen(regen_directory);
    if(n+1>=count) return 0;
    memcpy(path,regen_directory,(n+1)*sizeof(wchar_t));return (DWORD)n;
}
#define GetTempPathW regen_temp
'''

REGEN = r'''
static uint8_t regen_props[3][0xe8];
static void *regen_readonly;
static uint64_t regen_lists[2][128];
static uint64_t regen_full(unsigned k) { return 0x567800001000ULL+k; }
static uint64_t regen_agent(uint32_t slot,uint32_t serial) {
    uint64_t id=((uint64_t)serial<<32)|slot;
    if(id==0x100000001ULL) return (uint64_t)(uintptr_t)owners[0];
    for(unsigned k=0;k<3;++k) if(id==regen_full(k)) {
        if(regen_scenario==11) *(uint64_t *)(objects[0]+0x18)+=1;
        if(regen_scenario==12) regen_lists[0][0]=0;
        return (uint64_t)(uintptr_t)(regen_scenario==13 && k==0 ? regen_readonly : regen_props[k]);
    }
    return 0;
}
static void prepare_regen(void) {
    if(regen_readonly) { VirtualFree(regen_readonly,0,MEM_RELEASE);regen_readonly=NULL; }
    ZeroMemory(regen_props,sizeof(regen_props));ZeroMemory(regen_lists,sizeof(regen_lists));
    for(unsigned k=0;k<3;++k) {
        *(uint64_t *)(regen_props[k]+0x18)=0x6072656c5e70726fULL;
        *(uint64_t *)(regen_props[k]+0x20)=regen_full(k);
        *(uint64_t *)(regen_props[k]+0x50)=(uint64_t)(uintptr_t)owners[0];
        *(uint64_t *)(regen_props[k]+0x78)=(uint64_t)(k==1?2:1)<<32;
        *(float *)(regen_props[k]+0xd4)=k==1?2.5f:1.25f;
    }
    for(unsigned n=0;n<2;++n) {
        regen_lists[n][0]=(uint64_t)(uintptr_t)regen_props[0];
        regen_lists[n][1]=(uint64_t)(uintptr_t)regen_props[1];
        *(uint64_t *)(owners[0]+0xa0+n*0x10)=(uint64_t)(uintptr_t)regen_lists[n];
        *(uint64_t *)(owners[0]+0xa8+n*0x10)=64;
    }
    if(regen_scenario==1) regen_lists[0][0]=regen_lists[1][0]=0;
    if(regen_scenario==2) regen_lists[0][1]=regen_lists[1][1]=0;
    if(regen_scenario==3) *(uint64_t *)(owners[0]+0xa8)=0x408;
    if(regen_scenario==4) *(uint64_t *)(owners[0]+0xa8)=7;
    if(regen_scenario==5) *(uint64_t *)(owners[0]+0xa0)=1;
    if(regen_scenario==6) *(uint64_t *)(regen_props[0]+0x50)=0;
    if(regen_scenario==7) *(uint64_t *)(regen_props[0]+0x20)=123;
    if(regen_scenario==8) regen_lists[1][2]=(uint64_t)(uintptr_t)regen_props[2];
    if(regen_scenario==9) regen_lists[0][0]=1;
    if(regen_scenario==10) *(uint64_t *)(objects[0]+0x18)+=1;
    if(regen_scenario==13) {
        DWORD old;
        regen_readonly=VirtualAlloc(NULL,0x1000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
        if(!regen_readonly) RaiseException(0xe0000001,0,0,NULL);
        memcpy(regen_readonly,regen_props[0],0xe8);
        if(!VirtualProtect(regen_readonly,0x1000,PAGE_READONLY,&old)) RaiseException(0xe0000001,0,0,NULL);
        regen_lists[0][0]=regen_lists[1][0]=(uint64_t)(uintptr_t)regen_readonly;
    }
    g_persistent_agent_resolver=(uint64_t)(uintptr_t)regen_agent;
}
__declspec(dllexport) unsigned read_regen(unsigned scenario,uint64_t *out,unsigned *length) {
    unsigned counts[1]={0},units;
    regen_scenario=scenario;
    return collect(1,counts,UINT32_MAX,0,out,154,length,&units);
}
__declspec(dllexport) unsigned write_regen(const wchar_t *directory,unsigned scenario,unsigned mask,
                                         unsigned hp,unsigned mp,unsigned *after) {
    uint64_t baseline[154];unsigned length;DWORD error=read_regen(0,baseline,&length),bytes;
    NativeCommand cmd={0};wchar_t path[MAX_PATH];HANDLE file;
    if(error) return error;
    if(wcslen(directory)>=MAX_PATH-1) return ERROR_INVALID_PARAMETER;
    wcscpy(regen_directory,directory);
    regen_scenario=scenario;prepare_regen();
    cmd.magic=WAR3_NATIVE_MAGIC;cmd.version=WAR3_NATIVE_VERSION;cmd.status=WAR3_NATIVE_STATUS_PENDING;
    cmd.unit_handle=1;cmd.op_count=2;
    cmd.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;
    cmd.ops[0].handler=(uint64_t)(uintptr_t)objects[0];cmd.ops[0].arg0=0x100000001ULL;
    cmd.ops[0].arg1=(uint64_t)(uintptr_t)owners[0];
    cmd.ops[1].kind=WAR3_NATIVE_OP_SET_UNIT_REGEN;cmd.ops[1].rawcode=mask;
    cmd.ops[1].arg0=hp;cmd.ops[1].arg1=mp;
    command_path(path,MAX_PATH);
    file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();
    BOOL ok=WriteFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);
    if(!ok || bytes!=sizeof(cmd)) return ERROR_WRITE_FAULT;
    run_command();
    after[0]=*(uint32_t *)(regen_props[0]+0xd4);after[1]=*(uint32_t *)(regen_props[1]+0xd4);
    if(regen_readonly) { VirtualFree(regen_readonly,0,MEM_RELEASE);regen_readonly=NULL; }
    return 0;
}
'''


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler: pytest.skip('clang required')
    root=tmp_path_factory.mktemp('regen');source=root/'test.c';library=root/'test.dll'
    harness=HARNESS.replace('#include "HELPER_SOURCE"',TEMP_PATH+'\n#include "HELPER_SOURCE"')
    harness=harness.replace('__declspec(dllexport) unsigned collect(',
        'static unsigned regen_scenario; static void prepare_regen(void);\n__declspec(dllexport) unsigned collect(')
    harness=harness.replace('error = war3_persistent_selected_snapshot(',
        'prepare_regen();\n    error = war3_persistent_selected_snapshot(')
    source.write_text(harness.replace('HELPER_SOURCE',(Path(__file__).parent/'analysis/fixtures/legacy-native-helper.c').as_posix())+REGEN,encoding='utf8')
    subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(library),
                    '-luser32','-lkernel32'],check=True,capture_output=True,timeout=60)
    lib=ctypes.CDLL(str(library))
    lib.read_regen.argtypes=[ctypes.c_uint,ctypes.POINTER(ctypes.c_uint64),ctypes.POINTER(ctypes.c_uint)]
    lib.read_regen.restype=ctypes.c_uint
    lib.write_regen.argtypes=[ctypes.c_wchar_p,*([ctypes.c_uint]*4),ctypes.POINTER(ctypes.c_uint)]
    lib.write_regen.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)


@pytest.mark.parametrize('scenario',range(13))
def test_regeneration_in_production_unit_snapshot(native,scenario):
    out=(ctypes.c_uint64*154)();length=ctypes.c_uint()
    error=native.read_regen(scenario,out,ctypes.byref(length))
    if scenario>2:
        assert error and length.value==0
        return
    assert not error and length.value==154
    trainer=module.War3Trainer.__new__(module.War3Trainer)
    result=module.NativeHelperOpResult(130,1,extra_results=tuple(out))
    snapshot=trainer._parse_persistent_native_snapshots(result)[0]
    assert snapshot.hp_regen==(None if scenario==1 else 1.25)
    assert snapshot.mp_regen==(None if scenario==2 else 2.5)
    memory=Mock();candidate=trainer._candidate_from_native_snapshot(memory,snapshot)
    assert candidate.hp_regen_address==(snapshot.hp_property+0xd4 if snapshot.hp_property else 0)
    assert memory.mock_calls==[]


@pytest.mark.parametrize('scenario,mask,hp,mp', [(n,3,5.5,-2.0) for n in range(14)]+
    [(0,1,0.0,9.0),(0,2,9.0,0.0),(0,0,1.0,2.0),(0,4,1.0,2.0),
     (0,3,float('nan'),2.0),(0,3,1.0,float('inf'))])
def test_guarded_regeneration_write_validates_both_fields_before_any_change(native,tmp_path,scenario,mask,hp,mp):
    bits=module.War3Trainer._float_bits
    after=(ctypes.c_uint*2)()
    assert native.write_regen(str(tmp_path)+'\\',scenario,mask,bits(hp),bits(mp),after)==0
    trainer=module.War3Trainer.__new__(module.War3Trainer)
    payload=(tmp_path/f'war3_reforged_native_{os.getpid()}.bin').read_bytes()
    if scenario or mask not in (1,2,3) or not all(math.isfinite(v) for v in (hp,mp)):
        with pytest.raises(RuntimeError): trainer._parse_native_helper_results(payload,2)
        assert tuple(after)==(bits(1.25),bits(2.5))
    else:
        results=trainer._parse_native_helper_results(payload,2)
        assert results[1].result==mask
        assert tuple(after)==(bits(hp if mask&1 else 1.25),bits(mp if mask&2 else 2.5))


def test_python_regeneration_uses_one_guarded_batch_and_native_readback(context):
    trainer,memory,_,snapshot=context
    snapshot=replace(snapshot,hp_property=0x6000,mp_property=0x7000,hp_regen=1.25,mp_regen=2.5)
    candidate=make_candidate(snapshot)
    fresh=replace(snapshot,hp_regen=5.5,mp_regen=-2.0)
    trainer._run_native_helper_ops.side_effect=[[snapshot_result(snapshot)],[],[snapshot_result(fresh)]]
    result=trainer._write_basic_unit_values_to_candidate(memory,candidate,None,None,target_hp_regen=5.5,target_mp_regen=-2.0)
    assert (result.native_snapshot.hp_regen,result.native_snapshot.mp_regen)==(5.5,-2.0)
    assert trainer._run_native_helper_ops.call_args_list[1].args==(snapshot.handle,(
        (136,0,candidate.unit_address,candidate.handle,candidate.owner_address),
        (148,3,0,trainer._float_bits(5.5),trainer._float_bits(-2.0))))
    assert memory.mock_calls==[]
    trainer._elephant_handlers.assert_not_called()


def test_refresh_replaces_property_metadata_without_external_mapping(context):
    trainer,memory,_,snapshot=context
    old=replace(snapshot,hp_property=0x6000,hp_regen=1.0)
    fresh=replace(snapshot,hp_property=0x9000,hp_regen=2.0)
    candidate=trainer._candidate_from_native_snapshot(memory,old)
    trainer._run_native_helper_ops.return_value=[snapshot_result(fresh)]
    updated=trainer._refresh_native_candidate(candidate)
    assert updated.hp_regen_address==0x90d4
    assert updated.native_snapshot.hp_regen==2.0
    assert candidate.hp_regen_address==0x60d4
    assert memory.mock_calls==[]


def test_field_editor_routes_regeneration_without_any_external_address_write(context):
    trainer,memory,_,snapshot=context
    snapshot=replace(snapshot,hp_property=0x6000,mp_property=0x7000,hp_regen=1.25,mp_regen=2.5)
    candidate=make_candidate(snapshot)
    trainer._native_unit_field_memory=Mock(return_value=module.NativeUnitFieldMemory(candidate,
        (candidate.unit_address,candidate.handle,candidate.owner_address)+(0,)*290))
    trainer._selected_components=Mock(side_effect=AssertionError('external components'))
    fresh=replace(snapshot,hp_regen=7.5,mp_regen=0.0)
    trainer._run_native_helper_ops.side_effect=[[snapshot_result(snapshot)],[],[snapshot_result(fresh)]]
    fields=trainer._write_unit_fields_to_candidate(memory,candidate,[
        module.MemoryWriteSpec('hp_regen',0,'f32',7.5),module.MemoryWriteSpec('mp_regen',0,'f32',0.0)])
    assert [field.value for field in fields]==[7.5,0.0]
    assert all(field.native_write and field.write_address==0 for field in fields)
    assert memory.mock_calls==[]
    assert trainer._run_native_helper_ops.call_args_list[1].args[1][-1][0]==148
