"""Real C intelligence setter preserves bonuses and guards each engine callback."""
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


INT_HARNESS=r'''
static int32_t int_base,int_bonus;
static unsigned int_fault,int_sets,int_gets;
static int32_t int_level(uint64_t unit) { if(unit!=7) ++bad_arguments;return int_fault==1?0:5; }
static int32_t int_get(uint64_t unit,uint32_t bonus) {
    if(unit!=7 || bonus>1) ++bad_arguments;
    ++int_gets;
    if(int_fault==3) *(uint64_t *)(object+0x18)+=1;
    return bonus?(int32_t)((int64_t)int_base+int_bonus):int_base;
}
static void int_set(uint64_t unit,int32_t value,uint32_t permanent) {
    if(unit!=7 || permanent!=1 || *(uint64_t *)(object+0x18)!=full) ++bad_arguments;
    ++int_sets;int_base=value;
    if(int_fault==4) *(uint64_t *)(object+0x18)+=1;
    if(int_fault==5) *(uint64_t *)(field_data[1]+0x18)+=1;
    if(int_fault==6) *(uint64_t *)(object+0x5a8)=0;
    if(int_fault==7 && int_sets==1) ++int_bonus;
    if(int_fault==8) ++int_bonus;
    if(int_fault==9) RaiseException(0xe0000001,0,0,NULL);
}
__declspec(dllexport) DWORD intelligence_test(const wchar_t *directory,unsigned failure,int32_t base,
                                              int32_t bonus,unsigned target,int32_t *out) {
    DWORD error=field_snapshot(directory,15,0),bytes;HANDLE file;wchar_t path[MAX_PATH];NativeCommand cmd={0};
    if(error) return error;
    command_path(path,MAX_PATH);DeleteFileW(path);
    int_fault=failure;int_base=base;int_bonus=bonus;int_sets=int_gets=bad_arguments=0;field_fault=0;
    for(unsigned n=0;n<sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]);++n) {
        const char *name=g_persistent_native_names[n];
        if(!strcmp(name,"GetHeroInt")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)int_get;
        if(!strcmp(name,"SetHeroInt")) g_persistent_natives[n].handler=failure==2?0:(uint64_t)(uintptr_t)int_set;
        if(!strcmp(name,"GetHeroLevel")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)int_level;
    }
    cmd.magic=WAR3_NATIVE_MAGIC;cmd.version=WAR3_NATIVE_VERSION;cmd.status=WAR3_NATIVE_STATUS_PENDING;
    cmd.op_count=2;cmd.unit_handle=7;
    cmd.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;
    cmd.ops[0].handler=(uint64_t)(uintptr_t)object;cmd.ops[0].arg0=full;cmd.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    cmd.ops[1].kind=WAR3_NATIVE_OP_SET_BOUND_HERO_INT;cmd.ops[1].rawcode=target;
    cmd.ops[1].handler=(uint64_t)(uintptr_t)field_data[1];cmd.ops[1].arg0=*(uint64_t *)(field_data[1]+0x18);
    if(failure==10) ++cmd.ops[1].arg0;
    if(failure==11) *(uint64_t *)(field_wrappers[1]+0x50)=0;
    file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();
    BOOL ok=WriteFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);
    if(!ok || bytes!=sizeof(cmd)) return ERROR_WRITE_FAULT;
    run_command();out[0]=int_sets;out[1]=int_gets;out[2]=int_base;out[3]=int_bonus;out[4]=bad_arguments;
    return 0;
}
'''


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler:pytest.skip('clang required')
    root=tmp_path_factory.mktemp('intelligence');source=root/'test.c';library=root/'test.dll'
    harness=HARNESS.replace('static uint8_t object[0x20]','static uint8_t object[0x600]')
    source.write_text(harness.replace('HELPER_SOURCE',(Path(__file__).parent/'analysis/fixtures/legacy-native-helper.c').as_posix())
                      +FIELDS_HARNESS+INT_HARNESS,encoding='utf8')
    subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(library),
                    '-luser32','-lkernel32'],check=True,capture_output=True,timeout=60)
    lib=ctypes.CDLL(str(library))
    lib.intelligence_test.argtypes=[ctypes.c_wchar_p,ctypes.c_uint,ctypes.c_int32,ctypes.c_int32,ctypes.c_uint,
                                    ctypes.POINTER(ctypes.c_int32)]
    lib.intelligence_test.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)


