# DLL-owned inventory slot resolver

Branch `codex/v1.0.19-native-slot-resolver`, based on 7ea59fa. App 1.0.19,
game 2.0.4.23745, helper protocol 66. Last user acceptance remains the independent
1.0.19-924dd59 EXE. No new EXE delivered or running game accessed in this step.

## Removed controller dependency

The native inventory-slot replacement path previously queried UnitAddItemToSlotById
in Python, opened external memory, disassembled its code and submitted the last
of eight call destinations. Python now sends op 150 with handler zero alongside
the original unit/item identities and op 151 context. The DLL resolves the exact
slot adder before any item creation or mutation. Existing nonzero-handler private
commands retain their previous behavior; the public native path sends zero.

`war3_resolve_slot_add` obtains the current game context using the existing
validated bootstrap, hashes the native name and queries only its table bucket.
That query checks handler RVA, native signature and the initial code fingerprint.
The slot-specific resolver additionally checks the complete 0xe4-byte instruction
prefix through the first RET, hash f54fceaf4a2f036a, from the existing captured
contract. Only then does it decode the E8 at offset 0xcf and require destination
image+0x1177560 and executable memory. The handler must be image+0xcaae00.
No heap scan, injected cache address, instruction-boundary guessing or external
process reads are used. Code/table mismatches fail before creation. Image checks
are inherited from bootstrap; this change does not broaden version support.

The resulting function pointer feeds the existing transaction for exact-slot
placement, full unit/item generation checks, retaining the old item until verified
placement, and recovery that never overwrites a slot claimed by map callbacks.
It does not replace that transaction with UnitAddItemById or a raw type overwrite.

With this last inspected dependency removed, generic current-selection and pinned
field-write entrypoints no longer open an external write-memory context. Their
native route preflight from 7ea59fa remains in force. The private legacy branches
still take ProcessMemory when explicitly used; no claim of deleting all legacy
code is made.

## Verification

`test_native_slot_resolver.py` compiles the production helper with existing fake
inventory/transaction callbacks. A separately allocated, relocated synthetic image
contains the captured native code, a synthetic current context/table and test
trampolines for the context getter, name hash and internal adder. Captured game
instructions are checked as data, not executed. The test models an already
validated bootstrap image; full image validation is covered separately by the
bootstrap suite. It calls the real replacement function with handler zero,
exercising resolver/table lookup, successful empty/occupied-slot replacement,
engine refusal and safe restoration together. Invalid unvalidated image, null
context, wrong table signature/address, changed code past byte 64, altered call
displacement, changed RET and nonexecutable destination all prevent creation.

Separate production-dispatch testing confirms zero handler reaches image rejection
rather than the old nonzero-handler gate. Python tests exercise actual command
serialization and full public current/pinned item-field workflows for both trainer
classes, with all external memory/code lookups forbidden. They verify the original
item remains bound and the new item is read back.

Targeted inventory/field/identity regression passed 220 tests and 4 subtests in
17.15 seconds. After adding the full public-workflow cases, the resolver's 24 tests
passed in 3.33 seconds. The first new fixture compile exposed a missing stdint.h
include in test scaffolding, fixed before these successful runs.
Full regression on 2026-09-10 passed **1524 tests and 113 subtests in 97.53
seconds**. Local ignored log: `analysis/native-slot-resolver-regression.log`.

Production helper rebuilt with clang -shared -O2 -Wno-microsoft-goto,
user32/kernel32. SHA-256:
`8dd536e094062b6eaf51c2e9e777e1543bbe36b00bd86e1e0d9f40a7b15cb2e1`.

These are offline execution and source checks, not gameplay acceptance of the new
DLL. The broader migration remains active, including auditing per-command table
refresh cost and remaining selected-unit action paths. Retain the accepted EXE.
