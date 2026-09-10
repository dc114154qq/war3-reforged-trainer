"""Production slot resolver and replacement using a relocated synthetic image."""
import ctypes
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
from unittest.mock import Mock

import pytest
import war3_reforged_trainer as module
from test_native_identity_guard import HARNESS
from test_native_inventory_dispatch import INVENTORY_HARNESS
from test_native_inventory_transaction import TRANSACTION
from test_native_snapshot_binding import make_candidate,make_snapshot,snapshot_result,inventory_result


PREFIX=r'''
#include <stdint.h>
static uint8_t *slot_image;
static HMODULE slot_module(LPCWSTR name) {return slot_image?(HMODULE)slot_image:GetModuleHandleW(name);}
#define GetModuleHandleW slot_module
'''

RESOLVER=r'''
static uint8_t slot_context[0x80],slot_bucket[24],slot_node[0x48];
static unsigned slot_fault;
static void *slot_get_context(int32_t id) {
    if(id!=5) ++bad_arguments;
    return slot_fault==1?NULL:slot_context;
}
static uint32_t slot_hash_name(const char *name) {
    if(strcmp(name,"UnitAddItemToSlotById")) ++bad_arguments;
    return 3;
}
static void slot_jump(uint8_t *code,void *target) {
    code[0]=0x48;code[1]=0xb8;memcpy(code+2,&target,8);code[10]=0xff;code[11]=0xe0;
}
__declspec(dllexport) DWORD slot_test(const wchar_t *directory,unsigned failure,unsigned tx_failure,unsigned empty,
                                    const uint8_t *bytes,unsigned size,uint64_t *out) {
    /* Initialize fake engine objects with the existing transaction fixture.
       Missing IsItemOwned rejects before mutation; then restore that function. */
    unsigned initial[9];DWORD error=replace_test(directory,13,empty,initial);
    if(error) return error;
    tx_fault=tx_failure;
    for(unsigned n=0;n<sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]);++n)
        if(!strcmp(g_persistent_native_names[n],"IsItemOwned"))
            g_persistent_natives[n].handler=(uint64_t)(uintptr_t)tx_owned;
    slot_image=VirtualAlloc(NULL,0x1180000,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE);
    if(!slot_image) return ERROR_OUTOFMEMORY;
    if(size<WAR3_SLOT_CODE_SIZE) {VirtualFree(slot_image,0,MEM_RELEASE);slot_image=NULL;return ERROR_INVALID_PARAMETER;}
    ZeroMemory(slot_context,sizeof(slot_context));ZeroMemory(slot_bucket,sizeof(slot_bucket));ZeroMemory(slot_node,sizeof(slot_node));
    slot_fault=failure;
    slot_jump(slot_image+WAR3_BOOTSTRAP_CONTEXT_RVA,(void *)slot_get_context);
    slot_jump(slot_image+WAR3_BOOTSTRAP_HASH_RVA,(void *)slot_hash_name);
    slot_jump(slot_image+WAR3_SLOT_ADD_RVA,(void *)tx_add);
    memcpy(slot_image+WAR3_SLOT_HANDLER_RVA,bytes,WAR3_SLOT_CODE_SIZE);
    *(uint8_t **)(slot_context+0x28+0x30)=slot_bucket;
    *(uintptr_t *)(slot_bucket+0x10)=(uintptr_t)slot_node;
    *(uint32_t *)slot_node=3;*(uintptr_t *)(slot_node+8)=1;
    *(const char **)(slot_node+0x28)="UnitAddItemToSlotById";
    *(uint64_t *)(slot_node+0x30)=(uint64_t)(uintptr_t)(slot_image+WAR3_SLOT_HANDLER_RVA);
    *(const char **)(slot_node+0x40)="(Hunit;II)B";
    /* Model an already image-validated bootstrap; image validation itself is
       covered in test_native_table_bootstrap. Never execute captured game code. */
    g_bootstrap_module=slot_image;
    if(failure==2) *(const char **)(slot_node+0x40)="(Hunit;II)V";
    if(failure==3) *(uint64_t *)(slot_node+0x30)+=1;
    if(failure==4) slot_image[WAR3_SLOT_HANDLER_RVA+0x80]^=1;
    if(failure==5) {DWORD old;VirtualProtect(slot_image+WAR3_SLOT_ADD_RVA,16,PAGE_READWRITE,&old);}
    if(failure==6) slot_image[WAR3_SLOT_HANDLER_RVA+WAR3_SLOT_CALL_OFFSET+1]^=1;
    if(failure==7) g_bootstrap_module=NULL; /* invalid unvalidated image */
    if(failure==8) slot_image[WAR3_SLOT_HANDLER_RVA+WAR3_SLOT_CODE_SIZE-1]^=1;
    FlushInstructionCache(GetCurrentProcess(),slot_image,0x1180000);
    NativeCommand cmd={0};cmd.unit_handle=7;cmd.op_count=3;
    cmd.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;cmd.ops[0].handler=(uint64_t)(uintptr_t)object;
    cmd.ops[0].arg0=full;cmd.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    cmd.ops[1].kind=WAR3_NATIVE_OP_REPLACE_INVENTORY_ITEM;cmd.ops[1].rawcode=0x49303032;
    cmd.ops[1].arg0=empty?0:100;cmd.ops[1].arg1=empty?0:inv_full(0);
    cmd.ops[2].kind=WAR3_NATIVE_OP_REPLACE_INVENTORY_CONTEXT;
    cmd.ops[2].handler=empty?0:(uint64_t)(uintptr_t)inv_objects[0];cmd.ops[2].arg0=empty?0:0x49303031;
    error=war3_replace_inventory_item(&cmd);
    out[0]=bad_arguments;out[1]=tx_create_calls;out[2]=tx_add_calls;out[3]=tx_destroy_old;out[4]=tx_destroy_new;
    out[5]=inv_slots[0];out[6]=inv_slots[1];out[7]=cmd.ops[1].result;out[8]=cmd.ops[2].result;
    g_bootstrap_module=NULL;VirtualFree(slot_image,0,MEM_RELEASE);slot_image=NULL;
    return error;
}
__declspec(dllexport) DWORD slot_zero_dispatch(const wchar_t *directory,unsigned *out) {
    DWORD error=replace_test(directory,13,0,out);if(error) return error;
    NativeCommand cmd;wchar_t path[MAX_PATH];DWORD bytes;
    command_path(path,MAX_PATH);HANDLE file=CreateFileW(path,GENERIC_READ|GENERIC_WRITE,0,NULL,OPEN_EXISTING,0,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();
    ReadFile(file,&cmd,sizeof(cmd),&bytes,NULL);cmd.status=WAR3_NATIVE_STATUS_PENDING;cmd.ops[1].handler=0;
    SetFilePointer(file,0,NULL,FILE_BEGIN);WriteFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);
    run_command();
    file=CreateFileW(path,GENERIC_READ,0,NULL,OPEN_EXISTING,0,NULL);ReadFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);
    out[0]=tx_create_calls;out[1]=tx_add_calls;
    return cmd.last_error;
}
'''


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler:pytest.skip('clang required')
    root=tmp_path_factory.mktemp('slot-resolver');source=root/'test.c';library=root/'test.dll'
    harness=HARNESS.replace('#include "HELPER_SOURCE"',PREFIX+'\n#include "HELPER_SOURCE"\n#undef GetModuleHandleW')
    source.write_text(harness.replace('HELPER_SOURCE',(Path(__file__).parent/'tools/war3_native_helper.c').as_posix())
                      +INVENTORY_HARNESS+TRANSACTION+RESOLVER,encoding='utf8')
    subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(library),'-luser32','-lkernel32'],check=True,capture_output=True,timeout=60)
    lib=ctypes.CDLL(str(library))
    lib.slot_test.argtypes=[ctypes.c_wchar_p,*([ctypes.c_uint]*3),ctypes.c_void_p,ctypes.c_uint,ctypes.POINTER(ctypes.c_uint64)]
    lib.slot_test.restype=ctypes.c_uint
    lib.slot_zero_dispatch.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_uint)];lib.slot_zero_dispatch.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)


