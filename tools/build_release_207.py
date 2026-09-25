"""Build and verify the 2.0.7 package from this worktree only."""

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
BRANCH = "codex/war3-2.0.7-integration-20260926"
VERSION = (2, 0, 7, 0)
EXE_NAME = "War3ReforgedTrainer-v2.0.7.exe"
OUTPUT = ROOT / "dist-2.0.7-verified"
PACKAGE_BINARIES = (
    "tools\\war3_bridge_24268.dll",
    "tools\\war3_talent_icon_display.dll",
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
    files = set(ROOT.glob("war3_*.py"))
    files.update(ROOT.glob("tools/war3_bridge_*.h"))
    files.update(ROOT.glob("tools/war3_talent_icon_*.h"))
    files.update(ROOT.glob("tools/war3_talent_icon_*.c"))
    files.update(ROOT.glob("tools/war3_talent_icon_*.S"))
    files.update(
        ROOT / name for name in (
            "War3ReforgedTrainer-2.0.7.spec",
            "tools/war3_bridge_24268.c",
            "tools/build_engine_bridge.ps1",
            "tools/verify_engine_bridge.py",
            "tools/build_talent_icon_display.ps1",
            "tools/verify_talent_icon_display.py",
            "tools/build_release_207.py",
            "tools/war3-2.0.7-version-info.txt",
            "tools/capstone.dll",
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
    if branch != BRANCH:
        raise RuntimeError(f"Wrong branch: {branch}, expected {BRANCH}")
    tree = ast.parse((ROOT / "war3_reforged_trainer.py").read_text(encoding="utf-8"))
    versions = [node.value.value for node in tree.body
                if isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == "APP_VERSION"
                    for target in node.targets
                ) and isinstance(node.value, ast.Constant)]
    if versions != ["2.0.7"]:
        raise RuntimeError(f"Source version mismatch: {versions}")
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
    with tempfile.TemporaryDirectory(prefix="release-207-", dir=staging_root,
                                     ignore_cleanup_errors=True) as temporary:
        stage = Path(temporary)
        native = stage / "native"
        run("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            "tools/build_engine_bridge.ps1", "-OutputDirectory", str(native))
        run("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            "tools/build_talent_icon_display.ps1", "-OutputDirectory", str(native))
        compiled = {
            PACKAGE_BINARIES[0]: sha256(native / "war3_bridge_24268.dll"),
            PACKAGE_BINARIES[1]: sha256(native / "war3_talent_icon_display.dll"),
        }
        environment = dict(os.environ)
        environment["RELEASE_207_BRIDGE_DLL"] = str(native / "war3_bridge_24268.dll")
        environment["RELEASE_207_ICON_DLL"] = str(native / "war3_talent_icon_display.dll")
        run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
            "--distpath", str(stage / "dist"), "--workpath", str(stage / "build"),
            "War3ReforgedTrainer-2.0.7.spec", env=environment)
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
            "version": "2.0.7", "branch": branch, "head": head,
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
