import ast, ctypes, json, struct, subprocess, sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from war3_game_profile import (
    default_profile,
    load_profile,
    profile_scope,
    ProfileError,
    import_profile,
    ProfileCatalog,
)
from war3_game_session import (
    GameSession,
    SessionIdentity,
    SessionError,
    ObjectAddress,
    NativeHandle,
    FullHandle,
)
from war3_capabilities import CapabilitySet
from war3_object_registry import ObjectRegistry24268
from test_object_registry import RegistryFixture


def profile_file(tmp_path, mutate):
    data = default_profile().to_dict()
    mutate(data)
    path = tmp_path / "adapter.json"
    path.write_text(json.dumps(data), encoding="utf8")
    return path


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(schema_version=8),
        lambda d: d.update(bridge_profile_version=8),
        lambda d: d["decoder"].update(rol=64),
        lambda d: d["registry"].update(stride=3),
        lambda d: d["bridge_layout"].update(owner_data=8),
        lambda d: d["native_abi"].update(real_return="double"),
        lambda d: d["modules"]["talents"].update(implementation="evil.py"),
        lambda d: d["addresses"].update(registry_root=0xFFFFFFFFFFFFFFFF),
    ],
)
def test_pack_rejects_invalid_structure_abi_and_layout(tmp_path, change):
    with pytest.raises(ProfileError):
        load_profile(profile_file(tmp_path, change))


def test_candidate_pack_cannot_be_imported_or_selected(tmp_path):
    path = profile_file(
        tmp_path, lambda d: d.update(status="candidate", id="candidate")
    )
    with pytest.raises(ProfileError):
        import_profile(path, tmp_path / "installed")
    assert (
        ProfileCatalog(tmp_path).select(default_profile().fingerprint).id
        == default_profile().id
    )


def test_duplicate_keys_and_scripts_rejected(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"id":"a","id":"b"}')
    with pytest.raises(ProfileError):
        load_profile(path)
    with pytest.raises(ProfileError):
        load_profile(profile_file(tmp_path, lambda d: d.update(script="x.py")))


def test_import_round_trip_and_immutable(tmp_path):
    target = import_profile(Path("profiles/3.0.0.24268.json"), tmp_path / "installed")
    assert load_profile(target).digest == default_profile().digest
    with pytest.raises(TypeError):
        default_profile().section("registry")["stride"] = 99


def test_foreign_fingerprint_cannot_retarget_compiled_extensions(tmp_path):
    def change(d):
        d["fingerprint"]["timestamp"] += 1
        for module in d["modules"].values():
            module["fingerprint"][1] += 1

    p = load_profile(profile_file(tmp_path, change))
    assert not CapabilitySet(p).check("extension").available
    assert CapabilitySet(p).check("world").available


def test_native_signature_failure_is_per_capability():
    caps = CapabilitySet(default_profile(), {"Good": SimpleNamespace(signature="()V")})
    assert not caps.check("ability", [("Missing", "()I")]).available
    assert caps.check("world", [("Good", "()V")]).available
    assert (
        not CapabilitySet(default_profile(), common=("TLS invalid",))
        .check("world")
        .available
    )


