"""Run the production skill transaction against an isolated C engine fixture."""
import ctypes
from dataclasses import replace
import faulthandler
import os
from pathlib import Path
import shutil
import subprocess
from unittest.mock import Mock, patch

import pytest
import war3_reforged_trainer as module
from test_native_identity_guard import HARNESS
from test_native_unit_field_dispatch import FIELDS_HARNESS
from test_native_snapshot_binding import make_candidate, make_snapshot


SKILL_HARNESS = r'''
static uint8_t skill_data[2][0x100],skill_wrappers[2][0x98];
static unsigned skill_present[2],skill_fault,skill_adds,skill_removes[2],skill_index,skill_triggered;
static int32_t skill_levels[2];
static const uint32_t skill_ids[2]={0x41303031u,0x41303039u};
static uint64_t skill_full(unsigned n) {return 0x998800001234ULL+n;}
static uint64_t skill_agent(uint32_t slot,uint32_t serial) {
    uint64_t id=((uint64_t)serial<<32)|slot;
    if(skill_fault>=30 && skill_fault<=32 && !skill_triggered &&
       *(uint32_t *)(field_data[1]+0x204)==0x41303039u && skill_present[0]) {
        skill_triggered=1;
        if(skill_fault==30) *(uint64_t *)(skill_data[0]+0x18)+=1;
        if(skill_fault==31) *(uint64_t *)(skill_data[1]+0x18)+=1;
        if(skill_fault==32) RaiseException(0xe0000001,0,0,NULL);
    }
    for(unsigned n=0;n<2;++n) if(id==skill_full(n)) return (uint64_t)(uintptr_t)skill_wrappers[n];
    return field_agent(slot,serial);
}
static void skill_check(uint64_t unit) {
    if(unit!=7 || *(uint64_t *)(object+0x18)!=full ||
       *(uint64_t *)(field_data[1]+0x18)!=field_full(1)) ++bad_arguments;
}
static uint64_t skill_lookup(uint64_t unit,uint32_t id) {
    if(unit!=7) ++bad_arguments;
    for(unsigned n=0;n<2;++n) if(id==skill_ids[n] && skill_present[n]) return 100+n;
    return 0;
}
static uint64_t skill_resolve(uint64_t id) {
    if(skill_fault==20 && id==101) return 1;
    return id>=100 && id<=101 && skill_present[id-100]?(uint64_t)(uintptr_t)skill_data[id-100]:0;
}
static uint32_t skill_id(uint64_t id) {return id>=100 && id<=101?skill_ids[id-100]:0;}
static int32_t skill_level(uint64_t unit,uint32_t id) {
    for(unsigned n=0;n<2;++n) if(id==skill_ids[n]) return skill_present[n]?skill_levels[n]:0;
    return 0;
}
static uint32_t skill_add(uint64_t unit,uint32_t id) {
    skill_check(unit);++skill_adds;
    if(id!=skill_ids[1] || skill_present[1]) ++bad_arguments;
    if(skill_fault==5 || skill_fault==36) return 0; /* map resource missing */
    if(skill_fault==28) RaiseException(0xe0000001,0,0,NULL);
    skill_present[1]=1;skill_levels[1]=1;
    if(skill_fault==29) RaiseException(0xe0000001,0,0,NULL);
    if(skill_fault==7) *(uint64_t *)(object+0x18)+=1;
    if(skill_fault==8) *(uint64_t *)(field_data[1]+0x18)+=1;
    if(skill_fault==11) *(uint32_t *)(field_data[1]+0x204+skill_index*4)=0x41303939u;
    if(skill_fault==21) *(uint64_t *)(skill_wrappers[1]+0x50)=0;
    if(skill_fault==34) *(uint64_t *)(skill_wrappers[1]+0x18)=0x414865722b61676cULL;
    if(skill_fault==35) *(uint64_t *)(skill_wrappers[1]+0x18)=0x2b61676cULL;
    return skill_fault==6?0:1;
}
static uint32_t skill_set(uint64_t unit,uint32_t id,int32_t value) {
    skill_check(unit);
    if(id!=skill_ids[1]) ++bad_arguments;
    if(skill_fault==13) return 0;
    skill_levels[1]=skill_fault==12?1:value;
    if(skill_fault==9) *(uint64_t *)(skill_data[1]+0x18)+=1;
    if(skill_fault==10) *(uint64_t *)(skill_data[0]+0x18)+=1;
    if(skill_fault==26) skill_levels[1]=0;
    return skill_levels[1];
}
static uint32_t skill_remove(uint64_t unit,uint32_t id) {
    unsigned n=id==skill_ids[1]?1:0;
    skill_check(unit);++skill_removes[n];
    if(id!=skill_ids[n] || !skill_present[n] || *(uint64_t *)(skill_data[n]+0x18)!=skill_full(n)) ++bad_arguments;
    if(n==0 && (skill_fault==14 || skill_fault==18 || skill_fault==33)) {
        if(skill_fault==33) ++skill_levels[1];
        return 0;
    }
    if(n==0 && skill_fault==16) RaiseException(0xe0000001,0,0,NULL);
    if(n==1 && skill_fault==18) return 0;
    skill_present[n]=0;
    if(n==0 && skill_fault==17) RaiseException(0xe0000001,0,0,NULL);
    return (n==0 && skill_fault==15) || (n==1 && skill_fault==37)?0:1;
}
__declspec(dllexport) DWORD skill_test(const wchar_t *directory,unsigned failure,int32_t *out) {
    DWORD error=field_snapshot(directory,15,0),bytes;HANDLE file;wchar_t path[MAX_PATH];NativeCommand cmd={0};
    if(error) return error;
    command_path(path,MAX_PATH);DeleteFileW(path);
    skill_fault=failure;skill_adds=skill_removes[0]=skill_removes[1]=bad_arguments=0;
    skill_index=failure==23?4:0;field_fault=0;skill_triggered=0;
    skill_present[0]=failure!=1 && failure!=36 && failure!=37;
    skill_present[1]=failure==4;skill_levels[0]=3;skill_levels[1]=1;
    ZeroMemory(skill_data,sizeof(skill_data));ZeroMemory(skill_wrappers,sizeof(skill_wrappers));
    for(unsigned n=0;n<2;++n) {
        uint8_t *data=skill_data[n],*wrapper=skill_wrappers[n];
        *(uint64_t *)(data+0x18)=*(uint64_t *)(wrapper+0x20)=skill_full(n);
        *(uint64_t *)(data+0x68)=(uint64_t)(uintptr_t)object;
        *(uint32_t *)(data+0x70)=*(uint32_t *)(data+0x78)=skill_ids[n];
        *(uint64_t *)(wrapper+0x18)=((uint64_t)skill_ids[n]<<32)|0x2b61676cULL;
        *(uint64_t *)(wrapper+0x50)=(uint64_t)(uintptr_t)owner;
        *(uint64_t *)(wrapper+0x90)=(uint64_t)(uintptr_t)data;
    }
    for(unsigned n=0;n<5;++n) {
        *(uint32_t *)(field_data[1]+0x204+n*4)=0x41303032u+n;
        *(uint32_t *)(field_data[1]+0x1bc+n*4)=0x42303032u+n;
    }
    *(uint32_t *)(field_data[1]+0x204+skill_index*4)=skill_ids[0];
    *(uint32_t *)(field_data[1]+0x1bc+skill_index*4)=0x42303031u;
    if(failure==2) *(uint64_t *)(object+0x5a8)=0;
    if(failure==3) *(uint32_t *)(field_data[1]+0x208)=skill_ids[1];
    if(failure==19) *(uint64_t *)(skill_wrappers[0]+0x50)=0;
    if(failure==25) *(uint32_t *)(field_data[1]+0x204)=0x41303939u;
    g_persistent_agent_resolver=(uint64_t)(uintptr_t)skill_agent;
    g_persistent_ability_resolver=(uint64_t)(uintptr_t)skill_resolve;
    for(unsigned n=0;n<sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]);++n) {
        const char *name=g_persistent_native_names[n];
        if(!strcmp(name,"BlzGetUnitAbility")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)skill_lookup;
        if(!strcmp(name,"BlzGetAbilityId")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)skill_id;
        if(!strcmp(name,"GetUnitAbilityLevel")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)skill_level;
        if(!strcmp(name,"UnitAddAbility")) g_persistent_natives[n].handler=failure==22?0:(uint64_t)(uintptr_t)skill_add;
        if(!strcmp(name,"SetUnitAbilityLevel")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)skill_set;
        if(!strcmp(name,"UnitRemoveAbility")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)skill_remove;
    }
    cmd.magic=WAR3_NATIVE_MAGIC;cmd.version=WAR3_NATIVE_VERSION;cmd.status=WAR3_NATIVE_STATUS_PENDING;
    cmd.op_count=2;cmd.unit_handle=7;
    cmd.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;
    cmd.ops[0].handler=(uint64_t)(uintptr_t)object;cmd.ops[0].arg0=full;cmd.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    cmd.ops[1].kind=WAR3_NATIVE_OP_REPLACE_HERO_SKILL;
    cmd.ops[1].rawcode=skill_ids[failure==24?0:1];
    cmd.ops[1].handler=(uint64_t)(uintptr_t)field_data[1];cmd.ops[1].arg0=field_full(1);
    cmd.ops[1].arg1=((uint64_t)(failure==27?5:skill_index)<<32)|skill_ids[0];
    file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_ALWAYS,0,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();
    BOOL ok=WriteFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);
    if(!ok || bytes!=sizeof(cmd)) return ERROR_WRITE_FAULT;
    run_command();
    out[0]=skill_present[0];out[1]=skill_present[1];out[2]=*(uint32_t *)(field_data[1]+0x204+skill_index*4);
    out[3]=*(uint32_t *)(field_data[1]+0x1bc+skill_index*4);out[4]=skill_adds;
    out[5]=skill_removes[0];out[6]=skill_removes[1];out[7]=skill_levels[1];out[8]=bad_arguments;
    return 0;
}
'''


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler:pytest.skip('clang required')
    root=tmp_path_factory.mktemp('hero_skill');source=root/'test.c';library=root/'test.dll'
    harness=HARNESS.replace('static uint8_t object[0x20]','static uint8_t object[0x600]')
    source.write_text(harness.replace('HELPER_SOURCE',(Path(__file__).parent/'analysis/fixtures/legacy-native-helper.c').as_posix())
                      +FIELDS_HARNESS+SKILL_HARNESS,encoding='utf8')
    subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(library),
                    '-luser32','-lkernel32'],check=True,capture_output=True,timeout=60)
    lib=ctypes.CDLL(str(library))
    lib.skill_test.argtypes=[ctypes.c_wchar_p,ctypes.c_uint,ctypes.POINTER(ctypes.c_int32)]
    lib.skill_test.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)


