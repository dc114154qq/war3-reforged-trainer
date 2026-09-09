# Bind unit generation before collecting native fields

2026-09-09. Development branch: `codex/v1.0.19-property-identity`.
Application remains 1.0.19; C/Python helper protocol advances from 56 to 57.

## Evidence and implementation

The snapshot producer previously captured object/full-generation/owner identity
after reading ownership, type, vitals and position. A unit handle reused during
those field queries could make the final identity validation accept the new
unit while the payload retained earlier values. The targeted entry's initial
guard did not prevent the producer from subsequently rebinding its snapshot.

The production C snapshot harness now simulates same-address, same-JASS-handle
reuse with a changed full generation and consistent object-table backlinks.
Six subtests reproduced successful mixed snapshots before the fix: selection
and targeted reads, each with replacement during type, vital or position query.
The two late-replacement controls (during ability enumeration) already failed
as intended. Tests run in an isolated process/DLL environment, not Warcraft.

The producer now captures and validates identity before the first field query.
Targeted reads also require this identity to match the caller's expected tuple.
Final validation checks the pinned identity before accessing regeneration
properties. Readable-span checks guard object and owner dereferences.

All eight replacement scenarios now reject with ERROR_INVALID_HANDLE and no
partial payload. Group tests include a previously collected unit with more than
48 abilities, and verify cleanup of its overflow allocation and the group.
No extra controller/game-thread round trips, heap scans or sleeps were added.

## Verification

- Targeted snapshot/display identity/component suite: 59 passed, 28 subtests.
- Full regression: 961 passed, 113 subtests, 51.03 seconds.
- Log: `analysis/native-snapshot-generation-regression.log`.
- Release DLL rebuilt with clang `-shared -O2 -Wno-microsoft-goto`.
- Built and tracked DLL SHA256 both:
  `2cd8a33f3ebe1f62dfbefbb2535d2be21af313e70e9b83ec855f1aa3a77aceb8`.
- Diff whitespace checks passed.

The earlier ability overflow implementation remains: 48 inline entries plus
extended pairs, with existing C-to-Python tests through 4096 abilities per unit
and mixed groups. This audit did not find a 48-ability truncation bug.

No EXE was packaged, no running game was modified, and these results do not
constitute user gameplay acceptance or prove the entire long-term goal complete.
