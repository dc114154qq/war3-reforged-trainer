"""Production C field snapshot -> production parser -> complete field display."""
import ctypes
from dataclasses import replace
import os
from pathlib import Path
import shutil
import subprocess
from unittest.mock import Mock

import pytest
import war3_reforged_trainer as module
from test_native_identity_guard import HARNESS
from test_native_snapshot_binding import make_candidate, make_snapshot


FIELDS_HARNESS = r'''
static uint8_t field_data[4][0xa00], field_wrappers[4][0x98];
static unsigned field_fault, field_unit_calls;
static unsigned field_inventory_size;
static uint64_t field_slot(uint64_t unit,int32_t slot) { return 0; }
static int32_t field_capacity(uint64_t unit) { return (int32_t)field_inventory_size; }
static uint64_t field_vtable[] = {(uint64_t)(uintptr_t)fake_max};
static const uint32_t field_slots[4] = {0x5a0,0x5a8,0x5b0,0x5c0};
static uint64_t field_full(unsigned k) { return 0x234500005678ULL + k; }
static uint64_t field_unit(uint64_t handle) {
    ++field_unit_calls;
    if (field_unit_calls == 4) {
        if (field_fault == 5) *(uint64_t *)(object+0x18) += 1;
        if (field_fault == 6) *(uint64_t *)(object+0x5c0) = 0;
        if (field_fault == 7) *(uint64_t *)(field_data[3]+0x18) += 1;
        if (field_fault == 8) *(uint64_t *)(field_wrappers[3]+0x50) = 0;
        if (field_fault == 9) *(uint64_t *)(object+0x5b0) = (uint64_t)(uintptr_t)field_data[2];
    }
    return handle == 7 ? (uint64_t)(uintptr_t)object : 0;
}
static uint64_t field_agent(uint32_t slot, uint32_t serial) {
    uint64_t id = ((uint64_t)serial<<32)|slot;
    if (id == full) return (uint64_t)(uintptr_t)owner;
    if (field_fault == 14 && id == field_full(3)) return 1;
    for (unsigned k=0;k<4;++k)
        if (id == field_full(k)) return (uint64_t)(uintptr_t)field_wrappers[k];
    return 0;
}
__declspec(dllexport) DWORD field_snapshot(const wchar_t *directory,unsigned mask,unsigned failure) {
    NativeCommand cmd={0}; DWORD bytes; HANDLE file; wchar_t path[MAX_PATH];
    void *partial = NULL;
    const uint64_t tags[4]={0x41496e762b61676cULL,0x414865722b61676cULL,
                          0x416d6f762b61676cULL,0x4161746b2b61676cULL};
    if(wcslen(directory)>=MAX_PATH-1) return ERROR_INVALID_PARAMETER;
    wcscpy(test_directory,directory); field_fault=failure;field_unit_calls=0;
    field_inventory_size=(mask&1)?6:0;
    for(unsigned i=0;i<sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]);++i) {
        g_persistent_natives[i].name=g_persistent_native_names[i];
        g_persistent_natives[i].handler=(uint64_t)(uintptr_t)field_capacity;
        if(!strcmp(g_persistent_native_names[i],"UnitItemInSlot"))
            g_persistent_natives[i].handler=(uint64_t)(uintptr_t)field_slot;
    }
    g_persistent_item_resolver=(uint64_t)(uintptr_t)fake_item_resolver;
    ZeroMemory(object,sizeof(object));ZeroMemory(owner,sizeof(owner));
    ZeroMemory(field_data,sizeof(field_data));ZeroMemory(field_wrappers,sizeof(field_wrappers));
    *(uint64_t *)(object+0x18)=full;
    *(uint64_t *)(owner+0x18)=0x2b7733752b61676cULL;
    *(uint64_t *)(owner+0x20)=full;
    *(uint64_t *)(owner+0x90)=(uint64_t)(uintptr_t)object;
    *(float *)(object+0x2e8)=12.5f;*(int32_t *)(object+0x2f0)=4;
    for(unsigned k=0;k<4;++k) {
        uint8_t *data=field_data[k],*wrapper=field_wrappers[k];
        if(mask & (1u<<k)) *(uint64_t *)(object+field_slots[k])=(uint64_t)(uintptr_t)data;
        *(uint64_t *)data=(uint64_t)(uintptr_t)field_vtable;
        *(uint64_t *)(data+0x18)=*(uint64_t *)(wrapper+0x20)=field_full(k);
        *(uint64_t *)(data+0x68)=(uint64_t)(uintptr_t)object;
        *(uint64_t *)(wrapper+0x18)=tags[k];
        *(uint64_t *)(wrapper+0x50)=(uint64_t)(uintptr_t)owner;
        *(uint64_t *)(wrapper+0x90)=(uint64_t)(uintptr_t)data;
    }
    *(int32_t *)(field_data[1]+0x104)=9;
    *(float *)(field_data[1]+0x188)=2.25f;
    *(float *)(field_data[1]+0x198)=3.25f;
    *(float *)(field_data[1]+0x1a8)=4.25f;
    for(unsigned n=0;n<6;++n) {
        *(uint32_t *)(field_data[1]+0x204+n*4)=0x41303031u+n;
        *(uint32_t *)(field_data[1]+0x1bc+n*4)=0x42303031u+n;
        *(int32_t *)(field_data[1]+0x1d4+n*4)=n+1;
        *(int32_t *)(field_data[1]+0x1ec+n*4)=n+10;
    }
    for(unsigned n=0;n<2;++n) {
        uint8_t *attack=field_data[3]+n*0x638;
        *(uint64_t *)attack=(uint64_t)(uintptr_t)field_vtable;
        *(int32_t *)(attack+8)=42;
        *(int32_t *)(attack+0x104)=101+n;
        *(float *)(attack+0x200)=1.25f+n;
        *(float *)(attack+0x3c0)=100.5f+n;
    }
    if(failure==1) *(uint64_t *)(object+0x18)+=1;
    if(failure==2) *(uint64_t *)(field_wrappers[3]+0x18)=tags[1];
    if(failure==3) *(uint64_t *)(field_data[3]+0x68)=0;
    if(failure==4) *(uint64_t *)(field_wrappers[3]+0x90)=0;
    if(failure==10) *(uint64_t *)(object+0x5c0)=1;
    if(failure==11) *(uint64_t *)(field_data[3]+0x638)=1; /* no valid second attack */
    if(failure==12) *(int32_t *)(field_data[3]+0x640)=43;
    if(failure==15) {
        DWORD old;
        partial=VirtualAlloc(NULL,0x2000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
        if(!partial) return GetLastError();
        if(!VirtualProtect((uint8_t *)partial+0x1000,0x1000,PAGE_NOACCESS,&old)) {
            DWORD error=GetLastError();VirtualFree(partial,0,MEM_RELEASE);return error;
        }
        /* Header is readable, but the requested attack fields cross into an
           inaccessible page. A start-address check alone is insufficient. */
        memcpy((uint8_t *)partial+0xf90,field_data[3],0x70);
        *(uint64_t *)(object+0x5c0)=(uint64_t)(uintptr_t)((uint8_t *)partial+0xf90);
        *(uint64_t *)(field_wrappers[3]+0x90)=*(uint64_t *)(object+0x5c0);
    }
    g_persistent_unit_resolver=(uint64_t)(uintptr_t)field_unit;
    g_persistent_agent_resolver=(uint64_t)(uintptr_t)field_agent;
    cmd.magic=WAR3_NATIVE_MAGIC;cmd.version=WAR3_NATIVE_VERSION;cmd.status=WAR3_NATIVE_STATUS_PENDING;
    cmd.op_count=2;cmd.unit_handle=7;
    cmd.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;
    cmd.ops[0].handler=(uint64_t)(uintptr_t)object;cmd.ops[0].arg0=full;
    cmd.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    cmd.ops[1].kind=WAR3_NATIVE_OP_BOUND_UNIT_FIELDS;
    if(failure==13) cmd.ops[0].kind=WAR3_NATIVE_OP_INTERNAL_ABILITY_FIND;
    command_path(path,MAX_PATH);
    file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();
    BOOL ok=WriteFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);
    if(!ok || bytes!=sizeof(cmd)) return ERROR_WRITE_FAULT;
    run_command();if(partial) VirtualFree(partial,0,MEM_RELEASE);return 0;
}
'''


