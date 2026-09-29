"""Real C callback tests: own messages, foreign chain faults and delayed exit."""
import ctypes
from pathlib import Path
import faulthandler
import pytest


@pytest.fixture(scope='module')
def bridge():
    dll=ctypes.WinDLL(str(Path(__file__).parent/'build/architecture-fixture/engine-hero-fixture.dll'))
    dll.BridgeTestCallbackLifecycle.argtypes=[ctypes.c_uint32,ctypes.POINTER(ctypes.c_uint32)]
    dll.BridgeTestCallbackLifecycle.restype=ctypes.c_uint32
    dll.BridgeTestCallbackDrain.argtypes=[ctypes.c_uint32,ctypes.POINTER(ctypes.c_uint32)]
    dll.BridgeTestCallbackDrain.restype=ctypes.c_uint32
    return dll


@pytest.mark.parametrize('scenario',range(9))
def test_callback_execution_and_chain_ownership(bridge,scenario):
    out=(ctypes.c_uint32*10)()
    enabled=faulthandler.is_enabled()
    if enabled:faulthandler.disable()
    try:assert bridge.BridgeTestCallbackLifecycle(scenario,out)==0
    finally:
        if enabled:faulthandler.enable()
    assert out[2]==0 # active balanced even if the query or foreign hook faults
    if scenario in (1,2,3,4):
        assert out[0]==0 and out[1]==1 and out[7]==0
        assert out[3]==2
        assert out[9]==(0 if scenario==4 else 77)
    else:
        assert out[0]==1 and out[1]==0 and out[7]==1
        assert out[3]==3 and out[4]==(3 if scenario==7 else 2)
        assert out[5]==(0 if scenario==8 else 1)
    assert out[6]==(0xc0000005 if scenario in (4,7) else 0)
    assert out[8]==(2 if scenario in (5,6) else 1)


@pytest.mark.parametrize('stuck',[False,True])
def test_cleanup_waits_for_active_callback_without_faking_completion(bridge,stuck):
    out=(ctypes.c_uint32*3)()
    assert bridge.BridgeTestCallbackDrain(stuck,out)==0
    assert out[0]==int(stuck) and out[2]==int(stuck)
    assert out[1]>=(500 if stuck else 40)
