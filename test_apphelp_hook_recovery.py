"""Regression of 2026-09-27 external evidence, not a mock-success claim."""
from copy import deepcopy
from unittest.mock import patch
import pytest
import war3_engine_transport as t


def observed():
    return {'image_route':'sec_image_fallback','safe_to_release':True,
        'fault':{'code':'0xc0000005','access':0,'address':'0x108',
                 'instruction_mapping':{'mapped_file':r'\Device\HarddiskVolume4\Windows\System32\apphelp.dll',
                                        'module_rva':'0x2e16b'}},
        'after_cleanup':{'stage':2,'hook':0,'callback_tid':0,'callback_count':0,
            'query_stage':0,'bridge_install_trace':'0x105','last_error':126,
            'exception_code':'0xc0000005','unwind_registered':1,'unwind_removed':1}}


def test_external_fault_selects_native_installer_instead_of_same_shim():
    first=observed()
    # The fallback fails here deliberately: selecting it is not proof of success.
    second={'callback_verified':False,'query_completed':False,'error':'test failure'}
    with patch.object(t,'_dispatch_once',side_effect=[first,second]) as run:
        result=t.dispatch(1,2,3,None,4,b'',kind='extension')
    assert run.call_args_list[1].kwargs['hook_api']=='win32u'
    assert run.call_args_list[1].kwargs['delivery_mode']=='send'
    assert result['same_route_retry']['reason']=='clean_apphelp_install_read_fault'
    assert not result['callback_verified'] and not result['query_completed']


@pytest.mark.parametrize('change',[
    {'safe_to_release':False}, {'allocations_retained':True},
    {'image_route':'target_loadlibrary'}, {'fault':{'access':1}},
    {'fault':{'address':'0x50000'}}, {'fault':{'address':'invalid'}},
    {'fault':{'code':'0xc000001d'}},
    {'fault':{'instruction_mapping':{'mapped_file':r'C:\Windows\System32\other.dll'}}},
    {'after_cleanup':{'callback_count':1}}, {'after_cleanup':{'query_stage':1}},
    {'after_cleanup':{'active':1}}, {'after_cleanup':{'unwind_removed':0}},
    {'hook_install_api':'NtUserSetWindowsHookEx'},
])
def test_no_unrelated_or_uncertain_native_retry(change):
    r=observed()
    for k,v in change.items():
        if isinstance(v,dict):r[k].update(v)
        else:r[k]=v
    assert not t._apphelp_install_read_fault(r)


def test_successful_primary_is_never_redirected():
    r={'callback_verified':True,'query_completed':True,'safe_to_release':True}
    with patch.object(t,'_dispatch_once',return_value=r) as run:
        result=t.dispatch(1,2,3,None,4,b'',kind='unit_stats')
    run.assert_called_once()
    assert result['same_route_retry']=={'attempted':False}


@pytest.mark.parametrize('state,complete,delivered,expected',[
    ({'hook':0,'stage':2,'active':0,'unwind_registered':1,'unwind_removed':1},True,False,True),
    ({'hook':0,'stage':2,'active':1},True,False,False),
    ({'hook':0,'stage':2,'unwind_registered':1,'unwind_removed':0},True,False,False),
    ({'hook':1,'stage':3,'detached':1,'active':0},True,True,True),
    ({'hook':1,'stage':3,'detached':1,'active':0},False,True,False),
    ({'hook':1,'stage':3,'detached':0,'active':0},True,True,False),
    ({'hook':1,'stage':2,'detached':1,'active':0},True,False,False),
])
def test_product_cleanup_invariants(state,complete,delivered,expected):
    assert t.can_release(complete,delivered,state)==expected
