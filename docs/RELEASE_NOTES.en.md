# Warcraft III 3.0 Trainer 2.1.17

Corrects the conversion from mouse position to game coordinates for more accurate placement with Ctrl+X teleport, Ctrl+A unit cloning and other features that share mouse coordinates. Shortcuts and usage stay the same.

1. **More accurate Ctrl+X teleport**: corrects the offset from the mouse and accounts for camera view, zoom and window aspect ratio.
2. **Ctrl+A unit cloning also corrected**: units cloned at the mouse use the same updated coordinate conversion. Other features using this shared mouse-position path benefit too.

**A user tested the preview and confirmed accurate placement with both Ctrl+X and Ctrl+A.** Map collision and map boundaries can still affect final placement.

**Run**: Warcraft III 3.0, Windows 10/11 x64. Launch the EXE directly; no Python, Node.js or separate frontend server is needed. The lightweight desktop uses Microsoft WebView2. If missing, first launch offers an Internet-based installation.

Retains gold-mine editing, item effects, ability fields, loadout restoration, backpack-definition processing, custom artifact presets and existing features, with the same seven game adapter profiles.
