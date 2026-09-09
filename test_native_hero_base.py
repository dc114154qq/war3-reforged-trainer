"""Production dispatcher with query values that differ from component storage."""
import ctypes
import faulthandler
import os
from pathlib import Path
import shutil
import subprocess
import threading
from unittest.mock import Mock, patch

import pytest
import war3_reforged_trainer as module
from test_native_identity_guard import HARNESS
from test_native_unit_field_dispatch import FIELDS_HARNESS
from test_native_snapshot_binding import make_candidate, make_snapshot


BASE_HARNESS = r'''
static int32_t base_storage[2],base_calculated,base_excluded;
static unsigned base_fault,base_sets[2],base_gets;
static void base_recycle(void) { *(uint64_t *)(object+0x18)+=1; }
static int32_t base_level(uint64_t unit) {
    if(unit!=7) ++bad_arguments;
    if(base_fault==14) base_recycle();
    return base_fault==1?0:5;
}
static int32_t base_get(unsigned stat,uint64_t unit,uint32_t bonus) {
    ++base_gets;
    if(unit!=7 || bonus!=0) ++bad_arguments;
    if(base_fault==3) base_recycle();
    if(base_fault==15 && stat==1) *(uint64_t *)(field_data[1]+0x18)+=1;
    return base_storage[stat]+base_calculated-(bonus?0:base_excluded);
}
static int32_t base_get_str(uint64_t u,uint32_t b) {return base_get(0,u,b);}
static int32_t base_get_agi(uint64_t u,uint32_t b) {return base_get(1,u,b);}
static void base_set(unsigned stat,uint64_t unit,int32_t value,uint32_t permanent) {
    if(unit!=7 || permanent!=1 || *(uint64_t *)(object+0x18)!=full) ++bad_arguments;
    ++base_sets[stat];
    /* Model verified native semantics: adjustment = target - queried base,
       then add that adjustment to storage. Writing target to storage fails. */
    int32_t current=base_storage[stat]+base_calculated-base_excluded;
    base_storage[stat]+=value-current;
    if(base_fault==4) base_recycle();
    if(base_fault==5) *(uint64_t *)(field_data[1]+0x18)+=1;
    if(base_fault==6) *(uint64_t *)(object+0x5a8)=0;
    if(base_fault==7) --base_storage[stat];
    if(base_fault==8 && stat==1) --base_storage[0];
    if(base_fault==9) RaiseException(0xe0000001,0,0,NULL);
}
static void base_set_str(uint64_t u,int32_t v,uint32_t p) {base_set(0,u,v,p);}
static void base_set_agi(uint64_t u,int32_t v,uint32_t p) {base_set(1,u,v,p);}
__declspec(dllexport) DWORD base_test(const wchar_t *directory,unsigned fault,unsigned mask,
    unsigned target,int32_t calculated,int32_t excluded,int32_t *out) {
    DWORD error=field_snapshot(directory,15,0),bytes;HANDLE file;wchar_t path[MAX_PATH];NativeCommand cmd={0};
    if(error) return error;
    command_path(path,MAX_PATH);DeleteFileW(path);
    base_fault=fault;field_fault=0;field_unit_calls=0;
    base_storage[0]=20;base_storage[1]=30;base_sets[0]=base_sets[1]=base_gets=bad_arguments=0;
    base_calculated=calculated;base_excluded=excluded;
    for(unsigned n=0;n<sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]);++n) {
        const char *name=g_persistent_native_names[n];
        if(!strcmp(name,"GetHeroStr")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)base_get_str;
        if(!strcmp(name,"GetHeroAgi")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)base_get_agi;
        if(!strcmp(name,"SetHeroStr")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)base_set_str;
        if(!strcmp(name,"SetHeroAgi")) g_persistent_natives[n].handler=fault==2?0:(uint64_t)(uintptr_t)base_set_agi;
        if(!strcmp(name,"GetHeroLevel")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)base_level;
    }
    cmd.magic=WAR3_NATIVE_MAGIC;cmd.version=WAR3_NATIVE_VERSION;cmd.status=WAR3_NATIVE_STATUS_PENDING;
    cmd.op_count=1;cmd.unit_handle=7;
    cmd.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;cmd.ops[0].handler=(uint64_t)(uintptr_t)object;
    cmd.ops[0].arg0=full;cmd.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    for(unsigned stat=0;stat<2;++stat) if(mask&(1u<<stat)) {
        NativeOp *op=&cmd.ops[cmd.op_count++];op->kind=WAR3_NATIVE_OP_SET_BOUND_HERO_BASE;
        op->rawcode=stat;op->handler=(uint64_t)(uintptr_t)field_data[1];op->arg0=field_full(1);op->arg1=target;
    }
    if(fault==10) cmd.ops[2].rawcode=0;
    if(fault==11) cmd.ops[cmd.op_count-1].arg1=1000001;
    if(fault==12) cmd.ops[cmd.op_count-1].kind=WAR3_NATIVE_OP_WRITE_COMPONENT_FIELDS;
    if(fault==13) *(uint64_t *)(field_wrappers[1]+0x50)=0;
    if(fault==16) cmd.ops[cmd.op_count-1].rawcode=2;
    file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();
    BOOL ok=WriteFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);
    if(!ok || bytes!=sizeof(cmd)) return ERROR_WRITE_FAULT;
    run_command();out[0]=base_sets[0];out[1]=base_sets[1];out[2]=base_gets;out[3]=bad_arguments;
    out[4]=base_storage[0];out[5]=base_storage[1];
    return 0;
}
'''


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler: pytest.skip('clang required')
    root=tmp_path_factory.mktemp('hero-base');source=root/'test.c';library=root/'test.dll'
    source.write_text(HARNESS.replace('static uint8_t object[0x20]','static uint8_t object[0x600]')
        .replace('HELPER_SOURCE',(Path(__file__).parent/'tools/war3_native_helper.c').as_posix())
        +FIELDS_HARNESS+BASE_HARNESS,encoding='utf8')
    subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(library),
                    '-luser32','-lkernel32'],check=True,capture_output=True,timeout=60)
    lib=ctypes.CDLL(str(library))
    lib.base_test.argtypes=[ctypes.c_wchar_p,ctypes.c_uint,ctypes.c_uint,ctypes.c_uint,
                           ctypes.c_int32,ctypes.c_int32,ctypes.POINTER(ctypes.c_int32)]
    lib.base_test.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)