@pytest.fixture(scope='module')
def dispatcher(tmp_path_factory):
    compiler = shutil.which('clang')
    if not compiler:
        pytest.skip('clang required')
    root = tmp_path_factory.mktemp('unit-fields')
    source, library = root/'test.c', root/'test.dll'
    harness = HARNESS.replace('static uint8_t object[0x20]', 'static uint8_t object[0x600]')
    source.write_text(harness.replace('HELPER_SOURCE', (Path(__file__).parent/'tools/war3_native_helper.c').as_posix())
                      + FIELDS_HARNESS, encoding='utf8')
    subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(library),
                    '-luser32','-lkernel32'],check=True,capture_output=True,timeout=60)
    native=ctypes.CDLL(str(library))
    native.field_snapshot.argtypes=[ctypes.c_wchar_p,ctypes.c_uint,ctypes.c_uint]
    native.field_snapshot.restype=ctypes.c_uint
    yield native
    import _ctypes
    _ctypes.FreeLibrary(native._handle)


@pytest.mark.parametrize('mask,failure', [(0,0),(15,0),(13,0),(2,0),(15,11),(15,12)] +
                         [(15,n) for n in range(1,9)] + [(11,9),(15,10),(15,13),(15,14),(15,15)])
def test_dispatch_identity_membership_and_complete_fields(dispatcher,tmp_path,mask,failure):
    assert dispatcher.field_snapshot(str(tmp_path)+'\\',mask,failure)==0
    payload=(tmp_path/f'war3_reforged_native_{os.getpid()}.bin').read_bytes()
    trainer=module.War3Trainer.__new__(module.War3Trainer)
    if failure not in (0,11,12):
        with pytest.raises(RuntimeError):
            trainer._parse_native_helper_results(payload,2)
        assert len(payload)==trainer._native_helper_command_size()
        return
    results=trainer._parse_native_helper_results(payload,2)
    values=results[0].extra_results
    snapshot=replace(make_snapshot(),handle=7,unit_address=values[0],full_handle=values[1],owner_address=values[2])
    candidate=make_candidate(snapshot)
    trainer._run_native_helper_ops=Mock(return_value=results)
    trainer._selected_components=Mock(side_effect=AssertionError('external component lookup'))
    trainer._looks_like_vtable=Mock(side_effect=AssertionError('heap address heuristic'))
    trainer._inventory_items_from_candidate=Mock(return_value=[])
    memory=Mock()
    for name in ('read','read_u32','read_u64','read_i32','read_f32','regions'):
        getattr(memory,name).side_effect=AssertionError('unexpected external field read')
    fields={f.key:f for f in trainer._unit_fields_from_candidate(memory,candidate)}
    assert fields['armor'].value==12.5 and fields['armor_type'].value==4
    assert ('skill_points' in fields)==bool(mask&2)
    if mask&2:
        assert fields['skill_points'].value==9
        assert [fields[k+'_growth'].value for k in ('strength','intelligence','agility')]==[2.25,3.25,4.25]
        for n in range(1,6):
            assert fields[f'skill{n}_name'].value==0x41303030+n
            assert fields[f'skill{n}_cache_rawcode'].value==0x42303030+n
            assert fields[f'skill{n}_learnable'].value==n
            assert fields[f'skill{n}_requirement'].value==n+9
    assert ('attack1_base1' in fields)==bool(mask&8)
    assert ('attack2_base1' in fields)==bool(mask&8 and failure not in (11,12))
    for n in (1,2):
        if f'attack{n}_base1' in fields:
            assert len([key for key in fields if key.startswith(f'attack{n}_')])==18
            assert fields[f'attack{n}_base1'].value==100+n
            assert fields[f'attack{n}_interval'].value==0.25+n
            assert fields[f'attack{n}_range_buffer'].value==99.5+n
    assert memory.mock_calls==[]
    trainer._selected_components.assert_not_called()
    trainer._looks_like_vtable.assert_not_called()
    trainer._run_native_helper_ops.assert_called_once_with(7,((136,0,values[0],values[1],values[2]),(147,0,0,0,0)))


@pytest.mark.parametrize('change', ['short','old_unit','old_full','old_owner','mask','missing_data','orphan_attack2'])
def test_malformed_or_stale_field_payload_rejected(change):
    candidate=make_candidate(make_snapshot())
    values=[candidate.unit_address,candidate.handle,candidate.owner_address]+[0]*290
    if change=='short': values.pop()
    elif change.startswith('old_'): values[{'old_unit':0,'old_full':1,'old_owner':2}[change]]+=1
    elif change=='mask': values[3]=16
    elif change=='missing_data': values[3]=1
    else: values[14]=1
    with pytest.raises(RuntimeError): module.NativeUnitFieldMemory(candidate,tuple(values))


def test_local_field_snapshot_does_not_read_outside_captured_bytes():
    candidate=make_candidate(make_snapshot())
    values=(candidate.unit_address,candidate.handle,candidate.owner_address)+(0,)*290
    memory=module.NativeUnitFieldMemory(candidate,values)
    for address,size in ((candidate.unit_address,4),(candidate.unit_address+0x2f7,2),(0,0)):
        with pytest.raises(OSError): memory.read(address,size)
