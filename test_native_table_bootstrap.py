"""Exercise production table lookup on synthetic memory and Python bootstrap IPC."""
import ctypes
import faulthandler
from pathlib import Path
import shutil
import subprocess
import threading
from unittest.mock import Mock

import pytest
import war3_reforged_trainer as module
from war3_native_profile import NATIVE_INDEX, PROFILE_ID


HARNESS = r'''
#include <windows.h>
static wchar_t test_directory[MAX_PATH];
static DWORD test_temp_path(DWORD size, wchar_t *path) {
    if (wcslen(test_directory) >= size) return 0;
    wcscpy(path, test_directory); return (DWORD)wcslen(path);
}
#define GetTempPathW test_temp_path
#include "HELPER_SOURCE"
__declspec(dllexport) DWORD lookup(unsigned fault, uint64_t *out) {
    uint8_t table[0x48] = {0}, buckets[48] = {0}, nodes[3][0x48] = {0};
    uint8_t *code = VirtualAlloc(NULL, 4096, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    War3BootstrapNative profile = {"ExampleNative", "(Hunit;)I", 0, 0};
    uint64_t handler = 123;
    DWORD result;
    if (!code) return ERROR_OUTOFMEMORY;
    memset(code, 0xc3, 64);
    profile.code_hash = war3_bootstrap_hash(code, 64);
    *(uint32_t *)(table + 0x40) = 1;
    *(uint8_t **)(table + 0x30) = buckets;
    *(int32_t *)(buckets + 24) = 0;
    *(uintptr_t *)(buckets + 24 + 0x10) = (uintptr_t)nodes[0];
    *(uint32_t *)nodes[0] = 3;
    *(uintptr_t *)(nodes[0] + 8) = (uintptr_t)nodes[1];
    *(const char **)(nodes[0] + 0x28) = "CollisionName";
    *(uint32_t *)nodes[1] = 3;
    *(uintptr_t *)(nodes[1] + 8) = 1;
    *(const char **)(nodes[1] + 0x28) = "ExampleNative";
    *(uint64_t *)(nodes[1] + 0x30) = (uint64_t)(uintptr_t)code;
    *(const char **)(nodes[1] + 0x40) = "(Hunit;)I";
    if (fault == 1) *(uint32_t *)(table + 0x40) = UINT32_MAX;
    if (fault == 2) *(uint32_t *)(table + 0x40) = 5;
    if (fault == 3) *(int32_t *)(buckets + 24) = 0x1000;
    if (fault == 4) *(uintptr_t *)(buckets + 24 + 0x10) = 1;
    if (fault == 5) *(uintptr_t *)(nodes[0] + 8) = (uintptr_t)nodes[0];
    if (fault == 6) *(const char **)(nodes[1] + 0x40) = "(Hitem;)I";
    if (fault == 7) *(uint64_t *)(nodes[1] + 0x30) += 16;
    if (fault == 8) code[0] ^= 1;
    if (fault == 9) *(const char **)(nodes[1] + 0x28) = NULL;
    if (fault == 10) *(uint8_t **)(table + 0x30) = NULL;
    if (fault == 11) *(uintptr_t *)(buckets + 24 + 0x10) = (uintptr_t)nodes[0] + 2;
    if (fault == 12) { /* Valid negative signed offset; chain lives at node+0. */
        *(int32_t *)(buckets + 24) = -8;
        *(uintptr_t *)(buckets + 24 + 0x10) = (uintptr_t)nodes[1];
        *(uintptr_t *)nodes[1] = 3; /* hash 3 and low-bit end marker */
    }
    result = war3_bootstrap_find(table, 3, &profile, code, &handler);
    out[0] = handler == (uint64_t)(uintptr_t)code;
    out[1] = handler;
    VirtualFree(code, 0, MEM_RELEASE);
    return result;
}
__declspec(dllexport) DWORD reject_host_image(void) {
    return war3_bootstrap_validate_image((uint8_t *)GetModuleHandleW(NULL));
}
__declspec(dllexport) DWORD dispatch(const wchar_t *directory, unsigned kind, unsigned fault) {
    NativeCommand cmd = {0}; wchar_t path[MAX_PATH]; DWORD bytes; HANDLE file;
    wcscpy(test_directory, directory); command_path(path, MAX_PATH);
    cmd.magic = WAR3_NATIVE_MAGIC; cmd.version = WAR3_NATIVE_VERSION;
    cmd.status = WAR3_NATIVE_STATUS_PENDING; cmd.op_count = 1; cmd.ops[0].kind = kind;
    cmd.ops[0].rawcode = kind == 139 ? WAR3_BOOTSTRAP_PROFILE_ID : 0;
    cmd.ops[0].arg0 = WAR3_BOOTSTRAP_PROFILE_ID;
    if (fault) { cmd.ops[0].rawcode = 0; cmd.ops[0].arg0 = 0; }
    file = CreateFileW(path, GENERIC_READ | GENERIC_WRITE, 0, NULL, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) return 0xffffffffu;
    WriteFile(file, &cmd, sizeof(cmd), &bytes, NULL); CloseHandle(file);
    run_command();
    file = CreateFileW(path, GENERIC_READ, 0, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) return 0xffffffffu;
    ReadFile(file, &cmd, sizeof(cmd), &bytes, NULL); CloseHandle(file); DeleteFileW(path);
    return cmd.status == WAR3_NATIVE_STATUS_FAILED ? cmd.ops[0].last_error : 0;
}
'''


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler = shutil.which('clang')
    if not compiler:
        pytest.skip('clang required')
    directory = tmp_path_factory.mktemp('native-table')
    source, library = directory/'test.c', directory/'test.dll'
    source.write_text(HARNESS.replace('HELPER_SOURCE', (Path(__file__).parent/'tools/war3_native_helper.c').as_posix()))
    subprocess.run([compiler, '-shared', '-O2', '-Wno-microsoft-goto', str(source), '-o', str(library),
                    '-luser32', '-lkernel32'], check=True, capture_output=True, timeout=60)
    lib = ctypes.CDLL(str(library))
    lib.lookup.argtypes = [ctypes.c_uint, ctypes.POINTER(ctypes.c_uint64)]
    lib.lookup.restype = ctypes.c_uint
    lib.reject_host_image.restype = ctypes.c_uint
    lib.dispatch.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_uint]
    lib.dispatch.restype = ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)


