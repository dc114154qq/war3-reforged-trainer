import ast,ctypes as c,struct
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock
import pytest
from war3_selection_protocol import SIGNATURES as SELECTION
from war3_item_protocol import SIGNATURES,WORK_SIZE,build_work,decode_work
from war3_native_table import LiveNativeEntry
import war3_engine_transport as transport

def entries():return {n:LiveNativeEntry(n,s,0x300000+i*80,0x500000+i*256) for i,(n,s) in enumerate(SELECTION+SIGNATURES)}
def work(action=0,charges=-1):return build_work(entries(),0x10000000,action,0x70686561 if action in (1,3,7) else 0,charges)
@pytest.fixture(scope='module')
def fixture():
    dll=c.WinDLL(str(Path(__file__).parent/'analysis/bridge-build-check-r35/engine-hero-fixture.dll'))
    dll.BridgeItemTestRun.argtypes=[c.c_void_p,c.c_int,c.c_int];dll.BridgeItemTestRun.restype=c.c_uint64
    dll.BridgeItemTestStat.argtypes=[c.c_int];dll.BridgeItemTestStat.restype=c.c_int
    return dll

def run(dll,count,action=0,charges=-1,scenario=0,rawcode=None):
    payload=build_work(entries(),0x10000000,action,rawcode if rawcode is not None else (0x70686561 if action in (1,3,7) else 0),charges)
    buf=c.create_string_buffer(payload);n=dll.BridgeItemTestRun(buf,count,scenario)
    return buf.raw[:WORK_SIZE],n,tuple(dll.BridgeItemTestStat(i) for i in range(3))
@pytest.mark.parametrize('count',[1,15,24])
@pytest.mark.parametrize('action,charges',[(0,-1),(1,-1),(1,7),(2,7),(2,1),(3,7)])
def test_compiled_item_actions(fixture,count,action,charges):
    data,n,stats=run(fixture,count,action,charges);r=decode_work(data,n)
    assert r['count']==count
    if action==0:assert stats==(0,0,0)
    if action==1:
        stored=(count+2)//3;assert r['stored']==stored and r['ground']==count-stored
        assert stats==(count,count if charges==7 else 0,0)
    if action==2:assert stats==(0,(count+2)//3 if charges==7 else 0,0)
    if action==3:
        eligible=(count+2)//3;assert stats==(eligible,eligible,eligible)
        assert r['skipped']==count-eligible and all(x['before']==x['after'] for x in r['rows'])


@pytest.mark.parametrize('action,stat_index',[(4,2),(6,2)])
def test_compiled_item_inventory_removal_actions(fixture,action,stat_index):
    data,n,stats=run(fixture,15,action,-1)
    result=decode_work(data,n)
    assert result['changed']==5 and result['skipped']==0
    assert all(not item['handle'] for row in result['rows'] for item in row['after'])
    assert stats[stat_index]==(5 if action==4 else 0)


def test_compiled_item_duplicate_preserves_sources_and_reports_count(fixture):
    data,n,stats=run(fixture,15,5,-1)
    result=decode_work(data,n)
    assert result['changed']==5 and result['skipped']==10
    assert stats==(5,0,0)
    for row in result['rows']:
        if row['status']==9:
            assert row['reserved']==1 and row['created']
            assert row['before'][0]==row['after'][0]
        else:
            assert row['status']==6 and not row['created']


def test_compiled_item_duplicate_full_inventory_keeps_originals(fixture):
    data,n,stats=run(fixture,15,5,-1,5)
    result=decode_work(data,n)
    assert result['changed']==90 and result['skipped']==0
    assert stats==(90,0,0)
    assert all(row['before']==row['after'] for row in result['rows'])


@pytest.mark.parametrize('count',[1,15,24])
def test_compiled_item_exact_slot_replace_preserves_other_slots(fixture,count):
    data,n,stats=run(fixture,count,7,2,5)
    result=decode_work(data,n)
    assert result['count']==count and result['changed']==count and stats==(count,0,count)
    for row in result['rows']:
        assert row['status']==10 and row['created_slot']==2
        assert row['after'][2]['rawcode']==0x70686561
        assert all(row['before'][slot]==row['after'][slot] for slot in (0,1,3,4,5))


def test_compiled_item_exact_slot_replace_is_idempotent(fixture):
    data,n,stats=run(fixture,15,7,0,5,0x73747770)
    result=decode_work(data,n)
    assert result['changed']==0 and stats==(0,0,0)
    assert all(row['status']==11 and not row['created'] for row in result['rows'])


def test_compiled_item_exact_slot_replace_failure_is_not_accepted(fixture):
    data,n,stats=run(fixture,15,7,2,7)
    with pytest.raises(ValueError):decode_work(data,n)

@pytest.mark.parametrize('scenario,action,charges',[(1,1,-1),(2,2,7),(3,1,-1),(4,3,7)])
def test_failure_not_accepted(fixture,scenario,action,charges):
    data,n,stats=run(fixture,15,action,charges,scenario)
    with pytest.raises(ValueError):decode_work(data,n)
    if scenario==3:assert stats==(1,0,1)

def test_full_inventories_create_on_ground_instead_of_overwriting(fixture):
    data,n,stats=run(fixture,15,1,-1,5);r=decode_work(data,n)
    assert r['ground']==15 and all(x['before']==x['after'] for x in r['rows'])

def test_diagnostic_skips_full_inventories_without_creating(fixture):
    data,n,stats=run(fixture,15,3,7,5);r=decode_work(data,n)
    assert r['skipped']==15 and stats==(0,0,0)

def test_new_item_charge_failure_cleans_only_new_item(fixture):
    data,n,stats=run(fixture,15,3,7,2)
    assert stats==(1,1,1)
    before=data[592:688];after=data[688:784];assert before==after
    with pytest.raises(ValueError):decode_work(data,n)

@pytest.mark.parametrize('name',[n for n,_ in SIGNATURES])
def test_item_signatures(name):
    es=entries();es[name]=replace(es[name],signature='()V')
    if name=='UnitAddItemToSlotById':
        with pytest.raises(ValueError):build_work(es,0x10000000,7,0x70686561,0)
    else:
        with pytest.raises(ValueError):build_work(es,0x10000000)


def test_slot_native_is_optional_for_non_slot_actions():
    es=entries();es.pop('UnitAddItemToSlotById')
    assert build_work(es,0x10000000,1,0x70686561,-1)
    with pytest.raises(ValueError):build_work(es,0x10000000,7,0x70686561,0)

@pytest.mark.parametrize('size',[0,480,4096,5959,5961,8193])
def test_wrong_work_never_opens_target(monkeypatch,size):
    monkeypatch.setattr(transport,'window_thread',Mock(side_effect=AssertionError('opened')))
    with pytest.raises(ValueError):transport.dispatch(1,2,3,Path('missing.dll'),0,bytes(size),kind='item')

@pytest.mark.parametrize('name',["elephant_add_item","elephant_set_inventory_charges"])
def test_gui_submits_once(name):
    tree=ast.parse((Path(__file__).parent/'war3_reforged_trainer.py').read_text(encoding='utf8'))
    fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name)
    trainer=Mock();trainer._native_selection_unavailable=True;trainer.item_batch_24268.return_value={'count':24,'changed':8,'stored':8,'ground':16}
    raw=Mock();raw.get.return_value='phea';charges=Mock();charges.get.return_value='7'
    env={'elephant_trainer':lambda:trainer,'elephant_item_rawcode':raw,'elephant_item_charges':charges,
        'parse_int':lambda value,label:int(value),'elephant_batch':Mock(side_effect=AssertionError('repeated'))}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'<gui-item>','exec'),env)
    assert '24' in env[name]() and trainer.item_batch_24268.call_count==1

