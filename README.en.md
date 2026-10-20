[中文](README.md) | [English](README.en.md)

# Warcraft III 3.0 Trainer · 2.1.12

Read and edit units, abilities, items and player resources. Includes batch editing, extended backpacks and save-data extraction.

## Download and use

Download the EXE from the [website](https://twomengxi.xyz/trainer/?lang=en) or [GitHub Release](https://github.com/dc114154qq/war3-reforged-trainer/releases/tag/v2.1.12). Enter a map, select a unit and connect.

Includes a dedicated **3.0.1.24371** adapter, the previous local Ctrl+X terrain-intersection fix, and a correction to premature object-identity confirmation in discovery.

## Game profiles

Seven bundled builds: `3.0.0.24268`, `3.0.1.24323`, `3.0.1.24332`, `3.0.1.24342`, `3.0.1.24360`, `3.0.1.24365`, `3.0.1.24371`.

On 24371, **3.0 detailed attributes, fog operations and alternate local-player mode remain disabled**. Other builds retain their own capability limits. Complete automatic adaptation to future unknown builds remains unverified.

## Build from source

Windows 10/11 x64, Git and Python 3.12 with Tkinter. From the repository root:

```powershell
python -m pip install -r requirements-build.txt
python tools/prepare_build_baseline_2112.py
python tools/build_release_2112.py
python tools/build_release_2112.py --verify-only
```

The preparation script downloads this release's hash-pinned EXE as the carrier of native/runtime dependencies verified identical to local 2.1.11. Use `--from-file PATH` for an existing identical download. The builder checks native inputs and discovery source coverage for all seven profiles. Runtime adapter downloads are not required.

Output: `dist-2.1.12-verified/<hash-prefix>/War3ReforgedTrainer-v2.1.12.exe`.

## Verification and history

Across separate runs, 5,013 distinct tests and 120 subtests passed; 29 skipped. Archive checks and EXE startup self-test passed. Live read-only queries passed; mutation effects, teleport landing and external-machine operation remain unverified. One existing Tk initialization failure in the full process passed in a fresh process; records are retained.

This tree contains current build inputs and historical release notes. Root candidate notes preserve their original local snapshot; published notes are linked below.

[Current release](docs/RELEASE_NOTES_v2.1.12.en.md) · [History](docs/HISTORY.md) · [Validation](docs/VALIDATION.json) · [Backpack definitions](docs/EXTENSION_DEFINITIONS.md)
