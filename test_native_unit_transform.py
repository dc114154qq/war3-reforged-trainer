"""Production scale/position/ownership dispatch with full selected identity."""
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
from test_native_selected_context import trainer


TRANSFORM = r'''
static unsigned tr_fault,tr_calls,tr_queries,tr_local_calls;
static uint64_t tr_player;
static float tr_x,tr_y,tr_z;
static void tr_changed(void) {
    ++tr_calls;
    if(tr_fault==5) *(uint64_t *)(object+0x18)+=1ULL<<32;
    if(tr_fault==6) *(uint64_t *)(owner+0x90)=0;
    if(tr_fault==7) fault=1;
    if(tr_fault==8) RaiseException(0xe0123456,0,0,NULL);
}
static void tr_scale(uint64_t unit,float *x,float *y,float *z) {
    if(unit!=7 || x==y || x==z || y==z || *x!=*y || *y!=*z) ++bad_arguments;
    tr_x=*x;tr_y=*y;tr_z=*z;tr_changed();
}
static void tr_position(uint64_t unit,float *x,float *y) {
    if(unit!=7 || x==y) ++bad_arguments;
    tr_x=*x;tr_y=*y;tr_changed();
}
static uint64_t tr_local(void) {
    ++tr_local_calls;
    if(tr_fault==10) *(uint64_t *)(object+0x18)+=1;
    if(tr_fault==15) RaiseException(0xe0123456,0,0,NULL);
    return tr_fault==9?0:23;
}
static void tr_owner(uint64_t unit,uint64_t player,uint32_t color) {
    if(unit!=7 || player!=23 || color!=1) ++bad_arguments;
    if(tr_fault!=11) tr_player=player;
    tr_changed();
}
static uint64_t tr_get_owner(uint64_t unit) {
    if(unit!=7) ++bad_arguments;
    ++tr_queries;
    if(tr_fault==12) *(uint64_t *)(object+0x18)+=1;
    if(tr_fault==13) RaiseException(0xe0123456,0,0,NULL);
    return tr_player;
}
__declspec(dllexport) DWORD transform_test(const wchar_t *directory,unsigned kind,unsigned failure,
                                         unsigned xbits,uint64_t ybits,unsigned repeat,unsigned *out) {
    NativeCommand cmd={0};DWORD bytes;wchar_t path[MAX_PATH];
    if(wcslen(directory)>=MAX_PATH-1 || repeat<1 || repeat>2) return ERROR_INVALID_PARAMETER;
    wcscpy(test_directory,directory);ZeroMemory(object,sizeof(object));ZeroMemory(owner,sizeof(owner));
    *(uint64_t *)(object+0x18)=full;*(uint64_t *)(owner+0x18)=0x2b7733752b61676cULL;
    *(uint64_t *)(owner+0x20)=full;*(uint64_t *)(owner+0x90)=(uint64_t)(uintptr_t)object;
    fault=bad_arguments=tr_calls=tr_queries=tr_local_calls=0;tr_fault=failure;
    tr_x=tr_y=tr_z=0;tr_player=13;
    g_persistent_unit_resolver=(uint64_t)(uintptr_t)fake_unit;g_persistent_agent_resolver=(uint64_t)(uintptr_t)fake_agent;
    cmd.magic=WAR3_NATIVE_MAGIC;cmd.version=WAR3_NATIVE_VERSION;cmd.status=WAR3_NATIVE_STATUS_PENDING;
    cmd.unit_handle=7;cmd.op_count=repeat+1;
    cmd.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;
    cmd.ops[0].handler=(uint64_t)(uintptr_t)object;cmd.ops[0].arg0=full;cmd.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    for(unsigned n=1;n<=repeat;++n) {
        NativeOp *op=&cmd.ops[n];op->kind=kind;op->rawcode=xbits;
        if(kind==75) op->handler=(uint64_t)(uintptr_t)tr_scale;
        if(kind==94) {op->handler=(uint64_t)(uintptr_t)tr_position;op->arg0=ybits;}
        if(kind==79) {
            op->handler=(uint64_t)(uintptr_t)tr_local;op->arg0=(uint64_t)(uintptr_t)tr_owner;
            op->arg1=(uint64_t)(uintptr_t)tr_get_owner;
        }
        if(failure==2) op->handler=(uint64_t)(uintptr_t)object;
        if(failure==3) op->arg0=1;
        if(failure==4) op->arg1=1;
    }
    if(failure==1) cmd.ops[0].arg0+=1;
    command_path(path,MAX_PATH);
    HANDLE file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();
    BOOL ok=WriteFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);
    if(!ok || bytes!=sizeof(cmd)) return ERROR_WRITE_FAULT;
    run_command();out[0]=bad_arguments;out[1]=tr_calls;out[2]=tr_queries;out[3]=tr_local_calls;
    memcpy(out+4,&tr_x,4);memcpy(out+5,&tr_y,4);memcpy(out+6,&tr_z,4);out[7]=(unsigned)tr_player;
    return 0;
}
'''


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler:pytest.skip('clang required')
    root=tmp_path_factory.mktemp('unit-transform');source=root/'test.c';library=root/'test.dll'
    source.write_text(HARNESS.replace('HELPER_SOURCE',(Path(__file__).parent/'analysis/fixtures/legacy-native-helper.c').as_posix())
                      +TRANSFORM,encoding='utf8')
    subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(library),
                    '-luser32','-lkernel32'],check=True,capture_output=True,timeout=60)
    lib=ctypes.CDLL(str(library))
    lib.transform_test.argtypes=[ctypes.c_wchar_p,*([ctypes.c_uint]*3),ctypes.c_uint64,ctypes.c_uint,ctypes.POINTER(ctypes.c_uint)]
    lib.transform_test.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)


