# Bound clone unit execution — 2026-09-10

Branch: `codex/v1.0.19-bound-clone-units`, parent `32f8105`.
Application version remains 1.0.19. The accepted 924dd59 EXE is preserved.
This stage changes source and the development DLL; it does not deliver an EXE
or claim new gameplay acceptance.

## Change

Selected-unit cloning now sends full original source identity (op 136), followed
by the clone and its 13 argument descriptors in one command. Python requires
all 15 results, the clone operation kind, a nonzero target, and no errors.
Protocol is 67 in both Python and C. The old 14-operation C form remains for
compatibility, but the current selected-unit entry point always uses the bound
form and never downgrades to it.

The DLL validates the source before execution, captures the created target's
full identity, and checks both after each engine callback. Nested source getters
are checked before the enclosing target setter executes. Hero attributes,
inventory fields/charges, abilities, and vitals share this validation. These
checks stay inside the same game-thread command and add no host round trips or
memory scans. NaN/out-of-range coordinates fail before engine execution.

Source identity changes abort the operation. Cleanup removes the created target
only while its captured identity still matches. Reused targets, unverifiable
creation results, and a creation result aliasing the source are never removed.
The bound ability-copy path no longer swallows an identity exception or proceeds
after a level readback failure.

## Offline validation

`test_native_clone_unit_guard.py` compiles and executes the production C dispatch
with synthetic engine callbacks. All eight combinations of hero/nonhero,
inventory/ability content, and preserve-owner mode are exercised. Fault injection
changes source or target generation at every callback position after identity
is known, asserting no further engine calls use the invalid identity and checking
cleanup behavior. Separate cases reject stale initial identity, NaN coordinates,
wrong source type, source-alias/unverifiable creation results, and failed ability
level readback. Item integer, real, boolean and charge copying is exercised.

Python tests use actual serialization, bind the original selection even if it
changes during handler lookup, and reject truncated, erroneous, wrong-kind or
empty clone results. External memory and legacy preparation are forbidden by
the fixtures.

The initial targeted run passed 66 tests/16 subtests and exposed one obsolete
source-string assertion. The removed assertion is superseded by executing an
actual wrong-source-type command. The expanded targeted run then passed 77
tests/16 subtests in 6.28 seconds, before adding preserve-owner fault cases and
malformed-response tests for the full regression.

Full regression: **1615 passed, 113 subtests passed, one failed in 94.34 seconds**.
The remaining failure was an older explicit-creation fixture still mocking
`_elephant_handlers` after parent 32f8105 moved creation to
`_query_native_table_handlers`. Updating that fixture (and explicitly forbidding
external memory) required no production-code change. Final affected-file
regression: **118 passed and 16 subtests passed in 12.02 seconds**. This covers
the previously failing test and all clone additions; no failures remain known.
Logs: `analysis/native-clone-unit-guard-regression.log` and
`analysis/native-clone-unit-guard-final-targeted.log` (ignored local evidence).

Production DLL rebuilt with clang -shared -O2 -Wno-microsoft-goto,
user32/kernel32. SHA-256:
`cba9966aa0fc76e8916b427c2cf764c560ed3b870dd513a6556470a3cdc02d90`.

## Remaining scope

These tests prove unit identity handling in the compiled dispatch, not game
engine semantics or measured live-game latency. Identity cannot be captured
until CreateUnit returns. Item and ability objects inside valid units still
need their own full-identity and membership audit across callbacks; unit guards
alone do not cover their replacement. The existing behavior of skipping an
ability whose engine add call returns false is also unchanged. Continue this
work rather than marking the broader migration complete.
