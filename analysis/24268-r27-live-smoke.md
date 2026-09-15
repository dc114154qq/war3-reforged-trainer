# Warcraft III 3.0.0.24268 r27 live smoke

Date: 2026-09-15
Branch: `codex/war3-3.0.0.24268-adaptation`
Target: PID `26796`, `E:\Warcraft III\_retail_\x86_64\Warcraft III.exe`

The current-engine bridge now uses synchronous `WH_CALLWNDPROC` plus
`SendMessageTimeout` delivery. The previous posted-message route could leave a
camera dispatch pending while the render thread was busy.

Live results on the selected mixed group:

- 15 selected units were read in one batch.
- Hero level roundtrip `1 -> 2 -> 1` succeeded through the new hero ABI.
- Item snapshot returned 15 rows with no mutation.
- Ability add/remove diagnostic changed 14 units and restored them.
- Item `amrc` create/remove diagnostic changed one unit and restored it.
- Clone transaction created and cleaned 15 clones, including ability/item copy;
  no clone was kept.
- Instant move changed all 15 units to the projected target and verified the
  coordinate readback; original coordinates were restored afterward.

Focused product regression: `287 passed`.

Cross-device acceptance remains pending user testing. No personal website
synchronization was performed.