def test_profile_layout_and_rva_change_without_code_change(tmp_path):
    def change(d):
        d["addresses"]["registry_root"] += 0x1000
        r = d["registry"]
        r.update(
            primary=0x28,
            alternate=0x90,
            count=0x20,
            stride=32,
            slot_owner=16,
            owner_handle=0x38,
            owner_tag=0x30,
            owner_data=0xB0,
            object_handle=0x28,
        )
        for key in (
            "primary",
            "alternate",
            "stride",
            "slot_owner",
            "owner_handle",
            "owner_data",
            "object_handle",
        ):
            d["bridge_layout"][key] = r[key]
        d["bridge_layout"]["table_count"] = r["count"]
        d["bridge_layout"]["registry_root_rva"] = d["addresses"]["registry_root"]

    p = load_profile(profile_file(tmp_path, change))
    m = RegistryFixture(0x140000000)
    r = p.section("registry")
    base = m.base
    owner = 0x700000
    unit = 0x600000
    handle = (99 << 32) | 3
    m.put(base + p.section("addresses")["registry_root"], struct.pack("<Q", m.root))
    table = bytearray(r["count"] + 4)
    struct.pack_into("<Q", table, 0, m.table)
    struct.pack_into("<I", table, r["count"], 4)
    m.put(m.root + r["primary"], table)
    slot = bytearray(r["stride"])
    struct.pack_into("<I", slot, 0, 0xFFFFFFFE)
    struct.pack_into("<Q", slot, r["slot_owner"], owner)
    m.put(m.table + 3 * r["stride"], slot)
    for address, value in (
        (owner + r["owner_handle"], handle),
        (owner + r["owner_tag"], r["unit_tag"]),
        (owner + r["owner_data"], unit),
        (unit + r["object_handle"], handle),
    ):
        m.put(address, struct.pack("<Q", value))
    with profile_scope(p):
        assert ObjectRegistry24268(m, base).resolve_unit(m, unit) == (handle, owner)
    assert default_profile().section("registry")["stride"] == 16


@pytest.fixture
def bound():
    m = RegistryFixture()
    h, o, u = m.unit(3)
    m.put(u + 0x70, struct.pack("<I", 0x4865726F))
    s = GameSession(1, 2, profile=default_profile(), creation_reader=lambda m: 10)
    identity = SessionIdentity(
        1, 10, m.base, default_profile().fingerprint, default_profile().digest
    )
    s.observe(identity, (2, 3, 4))
    r = ObjectRegistry24268(m, m.base)
    return s, m, r, s.bind_unit(m, r, ObjectAddress(u))


@pytest.mark.parametrize(
    "event", ["pid_reuse", "base", "fingerprint", "thread", "map", "reload", "close"]
)
def test_old_references_and_caches_never_survive_lifecycle(bound, event):
    s, m, r, ref = bound
    s.cache["old"] = "value"
    i = s.identity
    key = s.context_key
    if event == "pid_reuse":
        i = replace(i, created=11)
    if event == "base":
        i = replace(i, module_base=i.module_base + 4096)
    if event == "fingerprint":
        i = replace(i, fingerprint=(1, 2, 3))
    if event == "thread":
        key = (2, 99, 4)
    if event == "map":
        key = (2, 3, 99)
    if event == "reload":
        s.invalidate("reload notification")
    elif event == "close":
        s.close()
    else:
        s.observe(i, key)
    assert "old" not in s.cache
    with pytest.raises(SessionError):
        s.resolve(m, r, ref)


def test_destroy_recreate_same_address_rejects_generation(bound):
    s, m, r, ref = bound
    m.unit(3, generation=11)
    with pytest.raises((SessionError, RuntimeError)):
        s.resolve(m, r, ref)


def test_handles_are_not_interchangeable(bound):
    s, m, r, ref = bound
    with pytest.raises(TypeError):
        s.bind_unit(m, r, NativeHandle(ref.address.value))
    with pytest.raises(TypeError):
        s.resolve(m, r, replace(ref, handle=NativeHandle(ref.handle.value)))


@pytest.mark.parametrize(
    "dispatch",
    [
        {
            "callback_verified": True,
            "query_completed": False,
            "work_freed": True,
            "block_freed": True,
            "image_unmap_status": "0x0",
        },
        {
            "callback_verified": True,
            "query_completed": True,
            "allocations_retained": True,
        },
        {
            "callback_verified": True,
            "query_completed": True,
            "work_freed": True,
            "block_freed": False,
            "image_unmap_status": "0x0",
        },
    ],
)
def test_uncertain_execution_or_cleanup_blocks_replay(bound, dispatch):
    s, *_ = bound
    e = s.finish(dispatch)
    assert e.uncertain and not e.effect_verified
    with pytest.raises(SessionError):
        s.require_write()


