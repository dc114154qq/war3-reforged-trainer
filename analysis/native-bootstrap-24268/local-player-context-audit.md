# Verified local player and real native table — 2026-09-13

Supersedes the unresolved-local-player section of `object-registry-audit.md`.
The overall 3.0 trainer goal remains open; no native execution or EXE is accepted.

## Frame context and precise player selection

The context getter's IAT trampoline was decoded with read-only arithmetic. Its
target is **kernel32!TlsGetValue**, not FlsGetValue. The trampoline incorporates
the current PEB Ldr pointer, so its immediate values/absolute addresses must not
be copied to another process. Production does not use those process-specific
constants; the game accessor code is checked and the TLS index is read afresh
from the verified game RVA `0x2f5b528`.

The visible game window's thread is **37144**, TEB `0xf7d13fd000`, in PID 16700.
TLS slot 22 is populated only during portions of a running frame. Initial
one-shot reads of all threads found zero, but a second timed sample found
`0x2062ef5ea60` in the window thread. Do not reinterpret a null sample as missing
3.0 support. No focus changes, input, game writes or injected code were needed.

For the sampled context:

- `TLS_value + 0x10 + 13*8` → `0x20631322ff0`.
- Dereference +0x20, then +0xb8 → mode object `0x206593be050`.
- Dword +0x30e8 is **0**, so GetLocalPlayer uses game-state word +0x262c = **1**.
- Mode exactly **1** selects word +0x262e; other mode values select +0x262c.
  The alternate word is currently `0xfefe`; the reader does not substitute the
  other index if the selected one is invalid. Both branches are parts of the
  same game accessor, not alternate/backup memory-reading backends.

`war3_thread_context.py` verifies the live context getter and mode predicate
code, queries only the game's window thread identity/TEB, and derives TLS field
offsets from the current Windows TlsGetValue implementation. This OS uses
direct slots at TEB+0x1480 and an expansion pointer at +0x1780. Tests cover the
direct GS and indirect TEB forms, relocated offsets, and indexes 0/22/63/64/1087.
These tests are not physical Win10/other-device acceptance.

The reader checks the chain and TLS binding before accepting a frame sample.
Null/changing contexts and retired-page read errors retry within a **250 ms**
deadline; permission errors propagate immediately. Deadline errors include time
and attempt count. No remembered frame pointer is trusted as a persistent TLS
binding. The last successful mode snapshot is retained for diagnostics.

`_classic_selection_candidates` now resolves the local player from this mode
every time. The unique-nonempty-list heuristic is removed. Empty local selection
and multiple other player lists no longer require guessing. The existing
registry and canonical list checks remain in place; no process scans are used.

Validation: **33 tests, 34 subtests passed**, covering mode selection, no fallback
to another player index, transient frames, thread replacement, TLS expansion,
identity reuse and selection races. `local-player-context-live.json` records the
production method under a memory-scanning prohibition: 28 players validated,
14 unit identities unchanged, four matching reads; first read **28.7 ms**, warm
median **18.4 ms**. The final mode sample took 2.7 ms / three attempts. Actual
alternate-mode and empty-selection live tests remain separate from fixtures.

## Real native registration table found

The same frame context contains slot 5 at `TLS_value+0x38`:
`0x2065f919bc0`. Its native table is **embedded at context5+0x28**;
do not dereference +0x28 as a pointer (it is the table's vtable).

Verified list layout:

- Table +0x18: first full node.
- Node +0x20: next full node.
- Terminal: `(table+0x10)|1`.
- Node +0x28: name string pointer; +0x30: handler; +0x40: signature string pointer.

`verify-native-table-context-live.py` traversed **1826** unique registrations to
the expected terminal, rechecked the head/context, and found all nine requested
entries. It reads bounded strings and nodes; it never calls the functions.
Result: `native-table-context-live.json`.

| Name | Current handler RVA | Signature |
| --- | --- | --- |
| GetLocalPlayer | 0xca73d0 | ()Hplayer; |
| GroupEnumUnitsSelected | 0xcb08a0 | (Hgroup;Hplayer;Hboolexpr;)V |
| CreateUnit | 0xc98620 | (Hplayer;IRRR)Hunit; |
| GetUnitState | 0xcaf3b0 | (Hunit;Hunitstate;)R |
| GetHeroStr | 0xca6440 | (Hunit;B)I |
| UnitAddItemById | 0xcffff0 | (Hunit;I)Hitem; |
| UnitAddAbility | 0xcffd30 | (Hunit;I)B |
| SetPlayerState | 0xcf4690 | (Hplayer;Hplayerstate;I)V |
| GetPlayerState | 0xca9290 | (Hplayer;Hplayerstate;)I |

The registered GetLocalPlayer address independently confirms the function that
was previously identified by code structure. The previous speculation that
native handlers required locating a loader-owned dynamic table is superseded.
The loader `.eid` index remains unrelated evidence; do not resume that detour.

## Next work

Use this native context/table as the actual 3.0 discovery source. Audit handler
ABIs and current unit/item/ability resolvers before adapting helper execution;
do not use the old 23745 profile or silently pass full object handles as JASS
handles. The helper's loading/game-thread execution problem remains distinct
from now-working native discovery. Resources/UI and most native actions still
require migration, regression checks, packaging and physical cross-device test.
Keep old 1.0.19 release untouched and all 3.0 work on its independent branch.
