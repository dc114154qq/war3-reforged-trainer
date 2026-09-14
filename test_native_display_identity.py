"""Full identity -> native snapshot, without selection/cache/heap lookup."""
import ctypes
from contextlib import nullcontext
from dataclasses import replace
import faulthandler
import os
from pathlib import Path
import shutil
import subprocess
from unittest.mock import Mock

import pytest
import war3_reforged_trainer as module
from test_native_identity_guard import HARNESS
from test_native_snapshot_binding import make_snapshot, snapshot_result


IDENTITY_HARNESS=r'''
static unsigned identity_fault,identity_converts,identity_reads,identity_selections;
static uint64_t identity_zero(void) {return 0;}
static uint64_t identity_select(void) {++identity_selections;return 0;}
static uint32_t identity_type(uint64_t unit) {
    ++identity_reads;if(unit!=7) ++bad_arguments;
    if(identity_fault==14) *(uint64_t *)(object+0x18)+=1;
    return 0x68666f6fu;
}
static uint64_t identity_owner(uint64_t unit) {return 2;}
static uint64_t identity_convert(uint64_t unit,uint8_t create) {
    ++identity_converts;
    if(unit!=(uint64_t)(uintptr_t)object || create!=1 ||
       *(uint64_t *)(object+0x18)!=full || *(uint64_t *)(owner+0x20)!=full) ++bad_arguments;
    if(identity_fault==9) return 0;
    if(identity_fault==10) return 99;
    if(identity_fault==11) *(uint64_t *)(object+0x18)+=1;
    if(identity_fault==12) *(uint64_t *)(owner+0x90)=0;
    if(identity_fault==13) RaiseException(0xe0000001,0,0,NULL);
    return 7;
}
__declspec(dllexport) DWORD identity_test(const wchar_t *directory,unsigned failure,unsigned *out) {
    NativeCommand cmd={0};DWORD bytes;HANDLE file;wchar_t path[MAX_PATH];
    uint8_t *code=VirtualAlloc(NULL,8192,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);
    if(!code) return GetLastError();
    memcpy(code,war3_first_group_code,sizeof(war3_first_group_code));
    *(int32_t *)(code+40)=128-44;
    code[128]=0xff;code[129]=0x25; /* RIP-relative indirect tail jump to the fixture callback */
    *(uint64_t *)(code+134)=(uint64_t)(uintptr_t)identity_convert;
    FlushInstructionCache(GetCurrentProcess(),code,4096);
    wcscpy(test_directory,directory);command_path(path,MAX_PATH);DeleteFileW(path);
    identity_fault=failure;identity_converts=identity_reads=identity_selections=bad_arguments=fault=0;
    ZeroMemory(object,sizeof(object));ZeroMemory(owner,sizeof(owner));
    *(uint64_t *)(object+0x18)=full;
    *(uint64_t *)(owner+0x18)=0x2b7733752b61676cULL;
    *(uint64_t *)(owner+0x20)=full;*(uint64_t *)(owner+0x90)=(uint64_t)(uintptr_t)object;
    g_persistent_unit_resolver=(uint64_t)(uintptr_t)fake_unit;
    g_persistent_agent_resolver=(uint64_t)(uintptr_t)fake_agent;
    for(unsigned n=0;n<sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]);++n) {
        const char *name=g_persistent_native_names[n];
        g_persistent_natives[n].name=name;g_persistent_natives[n].handler=(uint64_t)(uintptr_t)identity_zero;
        if(!strcmp(name,"FirstOfGroup")) g_persistent_natives[n].handler=failure==7?0:(uint64_t)(uintptr_t)code;
        if(!strcmp(name,"GetUnitTypeId")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)identity_type;
        if(!strcmp(name,"GetOwningPlayer")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)identity_owner;
        if(!strcmp(name,"CreateGroup")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)identity_select;
    }
    cmd.magic=WAR3_NATIVE_MAGIC;cmd.version=WAR3_NATIVE_VERSION;cmd.status=WAR3_NATIVE_STATUS_PENDING;
    cmd.op_count=1;cmd.ops[0].kind=WAR3_NATIVE_OP_IDENTITY_UNIT_SNAPSHOT;
    cmd.ops[0].handler=(uint64_t)(uintptr_t)object;cmd.ops[0].arg0=full;
    cmd.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    if(failure==1) cmd.ops[0].arg0+=1ULL<<32;
    if(failure==2) cmd.ops[0].arg1=(uint64_t)(uintptr_t)other;
    if(failure==3) *(uint64_t *)(owner+0x18)=0;
    if(failure==4) *(uint64_t *)(owner+0x90)=0;
    if(failure==5) cmd.ops[0].handler=*(uint64_t *)(owner+0x90)=1;
    if(failure==6) code[30]=0x90;
    if(failure==8) {
        /* Valid FirstOfGroup signature with a non-executable conversion target. */
        *(int32_t *)(code+40)=4096-44;
        DWORD old;VirtualProtect(code+4096,4096,PAGE_READWRITE,&old);
    }
    if(failure==15) cmd.unit_handle=7; /* caller must not supply an unverified JASS id */
    file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_ALWAYS,0,NULL);
    if(file==INVALID_HANDLE_VALUE) {VirtualFree(code,0,MEM_RELEASE);return GetLastError();}
    BOOL ok=WriteFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);
    if(!ok || bytes!=sizeof(cmd)) {VirtualFree(code,0,MEM_RELEASE);return ERROR_WRITE_FAULT;}
    run_command();out[0]=identity_converts;out[1]=identity_reads;out[2]=identity_selections;out[3]=bad_arguments;
    VirtualFree(code,0,MEM_RELEASE);return 0;
}
'''


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler:pytest.skip('clang required')
    root=tmp_path_factory.mktemp('display_identity');source=root/'test.c';library=root/'test.dll'
    source.write_text(HARNESS.replace('static uint8_t object[0x20]','static uint8_t object[0x600]')
                      .replace('HELPER_SOURCE',(Path(__file__).parent/'analysis/fixtures/legacy-native-helper.c').as_posix())
                      +IDENTITY_HARNESS,encoding='utf8')
    subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(library),
                    '-luser32','-lkernel32'],check=True,capture_output=True,timeout=60)
    lib=ctypes.CDLL(str(library));lib.identity_test.argtypes=[ctypes.c_wchar_p,ctypes.c_uint,ctypes.POINTER(ctypes.c_uint)]
    lib.identity_test.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)


