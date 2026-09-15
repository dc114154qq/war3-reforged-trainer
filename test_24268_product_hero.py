import ctypes as c
from dataclasses import replace
from pathlib import Path
import struct
from unittest.mock import Mock,patch
import pytest
from war3_native_table import LiveNativeEntry
from war3_selection_protocol import SIGNATURES
from war3_hero_protocol import build_work,validate_work,decode_work
import war3_reforged_trainer as trainer_module
import war3_engine_transport as transport

def entries():
    signatures=SIGNATURES+(
        ('SetHeroLevel','(Hunit;IB)V'),
        ('UnitStripHeroLevel','(Hunit;I)B'),
        ('SuspendHeroXP','(Hunit;B)V'),
        ('IsSuspendedXP','(Hunit;)B'),
    )
    return {n:LiveNativeEntry(n,s,0x300000+i*80,0x500000+i*256) for i,(n,s) in enumerate(signatures)}
def work(target=0):return build_work(entries(),0x10000000,target)

@pytest.mark.parametrize('size',[0,480,607,609])
def test_transport_rejects_incomplete_work_before_window_access(monkeypatch,size):
    monkeypatch.setattr(transport,'window_thread',Mock(side_effect=AssertionError('window accessed')))
    with pytest.raises(ValueError):transport.dispatch(1,2,3,Path('missing.dll'),0,bytes(size))

@pytest.mark.parametrize('name',[n for n,_ in SIGNATURES]+['SetHeroLevel'])
def test_every_signature_is_exact(name):
    es=entries();es[name]=replace(es[name],signature='()V')
    with pytest.raises(ValueError):build_work(es,0x10000000,2)

def test_legacy_native_never_called_by_new_product_entry():
    trainer=object.__new__(trainer_module.War3Trainer);trainer._native_selection_unavailable=True
    trainer.hero_progress_24268=Mock(return_value={'rows':[{'after':7}]})
    trainer._run_bound_hero_progress=Mock(side_effect=AssertionError('legacy called'))
    trainer._query_elephant_unit_int=Mock(side_effect=AssertionError('legacy called'))
    assert trainer.get_selected_hero_level()==7
    assert trainer.set_selected_hero_level(7)==7
    assert trainer.hero_progress_24268.call_count==2

@pytest.mark.parametrize('level',[0,-1,100001])
def test_bad_user_level_never_dispatches(level):
    trainer=object.__new__(trainer_module.War3Trainer);trainer._native_selection_unavailable=True
    trainer.hero_progress_24268=Mock(side_effect=AssertionError('dispatched'))
    with pytest.raises(ValueError):trainer.set_selected_hero_level(level)

@pytest.fixture(scope='module')
def fixture_dll():
    path=Path(__file__).parent/'analysis/engine-hero-fixture.dll'
    assert path.is_file(),'Compile tools/war3_bridge_24268.c with BRIDGE_TEST before this gate'
    dll=c.WinDLL(str(path));dll.BridgeTestRun.argtypes=[c.c_void_p,c.c_int,c.c_int];dll.BridgeTestRun.restype=c.c_uint64
    dll.BridgeTestWrites.argtypes=[];dll.BridgeTestWrites.restype=c.c_int
    return dll

def run_fixture(dll,count,target,scenario=0):
    buf=c.create_string_buffer(work(target));actual=dll.BridgeTestRun(buf,count,scenario)
    return buf.raw[:632],actual,dll.BridgeTestWrites()

@pytest.mark.parametrize('count',[1,4,15,24])
@pytest.mark.parametrize('target',[0,1,2,7])
def test_actual_c_batch_skips_nonheroes_and_writes_once(fixture_dll,count,target):
    data,actual,writes=run_fixture(fixture_dll,count,target)
    result=decode_work(data,actual);heroes=(count+2)//3
    assert len(result['rows'])==heroes and result['skipped']==count-heroes
    assert writes==result['changed']==(heroes if target>1 else 0)
    assert all(r['after']==(target or 1) for r in result['rows'])

