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
