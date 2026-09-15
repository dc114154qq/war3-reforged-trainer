# Warcraft III 3.0.0.24268 r29 position investigation

Date: 2026-09-15
Branch: `codex/war3-3.0.0.24268-adaptation`

## Production change

- Removed the product movement dependency on direct position-field writes.
- Removed the product movement dependency on the retired `SetUnitPosition`
  batch and the legacy helper mover.
- Added an independent current-engine position ABI using `SetUnitX`,
  `SetUnitY`, `GetUnitX`, and `GetUnitY` with 24-unit selection capacity.
- The controller accepts success only after per-unit native coordinate readback
  within a 0.01 map-unit tolerance.

## Evidence

- Position fixture: 15/15 units, 15 setter calls for each axis, 15 reader calls
  for each axis.
- Product 3.0 suites: `291 passed`.
- r29 bridge ABI: `0x2426801d`, work size `1312`, verified by
  `tools/verify_engine_bridge.py`.
- Frozen runtime self-test: `ok=true`; retired 2.0 helper absent.
- GUI smoke: r29 process remained responding for 4 seconds.
- Static/live read-only investigation showed the previous `candidate.x/y`
  fields are not the engine world-coordinate source.

## Live status

- Previous live `SetUnitPosition` probes were not accepted as product success;
  one path produced a partial readback and another blocked/terminated the game
  process. Those results are retained in the generated `live-*r28*.json`
  records.
- The current visible game PID `3928` had zero selected units at the time of
  r29 verification. The r29 `SetUnitX/Y` write was therefore **not executed**.
- Cross-device acceptance remains pending.
