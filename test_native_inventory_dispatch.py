"""Production op 149, its binary parser and native inventory routing together."""
import ctypes
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import subprocess
from unittest.mock import Mock

import pytest
import war3_reforged_trainer as module
from test_native_identity_guard import HARNESS
from test_native_snapshot_binding import make_candidate, make_snapshot


INVENTORY_HARNESS = r'''
static uint8_t inv_objects[6][0x1c0], inv_wrappers[6][0x98];
static uint64_t inv_slots[6];
static unsigned inv_failure, inv_capacity, inv_slot_calls, inv_capacity_calls;
static uint64_t inv_full(unsigned n) { return 0x223300004455ULL+n; }
static uint64_t inv_agent(uint32_t lo,uint32_t hi) {
    uint64_t id=((uint64_t)hi<<32)|lo;
    if(id==full) return (uint64_t)(uintptr_t)owner;
    for(unsigned n=0;n<6;++n) if(id==inv_full(n))
        return inv_failure==5 ? 1 : (uint64_t)(uintptr_t)inv_wrappers[n];
    return 0;
}
static int32_t inv_size(uint64_t unit) {
    if(unit!=7) ++bad_arguments;
    ++inv_capacity_calls;
    if(inv_failure==11 && inv_capacity_calls==2) return 0;
    return inv_failure==1 ? 7 : (int32_t)inv_capacity;
}
static uint64_t inv_slot(uint64_t unit,int32_t slot) {
    ++inv_slot_calls;
    if(unit!=7 || slot<0 || slot>=6) { ++bad_arguments;return 0; }
    return inv_slots[slot];
}
static uint64_t inv_resolve(uint64_t handle) {
    if(inv_failure==4) return 1;
    if(handle<100 || handle>=106) { ++bad_arguments;return 0; }
    return (uint64_t)(uintptr_t)inv_objects[handle-100];
}
static uint32_t inv_type(uint64_t handle) {
    if(handle<100 || handle>=106) { ++bad_arguments;return 0; }
    return inv_failure==7 ? 0x49303039 : 0x49303031;
}
static int32_t inv_charges(uint64_t handle) {
    if(handle<100 || handle>=106) { ++bad_arguments;return 0; }
    if(inv_failure==8) inv_slots[0]=0;
    if(inv_failure==9) *(uint64_t *)(inv_objects[0]+0x18)+=1;
    if(inv_failure==10) *(uint64_t *)(object+0x18)+=1;
    if(inv_failure==12) inv_slots[5]=105;
    if(inv_failure==13) *(uint64_t *)(inv_wrappers[0]+0x90)=0;
    return handle==100 ? 1500 : -3;
}
__declspec(dllexport) DWORD inventory_dispatch(const wchar_t *directory,unsigned capacity,unsigned occupied,
                                               unsigned failure,unsigned *out) {
    NativeCommand cmd={0};DWORD bytes;HANDLE file;wchar_t path[MAX_PATH];
    if(wcslen(directory)>=MAX_PATH-1 || capacity>6) return ERROR_INVALID_PARAMETER;
    wcscpy(test_directory,directory);
    fault=bad_arguments=inv_slot_calls=inv_capacity_calls=0;
    inv_failure=failure;inv_capacity=capacity;
    ZeroMemory(object,sizeof(object));ZeroMemory(owner,sizeof(owner));
    ZeroMemory(inv_objects,sizeof(inv_objects));ZeroMemory(inv_wrappers,sizeof(inv_wrappers));
    *(uint64_t *)(object+0x18)=full;
    *(uint64_t *)(owner+0x18)=0x2b7733752b61676cULL;
    *(uint64_t *)(owner+0x20)=full;*(uint64_t *)(owner+0x90)=(uint64_t)(uintptr_t)object;
    for(unsigned n=0;n<6;++n) {
        uint8_t *obj=inv_objects[n],*wrapper=inv_wrappers[n];
        inv_slots[n]=(occupied&(1u<<n)) ? 100+n : 0;
        *(uint64_t *)(obj+0x18)=*(uint64_t *)(wrapper+0x20)=inv_full(n);
        *(uint32_t *)(obj+0x70)=0x49303031;
        *(uint32_t *)(obj+0x178)=0x49303032;
        *(uint32_t *)(obj+0x1b8)=n==0 ? 0x41303031 : 0; /* optional ability */
        *(uint64_t *)(wrapper+0x18)=0x6974656d2b61676cULL;
        *(uint64_t *)(wrapper+0x90)=(uint64_t)(uintptr_t)obj;
    }
    if(failure==2) inv_slots[5]=105;
    if(failure==3) inv_slots[1]=inv_slots[0];
    if(failure==6) *(uint64_t *)(inv_wrappers[0]+0x18)=0x2b7733752b61676cULL;
    g_persistent_unit_resolver=(uint64_t)(uintptr_t)fake_unit;
    g_persistent_item_resolver=(uint64_t)(uintptr_t)inv_resolve;
    g_persistent_agent_resolver=(uint64_t)(uintptr_t)inv_agent;
    for(unsigned n=0;n<sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]);++n) {
        const char *name=g_persistent_native_names[n];
        g_persistent_natives[n].name=name;g_persistent_natives[n].handler=0;
        if(!strcmp(name,"UnitInventorySize")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)inv_size;
        if(!strcmp(name,"UnitItemInSlot")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)inv_slot;
        if(!strcmp(name,"GetItemTypeId")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)inv_type;
        if(!strcmp(name,"GetItemCharges") && failure!=14) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)inv_charges;
    }
    cmd.magic=WAR3_NATIVE_MAGIC;cmd.version=WAR3_NATIVE_VERSION;cmd.status=WAR3_NATIVE_STATUS_PENDING;
    cmd.op_count=2;cmd.unit_handle=7;
    cmd.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;
    cmd.ops[0].handler=(uint64_t)(uintptr_t)object;cmd.ops[0].arg0=full;
    cmd.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    cmd.ops[1].kind=WAR3_NATIVE_OP_BOUND_INVENTORY;
    if(failure==15) cmd.ops[0].arg0+=1;
    command_path(path,MAX_PATH);
    file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();
    BOOL ok=WriteFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);
    if(!ok || bytes!=sizeof(cmd)) return ERROR_WRITE_FAULT;
    run_command();out[0]=bad_arguments;out[1]=inv_slot_calls;return 0;
}
'''


