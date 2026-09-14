from dataclasses import replace
from pathlib import Path
import struct
import pytest
from war3_native_table import LiveNativeEntry
from war3_lifecycle_protocol import SIGNATURES,build_work,validate_work,decode_work
from test_game_thread_dispatch_cleanup import m as dispatch

def entries():
    return {n:LiveNativeEntry(n,s,0x10000+i*80,0x100000+i*256) for i,(n,s) in enumerate(SIGNATURES)}
def work():return build_work(entries(),0x10082d,0x4870616c,2,0x10000000)

def test_exact_abi_and_zero_outputs():
    w=work();assert len(w)==128 and not any(w[88:]);validate_work(w)
@pytest.mark.parametrize('index',range(8))
def test_every_signature(index):
    es=entries();n=SIGNATURES[index][0];es[n]=replace(es[n],signature='()V')
    with pytest.raises(ValueError):build_work(es,1,2,2,0x10000000)
@pytest.mark.parametrize('source,target,tls',[(0,2,0x10000),(0x4a2e0000394b,2,0x10000),(1,1,0x10000),(1,11,0x10000),(1,2,1)])
def test_invalid_input(source,target,tls):
    with pytest.raises(ValueError):build_work(entries(),source,0x4870616c,target,tls)
@pytest.mark.parametrize('size',[0,40,127,129])
def test_dispatch_rejects_before_access(size):
    with pytest.raises(ValueError):dispatch.inspect(1,2,3,Path('not-open.dll'),query_mode='unit_lifecycle',work_payload=bytes(size))
def test_complete_roundtrip():
    w=bytearray(work());struct.pack_into('<QIIIiiIII',w,88,0x100900,5,0,1,1,2,0,0x4870616c,0)
    assert decode_work(w)['ok']
@pytest.mark.parametrize('offset,value',[(96,4),(100,1),(104,0),(108,0),(112,1),(116,123),(120,123),(124,1)])
def test_partial_result_is_not_success(offset,value):
    w=bytearray(work());struct.pack_into('<QIIIiiIII',w,88,0x100900,5,0,1,1,2,0,0x4870616c,0)
    struct.pack_into('<I',w,offset,value);assert not decode_work(w)['ok']

from war3_lifecycle_protocol import MEMBERSHIP_SIGNATURES,build_membership,validate_membership,decode_membership

def membership():
    es={n:LiveNativeEntry(n,s,0x20000+i*80,0x300000+i*256) for i,(n,s) in enumerate(MEMBERSHIP_SIGNATURES)}
    return build_membership(es,0x100850,0x10000000)

def test_membership_binary_layout():
    w=membership();assert len(w)==80 and not any(w[56:]);validate_membership(w)
@pytest.mark.parametrize('member',[0,1])
def test_membership_result(member):
    w=bytearray(membership());struct.pack_into('<2Q2I',w,56,0x100900,0x100008,member,1)
    assert decode_membership(w)['member']==bool(member)
@pytest.mark.parametrize('size',[0,40,79,81])
def test_membership_rejected_before_process(size):
    with pytest.raises(ValueError):dispatch.inspect(1,2,3,Path('not-open.dll'),query_mode='unit_membership',work_payload=bytes(size))

def test_deferred_removal_needs_followup():
    w=bytearray(work());struct.pack_into('<QIIIiiIII',w,88,0x100900,5,0,1,1,2,0x4870616c,0x4870616c,0)
    result=decode_work(w)
    assert result['mutation_verified'] and not result['ok']

@pytest.mark.parametrize('size',[0,8,15,17,40])
def test_unit_query_rejects_invalid_work_before_access(size):
    with pytest.raises(ValueError):dispatch.inspect(1,2,3,Path('not-open.dll'),query_mode='unit',work_payload=bytes(size))

@pytest.mark.parametrize('mode',["unit", "unit_void"])
@pytest.mark.parametrize('handler,unit',[(0,1),(0x100000,0),(0x100000,0x4a2e0000394b)])
def test_unit_query_identity_bounds(mode,handler,unit):
    with pytest.raises(ValueError):dispatch.inspect(1,2,3,Path('not-open.dll'),query_mode=mode,
        work_payload=struct.pack('<2Q',handler,unit))

def test_incomplete_membership_never_reports_absence():
    with pytest.raises(ValueError):decode_membership(membership())