def test_delivery_readback_and_gameplay_are_distinct(bound):
    s, *_ = bound
    d = dict(
        callback_verified=True,
        query_completed=True,
        work_freed=True,
        block_freed=True,
        image_unmap_status="0x0",
    )
    e = s.finish(d)
    assert e.delivered and not e.readback_verified and not e.effect_verified
    e = s.finish(d, True)
    assert e.readback_verified and not e.effect_verified
    s.require_write()


def test_domain_extraction_preserves_unmodified_baseline_method_bodies():
    baseline = subprocess.check_output(
        ["git", "show", "70446ba:war3_engine_24268.py"], text=True, encoding="utf8"
    )
    cls = next(
        n
        for n in ast.parse(baseline).body
        if isinstance(n, ast.ClassDef) and n.name == "Engine24268"
    )
    original = {
        n.name: ast.dump(n, include_attributes=False)
        for n in cls.body
        if isinstance(n, ast.FunctionDef)
    }
    count = 0
    # New services have their own protocol tests. The intentional fullscreen
    # change is covered by effect/lifecycle tests rather than byte-for-byte AST equality.
    added = {'direct_cast', 'game_speed'}
    changed = {'effect_batch'}
    seen_added, seen_changed = set(), set()
    for path in (
        Path("war3_services") / (name + ".py")
        for name in ("units", "abilities", "items", "extensions", "world")
    ):
        for c in ast.parse(path.read_text(encoding="utf8")).body:
            if isinstance(c, ast.ClassDef):
                for method in c.body:
                    if isinstance(method, ast.FunctionDef):
                        if method.name in added:
                            assert method.name not in original
                            seen_added.add(method.name)
                            continue
                        if method.name in changed:
                            assert method.name in original
                            seen_changed.add(method.name)
                            continue
                        assert (
                            ast.dump(method, include_attributes=False)
                            == original[method.name]
                        )
                        count += 1
    assert count == 27
    assert seen_added == added and seen_changed == changed


def test_c_defaults_match_python_single_source():
    dll = ctypes.WinDLL(
        str(Path("build/architecture-fixture/engine-hero-fixture.dll").resolve())
    )
    expected = default_profile().bridge_bytes()
    actual = (ctypes.c_ubyte * len(expected)).in_dll(dll, "bridge_profile")
    assert bytes(actual) == expected
    marker = (ctypes.c_uint32 * 2).in_dll(dll, "bridge_profile_abi")
    assert struct.pack("<2I", *marker) == expected[:8]