@pytest.mark.parametrize('fault', range(13))
def test_real_c_bucket_lookup_checks_name_signature_code_and_bounded_chain(native, fault):
    out = (ctypes.c_uint64*2)()
    enabled = faulthandler.is_enabled()
    try:
        faulthandler.disable()
        error = native.lookup(fault, out)
    finally:
        if enabled:
            faulthandler.enable()
    if fault in (0, 12):
        assert error == 0 and out[0] == 1 and out[1]
    else:
        assert error and out[1] == 0


def test_wrong_executable_rejected_before_context_call(native):
    assert native.reject_host_image() != 0


@pytest.mark.parametrize('kind', [139, 140])
def test_actual_dispatch_accepts_zero_handler_and_reaches_profile_validation(native, tmp_path, kind):
    assert native.dispatch(str(tmp_path)+'\\', kind, 0) == native.reject_host_image()
    assert native.dispatch(str(tmp_path)+'\\', kind, 1) == 1306  # ERROR_REVISION_MISMATCH


def make_trainer():
    trainer = module.War3Trainer.__new__(module.War3Trainer)
    trainer._persistent_bootstrap_lock = threading.RLock()
    trainer._native_handlers = {'old': module.NativeHandler('old', 99, 0xdeadbeef)}
    trainer._process_memory = Mock(side_effect=AssertionError('No external memory access'))
    trainer._find_native_table_regions = Mock(side_effect=AssertionError('No heap scan'))
    values = tuple(0x100000 + i*0x100 for i in range(len(trainer.PERSISTENT_NATIVE_NAMES)+3))
    trainer._run_native_helper_ops = Mock(return_value=(module.NativeHelperOpResult(139, len(values)-3, extra_results=values),))
    return trainer, values


def test_bootstrap_uses_one_dll_command_and_discards_previous_process_records():
    trainer, values = make_trainer()
    assert trainer.persistent_native_init() == 29
    trainer._run_native_helper_ops.assert_called_once_with(0, ((139, PROFILE_ID, 0, 0, 0),), timeout_ms=30000)
    assert 'old' not in trainer._native_handlers
    assert trainer._jass_unit_resolver_address == values[0]
    assert trainer._native_handlers['UnitAddAbility'] == module.NativeHandler('UnitAddAbility', 0, values[3])
    trainer._process_memory.assert_not_called()


@pytest.mark.parametrize('failure', ['exception', 'count', 'payload', 'address'])
def test_failed_bootstrap_does_not_publish_partial_handlers_or_fallback(failure):
    trainer, values = make_trainer()
    original = trainer._native_handlers.copy()
    if failure == 'exception':
        trainer._run_native_helper_ops.side_effect = RuntimeError('wrong build')
    else:
        count = 28 if failure == 'count' else 29
        if failure == 'payload': values = values[:-1]
        if failure == 'address': values = (0,)+values[1:]
        trainer._run_native_helper_ops.return_value = (module.NativeHelperOpResult(139, count, extra_results=values),)
    with pytest.raises(RuntimeError): trainer.persistent_native_init()
    assert trainer._native_handlers == original
    assert not getattr(trainer, '_persistent_native_initialized', False)
    trainer._find_native_table_regions.assert_not_called()


def test_additional_natives_use_profile_indexes_and_atomic_result_publication():
    trainer, _ = make_trainer()
    trainer.persistent_native_init()
    trainer._run_native_helper_ops.reset_mock()
    trainer._run_native_helper_ops.return_value = (module.NativeHelperOpResult(140, 0x200000),)
    result = trainer._discover_native_handlers_near_table(Mock(), ['SetHeroStr'])
    assert result['SetHeroStr'].handler_address == 0x200000
    trainer._run_native_helper_ops.assert_called_once_with(0, ((140, NATIVE_INDEX['SetHeroStr'], 0, PROFILE_ID, 0),))
    trainer._run_native_helper_ops.return_value = (module.NativeHelperOpResult(140, 0),)
    with pytest.raises(RuntimeError): trainer._discover_native_handlers(Mock(), ['SetHeroAgi'])
    assert 'SetHeroAgi' not in trainer._native_handlers
