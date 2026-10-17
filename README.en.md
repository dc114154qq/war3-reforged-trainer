[中文](README.md) | [English](README.en.md)

# Warcraft III 3.0 Trainer · 2.1.10

Read and edit units, abilities, items and player resources. Includes batch editing, extended backpacks and save-data extraction.

## Download and use

Get the EXE from the [website](https://twomengxi.xyz/trainer/?lang=en) or [GitHub Release](https://github.com/dc114154qq/war3-reforged-trainer/releases/tag/v2.1.10). Enter a map, select a unit and connect.

**New:** below Read Extension State in 3.0 Extensions, prepare missing backpack definitions for a .w3n campaign or .w3x map. A separate copy is produced with a complete copyable path. All passives / All auras skip individually rejected skills after cleanup is confirmed and continue the rest.

Put the processed copy in the game folder and enter the map afresh. Existing saves retain their old data. [Details](docs/EXTENSION_DEFINITIONS.md)

## Game builds

Warcraft III 3.0: `3.0.0.24268`, `3.0.1.24323`, `3.0.1.24332`, `3.0.1.24342`, `3.0.1.24360`. Profiles are selected by executable fingerprint. Unlisted builds use automatic discovery with capability checks.

## Build from source

Windows 10/11 x64, Git and Python 3.12 with Tkinter. Run from the repository root:

```powershell
python -m pip install -r requirements-build.txt
python tools/prepare_build_baseline_2110.py
python tools/build_release_2110.py
python tools/build_release_2110.py --verify-only
```

The preparation script downloads the hash-pinned native build baseline. The builder also prepares and verifies the MPQ component. The definition data pack is included; the trainer needs no runtime download.

Output: `dist-2.1.10-verified/<hash-prefix>/War3ReforgedTrainer-v2.1.10.exe`.

## Source and verification

Only source and data needed for the current build are included. Historical release notes, Git tags and Releases are preserved.

4,953 offline tests and 120 subtests passed; 29 skipped. EXE self-test, long-path and scaling checks passed. Processed-campaign gameplay and external-machine execution remain unverified. Root build notes preserve the candidate validation snapshot; current public notes are linked below.

[Current release](docs/RELEASE_NOTES_v2.1.10.en.md) · [History](docs/HISTORY.md) · [Validation](docs/VALIDATION.json)