@pytest.mark.parametrize('offset,value',[(572,999),(576,1),(580,14),(584,3)])
def test_status_counts_are_verified(fixture,offset,value):
    data,n,_=run(fixture,15,3,7);bad=bytearray(data);struct.pack_into('<I',bad,offset,value)
    with pytest.raises(ValueError):decode_work(bad,n)

def test_returned_existing_item_is_never_deleted(fixture):
    data,n,stats=run(fixture,15,1,-1,6)
    assert stats==(1,0,0)
    with pytest.raises(ValueError):decode_work(data,n)

def test_diagnostic_already_owned_item_is_not_touched(fixture):
    payload=build_work(entries(),0x10000000,3,0x73747770,7)
    buf=c.create_string_buffer(payload);n=fixture.BridgeItemTestRun(buf,15,0)
    r=decode_work(buf.raw[:WORK_SIZE],n)
    assert r['skipped']==15 and r['changed']==0
    assert tuple(fixture.BridgeItemTestStat(i) for i in range(3))==(0,0,0)

@pytest.mark.parametrize('action,rawcode,charges',[(1,0,-1),(3,0,7),(0,0,1),(2,0,0),(2,1,7)])
def test_invalid_request_rejected(action,rawcode,charges):
    with pytest.raises(ValueError):build_work(entries(),0x10000000,action,rawcode,charges)

def test_product_item_methods_use_new_bridge_only():
    import war3_reforged_trainer as product
    t=object.__new__(product.War3Trainer);t._native_selection_unavailable=True
    t.item_batch_24268=Mock(return_value={'rows':[{'created':0x100800,'after':[{'handle':0x100800}]}]})
    t._run_bound_item_create=Mock(side_effect=AssertionError('old helper'))
    t._process_memory=Mock(side_effect=AssertionError('direct cached write'))
    assert t.add_item_to_selected_unit('phea')==0x100800
    assert t.set_selected_inventory_charges(7)==1
    assert t.item_batch_24268.call_count==2
