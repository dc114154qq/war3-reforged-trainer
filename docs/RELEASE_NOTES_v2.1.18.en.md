# Warcraft III 3.0 Trainer 2.1.18

Improves unit cloning with classic inventory, extended bags, equipment positions and native talent progress. Fixes duplicate backpack abilities and missing talent choices, with clearer copy results and detailed logs.

1. **Copy extended inventory**: copies the 30-slot extended bag as well as the classic six slots, preserving occupied slots and gaps. Checks actual inventory membership so a dropped item is not reported as successfully copied.

2. **Keep equipment in the correct slots**: restores main-hand, off-hand and accessory positions. Two rings retain separate slots instead of the second replacing the first.

3. **Copy talent selections and unspent points**: preserves learned choices and remaining points in supported native talent systems, fixing clones that appear to have no talent progress.

4. **Avoid duplicate backpack abilities**: restores abilities supplied by inventory and equipment through their items, avoiding an additional standalone copy of the same ability.

5. **Fix talent choices**: supports custom backpacks that use the native talent structure. Selecting a tier shows its actual choices, and adding a talent validates both tier and choice. Removes the misleading manual icon-refresh button.

6. **Clear results and detailed logs**: verifies copied item positions and talent state. Failed or partial operations show a popup with the differences and the detailed log location.

Cloning covers the exposed inventory and equipment positions, ordinary ability levels and native talent state described above. Campaign-private quest progress and character-specific script variables are outside this scope.

**Run**: Warcraft III 3.0, Windows 10/11 x64. Close the previous version and launch the EXE directly; no Python, Node.js or separate frontend server is needed. The lightweight desktop uses Microsoft WebView2. If missing, first launch offers an Internet-based installation.

Retains the previous mouse-position correction, gold-mine editing, ability and item fields, loadout restoration and existing features. The implementation passed 961 related regression tests, including native copy tests for all seven adapter profiles. This version promotion also checks the EXE and public-source build. Full cloning has not received a real-game acceptance test in this round.
