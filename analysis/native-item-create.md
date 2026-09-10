# Bound item creation — game 2.0.4.23745, app 1.0.19

Branch: `codex/v1.0.19-bound-item-create`, based on inventory batch commit
`17d07c4`. The last user acceptance still applies to delivered `1.0.19-c358dbc`.
Neither subsequent inventory change has user game-test acceptance yet.

## Change

`add_item_to_selected_unit` and `duplicate_selected_inventory_items` now use one
persistent selected-unit snapshot and one command containing guard 136 plus
operation 168. They no longer enter the controller process-memory context or
resolve the old Elephant handler set. The helper calls `UnitAddItemById` from
its persistent native table on the game thread. That table now has 55 required
names, matched in Python and C; protocol is 64 and the app stays 1.0.19.

For addition, the requested rawcode goes straight to the engine; there is no
search for an existing instance of that item. For duplication, the helper captures
the original inventory's types and full identities once, and only those original
types are duplicated. After each creation it checks the original unit, capacity
and occupied slots' handle, generation, object, type and wrapper. A changed
original stops subsequent callbacks. The existing duplication code already froze
rawcodes; this change adds full identity binding and removes its controller lookup.

New copies may fill initially empty slots. Creation uses the existing engine
semantics for full inventories and units without inventory; it does not force a
slot insertion or restore an item removed by a map callback. A zero creation
return or exception stops the operation. Earlier side effects remain in the game.

The result counts nonzero engine acknowledgments whose target/source checks
passed, and `arg0` carries the last returned handle. Failure details expose
`item_creations_acknowledged` and `last_created_handle`. These are not a guarantee
that every created item remains alive, in inventory, or on the ground: map code
can immediately consume, transform, merge or transfer it. The helper never
modifies or destroys a new return handle as guessed recovery. Duplication retains
the existing type-only behavior and engine default quantities.

## Evidence

`test_native_item_create.py` compiles the production helper and exercises its
binary command dispatcher with fake engine callbacks. Tests check full/sparse/
empty/zero-capacity inventories, creation of a type with no existing instance,
original identity replacement, slot swapping, invalid command shapes, missing
native handlers, refusal on the first or a later creation, exceptions and unit
replacement. They assert the exact number of callbacks and no speculative cleanup.
Further cases preserve acknowledgments when new copies are consumed, transformed
or merged while the original inventory remains valid.

Python tests cover both trainer classes, actual binary serialization, stale
selection avoidance through bound context, invalid input before selection, and
malformed acknowledgments. The bootstrap tests check the updated native table.
The final targeted run passed 107 tests in 8.84 seconds. These isolated tests do
not attach to the running game and do not prove engine/map behavior in every state.

Full regression on 2026-09-10 passed **1337 tests and 113 subtests** in 129.50
seconds, including 77 new creation cases. Local log:
`analysis/native-item-create-regression.log` (ignored by the repository).

Production DLL was rebuilt with clang (`-shared -O2 -Wno-microsoft-goto`,
user32/kernel32). SHA-256:
`82571e7013452e1463e2f2f4ddd04e8e9316a2199f480833ad2467cd2c0fda08`.

## Remaining goal

The five public bulk inventory operations are now on bound native commands.
Other public actions that still use the old selected-handle/handler lookup need
reachability review and migration. Full in-game acceptance of these inventory
changes remains separate from the offline tests. Delivered EXEs are untouched.
The current source audit identifies four public methods still directly calling
`_elephant_selected_handle`: unit scale, coordinate writes, taking control and
killing the selected unit's owner group. Their reachable behavior should be
reviewed together; merely finding that call is not proof of a heap scan.
