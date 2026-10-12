"""Production-C regression, including failure cases; not external game acceptance."""
import ctypes as c
import struct
from pathlib import Path
from types import SimpleNamespace
import pytest
import war3_direct_cast_protocol as cast
import war3_item_ability_protocol as item
from war3_game_profile import load_profile
from war3_selection_protocol import SIGNATURES as SELECTION

VERSIONS=('3.0.0.24268','3.0.1.24323','3.0.1.24332','3.0.1.24342')
def entries(signatures):
    names=dict(SELECTION+signatures)
    return {n:SimpleNamespace(name=n,signature=s,handler=0x300000+i*256) for i,(n,s) in enumerate(names.items())}
def real(bits):return struct.unpack('<f',struct.pack('<I',bits))[0]

@pytest.fixture(scope='module')
def dll():
    value=c.WinDLL(str(Path(__file__).parent/'build/architecture-fixture/engine-hero-fixture.dll'))
    value.BridgeCompatCastTestRun.argtypes=[c.c_void_p,c.c_uint32,c.c_uint32]
    value.BridgeCompatCastTestRun.restype=c.c_uint64
    value.BridgeCompatCastTestStat.argtypes=[c.c_uint32];value.BridgeCompatCastTestStat.restype=c.c_uint32
    value.BridgeCompatItemAbilityTestRun.argtypes=[c.c_void_p,c.c_uint32];value.BridgeCompatItemAbilityTestRun.restype=c.c_uint64
    value.BridgeCompatItemAbilityTestStat.restype=c.c_uint32
    return value

@pytest.fixture(params=VERSIONS)
def version(request,dll):
    profile=load_profile(Path('profiles')/(request.param+'.json'))
    saved=bytes((c.c_ubyte*len(profile.bridge_bytes())).in_dll(dll,'bridge_profile'))
    c.memmove(c.addressof((c.c_ubyte*len(saved)).in_dll(dll,'bridge_profile')),profile.bridge_bytes(),len(saved))
    yield request.param
    c.memmove(c.addressof((c.c_ubyte*len(saved)).in_dll(dll,'bridge_profile')),saved,len(saved))

def run_cast(dll,code,action=1,state=None,scenario=0):
    payload=cast.build_work(entries(cast.SIGNATURES),0x10000000,module_base=0x300000,
        unit_resolver=0x300100,action=action,rawcode=int.from_bytes(code.encode(),'big'),
        mode=3 if code=='ANmo' else 2,state=state)
    buf=c.create_string_buffer(payload)
    count=dll.BridgeCompatCastTestRun(buf,scenario,struct.unpack('<I',struct.pack('<f',2.5))[0])
    return buf.raw[:cast.WORK_SIZE],count

@pytest.mark.parametrize('code',('ANmo','AEsb'))
@pytest.mark.parametrize('scenario',(0,1,3,4,10))
def test_both_shortcuts_cast_with_zero_mana_and_restore_same_original_skill(dll,version,code,scenario):
    raw,count=run_cast(dll,code,scenario=scenario)
    start=cast.decode_work(raw,count)
    assert start['mana_before']==0 and start['invoked']==1
    assert dll.BridgeCompatCastTestStat(3)==1
    assert dll.BridgeCompatCastTestStat(5)==dll.BridgeCompatCastTestStat(6)==0
    state,count=run_cast(dll,code,3,start,scenario)
    assert cast.decode_work(state,count)['ability_full']==start['ability_full']
    cleanup,count=run_cast(dll,code,2,start,scenario)
    assert cast.decode_work(cleanup,count)['cleanup_verified']
    assert real(dll.BridgeCompatCastTestStat(4))==900
    assert dll.BridgeCompatCastTestStat(5)==300
    assert real(dll.BridgeCompatCastTestStat(6))==100
    assert dll.BridgeCompatCastTestStat(9)==(scenario in (1,4,10))
    if scenario==4:
        assert dll.BridgeCompatCastTestStat(0)==dll.BridgeCompatCastTestStat(2)==0
        assert dll.BridgeCompatCastTestStat(8)==0
    if scenario==10:
        assert real(dll.BridgeCompatCastTestStat(7))==17.5
        assert dll.BridgeCompatCastTestStat(10)==1 and dll.BridgeCompatCastTestStat(11)==0

@pytest.mark.parametrize('scenario,error',[(2,344),(6,355),(7,353)])
def test_failed_start_never_becomes_effect_success_and_preserves_cleanup(dll,version,scenario,error):
    raw,count=run_cast(dll,'ANmo',scenario=scenario)
    with pytest.raises(ValueError):cast.decode_work(raw,count)
    assert struct.unpack_from('<I',raw,728)[0]==error
    assert struct.unpack_from('<I',raw,820)[0]==0
    assert dll.BridgeCompatCastTestStat(3)==0 and dll.BridgeCompatCastTestStat(9)==0

