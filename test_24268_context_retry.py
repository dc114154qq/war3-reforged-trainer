from unittest.mock import Mock
import pytest
import war3_thread_context as context
from war3_object_registry import ObjectIdentityError
BASE=0x100000

def partial(code=299):
    e=OSError('memory read failed');e.winerror=code;return e

def exact(address,size):
    return dict((BASE+rva,code) for rva,code in context.CONTEXT_CODE_CHECKS)[address]

def test_partial_read_restarts_all_exact_checks(monkeypatch):
    seen=[];failed=False
    def read(address,size):
        nonlocal failed
        seen.append(address)
        if address==BASE+context.CONTEXT_CODE_CHECKS[1][0] and not failed:
            failed=True;raise partial()
        return exact(address,size)
    sleep=Mock();monkeypatch.setattr(context.time,'sleep',sleep)
    context.verify_context_code(Mock(read=Mock(side_effect=read)),BASE)
    first=BASE+context.CONTEXT_CODE_CHECKS[0][0]
    assert seen.count(first)==2
    sleep.assert_called_once_with(.01)

def test_persistent_failure_is_bounded_and_rejected(monkeypatch):
    memory=Mock();memory.read.side_effect=partial()
    sleep=Mock();monkeypatch.setattr(context.time,'sleep',sleep)
    with pytest.raises(ObjectIdentityError,match='3 attempts'):context.verify_context_code(memory,BASE)
    assert memory.read.call_count==3 and sleep.call_count==2

def test_mismatch_never_retried(monkeypatch):
    memory=Mock();memory.read.side_effect=lambda address,size:bytes(size)
    sleep=Mock();monkeypatch.setattr(context.time,'sleep',sleep)
    with pytest.raises(ObjectIdentityError,match='differs'):context.verify_context_code(memory,BASE)
    assert memory.read.call_count==1;sleep.assert_not_called()

@pytest.mark.parametrize('error',[5,6,87])
def test_other_os_errors_not_retried(monkeypatch,error):
    memory=Mock();memory.read.side_effect=partial(error)
    sleep=Mock();monkeypatch.setattr(context.time,'sleep',sleep)
    with pytest.raises(OSError):context.verify_context_code(memory,BASE)
    assert memory.read.call_count==1;sleep.assert_not_called()

def test_short_read_is_not_retryable_success(monkeypatch):
    memory=Mock();memory.read.return_value=b''
    sleep=Mock();monkeypatch.setattr(context.time,'sleep',sleep)
    with pytest.raises(ObjectIdentityError):context.verify_context_code(memory,BASE)
    assert memory.read.call_count==1;sleep.assert_not_called()
