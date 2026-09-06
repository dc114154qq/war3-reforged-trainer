"""Run the C group mover against fake natives; never attach to Warcraft."""
import ctypes
import faulthandler
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


HARNESS = r'''
#include "HELPER_SOURCE"
static unsigned selected_count, cursor, moved, destroyed, bad_target, fail_at;
static uint64_t generation;
static uint64_t fake_create(void) { return 1; }
static uint64_t fake_player(void) { return 2; }
static void fake_enum(uint64_t g, uint64_t p, uint64_t f) { cursor = 0; }
static uint64_t fake_first(uint64_t g) {
    return cursor < selected_count ? generation + cursor + 1 : 0;
}
static void fake_remove(uint64_t g, uint64_t u) { ++cursor; }
static void fake_destroy(uint64_t g) { ++destroyed; }
static void fake_move(uint64_t u, float *x, float *y) {
    if (moved + 1 == fail_at) RaiseException(0xe0000001u, 0, 0, NULL);
    if (u != generation + moved + 1 || *x != 12.5f || *y != -8.0f) ++bad_target;
    ++moved;
}
__declspec(dllexport) unsigned run_case(unsigned count, unsigned fail, uint64_t gen, unsigned missing) {
    NativeOp op = {0};
    selected_count = count; fail_at = fail; generation = gen;
    cursor = moved = destroyed = bad_target = 0;
    g_persistent_ready = 0;
    for (unsigned i = 0; i < sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]); ++i) {
        g_persistent_natives[i].name = g_persistent_native_names[i];
        g_persistent_natives[i].handler = (uint64_t)(uintptr_t)fake_create;
        const char *name = g_persistent_native_names[i];
        if (!strcmp(name, "CreateGroup")) g_persistent_natives[i].handler = (uint64_t)(uintptr_t)fake_create;
        if (!strcmp(name, "GetLocalPlayer")) g_persistent_natives[i].handler = (uint64_t)(uintptr_t)fake_player;
        if (!strcmp(name, "GroupEnumUnitsSelected")) g_persistent_natives[i].handler = (uint64_t)(uintptr_t)fake_enum;
        if (!strcmp(name, "FirstOfGroup")) g_persistent_natives[i].handler = (uint64_t)(uintptr_t)fake_first;
        if (!strcmp(name, "GroupRemoveUnit")) g_persistent_natives[i].handler = missing ? 0 : (uint64_t)(uintptr_t)fake_remove;
        if (!strcmp(name, "DestroyGroup")) g_persistent_natives[i].handler = (uint64_t)(uintptr_t)fake_destroy;
    }
    op.handler = (uint64_t)(uintptr_t)fake_move;
    return war3_move_selected_group_at_point(&op, 0xc100000041480000ULL);
}
__declspec(dllexport) unsigned moved_count(void) { return moved; }
__declspec(dllexport) unsigned destroyed_count(void) { return destroyed; }
__declspec(dllexport) unsigned invalid_target_count(void) { return bad_target; }
'''


class NativeGroupMoveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which("clang")
        if not compiler:
            raise unittest.SkipTest("clang is required for the native mock harness")
        cls.directory = tempfile.TemporaryDirectory(prefix="war3-group-unit-test-")
        cls.addClassCleanup(cls.directory.cleanup)
        root = Path(cls.directory.name)
        source = root / "group_test.c"
        helper = Path(__file__).with_name("tools") / "war3_native_helper.c"
        source.write_text(HARNESS.replace("HELPER_SOURCE", helper.as_posix()), encoding="utf-8")
        library = root / "group_test.dll"
        subprocess.run([compiler, "-shared", "-O2", "-Wno-microsoft-goto", str(source),
                        "-o", str(library), "-luser32", "-lkernel32"],
                       check=True, capture_output=True, timeout=60)
        cls.native = ctypes.CDLL(str(library))
        import _ctypes
        cls.addClassCleanup(_ctypes.FreeLibrary, cls.native._handle)
        cls.native.run_case.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_uint64, ctypes.c_uint]
        cls.native.run_case.restype = ctypes.c_uint

    def test_group_sizes_and_changed_handles(self):
        for count, generation in ((1, 0x100000), (9, 0x200000), (12, 0x300000)):
            with self.subTest(count=count):
                self.assertEqual(self.native.run_case(count, 0, generation, 0), 0)
                self.assertEqual(self.native.moved_count(), count)
                self.assertEqual(self.native.destroyed_count(), 1)
                self.assertEqual(self.native.invalid_target_count(), 0)

    def test_empty_and_oversized_groups_change_nothing(self):
        for count, error in ((0, 1168), (13, 234)):
            with self.subTest(count=count):
                self.assertEqual(self.native.run_case(count, 0, 0x400000, 0), error)
                self.assertEqual(self.native.moved_count(), 0)
                self.assertEqual(self.native.destroyed_count(), 1)

    def test_exception_stops_movement_and_cleans_up_group(self):
        # Python's vectored faulthandler runs before the C SEH handler. This
        # exception is deliberately raised and caught by the group mover.
        enabled = faulthandler.is_enabled()
        try:
            faulthandler.disable()
            self.assertEqual(self.native.run_case(9, 3, 0x500000, 0), 0xe0000001)
        finally:
            if enabled:
                faulthandler.enable()
        self.assertEqual(self.native.moved_count(), 2)
        self.assertEqual(self.native.destroyed_count(), 1)

    def test_missing_group_native_changes_nothing(self):
        self.assertEqual(self.native.run_case(9, 0, 0x600000, 1), 127)
        self.assertEqual(self.native.moved_count(), 0)
        self.assertEqual(self.native.destroyed_count(), 0)