@pytest.mark.parametrize('failure',range(16))
def test_native_identity_conversion_precedes_field_calls_and_never_selects(native,tmp_path,failure):
    out=(ctypes.c_uint*4)();enabled=faulthandler.is_enabled()
    if failure==13 and enabled:faulthandler.disable()
    try:assert native.identity_test(str(tmp_path)+'\\',failure,out)==0
    finally:
        if failure==13 and enabled:faulthandler.enable()
    assert out[2:4]==[0,0]
    assert out[0]==(failure in (0,9,10,11,12,13,14))
    assert bool(out[1])==(failure in (0,14))
    payload=(tmp_path/f'war3_reforged_native_{os.getpid()}.bin').read_bytes()
    trainer=module.War3Trainer.__new__(module.War3Trainer)
    if failure:
        with pytest.raises(RuntimeError):trainer._parse_native_helper_results(payload,1)
        assert len(payload)==trainer._native_helper_command_size()
    else:
        result=trainer._parse_native_helper_results(payload,1)[0]
        snapshot=trainer._parse_persistent_native_snapshots(result)[0]
        assert snapshot.handle==7 and snapshot.full_handle==0x123400005678
        assert snapshot.type_id==0x68666f6f and result.kind==155


def test_display_identity_resolves_without_recent_selection_and_rejects_reuse():
    trainer=module.War3Trainer.__new__(module.War3Trainer);snapshot=make_snapshot();pm=Mock()
    trainer.persistent_native_init=Mock();trainer._last_persistent_native_snapshots=()
    trainer._candidate_from_identity=Mock(side_effect=AssertionError('external identity lookup'))
    trainer._run_native_helper_ops=Mock(return_value=[replace(snapshot_result(snapshot),kind=155)])
    identity=(snapshot.full_handle,snapshot.owner_address,snapshot.unit_address)
    candidate=trainer._candidate_from_display_identity(pm,*identity,'remembered',860)
    assert candidate.native_snapshot==snapshot and candidate.note=='remembered'
    trainer._run_native_helper_ops.assert_called_once_with(0,((155,0,identity[2],identity[0],identity[1]),))
    assert pm.mock_calls==[] and trainer._last_persistent_native_snapshots==()
    trainer._run_native_helper_ops.return_value=[snapshot_result(replace(snapshot,full_handle=snapshot.full_handle+1))]
    with pytest.raises(RuntimeError,match='does not match'):
        trainer._candidate_from_display_identity(pm,*identity,'remembered')


@pytest.mark.parametrize('compat',[False,True])
def test_identity_field_read_routes_share_native_binding_without_extra_snapshot(compat):
    trainer=module.War3Trainer.__new__(module.War3Trainer);snapshot=make_snapshot();pm=Mock()
    trainer._process_memory=Mock(return_value=nullcontext(pm));trainer.persistent_native_init=Mock()
    trainer._run_native_helper_ops=Mock(return_value=[replace(snapshot_result(snapshot),kind=155)])
    trainer._unit_fields_from_candidate=Mock(return_value=[])
    trainer._candidate_from_identity=Mock(side_effect=AssertionError('legacy scan'))
    trainer._win10_session_for_identity=Mock(side_effect=AssertionError('backup session'))
    fn=trainer.read_unit_fields_by_identity_win10 if compat else trainer.read_unit_fields_by_identity
    panel,candidate,fields=fn(snapshot.full_handle,snapshot.owner_address,snapshot.unit_address)
    assert candidate.native_snapshot==snapshot and fields==[] and trainer._run_native_helper_ops.call_count==1
    assert pm.mock_calls==[]


def test_identity_summary_uses_native_components_even_for_nonhero_empty_inventory():
    trainer=module.War3Trainer.__new__(module.War3Trainer);snapshot=replace(make_snapshot(),hero_level=0,move_speed=0)
    pm=Mock();trainer._process_memory=Mock(return_value=nullcontext(pm));trainer.persistent_native_init=Mock()
    trainer._run_native_helper_ops=Mock(return_value=[replace(snapshot_result(snapshot),kind=155)])
    trainer._native_unit_field_memory=Mock(return_value=Mock(components={'inventory':(123,456)},inventory_items=[]))
    summary=trainer.selection_summary_from_identity(snapshot.full_handle,snapshot.owner_address,snapshot.unit_address)
    assert summary.components==('inventory',) and not summary.hero and summary.inventory==()
    assert summary.ability_count==1 and summary.hp_text=='100/200' and pm.mock_calls==[]