@pytest.mark.parametrize('failure',range(38))
def test_resource_creation_commit_rollback_and_recycled_targets(native,tmp_path,failure):
    out=(ctypes.c_int32*9)();enabled=faulthandler.is_enabled()
    if failure in (16,17,28,29,32) and enabled:faulthandler.disable()
    try:assert native.skill_test(str(tmp_path)+'\\',failure,out)==0
    finally:
        if failure in (16,17,28,29,32) and enabled:faulthandler.enable()
    assert out[8]==0, ('unsafe engine call',list(out))
    payload=(tmp_path/f'war3_reforged_native_{os.getpid()}.bin').read_bytes()
    trainer=module.War3Trainer.__new__(module.War3Trainer)
    if failure in (0,1,12,23,24):
        result=trainer._parse_native_helper_results(payload,2)[1]
        assert result.result==(0x41303031 if failure==24 else 0x41303039)
        assert result.arg1==(0 if failure==1 else 1 if failure==12 else 3)
        assert out[0]==(failure==24) and out[1]==(failure not in (1,24))
        assert out[4]==(failure!=24)
        assert out[2]==result.result
    else:
        with pytest.raises(RuntimeError,match='skill_phase=.*skill_cleanup_error='):
            trainer._parse_native_helper_results(payload,2)
        assert out[0]==(failure not in (15,17,36,37)), list(out)
        if failure in (13,14,16,26,32,36,37):
            assert out[1]==0 and out[2:4]==[0x41303031,0x42303031]
        if failure in (15,17):
            assert out[1]==1 and out[2:4]==[0x41303039]*2 # old is gone; retain replacement
        if failure in (2,3,4,19,22,25,27):assert out[4]==0
        if failure in (7,8,9,10,11,20,21,29,30,31,34,35):assert out[5:7]==[0,0]
        if failure==11:assert out[2]==0x41303939 # never overwrite map trigger's slot
        if failure in (6,7,8,9,10,11,15,17,18,20,21,28,29,30,31,33,34,35):
            op=module.War3Trainer.NATIVE_HELPER_OP_STRUCT.unpack_from(payload,32+48)
            assert op[7]!=0, ('cleanup must report an incomplete recovery',failure)


