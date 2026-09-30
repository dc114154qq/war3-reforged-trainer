from types import SimpleNamespace
from unittest.mock import Mock
import struct
import pytest

from war3_game_profile import default_profile
from war3_game_session import GameSession, SessionError
from war3_services.speed import toggle_scaled_speed
from war3_speed_clock_backend import SpeedClockBackend, encode_speed_factor


class Clock:
    def __init__(self):self.handle=1;self.saved_rate=None;self.rate=1;self.sets=[]
    def query(self):return {'rate':self.rate}
    def set_rate(self,rate):self.rate=rate;self.sets.append(rate);return {'rate':rate}


def trainer(clock=None):
    session=GameSession(1,2,profile=default_profile())
    session.identity=SimpleNamespace(pid=1,created=1)
    clock=clock or Clock()
    session.resources['speed_clock']=clock
    engine=SimpleNamespace(session=session)
    return SimpleNamespace(_engine_instance_24268=lambda:engine),session,clock


def test_toggle_is_reversible_when_user_changes_requested_factor():
    t,_,clock=trainer()
    assert toggle_scaled_speed(t,2)=={'rate':2,'accelerated':True}
    assert toggle_scaled_speed(t,3)=={'rate':1,'accelerated':False}
    assert clock.sets==[2,1] and clock.saved_rate is None


def test_map_change_preserves_process_wide_restoration_state():
    t,session,clock=trainer()
    toggle_scaled_speed(t,2)
    session.invalidate('map changed')
    assert not toggle_scaled_speed(t,2)['accelerated']
    assert clock.rate==1


def test_current_rate_is_not_reported_as_new_acceleration():
    t,_,clock=trainer()
    result=toggle_scaled_speed(t,1)
    assert result['unchanged'] and not result['accelerated']
    assert clock.sets==[] and clock.saved_rate is None


@pytest.mark.parametrize('factor',[True,False,None,'2',float('nan'),float('inf'),0.5,4294967.296,1e308,10**1000])
def test_invalid_factor_is_rejected_before_target_access(factor):
    t=SimpleNamespace(_engine_instance_24268=Mock(side_effect=AssertionError('opened')))
    with pytest.raises(ValueError):toggle_scaled_speed(t,factor)
    t._engine_instance_24268.assert_not_called()


@pytest.mark.parametrize('factor',[4.01,8,16,20,100,123.456,10000,4294967.295])
def test_custom_multiplier_has_no_artificial_ceiling_and_restores(factor):
    t,_,clock=trainer()
    assert toggle_scaled_speed(t,factor)['rate']==factor
    assert not toggle_scaled_speed(t,factor)['accelerated']
    assert clock.sets==[factor,1]
    assert encode_speed_factor(factor)==round(factor*1000)


def test_fractional_multiplier_encoding_is_explicit():
    assert encode_speed_factor(8.125)==8125
    assert encode_speed_factor(20.1234)==20123


def test_high_multiplier_readback_is_accepted_and_released(monkeypatch):
    clock=backend()
    module,allocated,release=transport_setup(monkeypatch,clock,Mock(return_value=(0,99)))
    def result(*_):
        data=bytearray(allocated['data'])
        assert struct.unpack_from('<I',data,12)[0]==20000
        struct.pack_into('<8I',data,40,1,1,20000,0,1,1,0,7)
        return bytes(data)
    monkeypatch.setattr(module.transport,'bytes_at',result)
    assert clock.set_rate(20)['rate']==20
    assert not clock.uncertain
    release.assert_called_once()


def test_failed_set_does_not_commit_original_rate():
    t,_,clock=trainer()
    clock.set_rate=Mock(side_effect=RuntimeError('failed'))
    with pytest.raises(RuntimeError):toggle_scaled_speed(t,2)
    assert clock.saved_rate is None


def test_failed_restore_retains_original_rate():
    t,_,clock=trainer()
    clock.saved_rate=1;clock.rate=2
    clock.set_rate=Mock(side_effect=RuntimeError('failed'))
    with pytest.raises(RuntimeError):toggle_scaled_speed(t,3)
    assert clock.saved_rate==1


def test_uncertain_session_does_not_open_or_replay_clock():
    t,session,clock=trainer()
    session.uncertain=True
    with pytest.raises(SessionError):toggle_scaled_speed(t,2)
    assert clock.sets==[]


def backend():
    clock=object.__new__(SpeedClockBackend)
    clock.engine=SimpleNamespace(session=GameSession(1,2))
    clock.handle=1;clock.base=0x100000;clock.created=1
    clock.unwind=SimpleNamespace(VirtualAddress=0x1000,Size=12)
    clock.exports={b'SpeedControl':0x2000}
    clock.uncertain=False;clock.pinned=False;clock.last_result={};clock.saved_rate=None
    clock._validate=Mock()
    return clock


def transport_setup(monkeypatch,clock,call):
    import war3_speed_clock_backend as module
    allocated={}
    def write(handle,block,data,length,count):
        count._obj.value=length
        allocated['data']=bytes(data.raw[:length]);return True
    release=Mock(return_value=True)
    monkeypatch.setitem(module.transport.p,'alloc',Mock(return_value=0x900000))
    monkeypatch.setitem(module.transport.p,'write',write)
    monkeypatch.setitem(module.transport.p,'free',release)
    monkeypatch.setattr(module.transport,'remote_thread_call',call)
    return module,allocated,release


