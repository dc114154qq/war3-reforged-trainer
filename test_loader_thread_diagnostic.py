"""Validate diagnostic result semantics; these tests never create a thread."""
import importlib.util
from pathlib import Path
from unittest.mock import Mock
import pytest

spec=importlib.util.spec_from_file_location('loader_thread',Path(__file__).parent/'analysis/verify-loader-thread.py')
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


@pytest.mark.parametrize('result,module,expected',[
 ({'created':False},None,'thread_creation_failed'),
 ({'created':True,'completed':False},None,'pending_load_thread_no_forced_cleanup'),
 ({'created':True,'completed':True,'stage':0},None,'entry_not_observed'),
 ({'created':True,'completed':True,'stage':1},None,'entry_incomplete_or_unreadable'),
 ({'created':True,'completed':True,'stage':None},None,'entry_incomplete_or_unreadable'),
 ({'created':True,'completed':True,'stage':2,'module_result':'0x0'},None,'loader_returned_null'),
 ({'created':True,'completed':True,'stage':2,'module_result':'0x123000'},None,'loader_result_not_in_module_list'),
 ({'created':True,'completed':True,'stage':2,'module_result':'0x123000'},0x123000,'loaded'),
 ({'created':True,'completed':True},None,'module_not_loaded'),
])
def test_outcomes_do_not_infer_load_success_from_thread_exit(result,module,expected):
 assert m.classify_load(result,module)==expected


@pytest.mark.parametrize('wait_status,completed',[(0,True),(258,False),(0xffffffff,False)])
def test_thread_wait_closes_handle_without_forced_termination(monkeypatch,wait_status,completed):
 create=Mock(return_value=5);close=Mock();get_exit=Mock(return_value=0)
 monkeypatch.setattr(m,'create_thread',create)
 monkeypatch.setattr(m,'wait',Mock(return_value=wait_status))
 monkeypatch.setattr(m,'exit_code',get_exit)
 monkeypatch.setattr(m,'close',close)
 r=m.invoke(10,20,30,300)
 assert r['completed']==completed
 assert r['created']
 close.assert_called_once_with(5)
 assert get_exit.call_count==int(completed)


def test_failed_thread_creation_has_no_wait(monkeypatch):
 monkeypatch.setattr(m,'create_thread',Mock(return_value=0))
 wait=Mock();monkeypatch.setattr(m,'wait',wait)
 assert not m.invoke(10,20,30,300)['created']
 wait.assert_not_called()
