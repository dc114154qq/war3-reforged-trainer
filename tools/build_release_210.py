"""Build and verify the 2.1.05 package from this worktree only."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import pefile
from PyInstaller.archive.readers import CArchiveReader


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
ALLOWED_BRANCHES = {
    "main",
    "master",
    "codex/war3-modular-adapters-20260926",
}
VERSION = (2, 1, 5, 0)
EXE_NAME = "War3ReforgedTrainer-v2.1.05.exe"
OUTPUT = ROOT / "dist-2.1.05-verified"
PACKAGE_BINARIES = (
    "tools\\war3_bridge_24268.dll",
    "tools\\war3_talent_icon_display.dll",
    "tools\\war3_speed_clock.dll",
)


def run(*args: str, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(args, cwd=ROOT, env=env, text=True, capture_output=True)
    if completed.stdout.strip():
        print(completed.stdout.strip())
    if completed.stderr.strip():
        print(completed.stderr.strip(), file=sys.stderr)
    if completed.returncode:
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(args)}")
    return completed.stdout.strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def source_paths() -> tuple[Path, ...]:
    # Keep this list aligned with the actual 2.1.05 build closure.  In
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
            "War3ReforgedTrainer-2.1.05.spec",
            "tools/war3_bridge_24268.c",
            "tools/build_engine_bridge.ps1",
            "tools/build_talent_icon_display.ps1",
            "tools/war3_speed_clock.c",
            "tools/build_speed_clock.ps1",
            "tools/verify_engine_bridge.py",
            "tools/verify_talent_icon_display.py",
            "tools/verify_speed_clock.py",
            "third_party/minhook/LICENSE.txt",
            "tools/build_release_210.py",
            "RELEASE_NOTES_v2.1.05.md",
            "tools/war3-2.1.05-version-info.txt",
            "assets/app_icon.ico",
            "assets/app_icon.png",
        )
    )
    missing = sorted(str(path.relative_to(ROOT)) for path in files if not path.is_file())
    if missing:
        raise RuntimeError(f"Release inputs are missing: {missing}")
    return tuple(sorted(files, key=lambda path: str(path.relative_to(ROOT)).lower()))


def source_hashes() -> dict[str, str]:
    return {path.relative_to(ROOT).as_posix(): sha256(path) for path in source_paths()}


def assert_workspace() -> tuple[str, str]:
    top = Path(run("git", "rev-parse", "--show-toplevel"))
    if not top.samefile(ROOT):
        raise RuntimeError(f"Wrong worktree: {top}, expected {ROOT}")
    branch = run("git", "branch", "--show-current")
    if branch not in ALLOWED_BRANCHES:
        allowed = ", ".join(sorted(ALLOWED_BRANCHES))
        raise RuntimeError(f"Wrong branch: {branch}, expected one of: {allowed}")
    tree = ast.parse((ROOT / "war3_reforged_trainer.py").read_text(encoding="utf-8"))
    versions = [node.value.value for node in tree.body
                if isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == "APP_VERSION"
                    for target in node.targets
                ) and isinstance(node.value, ast.Constant)]
    if versions != ["2.1.05"]:
        raise RuntimeError(f"Source version mismatch: {versions}")
    channels = [node.value.value for node in tree.body
                if isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == "APP_RELEASE_CHANNEL"
                    for target in node.targets) and isinstance(node.value, ast.Constant)]
    if channels != ["stable"]:
        raise RuntimeError(f"Expected stable release channel: {channels}")
    return branch, run("git", "rev-parse", "HEAD")


def inspect_exe(exe: Path, expected: dict[str, str] | None = None) -> dict[str, str]:
    pe = pefile.PE(str(exe), fast_load=False)
    fixed = pe.VS_FIXEDFILEINFO[0]
    version = (
        fixed.FileVersionMS >> 16, fixed.FileVersionMS & 0xFFFF,
        fixed.FileVersionLS >> 16, fixed.FileVersionLS & 0xFFFF,
    )
    if version != VERSION:
        raise RuntimeError(f"EXE version differs: {version}")
    if fixed.FileFlags & 0x2:
        raise RuntimeError("EXE must not carry the prerelease flag")
    archive = CArchiveReader(str(exe))
    if "PYZ-00.pyz" not in archive.toc:
        raise RuntimeError("Packaged Python modules are missing")
    bundled = {}
    for name in PACKAGE_BINARIES:
        if name not in archive.toc:
            raise RuntimeError(f"Missing packaged binary: {name}")
        bundled[name] = hashlib.sha256(archive.extract(name)).hexdigest().upper()
        if expected is not None and bundled[name] != expected[name]:
            raise RuntimeError(f"Packaged binary differs from compiled image: {name}")
    for profile_path in (ROOT / "profiles").glob("*.json"):
        entry = "profiles\\" + profile_path.name
        if entry not in archive.toc or archive.extract(entry) != profile_path.read_bytes():
            raise RuntimeError(f"Packaged game profile missing or different: {entry}")
    from war3_operations import OPERATIONS
    pyz = archive.open_embedded_archive("PYZ-00.pyz")
    required = {spec.protocol for spec in OPERATIONS.values() if spec.protocol}
    required.update("war3_services." + path.stem for path in (ROOT / "war3_services").glob("*.py") if path.stem != "__init__")
    required.update({"war3_game_session", "war3_game_profile", "war3_capabilities", "war3_external_backend",
                     "war3_adapter_24332"})
    required.update({"war3_speed_clock_backend", "war3_loadout_restore", "war3_loadout_storage"})
    required.update({"war3_error_messages", "war3_item_safety_protocol"})
    required.update({"war3_remote_exports", "war3_engine_continuation"})
    required.update({"war3_save_codes", "war3_save_extraction_ui", "war3_services.save_extraction",
                     "war3_gamecache_fields", "war3_archive_fields_ui", "war3_services.archive_fields"})
    if required - set(pyz.toc):
        raise RuntimeError(f"Packaged architecture modules missing: {sorted(required - set(pyz.toc))}")
    bridge = pefile.PE(data=archive.extract(PACKAGE_BINARIES[0]))
    exported = {s.name: s.address for s in bridge.DIRECTORY_ENTRY_EXPORT.symbols}
    import struct
    for name, values in ((b"bridge_native_hook_abi", (0x24268049, 216, 6)),
                         (b"bridge_callback_lifecycle_abi", (0x2426804a, 216, 32))):
        if name not in exported or bridge.get_data(exported[name], 12) != struct.pack("<3I", *values):
            raise RuntimeError(f"Missing or mismatched compatibility bridge ABI: {name!r}")
    from war3_game_profile import default_profile
    profile = default_profile().bridge_bytes()
    for name, expected_bytes in ((b"bridge_profile_abi", profile[:8]), (b"bridge_profile", profile)):
        if name not in exported or bridge.get_data(exported[name], len(expected_bytes)) != expected_bytes:
            raise RuntimeError(f"Packaged architecture profile differs: {name!r}")
    if not {b"BridgeDiagnoseLoadSafe", b"bridge_callback_lifecycle"}.issubset(exported):
        raise RuntimeError("Packaged bridge lacks the 2.0.8/2.0.9 repairs")
    for name, expected_bytes in (
        (b'equipment_effect_abi',struct.pack('<3I',0x2426805b,216,1672)),
        (b'item_safety_abi',struct.pack('<3I',0x24268056,216,600)),
    ):
        if name not in exported or bridge.get_data(exported[name],12)!=expected_bytes:
            raise RuntimeError('Packaged equipment safety ABI differs: '+name.decode('ascii'))
    clock=pefile.PE(data=archive.extract(PACKAGE_BINARIES[2]))
    exports={entry.name:entry.address for entry in clock.DIRECTORY_ENTRY_EXPORT.symbols}
    if (clock.FILE_HEADER.Machine!=0x8664 or b"SpeedControl" not in exports
            or b"speed_clock_abi" not in exports
            or clock.get_data(exports[b"speed_clock_abi"],16)!=struct.pack("<4I",0x57435331,1,88,1000)):
        raise RuntimeError("Packaged speed clock ABI differs")
    license_entry="licenses\\LICENSE.txt"
    if license_entry not in archive.toc or archive.extract(license_entry)!=(ROOT/"third_party/minhook/LICENSE.txt").read_bytes():
        raise RuntimeError("MinHook distribution license missing or different")
    return bundled


def verify_manifest() -> None:
    branch, head = assert_workspace()
    manifest = json.loads((OUTPUT / "current.json").read_text(encoding="utf-8"))
    exe = (OUTPUT / manifest["artifact"]).resolve()
    if not exe.is_relative_to(OUTPUT.resolve()) or exe.name != EXE_NAME:
        raise RuntimeError("Release manifest points outside the verified output")
    if (manifest["branch"] != branch or manifest["head"] != head
            or manifest["source_sha256"] != source_hashes()):
        raise RuntimeError("Worktree inputs differ from the built release")
    if manifest["exe_sha256"] != sha256(exe):
        raise RuntimeError("Release EXE differs from the recorded build")
    if manifest["bundled_sha256"] != inspect_exe(exe):
        raise RuntimeError("Packaged DLLs differ from the recorded build")
    print(f"verified: {exe} SHA-256={manifest['exe_sha256']}")


def build() -> None:
    branch, head = assert_workspace()
    before = source_hashes()
    staging_root = ROOT / "build"
    staging_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="release-2105-", dir=staging_root,
                                     ignore_cleanup_errors=True) as temporary:
        stage = Path(temporary)
        native = stage / "native"
        run("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            "tools/build_engine_bridge.ps1", "-OutputDirectory", str(native))
        run("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            "tools/build_talent_icon_display.ps1", "-OutputDirectory", str(native))
        run("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            "tools/build_speed_clock.ps1", "-OutputDirectory", str(native))
        compiled = {
            PACKAGE_BINARIES[0]: sha256(native / "war3_bridge_24268.dll"),
            PACKAGE_BINARIES[1]: sha256(native / "war3_talent_icon_display.dll"),
            PACKAGE_BINARIES[2]: sha256(native / "war3_speed_clock.dll"),
        }
        environment = dict(os.environ)
        environment["RELEASE_210_BRIDGE_DLL"] = str(native / "war3_bridge_24268.dll")
        environment["RELEASE_210_ICON_DLL"] = str(native / "war3_talent_icon_display.dll")
        environment["RELEASE_210_SPEED_DLL"] = str(native / "war3_speed_clock.dll")
        run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
            "--distpath", str(stage / "dist"), "--workpath", str(stage / "build"),
            "War3ReforgedTrainer-2.1.05.spec", env=environment)
        exe = stage / "dist" / EXE_NAME
        bundled = inspect_exe(exe, compiled)
        if before != source_hashes():
            raise RuntimeError("Release inputs changed during the build")
        exe_hash = sha256(exe)
        artifact = Path(exe_hash[:12]) / EXE_NAME
        final_exe = OUTPUT / artifact
        final_exe.parent.mkdir(parents=True, exist_ok=True)
        if final_exe.exists():
            if sha256(final_exe) != exe_hash:
                raise RuntimeError("Existing immutable release artifact differs")
        else:
            pending_exe = final_exe.with_suffix(".exe.tmp")
            shutil.copyfile(exe, pending_exe)
            if sha256(pending_exe) != exe_hash:
                raise RuntimeError("Copied release artifact differs")
            os.replace(pending_exe, final_exe)
        manifest = {
            "version": "2.1.05", "release_channel": "stable", "prerelease": False,
            "release_status": "built_not_published", "branch": branch, "head": head,
            "source_sha256": before, "bundled_sha256": bundled,
            "exe_sha256": exe_hash, "artifact": artifact.as_posix(),
        }
        pending = OUTPUT / "current.json.tmp"
        pending.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(pending, OUTPUT / "current.json")
    verify_manifest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    verify_manifest() if args.verify_only else build()
