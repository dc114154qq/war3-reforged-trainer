# Base strength/agility use game setters and display readback

2026-09-09. Branch: `codex/v1.0.19-native-hero-base`.
Application remains 1.0.19; C/Python native protocol 58.

## Change

The verified disassembly in `native-hero-stat-semantics.md` established that
GetHeroStr/GetHeroAgi(false) do not simply return the component locations that
the field editor was writing. This patch routes base strength and agility to
SetHeroStr/SetHeroAgi, with `permanent=1`, followed by the same false/base getter
used in the display. The requested displayed base value must match the readback.
Raw component op 152 IDs 7 and 8 now fail without stores, so they cannot silently
retain the old behavior. The two setters join the initial native table bootstrap.

Op 163 carries stat index (0 strength, 1 agility), hero component data/full
generation and target. It accepts one or two distinct stats, validates the full
batch before mutation, and checks unit and hero component identity across every
engine callback. Both fields share one game-thread callback. After setting both,
both getters are checked again to detect a second setter changing the first stat.
Unexpected readback returns an error; there is no blind retry or delayed sleep.

The controller validates targets as integers 0..1,000,000 before any mutations,
groups the two stats into their dedicated native batch, and preserves result
order for mixed stat/component requests. Ordinary component fields retain op
152. Base intelligence and total strength/agility remain read-only. Intelligence
total keeps its existing dedicated setter. UI notes describe the new base-stat
setter and readback behavior, with actual writability still determined by the
bound component.

## Validation scope

`test_native_hero_base.py` compiles the production C dispatcher with isolated
engine callbacks. The model uses `query = storage + calculated - excluded` and
implements the setter's verified delta adjustment. Positive and negative offsets
exercise a difference between stored bytes and displayed values; direct stores
of the target would fail these value assertions.

Coverage includes strength only, agility only, paired writes, zero/upper bounds,
nonheroes, unavailable second setter, duplicate/invalid operations, invalid
hero ownership, unit/component recycling, component detachment, setter exception,
incorrect getter result and a second setter altering the first result. Invalid
batch/initial-read failures are checked for zero setters; post-set identity
failures stop without accessing invalid targets again.

Python tests run the real field router and command serializer, enforce one
paired command without external memory accesses/sleeps, preserve output order
when mixing ordinary fields, and reject invalid second values before the first
write. Existing component tests now assert raw IDs 7/8 are rejected. Bootstrap
tests use other optional natives because strength/agility setters are now
required at initialization.

The tests model engine callbacks; they are not execution of Warcraft's full stat
implementation, and cannot replace the user's live check of the corrected path.
On failure after an earlier successful mutation, values are not rolled back.
Mixed native batches are likewise not an all-or-nothing transaction.

New DLL SHA256:
`355e99543ef17a371a72c17b17e81ad0733b5ee6f5d439e1ce45ba0594bde1d5`.
Compiled with clang `-shared -O2 -Wno-microsoft-goto` and matched to the tracked DLL.
Previously delivered 047b4e5 and b93ee58 EXEs remain unchanged. No game process
was accessed or modified during development.

## Executed checks

- Hero base + table bootstrap suite after updating the optional-native test:
  65 passed in 8.11 seconds.
- Full suite: 995 passed, 113 subtests passed, one localization failure in
  106.47 seconds. Log: `analysis/native-hero-base-regression.log`.
- That failure exposed missing English translations for the previous notes
  additions as well as the new base-stat notes. Added all nine missing mappings;
  no native/controller behavior changed in that correction.
- Localization + hero base + hero fields rerun: 47 passed in 6.12 seconds.
  The full suite was not repeated after a translation-only correction; the
  earlier failing full-run log is retained as evidence, not described as green.
- DLL compilation and whitespace checks passed.

The user has not tested this new setter path. Do not apply the prior 047b4e5
acceptance to this change, or claim that the exact reported downward difference
has been verified fixed in their game. This source change addresses the proven
semantic mismatch and needs a separate future gameplay check.
