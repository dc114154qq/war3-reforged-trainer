# Bound clone item execution — 2026-09-10

Branch: `codex/v1.0.19-bound-clone-items`, parent `506f0d3`.
Application version remains 1.0.19; helper protocol is 68 in Python and C.
The accepted 924dd59 EXE is preserved. No EXE or gameplay acceptance is added
by this development step.

## Problem and change

The previous clone guard pinned the source and created units. Inventory copying
still obtained items slot by slot after creation and used their JASS handles
across field callbacks. A map trigger could substitute a same-type item while
both units remained valid, or change an initially empty slot before enumeration.

The bound clone now captures all six source slots before CreateUnit. Each
nonempty entry includes the JASS handle, object address, full generation,
rawcode, wrapper address, wrapper tag and object-table backlink. It rejects
duplicate source identities and requires the native item resolver before
creation. The original inventory is rechecked after creation and before copying.

For each item, both the original source slot and the actual newly occupied
target slot are bound. The two objects and memberships are checked after field
and charge callbacks, alongside the unit guards. New items must have the right
rawcode, a valid object-table identity, a unique target slot, and no identity
alias with any source or earlier copied item. Target slots need not equal source
slots; the engine may pack a sparse source inventory differently.

The complete saved source inventory and all copied target items are checked
again before reporting success, including empty source slots and objects visited
earlier in the final pass. On failure, existing unit-identity cleanup rules still
apply. The code does not issue speculative RemoveItem calls for escaped objects.

The command still contains 15 operations and executes on one game-thread
invocation. The hot field-copy check inspects only the active source/target item
pair and at most two UnitItemInSlot queries. Six-slot passes run at preparation,
after unit creation and before success. There are no process scans or added host
round trips. Readable spans and executable resolvers are checked on initial
capture. Hot checks still resolve JASS/full identities and compare all links
each time, but avoid repeated VirtualQuery calls. They execute inside the clone's
existing SEH region; a newly unreadable object aborts there. Source and target
item pages are independently changed to PAGE_NOACCESS by production-dispatch
tests to verify this behavior, not just explicit RaiseException injection.

## Verification scope

The fixture compiles the actual production dispatch and models twelve distinct
item objects/wrappers, independent target fields/charges, source slot gaps and
reverse target-slot assignment. Tests cover heroes and nonheroes, all six slots,
sparse inventories, recycled unit generations, recycled item generations,
detached items, invalid wrappers, aliases, wrong types, duplicate slots, absent
resolvers, newly occupied source slots, and item detachment during later ability
copying. Stale item field/charge access increments an independent fixture error
counter; every dispatch asserts it remains zero.

Item generation/wrapper faults are injected at every callback position after
the relevant identity is known. Membership faults are injected in creation and
item-copy callbacks: UnitItemInSlot is modeled as a read-only membership query,
not as a map-triggering mutation. Identity cannot be pinned before a creation
native returns. Simulated callbacks do not prove all actual map behavior.

Initial unit fault regression passed 30 tests in 26.10 seconds. New item fault
tests passed 15 tests in 37.68 seconds. The full/sparse/reverse-slot cases and
creation rejection tests then passed 11 tests in 3.80 seconds. The expanded full
regression passed **1644 tests and 113 subtests in 147.45 seconds** before the
hot-path optimization. The added unreadable-page cases then passed **2 tests in
5.72 seconds**. The final optimized full regression passed **1646 tests and
113 subtests in 121.27 seconds**. Local ignored log:
`analysis/native-clone-items-final-regression.log`.

Production DLL SHA-256:
`4d2391e56bc3f993cb1d0509d3b1564e4b10f874713f9fa6d0d57cdba2795b8e`.

`analysis/measure-clone-item-guards.py` measures the compiled production guard
in isolation with synthetic callbacks/object tables: seven samples, 2,000 checks
each. It verifies zero membership queries for unit-only checks and exactly two
for the active item pair. Before optimization the medians were 9.1974 microseconds
for units and 39.47255 microseconds for units plus items. This exposed repeated
VirtualQuery work in the callback path. Final medians were **0.0147 microseconds
for units and 0.0974 microseconds for units plus items**, with raw samples in
`analysis/native-clone-item-guard-cost-fast.json`; pre-optimization samples are
in `analysis/native-clone-item-guard-cost.json`. These are warm synthetic lookup
costs; real game resolvers, cold memory,
creation/copy natives, command binding and IPC are excluded. Do not quote these
figures as end-to-end game latency.

## Remaining work

Clone ability enumeration still needs its own full object identity/membership
protection. The existing behavior of skipping an ability when its engine add
call returns false also needs explicit handling rather than implying a complete
copy. These tests do not establish live latency, gameplay acceptance, or atomic
rollback of arbitrary map-trigger side effects (including items moved by a
trigger). Keep the broader migration goal active and preserve this work.
