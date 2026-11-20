[中文](README.md) | [English](README.en.md)

# Warcraft III 3.0 Trainer · 2.2.6

A Warcraft-style desktop interface for editing units, abilities, items, and resources, with batch editing. Save and restore equipment, talents, and items from 30-slot backpacks for one hero or all selected heroes. Loadouts can be imported and exported. Prepare map definitions, extract saves, search and export custom objects and upgrades, or embed classic HKE menus into map copies for independent in-game use.

## Download and run

Download the EXE from the [website](https://twomengxi.xyz/trainer/?lang=en) or [GitHub Release](https://github.com/dc114154qq/war3-reforged-trainer/releases/tag/v2.2.6). Enter a map, select a unit and connect.

Windows 10/11 x64. No Python, Node.js or separate frontend server is needed. Startup offers Microsoft WebView2 setup when it is missing or outdated; installation requires Internet access.

For a blank or black window, use the safe-render launcher included in the download ZIP. Startup failures display a native error dialog with the log path. Logs normally live in `%LOCALAPPDATA%\War3Trainer\log\desktop-startup-*.log` and include the trainer version, EXE checksum, WebView2 version and interface errors. Attach the trainer operation log when a game action fails. A failed Alt+P request no longer blocks later presses; each new request reads the current target again. The hero skill catalog includes the Forsaken Paladin and its four abilities.

HKE injection preserves old map object definitions. An incomplete auxiliary object catalogue no longer blocks injection; details are recorded in the processing log.

ID search and custom map data can add items or abilities, create units, and set upgrades. Unit creation starts after a three-second countdown; move the cursor into the game view. Upgrade levels default to the catalogue maximum and remain editable.

Switching sections retains catalogue position, search, and filters. Global hotkey settings, common inputs, file paths, and chapter order are saved. Drag the top chapters to reorder them. Restore the default order from the system menu.

## Build from source

Windows x64, Python 3.12 and Node.js 22. The helper downloads and verifies pinned native components and Microsoft setup dependencies.

```powershell
python -m pip install -r requirements-build.txt
python tools/prepare_build_baseline_226.py
npm ci --prefix frontend
npm run build --prefix frontend
python tools/build_modern_release_226.py
python tools/build_modern_release_226.py --verify-only
```

Output: `dist-2.2.6-modern-verified/<hash-prefix>/War3ReforgedTrainer-v2.2.6-Web.exe`.

[Validation](docs/VALIDATION.json)