def test_replaced_instance_is_not_written_during_cleanup(dll,version):
    raw,count=run_cast(dll,'AEsb')
    start=cast.decode_work(raw,count)
    raw,count=run_cast(dll,'AEsb',2,start,5)
    with pytest.raises(ValueError):cast.decode_work(raw,count)
    assert struct.unpack_from('<I',raw,820)[0]!=0
    assert dll.BridgeCompatCastTestStat(2)==0
    assert dll.BridgeCompatCastTestStat(5)==0

def test_unknown_setter_fault_is_not_declared_clean_or_replayed(dll,version):
    raw,count=run_cast(dll,'ANmo',scenario=16)
    with pytest.raises(ValueError):cast.decode_work(raw,count)
    assert struct.unpack_from('<I',raw,728)[0]!=0
    assert struct.unpack_from('<I',raw,820)[0]!=0
    assert dll.BridgeCompatCastTestStat(0)==1
    assert dll.BridgeCompatCastTestStat(2)==dll.BridgeCompatCastTestStat(3)==0

@pytest.mark.parametrize('scenario,error',[(0,0),(1,445),(2,0),(3,446),(4,447),(6,0)])
def test_item_registration_preserves_instance_and_original_capabilities(dll,version,scenario,error):
    payload=item.build_work(entries(item.SIGNATURES),0x10000000,target=0x100000,item=0x500000,base=0x300000,
        unit_full=0xabcd00000001,item_full=0xdcba00000002,rawcode=int.from_bytes(b'ebhg','big'),
        action=1,ability_rawcode=int.from_bytes(b'AIni','big'))
    buf=c.create_string_buffer(payload);count=dll.BridgeCompatItemAbilityTestRun(buf,scenario)
    raw=buf.raw[:item.WORK_SIZE]
    assert item.status(raw)['error']==error
    if error:
        with pytest.raises(ValueError):item.decode_work(raw,count)
    else:
        result=item.decode_work(raw,count)
        assert result['identity_verified'] and result['classic_before']==result['classic_after']
        assert result['after_handle']
    assert dll.BridgeCompatItemAbilityTestStat()==(0 if scenario==2 else 1)

@pytest.mark.parametrize('scenario', (7,8,12))
def test_item_bound_list_is_used_when_direct_lookup_is_empty(dll,version,scenario):
    payload=item.build_work(entries(item.SIGNATURES),0x10000000,target=0x100000,item=0x500000,base=0x300000,
        unit_full=0xabcd00000001,item_full=0xdcba00000002,rawcode=int.from_bytes(b'ebhg','big'),
        action=1,ability_rawcode=int.from_bytes(b'AIni','big'))
    buf=c.create_string_buffer(payload);count=dll.BridgeCompatItemAbilityTestRun(buf,scenario)
    result=item.decode_work(buf.raw[:item.WORK_SIZE],count)
    assert result['identity_verified'] and result['classic_before']==result['classic_after']
    assert result['lookup_evidence']['after']==dict(direct=False,indexed=True)
    assert dll.BridgeCompatItemAbilityTestStat()==(0 if scenario==7 else 1)
    if scenario==7:
        assert result['before_handle']==result['after_handle']==0x710000
        assert result['changed']==0
        assert result['lookup_evidence']['before']==dict(direct=False,indexed=True)
    else:
        assert result['before_handle']==0 and result['after_handle']==0x710010
        assert result['changed']==1 and result['add_return']==(scenario==8)

@pytest.mark.parametrize('scenario,error', [(9,444),(10,443),(11,444)])
def test_ambiguous_item_ability_identity_stops_without_duplicate_add(dll,version,scenario,error):
    payload=item.build_work(entries(item.SIGNATURES),0x10000000,target=0x100000,item=0x500000,base=0x300000,
        unit_full=0xabcd00000001,item_full=0xdcba00000002,rawcode=int.from_bytes(b'ebhg','big'),
        action=1,ability_rawcode=int.from_bytes(b'AIni','big'))
    buf=c.create_string_buffer(payload);count=dll.BridgeCompatItemAbilityTestRun(buf,scenario)
    raw=buf.raw[:item.WORK_SIZE]
    assert item.status(raw)['error']==error and dll.BridgeCompatItemAbilityTestStat()==0
    with pytest.raises(ValueError):item.decode_work(raw,count)
    # A fresh independent request must execute after a completed rejection.
    fresh=c.create_string_buffer(payload);count=dll.BridgeCompatItemAbilityTestRun(fresh,7)
    assert item.decode_work(fresh.raw[:item.WORK_SIZE],count)['completed']==1
    assert dll.BridgeCompatItemAbilityTestStat()==0
