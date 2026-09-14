"""An old executor renamed for 24268 must not trigger bootstrap or slow reads."""
from unittest.mock import Mock, patch
import pytest
import war3_reforged_trainer as m


@pytest.mark.parametrize('dll_exists', [False, True])
def test_constructor_uses_indexed_path_without_starting_worker(dll_exists):
    with patch.object(m, 'find_war3', return_value=(100, 200)), \
            patch.object(m.Path, 'is_file', return_value=dll_exists), \
            patch.object(m.threading, 'Thread') as worker:
        trainer = m.War3Trainer(200)
    assert trainer._native_selection_unavailable
    assert trainer._persistent_bootstrap_stop.is_set()
    assert trainer._persistent_bootstrap_thread is None
    worker.assert_not_called()


def test_explicit_init_rejects_before_lock_or_transport():
    trainer = object.__new__(m.War3Trainer)
    trainer._native_selection_unavailable = True
    trainer._run_native_helper_ops = Mock(side_effect=AssertionError('transport called'))
    with pytest.raises(RuntimeError, match='legacy bootstrap was not dispatched'):
        trainer.persistent_native_init()
    trainer._run_native_helper_ops.assert_not_called()


def test_restart_stops_existing_worker_without_creating_another():
    trainer = object.__new__(m.War3Trainer)
    previous = Mock()
    trainer._persistent_bootstrap_stop = previous
    trainer._native_selection_unavailable = True
    with patch.object(m.threading, 'Thread') as worker:
        trainer._start_persistent_bootstrap()
    previous.set.assert_called_once()
    worker.assert_not_called()


def test_reconnect_does_not_treat_dll_presence_as_readiness():
    with patch.object(m, 'find_war3', return_value=(100, 200)):
        trainer = m.War3Trainer(200)
    trainer._native_selection_unavailable = False
    with patch.object(m, 'is_war3_window', return_value=False), \
            patch.object(m, 'find_war3', return_value=(300, 400)), \
            patch.object(m.Path, 'is_file', return_value=True), \
            patch.object(m.threading, 'Thread') as worker:
        trainer.refresh_window(allow_pid_change=True)
    assert trainer.pid == 400
    assert trainer._native_selection_unavailable
    worker.assert_not_called()