def dispatch(native,path,fault=0,mask=3,target=100,calculated=28,excluded=35):
    out=(ctypes.c_int32*6)();enabled=faulthandler.is_enabled()
    if fault==9 and enabled:faulthandler.disable()
    try:
        assert native.base_test(str(path)+'\\',fault,mask,target,calculated,excluded,out)==0
    finally:
        if fault==9 and enabled:faulthandler.enable()
    assert out[3]==0
    return out,(path/f'war3_reforged_native_{os.getpid()}.bin').read_bytes()


@pytest.mark.parametrize('mask',[1,2,3])
@pytest.mark.parametrize('target,calculated,excluded',[(100,28,35),(100,35,28),(0,28,35),(1000000,0,0)])
def test_game_setter_meets_display_target_despite_storage_difference(native,tmp_path,mask,target,calculated,excluded):
    out,payload=dispatch(native,tmp_path,mask=mask,target=target,calculated=calculated,excluded=excluded)
    results=module.War3Trainer.__new__(module.War3Trainer)._parse_native_helper_results(payload,1+mask.bit_count())
    assert [r.result for r in results[1:]]==[target]*mask.bit_count()
    for stat in (0,1):
        assert out[stat]==bool(mask&(1<<stat))
        if mask&(1<<stat): assert out[4+stat]+calculated-excluded==target
        else: assert out[4+stat]==20+10*stat
    assert out[2]==(6 if mask==3 else 2)


