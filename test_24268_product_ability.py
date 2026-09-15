import ast,ctypes as c,struct
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock
import pytest
from war3_selection_protocol import SIGNATURES as SELECTION
from war3_ability_protocol import SIGNATURES,build_work,decode_work,validate_work
from war3_native_table import LiveNativeEntry
import war3_engine_transport as transport
import war3_reforged_trainer as product

def entries():
    return {n:LiveNativeEntry(n,s,0x300000+i*80,0x500000+i*256) for i,(n,s) in enumerate(SELECTION+SIGNATURES)}
def work(action=0,level=0):return build_work(entries(),0x10000000,0x41487664,action,level)
@pytest.fixture(scope='module')
def fixture():
    dll=c.WinDLL(str(Path(__file__).parent/'analysis/bridge-build-check-r32/engine-hero-fixture.dll'))
    dll.BridgeAbilityTestRun.argtypes=[c.c_void_p,c.c_int,c.c_int,c.c_int];dll.BridgeAbilityTestRun.restype=c.c_uint64
    dll.BridgeAbilityTestStat.argtypes=[c.c_int];dll.BridgeAbilityTestStat.restype=c.c_int
    return dll

def run(dll,count,action,level=0,initial=0,scenario=0):
    buf=c.create_string_buffer(work(action,level));count=dll.BridgeAbilityTestRun(buf,count,scenario,initial)
    return buf.raw[:832],count,tuple(dll.BridgeAbilityTestStat(i) for i in range(3))
@pytest.mark.parametrize('count',[1,15,24])
@pytest.mark.parametrize('action,level,initial',[(0,0,0),(0,0,2),(1,0,0),(1,0,2),(1,3,0),(1,3,1),(2,0,1),(2,0,0),(3,3,1),(3,1,1),(4,2,0),(4,2,1),(5,0,0),(5,0,1)])
def test_compiled_batch_semantics(fixture,count,action,level,initial):
    data,n,stats=run(fixture,count,action,level,initial)
    result=decode_work(data,n);assert result['count']==count
    if action==4:
        assert all(r['after']==initial for r in result['rows'])
        assert stats[:2]==((count,count) if initial==0 else (0,0))
    elif action==5:
        assert all(r['after']>0 for r in result['rows'])
        assert stats[:2]==((count,count) if initial else (count,0))
    elif action==0:assert stats==(0,0,0)
@pytest.mark.parametrize('scenario,action,level,initial',[(1,1,0,0),(2,3,2,1),(3,2,0,1),(3,5,0,1),(6,1,0,0)])
def test_failure_never_claimed_success(fixture,scenario,action,level,initial):
    data,n,stats=run(fixture,15,action,level,initial,scenario)
    with pytest.raises(ValueError):decode_work(data,n)
    if scenario==6:assert stats==(0,0,0)

def test_failed_diagnostic_level_still_removes_new_ability(fixture):
    data,n,stats=run(fixture,15,4,2,0,2)
    assert stats==(1,1,1)
    assert struct.unpack_from('<i',data,548)[0]==0
    with pytest.raises(ValueError):decode_work(data,n)

def test_diagnostic_preserves_preexisting_skills(fixture):
    data,n,stats=run(fixture,15,4,2,0,5)
    result=decode_work(data,n)
    assert stats==(10,10,10)
    assert all(r['after']==r['before'] for r in result['rows'])

def test_level_batch_preflights_all_missing_skills_before_any_write(fixture):
    data,n,stats=run(fixture,15,3,2,0,5)
    assert stats==(0,0,0)
    with pytest.raises(ValueError):decode_work(data,n)
@pytest.mark.parametrize('name',[n for n,_ in SIGNATURES])
def test_each_signature(name):
    es=entries();es[name]=replace(es[name],signature='()V')
    with pytest.raises(ValueError):build_work(es,0x10000000,1)
@pytest.mark.parametrize('size',[0,480,608,831,833])
def test_bad_payload_rejected_before_target_access(monkeypatch,size):
    monkeypatch.setattr(transport,'window_thread',Mock(side_effect=AssertionError('accessed')))
    with pytest.raises(ValueError):transport.dispatch(1,2,3,Path('missing.dll'),0,bytes(size),kind='ability')
@pytest.mark.parametrize('name,action',[('elephant_add_ability',1),('elephant_remove_ability',2),('elephant_set_ability_level',3)])
def test_gui_does_not_repeat_whole_batch(name,action):
    tree=ast.parse((Path(__file__).parent/'war3_reforged_trainer.py').read_text(encoding='utf8'))
    fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name)
    trainer=Mock();trainer._native_selection_unavailable=True;trainer.ability_batch_24268.return_value={'count':24,'changed':24}
    raw=Mock();raw.get.return_value='AHad';level=Mock();level.get.return_value='2'
    env={'elephant_trainer':lambda:trainer,'elephant_ability_rawcode':raw,'elephant_ability_level':level,
        'parse_int':lambda value,label:int(value),'elephant_batch':Mock(side_effect=AssertionError('repeated'))}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'<gui-ability>','exec'),env)
    assert '24' in env[name]()
    trainer.ability_batch_24268.assert_called_once_with('AHad',action,2 if action==3 else 0)

