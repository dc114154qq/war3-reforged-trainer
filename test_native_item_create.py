"""Production item creation dispatch, including callback-driven identity changes."""
import ctypes
import faulthandler
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
from test_native_selected_context import trainer


CREATE = r'''
static uint8_t create_objects[6][0x1c0],create_wrappers[6][0x98];
static unsigned create_fault,create_calls,create_cleanup;
static uint32_t create_types[6];
static uint64_t create_full(unsigned n) {return 0x334455000100ULL+n;}
static uint64_t create_resolve(uint64_t handle) {
    if(handle>=200 && handle<206)
        return create_fault==19?1:(uint64_t)(uintptr_t)create_objects[handle-200];
    return inv_resolve(handle);
}
static uint64_t create_agent(uint32_t lo,uint32_t hi) {
    uint64_t id=((uint64_t)hi<<32)|lo;
    for(unsigned n=0;n<6;++n) if(id==create_full(n)) return (uint64_t)(uintptr_t)create_wrappers[n];
    return inv_agent(lo,hi);
}
static uint32_t create_type(uint64_t item) {
    if(item>=200 && item<206) return *(uint32_t *)(create_objects[item-200]+0x70);
    return inv_type(item);
}
static int32_t create_charges(uint64_t item) {
    if(item>=200 && item<206) return 7;
    return inv_charges(item);
}
static void create_destroy(uint64_t item) {++create_cleanup;}
static uint64_t create_item(uint64_t unit,uint32_t rawcode) {
    if(unit!=7 || !rawcode || create_calls>=6) {++bad_arguments;return 0;}
    unsigned n=create_calls++;create_types[n]=rawcode;
    if(create_fault==1 || (create_fault==22 && n==1)) return 0;
    if(create_fault==8) return 100;
    if(create_fault==9 && n==1) return 200;
    uint8_t *obj=create_objects[n],*wrapper=create_wrappers[n];
    *(uint64_t *)(obj+0x18)=*(uint64_t *)(wrapper+0x20)=create_full(n);
    *(uint32_t *)(obj+0x70)=rawcode;*(uint32_t *)(obj+0x178)=rawcode;
    *(uint64_t *)(wrapper+0x18)=0x6974656d2b61676cULL;
    *(uint64_t *)(wrapper+0x90)=(uint64_t)(uintptr_t)obj;
    for(unsigned slot=0;slot<inv_capacity;++slot) if(!inv_slots[slot]) {inv_slots[slot]=200+n;break;}
    if(n==0) {
        if(create_fault==2) *(uint32_t *)(obj+0x70)=0x49303039;
        if(create_fault==3) *(uint64_t *)(wrapper+0x90)=0;
        if(create_fault==4) *(uint64_t *)(object+0x18)+=1;
        if(create_fault==5) inv_slots[1]=104;
        if(create_fault==6) {uint64_t x=inv_slots[1];inv_slots[1]=inv_slots[2];inv_slots[2]=x;}
        if(create_fault==7) *(uint64_t *)(inv_objects[1]+0x18)+=10;
        if(create_fault==11) RaiseException(0xe0123456,0,0,NULL);
        if(create_fault==18) inv_capacity=5;
        if(create_fault==20) *(uint64_t *)(obj+0x18)=0;
        if(create_fault==21) {*(uint64_t *)(obj+0x18)=0;inv_slots[3]=0;}
        if(create_fault==24) inv_slots[0]=200;
    }
    if(create_fault==10 && n==1) {*(uint64_t *)(create_objects[0]+0x18)=0;inv_slots[3]=0;}
    if(create_fault==23 && n==1) *(uint64_t *)(object+0x18)+=1;
    return 200+n;
}
__declspec(dllexport) DWORD create_test(const wchar_t *directory,unsigned rawcode,unsigned failure,
                                      unsigned capacity,unsigned occupied,unsigned *out) {
    DWORD setup=inventory_dispatch(directory,capacity,occupied,0,out);
    if(setup) return setup;
    wchar_t path[MAX_PATH];command_path(path,MAX_PATH);
    if(!DeleteFileW(path)) return GetLastError();
    create_fault=failure;create_calls=create_cleanup=0;
    inv_slot_calls=inv_capacity_calls=0;
    ZeroMemory(create_objects,sizeof(create_objects));ZeroMemory(create_wrappers,sizeof(create_wrappers));
    ZeroMemory(create_types,sizeof(create_types));
    if(failure==17) inv_slots[1]=inv_slots[0];
    g_persistent_item_resolver=(uint64_t)(uintptr_t)create_resolve;
    g_persistent_agent_resolver=(uint64_t)(uintptr_t)create_agent;
    for(unsigned n=0;n<sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]);++n) {
        const char *name=g_persistent_native_names[n];
        if(!strcmp(name,"UnitAddItemById") && failure!=12) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)create_item;
        if(!strcmp(name,"GetItemTypeId")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)create_type;
        if(!strcmp(name,"GetItemCharges")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)create_charges;
        if(!strcmp(name,"RemoveItem")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)create_destroy;
    }
    NativeCommand cmd={0};DWORD bytes;
    cmd.magic=WAR3_NATIVE_MAGIC;cmd.version=WAR3_NATIVE_VERSION;cmd.status=WAR3_NATIVE_STATUS_PENDING;
    cmd.unit_handle=7;cmd.op_count=2;
    cmd.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;
    cmd.ops[0].handler=(uint64_t)(uintptr_t)object;cmd.ops[0].arg0=full;
    cmd.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    cmd.ops[1].kind=WAR3_NATIVE_OP_BOUND_ITEM_CREATE;cmd.ops[1].rawcode=rawcode;
    if(failure==13) cmd.ops[0].arg0+=1;
    if(failure==14) cmd.ops[1].handler=(uint64_t)(uintptr_t)create_item;
    if(failure==15) cmd.ops[1].arg0=1;
    if(failure==16) cmd.ops[1].arg1=1;
    HANDLE file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();
    BOOL ok=WriteFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);
    if(!ok || bytes!=sizeof(cmd)) return ERROR_WRITE_FAULT;
    run_command();out[0]=bad_arguments;out[1]=create_calls;out[2]=create_cleanup;
    out[3]=inv_slot_calls;out[4]=inv_capacity_calls;
    for(unsigned n=0;n<6;++n) {out[5+n]=create_types[n];out[11+n]=(unsigned)inv_slots[n];}
    return 0;
}
'''


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler:pytest.skip('clang required')
    root=tmp_path_factory.mktemp('item-create');source=root/'test.c';library=root/'test.dll'
    source.write_text(HARNESS.replace('HELPER_SOURCE',(Path(__file__).parent/'analysis/fixtures/legacy-native-helper.c').as_posix())
                      +INVENTORY_HARNESS+CREATE,encoding='utf8')
    subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(library),
                    '-luser32','-lkernel32'],check=True,capture_output=True,timeout=60)
    lib=ctypes.CDLL(str(library))
    lib.create_test.argtypes=[ctypes.c_wchar_p,*([ctypes.c_uint]*4),ctypes.POINTER(ctypes.c_uint)]
    lib.create_test.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)


