from types import SimpleNamespace
from unittest.mock import Mock,patch
import struct
import pytest
import war3_talent_icon_control_protocol as protocol
from war3_talent_icon_display import TalentIconDisplay,ORIGINAL
import war3_engine_transport as transport


def payload():
    return protocol.build_work(0x90000,0x100000,0x101000,0x102000,0x80000,0x81000,0x103000,0x104000,8,0)


def test_control_keeps_retained_image_state_even_when_install_fails():
    data=bytearray(payload())
    struct.pack_into('<8I',data,64,8,0,1,5,1,0,1,0)
    result=protocol.decode_work(data,1)
    assert not result['success'] and result['registered'] and result['installed']


@pytest.mark.parametrize('offset,value',[(16,0x80000),(24,0x80000),(48,0x80000),(56,0x80000)])
def test_control_rejects_entries_outside_module(offset,value):
    data=bytearray(payload());struct.pack_into('<Q',data,offset,value)
    with pytest.raises(ValueError):protocol.validate_work(data)


def lease():
    obj=TalentIconDisplay(SimpleNamespace(pid=1),'unused.dll')
    obj.handle=123;obj.base=0x100000;obj.game_base=0x140000000
    obj._alive=Mock(return_value=True)
    return obj


def test_unknown_completion_does_not_unmap_or_close_handle():
    obj=lease();obj.uncertain=True
    with patch.dict(transport.x,unmap_section=Mock()) as api,patch.dict(transport.p,close=Mock()) as process:
        with pytest.raises(RuntimeError):obj.close()
        api['unmap_section'].assert_not_called();process['close'].assert_not_called()


def test_removal_failure_retains_code_and_unwind_data():
    obj=lease();obj.registered=True;obj.snapshot=Mock(return_value={'installed':True})
    obj._control=Mock(return_value={'error':8,'installed':True,'registered':True,'active':0})
    with patch.dict(transport.x,unmap_section=Mock()) as api:
        with pytest.raises(RuntimeError):obj.close()
        api['unmap_section'].assert_not_called()
    assert obj.handle==123 and obj.base==0x100000


def test_verified_removal_restores_code_before_unmapping():
    obj=lease();obj.registered=True;obj.snapshot=Mock(return_value={'installed':True})
    obj._control=Mock(return_value={'error':0,'installed':False,'registered':False,'active':0})
    with patch.object(transport,'bytes_at',return_value=ORIGINAL),patch.dict(transport.x,unmap_section=Mock(return_value=0)) as api,patch.dict(transport.p,close=Mock()) as process:
        assert obj.close()['original_code_restored']
        api['unmap_section'].assert_called_once();process['close'].assert_called_once_with(123)
    assert not obj.base and obj.handle is None


def test_exited_original_process_does_not_dispatch_into_reused_pid():
    obj=lease();obj._alive.return_value=False;obj._control=Mock()
    with patch.dict(transport.p,close=Mock()):assert obj.close()['process_exited']
    obj._control.assert_not_called()
