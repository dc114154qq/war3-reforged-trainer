# Native hero level and skill-point transactions

2026-09-10. Branch `codex/v1.0.19-bound-hero-progression`.
Application remains 1.0.19; native protocol 62.

## Change

Hero level modification previously performed separate unguarded controller/game
calls for current level, XP suspension, setter/strip, restoration and readback.
Skill-point addition used only a JASS handle and trusted its boolean return.

The public methods now capture one native candidate/JASS pair and submit a
single guard plus op 165 (level) or 166 (skill points). Both support the existing
per-unit batch override and need no external memory backend. Five additional
native names join bootstrap: SetHeroLevel, UnitStripHeroLevel, SuspendHeroXP,
IsSuspendedXP and UnitModifySkillPoints. These use the pinned build's table.

Both operations capture the hero component on the game thread and validate its
data/full generation, wrapper and owning unit across callbacks. Nonheroes are
rejected. Level retains range 1..100000; skill delta retains 1..1000000.

### Levels

The DLL queries current level, raises through SetHeroLevel or lowers through
UnitStripHeroLevel, then checks the final level. For a raise with XP suspended,
it records cleanup responsibility *before* calling SuspendHeroXP(false),
verifies that unpause succeeded, and restores suspension before final level
readback. If unpause or the setter changes state and then raises, cleanup still
runs if unit and hero identity remain valid. An already-restored flag is left
alone. A changed/invalid identity prevents restoration onto another object.

Restoration failure is carried separately as `xp_restore_error`; the original
operation error remains primary. If restoration itself changes the level, final
level readback catches that mismatch. No-op and lowering do not toggle XP.

### Skill points

The DLL reads the bound hero component's existing skill-point field at +0x104,
checks signed int32 addition for overflow, calls UnitModifySkillPoints, verifies
the component identity again, and compares the actual field to the expected
sum. It does not trust a successful boolean alone. No raw component store or
controller sleep is used.

## Verification

Production C dispatcher tests cover raise/lower/no-op, initial XP on/off, bounds,
nonheroes, missing functions, wrong identities, invalidating query/unpause/setter
callbacks, exceptions after temporary state mutation, failed/no-op restoration,
restoration that changes level, strip refusal/mismatch, skill-point refusal,
wrong increments, overflow, removal and exceptions. They verify no mutations
on initial failures and no restoration onto recycled identities.

Controller tests cover both trainer classes, actual selection binding and
serializer, one native command, batch override preservation, invalid input
before selection, and incomplete or wrong acknowledgments.

Targeted suite: 132 passed in 7.43 seconds.
Full regression: 1169 tests and 113 subtests passed in 63.61 seconds.
Log: `analysis/native-hero-progress-regression.log`. Diff whitespace checks passed.
DLL compiled with clang `-shared -O2 -Wno-microsoft-goto`; built and tracked
SHA256 both `295d399d254c0793852404f4edff4d9aebe8b693d35059d7a3c4e48cbe79f3d6`.

This is isolated code verification. No game process was accessed or modified,
and no new EXE was packaged. User acceptance of e034231 remains scoped to that
package. Later native transactions may partially mutate before a failure;
there is no level/skill rollback. XP restoration is attempted once, not retried
indefinitely. A flag changed away and back by unrelated map logic cannot be
distinguished using a boolean alone.
