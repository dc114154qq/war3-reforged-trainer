# Warcraft III Reforged Trainer 2.1.0-beta

This repository contains the source and version adapter data for the 2.1.0-beta Warcraft III Reforged trainer. The repository does not commit generated EXE/DLL files, `dist` directories, test fixtures, reverse-engineering evidence, or the separate hotkey product.

## Build Requirements

Build on Windows 10/11 x64 with:

- Git
- Python 3.10 or newer (Python 3.12 is recommended)
- LLVM/Clang with `clang` available in `PATH`
- Windows SDK and its x64 import libraries, available to the Clang toolchain

The native bridge is compiled with Clang. A Python compiler package alone is not enough: the build also needs the Windows headers/import libraries supplied by the Windows SDK.

## Build From Source

Run these commands from the repository root in PowerShell:

```powershell
git clone https://github.com/dc114154qq/war3-reforged-trainer.git
Set-Location war3-reforged-trainer
git switch main

py -3.12 -m venv .venv
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt

python tools/build_release_210.py
```

The build script performs all native compilation itself. It builds and validates the engine bridge, talent-display module, and speed-clock module in a temporary directory, then passes those validated images to PyInstaller. It also checks the packaged profiles, Python architecture modules, bridge ABI, speed-clock ABI, version resource, and packaged MinHook license.

The verified executable is written below an ignored directory:

```text
dist-2.1.0-beta-verified/<sha256-prefix>/War3ReforgedTrainer-v2.1.0-beta.exe
```

The exact output path is printed by the build command. No prebuilt DLL or EXE is required in the checkout.

## Verify An Existing Local Build

After a successful build, verify the immutable artifact and its manifest with:

```powershell
python tools/build_release_210.py --verify-only
```

Verification succeeds only when the current source inputs, Git revision, recorded hashes, packaged profiles, and packaged native modules match the recorded build. If source files have changed, run a new build before verifying.

## Build Inputs

- `War3ReforgedTrainer-2.1.0-beta.spec`: the PyInstaller specification used by the release builder.
- `war3_*.py`, `war3_services/`, and the three files under `diagnostics/`: runtime Python modules included by the trainer and its explicit hidden-import list.
- `profiles/`: strict game-build adapter data.
- `tools/`: native source, generated-profile check, build scripts, and ABI validators used by this version.
- `third_party/minhook/`: the MinHook source closure required by the speed-clock module and its license.
- `assets/app_icon.ico` and `assets/app_icon.png`: application icons used by the executable and runtime UI.

The builder hashes these inputs before and after compilation. The separate `war3_hotkey_*` modules are intentionally excluded because they belong to a different product.

## Version Adapter Scope

The current adapter is for the game profile included in `profiles/`, including the verified 3.0.0.24268 profile and the supported 3.0.1 profile data present in this branch. An unknown game build must be diagnosed and matched with an adapter profile before write operations are enabled; changing a module base address alone is not a complete port.

## Repository Layout

- `main` and `master`: synchronized maintained source entry points.
- `release/v*`: source-only branches corresponding to published trainer versions.
- `v*`: immutable trainer release tags.
- `profiles/`: build-specific adapter data.
- `tools/`: buildable native sources and release verification tools.

Generated files are intentionally ignored. Build from a clean checkout when producing a release artifact.