@pytest.fixture(scope='module')
def dispatcher(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler: pytest.skip('clang required')
    root=tmp_path_factory.mktemp('inventory-dispatch');source=root/'test.c';library=root/'test.dll'
    source.write_text(HARNESS.replace('HELPER_SOURCE',(Path(__file__).parent/'tools/war3_native_helper.c').as_posix())
                      + INVENTORY_HARNESS,encoding='utf8')
    subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(library),
                    '-luser32','-lkernel32'],check=True,capture_output=True,timeout=60)
    lib=ctypes.CDLL(str(library))
    lib.inventory_dispatch.argtypes=[ctypes.c_wchar_p,*([ctypes.c_uint]*3),ctypes.POINTER(ctypes.c_uint)]
    lib.inventory_dispatch.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)


@pytest.mark.parametrize('capacity,occupied,failure',
    [(0,0,0),(1,0,0),(1,1,0),(6,0,0),(6,33,0),(6,63,0)]+[(5,1,n) for n in range(1,16)])
@pytest.mark.parametrize('initialized',[False,True])
def test_production_inventory_payload_and_no_external_fallback(dispatcher,tmp_path,capacity,occupied,failure,initialized):
    out=(ctypes.c_uint*2)()
    assert dispatcher.inventory_dispatch(str(tmp_path)+'\\',capacity,occupied,failure,out)==0
    assert out[0]==0 and out[1]<=12
    payload=(tmp_path/f'war3_reforged_native_{os.getpid()}.bin').read_bytes()
    trainer=module.War3Trainer.__new__(module.War3Trainer)
    trainer._persistent_native_initialized=initialized
    trainer._run_native_helper_ops=Mock(side_effect=lambda *a:trainer._parse_native_helper_results(payload,2))
    trainer._selected_components=Mock(side_effect=AssertionError('external component lookup'))
    trainer._item_objects_from_handles=Mock(side_effect=AssertionError('item scan'))
    candidate=make_candidate(make_snapshot()) # deliberately no HP or MP property
    memory=Mock()
    if failure:
        with pytest.raises(RuntimeError): trainer._inventory_items_from_candidate(memory,candidate)
        assert len(payload)==trainer._native_helper_command_size()
    else:
        items=trainer._inventory_items_from_candidate(memory,candidate)
        assert len(items)==6
        for n,item in enumerate(items):
            assert item.native_slot==(n<capacity)
            assert bool(item.item_address)==bool(occupied&(1<<n))
            if item.item_address:
                assert item.rawcode==0x49303031
                assert item.charges==(1500 if n==0 else -3)
                assert item.mirror_rawcode==0x49303032
                assert item.ability_rawcode==(0x41303031 if n==0 else 0)
    trainer._run_native_helper_ops.assert_called_once_with(candidate.native_snapshot.handle,(
        (136,0,candidate.unit_address,candidate.handle,candidate.owner_address),(149,0,0,0,0)))
    assert memory.mock_calls==[]
    trainer._selected_components.assert_not_called();trainer._item_objects_from_handles.assert_not_called()


