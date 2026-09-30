import ctypes
import struct
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from war3_game_session import GameSession
from war3_game_speed_protocol import SIGNATURES, WORK_SIZE, build_work, validate_work, decode_work
from war3_native_table import LiveNativeEntry
from war3_operation_reports import record_status
from war3_services.facade_native import NativeFacade


def work(action=0, target=2):
    entries = {name: LiveNativeEntry(name, sig, 0x300000+i*80, 0x500000+i*256)
               for i,(name,sig) in enumerate(SIGNATURES)}
    return build_work(entries,0x10000000,action,target)


@pytest.fixture(scope='module')
def fixture():
    dll=ctypes.WinDLL(str(Path(__file__).parent/'build/game-speed-fixture/engine-hero-fixture.dll'))
    dll.BridgeGameSpeedTest.argtypes=[ctypes.c_void_p,ctypes.c_uint32]
    dll.BridgeGameSpeedTest.restype=ctypes.c_uint64
    dll.BridgeGameSpeedTestSetCount.restype=ctypes.c_uint32
    return dll


def run(fixture,action=1,target=4,scenario=0):
    buffer=ctypes.create_string_buffer(work(action,target))
    returned=fixture.BridgeGameSpeedTest(buffer,scenario)
    return buffer.raw[:WORK_SIZE],returned


@pytest.mark.parametrize('tier',range(5))
def test_native_five_constants_use_typed_abi(fixture,tier):
    payload,result=run(fixture,target=tier)
    assert result==1
    assert decode_work(payload,result)==dict(before=2,after=tier,changed=int(tier!=2),
                                            action=1,lock_before=0,lock_after=0)
    assert fixture.BridgeGameSpeedTestSetCount()==int(tier!=2)


def test_query_does_not_set_speed(fixture):
    payload,result=run(fixture,action=0)
    assert decode_work(payload,result)['after']==2
    assert fixture.BridgeGameSpeedTestSetCount()==0


def test_locked_map_is_restored(fixture):
    payload,result=run(fixture,scenario=2)
    assert decode_work(payload,result)['lock_after']==1


@pytest.mark.parametrize('scenario,error,unchanged',[(1,362,True),(3,363,False),
    (4,364,False),(5,361,False),(6,362,True),(7,0xc0000005,False)])
def test_rejections_faults_and_lock_cleanup(fixture,scenario,error,unchanged):
    payload,result=run(fixture,scenario=scenario)
    assert result==0
    assert struct.unpack_from('<I',payload,76)[0]==error
    with pytest.raises(ValueError):
        decode_work(payload,result)
    report={}
    record_status('game_speed',{'work_result_hex':payload.hex()},report)
    assert (report['game_speed_status'].get('changed')==0)==unchanged


@pytest.mark.parametrize('action,target',[(True,2),(1,True),(-1,2),(2,2),(1,-1),(1,5)])
def test_invalid_requests(action,target):
    with pytest.raises((ValueError,struct.error)):
        work(action,target)


def test_reserved_and_pointer_validation():
    payload=bytearray(work())
    payload[-1]=1
    with pytest.raises(ValueError):validate_work(payload)
    payload=bytearray(work())
    struct.pack_into('<Q',payload,0,0)
    with pytest.raises(ValueError):validate_work(payload)


def facade():
    trainer=NativeFacade()
    engine=SimpleNamespace(session=GameSession(123,456),game_speed=Mock())
    trainer._engine_instance_24268=Mock(return_value=engine)
    return trainer,engine


def test_toggle_restores_captured_speed_even_if_combo_changed():
    trainer,engine=facade()
    engine.game_speed.side_effect=[{'after':0},{'before':0,'after':2},{'after':2},{'before':2,'after':0}]
    assert trainer.toggle_native_game_speed(2)['accelerated']
    assert not trainer.toggle_native_game_speed(1)['accelerated']
    assert engine.game_speed.call_args_list[-1].args==(1,0)
    assert 'game_speed_original' not in engine.session.cache


def test_failed_set_does_not_create_restore_record():
    trainer,engine=facade()
    engine.game_speed.side_effect=[{'after':1},ValueError('rejected')]
    with pytest.raises(ValueError):trainer.toggle_native_game_speed(4)
    assert 'game_speed_original' not in engine.session.cache


def test_failed_restore_keeps_record_for_manual_retry():
    trainer,engine=facade()
    engine.session.cache['game_speed_original']=0
    engine.game_speed.side_effect=[{'after':2},ValueError('rejected')]
    with pytest.raises(ValueError):trainer.toggle_native_game_speed(2)
    assert engine.session.cache['game_speed_original']==0


def test_map_change_discards_restore_record():
    trainer,engine=facade()
    engine.session.cache['game_speed_original']=0
    engine.session.invalidate('map changed')
    engine.game_speed.side_effect=[{'after':1},{'before':1,'after':2}]
    trainer.toggle_native_game_speed(2)
    assert engine.game_speed.call_args_list[-1].args==(1,2)
    assert engine.session.cache['game_speed_original']==1


def test_no_change_does_not_claim_acceleration():
    trainer,engine=facade()
    engine.game_speed.return_value={'after':2}
    result=trainer.toggle_native_game_speed(2)
    assert result['unchanged'] and not result['accelerated']
    assert engine.game_speed.call_count==1
    assert 'game_speed_original' not in engine.session.cache


def test_hotkey_is_unique_and_uses_native_facade():
    import war3_reforged_trainer as product
    specs=product.ELEPHANT_HOTKEY_SPECS
    key=next(spec for spec in specs if spec.name=='game_speed')
    assert (key.modifiers,key.virtual_key)==(product.MOD_ALT,ord('N'))
    assert sum((spec.modifiers,spec.virtual_key)==(key.modifiers,key.virtual_key) for spec in specs)==1
    from war3_trainer_session import NATIVE_ONLY
    assert 'toggle_game_speed' in NATIVE_ONLY


def test_map_change_between_query_and_write_stops_dispatch():
    from war3_services.world import WorldService
    from war3_game_session import SessionError
    service=WorldService()
    service.session=GameSession(123,456)
    def execute(_kind,_names,builder,_decoder,_request):
        service.session.invalidate('map changed after query')
        return builder({},0x10000000)
    service._execute=execute
    with pytest.raises(SessionError):
        service.game_speed(1,2,expected_epoch=0)
