# 3.0 stat read audit — 2026-09-26

- Target: local Warcraft III process PID `22708`; read-only probe, no field write.
- Target unit: `1052556`.
- Runtime values read from the current stat-detail transaction:
  - critical chance: `100%`
  - critical damage: `150%`
  - spell critical chance: `100%`
  - spell critical damage: `150%`
  - ability speed flat: `0`
  - ability speed percent: approximately `60%`
- The transaction returned `changed=0` and identical before/after raw values, confirming this probe did not modify the unit.
- This verifies runtime-field readback and target binding. It does not verify actual combat damage or cooldown timing; those remain user gameplay tests.