@pytest.mark.parametrize('change',['capacity','truncated','orphan','duplicate','missing_full','outside_capacity'])
def test_corrupt_inventory_payload_is_rejected(change):
    trainer=module.War3Trainer.__new__(module.War3Trainer)
    row=[100,0x223300004455,0x123000,0x49303031,1500,0,0,0x456000]
    values=[6]+row+[0]*40
    if change=='capacity':values[0]=7
    elif change=='truncated':values.pop()
    elif change=='orphan':values[9+2]=0x9999
    elif change=='duplicate':values[9:17]=row
    elif change=='missing_full':values[2]=0
    elif change=='outside_capacity':values[0]=0
    with pytest.raises(RuntimeError):trainer._parse_native_inventory_items(tuple(values))


def test_internal_item_calls_keep_unit_guard_without_vital_properties():
    trainer=module.War3Trainer.__new__(module.War3Trainer)
    candidate=make_candidate(make_snapshot())
    trainer._query_native_table_handlers=Mock(side_effect=AssertionError('Controller function lookup'))
    trainer._rel32_calls_in_function=Mock(side_effect=AssertionError('External code read'))
    trainer._is_executable_image_address=Mock(return_value=True)
    trainer._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(136,1),
        module.NativeHelperOpResult(150,0x456000),module.NativeHelperOpResult(151,0x49303032)])
    assert not candidate.native_snapshot.hp_property and not candidate.native_snapshot.mp_property
    assert trainer._set_inventory_slot_item_via_native_handler(Mock(),candidate,0,0x49303032)==(
        candidate.native_snapshot.item_addresses[0],0x456000,0x49303032)
    handle,ops=trainer._run_native_helper_ops.call_args.args
    assert handle==candidate.native_snapshot.handle
    assert ops[0]==(136,0,candidate.unit_address,candidate.handle,candidate.owner_address)
    assert [op[0] for op in ops]==[136,150,151]
    assert ops[1][2]==0
    trainer._query_native_table_handlers.assert_not_called()
    trainer._rel32_calls_in_function.assert_not_called()
    assert ops[1][3:]==(candidate.native_snapshot.item_handles[0],candidate.native_snapshot.item_full_handles[0])
    assert ops[2][2:4]==(candidate.native_snapshot.item_addresses[0],candidate.native_snapshot.item_ids[0])
