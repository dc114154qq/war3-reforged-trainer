import ctypes as c
import struct
from pathlib import Path
from unittest.mock import Mock

import pytest

from war3_native_table import LiveNativeEntry
from war3_world_protocol import (
    ACTION_END_GAME,
    ACTION_QUERY_FOG,
    ACTION_SET_FOG,
    ACTION_SET_GAME_PAUSED,
    ACTION_SET_TECH,
    ACTION_SET_XP_RATE,
    SIGNATURES,
    build_work,
    decode_work,
)
import war3_engine_transport as transport
import war3_reforged_trainer as product


def entries():
    return {name: LiveNativeEntry(name, signature, 0x300000 + i * 80, 0x500000 + i * 256)
            for i, (name, signature) in enumerate(SIGNATURES)}


def work(action, rawcode=0, value=0):
    return build_work(entries(), 0x10000000, action, rawcode, value)


@pytest.fixture(scope='module')
def fixture():
    dll = c.WinDLL(str(Path(__file__).parent / 'analysis' / 'engine-hero-fixture.dll'))
    dll.BridgeWorldTestRun.argtypes = [c.c_void_p, c.c_int, c.c_uint32, c.c_uint32]
    dll.BridgeWorldTestRun.restype = c.c_uint64
    dll.BridgeWorldTestStat.argtypes = [c.c_int]
    dll.BridgeWorldTestStat.restype = c.c_int
    return dll


def run(dll, action, rawcode=0, value=0):
    buf = c.create_string_buffer(work(action, rawcode, value))
    result = dll.BridgeWorldTestRun(buf, action, rawcode, value)
    return buf.raw[:128], result


@pytest.mark.parametrize('action,rawcode,value', [
    (ACTION_SET_TECH, 0x526F7374, 3),
    (ACTION_SET_XP_RATE, 0, struct.unpack('<I', struct.pack('<f', 2.5))[0]),
    (ACTION_QUERY_FOG, 0, 0),
    (ACTION_SET_FOG, 0, 1),
    (ACTION_SET_GAME_PAUSED, 0, 1),
    (ACTION_END_GAME, 0, 1),
])
def test_compiled_world_actions(fixture, action, rawcode, value):
    data, result = run(fixture, action, rawcode, value)
    decoded = decode_work(data)
    assert result == 1 and decoded['action'] == action
    if action == ACTION_SET_TECH:
        assert decoded['after0'] == 3
        assert fixture.BridgeWorldTestStat(0) == fixture.BridgeWorldTestStat(1) == 1
    elif action == ACTION_SET_XP_RATE:
        assert decoded['after0'] == value and fixture.BridgeWorldTestStat(2) == 1
    elif action == ACTION_QUERY_FOG:
        assert decoded['after0'] == decoded['after1'] == 1
    elif action == ACTION_SET_FOG:
        assert decoded['after0'] == decoded['after1'] == 0
    else:
        assert fixture.BridgeWorldTestStat(7) == 1


@pytest.mark.parametrize('action,rawcode,value', [
    (ACTION_SET_TECH, 0, 1),
    (ACTION_SET_XP_RATE, 1, 0),
    (ACTION_QUERY_FOG, 0, 1),
    (ACTION_SET_FOG, 0, 2),
])
def test_invalid_world_request_rejected(action, rawcode, value):
    with pytest.raises(ValueError):
        work(action, rawcode, value)


def test_world_transport_rejects_wrong_payload_before_target_access(monkeypatch):
    monkeypatch.setattr(transport, 'window_thread', Mock(side_effect=AssertionError('opened')))
    with pytest.raises(ValueError):
        transport.dispatch(1, 2, 3, Path('missing.dll'), 0, bytes(127), kind='world')


def test_product_world_methods_use_current_batch():
    trainer = object.__new__(product.War3Trainer)
    trainer._native_selection_unavailable = True
    trainer.world_batch_24268 = Mock(side_effect=lambda action, rawcode=0, value=0:
                                     {'after0': value, 'after1': value, 'changed': 1})
    trainer.map_flags_batch_24268 = Mock(side_effect=lambda action, revealed=0:
                                         {'after0': 0 if action == 1 or revealed else 1,
                                          'after1': 0 if action == 1 or revealed else 1,
                                          'changed': 0 if action == 1 else 1})
    trainer._elephant_handlers = Mock(side_effect=AssertionError('old helper'))
    assert trainer.set_local_player_tech('Rost', 3) == 3
    assert trainer.set_local_player_xp_rate(2.5) == pytest.approx(2.5)
    assert trainer.get_map_fog_state() == (False, False)
    trainer.set_map_revealed(True)
    trainer.set_game_paused(True)
    trainer.end_current_game(True)
    assert [call.args[0] for call in trainer.world_batch_24268.call_args_list] == [1, 2, 5, 6]
    assert [(call.args[0], call.args[1]) for call in trainer.map_flags_batch_24268.call_args_list] == [(1, 0), (2, 1)]
