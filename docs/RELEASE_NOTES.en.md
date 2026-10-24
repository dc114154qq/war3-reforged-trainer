# Warcraft III 3.0 Trainer 2.1.18

Improves backpack-definition processing with chapter-script preflight checks, obsolete archive-data cleanup and verification of original resources. Retains this version's inventory cloning, equipment placement and native talent-state improvements.

1. **Copy extended inventory**: fixes copy failures caused by incorrect ability and item identity conversion in some maps; copies the 30-slot extended bag as well as the classic six slots, preserving occupied slots and gaps. Checks actual inventory membership so a dropped item is not reported as successfully copied.

2. **Keep equipment in the correct slots**: restores main-hand, off-hand and accessory positions. Two rings retain separate slots instead of the second replacing the first.

3. **Copy talent selections and unspent points**: preserves learned choices and remaining points in supported native talent systems, fixing clones that appear to have no talent progress.

4. **Avoid duplicate backpack abilities**: restores abilities supplied by inventory and equipment through their items, avoiding an additional standalone copy of the same ability.

5. **Fix talent choices**: supports custom backpacks that use the native talent structure. Selecting a tier shows its actual choices, and adding a talent validates both tier and choice. Removes the misleading manual icon-refresh button.

6. **Clear results and detailed logs**: verifies copied item positions and talent state. Failed or partial operations show a popup with the differences and the detailed log location.

7. **More robust definition processing**: retains support for incomplete archive filenames. Checks map-function declaration order before writing and reports the affected chapter and line if an error is found. Removes obsolete archive data to prevent repeated processing from inflating the file, then reopens and verifies original scripts, resources and added definitions. The original file is preserved.

Cloning covers the exposed inventory and equipment positions, ordinary ability levels and native talent state described above. Campaign-private quest progress and character-specific script variables are outside this scope.

**Run**: Warcraft III 3.0, Windows 10/11 x64. Close the previous version and launch the EXE directly; no Python, Node.js or separate frontend server is needed. The lightweight desktop uses Microsoft WebView2. If missing, first launch offers an Internet-based installation.

Retains mouse positioning, gold-mine editing, ability and item fields, loadout restoration and existing features. This revision changes offline map archive processing; all game profiles and four native components are unchanged. This revision passed 49 related regression tests, three special-archive samples and a complete 12-chapter processing check. The built-in script preflight checks declaration order; gameplay still requires testing the processed map in the game.
