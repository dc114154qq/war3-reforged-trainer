import ast
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import war3_reforged_trainer as trainer_module


SOURCE_PATH = Path(__file__).with_name("war3_reforged_trainer.py")


class _Diagnostics:
    latest_path = Path("backup-test.log")

    def __init__(self):
        self.close_calls = 0

    def close(self):
        self.close_calls += 1


class _BackupMemory:
    def __init__(self, pid: int, diagnostics=None, write: bool = False):
        self.pid = pid
        self.write = write
        self.diagnostics = diagnostics or _Diagnostics()
        self.force_refresh = None
        self.closed = False

    def regions(self, force_refresh: bool = False):
        self.force_refresh = force_refresh
        return []

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        self.close()


class ElephantSourceRoutingTests(unittest.TestCase):
    def test_backup_log_archives_are_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            log_root = Path(directory)
            for index in range(trainer_module.Win10ReadLogger.MAX_ARCHIVE_LOGS + 5):
                (log_root / f"win10-read-20260719-000000-{index:03d}-pid1.log").touch()

            trainer_module.Win10ReadLogger._prune_archives(log_root)

            archives = list(log_root.glob("win10-read-*-pid*.log"))
            self.assertLessEqual(
                len(archives),
                trainer_module.Win10ReadLogger.MAX_ARCHIVE_LOGS - 1,
            )

    def test_normal_source_returns_main_trainer(self):
        main = object.__new__(trainer_module.War3Trainer)
        identity = (0x10, 0x20, 0x30)
        self.assertIs(main.trainer_for_read_source(identity, False), main)

    def test_backup_source_returns_matching_backup_session(self):
        main = object.__new__(trainer_module.War3Trainer)
        backup = object.__new__(trainer_module.BackupReadWar3Trainer)
        main.pid = backup.pid = 123
        identity = (0x10, 0x20, 0x30)
        main._win10_session_trainer = backup
        main._win10_session_identity = identity
        backup._backup_selected_identity = None

        selected = main.trainer_for_read_source(identity, True)

        self.assertIs(selected, backup)
        self.assertEqual(backup._backup_selected_identity, identity)

    def test_backup_source_rejects_stale_session(self):
        main = object.__new__(trainer_module.War3Trainer)
        main.pid = 123
        main._win10_session_trainer = None
        main._win10_session_identity = None
        with self.assertRaisesRegex(RuntimeError, "备用读取会话已经失效"):
            main.trainer_for_read_source((0x10, 0x20, 0x30), True)

    def test_failed_backup_read_invalidates_previous_session(self):
        main = object.__new__(trainer_module.War3Trainer)
        backup = object.__new__(trainer_module.BackupReadWar3Trainer)
        diagnostics = _Diagnostics()
        backup._backup_diagnostics = diagnostics
        main.pid = backup.pid = 123
        main._win10_session_trainer = backup
        main._win10_session_identity = (0x10, 0x20, 0x30)

        with patch.object(
            trainer_module,
            "Win10ReadLogger",
            side_effect=RuntimeError("log unavailable"),
        ):
            with self.assertRaisesRegex(RuntimeError, "log unavailable"):
                main.read_selected_unit_fields_win10()

        self.assertIsNone(main._win10_session_trainer)
        self.assertIsNone(main._win10_session_identity)
        self.assertEqual(diagnostics.close_calls, 1)

    def test_backup_memory_factory_never_builds_normal_memory(self):
        backup = object.__new__(trainer_module.BackupReadWar3Trainer)
        backup.pid = 123
        backup._last_win10_log_path = ""
        backup._readable_pointer_bases = ()
        backup._readable_pointer_ends = ()
        backup._backup_diagnostics = _Diagnostics()
        with patch.object(trainer_module, "Win10ProcessMemory", _BackupMemory):
            memory = backup._process_memory(write=True)

        self.assertIsInstance(memory, _BackupMemory)
        self.assertTrue(memory.write)
        self.assertTrue(memory.force_refresh)

    def test_backup_memory_factory_reuses_session_diagnostics(self):
        backup = object.__new__(trainer_module.BackupReadWar3Trainer)
        backup.pid = 123
        backup._last_win10_log_path = ""
        backup._readable_pointer_bases = ()
        backup._readable_pointer_ends = ()
        diagnostics = _Diagnostics()
        backup._backup_diagnostics = diagnostics

        with patch.object(trainer_module, "Win10ProcessMemory", _BackupMemory):
            first = backup._process_memory()
            second = backup._process_memory(write=True)

        self.assertIs(first.diagnostics, diagnostics)
        self.assertIs(second.diagnostics, diagnostics)
        self.assertEqual(diagnostics.close_calls, 0)

    def test_backup_native_discovery_rejects_normal_memory(self):
        backup = object.__new__(trainer_module.BackupReadWar3Trainer)
        with self.assertRaisesRegex(RuntimeError, "拒绝回落到普通内存路径"):
            backup._discover_native_handlers_near_table(object(), ("CreateUnit",))

    def test_backup_elephant_handlers_use_win10_discovery(self):
        backup = object.__new__(trainer_module.BackupReadWar3Trainer)
        handler = trainer_module.NativeHandler("CreateUnit", 0x1000, 0x2000)
        backup._native_handlers = {"CreateUnit": handler}
        pm = object.__new__(trainer_module.Win10ProcessMemory)
        with (
            patch.object(
                trainer_module.War3Trainer,
                "_discover_native_handlers_near_table_win10",
                return_value={"CreateUnit": handler},
            ) as backup_discovery,
            patch.object(
                trainer_module.War3Trainer,
                "_discover_native_handlers_near_table",
                side_effect=AssertionError("ordinary native discovery used"),
            ),
        ):
            handlers = trainer_module.War3Trainer._elephant_handlers(
                backup,
                pm,
                ("CreateUnit",),
            )

        self.assertEqual(handlers, {"CreateUnit": handler})
        backup_discovery.assert_called_once()

    def test_inherited_elephant_method_uses_virtual_memory_factory(self):
        backup = object.__new__(trainer_module.BackupReadWar3Trainer)
        memory = _BackupMemory(123)
        handler = trainer_module.NativeHandler("GetHeroLevel", 0x1000, 0x2000)
        backup._process_memory = unittest.mock.Mock(return_value=memory)
        backup._elephant_selected_handle = unittest.mock.Mock(return_value=0x3000)
        backup._elephant_handlers = unittest.mock.Mock(
            return_value={"GetHeroLevel": handler}
        )
        backup._run_native_helper_ops = unittest.mock.Mock(
            return_value=[trainer_module.NativeHelperOpResult(kind=0, result=17)]
        )

        level = backup.get_selected_hero_level()

        self.assertEqual(level, 17)
        backup._process_memory.assert_called_once_with()
        self.assertTrue(memory.closed)

    def test_normal_elephant_method_never_builds_backup_memory(self):
        normal = object.__new__(trainer_module.War3Trainer)
        normal.pid = 123
        memory = _BackupMemory(123)
        handler = trainer_module.NativeHandler("GetHeroLevel", 0x1000, 0x2000)
        normal._elephant_selected_handle = unittest.mock.Mock(return_value=0x3000)
        normal._elephant_handlers = unittest.mock.Mock(
            return_value={"GetHeroLevel": handler}
        )
        normal._run_native_helper_ops = unittest.mock.Mock(
            return_value=[trainer_module.NativeHelperOpResult(kind=0, result=23)]
        )

        with (
            patch.object(trainer_module, "ProcessMemory", return_value=memory) as ordinary,
            patch.object(
                trainer_module,
                "Win10ProcessMemory",
                side_effect=AssertionError("backup memory used"),
            ),
        ):
            level = normal.get_selected_hero_level()

        self.assertEqual(level, 23)
        ordinary.assert_called_once_with(123, write=False)
        self.assertTrue(memory.closed)

    def test_cached_clone_does_not_reselect_unit(self):
        trainer = object.__new__(trainer_module.War3Trainer)
        memory = _BackupMemory(123)
        handler = trainer_module.NativeHandler("CreateUnit", 0x1000, 0x2000)
        trainer._process_memory = unittest.mock.Mock(return_value=memory)
        trainer.query_mouse_world_position = unittest.mock.Mock(return_value=(1.0, 2.0))
        trainer._coerce_memory_value = unittest.mock.Mock(return_value=0x68666F6F)
        trainer._elephant_selected_candidate = unittest.mock.Mock(
            side_effect=AssertionError("selected unit was read again")
        )
        trainer._elephant_handlers = unittest.mock.Mock(
            return_value={"GetLocalPlayer": handler, "CreateUnit": handler}
        )
        trainer._run_native_helper_ops = unittest.mock.Mock(
            return_value=[trainer_module.NativeHelperOpResult(kind=0, result=0x4444)]
        )

        rawcode, handle = trainer.create_local_unit(
            "hfoo",
            use_selected_lookup=False,
        )

        self.assertEqual((rawcode, handle), (0x68666F6F, 0x4444))
        trainer._elephant_selected_candidate.assert_not_called()

    def test_elephant_gui_functions_do_not_call_main_trainer_directly(self):
        tree = ast.parse(SOURCE_PATH.read_text(encoding="utf-8"))
        run_gui = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "run_gui"
        )
        offenders = []
        for function in (
            node
            for node in run_gui.body
            if isinstance(node, ast.FunctionDef)
            and node.name.startswith("elephant_")
            and node.name != "elephant_trainer"
        ):
            for node in ast.walk(function):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "trainer"
                ):
                    offenders.append((function.name, node.lineno))
        self.assertEqual(offenders, [])

    def test_hotkeys_do_not_bind_main_trainer(self):
        tree = ast.parse(SOURCE_PATH.read_text(encoding="utf-8"))
        run_gui = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "run_gui"
        )
        assignment = next(
            node
            for node in run_gui.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "hotkey_callbacks"
        )
        direct_calls = [
            node.lineno
            for node in ast.walk(assignment)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "trainer"
        ]
        self.assertEqual(direct_calls, [])

    def test_inline_gui_callbacks_do_not_bind_main_trainer(self):
        tree = ast.parse(SOURCE_PATH.read_text(encoding="utf-8"))
        run_gui = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "run_gui"
        )
        direct_calls = []
        for statement in run_gui.body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            direct_calls.extend(
                node.lineno
                for node in ast.walk(statement)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "trainer"
            )
        self.assertEqual(direct_calls, [])


if __name__ == "__main__":
    unittest.main()