bits=module.War3Trainer._float_bits


def dispatch(native,path,kind=75,failure=0,x=None,y=None,repeat=1):
    out=(ctypes.c_uint*8)();enabled=faulthandler.is_enabled()
    if failure in (8,13,15) and enabled:faulthandler.disable()
    try:assert native.transform_test(str(path)+'\\',kind,failure,
        (0 if kind==79 else bits(2.5)) if x is None else x,bits(-4) if y is None else y,repeat,out)==0
    finally:
        if failure in (8,13,15) and enabled:faulthandler.enable()
    assert out[0]==0
    return out,(path/f'war3_reforged_native_{os.getpid()}.bin').read_bytes()


def parse(payload,count=2):return module.War3Trainer.__new__(module.War3Trainer)._parse_native_helper_results(payload,count)


@pytest.mark.parametrize('scale',[0.01,2.5,100])
def test_scale_abi_and_float_limits(native,tmp_path,scale):
    out,payload=dispatch(native,tmp_path,x=bits(scale))
    assert parse(payload)[1].result==bits(scale) and list(out[4:7])==[bits(scale)]*3
    assert out[1]==1


@pytest.mark.parametrize('x,y',[(0,0),(12,-4),(-1000000,1000000)])
def test_position_abi_and_packed_ack(native,tmp_path,x,y):
    out,payload=dispatch(native,tmp_path,kind=94,x=bits(x),y=bits(y))
    assert parse(payload)[1].result==bits(x)|(bits(y)<<32)
    assert list(out[4:6])==[bits(x),bits(y)] and out[1]==1


def test_ownership_readback_matches_local_player(native,tmp_path):
    out,payload=dispatch(native,tmp_path,kind=79)
    assert parse(payload)[1].result==out[7]==23 and list(out[1:4])==[1,1,1]


@pytest.mark.parametrize('kind',[75,79,94])
@pytest.mark.parametrize('failure',[1,2,4,5,6,7,8])
def test_bad_identity_or_callback_replacement_prevents_following_action(native,tmp_path,kind,failure):
    out,payload=dispatch(native,tmp_path,kind=kind,failure=failure,repeat=2)
    with pytest.raises(RuntimeError):parse(payload,3)
    assert out[1]==int(failure>=5)


@pytest.mark.parametrize('failure',[9,10,11,12,13,15])
def test_owner_lookup_refusal_and_readback_races(native,tmp_path,failure):
    out,payload=dispatch(native,tmp_path,kind=79,failure=failure)
    with pytest.raises(RuntimeError):parse(payload)
    assert out[1]==int(failure in (11,12,13))
    assert out[2]==out[1] and out[3]==1


@pytest.mark.parametrize('kind,x,y,failure',[(75,bits(0.009),0,0),(75,bits(float('nan')),0,0),
    (75,bits(float('inf')),0,0),(75,bits(101),0,0),(75,bits(1),0,3),
    (94,bits(float('nan')),0,0),(94,0,bits(float('inf')),0),(94,bits(1000001),0,0),
    (94,0,1<<32,0),(79,1,0,0),(79,0,0,3)])
def test_invalid_values_and_shapes_never_invoke_engine(native,tmp_path,kind,x,y,failure):
    out,payload=dispatch(native,tmp_path,kind=kind,x=x,y=y,failure=failure)
    with pytest.raises(RuntimeError):parse(payload)
    assert list(out[1:4])==[0,0,0]


