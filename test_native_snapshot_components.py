"""Production selection snapshot includes actual component identities in one call."""
import ctypes
from pathlib import Path
import shutil
import subprocess
from unittest.mock import Mock

import pytest
import war3_reforged_trainer as module
from test_native_snapshot_payload import HARNESS


COMPONENTS=r'''
static unsigned component_mask,component_fault,component_calls;
static uint8_t component_data[13][4][0x70],component_wrappers[13][4][0x98];
static const uint32_t component_offsets[4]={0x5a0,0x5a8,0x5b0,0x5c0};
static const uint64_t component_tags[4]={0x41496e762b61676cULL,0x414865722b61676cULL,
                                      0x416d6f762b61676cULL,0x4161746b2b61676cULL};
static uint64_t component_full(unsigned n,unsigned k) {return 0x445500000001ULL+n*4+k;}
static uint64_t component_agent(uint32_t slot,uint32_t serial) {
    uint64_t full=((uint64_t)serial<<32)|slot;
    for(unsigned n=0;n<selected;++n) for(unsigned k=0;k<4;++k) if(full==component_full(n,k)) {
        ++component_calls;
        if(component_fault==7) return 1;
        if(k==3 && n==selected-1) {
            if(component_fault==8) *(uint64_t *)(objects[n]+0x5a0)=0;
            if(component_fault==9) *(uint64_t *)(objects[n]+0x5a0)=(uint64_t)(uintptr_t)component_data[n][0];
            if(component_fault==10) *(uint64_t *)(objects[n]+0x18)+=1ULL<<32;
        }
        return (uint64_t)(uintptr_t)component_wrappers[n][k];
    }
    return fake_agent(slot,serial);
}
static uint64_t component_unit(uint64_t unit) {
    if(component_fault==11 && component_calls==4)
        *(uint64_t *)(component_data[unit-1][0]+0x18)+=1;
    return fake_unit(unit);
}
static uint64_t component_empty_slot(uint64_t unit,int32_t slot) {return 0;}
static void prepare_components(void) {
    ZeroMemory(component_data,sizeof(component_data));ZeroMemory(component_wrappers,sizeof(component_wrappers));
    component_calls=0;
    for(unsigned n=0;n<selected;++n) for(unsigned k=0;k<4;++k) {
        uint8_t *data=component_data[n][k],*wrapper=component_wrappers[n][k];
        unsigned mask=component_mask==16?n:component_mask;
        if(mask&(1u<<k)) *(uint64_t *)(objects[n]+component_offsets[k])=(uint64_t)(uintptr_t)data;
        *(uint64_t *)(data+0x18)=*(uint64_t *)(wrapper+0x20)=component_full(n,k);
        *(uint64_t *)(data+0x68)=(uint64_t)(uintptr_t)objects[n];
        *(uint64_t *)(wrapper+0x18)=component_tags[k];
        *(uint64_t *)(wrapper+0x50)=(uint64_t)(uintptr_t)owners[n];
        *(uint64_t *)(wrapper+0x90)=(uint64_t)(uintptr_t)data;
    }
    unsigned n=selected-1;
    if(component_fault==1) *(uint64_t *)(component_data[n][0]+0x18)+=1;
    if(component_fault==2) *(uint64_t *)(component_wrappers[n][0]+0x50)=0;
    if(component_fault==3) *(uint64_t *)(component_wrappers[n][0]+0x18)=component_tags[1];
    if(component_fault==4) *(uint64_t *)(component_data[n][0]+0x68)=0;
    if(component_fault==5) *(uint64_t *)(component_wrappers[n][0]+0x90)=0;
    if(component_fault==6) *(uint64_t *)(objects[n]+0x5a0)=1;
    g_persistent_unit_resolver=(uint64_t)(uintptr_t)component_unit;
    g_persistent_agent_resolver=(uint64_t)(uintptr_t)component_agent;
    for(unsigned k=0;k<sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]);++k)
        if(!strcmp(g_persistent_native_names[k],"UnitItemInSlot"))
            g_persistent_natives[k].handler=(uint64_t)(uintptr_t)component_empty_slot;
}
__declspec(dllexport) unsigned component_snapshot(unsigned n,unsigned mask,unsigned fault,uint64_t *out,
                                                 unsigned *length,unsigned *units) {
    unsigned counts[12]={0};component_mask=mask;component_fault=fault;
    return collect(n,counts,UINT32_MAX,0,out,12*154,length,units);
}
'''


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler:pytest.skip('clang required')
    root=tmp_path_factory.mktemp('snapshot_components');source=root/'test.c';library=root/'test.dll'
    harness=HARNESS.replace('__declspec(dllexport) unsigned collect(',
                           'static void prepare_components(void);\n__declspec(dllexport) unsigned collect(')
    harness=harness.replace('error = war3_persistent_selected_snapshot(',
                            'prepare_components();\n    error = war3_persistent_selected_snapshot(')
    source.write_text(harness.replace('HELPER_SOURCE',(Path(__file__).parent/'tools/war3_native_helper.c').as_posix())
                      +COMPONENTS,encoding='utf8')
    subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(library),
                    '-luser32','-lkernel32'],check=True,capture_output=True,timeout=60)
    lib=ctypes.CDLL(str(library))
    lib.component_snapshot.argtypes=[ctypes.c_uint]*3+[ctypes.POINTER(ctypes.c_uint64),ctypes.POINTER(ctypes.c_uint),ctypes.POINTER(ctypes.c_uint)]
    lib.component_snapshot.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)


