# Bound hero intelligence, 2.0.4.23745

Protocol 45 registers `SetHeroInt` alongside `GetHeroInt` and adds op 153 after
the unit identity guard (136). The operation carries the hero component's data
address and full generation from the field snapshot. It validates the unit,
hero component, object-table wrapper and ownership, and rejects nonheroes.

One game-thread callback reads base and total intelligence, computes the base
needed for the requested total while preserving the current bonus, calls
`SetHeroInt(unit, base, permanent=1)`, and reads both values back. Identity is
checked after every native callback. A mismatch permits at most one correction
using the newly observed base/total pair; a second mismatch is an error. The
base calculation uses int64 arithmetic and rejects a negative base or int32
overflow. Targets retain the UI's existing integer range of 0–1,000,000.

The native UI and the compatibility UI use this operation without requerying
selection, scanning native functions, reading external hero memory, or sleeping
50 ms between calls. The compatibility field overlay preserves already-native
intelligence values and identity instead of issuing a separate legacy query.
Legacy candidates without a native binding retain their separate path.

Validation:

- Production C dispatcher and parser tests cover positive/negative bonuses,
  zero/maximum targets, a target below the current bonus, arithmetic overflow,
  nonheroes, unavailable setters, invalid hero ownership/generation, recycling
  during the initial read or setter, a changed bonus requiring one correction,
  persistent mismatch after two setters, and an exception in the setter.
- Both UI routes use one guarded command with process reads and fixed sleeps
  trapped. The field-editor test confirms intelligence does not enter the raw
  component-field writer. Missing hero identity cannot use legacy discovery.
- Full regression: 619 tests and 103 subtests passed (25.84 seconds). The helper
  DLL was compiled successfully; no live-game mutation or EXE test was performed.

An identity failure after a setter can report failure after that setter has
already run; this operation does not restore earlier intelligence or force
further writes onto a changed object. Gameplay semantics beyond these isolated
tests remain unverified. Skill-slot replacement and remaining legacy entry
routes still need work before the complete DLL-only goal can be claimed.

Application version remains 1.0.19 and the validated EXE is preserved.
