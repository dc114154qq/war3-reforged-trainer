[中文](README.md) | [English](README.en.md)

# Warcraft III 3.0 Trainer · 2.2.3

A Warcraft-style desktop interface for editing units, abilities, items and resources, with an expanded unit field editor. Includes batch editing, extended backpacks, and equipment/talent plans with import/export, including multiple talents in the same tier. Prepare map definitions, extract saves, search/export custom objects and upgrades, or embed classic HKE menus into map copies for independent in-game use.

## Download and run

Download the EXE from the [website](https://twomengxi.xyz/trainer/?lang=en) or [GitHub Release](https://github.com/dc114154qq/war3-reforged-trainer/releases/tag/v2.2.3). Enter a map, select a unit and connect.

Windows 10/11 x64. No Python, Node.js or separate frontend server is needed. Startup offers Microsoft WebView2 setup when it is missing or outdated; installation requires Internet access.

For a blank or black window, use the safe-render launcher included in the download ZIP. Startup failures display a native error dialog with the log path. Logs normally live in `%LOCALAPPDATA%\War3Trainer\log\desktop-startup-*.log` and include the trainer version, EXE checksum, WebView2 version and interface errors. Attach the trainer operation log when a game action fails. A failed Alt+P request no longer blocks later presses; each new request reads the current target again. The hero skill catalog includes the Forsaken Paladin and its four abilities.

HKE injection preserves old map object definitions. An incomplete auxiliary object catalogue no longer blocks injection; details are recorded in the processing log.

## Build from source

Windows x64, Python 3.12 and Node.js 22. The helper downloads and verifies pinned native components and Microsoft setup dependencies.

```powershell
python -m pip install -r requirements-build.txt
python tools/prepare_build_baseline_223.py
npm ci --prefix frontend
npm run build --prefix frontend
python tools/build_modern_release_223.py
python tools/build_modern_release_223.py --verify-only
```

Output: `dist-2.2.3-modern-verified/<hash-prefix>/War3ReforgedTrainer-v2.2.3-Web.exe`.

[Validation](docs/VALIDATION.json)