def test_worker_timeout_quarantines_image_and_argument_memory(monkeypatch):
    clock=backend()
    _,_,release=transport_setup(monkeypatch,clock,Mock(side_effect=TimeoutError('worker running')))
    with pytest.raises(TimeoutError):clock.set_rate(2)
    release.assert_not_called()
    assert clock.uncertain and clock.engine.session.uncertain
    assert clock.engine.session.retained['speed_clock']['command_block']=='0x900000'


def test_missing_hook_readback_blocks_replay_even_with_zero_native_error(monkeypatch):
    clock=backend()
    module,allocated,release=transport_setup(monkeypatch,clock,Mock(return_value=(0,99)))
    def result(*_):
        data=bytearray(allocated['data'])
        struct.pack_into('<8I',data,40,1,0,2000,0,1,1,0,7)
        return bytes(data)
    monkeypatch.setattr(module.transport,'bytes_at',result)
    with pytest.raises(RuntimeError):clock.set_rate(2)
    assert clock.uncertain and clock.engine.session.uncertain
    release.assert_called_once()


def test_argument_release_failure_is_not_reported_as_clean(monkeypatch):
    clock=backend()
    module,allocated,release=transport_setup(monkeypatch,clock,Mock(return_value=(0,99)))
    release.return_value=False
    def result(*_):
        data=bytearray(allocated['data'])
        struct.pack_into('<8I',data,40,1,1,2000,0,1,1,0,7)
        return bytes(data)
    monkeypatch.setattr(module.transport,'bytes_at',result)
    with pytest.raises(OSError):clock.set_rate(2)
    assert clock.engine.session.uncertain
    assert not clock.engine.session.last_evidence.cleanup_complete
    assert clock.engine.session.retained['speed_clock']['command_block']=='0x900000'


def test_dead_original_process_cleanup_never_touches_a_reused_pid(monkeypatch):
    clock=backend();clock._alive=Mock(return_value=False)
    import war3_speed_clock_backend as module
    close=Mock();monkeypatch.setitem(module.transport.p,'close',close)
    clock.set_rate=Mock(side_effect=AssertionError('wrote to replacement'))
    result=clock.close()
    assert result['process_exited'] and clock.handle is None
    clock.set_rate.assert_not_called()


def test_resident_generation_mismatch_cannot_reuse_new_export_offsets(monkeypatch):
    clock=backend()
    clock._attach=Mock(side_effect=RuntimeError('generation mismatch'))
    clock.engine.session.resources['speed_clock']=clock
    import war3_speed_clock_backend as module
    dispatch=Mock(side_effect=AssertionError('wrong old-image export'))
    monkeypatch.setattr(module.transport,'remote_thread_call',dispatch)
    with pytest.raises(RuntimeError):clock.attach()
    assert clock.uncertain and clock.engine.session.uncertain
    with pytest.raises(RuntimeError):clock.query()
    dispatch.assert_not_called()
    assert 'speed_clock_attachment' in clock.engine.session.retained


def test_unmapped_attach_failure_releases_handle_and_resource(monkeypatch):
    clock=backend();clock.base=0
    clock._attach=Mock(side_effect=RuntimeError('invalid image'))
    clock.engine.session.resources['speed_clock']=clock
    import war3_speed_clock_backend as module
    close=Mock();monkeypatch.setitem(module.transport.p,'close',close)
    with pytest.raises(RuntimeError):clock.attach()
    close.assert_called_once_with(1)
    assert clock.handle is None and not clock.engine.session.resources


def test_unsupported_clock_does_not_block_unrelated_unit_reads_and_writes(monkeypatch):
    clock=backend()
    clock.engine.session.identity=SimpleNamespace(pid=1,created=1)
    module,allocated,release=transport_setup(monkeypatch,clock,Mock(return_value=(50,99)))
    def result(*_):
        data=bytearray(allocated['data'])
        struct.pack_into('<8I',data,40,0,0,1000,50,0,1,8,0)
        return bytes(data)
    monkeypatch.setattr(module.transport,'bytes_at',result)
    with pytest.raises(RuntimeError):clock.set_rate(2)
    assert not clock.uncertain and not clock.engine.session.uncertain
    clock.engine.session.require_write()
    assert not clock.engine.session.retained
    with pytest.raises(RuntimeError):clock.set_rate(2)
    release.assert_called_once()


def test_partial_hook_installation_is_not_accepted_by_fresh_query(monkeypatch):
    clock=backend()
    module,allocated,release=transport_setup(monkeypatch,clock,Mock(return_value=(0,99)))
    def result(*_):
        data=bytearray(allocated['data'])
        struct.pack_into('<8I',data,40,1,0,1000,0,1,1,0,7)
        return bytes(data)
    monkeypatch.setattr(module.transport,'bytes_at',result)
    with pytest.raises(RuntimeError):clock.query()
    assert clock.uncertain and clock.engine.session.uncertain
    release.assert_called_once()


def test_inactive_registered_image_is_not_unmapped_on_close(monkeypatch):
    clock=backend();clock.pinned=True
    clock.unavailable_reason='unsupported forwarding thunk'
    clock._alive=Mock(return_value=True)
    import war3_speed_clock_backend as module
    unmap=Mock(side_effect=AssertionError('registered unwind table would dangle'))
    monkeypatch.setitem(module.transport.x,'unmap_section',unmap)
    monkeypatch.setitem(module.transport.p,'close',Mock())
    clock.set_rate=Mock(side_effect=AssertionError('replayed failed installation'))
    assert clock.close()['resident_until_process_exit']
    unmap.assert_not_called();clock.set_rate.assert_not_called()
