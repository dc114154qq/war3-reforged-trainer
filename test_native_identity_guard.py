"""Run the real C command dispatcher in an isolated fake game environment."""
import ctypes
import faulthandler
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


HARNESS = r'''
#include <windows.h>
#include <wchar.h>
static wchar_t test_directory[MAX_PATH];
static DWORD fake_temp_path(DWORD count, wchar_t *path) {
    size_t n = wcslen(test_directory);
    if (n + 1 >= count) return 0;
    memcpy(path, test_directory, (n + 1) * sizeof(wchar_t));
    return (DWORD)n;
}
#define GetTempPathW fake_temp_path
#include "HELPER_SOURCE"
#undef GetTempPathW
static uint8_t object[0x20], other[0x20], owner[0xa0];
static unsigned fault, writes, bad_arguments;
static const uint64_t full = 0x123400005678ULL;
static uint64_t fake_unit(uint64_t handle) {
    if (handle != 7) return 0;
    if (fault == 1) return 0;
    if (fault == 2) return (uint64_t)(uintptr_t)other;
    if (fault == 10) RaiseException(0xe0000001u, 0, 0, NULL);
    return (uint64_t)(uintptr_t)object;
}
static uint64_t fake_agent(uint32_t slot, uint32_t serial) {
    if (fault == 3 || slot != (uint32_t)full || serial != (uint32_t)(full >> 32)) return 0;
    return (uint64_t)(uintptr_t)owner;
}
static void fake_max(uint64_t handle, int32_t value) {
    if (handle != 7 || value != 300) ++bad_arguments;
    ++writes;
    if (fault == 7) *(uint64_t *)(object + 0x18) = full + (1ULL << 32);
}
static void fake_state(uint64_t handle, int32_t state, float *value) {
    if (handle != 7 || state != 0 || *value != 150.0f) ++bad_arguments;
    ++writes;
}
static void fake_move(uint64_t handle, float *x, float *y) {
    if (handle != 7 || *x != 12.0f || *y != -4.0f) ++bad_arguments;
    ++writes;
}
static uint8_t item_object[0x20];
static int32_t quantity;
static uint64_t fake_item_slot(uint64_t unit, int32_t slot) {
    if (unit != 7 || slot != 2) ++bad_arguments;
    return fault == 21 || (fault == 23 && writes) ? 101 : 100;
}
static uint64_t fake_item_resolver(uint64_t item) {
    return fault == 22 ? 0 : (uint64_t)(uintptr_t)item_object;
}
static void fake_set_charges(uint64_t item, int32_t value) {
    if (item != 100 || value != 1500) ++bad_arguments;
    ++writes; quantity = value;
    if (fault == 26) *(uint64_t *)(item_object + 0x18) += 1;
    if (fault == 27) *(uint64_t *)(owner + 0x20) += 1;
}
static int32_t fake_get_charges(uint64_t item) { return fault == 24 ? quantity - 1 : quantity; }
__declspec(dllexport) DWORD execute(const wchar_t *directory, unsigned failure, unsigned *out) {
    NativeCommand cmd = {0}; DWORD bytes; wchar_t path[MAX_PATH]; HANDLE file;
    fault = failure; writes = bad_arguments = 0;
    if (wcslen(directory) >= MAX_PATH - 1) return ERROR_INVALID_PARAMETER;
    wcscpy(test_directory, directory);
    ZeroMemory(object, sizeof(object)); ZeroMemory(owner, sizeof(owner));
    *(uint64_t *)(object + 0x18) = fault == 4 ? full + 1 : full;
    *(uint64_t *)(owner + 0x18) = fault == 11 ? 0 : 0x2b7733752b61676cULL;
    *(uint64_t *)(owner + 0x20) = fault == 12 ? full + 1 : full;
    *(uint64_t *)(owner + 0x90) = fault == 5 ? 0 : (uint64_t)(uintptr_t)object;
    g_persistent_unit_resolver = fault == 6 ? 0 : (uint64_t)(uintptr_t)fake_unit;
    g_persistent_agent_resolver = (uint64_t)(uintptr_t)fake_agent;
    cmd.magic = WAR3_NATIVE_MAGIC; cmd.version = WAR3_NATIVE_VERSION;
    cmd.status = WAR3_NATIVE_STATUS_PENDING; cmd.unit_handle = fault == 13 ? full : 7;
    cmd.op_count = 4;
    cmd.ops[0].kind = WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;
    cmd.ops[0].handler = (uint64_t)(uintptr_t)object;
    cmd.ops[0].arg0 = full; cmd.ops[0].arg1 = (uint64_t)(uintptr_t)owner;
    cmd.ops[1].kind = WAR3_NATIVE_OP_JASS_SET_UNIT_INT;
    cmd.ops[1].handler = (uint64_t)(uintptr_t)fake_max; cmd.ops[1].arg0 = 300;
    cmd.ops[2].kind = WAR3_NATIVE_OP_JASS_SET_UNIT_STATE;
    cmd.ops[2].handler = (uint64_t)(uintptr_t)fake_state; cmd.ops[2].arg0 = 0x43160000u;
    cmd.ops[3].kind = WAR3_NATIVE_OP_JASS_SET_UNIT_POSITION;
    cmd.ops[3].handler = (uint64_t)(uintptr_t)fake_move;
    cmd.ops[3].rawcode = 0x41400000u; cmd.ops[3].arg0 = 0xc0800000u;
    if (fault == 8) { memmove(cmd.ops, cmd.ops + 1, 3 * sizeof(NativeOp)); cmd.op_count = 3; }
    if (fault == 9) { NativeOp swap = cmd.ops[0]; cmd.ops[0] = cmd.ops[1]; cmd.ops[1] = swap; }
    if (fault >= 20) {
        quantity = 3;
        *(uint64_t *)(item_object + 0x18) = 0x555500006666ULL;
        g_persistent_item_resolver = (uint64_t)(uintptr_t)fake_item_resolver;
        for (unsigned i = 0; i < sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]); ++i) {
            const char *name = g_persistent_native_names[i];
            g_persistent_natives[i].name = name;
            g_persistent_natives[i].handler = 0;
            if (!strcmp(name, "UnitItemInSlot")) g_persistent_natives[i].handler = (uint64_t)(uintptr_t)fake_item_slot;
            if (!strcmp(name, "SetItemCharges")) g_persistent_natives[i].handler = (uint64_t)(uintptr_t)fake_set_charges;
            if (!strcmp(name, "GetItemCharges") && fault != 25) g_persistent_natives[i].handler = (uint64_t)(uintptr_t)fake_get_charges;
        }
        cmd.op_count = 2;
        cmd.ops[1].kind = WAR3_NATIVE_OP_SET_BOUND_ITEM_CHARGES;
        cmd.ops[1].rawcode = 2;
        cmd.ops[1].handler = (uint64_t)(uintptr_t)item_object;
        cmd.ops[1].arg0 = 100; cmd.ops[1].arg1 = 1500;
    }
    command_path(path, MAX_PATH);
    file = CreateFileW(path, GENERIC_READ | GENERIC_WRITE, 0, NULL, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) return GetLastError();
    if (!WriteFile(file, &cmd, sizeof(cmd), &bytes, NULL)) { CloseHandle(file); DeleteFileW(path); return ERROR_WRITE_FAULT; }
    CloseHandle(file);
    run_command();
    file = CreateFileW(path, GENERIC_READ, 0, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) return GetLastError();
    if (!ReadFile(file, &cmd, sizeof(cmd), &bytes, NULL)) { CloseHandle(file); DeleteFileW(path); return ERROR_READ_FAULT; }
    CloseHandle(file); DeleteFileW(path);
    if (fault >= 20 && cmd.status == WAR3_NATIVE_STATUS_OK && cmd.ops[1].result != 1500) ++bad_arguments;
    out[0] = cmd.status; out[1] = cmd.last_error; out[2] = writes; out[3] = bad_arguments;
    return ERROR_SUCCESS;
}
'''


class NativeIdentityGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which('clang')
        if not compiler:
            raise unittest.SkipTest('clang required')
        cls.directory = tempfile.TemporaryDirectory(prefix='war3-guard-test-')
        cls.addClassCleanup(cls.directory.cleanup)
        root = Path(cls.directory.name)
        source = root / 'guard.c'
        helper = Path(__file__).with_name('tools') / 'war3_native_helper.c'
        source.write_text(HARNESS.replace('HELPER_SOURCE', helper.as_posix()), encoding='utf-8')
        library = root / 'guard.dll'
        subprocess.run([compiler, '-shared', '-O2', '-Wno-microsoft-goto', str(source),
                        '-o', str(library), '-luser32', '-lkernel32'], check=True, capture_output=True, timeout=60)
        cls.native = ctypes.CDLL(str(library))
        import _ctypes
        cls.addClassCleanup(_ctypes.FreeLibrary, cls.native._handle)
        cls.native.execute.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_uint)]
        cls.native.execute.restype = ctypes.c_uint

    def execute(self, fault):
        out = (ctypes.c_uint * 4)()
        enabled = faulthandler.is_enabled()
        try:
            faulthandler.disable()
            self.assertEqual(self.native.execute(self.directory.name + '\\', fault, out), 0)
        finally:
            if enabled:
                faulthandler.enable()
        return tuple(out)

    def test_matching_identity_dispatches_all_setters_with_jass_handle(self):
        self.assertEqual(self.execute(0), (2, 0, 3, 0))

    def test_invalid_identity_and_missing_or_misplaced_guard_never_write(self):
        for fault in (1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13):
            with self.subTest(fault=fault):
                status, error, writes, bad = self.execute(fault)
                self.assertEqual(status, 3)
                self.assertNotEqual(error, 0)
                self.assertEqual((writes, bad), (0, 0))

    def test_recycled_identity_after_first_setter_stops_remaining_writes(self):
        self.assertEqual(self.execute(7), (3, 6, 1, 0))

    def test_bound_item_quantity_supports_large_values_and_immediate_readback(self):
        self.assertEqual(self.execute(20), (2, 0, 1, 0))

    def test_changed_or_unresolved_item_prevents_setter(self):
        for fault in (21, 22, 25):
            with self.subTest(fault=fault):
                status, error, writes, bad = self.execute(fault)
                self.assertEqual((status, writes, bad), (3, 0, 0))
                self.assertNotEqual(error, 0)

    def test_item_or_unit_changes_during_setter_are_not_reported_as_success(self):
        for fault in (23, 24, 26, 27):
            with self.subTest(fault=fault):
                status, error, writes, bad = self.execute(fault)
                self.assertEqual((status, writes, bad), (3, 1, 0))
                self.assertNotEqual(error, 0)
