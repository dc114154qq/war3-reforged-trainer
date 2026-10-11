# Warcraft III Reforged Trainer 2.1.06

This release is for **Warcraft III 3.0**. It improves official backpack setup and diagnostic logs, and adds automatic detection for newer game builds. Users of official backpacks are encouraged to update.

## Changes

- **Check the abilities that an official backpack needs.** For reports where the backpack item was added but the equipment or talent panel did not open, setup now checks the inventory, equipment, hero talent controller and panel-opening ability, adding missing parts. Garrick's backpack is included. Each added part is checked in the game; a failed check stops the remaining steps.
- **More useful backpack logs.** Both success and failure record the trainer and game versions, target unit and individual steps. Include `backpack-*.log` from the log directory when reporting a problem.
- **Automatic detection for new game builds.** For a build in the same version series without its own adapter, the trainer attempts to find the required data and enables functions as their dependencies are confirmed. The four supported builds keep their own adapters.
- **Expanded equipment and hero ability lists.** The official equipment list now has 325 entries, with 27 ability records added for six heroes. Availability depends on the data loaded by the map.
- **Corrected the attack-speed component configuration for 3.0.1.24332.** Campaign-save, hero-data and RPG save-code extraction from the previous release are retained.

## Supported builds and use

Supported Warcraft III builds remain **3.0.0.24268, 3.0.1.24323, 3.0.1.24332 and 3.0.1.24342**. The matching adapter is selected automatically.

Select the target hero before adding an official backpack. Clear the first ordinary inventory slot if it holds another item. If the correct backpack is already there, using the add function again checks and completes missing abilities.

Automatic detection has limits. Some equipment, talent, effect and map-reveal data on new builds remain unconfirmed. Affected functions report this while independently confirmed functions remain available. Detection does not establish complete support for all future updates.

## Verification

The full code regression completed with 4,636 tests and 120 subtests passing and 29 skipped. Adapter-path and performance checks passed for all four supported builds. Packaging and the offline startup self-test passed. Read-only detection was also checked on the current 3.0.1.24342 game.

Backpack completion passed code checks. Whether the panel opens on the previously affected PC still needs that PC's result with this release; the issue is not listed as resolved by an external-PC game test.
