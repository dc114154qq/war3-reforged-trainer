# Component field writes, 2.0.4.23745

Protocol 44 appends four component generations to the op 147 response (346
qwords total). Displayed writable component fields retain the data address and
full generation from this response. They no longer carry an external write
address or mirror writes.

Op 152 supports a fixed build-specific set of 54 field IDs: armor and armor
type, hero skill points/growth/XP/base strength/base agility, movement speed,
17 writable fields for each attack, and the five hero learnable/requirement
entries. Raw ability IDs, intelligence's special setter, read-only attack
fields and arbitrary offsets are not accepted by this operation.

For component fields, the helper checks the owning unit's component pointer,
component generation and owner backlink, and its object-table wrapper tag,
generation, owner and data pointer. Second-attack fields require a valid second
record. Unit fields bind directly to the complete unit identity. The helper
rejects unknown fields, non-finite reals, oversized payload values, duplicate
addresses and unavailable/non-writable memory. It validates the whole batch
before storing any values, then returns the written bits in the same callback.
The game APIs are not called between those stores and readback.

The Python field editor validates all requested values before submission and
uses batches of at most 15 fields plus op 136. Requests larger than one batch,
or requests combining component fields with other operation types, are not a
single atomic transaction; earlier successful batches are not rolled back if
a later batch fails. Each batch still pins the original unit and component
identities. This does not add game-side refresh semantics beyond the prior
direct field writes.

Validation:

- Production C dispatcher exercises all 54 accepted field IDs and verifies the
  actual memory values and binary readback. It also rejects an invalid second
  field without writing the valid first field: stale generations, unknown or
  read-only fields, NaN, removed components, recycled units, invalid owners,
  wrong operation kinds, bad pointers, missing second attack and oversized
  values. Duplicate addresses are rejected before writing.
- The Python field-editor test submits multiple fields in one guarded command
  with no process-memory calls; non-finite inputs fail before submission.
- Full regression: 598 tests and 103 subtests passed (24.08 seconds).
- Read-only verification with the rebuilt DLL in PID 15028: 9 selected units
  (2 heroes, 7 nonheroes), complete field reads with external-memory access
  trapped, and 20 or 37 component fields per unit carrying native identities
  and native write capability. See `native-component-write-readonly.json`.
  No game mutation or EXE test was performed.

Version remains 1.0.19 and the validated EXE is preserved. The complete goal is
still open: special hero/skill operations and legacy entry/recovery routes need
their remaining audit and migration, and gameplay behavior of these writes has
not yet been tested by the user.
