# Native field route audit — app 1.0.19 / game 2.0.4.23745

Branch `codex/v1.0.19-native-field-routing`, based on 3ee0284. Latest accepted
gameplay artifact remains 1.0.19-924dd59; this step changes Python validation only.

## Finding and fix

The generic field dispatcher previously checked writability before batching
basic/component writes, but checked for an unsupported native setter only in
the final dispatch loop. A malformed or future descriptor could therefore cause
an earlier basic write before failure; a writable non-native descriptor paired
with a native candidate could even fall through to external address writes.

For a native candidate, the entire request must now have native_write and a
recognized route before any mutation: basic field, component field with complete
component identity, intelligence/hero skill with hero identity, inventory slot
or quantity. Missing routes fail before earlier setters. Non-native legacy
private callers retain their prior behavior; this is not removal of legacy code.

The production C field-dispatch tests now examine every exposed writable field
across available/absent components, checking native route, zero write address,
no extra raw-address writes and required identities. Existing actual setter
tests exercise component destinations, hero skills, item quantities/replacements
and mixed-field identity changes. New tests inject malformed descriptors after
a valid HP request and require no mutation or external memory call for either
trainer class. Targeted regression: **180 tests passed in 10.90 seconds**.
Full regression on 2026-09-10: **1500 tests and 113 subtests passed in 97.97
seconds**, including the preceding read-entrypoint changes. Local ignored log:
`analysis/native-field-routing-regression.log`.

## Remaining real dependency

Do not blindly remove the external memory context from generic public writes.
The native branch of `_set_inventory_slot_item_via_native_handler` still calls
`_rel32_calls_in_function`, which reads game code and regions through ProcessMemory
to locate the internal exact-slot adder. This is a bounded code read, not a
process-wide heap scan, but it is an actual controller dependency.

The existing captured 23745 contract was decoded offline: UnitAddItemToSlotById
RVA 0xcaae00 contains eight calls before return; the final E8 at offset 0xcf
targets RVA 0x1177560. These values match the stored contract's final target.
This identifies the next migration step: validate and resolve that contract in
the DLL before calling the existing guarded replacement transaction. Merely
hardcoding the destination without current image/code validation is insufficient.

No DLL rebuild, protocol change or EXE delivery is needed for this Python guard.
No current game process was read or modified. The overall goal remains active.
