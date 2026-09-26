from types import SimpleNamespace
from unittest.mock import Mock,patch
import struct
import threading
import pytest
import war3_talent_icon_control_protocol as protocol
from war3_talent_icon_display import TalentIconDisplay,ORIGINAL
import war3_engine_transport as transport
from war3_reforged_trainer import War3Trainer, user32


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


def test_minimized_game_still_installs_through_bound_game_thread():
    trainer = War3Trainer.__new__(War3Trainer)
    trainer.hwnd = 123
    trainer._talent_icon_display = None
    trainer._engine_instance_24268 = Mock(return_value=object())
    trainer._talent_icon_display_path_24268 = Mock(return_value="icon.dll")
    display = Mock()
    display.install.return_value = {"installed": True}
    with patch.object(user32, "IsIconic", return_value=True), \
            patch("war3_talent_icon_display.TalentIconDisplay", return_value=display):
        result = trainer.refresh_talent_icon_display_24268()
    assert result["installed"] is True
    trainer._engine_instance_24268.assert_called_once()
    assert trainer._talent_icon_display is display


def test_unbound_window_does_not_break_talent_transaction():
    trainer = War3Trainer.__new__(War3Trainer)
    trainer._talent_icon_display = None
    trainer._engine_instance_24268 = Mock(side_effect=AssertionError("Must not dispatch without a window"))
    result = trainer.refresh_talent_icon_display_24268()
    assert result["reason"] == "window_unavailable"
    trainer._engine_instance_24268.assert_not_called()


def test_undecoded_talent_site_has_distinct_error_reason():
    trainer = War3Trainer.__new__(War3Trainer)
    trainer.hwnd = 123
    trainer._talent_icon_display = None
    trainer._engine_instance_24268 = Mock(return_value=object())
    trainer._talent_icon_display_path_24268 = Mock(return_value="icon.dll")
    display = Mock()
    display.install.side_effect = RuntimeError("code differs")
    display.observed_code = "c7" * 36
    with patch.object(user32, "IsIconic", return_value=False), \
            patch("war3_talent_icon_display.TalentIconDisplay", return_value=display):
        result = trainer.refresh_talent_icon_display_24268()
    assert result["reason"] == "code_unavailable"
    display.close.assert_called()


def test_uncertain_icon_cleanup_retains_mapping_and_refuses_reinstall():
    trainer = War3Trainer.__new__(War3Trainer)
    trainer.hwnd = 123
    trainer._talent_icon_display = None
    trainer._engine_instance_24268 = Mock(return_value=object())
    trainer._talent_icon_display_path_24268 = Mock(return_value="icon.dll")
    display = Mock()
    display.install.side_effect = RuntimeError("dispatch completion unknown")
    display.close.side_effect = RuntimeError("mapped image retained")
    with patch.object(user32, "IsIconic", return_value=False), \
            patch("war3_talent_icon_display.TalentIconDisplay", return_value=display) as constructor:
        first = trainer.refresh_talent_icon_display_24268()
        assert first["reason"] == "cleanup_uncertain" and first["retained"]
        assert trainer._talent_icon_display is display
        display.snapshot.side_effect = RuntimeError("state unreadable")
        second = trainer.refresh_talent_icon_display_24268()
        assert second["reason"] == "cleanup_uncertain" and second["retained"]
        constructor.assert_called_once()
    assert trainer._talent_icon_display is display


def test_pid_change_waits_for_verified_icon_cleanup():
    trainer = War3Trainer.__new__(War3Trainer)
    trainer.hwnd = 10
    trainer.pid = 100
    trainer._executable_path = "game.exe"
    display = Mock()
    display.close.side_effect = RuntimeError("mapped image retained")
    trainer._talent_icon_display = display
    with patch("war3_reforged_trainer.is_war3_window", return_value=False), \
            patch("war3_reforged_trainer.find_war3_with_retry", return_value=(20, 200)):
        with pytest.raises(RuntimeError, match="PID 切换已中止"):
            trainer.refresh_window(allow_pid_change=True)
    assert (trainer.hwnd, trainer.pid) == (10, 100)
    assert trainer._talent_icon_display is display


def test_close_keeps_uncertain_icon_mapping_reference():
    trainer = War3Trainer.__new__(War3Trainer)
    display = Mock()
    display.close.side_effect = RuntimeError("mapped image retained")
    trainer._talent_icon_display = display
    trainer._persistent_bootstrap_stop = Mock()
    trainer._engine24268 = None
    trainer._native_helper_lock = threading.RLock()
    trainer._native_helper_persistent_module = None
    trainer._native_helper_persistent_hook = None
    trainer._win10_session_trainer = None
    trainer._persistent_bootstrap_thread = None
    trainer.close()
    assert trainer._talent_icon_display is display
    assert "映射引用已保留" in trainer._talent_icon_display_error