def test_product_methods_never_call_old_helper():
    trainer=object.__new__(product.War3Trainer);trainer._native_selection_unavailable=True
    trainer.ability_batch_24268=Mock(return_value={'count':15,'changed':15})
    trainer._run_bound_ability_actions=Mock(side_effect=AssertionError('old helper'))
    trainer.add_ability_to_selected_unit('AHad');trainer.remove_ability_from_selected_unit('AHad')
    assert trainer.set_selected_unit_ability_level('AHad',2)==2
    trainer.reset_selected_unit_ability('AHad')
    assert trainer.ability_batch_24268.call_count==4

@pytest.mark.parametrize('action,level',[(0,1),(2,1),(3,0),(4,0),(5,1)])
def test_invalid_actions(action,level):
    with pytest.raises(ValueError):work(action,level)

def test_partial_batch_not_accepted_even_when_some_rows_succeed(fixture):
    data,n,_=run(fixture,15,1,0,0)
    bad=bytearray(data);struct.pack_into('<I',bad,540,14)
    with pytest.raises(ValueError):decode_work(bad,n)

def test_failure_message_contains_real_ability_stage():
    from war3_engine_24268 import EngineExecutionError
    error=EngineExecutionError('failed',{'pid':1,'ability_status':{'changed':1,'error':300,'completed':0}})
    assert '300' in str(error) and 'ability_status' in str(error)

def test_fault_register_record_retains_actual_access_details():
    record=struct.pack('<4I10Q',0x24268012,1,0xc0000005,0,*range(0x100000,0x10000a))
    decoded=transport.decode_fault(record)
    assert decoded['instruction']=='0x100000' and decoded['address']=='0x100001'
    assert decoded['rcx']=='0x100002' and decoded['code']=='0xc0000005'

def test_absent_fault_is_not_fabricated():
    assert transport.decode_fault(bytes(96)) is None

@pytest.mark.parametrize('data',[b'',bytes(95),struct.pack('<4I10Q',1,1,1,1,*([0]*10))])
def test_bad_fault_telemetry_is_rejected(data):
    with pytest.raises(ValueError):transport.decode_fault(data)

@pytest.mark.parametrize('index,value',[(0,0),(1,0xc0000094),(2,1),(3,1),(4,0x5004bd),(5,1),(5,8),(6,8)])
def test_compiled_tail_gate_rejects_other_faults(fixture,index,value):
    fn=fixture.BridgeTestKnownAbilityTail
    fn.argtypes=[c.c_uint64,c.c_uint32,c.c_uint32,c.c_uint32,c.c_uint64,c.c_uint64,c.c_uint64,c.c_uint64];fn.restype=c.c_int
    args=[0x500000,0xc0000005,0,2,0x5004bc,0,0,0]
    assert fn(*args)==1
    args[index]=value
    assert fn(*args)==0


def test_compiled_tail_gate_ignores_unstable_r15(fixture):
    fn=fixture.BridgeTestKnownAbilityTail
    fn.argtypes=[c.c_uint64,c.c_uint32,c.c_uint32,c.c_uint32,c.c_uint64,c.c_uint64,c.c_uint64,c.c_uint64]
    fn.restype=c.c_int
    assert fn(0x500000,0xc0000005,0,2,0x5004bc,0,0,8)==1

@pytest.mark.parametrize('actual,target,expected',[(2,2,2),(1,2,-1),(3,2,-1),(0,0,-1),(-1,2,-1)])
def test_compiled_tail_recovery_requires_exact_readback(fixture,actual,target,expected):
    f=fixture.BridgeTestTailReadback;f.argtypes=[c.c_int,c.c_int];f.restype=c.c_int
    assert f(actual,target)==expected

def test_recovered_fault_is_saved_not_silently_erased(tmp_path,monkeypatch):
    monkeypatch.setattr(product.sys,'frozen',True,raising=False)
    monkeypatch.setattr(product.sys,'executable',str(tmp_path/'trainer.exe'))
    report={'ok':True,'dispatch':{'recovered_tail_faults':15,'fault':{'instruction':'0x123','address':'0x0'}}}
    path=Path(product.record_engine_recovery(1234,report))
    text=path.read_text(encoding='utf-8-sig')
    assert 'verified_tail_fault_recovery' in text and 'recovered_tail_faults' in text and '0x123' in text
