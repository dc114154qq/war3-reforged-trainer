"""Exercise production replacement/rollback with game callbacks that change identity."""
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
from test_native_inventory_dispatch import INVENTORY_HARNESS
from test_native_basic_writes import context
from test_native_snapshot_binding import snapshot_result, inventory_result


TRANSACTION = r'''
static unsigned tx_fault,tx_create_calls,tx_add_calls,tx_destroy_old,tx_destroy_new;
static unsigned tx_live[6],tx_foreign[6];
static uint64_t tx_resolve(uint64_t h) {
    return h>=100 && h<106 && tx_live[h-100] ? (uint64_t)(uintptr_t)inv_objects[h-100] : 0;
}
static uint32_t tx_type(uint64_t h) {
    return tx_resolve(h) ? *(uint32_t *)(inv_objects[h-100]+0x70) : 0;
}
static uint32_t tx_real(uint64_t unit) { if(unit!=7) ++bad_arguments;return 0; }
static uint32_t tx_owned(uint64_t h) {
    if(!tx_resolve(h)) return 0;
    if(tx_foreign[h-100]) return 1;
    for(unsigned n=0;n<6;++n) if(inv_slots[n]==h) return 1;
    return 0;
}
static uint64_t tx_create(uint32_t id,float *x,float *y) {
    ++tx_create_calls;
    if(id!=0x49303032 || *x || *y) ++bad_arguments;
    if(tx_fault==1) return 0;
    tx_live[2]=1;
    *(uint32_t *)(inv_objects[2]+0x70)=tx_fault==2 ? 0x49303039 : id;
    if(tx_fault==5) *(uint64_t *)(object+0x18)+=1;
    if(tx_fault==8) *(uint64_t *)(inv_objects[0]+0x18)+=1;
    return 102;
}
static void tx_detach(uint64_t unit,uint64_t h) {
    if(unit!=7 || !tx_resolve(h) || *(uint64_t *)(object+0x18)!=full) ++bad_arguments;
    if(tx_fault==4) return;
    for(unsigned n=0;n<6;++n) if(inv_slots[n]==h) inv_slots[n]=0;
    if(tx_fault==6) *(uint64_t *)(object+0x18)+=1;
}
static uint8_t tx_add(uint64_t unit,uint64_t obj,int32_t slot,uint8_t notify,uint8_t check) {
    ++tx_add_calls;
    if(unit!=(uint64_t)(uintptr_t)object || slot!=0 || notify!=1 || check ||
       *(uint64_t *)(object+0x18)!=full) ++bad_arguments;
    uint64_t h=obj==(uint64_t)(uintptr_t)inv_objects[2] ? 102 : 100;
    if(inv_slots[slot]) ++bad_arguments; /* never overwrite a claimed slot */
    if(h==100) {
        if(tx_fault==11) return 0;
        inv_slots[slot]=100;return 1;
    }
    if(tx_destroy_old) ++bad_arguments; /* old must still exist until placement verified */
    if(tx_fault==3 || tx_fault==11) return 0;
    if(tx_fault==7) { *(uint64_t *)(object+0x18)+=1;return 0; }
    if(tx_fault==9) { *(uint64_t *)(inv_objects[2]+0x18)+=1;return 0; }
    if(tx_fault==10) { inv_slots[slot]=103;tx_live[3]=1;return 0; }
    if(tx_fault==15) { tx_foreign[0]=1;return 0; }
    if(tx_fault==16) { tx_foreign[2]=1;return 0; }
    if(tx_fault==17) inv_slots[1]=0;
    inv_slots[slot]=h;
    return tx_fault==12 ? 0 : 1;
}
static void tx_destroy(uint64_t h) {
    if(!tx_resolve(h) || tx_owned(h)) ++bad_arguments;
    if(h==100) {
        ++tx_destroy_old;
        if(inv_slots[0]!=102) ++bad_arguments;
    } else if(h==102) ++tx_destroy_new;
    else ++bad_arguments;
    tx_live[h-100]=0;
    if(tx_fault==18 && h==100) *(uint64_t *)(object+0x18)+=1;
}
__declspec(dllexport) DWORD replace_test(const wchar_t *directory,unsigned failure,unsigned empty,unsigned *out) {
    unsigned initial[2];DWORD error=inventory_dispatch(directory,6,empty?2:3,0,initial),bytes;
    NativeCommand cmd={0};wchar_t path[MAX_PATH];HANDLE file;
    if(error) return error;
    command_path(path,MAX_PATH);DeleteFileW(path);
    tx_fault=failure;tx_create_calls=tx_add_calls=tx_destroy_old=tx_destroy_new=0;
    ZeroMemory(tx_live,sizeof(tx_live));ZeroMemory(tx_foreign,sizeof(tx_foreign));
    tx_live[0]=!empty;tx_live[1]=1;
    for(unsigned n=0;n<sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]);++n) {
        const char *name=g_persistent_native_names[n];
        if(!strcmp(name,"CreateItem")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)tx_create;
        if(!strcmp(name,"RemoveItem")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)tx_destroy;
        if(!strcmp(name,"UnitRemoveItem")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)tx_detach;
        if(!strcmp(name,"IsItemOwned")) g_persistent_natives[n].handler=failure==13?0:(uint64_t)(uintptr_t)tx_owned;
        if(!strcmp(name,"GetItemTypeId")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)tx_type;
        if(!strcmp(name,"GetUnitX") || !strcmp(name,"GetUnitY")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)tx_real;
    }
    g_persistent_item_resolver=(uint64_t)(uintptr_t)tx_resolve;
    cmd.magic=WAR3_NATIVE_MAGIC;cmd.version=WAR3_NATIVE_VERSION;cmd.status=WAR3_NATIVE_STATUS_PENDING;
    cmd.op_count=3;cmd.unit_handle=7;
    cmd.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;
    cmd.ops[0].handler=(uint64_t)(uintptr_t)object;cmd.ops[0].arg0=full;cmd.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    cmd.ops[1].kind=WAR3_NATIVE_OP_REPLACE_INVENTORY_ITEM;cmd.ops[1].rawcode=0x49303032;
    cmd.ops[1].handler=(uint64_t)(uintptr_t)tx_add;
    cmd.ops[1].arg0=empty?0:100;cmd.ops[1].arg1=empty?0:inv_full(0);
    cmd.ops[2].kind=WAR3_NATIVE_OP_REPLACE_INVENTORY_CONTEXT;cmd.ops[2].rawcode=0;
    cmd.ops[2].handler=empty?0:(uint64_t)(uintptr_t)inv_objects[0];cmd.ops[2].arg0=empty?0:0x49303031;
    if(failure==14) ++cmd.ops[1].arg1;
    file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();
    BOOL ok=WriteFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);
    if(!ok || bytes!=sizeof(cmd)) return ERROR_WRITE_FAULT;
    run_command();
    out[0]=bad_arguments;out[1]=(unsigned)inv_slots[0];out[2]=(unsigned)inv_slots[1];
    out[3]=tx_live[0];out[4]=tx_live[2];out[5]=tx_destroy_old;out[6]=tx_destroy_new;
    out[7]=tx_create_calls;out[8]=tx_add_calls;
    return 0;
}
'''


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler: pytest.skip('clang required')
    root=tmp_path_factory.mktemp('inventory-transaction');source=root/'test.c';library=root/'test.dll'
    source.write_text(HARNESS.replace('HELPER_SOURCE',(Path(__file__).parent/'tools/war3_native_helper.c').as_posix())
                      +INVENTORY_HARNESS+TRANSACTION,encoding='utf8')
    subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(library),
                    '-luser32','-lkernel32'],check=True,capture_output=True,timeout=60)
    lib=ctypes.CDLL(str(library))
    lib.replace_test.argtypes=[ctypes.c_wchar_p,ctypes.c_uint,ctypes.c_uint,ctypes.POINTER(ctypes.c_uint)]
    lib.replace_test.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)


