import ctypes as c,struct
from pathlib import Path
import pytest
from war3_equipment_protocol import SIGNATURES,WORK_SIZE,build_work,decode_work,validate_work
from war3_selection_protocol import SIGNATURES as SELECTION
from war3_native_table import LiveNativeEntry

def entries():return {n:LiveNativeEntry(n,s,0x300000+i*80,0x500000+i*256) for i,(n,s) in enumerate(SELECTION+SIGNATURES)}

@pytest.fixture(scope='module')
def fixture():
    d=c.WinDLL(str(Path(__file__).parent/'analysis/bridge-build-direct-r5/engine-hero-fixture.dll'))
    d.BridgeEquipmentTestRun.argtypes=[c.c_void_p,c.c_int];d.BridgeEquipmentTestRun.restype=c.c_uint64
    return d

def run(d,scenario=0,action=1):
    p=build_work(entries(),0x10000000,0 if action==2 else 0x65656833,action,0x100000,
                 0xA00000 if action==2 else 0,0xC00000 if action==2 else 0)
    b=c.create_string_buffer(p);n=d.BridgeEquipmentTestRun(b,scenario)
    return b.raw[:WORK_SIZE],n

def test_occupied_equipment_slot_and_ordinary_inventory_are_independent(fixture):
    data,n=run(fixture);r=decode_work(data,n)
    assert r['created']==0xA00000 and r['replaced']==0xC00000 and r['slot']==0
    assert r['before'][1:]==r['after'][1:]
    assert r['inventory_before']==r['inventory_after']

def test_rejected_equip_restores_same_original_instance(fixture):
    data,n=run(fixture,1)
    assert struct.unpack_from('<I',data,592)[0]==208
    assert struct.unpack_from('<I',data,608)[0]==0
    assert data[632:704]==data[704:776]
    with pytest.raises(ValueError):decode_work(data,n)

def test_equipment_restoration_is_verified(fixture):
    data,n=run(fixture,action=2);r=decode_work(data,n)
    assert r['before'][0]==0xA00000 and r['after'][0]==0xC00000

def test_equipment_type_query_makes_no_slot_changes(fixture):
    data,n=run(fixture,action=0);r=decode_work(data,n)
    assert r['equipment_type']==1 and r['changed']==0 and not r['created']

def test_decoder_rejects_unrelated_inventory_change(fixture):
    data,n=run(fixture);data=bytearray(data);struct.pack_into('<Q',data,824,0xBAD)
    with pytest.raises(ValueError):decode_work(data,n)

@pytest.mark.parametrize('size',[0,480,871,873])
def test_invalid_equipment_payload(size):
    with pytest.raises(ValueError):validate_work(bytes(size))