def run(native,path,failure=0,tx_failure=0,empty=0):
    records=json.loads((Path(__file__).parent/'tools/native-call-contracts-23745.json').read_text())['contracts']
    code=bytes.fromhex(next(r['code'] for r in records if r['name']=='UnitAddItemToSlotById'))
    buf=ctypes.create_string_buffer(code);out=(ctypes.c_uint64*9)()
    error=native.slot_test(str(path)+'\\',failure,tx_failure,empty,buf,len(code),out)
    assert out[0]==0 and out[6]==101
    return error,out


@pytest.mark.parametrize('empty',[0,1])
@pytest.mark.parametrize('tx_failure',[0,1,3,4,11])
def test_real_resolver_reaches_replacement_and_safe_recovery(native,tmp_path,empty,tx_failure):
    error,out=run(native,tmp_path,tx_failure=tx_failure,empty=empty)
    if tx_failure==0:
        assert error==0 and out[5]==102 and out[7] and out[8]==0x49303032
        assert out[3]==1-empty and out[4]==0
    elif empty and tx_failure==4:
        assert error==0 and out[5]==102
    else:
        assert error and out[3]==0
        assert out[5]==(0 if empty or tx_failure==11 else 100)


@pytest.mark.parametrize('failure',range(1,9))
def test_bad_image_table_code_or_target_prevents_creation(native,tmp_path,failure):
    error,out=run(native,tmp_path,failure=failure)
    assert error and list(out[1:5])==[0]*4 and out[5]==100


