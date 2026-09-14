"""Execute production inventory batches against mutating engine callbacks."""
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


BATCH = r'''
static unsigned batch_fault,batch_calls,batch_targets,batch_mode;
static int32_t batch_charges[6];
static int32_t batch_get(uint64_t item) {return batch_charges[item-100];}
static void batch_change(uint64_t item,int32_t quantity) {
    if(item<100 || item>=106) {++bad_arguments;return;}
    ++batch_calls;batch_targets|=1u<<(item-100);
    if(batch_mode==1) batch_charges[item-100]=quantity;
    else for(unsigned n=0;n<6;++n) if(inv_slots[n]==item) inv_slots[n]=0;
    if(batch_calls==1) {
        if(batch_fault==1) inv_slots[1]=104; /* valid replacement */
        if(batch_fault==2) {uint64_t x=inv_slots[1];inv_slots[1]=inv_slots[2];inv_slots[2]=x;}
        if(batch_fault==3) *(uint64_t *)(object+0x18)+=1;
        if(batch_fault==4) inv_capacity=5;
        if(batch_fault==5) inv_slots[5]=105;
        if(batch_fault==6) batch_charges[item-100]=quantity-1;
        if(batch_fault==8) RaiseException(0xe0123456,0,0,NULL);
        if(batch_fault==9) inv_slots[0]=item; /* engine refused removal */
        if(batch_fault==10) *(uint64_t *)(inv_objects[1]+0x18)+=9;
        if(batch_fault==11) *(uint64_t *)(inv_wrappers[1]+0x90)=0;
    }
    if(batch_calls==2 && batch_fault==7) batch_charges[0]-=1;
}
static void batch_remove(uint64_t item) {batch_change(item,0);}
static void batch_set(uint64_t item,int32_t quantity) {batch_change(item,quantity);}
static void batch_drop(uint64_t unit,uint64_t item) {
    if(unit!=7) ++bad_arguments;
    batch_change(item,0);
}
__declspec(dllexport) DWORD batch_test(const wchar_t *directory,unsigned mode,unsigned failure,
                                     unsigned capacity,unsigned occupied,uint64_t quantity,unsigned *out) {
    DWORD setup=inventory_dispatch(directory,capacity,occupied,0,out);
    if(setup) return setup;
    wchar_t path[MAX_PATH];command_path(path,MAX_PATH);
    if(!DeleteFileW(path)) return GetLastError();
    batch_fault=failure;batch_mode=mode;batch_calls=batch_targets=0;
    inv_slot_calls=inv_capacity_calls=0;
    for(unsigned n=0;n<6;++n) batch_charges[n]=3+n;
    if(failure==12) inv_slots[1]=inv_slots[0];
    for(unsigned n=0;n<sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]);++n) {
        const char *name=g_persistent_native_names[n];
        if(!strcmp(name,"GetItemCharges")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)batch_get;
        if(!strcmp(name,"RemoveItem")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)batch_remove;
        if(!strcmp(name,"SetItemCharges")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)batch_set;
        if(!strcmp(name,"UnitRemoveItem")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)batch_drop;
        if(failure==13 && ((!strcmp(name,"RemoveItem") && mode==0) ||
                          (!strcmp(name,"SetItemCharges") && mode==1) ||
                          (!strcmp(name,"UnitRemoveItem") && mode==2))) g_persistent_natives[n].handler=0;
    }
    NativeCommand cmd={0};DWORD bytes;
    cmd.magic=WAR3_NATIVE_MAGIC;cmd.version=WAR3_NATIVE_VERSION;cmd.status=WAR3_NATIVE_STATUS_PENDING;
    cmd.unit_handle=7;cmd.op_count=2;
    cmd.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;
    cmd.ops[0].handler=(uint64_t)(uintptr_t)object;cmd.ops[0].arg0=full;
    cmd.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    cmd.ops[1].kind=WAR3_NATIVE_OP_BOUND_INVENTORY_BATCH;
    cmd.ops[1].rawcode=mode;cmd.ops[1].arg0=quantity;
    if(failure==14) cmd.ops[0].arg0+=1;
    if(failure==15) cmd.ops[1].handler=(uint64_t)(uintptr_t)batch_set;
    if(failure==16) cmd.ops[1].arg1=1;
    HANDLE file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();
    BOOL ok=WriteFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);
    if(!ok || bytes!=sizeof(cmd)) return ERROR_WRITE_FAULT;
    run_command();out[0]=bad_arguments;out[1]=batch_calls;out[2]=batch_targets;
    out[3]=inv_slot_calls;out[4]=inv_capacity_calls;
    out[5]=0;for(unsigned n=0;n<6;++n) if(inv_slots[n]) out[5]|=1u<<n;
    for(unsigned n=0;n<6;++n) out[6+n]=(unsigned)batch_charges[n];
    return 0;
}
'''


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler: pytest.skip('clang required')
    root=tmp_path_factory.mktemp('inventory-batch');source=root/'test.c';library=root/'test.dll'
    source.write_text(HARNESS.replace('HELPER_SOURCE',(Path(__file__).parent/'analysis/fixtures/legacy-native-helper.c').as_posix())
                      +INVENTORY_HARNESS+BATCH,encoding='utf8')
    subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(library),
                    '-luser32','-lkernel32'],check=True,capture_output=True,timeout=60)
    lib=ctypes.CDLL(str(library))
    lib.batch_test.argtypes=[ctypes.c_wchar_p,*([ctypes.c_uint]*4),ctypes.c_uint64,ctypes.POINTER(ctypes.c_uint)]
    lib.batch_test.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)


