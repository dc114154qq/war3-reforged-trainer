# Warcraft III 3.0 Trainer 2.1.15

Adds equipment bonus and item ability fields and detailed ID descriptions. Fixes repeated ability-field reads, loadout speed and equipment slots, catalogue creation, and backpack-definition processing in some campaigns.

1. **Equipment bonus and item ability editing**: choose the new mode under Item Fields, then select the item location, slot and level. Changes target the selected item instance, show the source ability, and verify identity and the previous value before writing. Map-scripted effects may behave differently.
2. **Detailed ID descriptions**: items and abilities include descriptions and base effect values; units include introductions. Search by effect text and read full descriptions. Data comes from the game's base tables; custom maps may differ. Entries without verifiable data say so.
3. **Repeated ability-field reads**: filters retired ability records and fixes errors or blank lists after editing the level. A failed read clears the previous ability summary.
4. **Faster, more accurate loadout restoration**: keeps matching items already in their correct slots, restores weapons first, and places accessories and temporarily removed equipment in their saved slots. Handles unrestricted slots automatically, shows elapsed time and blocks duplicate requests. Cyclic slot conflicts preserve all items and prompt manual completion.
5. **Equipment catalogue creation**: fixes the Create button for eagt and other items by using the same entry point as Elephant item creation. Also corrects code and level arguments in the ability catalogue.
6. **Campaign backpack-definition compatibility**: accepts copied or renamed objects that retain an older end marker, preserves original custom object data, and records the exact file, object and field position in logs. Six campaigns covering 64 chapters passed file-processing and archive verification; chapters were not individually played. Reprocess affected files and enter the generated copy from its chapter menu. Existing saved games retain their stored map data.
7. **Talent points in affected maps**: adds points directly to the hero's existing talent system. A real +1 test passed; reprocessing the map is not required for this fix.

**Run**: Warcraft III 3.0, Windows 10/11 x64. Launch the EXE directly; no Python, Node.js or separate frontend server is needed. The lightweight desktop uses Microsoft WebView2. If missing, first launch offers an Internet-based installation.

Retains the 2.1.14 desktop UI, persistent custom six-artifact preset and existing features, with the same seven supported game builds.