def dispatch(native,path,rawcode=0,failure=0,capacity=6,occupied=7):
    out=(ctypes.c_uint*17)();enabled=faulthandler.is_enabled()
    if failure==11 and enabled:faulthandler.disable()
    try:assert native.create_test(str(path)+'\\',rawcode,failure,capacity,occupied,out)==0
    finally:
        if failure==11 and enabled:faulthandler.enable()
    assert out[0]==out[2]==0 # no invalid calls or guessed cleanup
    assert out[3]<=84 and out[4]<=14
    return out,(path/f'war3_reforged_native_{os.getpid()}.bin').read_bytes()


def parse(payload):return module.War3Trainer.__new__(module.War3Trainer)._parse_native_helper_results(payload,2)


@pytest.mark.parametrize('capacity,occupied',[(0,0),(1,0),(1,1),(6,0),(6,1),(6,33),(6,63)])
def test_duplicate_original_items_only_with_empty_slots_or_ground(native,tmp_path,capacity,occupied):
    out,payload=dispatch(native,tmp_path,capacity=capacity,occupied=occupied)
    count=occupied.bit_count();result=parse(payload)[1]
    assert result.result==out[1]==count
    assert result.arg0==(199+count if count else 0)
    assert list(out[5:5+count])==[0x49303031]*count
    for slot in range(6):
        if occupied&(1<<slot):assert out[11+slot]==100+slot


@pytest.mark.parametrize('capacity,occupied',[(0,0),(6,0),(6,63)])
def test_add_type_without_existing_instance_or_inventory_space(native,tmp_path,capacity,occupied):
    out,payload=dispatch(native,tmp_path,rawcode=0x49303032,capacity=capacity,occupied=occupied)
    result=parse(payload)[1]
    assert result.result==out[1]==1 and result.arg0==200
    assert out[5]==0x49303032 and out[3]==out[4]==0