PUBLIC=[('set_selected_unit_scale',(2.5,),('SetUnitScale',),75,bits(2.5)),
        ('set_selected_unit_position',(12,-4),('SetUnitPosition',),94,bits(12)|(bits(-4)<<32)),
        ('take_selected_unit_control',(),('GetLocalPlayer','SetUnitOwner','GetOwningPlayer'),79,23)]


@pytest.mark.parametrize('method,args,names,kind,ack',PUBLIC)
def test_public_routes_bind_once_query_only_needed_functions_and_serialize(trainer,method,args,names,kind,ack):
    if method == 'set_selected_unit_position':
        target_x, target_y = args
        trainer.position_batch_24268 = Mock(return_value={
            'count': 1,
            'changed': 1,
            'completed': 1,
            'rows': [{
                'actual_x_bits': bits(target_x),
                'actual_y_bits': bits(target_y),
            }],
        })
        assert getattr(trainer,method)(*args) == args
        trainer.position_batch_24268.assert_called_once_with(
            bits(target_x), bits(target_y),
        )
        return
    trainer._query_native_table_handlers=Mock(return_value={name:module.NativeHandler(name,0,0x200000+n*0x100)
                                                         for n,name in enumerate(names)})
    trainer._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(kind,ack)])
    assert getattr(trainer,method)(*args)==(23 if kind==79 else args[0] if kind==75 else args)
    trainer._query_native_table_handlers.assert_called_once_with(names)
    trainer._process_memory.assert_not_called()
    snapshot=trainer.persistent_native_selected_snapshots.return_value[0]
    operation=(kind,0 if kind==79 else bits(args[0]),0x200000,
               0x200100 if kind==79 else bits(args[1]) if kind==94 else 0,0x200200 if kind==79 else 0)
    ops=((136,0,snapshot.unit_address,snapshot.full_handle,snapshot.owner_address),operation)
    trainer._run_native_helper_ops.assert_called_once_with(snapshot.handle,ops)
    trainer._native_helper_command_path=Mock(return_value='offline-command');trainer._write_native_helper_command=Mock()
    trainer._native_helper_batch_hook=1;trainer._native_helper_batch_thread_id=threading.get_ident()
    trainer._wait_native_helper_result=Mock(return_value=[]);trainer._run_native_helper_ops_locked(snapshot.handle,ops)
    payload=trainer._write_native_helper_command.call_args.args[1]
    base=trainer.NATIVE_HELPER_HEADER_STRUCT.size;size=trainer.NATIVE_HELPER_OP_STRUCT.size
    assert [trainer.NATIVE_HELPER_OP_STRUCT.unpack_from(payload,base+n*size)[:5] for n in range(2)]==list(ops)


@pytest.mark.parametrize('method,args',[('set_selected_unit_scale',(float('nan'),)),('set_selected_unit_scale',(0,)),
    ('set_selected_unit_position',(float('inf'),0)),('set_selected_unit_position',(0,1000001))])
def test_invalid_user_input_precedes_selection(trainer,method,args):
    with pytest.raises(ValueError):getattr(trainer,method)(*args)
    trainer.persistent_native_selected_snapshots.assert_not_called()


@pytest.mark.parametrize('method,args,names,kind,ack',PUBLIC)
@pytest.mark.parametrize('bad',['empty','kind','ack'])
def test_bad_acknowledgments_are_not_success(trainer,method,args,names,kind,ack,bad):
    if method == 'set_selected_unit_position':
        trainer.position_batch_24268 = Mock(return_value={})
        with pytest.raises(RuntimeError):
            getattr(trainer,method)(*args)
        return
    trainer._query_native_table_handlers=Mock(return_value={name:module.NativeHandler(name,0,0x200000) for name in names})
    trainer._run_native_helper_ops=Mock(return_value=[] if bad=='empty' else
        [module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(70 if bad=='kind' else kind,0 if bad=='ack' else ack)])
    with pytest.raises(RuntimeError):getattr(trainer,method)(*args)


def test_handler_lookup_does_not_replace_bound_target(trainer):
    candidate,handle=trainer._direct_selected_context()
    trainer.persistent_native_selected_snapshots.side_effect=AssertionError('Do not reread selection')
    trainer._query_native_table_handlers=Mock(return_value={'SetUnitScale':module.NativeHandler('SetUnitScale',0,0x200000)})
    trainer._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(75,bits(2))])
    with trainer._bound_elephant_selection(candidate,handle):assert trainer.set_selected_unit_scale(2)==2
    assert trainer._run_native_helper_ops.call_args.args[0]==handle
