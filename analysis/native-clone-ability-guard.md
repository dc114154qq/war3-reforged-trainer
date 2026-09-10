# Bound clone ability execution — 2026-09-10

Branch `codex/v1.0.19-bound-clone-abilities`, parent `1d7b479`.
App version stays 1.0.19. Python and helper protocol advance together to 69.
The accepted 924dd59 EXE remains the gameplay baseline until a later package
receives its own user feedback.

## Change

Previously, cloning enumerated source abilities after creating the unit and
copying items, and used a rawcode across add/level callbacks. A same-type ability
replacement could evade unit identity checks. UnitAddAbility returning false was
silently skipped, even when the target lacked that skill.

Bound cloning now freezes the complete source ability list before CreateUnit,
including each JASS handle, object, full generation, wrapper/class tag, rawcode,
source index and ownership backlinks. Enumeration allows 256 entries and probes
the next index to reject overflow. Duplicate object identities are rejected;
duplicate rawcodes remain supported because item-provided skills may repeat.
Their individual source identities remain checked, while the engine's rawcode
add/level APIs are invoked once per distinct nonessential rawcode.

The list is rechecked after creation, before copying abilities and before success.
A final object-table pass covers units, saved items and saved abilities after all
callback-based membership queries, so later skill queries cannot invalidate an
already checked item unnoticed. This last pass adds no membership callbacks.
During ability copying, source membership is bound by index and target membership
by the game's rawcode lookup. Object-table and ownership checks follow each
callback. The existing five essential component rawcodes and nonpositive-level
handling are retained. Existing target abilities are leveled without re-adding.
Missing target abilities are created through UnitAddAbility, then the actual
lookup and level are verified. An absent result is a failure even if the native
returned true; a valid actual result is accepted even if it returned false.

Temporary identity arrays use one bounded heap allocation per bound clone, freed
on success, validation failure or a caught exception. Active identity checks use
the same direct object-table approach as the previous item work, inside SEH;
readable spans and executable resolvers are validated on initial capture.
BlzGetUnitAbility comes from the already-required persistent native table. The
command remains 15 operations with no new host round trip or process scan.
The legacy unbound C form remains unchanged; current Python selected-unit
cloning always sends the bound form.

## Tests and limits

The production C fixture supplies independent source/target ability objects and
wrappers. Tests cover heroes and nonheroes, multiple skills, exactly 256 and
overflow, essential abilities, duplicate rawcodes and duplicate objects, existing
target skills, missing natives, mismatched IDs, source list changes during
creation, native add acknowledgments that disagree with actual lookup, level
readback failure and late target recycling. Source and target ability pages are
independently made unreadable to exercise actual Windows SEH.

Generation, owner, class and membership faults are injected at each relevant
callback position after identity capture. Read-only membership queries are not
modeled as map-triggering mutations. Independent fixture checks reject stale
ability native access and require all tracked helper heap allocations to be
released after every command, including forced allocation failure.

The initial fixture lacked native table-name initialization, causing a harness
access violation before dispatch. Initializing the synthetic table fixed that
fixture error. The existing clone smoke cases then passed 14 tests; new functional
cases passed 22 tests. The expanded ability suite passed **39 tests in 13.47
seconds**, including callback faults and allocation checks. Full regression and
package verification are recorded with the eventual delivery. The first full
run passed 1677 tests/113 subtests and failed eight existing item generation/tag
fault cases: those faults occurred in the new final ability queries after the
item pass. The combined final object-table check fixes this integration gap;
the existing tests are retained unchanged.

Final full regression passed **1685 tests and 113 subtests in 143.15 seconds**,
including all eight earlier failures. Local ignored log:
`analysis/native-clone-abilities-final-regression.log`.

Production helper SHA-256:
`8e633416819cf5515822279ec712bbf724ce8f64dbe1b699678c8dab4906c130`.

These are offline execution tests. They do not prove every real map's native
behavior, live latency, or rollback of arbitrary map-trigger side effects.
They also do not claim to copy arbitrary ability instance fields: this operation
continues to copy learned levels through the engine APIs. Preserve broader DLL
migration scope, including full field editing and the user's gameplay checks.
