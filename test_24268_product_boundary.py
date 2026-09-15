from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import war3_reforged_trainer as module


def test_multiple_clients_require_pid_without_reading_the_other_client():
    windows = [(100, 1000, "Warcraft III"), (200, 2000, "Warcraft III")]
    with patch.object(module, "enum_war3_windows", return_value=windows), \
            patch.object(module, "ProcessMemory", side_effect=AssertionError("Client probe")):
        with pytest.raises(RuntimeError, match="explicit PID"):
            module.find_war3()
        assert module.find_war3(1000) == (100, 1000)
        assert module.find_war3(2000) == (200, 2000)


def test_stale_requested_pid_is_released_after_game_restart():
    windows = [(300, 3000, "Warcraft III")]
    with patch.object(module, "enum_war3_windows", return_value=windows):
        assert module.resolve_requested_war3_pid(2000) is None
        assert module.resolve_requested_war3_pid(3000) == 3000


def test_window_discovery_retries_transient_loading_window():
    with patch.object(
        module,
        "find_war3",
        side_effect=[RuntimeError("没有找到标题为 Warcraft III 的可见窗口"), (300, 3000)],
    ), patch.object(module.time, "sleep") as sleep:
        assert module.find_war3_with_retry(3000, attempts=2, delay_seconds=0.25) == (300, 3000)
    sleep.assert_called_once_with(0.25)


def test_window_discovery_does_not_retry_multiple_client_selection_error():
    with patch.object(
        module,
        "find_war3",
        side_effect=RuntimeError("Multiple Warcraft III clients are open; select an explicit PID"),
    ), patch.object(module.time, "sleep") as sleep:
        with pytest.raises(RuntimeError, match="explicit PID"):
            module.find_war3_with_retry()
    sleep.assert_not_called()


def test_window_discovery_rebinds_to_same_installation_after_pid_restart():
    windows = [(100, 1000, "Warcraft III"), (200, 2000, "Warcraft III")]
    with patch.object(
        module,
        "find_war3",
        side_effect=RuntimeError("没有找到标题为 Warcraft III 的可见窗口"),
    ), patch.object(module, "enum_war3_windows", return_value=windows), patch.object(
        module,
        "process_executable_path",
        side_effect=lambda pid: {
            1000: r"E:\\Warcraft III",
            2000: r"E:\\Warcraft III - 副本",
        }[pid],
    ):
        assert module.find_war3_with_retry(
            9999,
            attempts=1,
            executable_path=r"e:\\warcraft iii - 副本",
        ) == (200, 2000)


def test_3_0_world_actions_are_not_blocked_by_selection_executor_state():
    import ast
    source = ast.parse(module.Path(module.__file__).read_text(encoding="utf-8"))
    function = next(
        node for node in ast.walk(source)
        if isinstance(node, ast.FunctionDef) and node.name == "elephant_action"
    )
    called = []
    from typing import Callable
    namespace = {"Callable": Callable}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "<elephant-action>", "exec"), namespace)
    assert namespace["elephant_action"](lambda: called.append(True), "done") == "done"
    assert called == [True]


def test_legacy_dll_files_never_satisfy_24268_loader(tmp_path):
    (tmp_path / "tools").mkdir()
    for name in ("war3_native_helper.dll", "war3_native_helper.3.0-live.dll"):
        (tmp_path / "tools" / name).write_bytes(b"legacy fixture")
    trainer = object.__new__(module.War3Trainer)
    with patch.object(module.sys, "_MEIPASS", str(tmp_path), create=True):
        with pytest.raises(RuntimeError, match="24268 engine execution module"):
            trainer._native_helper_dll_path()


def test_operation_log_preserves_traceback_pid_and_operation(tmp_path):
    with patch.object(module.sys, "frozen", True, create=True), \
            patch.object(module.sys, "executable", str(tmp_path / "trainer.exe")):
        try:
            raise RuntimeError("read_u64 fixture failure")
        except RuntimeError as exc:
            path = Path(module.record_operation_failure(1234, "read_selected_fields", exc))
    text = path.read_text(encoding="utf-8-sig")
    assert "read_selected_fields" in text
    assert "pid=1234" in text
    assert "Traceback" in text
    assert "read_u64 fixture failure" in text
    assert (tmp_path / "log" / "trainer-error-latest.log").is_file()
