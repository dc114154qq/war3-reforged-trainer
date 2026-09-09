# Hero skill-slot replacement (protocol 46)

The native field editor now sends one guarded game-thread command (136 + 154)
for a hero skill-slot replacement. It binds the hero component data/generation
and the expected old slot rawcode from the DLL field snapshot. The native route
does not call the legacy component/template lookup, write process memory, sleep,
or change the user's selection. Skill-only edits now retain the real field
snapshot instead of constructing a placeholder that discarded component identity.

The transaction validates all five slot configurations/caches, rejects duplicate
slots and existing target abilities, and calls UnitAddAbility to resolve the
new ability from the current map's resources. No other unit must own that ability.
For a learned skill it carries the old level to the new instance, accepting the
engine's clamp to the new resource's maximum. For an unlearned slot it creates
and removes a temporary instance to validate the resource without learning it.
The config/cache stores precede the removal native's command-card refresh.

Unit and hero identity, ability full generation and object-table backlinks are
checked between engine calls. Direct memory checks after the last callback guard
the mutation targets. A failed replacement cleans up only its still-matching
new instance and restores slot values only when they remain owned by the
transaction. It never recreates a destroyed old instance. If the old ability is
already gone, it retains the new ability/config instead of deleting both.
The original error plus operation phase and cleanup error are returned.

Validation performed:

- Production C dispatcher tests cover resource creation without a template,
  unlearned and learned slots, level clamping, missing resources, duplicate and
  stale configurations, invalid component/ability identities, recycling during
  add/set/final validation, trigger-owned state, deletion failures and exceptions
  before/after deletion, and incomplete cleanup diagnostics.
- The actual Python field-editor entry uses the one-command route with external
  memory access and sleeps trapped. Field snapshot tests verify all five slot
  identities and removal of external write addresses.
- Full regression: **659 tests and 103 subtests passed** (27.29 s).
- Optimized helper DLL compiled successfully. Read-only live validation on
  PID 15028 bound **38 natives**, including all three newly required bindings,
  and read all fields for nine selected units. Two hero components returned all
  five bound skill slots; seven other units returned none. External field reads
  were prohibited by a failing facade. See `native-hero-skill-readonly.json`.

No live skill replacement or EXE gameplay test was performed. In particular,
resource-specific side effects and command-card appearance still require game
testing; isolated engine fixtures do not prove those semantics. A map trigger
or callback exception can leave a partial operation, which is reported rather
than forcing a rollback onto changed objects. Empty-slot insertion retains the
existing restriction; this command replaces a configured slot.

Application version stays 1.0.19. The validated EXE remains untouched. Remaining
legacy identity/summary entry points and other ability lifecycle routes still
need auditing before the whole DLL-only objective can be considered complete.
