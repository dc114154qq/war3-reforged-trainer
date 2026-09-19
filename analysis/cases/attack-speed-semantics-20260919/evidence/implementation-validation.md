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

## Current engine speed restoration and Ctrl+K follow-up

The product exposes `Current Engine Attack Speed`: the reciprocal of the
effective interval read from the current runtime attack component with the
verified equivalent of the game's final-interval function. This field is
writable. The former `Expected Attack Speed` field and its session high-watermark
cache were removed because neither can reconstruct equipment, ability, aura,
slow, or custom-map contributions when the first observation is already made
after the campaign transition bug.

A true-speed write calculates the required base cooldown from the game's
current aggregate factor, calls `BlzSetUnitAttackCooldown`, calls the internal
final-interval function again, and accepts the write only if the requested
attacks-per-second value is read back. A failed verification restores the
captured base cooldown.

The display read itself does not dispatch a game-thread callback. This avoids a
read callback immediately followed by a write callback; that live stress case
completed the write readback but left cleanup active, after which the game
window exited. Only an explicit write uses the one-shot game-thread transaction.

The transaction resolves the actual selected JASS `Hunit` inside the callback.
It uses the same current-build unit resolver called by
`BlzGet/SetUnitAttackCooldown` and requires the result to equal the displayed
unit object. Object-table owner resolution, full handle, rawcode, and attack
pointer are also checked. It does not pass an object-table full handle as a
JASS handle.

`Ctrl+K` failed with spawn error 93 because its standalone `CreateUnit` bridge
passed JASS real parameters by value. The bridge now passes pointers, matching
the already working clone path. The newly compiled C fixture verified that X,
Y, and facing retain their exact float bits and that `hcth` creation returns a
valid handle.

Final regression after the identity correction: `2331 passed, 17 skipped, 120
subtests passed`. `test_avx_copy_model.py` was excluded from that final run
because its bundled Unicorn runtime raises a process-level access violation on
this host; it is unrelated to the changed product paths.

Final live validation used Warcraft III PID 36464:

- Zero-callback display read returned base cooldown `2.22`, speed factor
  `1.4799998`, effective interval `1.5000002`, and current engine speed
  `0.6666666` attacks per second.
- One explicit same-value true-speed write returned `0.6666665` attacks per
  second and confirmed base cooldown `2.22 -> 2.22`. The game remained
  responsive after the transaction.
- The `Ctrl+K` equivalent created rawcode `hcth` and returned handle `0x100f5e`.
  The game remained responsive after creation.

An earlier live stress attempt dispatched a read callback and an immediate
same-value write callback. The write itself returned `completed=1,error=0`, but
the second cleanup reported active/retained state and the game window later
exited. That sequence was removed from the product: display reads now use no
callback, and only an explicit write dispatches one transaction.

## Full-screen effect routing follow-up

The 3.0 immediate-effect route previously added the ability to every enemy and
invoked the enemy's own immediate callback. A successful callback therefore did
not prove that the local player's attack affected that enemy. An initial fix
kept Thunder Clap, Starfall, and the automatic area effect on the selected local
caster but incorrectly left Swarm, Monsoon, and Forked Lightning on the old
world-enumeration route.

The follow-up failure log for PID 22456 reported `error=175, attempts=0` for
Monsoon. Injection, window-thread delivery, and callback completion were all
verified. The failure occurred before enemy enumeration because the bridge
treated a JASS player handle as an internal unit owner while locating the
temporary source ability. Directly calling the protected `UnitAddAbility`
conversion target was rejected after a diagnostic run produced an execute
access violation; that experiment is not part of the product DLL.

All six full-screen commands now use the same selected-caster effect bridge.
Area effects temporarily set `aare` to `100000`; point effects also pass a
stable finite origin `(0, 0)`. Swarm and Monsoon use point callbacks, while
Forked Lightning uses its verified immediate callback. The temporary ability
and area restoration remain owned by one game-thread callback, and none of the
six commands enters the failing world-enumeration path.

Focused attack-speed, hero-attribute, product routing, native world-effect, and
localization regression: `58 passed`. Live callback validation on Warcraft III
PID 19232 returned `changed=6, count=6` for Monsoon, all three Swarm abilities,
and Forked Lightning; the game process remained responsive. Visual damage and
animation coverage still requires direct observation in the running game.