@pytest.mark.parametrize('scenario,expected_writes',[(1,1),(2,0),(3,0),(4,0)])
def test_actual_c_rejects_noop_setter_changed_identity_and_noheroes(fixture_dll,scenario,expected_writes):
    data,actual,writes=run_fixture(fixture_dll,15,2,scenario)
    assert writes==expected_writes
    with pytest.raises(ValueError):decode_work(data,actual)

def test_actual_c_strips_levels_for_downward_change(fixture_dll):
    data,actual,writes=run_fixture(fixture_dll,15,1,7)
    result=decode_work(data,actual)
    heroes=(15+2)//3
    assert result['changed']==heroes and writes==heroes
    assert all(row['level']==3 and row['after']==1 for row in result['rows'])

def test_no_analysis_or_old_profile_in_product_modules():
    root=Path(__file__).parent
    for name in ['war3_engine_24268.py','war3_engine_transport.py','tools/war3_bridge_24268.c']:
        text=(root/name).read_text(encoding='utf8')
        assert 'runpy.' not in text and 'war3_native_profile' not in text and 'WAR3_BOOTSTRAP_' not in text

def test_current_engine_report_is_preserved_in_user_error_log(tmp_path):
    from war3_engine_24268 import EngineExecutionError
    report={'pid':1234,'dispatch':{'after_send':{'query_stage':3,'exception_code':'0xc0000005'},'work_result_hex':'deadbeef'}}
    exc=EngineExecutionError('batch failed',report)
    with patch.object(trainer_module.sys,'frozen',True,create=True),patch.object(trainer_module.sys,'executable',str(tmp_path/'trainer.exe')):
        log=Path(trainer_module.record_operation_failure(1234,'hero_level',exc))
    text=log.read_text(encoding='utf-8-sig')
    assert 'engine24268_execution_report' in text and 'deadbeef' in text and '0xc0000005' in text

def test_missing_current_bridge_never_loads_legacy(tmp_path):
    from war3_engine_24268 import Engine24268,EngineExecutionError
    memory=Mock(side_effect=AssertionError('process opened'))
    engine=Engine24268(1234,42,memory,tmp_path/'missing.dll')
    with pytest.raises(EngineExecutionError,match='Missing current'):engine.hero_progress(2)
    memory.assert_not_called()

def test_pending_execution_is_not_retried(tmp_path):
    from war3_engine_24268 import Engine24268,EngineExecutionError
    memory=Mock(side_effect=AssertionError('process opened'))
    engine=Engine24268(1234,42,memory);engine.quarantined=True
    with pytest.raises(EngineExecutionError,match='retained'):engine.hero_progress(2)
    memory.assert_not_called()

@pytest.mark.parametrize('function_name',["elephant_read_hero_level","elephant_set_hero_level"])
def test_gui_uses_one_batch_for_24_mixed_units(function_name):
    import ast
    tree=ast.parse((Path(__file__).parent/'war3_reforged_trainer.py').read_text(encoding='utf8'))
    function=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==function_name)
    trainer=Mock();trainer._native_selection_unavailable=True
    trainer.hero_progress_24268.return_value={'rows':[{'after':7}]*8,'changed':8,'skipped':16}
    legacy_batch=Mock(side_effect=AssertionError('GUI dispatched per-unit legacy batch'))
    variable=Mock();variable.get.return_value='7'
    namespace={'elephant_trainer':lambda:trainer,'elephant_batch':legacy_batch,'root':Mock(),
        'elephant_hero_level':variable,'parse_int':lambda value,label:int(value)}
    exec(compile(ast.Module(body=[function],type_ignores=[]),'<gui-batch-test>','exec'),namespace)
    message=namespace[function_name]()
    assert trainer.hero_progress_24268.call_count==1 and '8' in message and '16' in message
    legacy_batch.assert_not_called()
