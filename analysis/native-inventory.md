# Native inventory snapshot (2.0.4.23745)

Protocol 42 adds a six slot inventory response to the game-thread unit-field
batch. It calls `UnitInventorySize`, `UnitItemInSlot`, `GetItemTypeId`, and
`GetItemCharges`, then resolves each item through the item object table. Full
item identity, item wrapper tag, rawcode and the owning unit's slot membership
are checked before and after the response is published. Python does not scan
item objects or read slot records when this response is present.

The same native batch supplies item handles, full handles, object addresses,
rawcodes, charges, mirror rawcodes and ability rawcodes. Native item and charge
fields are marked writable only when the item identity is complete. Empty slots
remain explicit six-slot results.

The initial protocol extension passed 453 tests and 108 subtests. At that point
many inventory lifecycle tests still exercised the previous external reader;
that result alone did not establish the same coverage for op 149.
The final DLL was also exercised read-only in the running 2.0.4.23745 process:
11 selected units returned six slots each; heroes had six occupied slots, all
nonheroes had empty slots in the captured state. No mutation was performed.
The validated 1.0.19 EXE remains untouched.

Protocol 43 adds a guarded replacement and recovery transaction; see
`native-item-transaction.md` for its checks, evidence and limits. The overall
DLL-only goal remains in progress.

## Routing audit, 2026-09-09

Removed the HP/MP property-address condition from native inventory routing and
from the internal item-operation unit guard. A native unit without those
properties must use the same DLL route. Removed the unused `inventory_native`
flag and the old native external-memory reader; a missing or failed DLL response
propagates an error instead of falling back to external slots or heap scans.
Replacement readback now queries native inventory capacity without calling the
external component locator. Internal function discovery and the replacement
mutation sequence still require further work; this is not full transaction
rollback protection.

`test_native_inventory_dispatch.py` compiles the production C dispatcher and
passes its real op 149 response through the Python binary parser and inventory
entry point. It covers empty and partially usable inventories, six occupied
slots, duplicate identities, invalid pointers, wrong tags/types, item and unit
recycling, changing slots/capacity, missing native functions, high and signed
quantities, and malformed payloads. Each case runs with the registration flag
both set and cleared; candidates have no HP/MP properties. Failed dispatches
publish no partial payload, and no external-memory reader or scan is called.
Replacement readback tests likewise trap external component reads.

Full regression after this audit: 500 tests and 103 subtests passed. Older
external-reader tests were replaced by production-dispatch tests; counts are
not a claim of gameplay coverage. No DLL binary/protocol change, EXE packaging,
or live-game mutation was performed in this audit.
