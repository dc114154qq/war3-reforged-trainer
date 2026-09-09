# Ability effect lifecycle, protocol 51

The selected sustained/area effect entry point now uses op 136 + 158 + 159 to
start, and op 136 + 160 to finish. The native helper retains the unit's JASS
handle and full identity, ability wrapper/data generation and level, original
and requested area bits, whether it created the ability, effect count and
current order. Python receives a token instead of an ability pointer. Point
effects with no explicit coordinates obtain the same unit's position inside
the start callback.

Start validates arguments before mutation, creates absent abilities using
UnitAddAbility, modifies and reads back area, hides a newly created held
ability, and executes all requested passes within one game-thread callback.
Each engine call is followed by identity checks. Finish verifies the same
token and unit, checks that the current order still matches, stops the effect,
restores the exact original area bits and removes only its own temporary
ability. An intervening third area value is not overwritten. Non-held effects
perform cleanup within start. No Sleep runs inside the helper.

This replaces the old unbound standalone ability-field writes (rejected by
the current dispatcher), external vtable/ability reads, per-pass commands and
unguarded field restoration. The controller only waits for the requested
effect duration; it issues finish from finally if the wait is interrupted.
Five additional natives are bound through the existing exact-build native
table profile, bringing the required table to 43 entries. The application
version remains 1.0.19; both protocol definitions and the DLL are updated.

Evidence:

- 35 lifecycle tests passed (3.59 s). The production C dispatcher is exercised
  with fake engine natives for existing/new abilities, immediate/point/noarg
  effects, native-coordinate lookup, held/unheld modes, area restoration,
  multiple passes, creation-independent validation, setter/effect exceptions,
  changed unit/ability generations and levels, conflicting orders/area writes,
  duplicate starts and replayed or unknown finish tokens. Controller tests
  exercise one start/finish pair and KeyboardInterrupt cleanup.
- Full regression: **839 tests and 103 subtests passed** (41.28 s), recorded
  in `analysis/native-effect-lifecycle-regression.log`.
- Helper compiled with clang -shared -O2 and was copied to the tracked DLL.
  No game calls, EXE build, or user gameplay acceptance occurred in this work.

Outstanding recovery work (not established by these tests):

- Held records have no automatic deadline cleanup. A controller crash, lost
  response, or missing finish call can leave a modified effect active. The
  current control-side transaction lock remains held during its chosen wait.
- Failed cleanup retains its token (included in the error) and blocks a new
  held effect on that unit. There is no UI retry/reconciliation flow yet;
  the table has 16 slots. Unknown creation ownership or an exception before
  a post-effect order was captured is reported rather than guessed away.
- Matching an order ID does not prove that the user did not reissue the same
  order during the wait. Gameplay resource compatibility, effect duration,
  map transitions, and cleanup after controller exit remain to be verified.
- Roar/buff constructor discovery, full-map direct enumeration, and toggle
  effects still have separate legacy paths. The overall goal is unfinished.