def test_editor_uses_one_callback_without_external_reads_writes_or_wait():
    trainer=module.War3Trainer.__new__(module.War3Trainer);candidate=make_candidate(make_snapshot());memory=Mock()
    field=module.UnitMemoryField('skill1_name','skill','rawcode',0x41303031,0,'skill',native_write=True,
                                 native_component_identity=(0x5000,0x6000))
    trainer._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(154,0x41303039,arg1=3)])
    trainer._unit_fields_from_candidate=Mock(return_value=[field])
    trainer._selected_components=Mock(side_effect=AssertionError('external components'))
    with patch.object(module.time,'sleep',side_effect=AssertionError('fixed wait')):
        result=trainer._write_unit_fields_to_candidate(memory,candidate,[module.MemoryWriteSpec('skill1_name',0,'',0x41303039)])[0]
    assert result.value==0x41303039 and result.native_write and result.write_address==0 and not result.extra_writes
    trainer._run_native_helper_ops.assert_called_once_with(candidate.native_snapshot.handle,(
        (136,0,candidate.unit_address,candidate.handle,candidate.owner_address),(154,0x41303039,0x5000,0x6000,0x41303031)))
    assert memory.mock_calls==[]


def test_missing_component_identity_cannot_use_legacy_writer():
    trainer=module.War3Trainer.__new__(module.War3Trainer);candidate=make_candidate(make_snapshot())
    field=module.UnitMemoryField('skill1_name','skill','rawcode',0x41303031,0,'skill')
    memory=Mock();trainer._run_native_helper_ops=Mock()
    with pytest.raises(RuntimeError,match='组件身份'):
        trainer._write_hero_skill_name_field(memory,candidate,field,0x41303039)
    trainer._run_native_helper_ops.assert_not_called();assert memory.mock_calls==[]