def test_zero_handler_dispatch_reaches_image_validation_without_mutation(native,tmp_path):
    out=(ctypes.c_uint*9)()
    assert native.slot_zero_dispatch(str(tmp_path)+'\\',out)==193 # host is not game PE
    assert list(out[:2])==[0,0]


def test_controller_submits_identity_only_and_accepts_zero_handler_in_serializer():
    subject=module.War3Trainer.__new__(module.War3Trainer);candidate=make_candidate(make_snapshot())
    subject._rel32_calls_in_function=Mock(side_effect=AssertionError('External code read'))
    subject._query_native_table_handlers=Mock(side_effect=AssertionError('Controller lookup'))
    subject._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(136,1),
        module.NativeHelperOpResult(150,0x999000),module.NativeHelperOpResult(151,0x49303032)])
    assert subject._set_inventory_slot_item_via_native_handler(None,candidate,0,0x49303032)[1]==0x999000
    handle,ops=subject._run_native_helper_ops.call_args.args
    assert ops[1][2]==0 and handle==candidate.native_snapshot.handle
    subject._native_helper_command_path=Mock(return_value='offline-command');subject._write_native_helper_command=Mock()
    subject._native_helper_batch_hook=1;subject._native_helper_batch_thread_id=threading.get_ident();subject._wait_native_helper_result=Mock(return_value=[])
    subject._run_native_helper_ops_locked(handle,ops)
    payload=subject._write_native_helper_command.call_args.args[1];base=subject.NATIVE_HELPER_HEADER_STRUCT.size;size=subject.NATIVE_HELPER_OP_STRUCT.size
    assert subject.NATIVE_HELPER_OP_STRUCT.unpack_from(payload,base+size)[:5]==ops[1]
    subject._rel32_calls_in_function.assert_not_called()


@pytest.mark.parametrize('cls',[module.War3Trainer,module.BackupReadWar3Trainer])
@pytest.mark.parametrize('pinned',[False,True])
def test_public_item_field_write_has_no_external_memory_or_code_lookup(cls,pinned):
    subject=cls.__new__(cls);original=make_snapshot();state=[original];writes=[]
    subject._unit_owner_index={};subject._last_persistent_native_snapshots=();subject._item_object_cache={}
    subject.persistent_native_init=Mock()
    subject.persistent_native_selected_snapshots=Mock(return_value=(original,))
    subject._unit_fields_from_candidate=Mock(return_value=[module.UnitMemoryField(
        'inventory_slot_1','slot','rawcode',original.item_ids[0],0,'inventory',native_write=True)])
    for name in ('_process_memory','_rel32_calls_in_function','_query_native_table_handlers','_selected_components'):
        setattr(subject,name,Mock(side_effect=AssertionError('Unexpected external dependency: '+name)))
    def command(handle,ops):
        if ops[0][0] in (133,155):return [snapshot_result(state[0])]
        assert handle==original.handle
        if ops[1][0]==149:return inventory_result(state[0])
        assert ops[1][0]==150 and ops[1][2]==0
        assert ops[1][3:]==(original.item_handles[0],original.item_full_handles[0])
        writes.append(ops)
        state[0]=replace(original,item_ids=(0x49303032,)+(0,)*5,item_handles=(102,)+(0,)*5,
                         item_full_handles=(0x223300000066,)+(0,)*5,item_addresses=(0x999000,)+(0,)*5)
        return [module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(150,0x999000),
                module.NativeHelperOpResult(151,0x49303032)]
    subject._run_native_helper_ops=Mock(side_effect=command)
    if pinned:
        result=subject.write_unit_field_by_identity_win10(original.full_handle,original.owner_address,
            original.unit_address,'inventory_slot_1','I002')
    else:result=subject.write_selected_unit_field('inventory_slot_1','I002')
    assert result.value==0x49303032 and len(writes)==1
    subject._process_memory.assert_not_called();subject._rel32_calls_in_function.assert_not_called()
    if pinned:subject.persistent_native_selected_snapshots.assert_not_called()
    else:subject.persistent_native_selected_snapshots.assert_called_once_with()
