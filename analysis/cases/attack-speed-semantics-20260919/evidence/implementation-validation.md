# 3.0 hero attributes and attack-speed implementation validation

Date: 2026-09-19

## Scoped product changes

- The 3.0 `Set Hero Attributes` command now executes one game-thread transaction
  using `GetHeroStr/Agi/Int` and `SetHeroStr/Agi/Int`.
- Every selected hero identity is validated before the first write. All three
  attributes are read back after each write. A partial failure restores the
  captured values and reports a rollback error if restoration is incomplete.
- The previous 3.0 direct writes to guessed hero-component offsets were removed
  from this command.
- The 3.0 attack panel now separates weapon base cooldown from current speed
  factor, effective interval, and attacks per second. The three derived values
  are read-only.

## Live validation

Target process: Warcraft III 3.0.0.24268, PID 5592.

- Runtime display sample: base cooldown `2.22`, speed factor `1.48`, effective
  interval `1.50`, attacks per second `0.6667`.
- Transaction roundtrip sample: native attributes `(29, 25, 44)` were changed to
  `(30, 26, 45)` and restored to `(29, 25, 44)`.
- Before and after restoration, attack multiplier, dice, base damage fields,
  speed factor (`1.4999995`), effective interval (`1.4200005`), and attacks per
  second (`0.7042251`) matched exactly.

## Verification

- Product and fixture bridge builds passed x64 ABI validation.
- Focused regression: 108 passed.
- Full regression: 2330 passed, 17 skipped, one localization assertion failed;
  after adding translations, that assertion and all focused tests passed, for
  an effective final result of 2331 passed and 17 skipped.
- Built executable stayed running during an eight-second one-file launch smoke
  test and contains both `war3_hero_attributes_protocol` and
  `tools/war3_bridge_24268.dll`.
- PE file version: `2.0.3.0`; product version: `2.0.3`.

## True-speed restoration and Ctrl+K follow-up

The product now distinguishes these values:

- `Expected Attack Speed`: the highest true attacks-per-second value observed
  for the same unit rawcode and weapon during the current trainer session. The
  value survives a map-side object rebuild and makes a later speed loss visible.
- `True Attack Speed`: the reciprocal of the effective interval returned by the
  current game's internal final-interval function. This field is writable.

A true-speed write calculates the required base cooldown from the game's
current aggregate factor, calls `BlzSetUnitAttackCooldown`, calls the internal
final-interval function again, and accepts the write only if the requested
attacks-per-second value is read back. A failed verification restores the
captured base cooldown.

The transaction resolves the actual selected JASS `Hunit` inside the callback.
It binds that handle to the displayed object with `GetHandleId`, object-table
owner resolution, unit-object address, full handle, rawcode, and attack pointer.
It does not pass an object-table full handle as a JASS handle.

`Ctrl+K` failed with spawn error 93 because its standalone `CreateUnit` bridge
passed JASS real parameters by value. The bridge now passes pointers, matching
the already working clone path. The newly compiled C fixture verified that X,
Y, and facing retain their exact float bits and that `hcth` creation returns a
valid handle.

Final regression after the identity correction: `2331 passed, 17 skipped, 120
subtests passed`. `test_avx_copy_model.py` was excluded from that final run
because its bundled Unicorn runtime raises a process-level access violation on
this host; it is unrelated to the changed product paths.

Live game write and live `Ctrl+K` validation were not executed in this follow-up
because the Warcraft III visible window had exited before the live test. The
attempt stopped during process/window attachment, before any game mutation.