@pytest.mark.parametrize('failure,base,bonus,target,sets,success',
    [(0,20,7,100,1,True),(0,20,-7,100,1,True),(0,20,0,0,1,True),(0,20,0,1000000,1,True),
     (0,20,7,5,0,False),(0,20,0,1000001,0,False),
     (0,2147483647,-2147483647,1000000,0,False)] +
    [(n,20,7,100,0 if n in (1,2,3,10,11) else 2 if n in (7,8) else 1,n==7) for n in range(1,12)])
def test_intelligence_native_abi_bonus_and_identity(native,tmp_path,failure,base,bonus,target,sets,success):
    out=(ctypes.c_int32*5)()
    enabled=faulthandler.is_enabled()
    if failure==9 and enabled:faulthandler.disable()
    try:
        assert native.intelligence_test(str(tmp_path)+'\\',failure,base,bonus,target,out)==0
    finally:
        if failure==9 and enabled:faulthandler.enable()
    assert out[0]==sets and out[4]==0
    payload=(tmp_path/f'war3_reforged_native_{os.getpid()}.bin').read_bytes()
    trainer=module.War3Trainer.__new__(module.War3Trainer)
    if success:
        result=trainer._parse_native_helper_results(payload,2)[1]
        assert result.result==target and result.arg1==out[2]
        assert out[2]+out[3]==target
        assert out[3]==bonus+(1 if failure==7 else 0)
    else:
        with pytest.raises(RuntimeError):trainer._parse_native_helper_results(payload,2)
    if not sets:assert out[2]==base
    if failure in (4,5,6,9):assert out[1]==2 # no readback/correction after target becomes invalid


@pytest.mark.parametrize('compat',[False,True])
def test_both_ui_routes_use_one_bound_callback_without_scanning_or_sleep(compat):
    trainer=module.War3Trainer.__new__(module.War3Trainer);candidate=make_candidate(make_snapshot());memory=Mock()
    field=module.UnitMemoryField('intelligence_total','intelligence','i32',30,0,'hero',native_write=True,
                                 native_component_identity=(0x5000,0x6000))
    trainer._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(153,100,arg1=93)])
    trainer._unit_fields_from_candidate=Mock(return_value=[field])
    trainer._discover_native_hero_int_internals=Mock(side_effect=AssertionError('internal disassembly'))
    trainer._current_jass_unit_handle_win10=Mock(side_effect=AssertionError('selection requery'))
    with patch.object(module.time,'sleep',side_effect=AssertionError('fixed wait')):
        if compat:result=trainer._write_hero_intelligence_field_win10(memory,candidate,field,100,Mock())
        else:result=trainer._write_unit_fields_to_candidate(memory,candidate,[module.MemoryWriteSpec('intelligence_total',0,'',100)])[0]
    assert result.value==100 and result.native_write and result.write_address==0
    trainer._run_native_helper_ops.assert_called_once_with(candidate.native_snapshot.handle,(
        (136,0,candidate.unit_address,candidate.handle,candidate.owner_address),(153,100,0x5000,0x6000,0)))
    assert memory.mock_calls==[]
    assert trainer._replace_win10_intelligence_field(memory,candidate,[field],Mock())==[field]


def test_missing_hero_identity_does_not_fall_back():
    trainer=module.War3Trainer.__new__(module.War3Trainer);candidate=make_candidate(make_snapshot())
    field=module.UnitMemoryField('intelligence_total','intelligence','i32',30,0,'hero')
    trainer._run_native_helper_ops=Mock()
    with pytest.raises(RuntimeError):trainer._write_hero_intelligence_field(Mock(),candidate,field,100)
    trainer._run_native_helper_ops.assert_not_called()
