# Warcraft III 3.0 Trainer 2.1.17

Corrects mouse positioning and custom-backpack talents, and fixes dropped items, duplicate backpack abilities and missing talent progress during unit cloning. The talent-choice list is also repaired.

1. **More accurate Ctrl+X teleport**: corrects the offset from the mouse and accounts for camera view, zoom and window aspect ratio.

2. **Ctrl+A unit cloning also corrected**: units cloned at the mouse use the same updated coordinate conversion. Other features using this shared mouse-position path benefit too.

3. **Custom backpack talents**: fixes missing talent lists and failed point grants or talent additions. Custom backpacks built on the native talent system now use the current map’s actual talent tiers and choices.

Verified talent reading, a one-point grant and a talent addition on a custom backpack, with test changes restored afterward.

**A user tested the preview and confirmed accurate placement with both Ctrl+X and Ctrl+A.** Map collision and map boundaries can still affect final placement.

**Run**: Warcraft III 3.0, Windows 10/11 x64. Launch the EXE directly; no Python, Node.js or separate frontend server is needed. The lightweight desktop uses Microsoft WebView2. If missing, first launch offers an Internet-based installation.

Retains gold-mine editing, item effects, ability fields, loadout restoration, backpack-definition processing, custom artifact presets and existing features, with the same seven game adapter profiles.


4. **Clone inventory and talent progress**: copies classic inventory, the 30-slot bag and all nine equipment positions, including selected talents and unspent talent points. Fixes dropped items being counted as successful and item-provided backpack abilities being added twice.

5. **Working talent choices**: selecting a tier displays its actual choices. The tier and ability code are checked again before adding a choice. Removes the misleading manual talent-icon refresh button.

6. **Clear copy results**: item location and charges are verified after creation. Special ability differences show a warning and are written to the diagnostic log. A dropped item is not reported as equipped.

Inventory and talent copying passed production-code regressions with all seven supported profiles. Campaign-private quest progress and unique-character script data are outside the copied state.
