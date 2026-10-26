"""Current 2.1.20 production source inventory for the desktop builder."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def source_paths() -> tuple[Path, ...]:
    # Keep this list aligned with the actual 2.1.20 build closure.  In
    # particular, the separate hotkey product and diagnostics probes must not
    # silently become part of the trainer source hash or package inputs.
    excluded_runtime = {
        "war3_code_observation.py",
        "war3_cooldown_probe_protocol.py",
        "war3_lifecycle_protocol.py",
        "war3_map_flags_protocol.py",
        "war3_native_profile.py",
    }
    files = {
        path for path in ROOT.glob("war3_*.py")
        if not path.name.startswith("war3_hotkey_") and path.name not in excluded_runtime
    }
    files.update(ROOT.glob("war3_services/*.py"))
    files.update(ROOT / name for name in (
        "diagnostics/__init__.py",
        "diagnostics/war3_native_profile.py",
    ))
    files.update(ROOT.glob("profiles/*.json"))
    files.update(ROOT.glob("profiles/discovery/*.json"))
    files.update(ROOT / name for name in (
        "third_party/minhook/LICENSE.txt",
        "third_party/minhook/include/MinHook.h",
        "third_party/minhook/src/buffer.c",
        "third_party/minhook/src/buffer.h",
        "third_party/minhook/src/hook.c",
        "third_party/minhook/src/trampoline.c",
        "third_party/minhook/src/trampoline.h",
        "third_party/minhook/src/hde/hde64.c",
        "third_party/minhook/src/hde/hde64.h",
        "third_party/minhook/src/hde/pstdint.h",
        "third_party/minhook/src/hde/table64.h",
        "tools/generate_bridge_profile.py",
        "tools/generate_discovery_references.py",
        "ADAPTER_NOTES_3.0.1.24360.md",
        "ADAPTER_NOTES_3.0.1.24365.md",
        "ADAPTER_NOTES_3.0.1.24371.md",
        "tools/war3_talent_icon_display.c",
        "tools/war3_talent_icon_predicate.h",
        "tools/war3_talent_icon_thunk.S",
    ))
    bridge_test_only = {
        "war3_bridge_cooldown_probe.h",
        "war3_bridge_talent_probe.h",
        "war3_bridge_test_fixture.h",
        "war3_bridge_equipment_effect_fixture.h",
    }
    files.update(
        path for path in ROOT.glob("tools/war3_bridge_*.h")
        if path.name not in bridge_test_only
    )
    files.update(
        ROOT / name for name in (
            "War3ReforgedTrainer-Web-2.1.20.spec",
            "tools/war3_bridge_24268.c",
            "tools/build_engine_bridge.ps1",
            "tools/build_talent_icon_display.ps1",
            "tools/war3_speed_clock.c",
            "tools/build_speed_clock.ps1",
            "tools/verify_engine_bridge.py",
            "tools/verify_talent_icon_display.py",
            "tools/verify_speed_clock.py",
            "third_party/minhook/LICENSE.txt",
            "tools/build_release_2120.py",
            "tools/war3-2.1.20-version-info.txt",
            "assets/app_icon.ico",
        "assets/extension-definitions-v1.zip",
        "third_party/stormlib/StormLib-LICENSE.txt",
        "tools/prepare_mpq_dependency.py",
        "tools/generate_extension_definitions.py",
        "docs/EXTENSION_DEFINITIONS.md",
        "docs/MPQ_MEMBER_RECOVERY.md",
        "docs/MOUSE_PROJECTION.md",
            "assets/app_icon.png",
        )
    )
    missing = sorted(str(path.relative_to(ROOT)) for path in files if not path.is_file())
    if missing:
        raise RuntimeError(f"Release inputs are missing: {missing}")
    return tuple(sorted(files, key=lambda path: str(path.relative_to(ROOT)).lower()))

