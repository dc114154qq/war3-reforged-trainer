# Bound all-hero-attributes action

2026-09-10. Branch: `codex/v1.0.19-bound-all-hero-stats`.
Application 1.0.19; helper protocol advances from 58 to 59.

## Finding

The user-confirmed e034231 package corrected the advanced editor's base
strength/agility fields. The separate all-attributes action still sent three
op-72 calls with only a JASS handle, no full-generation guard and no readback.
Its source did not establish identity across callbacks or prove the target
values were reached. The interrupted preceding turn only inspected this path;
it left no edits or running command to resume.

## Change

The public action now obtains the candidate and JASS handle together through
the existing native selected context (including bound multi-unit action
overrides), then submits one guard plus op 164. It opens no external memory
backend and performs no separate handler discovery.

Op 164 validates the full unit identity and captures its current hero component
data/full generation on the game thread. It prepares three internal requests
for the shared base-stat implementation. That implementation validates all
interfaces and identities before mutations, calls SetHeroStr/SetHeroAgi/
SetHeroInt with permanent=1, uses the corresponding base getters, and checks
all values again after the last setter. Identity failure or readback mismatch
stops further work and cannot return success. Controller results require the
correct operation and requested value.

The all-attributes target range remains 0..1,000,000,000, as before. The existing
editor op 163 still accepts only strength/agility and 0..1,000,000; base
intelligence is not newly exposed in the editor. No additional bootstrap
functions are needed. Later mutations can fail after earlier successful ones;
there is no rollback. Nonheroes without a valid hero component are rejected.

## Verification scope

Production C dispatcher tests use isolated fake game callbacks, with component
storage deliberately different from base query values. They cover all three
stats, zero and upper limits, missing third getter/setter, nonheroes, invalid
unit/component identity, component removal, exceptions, mismatched readback,
and a third setter changing an earlier stat. Prevalidation failures assert zero
setters; invalidating callbacks assert no later read/write on that target.

Controller tests run both trainer classes, the actual selection binding and
serialization; they forbid external memory setup, prevent selection changes
from replacing a bound batch target, reject wrong/incomplete responses and
reject invalid values before selection or mutation.

Initial tests caught the generic dispatcher rejecting op 164's zero handler
before it reached the implementation. That operation legitimately resolves
its functions inside the DLL; it was added to the handler-free dispatch list.
After the fix, the targeted all-stats/base-stats/selected-context suite passed
80 tests in 5.13 seconds.

Full regression: 1031 tests and 113 subtests passed in 53.87 seconds.
Log: `analysis/native-all-hero-stats-regression.log`. Diff whitespace checks passed.

DLL rebuilt with clang `-shared -O2 -Wno-microsoft-goto`; built and tracked
SHA256 both `d454f7239344930b0d3367f16ff1855e23aaeb132e4496e6ff595f281d915f58`.

These checks are code-level evidence. The previously delivered EXEs and their
user acceptance remain intact; they do not verify this new all-attributes path.
No game process was accessed or modified and no new EXE was packaged this turn.
