# 3.0 indexed object and player bootstrap — 2026-09-13

This supersedes the remaining-scan portion of `canonical-selection-audit.md`.
Goal remains incomplete; no 3.0 EXE or execution acceptance is claimed.

## Verified engine links

The old **agent resolver**, not its old address, survived the update. Matching
four independent instruction sequences in captured 3.0 `.text` gave one match:
old RVA `0x31f430` → new RVA `0x1951b0`. Both RIP-relative loads now point to
RVA `0x2f807f0`. Live code matches all 114 bytes of this resolver.

The root contains two tables. For full handle `(generation << 32) | index`, the
high bit of the low dword selects table/count offsets `0x50/0x68` instead of
`0x18/0x30`; clear that bit before indexing. Each entry is 16 bytes, live marker
`0xfffffffe` at +0, owner pointer at +8. The game's resolver checks generation
against owner+0x24. Our reader additionally verifies the whole handle at +0x20,
slot/table/root stability, unit tag at +0x18, and owner+0x90 ↔ unit+0x18.

All 14 existing unit identities matched the earlier scanned index. Deliberately
changing each generation was rejected (14/14). No native function was invoked.
The alternate table branch was tested with fixtures, not a live alternate handle.

The native GetLocalPlayer body was located by its unique pair of conditional
word loads, not by native-name references. It moved from old `0xc51800` to new
`0xca73d0..0xca74dd`. Selected real basic blocks, recovered from the **shared
image section capture**, reveal:

- Encoded game-state pointer: load at `0xca741c`, slot RVA `0x2e9ad00`.
- Decoder at `0xca7475`: ROR 1; ROL 30; add `0x5be06f37fc9b5b29`; XOR
  `0x3a11c7b7ef67132b`; add `0x2d2c27903e7f5d3d`, wrapping each step to uint64.
- GetPlayer helper `0x8bbf50..0x8bbf87`: maximum slot 27, count at state+0x2698,
  pointer array at state+0x26a0. This helper's live bytes are externally readable
  and fully checked by the production profile.
- Current state decodes to `0x2066166f980`; all **28** player pointers validate
  through the agent registry, including player 0's legitimate zero full handle.

Do not use linear disassembly through the unreachable filler between opaque
branches. Do not assume disk `.text` matches runtime bytes: the disk file differs
at the decoded-function checks. The GetLocalPlayer page itself returns RPM 299;
its decoder came from the section capture. Production verifies current PE
timestamp/size/machine, the readable agent resolver, the readable GetPlayer
helper, and every resulting player identity. It does not claim to validate the
GetLocalPlayer decoder page using RPM. No fallback memory scanning was added.

## Product change and tests

`war3_object_registry.py` now implements this guarded, read-only profile and
enumerates the game's loaded modules to obtain its current ASLR base.
`_classic_selection_candidates` uses the actual player array and indexed unit
identities, with neither `_selection_player_pointer_candidates` scans nor
`_build_unit_object_index` scans. Registry state is reset on reconnect. Each
lookup reads current table state, so newly added slots require no index refresh.

`test_object_registry.py` + `test_classic_player_selection.py`: **22 tests and
26 subtests passed**. Covers relocated images, both table branches, slot reuse,
new entries, wrong versions/code, invalid player arrays, zero player handle,
list integrity and changes during reads.

`verify-object-registry-live.py` overrides all process scanning methods to raise
and calls the actual production candidate method. With **no player supplied**:
28 players found, 14 units returned, four identical snapshots, every identity
matches prior independent evidence. First read **16.1 ms**, median warm read
**11.9 ms**. See `object-registry-bootstrap-live.json`. These are selection and
identity timings, not UI/native action timings or cross-device measurements.
An earlier supplied-player run is retained as `object-registry-live.json`.

## Next unresolved link: precise local player

Bootstrap still chooses a **unique nonempty canonical player list**. It rejects
ambiguity and keeps a cached player's empty selection empty, but this heuristic
must be replaced with the actual game mode condition (not a guessed valid index).

Verified GetLocalPlayer tail:

1. At `0xca74ad`, call predicate `0x152a690`.
2. Predicate true: state+0x262e (u16); false: state+0x262c (u16).
3. Pass index and state to `0x8bbf50`; then convert CPlayer to JASS handle through
   `0xcba850`. External selection needs the CPlayer, not that JASS conversion.

Live fields are `(1, 0xfefe)`. Do not simply choose whichever is valid.
Predicate `0x152a690` calls context getter `0x1838b0` with ECX=13, dereferences
returned+0x20, then +0xb8, and compares the dword at resulting+0x30e8 to 1.

Context getter bounds `0x1838b0..0x183976`. Real control path includes:
`0x1838c0 stc`, `jbe 0x1838dc`, `jmp 0x1838fd`. At `0x1838fd`, load ECX from
RVA **0x2f5b528** (live value **22**) and call `0x1e7a6e0`. The latter jumps via
IAT slot RVA **0x22607f0**. Return pointer is RCX; context slot is
`[RCX + index*8 + 0x10]` at `0x183963`. The external TLS/FLS route remains unproven.

The IAT target was `0x206201d3da9`, a private trampoline beginning
`48b847001fe41ba9489a48c1c82e48c1c0154805ba735a1a4805539e454f48ff...`.
It was read, **not called**. It is not directly equal to local TlsGetValue or
FlsGetValue exports. Follow its arithmetic/target with bounded reads to identify
the real API before assuming TLS vs FLS or any TEB offsets. Current Python lacks
Unicorn; an attempted import failed and no emulator was installed or run.

Other work remains: resource UI and operations still include older routes;
most native execution features still need 3.0 adaptation. Existing `_build_unit_
owner_index` force-refresh defect remains elsewhere, although selection no
longer uses it. No 24-unit live test, alternate player-mode live test, actual
new-unit creation test, executable packaging or cross-device acceptance yet.
