# Bound unit transforms and owner group — 2.0.4.23745 / app 1.0.19

Branch `codex/v1.0.19-bound-unit-transform`, based on `32351a3`.
The last user game acceptance applies to delivered c358dbc, not these changes.

## Behavior

Scale, position, taking ownership and killing the selected owner's units now
capture the native selected identity and query only the needed native functions.
They no longer use `_elephant_selected_handle` or the full Elephant handler set.
The old selector already used native snapshots; its defect here was discarding
the full generation/object/wrapper identity before mutation, not a proven scan.

Existing op 75 and 94 now validate executable handlers and parameter shape when
bound, and validate the same unit after the setter. Float pointer ABI and packed
acknowledgments are retained. Position and scale acknowledgments describe the
requested values and completed callbacks; they do not promise a final position
unaffected by game pathing or a map trigger. Op 79 validates identity after
GetLocalPlayer, SetUnitOwner and GetOwningPlayer, and verifies the resulting
player equals the requested local player. There is no rollback after callbacks.

New op 169 freezes a group of full unit identities using native enumeration and
object-table resolvers, deduplicates it, and destroys the group before KillUnit.
It rechecks every target identity and player immediately before mutation. Reused,
removed or transferred targets are skipped; new units cannot extend the batch.
The selected source can itself die during execution without aborting the other
original targets. During collection, the source must remain valid and its player
must still match before mutation begins. Collection is bounded to 100000 entries
and a 110-second deadline; this is a maximum, not an inserted delay. Controller
timeout is 120 seconds. Temporary arrays are freed on all returned paths.

Group cleanup is attempted once, including on collection failure. A failed
cleanup is reported separately. `owner_kill_callbacks` counts completed calls,
not confirmed deaths; a callback that mutates then throws is not counted.
`owner_kill_skipped` and `owner_kill_cleanup_error` explain partial failures.

Protocol is 65; required persistent native names remain 55. Old unbound op 84
remains for compatibility but the public owner-group action uses op 169.

## Validation

Production C dispatcher tests cover float limits and ABI, malformed commands,
stale identities, callback replacement, exceptions, owner lookup/readback races,
frozen group deduplication, source destruction, transferred/recycled targets,
spawned targets, missing functions, stuck enumeration and cleanup errors. Python
tests cover both trainer classes, exact binary serialization, limited function
queries, bound selection reuse, input checks and malformed acknowledgments.

The first owner-group test run found two wrong decimal exception constants in
test assertions; these were corrected to use the actual hexadecimal constant.
The final full regression on 2026-09-10 passed **1443 tests and 113 subtests** in
84.31 seconds. Log: `analysis/native-unit-transform-regression.log` (local,
ignored). Tests use fake engine objects and do not attach to the running game.

Production helper rebuilt with clang -shared -O2 -Wno-microsoft-goto and
user32/kernel32. SHA-256:
`bd3793f126c038f6108646b3e4efb8758d33a0b4878af2d8b6961d55db4ca04e`.

## Remaining work

No EXE packaged in this step; delivered artifacts remain intact. The pending
inventory and transform changes need a consolidated game test at a suitable
checkpoint. This regression does not prove the complete migration goal.
The component/vital writer still requests `_elephant_handlers` for its setter
list; group movement also opens a controller process-memory context around its
native-table lookup. Review their reachable implementations before attributing
heap scans or changing already accepted group-movement behavior.