@pytest.mark.parametrize('fault',range(1,17))
def test_bad_batch_identity_changes_and_readback_failures_never_report_success(native,tmp_path,fault):
    out,payload=dispatch(native,tmp_path,fault=fault)
    with pytest.raises(RuntimeError):module.War3Trainer.__new__(module.War3Trainer)._parse_native_helper_results(payload,3)
    expected_sets=2 if fault==8 else 1 if fault in (4,5,6,7,9) else 0
    assert out[0]+out[1]==expected_sets
    if not expected_sets:assert list(out[4:])==[20,30]
    if fault in (4,5,6,9):assert out[2]==2 # no query after first setter invalidates identity


def editor():
    t=module.War3Trainer.__new__(module.War3Trainer);candidate=make_candidate(make_snapshot())
    fields=[module.UnitMemoryField(key,key,'i32',10,0,'hero',native_write=True,
             native_component_identity=(0x5000,0x6000)) for key in ('base_strength','base_agility')]
    t._unit_fields_from_candidate=Mock(return_value=fields)
    t._run_native_helper_ops=Mock(side_effect=lambda handle,ops:[module.NativeHelperOpResult(136,1)]+
                                  [module.NativeHelperOpResult(op[0],op[4]) for op in ops[1:]])
    return t,candidate


def test_editor_batches_both_base_stats_without_external_reads_or_sleeps():
    t,candidate=editor();memory=Mock()
    with patch.object(module.time,'sleep',side_effect=AssertionError('No sleep')):
        result=t._write_unit_fields_to_candidate(memory,candidate,[module.MemoryWriteSpec(k,0,'',v)
                     for k,v in [('base_agility',200),('base_strength',100)]])
    assert [f.value for f in result]==[200,100]
    t._run_native_helper_ops.assert_called_once_with(candidate.native_snapshot.handle,(
        (136,0,candidate.unit_address,candidate.handle,candidate.owner_address),
        (163,1,0x5000,0x6000,200),(163,0,0x5000,0x6000,100)))
    assert memory.mock_calls==[]
    # Exercise the production controller whitelist/serializer as well.
    ops=t._run_native_helper_ops.call_args.args[1]
    t._native_helper_command_path=Mock(return_value='offline-command')
    t._write_native_helper_command=Mock()
    t._native_helper_batch_hook=1
    t._native_helper_batch_thread_id=threading.get_ident()
    t._wait_native_helper_result=Mock(return_value=[])
    t._run_native_helper_ops_locked(candidate.native_snapshot.handle,ops)
    payload=t._write_native_helper_command.call_args.args[1]
    base=t.NATIVE_HELPER_HEADER_STRUCT.size;size=t.NATIVE_HELPER_OP_STRUCT.size
    assert [t.NATIVE_HELPER_OP_STRUCT.unpack_from(payload,base+i*size)[:5] for i in range(3)]==list(ops)


def test_mixed_component_and_stat_request_uses_valid_separate_batches_and_preserves_results():
    t,candidate=editor()
    armor=module.UnitMemoryField('armor','armor','f32',1,0,'defense',native_write=True,
                                native_component_identity=(candidate.unit_address,candidate.handle))
    t._unit_fields_from_candidate.return_value.append(armor)
    specs=[module.MemoryWriteSpec(k,0,'',v) for k,v in [('base_strength',100),('armor',3.5),('base_agility',200)]]
    fields=t._write_unit_fields_to_candidate(Mock(),candidate,specs)
    assert [f.value for f in fields]==[100,3.5,200]
    assert [[op[0] for op in call.args[1]] for call in t._run_native_helper_ops.call_args_list]==[[136,163,163],[136,152]]


@pytest.mark.parametrize('value',[-1,1000001,'1.5',float('nan'),float('inf')])
def test_invalid_second_stat_prevents_first_stat_mutation(value):
    t,candidate=editor()
    with pytest.raises(ValueError):t._write_unit_fields_to_candidate(Mock(),candidate,[
        module.MemoryWriteSpec('base_strength',0,'',100),module.MemoryWriteSpec('base_agility',0,'',value)])
    t._run_native_helper_ops.assert_not_called()
