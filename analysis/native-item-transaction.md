# Item replacement transaction, 2.0.4.23745

Protocol 43 introduces op 150 with an op 151 slot/item identity descriptor after
op 136. The descriptor pins the item shown to the user (JASS handle, full
generation, object and rawcode), including an explicitly empty slot. Python
rejects changes during targeted refresh or inventory readback before submission.

In one game-thread callback the helper:

1. Checks the unit, usable slot count, full item identity and all six slots.
2. Creates the replacement from the map resource using `CreateItem`, before
   removing the old item. Creation refusal leaves the old item in place.
3. Detaches the old item with `UnitRemoveItem`, without destroying it, and
   verifies the target became empty without changing the other slots.
4. Calls the existing exact-slot internal add function with the validated unit
   object, item object, slot, notify=1 and check_mode=0. It validates membership
   and identity again before destroying the retained old item with `RemoveItem`.

On failure before destruction of the old item, recovery detaches the newly
placed item only if it still has the captured identity. It restores the old
object only if the unit is valid, the slot is empty, and `IsItemOwned` says the
old item has not been claimed elsewhere. It cleans up a newly created object
only if its full identity remains valid and it is unowned. Invalid/recycled
objects and objects claimed by map triggers are left untouched. Errors after
old-item destruction cannot roll back; the replacement is retained rather than
removed in an impossible restoration attempt. The original error and recovery /
cleanup error codes are reported separately.

Evidence for detachment behavior: captured runtime `.text` in
`analysis/native-bootstrap-20260907/module-text.bin`, matching the build used by
`tools/native-call-contracts-23745.json`. The internal `UnitRemoveItem` target at
RVA 0x1177da0 calls the inventory removal routine at 0x61a3a0 and then positions
the item through 0x117f4e0. Previously op 41 followed this call with explicit
item destruction through vtable entries 0x108 and 0x268. The exact-slot target
at RVA 0x1177560 reads the fifth argument for its eligibility check and calls
0x6180e0 with the requested slot. The current native path obtains this target
from the verified native handler, using instruction-boundary decoding, and no
longer discovers the separate internal create/remove functions.

Validation:

- Full regression: 529 tests and 103 subtests passed (20.29 seconds).
- `test_native_inventory_transaction.py` compiles and runs the production C
  dispatcher and binary parser. It exercises creation refusal, wrong resource,
  placement refusal, detach refusal, unit or item recycling at successive
  callbacks, a trigger taking the target slot, restoration refusal, an add that
  reports failure after placing an item, missing functions, a stale descriptor,
  ownership transfers, changes to another slot, and a unit change during final
  destruction. Empty-slot creation and failure cleanup are also covered.
- Python tests reject a changed item during both refresh and metadata readback;
  the mutation helper is never called. They also verify the native command uses
  the JASS unit handle and a complete item descriptor without HP/MP properties.
- Current-game read-only verification with the rebuilt protocol-43 DLL:
  PID 15028, 9 selected units, all six slots returned, all five required item
  handlers found and the exact-slot call contract resolved. See
  `item-transaction-readonly.json`. No live mutation or EXE test was performed.

Version remains 1.0.19; the validated EXE is unchanged. Generic component writes
and some legacy/recovery routes still need migration and validation. Map triggers
can prevent safe restoration; this change does not claim rollback is always
possible or that the overall DLL-only objective is complete.