def dispatch(native,path,mode=1,failure=0,capacity=6,occupied=7,quantity=None):
    out=(ctypes.c_uint*12)();enabled=faulthandler.is_enabled()
    if failure==8 and enabled:faulthandler.disable()
    try:
        assert native.batch_test(str(path)+'\\',mode,failure,capacity,occupied,
                                 (17 if mode==1 else 0) if quantity is None else quantity,out)==0
    finally:
        if failure==8 and enabled:faulthandler.enable()
    assert out[0]==0
    assert out[3]<=12*7 and out[4]<=2*7
    return out,(path/f'war3_reforged_native_{os.getpid()}.bin').read_bytes()


def parse(payload):return module.War3Trainer.__new__(module.War3Trainer)._parse_native_helper_results(payload,2)


@pytest.mark.parametrize('mode',[0,1,2])
@pytest.mark.parametrize('capacity,occupied',[(0,0),(1,0),(1,1),(6,0),(6,33),(6,63)])
def test_full_sparse_empty_and_nonhero_inventory(native,tmp_path,mode,capacity,occupied):
    out,payload=dispatch(native,tmp_path,mode=mode,capacity=capacity,occupied=occupied)
    count=occupied.bit_count()
    assert parse(payload)[1].result==count
    assert out[1]==count and out[2]==occupied
    assert out[5]==(occupied if mode==1 else 0)
    if mode==1:
        assert list(out[6:])==[17 if occupied&(1<<n) else 3+n for n in range(6)]


@pytest.mark.parametrize('mode',[0,1,2])
@pytest.mark.parametrize('failure',[1,2,3,4,5,8,10,11,12,13,14,15,16])
def test_changed_membership_identity_and_bad_command_stop_before_next_item(native,tmp_path,mode,failure):
    out,payload=dispatch(native,tmp_path,mode=mode,failure=failure)
    with pytest.raises(RuntimeError,match='inventory_verified=0'):parse(payload)
    assert out[1]==out[2]==int(failure<12)


