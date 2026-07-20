<p align="right"><a href="README.md">中文</a> | <strong>English</strong></p>

# Warcraft III: Reforged Trainer

This is a local trainer for Warcraft III: Reforged. The current version prioritizes stability: player resources, selected-unit attributes, learned hero abilities, inventory slots, and other features use direct memory reading and writing. The trainer rejects writes that could leave empty command-card slots, make abilities disappear, or crash the game.

## Community Link

This project links to and recognizes the [LINUX DO community](https://linux.do/), follows its open-source promotion requirements, and accepts community oversight.

## Download and Run

Download `War3ReforgedTrainer-v1.0.6.exe` from GitHub Releases and run it directly. It is a single-file GUI application packaged with PyInstaller. It does not open an additional console window and does not require Python to be installed.

Before running the trainer, start Warcraft III: Reforged, enter a map, and select the target unit. The trainer will automatically find the running `Warcraft III.exe` process.

## Compatible Versions

- Tested in-game version: `Warcraft III: Reforged 2.0.4.23745`.
- Other `2.0+` versions have not been tested individually and are not guaranteed to work. This trainer depends on the memory layout of the current Reforged process. If a Blizzard update changes the selected-handle, unit components, or inventory object layout, the trainer may require a compatibility update.
- If the game is running as administrator, the trainer must also be run as administrator.

## Use Backup Read When Normal Reading Fails

If clicking `Read Selected Unit` causes `WinError 299`, displays only part of the fields, fails to read, returns the wrong unit, or remains locked to the first unit read, follow these steps:

1. Left-click the target unit in the game and make sure it is the only selected unit.
2. Click `Backup Read` next to the normal read button.
3. After Backup Read succeeds, continue modifying attributes, Intelligence, abilities, and inventory through the same field table. Related writes will continue using the backup compatibility path.

`Backup Read` is only a feature name and is not limited to a particular Windows version. It handles differences in process-memory paging and heap layout across computers, so it can be used on both Windows 10 and Windows 11 when these issues occur. If Backup Read still fails, provide `log\win10-read-latest.log` from the trainer directory. If the application directory is not writable, the log is stored under `War3ReforgedTrainer\log` in the system temporary directory.

## Features

- Player resources: read multiple faction/player resource groups and modify gold, lumber, and food values.
- Current selected unit: read and modify HP, MP, regeneration, coordinates, experience, skill points, primary attributes, armor, movement speed, attack-related fields, and more. Non-hero units or units without inventories show only the component fields that actually exist. Missing hero, ability, or inventory components do not indicate a read failure.
- Unit component discovery: the first read builds a global component index validated by owner relationships rather than by the address distance between a component and its unit owner. Later reads in the same game process use the verified cache.
- Candidate unit list: when Reforged's selection state contains historical targets, temporary objects, or multiple unit references, the trainer can list candidates and show HP/MP, coordinates, `refs/known`, components, inventory slots, and `handle/owner/unit`. The user can then choose the unit that best matches the in-game display. The candidate table includes results from the slower global scan and does not depend on the selected-handle slot remaining valid.
- Inventory: read `Inventory Slot 1..6` and `Inventory Slot N Count` from the field table on the `Selected Unit` page, then modify the target slot with `Target Field Value` and `Write Field`. The current implementation modifies only the item object associated with the target slot; it does not imitate a change by swapping two slots. After a count write, the hero selection is refreshed so the inventory number updates immediately.
- Hero abilities: read and replace learned ability rawcodes. A write synchronizes the hero ability configuration with the runtime ability instance and refreshes the command card. The target ability does not require a living unit template in the current match. If the Reforged engine can create an ability with that rawcode from the current map/object data, the trainer can produce a safe runtime template.
- Ability fields: enter an ability rawcode and field level on the dedicated page to read exposed integer, real, Boolean, and string fields from the current ability instance. Selected fields can be modified temporarily for the current match and verified by reading them back.
- Elephant Features and hotkeys: provides map, unit, hero, item, ability, technology, buff/debuff, and full-screen effect functions, together with 45 independently configurable global hotkeys. Hotkeys first use Windows global registration. If a key combination is already occupied, the trainer automatically switches it to compatibility listening and lists the affected keys in the interface.

## Current Limitations

- Ability replacement does not attach a map object-record pointer directly to a runtime instance. The target ability is temporarily created through the Reforged engine, the required runtime fields are captured, and the temporary instance is immediately removed. The trainer rejects the write when the current unit already has a duplicate rawcode, the ability slot is empty, or the original slot cannot be identified unambiguously.
- In Reforged, the actual effect of a learned ability is not determined solely by the rawcode in the hero ability list or by a cached rawcode. It is bound to the runtime ability instance and data object. This version writes only the verified minimum runtime fields and does not copy a large ability payload.
- The trainer does not modify game files, save files, or map files.
- The trainer does not use OCR or screenshots to identify the current target. It locates the selected unit only through the in-memory selected-handle/selected-unit slots. The selected-unit locator dynamically scans the selection-state area and votes when multiple addresses consistently point to the same unit object. It retries briefly while a new match is initializing. If no verifiable selection slot is found, it reports an error instead of guessing from panel values or whole-memory unit-pointer reference counts.
- A purely external memory reader cannot guarantee 100% automatic identification of the selected unit. Reforged can retain historical targets, side-path objects, or temporary objects in the selection-state area. The trainer uses only strong-evidence results for automatic reading. Weak-evidence results are shown only in the candidate table so the user can select a target using component and inventory-slot clues.
- The trainer invokes the restricted helper only when the game engine must create a runtime template for an ability. The helper permits only internal ability find/add/remove/refresh operations and never writes an object-resource-record address directly into a runtime ability.

## Interface Notes

- `Read Selected Unit` and `Refresh Field Table` both read the unit currently selected in the game again and refresh the HP, MP, and coordinate inputs above. This prevents stale values from remaining visible after switching units.
- `Backup Read` is next to `Read Selected Unit` and is intended for `WinError 299`, missing fields, incorrect units, and normal-read failures. Backup Read revalidates the live in-game selection and never falls back to the previously read unit.
- `List Unit Candidates` shows every interpretable candidate in the current selection-state area. Higher `refs/known` values indicate stronger evidence. Heroes usually have `hero,inventory` components and an inventory-slot list, while regular units may have only components such as `attack,move`. After choosing a row, click `Read Selected Candidate`. Subsequent `Write Selected Unit` and `Write Field` operations remain fixed to that candidate's `handle/owner/unit` until another automatic read or manual candidate selection occurs.
- If the selected-handle slot is invalid, `Read Selected Unit` reports an error and automatically fills the candidate table. The slow global scan usually takes tens of seconds. Use HP/MP, coordinates, components, and inventory slots to identify the target.
- By default, a field-table write targets the unit represented by the current field table instead of guessing the current selection again for every write. After changing equipment, the trainer can therefore read back the same unit even if Reforged's selected-handle slot temporarily becomes invalid.
- `Write Selected Unit` writes current HP, maximum HP, current MP, maximum MP, regeneration, and coordinates through their respective interface fields. It automatically raises a maximum only when the current value exceeds that maximum.
- Equipment/item modification follows the classic trainer's field-table workflow. On the `Selected Unit` page, select `Inventory Slot N` or `Inventory Slot N Count`, enter `Target Field Value`, and click `Write Field`. An empty slot has no item object that can be rewritten directly and therefore produces an error. Count writes use Warcraft III's native item-count field.
- Ability modification also uses the field-table workflow. Select `skillN_name`, enter the target ability rawcode, and click `Write Field`. The write fails with an explanation if the target rawcode already exists on the current unit or the engine cannot create an ability template from the current map/object data.
- If no verifiable selected unit is found during the current read, the interface clears the old unit and inventory values and reports an error instead of keeping the previous unit on screen.

## Can Other Users Run the Downloaded EXE Directly?

What can be guaranteed: the EXE is a single-file GUI build. It does not depend on the local installation of Python, PIL, or Capstone, and it does not require a separately installed helper DLL. The current build has passed compilation, packaging, and local verification of selected-unit and field reads through memory.

It cannot be guaranteed to work on every computer because it depends on these external conditions:

- A 64-bit Windows environment.
- A running Warcraft III: Reforged process.
- A game version and memory layout compatible with this build's detection logic. Only `2.0.4.23745` has been tested.
- The trainer must have privileges equal to or higher than the game process. If the game is running as administrator, the trainer must also run as administrator.
- Antivirus software or system policies must not block reading from or writing to the game process.

When these conditions are met, the EXE from Releases should run directly. If a Blizzard update changes the memory layout, the selected-unit locator or field addresses may require another compatibility update.

The trainer also cannot promise to identify the correct unit automatically on every read. Automatic reading accepts only strong evidence such as selected-handle or known selected-unit slots. When the evidence is insufficient, use the candidate unit table and select the target using HP/MP, coordinates, components, inventory slots, and `handle/owner/unit` clues.

## Development Self-Checks

```powershell
python .\war3_reforged_trainer.py --read-selected
python .\war3_reforged_trainer.py --read-selected-fields
python .\war3_reforged_trainer.py --list-selection-candidates
python .\war3_reforged_trainer.py --verify-selection-locator
```

These checks are used only during development to verify process discovery and selected-unit location. `--read-selected`, `--read-selected-fields`, `--list-selection-candidates`, and `--verify-selection-locator` are read-only operations. The EXE in Releases is a console-free GUI build and is not suitable for viewing command-line output.

The `handle,owner,unit` tuple printed by the candidate table can also be used for fixed reads or same-value write verification:

```powershell
python .\war3_reforged_trainer.py --unit-identity 0xHANDLE,0xOWNER,0xUNIT --read-selected-fields
python .\war3_reforged_trainer.py --unit-identity 0xHANDLE,0xOWNER,0xUNIT --set-unit-field inventory_slot_1=ofir
```

## Development Notes

- Main program: `war3_reforged_trainer.py`
- Packaging configuration: `魔兽争霸3重制版修改器.spec`
- Read-only selected-unit probe for development: `tools/war3_selected_probe.py`
- Read-only native-table disassembler for development: `tools/war3_disasm_native.py`

Packaging command:

```powershell
python -m PyInstaller .\魔兽争霸3重制版修改器.spec --noconfirm
```

Build output:

```text
dist\魔兽争霸3重制版修改器.exe
```
