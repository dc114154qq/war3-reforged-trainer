[中文](README.md) | [English](README.en.md)

# Warcraft III 3.0 Trainer · 2.1.09

Read and edit units, abilities, items and player resources. Includes batch editing, extended backpacks and save-data extraction.

## Download and use

Get the EXE from the [website](https://twomengxi.xyz/trainer/?lang=en) or [GitHub Release](https://github.com/dc114154qq/war3-reforged-trainer/releases/tag/v2.1.09). Enter a map, select a unit, then open the trainer and connect.

The **3.0.1.24360** adapter is built in. No separate import is needed.

The batch tab now reads faster and keeps every unit's editable fields.

## Game builds

Warcraft III 3.0: `3.0.0.24268`, `3.0.1.24323`, `3.0.1.24332`, `3.0.1.24342` and `3.0.1.24360`.

Adapters are selected by executable fingerprint. Unlisted builds use automatic discovery, with checks for each function.

## Build from source

Requires Windows 10/11 x64, Git and Python 3.12 with Tkinter. Run from the repository root:

```powershell
python -m pip install -r requirements-build.txt
python tools/prepare_build_baseline_209.py
python tools/build_release_209.py
python tools/build_release_209.py --verify-only
```

The preparation script downloads a hash-pinned native build dependency. The builder reuses its three published DLLs and checks the source and file hashes. The trainer does not download this dependency at runtime.

Output: `dist-2.1.09-verified/<hash-prefix>/War3ReforgedTrainer-v2.1.09.exe`.

## Source and verification

This tree contains only the runtime, adapters, native source and build files for 2.1.09. Earlier releases remain in Git tags and Releases. Older game-build profiles in `profiles/` are still required by this version.

4,908 offline tests and 120 subtests passed (29 skipped), along with five-build performance, packaged-file, offline EXE startup and UI-resource checks. Read-only checks on 24360 covered players, selected units and properties. Gameplay changes and external-machine execution have not been verified.

[Release notes](docs/RELEASE_NOTES.en.md) · [Release history](docs/HISTORY.md) · [Validation](docs/VALIDATION.json)