@pytest.mark.parametrize('mask',range(17))
def test_real_group_snapshot_drives_summaries_without_extra_queries(native,mask):
    count=12 if mask==16 else 1
    out=(ctypes.c_uint64*(12*154))();length=ctypes.c_uint();units=ctypes.c_uint()
    assert native.component_snapshot(count,mask,0,out,ctypes.byref(length),ctypes.byref(units))==0
    assert length.value==count*154 and units.value==count
    trainer=module.War3Trainer.__new__(module.War3Trainer);trainer._unit_owner_index={}
    trainer._run_native_helper_ops=Mock(side_effect=AssertionError('extra IPC'))
    trainer._selected_components=Mock(side_effect=AssertionError('external component lookup'))
    snapshots=trainer._parse_persistent_native_snapshots(module.NativeHelperOpResult(
        trainer.NATIVE_HELPER_OP_PERSISTENT_SELECTED_SNAPSHOT,count,extra_results=tuple(out[:length.value])))
    pm=Mock()
    summaries=trainer._selected_summaries_from_snapshot(pm,trainer._selected_candidates_snapshot(pm,persistent_snapshots=snapshots))
    for n,summary in enumerate(summaries):
        expected=n if mask==16 else mask
        names=tuple(sorted(name for k,name in enumerate(('inventory','hero','move','attack')) if expected&(1<<k)))
        assert snapshots[n].component_mask==expected and summary.components==names
        assert summary.hero==bool(expected&2) and summary.inventory==()
    assert pm.mock_calls==[] and not trainer._run_native_helper_ops.called
    assert native.enumeration_count()==1 and native.live_allocations()==0


@pytest.mark.parametrize('fault',range(1,12))
def test_invalid_or_changed_component_aborts_the_entire_group(native,fault):
    count=1 if fault==11 else 2
    mask=8 if fault==9 else 15
    out=(ctypes.c_uint64*(12*154))();length=ctypes.c_uint();units=ctypes.c_uint()
    assert native.component_snapshot(count,mask,fault,out,ctypes.byref(length),ctypes.byref(units))!=0
    assert length.value==units.value==0 and native.live_allocations()==0


def test_parser_rejects_unknown_component_bits():
    from test_native_snapshot_binding import make_snapshot,snapshot_result
    from dataclasses import replace
    trainer=module.War3Trainer.__new__(module.War3Trainer)
    with pytest.raises(RuntimeError,match='invalid component mask'):
        trainer._parse_persistent_native_snapshots(snapshot_result(replace(make_snapshot(),component_mask=16)))
