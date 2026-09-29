"""2.0.9 lifecycle evidence through the modular session and ABI boundary."""
import ctypes
import struct
from unittest.mock import Mock
import pytest
import war3_engine_transport as transport
from war3_game_session import SessionError, session_scope
from test_game_architecture import bound
from test_24268_loader_backed_transport import _FakePE, _hero_payload


def finished(**changes):
    report = dict(callback_received=True, callback_exited=True,
                  callback_verified=True, cleanup_verified=True,
                  query_completed=True, safe_to_release=True,
                  work_freed=True, block_freed=True, image_unmap_status="0x0")
    report.update(changes)
    return report


def test_received_but_stuck_callback_preserves_evidence_and_blocks_replay(bound):
    session, *_ = bound
    report = finished(callback_exited=False, callback_verified=False,
                      cleanup_verified=False, safe_to_release=False,
                      allocations_retained=True,
                      after_cleanup=dict(active=1, query_stage=2, callback_count=1))
    evidence = session.finish(report)
    assert evidence.delivered and not evidence.callback_exited
    assert not evidence.cleanup_complete and evidence.uncertain
    assert not evidence.readback_verified and not evidence.effect_verified
    assert session.retained['dispatch'] is report
    with pytest.raises(SessionError):session.require_write()


@pytest.mark.parametrize('change', [
    dict(cleanup_verified=False), dict(safe_to_release=False),
    dict(callback_exited=False), dict(allocations_retained=True),
    dict(query_completed=False), dict(work_freed=False), dict(block_freed=False),
])
def test_explicit_failure_cannot_be_overridden_by_legacy_success(bound, change):
    session, *_ = bound
    evidence = session.finish(finished(**change))
    assert evidence.uncertain and not evidence.effect_verified
    with pytest.raises(SessionError):session.require_write()


def test_successful_query_does_not_claim_gameplay_verification(bound):
    session, *_ = bound
    first=session.finish(finished())
    assert first.delivered and first.callback_exited and first.cleanup_complete
    assert not first.readback_verified and not first.effect_verified
    verified=session.finish(finished(), readback=True)
    assert verified.readback_verified and not verified.effect_verified
    assert not verified.uncertain
    session.require_write()


def test_clean_failed_install_is_not_a_delivered_query(bound):
    session, *_ = bound
    evidence=session.finish(finished(callback_received=False, callback_exited=False,
                                     callback_verified=False, query_completed=False), readback=True)
    assert not evidence.delivered and not evidence.readback_verified
    assert evidence.cleanup_complete and not evidence.uncertain
    session.require_write()


def test_install_retry_rechecks_session_identity(bound, monkeypatch, tmp_path):
    session, *_ = bound
    # A reused PID must fail before import fixups, hook installation or any write.
    monkeypatch.setattr(transport.pefile, 'PE', lambda _: _FakePE())
    monkeypatch.setattr(session, 'creation_reader', lambda _: 11)
    def owner(hwnd, pointer):
        ctypes.cast(pointer, ctypes.POINTER(transport.U))[0] = session.pid
        return 44
    monkeypatch.setattr(transport, 'window_thread', owner)
    monkeypatch.setitem(transport.p, 'open_process', lambda *args: 1)
    monkeypatch.setitem(transport.p, 'close', lambda *args: True)
    write=Mock(); monkeypatch.setitem(transport.p, 'write', write)
    image=tmp_path/'bridge.dll';image.write_bytes(b'fixture')
    with session_scope(session):
        result=transport._dispatch_once(session.pid, session.hwnd, 44, image, 0, _hero_payload())
    assert 'Process identity changed' in result['error']
    write.assert_not_called()


@pytest.mark.parametrize('missing', ['bridge_profile_abi','bridge_callback_lifecycle_abi'])
def test_stale_bridge_rejected_before_opening_process(bound, monkeypatch, tmp_path, missing):
    pe=_FakePE()
    from types import SimpleNamespace
    pe.DIRECTORY_ENTRY_EXPORT=SimpleNamespace(symbols=[s for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name!=missing.encode()])
    monkeypatch.setattr(transport.pefile, 'PE', lambda _:pe)
    def owner(hwnd, pointer):
        ctypes.cast(pointer, ctypes.POINTER(transport.U))[0] = 1
        return 44
    monkeypatch.setattr(transport, 'window_thread', owner)
    opened=Mock();monkeypatch.setitem(transport.p,'open_process',opened)
    with pytest.raises(ValueError, match='ABI differs'):
        transport._dispatch_once(1,2,44,tmp_path/'old.dll',0,_hero_payload())
    opened.assert_not_called()
