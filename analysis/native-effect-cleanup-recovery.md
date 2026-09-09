# Cleanup after disappearance or completed phases (protocol 53)

Five new fault cases reproduced actual cleanup failures in protocol 52:
ability disappearance between start/finish, disappearance inside the stop
callback, removal that takes effect and then throws, a unit already idle when
cleanup runs, and an effect deleting its own ability during start.

Cleanup now probes both unit membership and the original ability's JASS
resolver. Only when the unit remains valid, membership is absent and the old
JASS handle resolves to zero does it retire the record without dereferencing
the former ability address. A detached but still resolving object or a new
generation is not treated as destroyed. The probe repeats after stop, which
can invoke triggers that remove the skill.

An idle current order (zero) needs no additional stop command. A different
nonzero order remains a conflict. A retry after a successful stop followed by
a failed area restoration does not repeat stop. A retry after removal took
effect but raised an exception retires the absent instance without deleting
again. Completion receipts and timer disarming use the existing path.

Tests exercise these changes through the production C command dispatcher and
the deadline callback. New conflicting detached/replaced-instance cases must
still fail without subsequent writes; self-removal during start still reports
that execution was interrupted, but cleanup succeeds and frees its record.
The failed restoration retry was already correct and remains covered.

Validation: the 52-test lifecycle suite passed after the fix (5.79 s), before
two additional deadline cases were included in the final full regression.
Full regression: **858 tests and 103 subtests passed** (45.11 s), recorded in
`analysis/native-effect-cleanup-regression.log`. Rebuilt protocol-53 DLL SHA256:
`403726ff1b147109f42fa95d83d1498e11e22ea9dbc858bc6231c1b20101ddd9`.

No Warcraft process was mutated, no application EXE was built, and this is not
user gameplay acceptance. Application version stays 1.0.19. The wider goal
remains open: buff/global/toggle paths and actual game-state testing still
need work. Nonzero-order conflicts, unknown creation ownership and unresolved
identity errors retain records; this change does not guess away those cases.