@pytest.mark.parametrize('failure,verified,calls',[(6,0,1),(7,1,2)])
def test_quantity_readback_includes_prior_completed_items(native,tmp_path,failure,verified,calls):
    out,payload=dispatch(native,tmp_path,failure=failure)
    with pytest.raises(RuntimeError,match=f'inventory_verified={verified}'):parse(payload)
    assert out[1]==calls and out[2]==(1<<calls)-1


@pytest.mark.parametrize('mode',[0,2])
def test_engine_refused_removal_stops_batch(native,tmp_path,mode):
    out,payload=dispatch(native,tmp_path,mode=mode,failure=9)
    with pytest.raises(RuntimeError,match='inventory_verified=0'):parse(payload)
    assert out[1]==out[2]==1


@pytest.mark.parametrize('mode,quantity',[(3,0),(0,1),(2,1),(1,0),(1,1000000001),(1,0xffffffffffffffff)])
def test_invalid_mode_or_quantity_never_mutates(native,tmp_path,mode,quantity):
    out,payload=dispatch(native,tmp_path,mode=mode,quantity=quantity)
    with pytest.raises(RuntimeError):parse(payload)
    assert out[1]==out[2]==0


@pytest.mark.parametrize('quantity',[1,1000000000])
def test_quantity_limits_reach_engine_exactly(native,tmp_path,quantity):
    out,payload=dispatch(native,tmp_path,quantity=quantity)
    assert parse(payload)[1].result==3 and list(out[6:9])==[quantity]*3


@pytest.mark.parametrize('method,mode,args',[
    ('clear_selected_unit_inventory',0,()),('set_selected_inventory_charges',1,(17,)),
    ('drop_selected_inventory_items',2,())])
def test_public_api_one_bound_command_and_serialization(trainer,method,mode,args):
    trainer._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(167,3)])
    assert getattr(trainer,method)(*args)==3
    snapshot=trainer.persistent_native_selected_snapshots.return_value[0]
    ops=((136,0,snapshot.unit_address,snapshot.full_handle,snapshot.owner_address),(167,mode,0,17 if args else 0,0))
    trainer._run_native_helper_ops.assert_called_once_with(snapshot.handle,ops)
    trainer._process_memory.assert_not_called()
    trainer._native_helper_command_path=Mock(return_value='offline-command');trainer._write_native_helper_command=Mock()
    trainer._native_helper_batch_hook=1;trainer._native_helper_batch_thread_id=threading.get_ident()
    trainer._wait_native_helper_result=Mock(return_value=[]);trainer._run_native_helper_ops_locked(snapshot.handle,ops)
    payload=trainer._write_native_helper_command.call_args.args[1]
    base=trainer.NATIVE_HELPER_HEADER_STRUCT.size
    for n,op in enumerate(ops):
        assert trainer.NATIVE_HELPER_OP_STRUCT.unpack_from(payload,base+n*trainer.NATIVE_HELPER_OP_STRUCT.size)[:5]==op


@pytest.mark.parametrize('quantity',[0,-1,1000000001])
def test_invalid_quantity_precedes_selection(trainer,quantity):
    with pytest.raises(ValueError):trainer.set_selected_inventory_charges(quantity)
    trainer.persistent_native_selected_snapshots.assert_not_called()


@pytest.mark.parametrize('returned',[[],[module.NativeHelperOpResult(136,1)],
    [module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(149,3)],
    [module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(167,7)]])
def test_bad_ack_is_not_success(trainer,returned):
    trainer._run_native_helper_ops=Mock(return_value=returned)
    with pytest.raises(RuntimeError):trainer.clear_selected_unit_inventory()


def test_bound_selection_is_retained(trainer):
    selected=trainer._selected_candidates_snapshot(None)
    trainer._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(167,1)])
    candidate,handle=selected[0]
    with trainer._bound_elephant_selection(candidate,handle):
        assert trainer.drop_selected_inventory_items()==1
    trainer.persistent_native_selected_snapshots.assert_called_once_with()
    assert trainer._run_native_helper_ops.call_args.args[0]==handle
