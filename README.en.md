[中文](README.md) | [English](README.en.md)

# Warcraft III 3.0 Trainer · 2.1.16

Read and edit units, abilities, items and resources. Includes batch editing, extended backpacks, equipment loadouts and save extraction.

## Download and run

Download the EXE from the [website](https://twomengxi.xyz/trainer/?lang=en) or [GitHub Release](https://github.com/dc114154qq/war3-reforged-trainer/releases/tag/v2.1.16). Enter a map, select a unit and connect.

Windows 10/11 x64. No Python, Node.js or separate frontend server is needed. First launch offers Microsoft WebView2 setup if it is missing; installation requires Internet access.

Adds remaining-gold editing for selected mines and all mines on the map under Player Resources, with amounts and outcomes shown per mine.

## Build from source

Windows x64, Python 3.12 and Node.js 22. The helper downloads and verifies pinned native components and Microsoft setup dependencies.

```powershell
python -m pip install -r requirements-build.txt
python tools/prepare_build_baseline_2116.py
npm ci --prefix frontend
npm run build --prefix frontend
python tools/build_modern_release.py
python tools/build_modern_release.py --verify-only
```

Output: `dist-2.1.16-modern-verified/<hash-prefix>/War3ReforgedTrainer-v2.1.16-Web.exe`.

[Release notes](docs/RELEASE_NOTES_v2.1.16.en.md) · [History](docs/HISTORY.md) · [Validation](docs/VALIDATION.json)
