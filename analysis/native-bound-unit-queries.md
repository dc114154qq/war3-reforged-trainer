# Bound shared unit queries

2026-09-10. Branch `codex/v1.0.19-bound-unit-queries`; application 1.0.19,
native protocol 61. Builds on the guarded simple-action implementation.

## Finding and change

Hero level, invulnerability state, paused state and position queries still
opened a process-memory backend, obtained a selection handle independently and
requested the broad Elephant native set. They submitted no full identity guard.

Those four read paths now share `_query_bound_unit_values`. It obtains a native
candidate/JASS-handle pair, honors an existing per-unit action override, resolves
only the requested functions, and sends one guard plus query operations. The
controller requires complete results with the correct kinds and no reported
errors; it does not replace failed reads with a default or cached value.

The C dispatcher accepts guarded op 77, validates arguments and executable
handler addresses, checks the identity before the call and checks it again
after the call. This includes the final query, preventing a changed identity
inside GetUnitY from producing an apparently valid X/Y result. Negative float
coordinates retain their uint32 bit representation through the existing ABI.
No sleeps or separate readback command were added.

## Validation scope

Production C dispatcher tests simulate disappearance, generation changes,
changed owner backlinks, exceptions and malformed commands before/between/inside
two queries. They assert no successful mixed-identity result, and check that
later queries do not run after an earlier invalidating query. Successful
coordinates decode to -50.0 and 50.25 from real C-produced result bytes.

Python tests execute all four public methods through both trainer classes,
the native selection context and production serializer. They verify only the
needed names are queried, no process-memory backend is opened, batch selection
binding survives a later selection change, and wrong/incomplete responses fail.
Two older routing tests were updated because they previously required the
legacy memory-factory calls which this change removes.

Targeted suite: 92 tests passed in 7.05 seconds. DLL rebuilt with clang
`-shared -O2 -Wno-microsoft-goto`. Built and tracked DLL SHA256 both:
`40dab1d5aa2ada9ff3272824899c0d373325eeb42c4f4ec060262920cac82986`.

Full regression: 1102 tests and 113 subtests passed in 57.39 seconds.
Log: `analysis/native-bound-unit-queries-regression.log`. Diff checks passed.

## Remaining audit candidates

An AST inventory found additional methods containing the old selected-handle
call: hero level modification, skill-point addition, scale, position writing,
take control, item addition, inventory clear/quantity/duplicate/drop actions,
owner-unit killing and a private ability-level helper. Presence of this call
alone does not prove an exposed scan or missing identity check; conditional
and legacy paths still need reachability review. This work does not claim
that the remaining setter and inventory flows have already been audited.

No game process was accessed or modified. These tests are isolated code
verification, not new user acceptance. No EXE was packaged; e034231 and other
previously delivered packages remain unchanged.