@pytest.mark.parametrize('failure',range(19))
def test_replace_recovers_only_live_unclaimed_objects(native,tmp_path,failure):
    out=(ctypes.c_uint*9)()
    assert native.replace_test(str(tmp_path)+'\\',failure,0,out)==0
    assert out[0]==0 # ABI, no destruction before success, no occupied-slot overwrite
    trainer=module.War3Trainer.__new__(module.War3Trainer)
    payload=(tmp_path/f'war3_reforged_native_{os.getpid()}.bin').read_bytes()
    if failure:
        with pytest.raises(RuntimeError) as caught:trainer._parse_native_helper_results(payload,3)
        assert 'item_recovery_error=' in str(caught.value) and 'item_cleanup_error=' in str(caught.value)
        if failure==11:assert 'item_recovery_error=1003' in str(caught.value)
    else:
        results=trainer._parse_native_helper_results(payload,3)
        assert results[1].result and results[2].result==0x49303032
    assert out[2]==(0 if failure==17 else 101) # other slots never intentionally rewritten
    if failure in (0,18):
        assert (out[1],out[3],out[4],out[5],out[6])==(102,0,1,1,0)
    else:
        assert out[3]==1 and out[5]==0 # failed replacement never deletes the old item
        expected_slot=103 if failure==10 else 0 if failure in (6,7,11,15) else 100
        assert out[1]==expected_slot
    if failure in (1,13,14): assert out[4]==0 and out[6]==0
    if failure in (2,3,4,5,6,7,8,10,11,12,15,17): assert out[4]==0 and out[6]==1
    if failure in (9,16): assert out[4]==1 and out[6]==0 # invalid or foreign item left untouched
    if failure in (13,14): assert out[7]==out[8]==0


