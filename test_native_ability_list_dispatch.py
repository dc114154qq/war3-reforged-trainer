"""Round-trip real C ability enumeration through the Python IPC decoder."""
import ctypes
import os
from pathlib import Path
import shutil
import subprocess
from unittest.mock import Mock

import pytest
import war3_reforged_trainer as module
from test_native_identity_guard import HARNESS
from test_native_snapshot_binding import make_candidate, make_snapshot


LIST_HARNESS = r'''
static uint8_t list_data[4097][0xa8], list_wrappers[4097][0x98];
static unsigned list_count, list_fault, index_calls;
static uint64_t list_full(unsigned i) { return 0x987600005432ULL + i; }
static uint64_t list_lookup(uint64_t unit, int32_t index) {
    ++index_calls;
    if (unit != 7 || index < 0 || index > 4096) ++bad_arguments;
    if (index < 0 || (unsigned)index >= list_count) return 0;
    return 200 + index;
}
static uint64_t list_resolve(uint64_t handle) {
    return handle >= 200 && handle < 200 + list_count ?
        (uint64_t)(uintptr_t)list_data[handle - 200] : 0;
}
static uint64_t list_agent(uint32_t slot, uint32_t serial) {
    uint64_t id = ((uint64_t)serial << 32) | slot;
    if (id == full) return (uint64_t)(uintptr_t)owner;
    if (id >= list_full(0) && id < list_full(list_count))
        return (uint64_t)(uintptr_t)list_wrappers[id - list_full(0)];
    return 0;
}
static uint32_t list_id(uint64_t handle) {
    if (!list_resolve(handle)) ++bad_arguments;
    /* Two separate instances may have the same rawcode. */
    return list_fault == 4 && handle == 200 ? 0x41496e76u : 0x41303031u;
}
static int32_t list_level(uint64_t unit, uint32_t id) {
    if (unit != 7 || (id != 0x41303031u && id != 0x41496e76u)) ++bad_arguments;
    if (list_fault == 1) *(uint64_t *)(object + 0x18) += 1;
    if (list_fault == 2) *(uint64_t *)(list_data[0] + 0x18) += 1;
    return 4;
}
__declspec(dllexport) DWORD enumerate_list(const wchar_t *directory, unsigned count, unsigned failure,
                                          unsigned *out) {
    NativeCommand cmd = {0}; DWORD bytes; HANDLE file; wchar_t path[MAX_PATH];
    if (count > 4097 || wcslen(directory) >= MAX_PATH - 1) return ERROR_INVALID_PARAMETER;
    fault = writes = bad_arguments = index_calls = 0;
    list_count = count; list_fault = failure;
    wcscpy(test_directory, directory);
    ZeroMemory(object, sizeof(object)); ZeroMemory(owner, sizeof(owner));
    *(uint64_t *)(object+0x18) = full;
    *(uint64_t *)(owner+0x18) = 0x2b7733752b61676cULL;
    *(uint64_t *)(owner+0x20) = full;
    *(uint64_t *)(owner+0x90) = (uint64_t)(uintptr_t)object;
    g_persistent_unit_resolver = (uint64_t)(uintptr_t)fake_unit;
    g_persistent_agent_resolver = (uint64_t)(uintptr_t)list_agent;
    g_persistent_ability_resolver = (uint64_t)(uintptr_t)list_resolve;
    for (unsigned i=0; i<count; ++i) {
        uint8_t *data=list_data[i], *wrapper=list_wrappers[i];
        ZeroMemory(data, 0xa8); ZeroMemory(wrapper, 0x98);
        *(uint64_t *)data = *(uint64_t *)wrapper = (uint64_t)(uintptr_t)list_id;
        *(uint64_t *)(data+0x18) = *(uint64_t *)(wrapper+0x20) = list_full(i);
        *(uint64_t *)(data+0x68) = (uint64_t)(uintptr_t)object;
        *(uint32_t *)(data+0x70) = *(uint32_t *)(data+0x78) = list_id(200+i);
        *(uint64_t *)(wrapper+0x18) = failure == 4 && i == 0 ? 0x41496e7630303030ULL : 0x4148737430303030ULL;
        *(uint64_t *)(wrapper+0x50) = (uint64_t)(uintptr_t)owner;
        *(uint64_t *)(wrapper+0x90) = (uint64_t)(uintptr_t)data;
    }
    for (unsigned i=0; i<sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]); ++i) {
        const char *name=g_persistent_native_names[i];
        g_persistent_natives[i].name=name; g_persistent_natives[i].handler=0;
        if (!strcmp(name,"BlzGetUnitAbilityByIndex") && failure != 3)
            g_persistent_natives[i].handler=(uint64_t)(uintptr_t)list_lookup;
        if (!strcmp(name,"BlzGetAbilityId")) g_persistent_natives[i].handler=(uint64_t)(uintptr_t)list_id;
        if (!strcmp(name,"GetUnitAbilityLevel")) g_persistent_natives[i].handler=(uint64_t)(uintptr_t)list_level;
    }
    cmd.magic=WAR3_NATIVE_MAGIC; cmd.version=WAR3_NATIVE_VERSION;
    cmd.status=WAR3_NATIVE_STATUS_PENDING; cmd.unit_handle=7; cmd.op_count=2;
    cmd.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;
    cmd.ops[0].handler=(uint64_t)(uintptr_t)object; cmd.ops[0].arg0=full;
    cmd.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    cmd.ops[1].kind=WAR3_NATIVE_OP_BOUND_ABILITY_LIST;
    command_path(path,MAX_PATH);
    file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();
    BOOL ok=WriteFile(file,&cmd,sizeof(cmd),&bytes,NULL); CloseHandle(file);
    if(!ok || bytes!=sizeof(cmd)) return ERROR_WRITE_FAULT;
    run_command();
    out[0]=bad_arguments; out[1]=index_calls;
    return 0;
}
'''


