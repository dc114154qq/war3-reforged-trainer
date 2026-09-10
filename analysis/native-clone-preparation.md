# Native clone preparation — 1.0.19 / 2.0.4.23745

Branch `codex/v1.0.19-native-clone-preparation`, based on cdbd6ae. Helper remains
protocol 66 and its binary is unchanged. Latest accepted gameplay package is
1.0.19-924dd59. No new EXE, live process reads or game execution in this step.

## Demonstrated preparation issue

`create_local_unit(None)` captured a native selected candidate, then reopened
ProcessMemory and called `_selected_components` to decide whether to clone hero
and inventory state. Exceptions in that lookup silently set both flags false.
That allowed a failed secondary lookup to downgrade the clone without explaining
that hero/inventory data was being omitted.

The method now requires that the candidate's native snapshot matches its JASS
handle, reads hero/inventory flags directly from the captured component mask,
and queries the needed native table functions directly. It no longer opens
external memory for either cloning or explicit rawcode creation. Missing or
mismatched native identity fails before handler lookup or creation. Selection
changes while preparing handlers cannot change the captured flags or handle.

The 14-descriptor single game-thread clone command is unchanged. Explicit
rawcode creation remains the plain creation command and does not query selection.
No arbitrary waits, fallback heuristics or new cache were introduced.

## Verification

New tests cover both trainer classes, six component-mask combinations, preserving
or changing owner, selection changes during handler lookup, absent/mismatched
native snapshots and explicit creation without selection. They prohibit external
memory and component queries, and check actual command serialization for all
14 descriptors. Existing clone preparation tests were updated to use real native
candidate fixtures instead of incomplete Mock objects.

**69 tests and 16 subtests passed in 0.80 seconds** across clone preparation,
helper runtime features and selected context. This verifies Python preparation,
not the full game cloning outcome. Production C was not changed, so unrelated
native fixture builds were not repeated.

## Required next work

This is not a claim that cloning meets the full identity requirement. C op 118
currently accepts only 14 descriptors at index zero, checks source unit type,
then reads/copies state across callbacks. It lacks the full source generation
guard used by the newer commands. Add a bound form that validates the original
source and newly created target around callbacks, handles original item/ability
identity during copying, and performs cleanup only for the original valid target.
Tests must include same-type recycled source and target, not just changed rawcode.
Preserve the existing fast single-command behavior and accepted user-visible clone
features while doing so. Keep this experiment; do not roll back useful progress.
