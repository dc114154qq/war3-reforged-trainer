# Bound world effects, protocol 56

The Python world target/point entry now sends one unit identity guard and op
162 containing only rawcode, mode and success limit. It no longer discovers
internal ability functions, reads vtables, creates/removes abilities through
the old path, or transmits callback/resolver addresses. Four group/player
natives were added to the exact-build persistent table (47 required natives).

The DLL captures at most 100000 enumerated entries across 24 players, records
each target's JASS handle and full object-table identity, and deduplicates by
a bounded open-addressed handle table. Conflicting identities for a duplicate
handle abort capture. It destroys the group before any effect is invoked;
spawned units cannot extend that invocation's target set. The capture storage
is allocated before ability creation and freed on success/error.

After capture the DLL finds or resource-creates the source ability. Each
target is checked against its captured generation, current type/life/owner,
enemy relationship and coordinates. Targets removed/recycled in earlier
callbacks are skipped. Source unit and ability changes stop later effects;
source player ownership is checked too. The source ability vtable supplies
the target or point callback inside the DLL. Original internal target-pointer
versus point-argument conventions are preserved. Temporary ability cleanup is
identity-bound and runs after exceptions as well as successful execution.
Group destruction is attempted once, even if the destroy callback throws.

Tests: 29 world-effect tests passed (3.38 s), running the production dispatcher
with isolated fake engine groups and object tables. They cover source/target
identity changes, dead/friendly filtering, duplicates across group/player
enumerations, success limits, both callback layouts, callback exceptions,
source owner changes, target invalid coordinates, empty groups, creation and
binding failures and pointer-free Python routing.

Full regression: **932 tests and 103 subtests passed** (53.53 s), recorded in
`analysis/native-world-effect-regression.log`. Rebuilt DLL SHA256:
`657d59a7dea43ea8bfb425416246e8cfb55d2cdc5dcd34cf0b352a3c221709e5`.

Known scope/limits: this is one synchronous game-thread callback, retaining
the old 110-second upper deadline and 100000-entry bound; an unusually large
map can still monopolize the thread, and the worst-case limits have not been
performance-tested. "Success" counts returned callbacks, not visual or
gameplay effect readback. Saved target identities prevent address reuse but
do not promise an atomic snapshot of every player's allegiance. Older op106
remains in the C dispatcher for now, although this entry no longer calls it.
Unknown creation/cleanup outcomes are reported, never guessed away.

Application version remains 1.0.19. No game mutation or application EXE build
was performed, and no user gameplay acceptance is asserted. A whole-project
reachability audit and validation in actual game states remain outstanding.