@pytest.fixture(scope='module')
def dispatcher(tmp_path_factory):
    compiler = shutil.which('clang')
    if not compiler:
        pytest.skip('clang required')
    root = tmp_path_factory.mktemp('ability-list-c')
    source, library = root/'list.c', root/'list.dll'
    source.write_text(HARNESS.replace('HELPER_SOURCE', (Path(__file__).parent/'tools/war3_native_helper.c').as_posix())
                      + LIST_HARNESS, encoding='utf8')
    subprocess.run([compiler, '-shared', '-O2', '-Wno-microsoft-goto', str(source), '-o', str(library),
                    '-luser32', '-lkernel32'], check=True, capture_output=True, timeout=60)
    native = ctypes.CDLL(str(library))
    native.enumerate_list.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_uint,
                                     ctypes.POINTER(ctypes.c_uint)]
    native.enumerate_list.restype = ctypes.c_uint
    yield native
    import _ctypes
    _ctypes.FreeLibrary(native._handle)


@pytest.mark.parametrize('count,failure', [(0,0),(1,0),(2,0),(49,0),(4096,0),(4097,0),
                                          (2,1),(2,2),(2,3),(2,4)])
@pytest.mark.parametrize('initialized', [False, True])
def test_real_dispatch_payload_and_boundaries(dispatcher, tmp_path, count, failure, initialized):
    out = (ctypes.c_uint*2)()
    assert dispatcher.enumerate_list(str(tmp_path)+'\\', count, failure, out) == 0
    assert out[0] == 0
    assert out[1] <= 4096*3+1  # bounded lookups even at capacity
    payload = (tmp_path/f'war3_reforged_native_{os.getpid()}.bin').read_bytes()
    trainer = module.War3Trainer.__new__(module.War3Trainer)
    if failure in (1,2,3) or count > 4096:
        with pytest.raises(RuntimeError):
            trainer._parse_native_helper_results(payload, 2)
        assert len(payload) == trainer._native_helper_command_size()  # no partial list published
        return
    results = trainer._parse_native_helper_results(payload, 2)
    assert results[1].result == count
    assert len(results[0].extra_results) == count*10
    assert results[1].extra_results == ()
    trainer._persistent_native_initialized = initialized
    trainer._near_ability_instances_from_candidate = Mock(side_effect=AssertionError('Unexpected wrapper search'))
    trainer._global_ability_instances_from_candidate = Mock(side_effect=AssertionError('Unexpected heap search'))
    trainer._validated_cached_ability_instances = Mock(side_effect=AssertionError('Unexpected stale cache lookup'))
    candidate = make_candidate(make_snapshot())
    trainer._query_native_table_handlers = Mock(return_value={
        name: module.NativeHandler(name,0,0x100000) for name in
        ('BlzGetUnitAbilityByIndex','BlzGetAbilityId','GetUnitAbilityLevel')})
    trainer._run_native_helper_ops = Mock(return_value=results)
    memory = Mock()
    instances = trainer._ability_instances_from_candidate(memory, candidate)
    skill_count = count - (1 if failure == 4 else 0)
    assert len(instances) == skill_count
    assert len({item.handle for item in instances}) == skill_count
    assert [item.slot for item in instances] == list(range(1,skill_count+1))
    assert all(item.rawcode == 0x41303031 for item in instances)
    assert memory.mock_calls == []


def test_reset_registration_cannot_hide_a_missing_native_payload():
    trainer = module.War3Trainer.__new__(module.War3Trainer)
    trainer._persistent_native_initialized = False
    trainer._validated_cached_ability_instances = Mock(side_effect=AssertionError('Unexpected stale cache'))
    trainer._query_native_table_handlers = Mock()
    candidate = module.replace(make_candidate(make_snapshot()), native_snapshot=None,
                               selection_source='persistent_native')
    with pytest.raises(RuntimeError):
        trainer._ability_instances_from_candidate(Mock(), candidate)
    trainer._query_native_table_handlers.assert_not_called()
    trainer._validated_cached_ability_instances.assert_not_called()
