[中文](README.md) | [English](README.en.md)

# Warcraft III 3.0 Trainer · 2.1.13

Read and edit units, abilities, items and resources. Includes batch editing, extended backpacks and save extraction.

## Download and use

Download the EXE from the [website](https://twomengxi.xyz/trainer/?lang=en) or [GitHub Release](https://github.com/dc114154qq/war3-reforged-trainer/releases/tag/v2.1.13). Enter a map, select a unit and connect.

Completes the **3.0.1.24371** detailed-stat, fog recovery, alternate-player and ability-tail data, and repairs automatic state decoding for the two recent updates.

Seven bundled builds: 24268, 24323, 24332, 24342, 24360, 24365 and 24371. Features retain each profile's limits. Advanced functions on future unknown builds may still need an adapter.

## Build from source

Windows 10/11 x64, Git, Python 3.12 with Tkinter, Visual Studio 2022 Community C++ tools and Windows SDK, and LLVM clang-cl. The builder uses the default VS installation path.

```powershell
python -m pip install -r requirements-build.txt
python tools/prepare_build_baseline_2113.py
python tools/build_release_2113.py
python tools/build_release_2113.py --verify-only
```

The helper downloads the fixed-hash published 2.1.12 dependency baseline. Use `--from-file PATH` for an identical local copy. This release recompiles the bridge and verifies/reuses the other native components and runtime. No runtime adapter download is needed.

Output: `dist-2.1.13-verified/<hash-prefix>/War3ReforgedTrainer-v2.1.13.exe`.

## Verification and history

Across separate processes, 5,052 distinct tests and 120 subtests passed; 29 skipped. Seven-profile performance, archive checks and startup self-test passed. Live read-only queries passed; mutation effects, alternate-mode gameplay, teleport landing and external-machine operation remain unverified.

[Current release](docs/RELEASE_NOTES_v2.1.13.en.md) · [History](docs/HISTORY.md) · [Validation](docs/VALIDATION.json) · [Backpack definitions](docs/EXTENSION_DEFINITIONS.md)
