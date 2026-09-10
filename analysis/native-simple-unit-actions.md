# Shared simple unit actions use full identity guards

2026-09-10. Branch `codex/v1.0.19-bound-unit-actions`; application 1.0.19,
native protocol 60. Builds on the previously committed all-attributes change.

## Reachable paths and fix

The boolean and void action helpers opened an external memory backend, obtained
a JASS handle, queried the complete Elephant function set, then issued an
unguarded operation. This affected invulnerability, pathing, pause, cooldown
reset, kill and removal. Explode separately combined flag-setting and killing
inside an older op without identity validation between its callbacks.

These seven public operations now share `_run_bound_simple_unit_actions`:

- Capture candidate and JASS handle together using `_direct_selected_context`,
  honoring the existing per-unit batch override.
- Query only the native names needed for the requested action through the DLL
  table. Already resolved handlers remain reusable; no external memory backend
  or broad Elephant function discovery is invoked by this helper.
- Submit a unit generation guard followed by bool/void operations in one
  command. Explode uses bool(SetUnitExploded,true) then void(KillUnit).
- Validate returned operation count, kinds, errors and callback acknowledgments.

The C dispatcher now permits bool/void operations after an identity guard and
checks that identity before each callback. Guarded operations validate argument
shape and executable handler address. If the explode flag callback destroys or
recycles the target, the following kill cannot operate on a replacement.

There is intentionally no final identity test after a lone RemoveUnit/KillUnit:
the action can legitimately invalidate its own target. A successful void call
means the callback returned; boolean acknowledgments echo the requested value.
These are not independent proofs of the resulting game state. The change does
not claim rollback if a later callback fails after an earlier one completed.

## Verification

Production C dispatcher tests cover true/false, void, both explode callbacks,
missing/reused handles, changed generation/owner, malformed commands,
nonexecutable handler addresses, exceptions and destruction between callbacks.
They also require successful acknowledgment when the final intentional removal
invalidates its own handle.

Python tests execute all seven public methods (including both boolean values),
both trainer classes, real selected-context binding and the command serializer.
They verify only the requested native names are queried, forbid external memory
setup, preserve a bound batch target across selection changes, and reject
incomplete/mismatched acknowledgments.

Targeted suite: 68 tests and 49 subtests passed in 4.80 seconds.
Full regression: 1072 tests and 113 subtests passed in 69.97 seconds.
Log: `analysis/native-simple-unit-actions-regression.log`. Diff checks passed.
Compiled helper and tracked DLL SHA256 both:
`d4705ba4d213a0a826c848d85b0d0845a40cd541dee69982a0cb721b37f72cff`.

These are isolated code tests; no running game was read or modified. No EXE was
packaged and previously delivered/accepted packages remain unchanged. User
acceptance of e034231 does not establish acceptance of these later changes.
