# Warcraft III 3.0.0.24268 r30 position investigation

Date: 2026-09-15
Branch: `codex/war3-3.0.0.24268-adaptation`

## Movement change

- The r29 route wrote the same target coordinate to every selected unit and
  left existing orders active. That combination could stack a large selection
  and leave the current-build pathing loop busy.
- r30 snapshots each unit's real `GetUnitX/GetUnitY` coordinates, stops a
  nonzero current order with order `851972`, and applies the requested target
  to the first unit while preserving every other unit's relative offset.
- The bridge reads back every unit after `SetUnitX/SetUnitY`. The old direct
  indexed position property and the retired helper mover remain outside the
  production movement path.

## Verified

- Position ABI: `0x2426801e`, work size `1328` bytes.
- Focused position/boundary tests: `6 passed`.
- Full current-engine product tests: `291 passed`.
- Live PID `33728`, 15 mixed selected units:
  - no-op anchor test: `15/15` changed and completed, formation readback
    matched, `479.32 ms`;
  - `+25,+25` movement followed by restoration: `15/15` for both operations,
    formation match and restoration match, `566.50 ms` total;
  - after both probes the game window was responsive and `IsHungAppWindow`
    was false.
- The live probes changed the current orders to stop; positions were restored
  to the pre-probe coordinates. A user-facing mouse target was not used in
  this code-level probe.

## Remaining validation

- Cross-device acceptance is still pending.
- The packaged EXE still needs the user's real mouse-target test with the
  current 3.0 game build.
