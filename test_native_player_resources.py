"""Production Python -> actual C dispatcher -> Python/UI, with isolated players."""
import ast
import ctypes
import faulthandler
import os
from pathlib import Path
import shutil
import subprocess
from unittest.mock import Mock

import pytest
import war3_reforged_trainer as module
from test_native_identity_guard import HARNESS

PLAYER_HARNESS = r'''
static int32_t resources[28][7];
static unsigned player_fault, player_writes;
static uint64_t resource_player(int32_t slot) {
    if(slot < 0 || slot >= 28) RaiseException(0xe0000010,0,0,NULL);
    if(player_fault == 1 && slot == 3) return 0;
    if(player_fault == 2 && slot == 3) RaiseException(0xe0000011,0,0,NULL);
    return 100 + slot;
}
static uint64_t resource_local(void) { return 107; }
static int32_t resource_id(uint64_t player) { return (int32_t)player - 100; }
static int32_t resource_get(uint64_t player, uint32_t state) {
    if(player < 100 || player >= 128 || state >= 7) RaiseException(0xe0000012,0,0,NULL);
    return resources[player-100][state];
}
static void resource_set(uint64_t player, uint32_t state, int32_t value) {
    if(player < 100 || player >= 128 || state >= 7) RaiseException(0xe0000013,0,0,NULL);
    ++player_writes;
    resources[player-100][state] = player_fault == 3 ? value - 1 : value;
}
__declspec(dllexport) uint64_t resource_function(unsigned index) {
    switch(index) {
        case 0: return (uint64_t)(uintptr_t)resource_player;
        case 1: return (uint64_t)(uintptr_t)resource_get;
        case 2: return (uint64_t)(uintptr_t)resource_set;
        case 3: return (uint64_t)(uintptr_t)resource_local;
        case 4: return (uint64_t)(uintptr_t)resource_id;
    }
    return 0;
}
__declspec(dllexport) void resource_reset(unsigned mode) {
    player_fault = mode; player_writes = 0;
    for(unsigned p=0;p<28;++p) for(unsigned s=0;s<7;++s) resources[p][s] = p*100+s;
    resources[0][1]=resources[1][1]=0; /* Zero/identical resources are still distinct players. */
}
__declspec(dllexport) unsigned resource_write_count(void) { return player_writes; }
__declspec(dllexport) void resource_dispatch(const wchar_t *directory) {
    wcscpy(test_directory,directory); run_command();
}
'''


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler = shutil.which('clang')
    assert compiler, 'Native resource tests require clang'
    root = tmp_path_factory.mktemp('player-resource-c')
    source, dll = root/'player.c', root/'player.dll'
    source.write_text(HARNESS.replace('HELPER_SOURCE', (Path(__file__).parent/'tools/war3_native_helper.c').as_posix())
                      + PLAYER_HARNESS, encoding='utf8')
    subprocess.run([compiler, '-shared', '-O2', '-Wno-microsoft-goto', str(source), '-o', str(dll),
                    '-luser32', '-lkernel32'], check=True, capture_output=True, timeout=60)
    lib = ctypes.CDLL(str(dll))
    lib.resource_function.argtypes = [ctypes.c_uint]
    lib.resource_function.restype = ctypes.c_uint64
    lib.resource_reset.argtypes = [ctypes.c_uint]
    lib.resource_dispatch.argtypes = [ctypes.c_wchar_p]
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)


@pytest.fixture
def player_trainer(native, tmp_path):
    native.resource_reset(0)
    trainer = module.War3Trainer.__new__(module.War3Trainer)
    functions = {name: module.NativeHandler(name, 0, native.resource_function(i)) for i, name in enumerate(
        ('Player', 'GetPlayerState', 'SetPlayerState', 'GetLocalPlayer', 'GetPlayerId'))}
    trainer._query_native_table_handlers = Mock(side_effect=lambda names: {name: functions[name] for name in names})
    trainer._process_memory = Mock(side_effect=AssertionError('External memory backend'))
    def dispatch(handle, ops, **kwargs):
        ops = tuple(ops)
        path = tmp_path/f'war3_reforged_native_{os.getpid()}.bin'
        path.write_bytes(trainer._pack_native_helper_command(handle, ops))
        enabled = faulthandler.is_enabled()
        faulthandler.disable()  # The deliberately raised SEH is caught by the real dispatcher.
        try:
            native.resource_dispatch(str(tmp_path) + '\\')
        finally:
            if enabled: faulthandler.enable()
        return trainer._parse_native_helper_results(path.read_bytes(), len(ops))
    trainer._run_native_helper_ops = Mock(side_effect=dispatch)
    return trainer