@pytest.mark.parametrize('failure',[0,1,3,12])
def test_empty_slot_create_and_refusal(native,tmp_path,failure):
    out=(ctypes.c_uint*9)()
    assert native.replace_test(str(tmp_path)+'\\',failure,1,out)==0
    assert out[0]==0 and out[2]==101 and out[3]==0 and out[5]==0
    assert out[1]==(0 if failure else 102)
    assert out[4]==(0 if failure else 1)
    payload=(tmp_path/f'war3_reforged_native_{os.getpid()}.bin').read_bytes()
    trainer=module.War3Trainer.__new__(module.War3Trainer)
    if failure:
        with pytest.raises(RuntimeError):trainer._parse_native_helper_results(payload,3)
    else:assert trainer._parse_native_helper_results(payload,3)[2].result==0x49303032


@pytest.mark.parametrize('phase',['refresh','inventory'])
@pytest.mark.parametrize('attribute',['item_addresses','item_ids','item_full_handles'])
def test_changed_display_item_never_reaches_replacement(context,phase,attribute):
    trainer,memory,candidate,snapshot=context
    changed=replace(snapshot,**{attribute:(getattr(snapshot,attribute)[0]+1,0,0,0,0,0)})
    trainer._run_native_helper_ops.side_effect=[[snapshot_result(changed if phase=='refresh' else snapshot)]]
    if phase=='inventory':
        trainer._run_native_helper_ops.side_effect=[[snapshot_result(snapshot)],inventory_result(changed)]
    trainer._set_inventory_slot_item_via_native_handler=Mock(side_effect=AssertionError('unexpected replacement'))
    field=module.UnitMemoryField('inventory_slot_1','item','rawcode',snapshot.item_ids[0],0,'inventory',native_write=True)
    with pytest.raises(RuntimeError,match='changed before writing'):
        trainer._write_inventory_slot_field(memory,candidate,field,0x49303032)
    trainer._set_inventory_slot_item_via_native_handler.assert_not_called()
    assert memory.mock_calls==[]
