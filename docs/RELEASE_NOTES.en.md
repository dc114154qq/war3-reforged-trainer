# Warcraft III 3.0 Trainer 2.1.13

Completes the bundled **3.0.1.24371 r2** adapter. No separate profile installation is needed.

- Restores the detailed-attribute service after independently reviewing both class methods for all four stat types.
- Adds all six fog recovery locations and the alternate player index. Fog recovery now checks the actual 4-byte or 5-byte instruction length.
- Handles the new ability-level tail register form, retaining mandatory level readback and strict exception checks.
- Fixes the decoder changes in 24365 and 24371 by following actual branches and the complete arithmetic into the independently located player accessor. With the target profile hidden, live automatic connection, external unit reads and cache validation succeeded.
- Adds typed recovery and player-mode discovery. Fog queries require only their getter dependencies. A unique newer exact-profile revision supersedes an older one; conflicting contents at the highest revision still report an error.

Automatic support remains partial: some protected code captures still lack Native ABI or advanced-field evidence, so dependent operations are blocked before dispatch. Future updates may still need a dedicated adapter.

Live read-only fog, unit-stat, binding, detailed-stat and camera queries completed with readback and cleanup. The detailed-stat sample had no matching abilities and returned zeros. No game stat setters, fog toggles, skill additions or game UI input were executed. Actual mutation effects, alternate-mode gameplay, Ctrl+X landing and external-machine behavior remain unverified.

Offline validation: 5,052 distinct tests and 120 native subtests passed across separate processes; 29 skipped. All seven exact profiles passed the paired offline performance gate, archive inspection and frozen startup self-test passed. Initial failures and subsequent corrections are retained in the evidence.

Bundled builds: 3.0.0.24268, 3.0.1.24323, 3.0.1.24332, 3.0.1.24342, 3.0.1.24360, 3.0.1.24365 and 3.0.1.24371. Other builds retain their existing profile limits.
