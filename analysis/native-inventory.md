# Native inventory snapshot (2.0.4.23745)

Protocol 42 adds a six slot inventory response to the game-thread unit-field
batch. It calls `UnitInventorySize`, `UnitItemInSlot`, `GetItemTypeId`, and
`GetItemCharges`, then resolves each item through the item object table. Full
item identity, item wrapper tag, unit ownership, rawcode and slot membership
are checked before and after the response is published. Python does not scan
item objects or read slot records when this response is present.

The same native batch supplies item handles, full handles, object addresses,
rawcodes, charges, mirror rawcodes and ability rawcodes. Native item and charge
fields are marked writable only when the item identity is complete. Empty slots
remain explicit six-slot results.

Validation includes duplicate objects, stale item generations, changed slots,
invalid item objects, incomplete payloads and absent inventory components. Full
regression after the protocol extension: 453 tests and 108 subtests passed.
The final DLL was also exercised read-only in the running 2.0.4.23745 process:
11 selected units returned six slots each; heroes had six occupied slots, all
nonheroes had empty slots in the captured state. No mutation was performed.
The validated 1.0.19 EXE remains untouched.

Item replacement and some item field operations still discover internal item
functions from the native handler code and need the same complete identity
transaction work. The overall DLL-only goal remains in progress.