@pytest.mark.parametrize('failure',[1,3,4,5,6,7,11,12,13,14,15,16,17,18,19,20,22,23,24])
def test_creation_errors_do_not_continue_or_destroy_guessed_handles(native,tmp_path,failure):
    out,payload=dispatch(native,tmp_path,failure=failure)
    verified=1 if failure in (22,23) else 0
    calls=0 if failure in (12,13,14,15,16,17) else verified+1
    with pytest.raises(RuntimeError,match=f'item_creations_acknowledged={verified}'):parse(payload)
    assert out[1]==calls


@pytest.mark.parametrize('failure',[1,4,11,12,13,14,15,16])
def test_single_add_rejects_invalid_unit_or_engine_refusal(native,tmp_path,failure):
    out,payload=dispatch(native,tmp_path,rawcode=0x49303032,failure=failure)
    with pytest.raises(RuntimeError,match='item_creations_acknowledged=0'):parse(payload)
    assert out[1]==int(failure not in (12,13,14,15,16))


@pytest.mark.parametrize('failure',[2,8,9,10,21])
def test_map_can_transform_merge_or_consume_new_copies(native,tmp_path,failure):
    out,payload=dispatch(native,tmp_path,failure=failure)
    assert parse(payload)[1].result==out[1]==3
    assert list(out[11:14])==[100,101,102]


def test_single_add_keeps_engine_ack_when_trigger_consumes_item(native,tmp_path):
    out,payload=dispatch(native,tmp_path,rawcode=0x49303032,failure=21)
    assert parse(payload)[1].result==out[1]==1 and parse(payload)[1].arg0==200


@pytest.mark.parametrize('rawcode',[0,0x49303032])
def test_public_routing_and_command_serializer(trainer,rawcode):
    trainer._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(136,1),
        module.NativeHelperOpResult(168,1 if rawcode else 3,arg0=200)])
    if rawcode:assert trainer.add_item_to_selected_unit('I002')==200
    else:assert trainer.duplicate_selected_inventory_items()==3
    snapshot=trainer.persistent_native_selected_snapshots.return_value[0]
    ops=((136,0,snapshot.unit_address,snapshot.full_handle,snapshot.owner_address),(168,rawcode,0,0,0))
    trainer._run_native_helper_ops.assert_called_once_with(snapshot.handle,ops)
    trainer._process_memory.assert_not_called()
    trainer._native_helper_command_path=Mock(return_value='offline-command');trainer._write_native_helper_command=Mock()
    trainer._native_helper_batch_hook=1;trainer._native_helper_batch_thread_id=threading.get_ident()
    trainer._wait_native_helper_result=Mock(return_value=[]);trainer._run_native_helper_ops_locked(snapshot.handle,ops)
    payload=trainer._write_native_helper_command.call_args.args[1]
    base=trainer.NATIVE_HELPER_HEADER_STRUCT.size;size=trainer.NATIVE_HELPER_OP_STRUCT.size
    for n,op in enumerate(ops):assert trainer.NATIVE_HELPER_OP_STRUCT.unpack_from(payload,base+n*size)[:5]==op


@pytest.mark.parametrize('rawcode',[0,0x49303032])
@pytest.mark.parametrize('returned',[[],[module.NativeHelperOpResult(136,1)],
    [module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(167,1,arg0=200)],
    [module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(168,7,arg0=200)],
    [module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(168,1)],
    [module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(168,0,arg0=200)]])
def test_bad_ack_is_rejected(trainer,rawcode,returned):
    trainer._run_native_helper_ops=Mock(return_value=returned)
    with pytest.raises(RuntimeError):trainer._run_bound_item_create(rawcode)


def test_empty_duplicate_success_and_add_refusal(trainer):
    trainer._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(168,0)])
    assert trainer.duplicate_selected_inventory_items()==0
    with pytest.raises(RuntimeError):trainer.add_item_to_selected_unit('I002')


def test_invalid_rawcode_precedes_selection(trainer):
    with pytest.raises(ValueError):trainer.add_item_to_selected_unit(0)
    trainer.persistent_native_selected_snapshots.assert_not_called()


def test_bound_selection_reused_for_creation(trainer):
    selected=trainer._selected_candidates_snapshot(None)
    trainer._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(168,1,arg0=200)])
    candidate,handle=selected[0]
    with trainer._bound_elephant_selection(candidate,handle):assert trainer.add_item_to_selected_unit('I002')==200
    trainer.persistent_native_selected_snapshots.assert_called_once_with()
    assert trainer._run_native_helper_ops.call_args.args[0]==handle
