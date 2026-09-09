# Full-identity native reads (protocol 47)

Display/remembered identities now resolve through operation 155 in the DLL.
Python supplies the full engine generation, owner wrapper and unit object;
it supplies no JASS handle and does not search the recent selection cache.
The DLL resolves the full identity through the agent object table, validates
the owner/unit backlinks, converts the validated object to its JASS handle,
and validates that handle back to the same full identity before field queries.
It then uses the existing guarded targeted snapshot reader in the same callback.

The conversion contract comes from the captured 2.0.4.23745 runtime .text:
FirstOfGroup RVA `0xc46370`, a 51-byte body with a tail jump at offset 39 to
RVA `0xc66bb0`. Immediately before that jump it passes the unit object in RCX
and flag 1 in DL. The DLL verifies the complete FirstOfGroup instruction body
(only the three rel32 operands may differ) and the target's executable mapping.
The source is the native registration table. There is no byte-pattern search,
heap enumeration, hardcoded process address or execution of an unverified match.
The rest of the target's protected/encoded implementation was not inferred.

All display identity field reads/writes, ability/item field contexts, and
remembered summaries use this entry. Compatibility identity APIs delegate to
the same implementation; an old UI source label no longer requires a backup
session. Unbound basic writes also resolve their supplied full identity instead
of looking for a matching unit in the current selection. Unit type comes from
the native snapshot instead of a redundant external memory read.

Remembered summaries obtain actual components/inventory from operation 147.
They do not guess attack, movement or inventory support from unrelated stats.
The separate group-summary fast path still has such guesses and remains an
explicit follow-up; this change does not claim all summary routes are finished.

Validation:

- Production C dispatcher tests cover conversion ABI, successful complete
  snapshot payload, stale generations, wrong owner/type/backlinks, unreadable
  unit addresses, mismatched instruction bodies, missing natives, non-executable
  conversion targets, empty/wrong JASS results, changes during conversion and
  field reads, and a converter exception. No field native runs before identity
  conversion succeeds; no selection group is queried.
- Python tests cover a missing recent-selection cache, mismatched returned
  identities, both UI read entry points, stopped writes on identity failure,
  and a nonhero summary with an empty inventory component and no attack/move
  component. External reads are trapped.
- Full regression: **679 tests and 103 subtests passed** (31.04 s).
- Optimized DLL compiled. Live read-only test on PID 15028 cleared the selection
  cache, then used the public identity field-read APIs for nine units, alternating
  normal and compatibility entry points. All returned the original full identity
  and complete fields while an external-memory facade raised on any access.
  A remembered summary also succeeded. See `native-display-identity-readonly.json`.

No gameplay mutation or EXE test was performed. The existing validated EXE is
preserved; the application version remains 1.0.19. Remaining legacy discovery
and ability lifecycle routes still need auditing against the full objective.