def test_native_c_resolver_uses_runtime_layout_not_fixed_root():
    dll = ctypes.WinDLL(
        str(Path("build/architecture-fixture/engine-hero-fixture.dll").resolve())
    )
    expected = default_profile().bridge_bytes()
    config = (ctypes.c_uint32 * (len(expected) // 4)).in_dll(dll, "bridge_profile")
    fields = list(default_profile().section("bridge_layout"))
    module = ctypes.create_string_buffer(0x1000)
    root = ctypes.create_string_buffer(0x200)
    table = ctypes.create_string_buffer(0x200)
    owner = ctypes.create_string_buffer(0x200)
    base, root_addr, table_addr, owner_addr = map(
        ctypes.addressof, (module, root, table, owner)
    )
    values = dict(default_profile().section("bridge_layout"))
    values.update(
        registry_root_rva=0x100,
        primary=0x28,
        alternate=0x90,
        table_count=0x20,
        stride=32,
        slot_owner=16,
        owner_handle=0x38,
    )
    handle = (99 << 32) | 3
    struct.pack_into("<Q", module, 0x100, root_addr)
    struct.pack_into("<Q", root, 0x28, table_addr)
    struct.pack_into("<I", root, 0x48, 4)
    struct.pack_into("<I", table, 3 * 32, 0xFFFFFFFE)
    struct.pack_into("<Q", table, 3 * 32 + 16, owner_addr)
    struct.pack_into("<Q", owner, 0x38, handle)
    fn = dll.BridgeTestResolveProfileOwner
    fn.argtypes = (ctypes.c_uint64, ctypes.c_uint64)
    fn.restype = ctypes.c_uint64
    try:
        for i, k in enumerate(fields, 2):
            config[i] = values[k]
        assert fn(base, handle) == owner_addr
        assert fn(base, handle + (1 << 32)) == 0
    finally:
        ctypes.memmove(ctypes.addressof(config), expected, len(expected))


def test_shared_engine_close_does_not_close_ui_session(tmp_path):
    from war3_engine_24268 import Engine24268

    s = GameSession(1, 2)
    engine = Engine24268(1, 2, Mock(), tmp_path / "bridge.dll", session=s)
    engine.close()
    assert not s.closed


def test_window_change_never_discards_unknown_write_state():
    from war3_trainer_session import session_entry

    s = GameSession(1, 2)
    s.uncertain = True
    s.prepare = Mock(side_effect=SessionError("frame unavailable"))
    t = SimpleNamespace(pid=1, hwnd=3, _game_session=s, _session_memory_factory=Mock())
    t._session_memory_factory.return_value.__enter__ = Mock(return_value=Mock())
    t._session_memory_factory.return_value.__exit__ = Mock(return_value=False)
    with pytest.raises(SessionError):
        session_entry(lambda self: None)(t)
    assert t._game_session is s and s.uncertain


def test_cleanup_failure_stays_owned_by_closed_session():
    s = GameSession(1, 2)
    resource = Mock()
    resource.close.side_effect = RuntimeError("still referenced")
    s.resources["icons"] = resource
    result = s.close()
    assert result["retained"] and s.retained["icons"]["resource"] is resource


def test_source_release_manifest_includes_adapter_and_services():
    from tools.build_release_207 import source_paths, ROOT

    paths = {p.relative_to(ROOT).as_posix() for p in source_paths()}
    assert "profiles/3.0.0.24268.json" in paths
    assert "war3_services/units.py" in paths
    assert "tools/generate_bridge_profile.py" in paths


def test_every_product_operation_has_a_protocol_and_rejects_truncated_work():
    from war3_operations import OPERATIONS, prepare_operation

    for kind, spec in OPERATIONS.items():
        if spec.diagnostic:
            continue
        assert spec.protocol, kind
        with pytest.raises((ValueError, struct.error)):
            prepare_operation(kind, b"")


def test_native_cache_rejects_in_place_handler_change():
    from test_native_table_live import fixture
    from war3_native_table import NativeTable24268, validate_cached_entries

    m, c = fixture()
    entries = NativeTable24268(m, c).require("Fn0")
    validate_cached_entries(m, entries)
    m.put(entries["Fn0"].node + 0x30, struct.pack("<Q", 0x800000))
    with pytest.raises(RuntimeError, match="Cached native"):
        validate_cached_entries(m, entries)


def test_prepare_tracks_real_snapshot_and_native_head(monkeypatch):
    import war3_object_registry as objects
    import war3_thread_context as threads

    m = RegistryFixture()
    m.player_array(1)
    tls = 0xA00000
    context5 = 0xB00000
    m.put(tls + 0x38, struct.pack("<Q", context5))
    m.put(context5 + 0x40, struct.pack("<Q", 0xC00000))
    mode = SimpleNamespace(
        thread_id=77, tls=tls, context=0xD00000, mode_object=0xE00000
    )
    context = SimpleNamespace(read_mode=lambda memory: mode)
    monkeypatch.setattr(
        objects, "_enumerate_process_modules", lambda memory: [(m.base, "game.exe", "")]
    )
    monkeypatch.setattr(threads, "GameThreadContext24268", lambda *args: context)
    s = GameSession(123, 456, creation_reader=lambda memory: 99)
    s.prepare(m)
    epoch = s.epoch
    s.cache["old"] = "native mapping"
    s.prepare(m)
    assert s.epoch == epoch and s.cache["old"] == "native mapping"
    m.put(context5 + 0x40, struct.pack("<Q", 0xC00200))
    s.prepare(m)
    assert s.epoch == epoch + 1 and "old" not in s.cache


def test_unknown_fingerprint_never_reaches_context_or_write(monkeypatch):
    import war3_object_registry as objects
    import war3_thread_context as threads

    m = RegistryFixture()
    m.put(m.base + 0x88, struct.pack("<I", 999))
    monkeypatch.setattr(
        objects, "_enumerate_process_modules", lambda memory: [(m.base, "game.exe", "")]
    )
    probe = Mock(side_effect=AssertionError("context entered"))
    monkeypatch.setattr(threads, "GameThreadContext24268", probe)
    with pytest.raises(SessionError, match="Unknown") as caught:
        GameSession(123, 456, creation_reader=lambda memory: 99).prepare(m)
    assert caught.value.session_report["build_diagnostics"][0]["fingerprint"][1] == 999
    probe.assert_not_called()


def vital_fixture():
    m = RegistryFixture()
    handle, owner, unit = m.unit(3)
    m.put(unit + 0x70, struct.pack("<I", 0x4865726F))
    array = 0x1100000
    prop = 0x1200000
    m.put(owner + 0xA0, struct.pack("<QQQQIII4x", array, 8, array, 8, 8, 1, 1))
    m.put(array, struct.pack("<Q", prop))
    from war3_basic_fields import REAL_TAG

    for offset, value in ((0x18, REAL_TAG), (0x20, 123), (0x50, owner)):
        m.put(prop + offset, struct.pack("<Q", value))
    m.put(prop + 0x7C, struct.pack("<I", 1))
    m.put(prop + 0xD0, struct.pack("<ff", 100, 1))
    m.put(prop + 0xE0, struct.pack("<f", 200))
    for name, fmt in (("read_u64", "<Q"), ("read_u32", "<I"), ("read_f32", "<f")):
        setattr(
            m,
            name,
            lambda address, fmt=fmt: struct.unpack(
                fmt, m.read(address, struct.calcsize(fmt))
            )[0],
        )
    m.write_f32 = lambda address, value: m.put(address, struct.pack("<f", value))
    candidate = SimpleNamespace(
        unit_address=unit,
        owner_address=owner,
        handle=handle,
        hp_current_address=prop + 0xD0,
        hp_max_address=prop + 0xE0,
        hp_regen_address=prop + 0xD4,
    )
    s = GameSession(1, 2, profile=default_profile())
    s.observe(
        SessionIdentity(
            1, 10, m.base, default_profile().fingerprint, default_profile().digest
        ),
        (1, 2, 3),
    )
    return s, m, ObjectRegistry24268(m, m.base), candidate


def test_health_write_vertical_slice_changes_state_and_matches_baseline():
    from war3_external_backend import ExternalMemoryBackend
    from war3_basic_fields import write_basic_fields

    s, m, r, c = vital_fixture()
    s2, m2, r2, c2 = vital_fixture()
    expected = write_basic_fields(m2, r2, c2, {"hp_current": 350})
    result = ExternalMemoryBackend(s).write_basic_fields(m, r, c, {"hp_current": 350})
    assert result == expected == {"hp_max": 350.0, "hp_current": 350.0}
    assert m.data == m2.data
    assert s.last_evidence.readback_verified and not s.last_evidence.effect_verified


def test_partial_health_write_is_not_repeated():
    from war3_external_backend import ExternalMemoryBackend

    s, m, r, c = vital_fixture()
    write = m.write_f32
    calls = []

    def change_after_first(address, value):
        calls.append(address)
        write(address, value)
        m.unit(3, generation=11)

    m.write_f32 = change_after_first
    backend = ExternalMemoryBackend(s)
    with pytest.raises(RuntimeError):
        backend.write_basic_fields(m, r, c, {"hp_current": 350})
    assert len(calls) == 1 and s.uncertain
    with pytest.raises(SessionError):
        backend.write_basic_fields(m, r, c, {"hp_current": 350})
    assert len(calls) == 1


def test_talent_adapter_failure_does_not_disable_bag_actions(tmp_path):
    p = load_profile(
        profile_file(tmp_path, lambda d: d["modules"]["talents"].update(enabled=False))
    )
    caps = CapabilitySet(p)
    assert caps.check("extension", request={"action": 1}).available
    assert caps.check("extension", request={"action": 4}).available
    assert not caps.check("extension", request={"action": 7}).available


def test_offline_cli_does_not_connect_to_a_game(monkeypatch, capsys):
    import war3_reforged_trainer as m

    connect = Mock(side_effect=AssertionError("game accessed"))
    monkeypatch.setattr(m, "find_war3", connect)
    assert m.main(["--inspect-game-profile", "profiles/3.0.0.24268.json"]) == 0
    assert default_profile().id in capsys.readouterr().out
    connect.assert_not_called()


def test_pid_reuse_releases_old_execution_block_but_map_change_does_not(bound):
    s, *_ = bound
    s.uncertain = True
    s.retained["old"] = "remote allocation"
    s.observe(s.identity, (1, 9, 3))
    assert s.uncertain and s.retained
    s.observe(replace(s.identity, created=s.identity.created + 1), (1, 9, 3))
    assert not s.uncertain and not s.retained
    assert s.previous_process_evidence["uncertain"]


def test_new_memory_handle_cannot_target_reused_pid(bound):
    from war3_game_session import session_scope, verify_opened_process

    s, m, r, ref = bound
    s.creation_reader = lambda memory: 10
    with session_scope(s):
        verify_opened_process(SimpleNamespace(pid=1))
    s.creation_reader = lambda memory: 11
    with (
        session_scope(s),
        pytest.raises(SessionError, match="Process identity changed"),
    ):
        verify_opened_process(SimpleNamespace(pid=1))


def test_typed_item_rejects_native_handle_and_replaced_object(bound):
    s, m, r, unit = bound
    h, o, u = m.unit(4, owner=0x710000, unit=0x610000)
    m.put(o + r.layout["owner_tag"], struct.pack("<Q", r.layout["item_tag"]))
    for offset in (r.layout["object_rawcode"], r.layout["item_rawcode_mirror"]):
        m.put(u + offset, struct.pack("<I", 0x65656833))
    item = s.bind_item(m, r, FullHandle(h))
    assert s.resolve(m, r, item) == u
    with pytest.raises(TypeError):
        s.bind_item(m, r, NativeHandle(h))
    m.put(o + r.layout["owner_tag"], struct.pack("<Q", r.layout["unit_tag"]))
    with pytest.raises(SessionError):
        s.resolve(m, r, item)


@pytest.mark.parametrize("scenario", [0, 1])
def test_engine_to_real_c_fixture_and_readback_lifecycle(
    monkeypatch, tmp_path, scenario
):
    import war3_engine_24268 as module
    import war3_integrity
    from test_24268_product_hero import entries
    from contextlib import nullcontext

    game = SimpleNamespace(
        base=0x140000000, local_player_for_mode=lambda memory, mode: 0x100000
    )
    mode = SimpleNamespace(value=0, tls=0x10000000, thread_id=7, tls_index=8)
    context = SimpleNamespace(read_mode=lambda memory: mode)
    memory = SimpleNamespace(read_u64=lambda address: 0x200000)
    s = GameSession(123, 456, profile=default_profile())
    s.observe(
        SessionIdentity(
            123, 10, game.base, default_profile().fingerprint, default_profile().digest
        ),
        (1, 2, 3),
    )
    s.prepare = lambda memory: (game, context, mode)
    table = SimpleNamespace(
        entries=entries(),
        require=lambda *names: {name: entries()[name] for name in names},
    )
    monkeypatch.setattr(module, "NativeTable24268", lambda *args: table)
    monkeypatch.setattr(module, "inspect_entries", lambda *args: {})
    monkeypatch.setattr(
        war3_integrity, "require_matching_integrity", lambda pid: {"match": True}
    )
    dll = ctypes.WinDLL(
        str(Path("build/architecture-fixture/engine-hero-fixture.dll").resolve())
    )
    dll.BridgeTestRun.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_int)
    dll.BridgeTestRun.restype = ctypes.c_uint64
    calls = []

    def dispatch(pid, hwnd, tid, image, tls_index, payload, kind):
        calls.append(kind)
        buffer = ctypes.create_string_buffer(payload)
        count = dll.BridgeTestRun(buffer, 4, scenario)
        return dict(
            callback_verified=True,
            query_completed=True,
            work_freed=True,
            block_freed=True,
            image_unmap_status="0x0",
            after_send={"tls_value": hex(mode.tls), "query_result": hex(count)},
            work_result_hex=buffer.raw[: len(payload)].hex(),
        )

    monkeypatch.setattr(module, "dispatch", dispatch)
    bridge = tmp_path / "bridge.dll"
    bridge.write_bytes(b"fixture path")
    engine = module.Engine24268(
        123, 456, lambda pid: nullcontext(memory), bridge, session=s
    )
    if scenario == 0:
        result = engine.hero_progress(7)
        assert result["changed"] == 2 and all(
            row["after"] == 7 for row in result["rows"]
        )
        assert engine.last_report["verification"]["readback_verified"]
        assert not engine.last_report["verification"]["effect_verified"]
    else:
        with pytest.raises(module.EngineExecutionError):
            engine.hero_progress(7)
        assert s.uncertain
        with pytest.raises(module.EngineExecutionError):
            engine.hero_progress(7)
        assert calls == ["hero"]


def test_native_table_layout_and_rva_pack_change(tmp_path):
    from test_classic_player_selection import Memory
    from war3_native_table import NativeTable24268

    def change(d):
        d["native_table"].update(
            table=0x88,
            head=0x28,
            terminal=0x10,
            next=0x40,
            name=0x60,
            handler=0x80,
            signature=0xA0,
        )

    profile = load_profile(profile_file(tmp_path, change))
    m = Memory()
    context = 0x300000
    node = 0x400000
    layout = profile.section("native_table")
    m.put(context + layout["table"] + layout["head"], struct.pack("<Q", node))
    for key, value in [
        ("next", (context + layout["table"] + layout["terminal"]) | 1),
        ("name", 0x500000),
        ("handler", 0x700000),
        ("signature", 0x600000),
    ]:
        m.put(node + layout[key], struct.pack("<Q", value))
    m.put(0x500000, b"Name\0")
    m.put(0x600000, b"(I)V\0")
    with profile_scope(profile):
        row = NativeTable24268(m, context).require("Name")["Name"]
        assert row.handler == 0x700000 and row.signature == "(I)V"


def test_current_service_and_startup_have_no_historical_transport_dependency():
    script = "import sys,war3_reforged_trainer; assert 'diagnostics.war3_native_profile' not in sys.modules; assert 'diagnostics.war3_engine_persistent_transport' not in sys.modules"
    subprocess.run([sys.executable, "-c", script], check=True)
    for path in (
        Path("war3_services") / (name + ".py")
        for name in ("units", "abilities", "items", "extensions", "world")
    ):
        assert "_native_selection_unavailable" not in path.read_text(encoding="utf8")


def test_managed_session_cannot_enter_legacy_helper_even_if_old_flag_changes():
    from war3_reforged_trainer import War3Trainer

    t = object.__new__(War3Trainer)
    t._game_session = GameSession(1, 2)
    t._native_selection_unavailable = False
    t._ensure_native_helper_persistent_hook = Mock(
        side_effect=AssertionError("legacy installed")
    )
    with pytest.raises(RuntimeError, match="未启用旧版"):
        t._run_native_helper_ops(
            0, [(t.NATIVE_HELPER_OP_UNLOCK_TALENT_TIER, 1, 1, 0, 0)]
        )
    t._ensure_native_helper_persistent_hook.assert_not_called()


def test_icon_snapshot_rejects_retired_context_before_remote_read():
    from war3_talent_icon_display import TalentIconDisplay

    s = GameSession(1, 2)
    s.epoch = 2
    display = TalentIconDisplay(SimpleNamespace(session=s), "unused.dll")
    display.session_epoch = 1
    display._alive = Mock(side_effect=AssertionError("remote read"))
    with pytest.raises(RuntimeError, match="context changed"):
        display.snapshot()


def test_missing_native_registry_does_not_break_external_session(monkeypatch):
    import war3_object_registry as objects
    import war3_thread_context as threads

    m = RegistryFixture()
    m.player_array(1)
    tls = 0xA00000
    m.put(tls + 0x38, struct.pack("<Q", 0))
    mode = SimpleNamespace(
        thread_id=77, tls=tls, context=0xD00000, mode_object=0xE00000
    )
    monkeypatch.setattr(
        objects, "_enumerate_process_modules", lambda memory: [(m.base, "game.exe", "")]
    )
    monkeypatch.setattr(
        threads,
        "GameThreadContext24268",
        lambda *args: SimpleNamespace(read_mode=lambda memory: mode),
    )
    s = GameSession(123, 456, creation_reader=lambda memory: 99)
    registry, context, actual = s.prepare(m)
    assert actual is mode and registry.base == m.base
    assert s.native_registry_error == "Native registry is not initialized"


def test_legacy_flag_cannot_change_managed_session_backend():
    from war3_reforged_trainer import War3Trainer

    t = object.__new__(War3Trainer)
    t._native_selection_unavailable = False
    assert not t._native_selection_unavailable
    t._game_session = GameSession(1, 2)
    assert t._native_selection_unavailable
    t._native_selection_unavailable = False
    assert t._native_selection_unavailable


def test_all_inherited_public_services_have_session_guard():
    import inspect
    from war3_reforged_trainer import War3Trainer
    from war3_trainer_session import WINDOW_ONLY

    for cls in War3Trainer.__mro__[1:-1]:
        for name, value in vars(cls).items():
            if (
                name.startswith("_")
                or name in WINDOW_ONLY
                or isinstance(value, (classmethod, staticmethod))
            ):
                continue
            if inspect.isfunction(value):
                actual = vars(War3Trainer)[name]
                assert hasattr(actual, "__wrapped__"), name


def test_inventory_identity_timeout_never_replays_as_basic_field_write():
    from war3_reforged_trainer import War3Trainer

    t = object.__new__(War3Trainer)
    t._native_selection_unavailable = False
    t._inventory_slot_index_from_field_key = Mock(return_value=1)
    t._coerce_memory_value = Mock(return_value=0x65656833)
    t._looks_like_item_rawcode = Mock(return_value=True)
    t._native_snapshot_for_candidate = Mock(return_value=None)
    failure = TimeoutError("identity pending")
    t._refresh_native_candidate = Mock(side_effect=failure)
    t._write_basic_unit_values_to_candidate = Mock(
        side_effect=AssertionError("wrong write")
    )
    t._set_inventory_slot_item_via_native_handler = Mock(
        side_effect=AssertionError("replayed")
    )
    with pytest.raises(TimeoutError) as caught:
        t._write_inventory_slot_field(
            Mock(), Mock(), SimpleNamespace(key="inventory_2"), "eeh3"
        )
    assert caught.value is failure
    t._write_basic_unit_values_to_candidate.assert_not_called()
    t._set_inventory_slot_item_via_native_handler.assert_not_called()


def test_parent_operation_cannot_continue_writing_after_nested_map_change(bound):
    from war3_game_session import session_scope

    s, *_ = bound
    with session_scope(s):
        s.observe(s.identity, (2, 3, 99))
        with pytest.raises(SessionError, match="Map context changed"):
            s.require_write()
    with session_scope(s):
        s.require_write()