def test_all_players_local_shortcuts_and_readback(player_trainer):
    t = player_trainer
    caches, local = t.list_resource_caches_win10()
    assert [c.player_value for c in caches] == list(range(28))
    assert local.player_value == 7  # Not the first row.
    assert caches[0].gold == caches[1].gold == 0
    assert caches[27].food_limit == 2706
    assert t._run_native_helper_ops.call_count == 11  # 10 batches plus local query.
    other = t.read_resource_cache_addresses(caches[12])
    assert other.player_value == 12 and other.gold == 1201
    result = t.write_resource_cache(other, target_gold=444, target_lumber=555,
                                    target_food_used=0, target_food_cap=200)
    assert (result.gold, result.lumber, result.food_used, result.food_cap) == (444,555,0,200)
    assert result.player_value == 12
    t.add_gold(5)
    assert t.read_resource_cache_addresses(caches[7]).gold == 706
    assert t.read_resource_cache_addresses(caches[12]).gold == 444
    assert t.read_resource_cache_addresses(caches[0]).gold == 0
    t._process_memory.assert_not_called()


@pytest.mark.parametrize('fault', [1, 2, 3])
def test_empty_slot_fault_and_clamped_write(native, player_trainer, fault):
    native.resource_reset(fault)
    if fault == 1:
        assert [c.player_value for c in player_trainer.list_resource_caches()] == [i for i in range(28) if i != 3]
    elif fault == 2:
        with pytest.raises(RuntimeError): player_trainer.list_resource_caches()
    else:
        cache = player_trainer._native_resource_cache_for_player(12)
        with pytest.raises(RuntimeError, match='读回不一致'):
            player_trainer.write_resource_cache(cache, target_gold=444)


def test_invalid_request_cannot_partially_write(native, player_trainer):
    t = player_trainer
    cache = t._native_resource_cache_for_player(12)
    with pytest.raises(ValueError): t.write_resource_cache(cache, target_gold=400, target_food_used=1001)
    assert native.resource_write_count() == 0
    for slot, state, value in [(28,1,10), (0,3,10), (0,4,1001), (0,1,-1)]:
        handlers = t._query_native_table_handlers(('Player','SetPlayerState'))
        with pytest.raises(RuntimeError):
            t._run_native_helper_ops(0, ((55,slot,handlers['Player'].handler_address,
                handlers['SetPlayerState'].handler_address,(state<<32)|(value & 0xffffffff)),))
    assert native.resource_write_count() == 0


def callbacks(namespace, *names):
    tree = ast.parse(Path(module.__file__).read_text(encoding='utf-8-sig'))
    for name in names:
        node = next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name)
        exec(compile(ast.Module(body=[node],type_ignores=[]), module.__file__, 'exec'), namespace)


def test_gui_rows_population_selection_and_two_locks(player_trainer):
    t = player_trainer; caches=t.list_resource_caches()
    names=('gold_current','lumber_current','food_current','food_cap_current','gold_target',
           'lumber_target','food_used_target','food_cap_target')
    ns = {'ResourceCache':module.ResourceCache, 'root':Mock(), 'state':{'locks':{}},
          'trainer':lambda:t, 'parse_int':lambda value,label:int(value),
          'populate_locks':Mock(), 'populate_resource_caches':Mock(),
          'selected_resource_label':lambda c:str(c.player_value)}
    ns.update({name:Mock() for name in names})
    ns['gold_target'].get.return_value = '444'
    callbacks(ns,'resource_iid','resource_row_values','set_resource_entries','add_resource_lock','apply_locks_once','refresh_resources')
    ns['refresh_resources']()
    refresh_args = ns['root'].after.call_args.args
    assert [c.player_value for c in refresh_args[2]] == list(range(28))
    assert refresh_args[3:] == ('native-player:7', 'native-player:7')
    assert refresh_args[2][7].food_limit == 706
    assert len({ns['resource_iid'](c) for c in caches}) == 28
    assert ns['resource_row_values'](1,caches[0])[3] == '5/4'
    ns['set_resource_entries'](caches[0])
    ns['food_current'].set.assert_called_with('5')
    ns['food_cap_current'].set.assert_called_with('4')
    ns['state']['local_resource_iid'] = ns['resource_iid'](caches[7])
    for slot in (0,12):
        ns['selected_resource_cache']=lambda slot=slot:caches[slot]
        ns['add_resource_lock']('gold')
    assert len(ns['state']['locks'])==2
    ns['apply_locks_once']()
    for slot in (0,12): assert t.read_resource_cache_addresses(caches[slot]).gold==444
    assert t.read_resource_cache_addresses(caches[7]).gold==701


def test_new_opcodes_reach_production_transport(player_trainer):
    t = player_trainer
    ns = {'Iterable':module.Iterable,'NativeHelperOpResult':module.NativeHelperOpResult,
          'ProcessMemory':module.ProcessMemory}
    t._native_helper_batch_hook=1
    t._native_helper_batch_thread_id=module.threading.get_ident()
    t._wait_native_helper_result=Mock(return_value=[])
    t._write_native_helper_command=Mock()
    t._native_helper_command_path=Mock(return_value=Path('unused'))
    # The transport's real allowlist must accept new operations before dispatch.
    callbacks(ns, '_run_native_helper_ops_locked')
    ns.update(vars(module))
    ns['_run_native_helper_ops_locked'](t, 0, ((54,0,1,2,1),(55,0,1,2,1<<32)))
