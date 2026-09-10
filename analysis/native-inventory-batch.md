# Bound inventory batches — 2.0.4.23745 / app 1.0.19

Development branch: `codex/v1.0.19-bound-inventory-batch`.
The user's 2026-09-10 acceptance applies to delivered package `1.0.19-c358dbc`.
This subsequent inventory change has not been tested by the user in game.

## Problem and implementation

Clear inventory, set all item quantities and drop inventory previously resolved
selection through the old controller path and interleaved slot lookup with each
mutation. A map callback could replace a later slot, causing subsequent work to
target the replacement rather than the inventory originally selected.

These three public methods now capture the persistent native selected identity
and submit guard 136 plus operation 167 as one game-thread command. The helper
uses the persistent native table and existing object-table inventory reader,
with no controller process-memory context, heap scan, sleep or per-item command.
Protocol is 63; application version stays 1.0.19.

Before mutating, the helper captures all six slots and inventory capacity. After
each affected item it validates the original unit, capacity and every slot's
JASS handle, full generation, object address, rawcode and wrapper address.
Removal/drop must leave the expected slot empty; quantity writes must read back
the requested value for every item already processed. Replacements, transfers,
unexpected insertion, identity changes and engine refusal stop the batch before
the next mutation. Empty slots are skipped. There are at most seven inventory
snapshots for six occupied slots, all within one command.

`inventory_verified` in failure details counts fully verified steps. A failed
step may already have mutated the game; preceding changes are not rolled back.
Removing an item verifies inventory membership, not an independent world-state
proof of destruction. A map that rearranges its inventory during a callback can
therefore cause a deliberate failure instead of the batch following new slots.

## Validation design

`test_native_inventory_batch.py` compiles the production helper into an isolated
test DLL and executes its command dispatcher with controlled engine callbacks.
Cases include full/sparse/empty inventories, zero inventory capacity, quantity
limits, valid later-slot replacement, slot swapping, new insertion, changed unit
and item identities, invalid wrapper backlinks, wrong quantity readback,
modification of an earlier completed item, engine refusal and exceptions.
Tests assert exactly which item callbacks ran and that later items were untouched
after a detected error. Invalid command shapes and missing handlers cannot mutate.

Python routing tests cover both trainer classes, bound selection reuse, binary
serialization, argument rejection before selection, and malformed acknowledgments.
The test setup uses local fake objects; it does not attach to the running game.

Validation completed on 2026-09-10: the full regression passed **1260 tests and
113 subtests** in 106.80 seconds, including 91 new inventory batch cases.
Log: `analysis/native-inventory-batch-regression.log`. The first targeted run
caught an incorrect struct constant name in six Python serialization tests;
that test code was corrected before the successful full regression.
Production helper was rebuilt with clang (`-shared -O2 -Wno-microsoft-goto`,
user32/kernel32); tracked DLL SHA-256:
`a832169ccc13ca4c298e3d966b51a1d110de727ba5a9d34383ff7691ec06454a`.
No EXE was packaged and no running game was attached during this work.

## Scope remaining

Inventory addition and duplication still require separate review. This change
does not establish acceptance of those operations or complete the overall DLL
migration goal. Existing delivered EXEs and the accepted attribute notes are kept.
The duplication implementation already freezes rawcodes before creating copies;
its remaining issues are the legacy selection path and missing full identity
checks across creation callbacks, rather than dynamically following new slots.
