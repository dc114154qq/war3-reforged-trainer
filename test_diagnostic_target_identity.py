from unittest.mock import patch
import pytest
import war3_reforged_trainer as product


@pytest.mark.parametrize('args', [['trainer.exe','--pid','23604'], ['trainer.exe','--pid=23604']])
def test_launch_pid_is_not_current_game_or_window_pid(args):
    with patch.object(product.sys,'argv',args):
        result=product.diagnostic_target_identity(3668,[(99,3668,'Warcraft III')])
    assert result['requested_game_pid']==23604
    assert result['game_pid']==result['target_game_pid']==3668
    assert result['target_window_pid']==3668 and result['target_window_hwnd']=='0x63'


def test_missing_window_does_not_invent_window_pid():
    result=product.diagnostic_target_identity(3668,[(99,9999,'Warcraft III')])
    assert result['target_window_pid'] is None and result['target_window_hwnd'] is None


def test_window_lookup_failure_preserves_error_logging():
    with patch.object(product,'enum_war3_windows',side_effect=OSError('window gone')):
        result=product.diagnostic_target_identity(3668)
    assert result['target_game_pid']==3668
    assert 'window gone' in result['target_window_lookup_error']


def test_unknown_target_keeps_game_and_window_pids_unset():
    result = product.diagnostic_target_identity(
        None,
        [(99, 3668, 'Warcraft III'), (100, 4777, 'Warcraft III')],
        requested_pid=23604,
    )
    assert result['requested_game_pid'] == 23604
    assert result['game_pid'] is None
    assert result['actual_target_pid'] is None
    assert result['window_pid'] is None
    assert result['target_window_pid'] is None
    assert len(result['target_windows']) == 2
