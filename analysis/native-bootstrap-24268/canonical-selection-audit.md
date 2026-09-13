# 3.0.0.24268: canonical selection correction, 2026-09-13

Current process: 16700. No writes, helper installation, native invocation or UI
actions were used for these live checks. Old 1.0.19 release remains separate.

## Corrections to earlier interpretations

- Loader context RVA is `0x21b6c40`, not `0x20f6c40`. The incorrect arithmetic
  invalidates the prior “not initialized” claim. It also invalidates explanations
  of the failed table read as a paging or 256th-entry boundary problem.
- The context's `+0x20` pointer targets loader RVA `0x22906e8`, in `.eid`, outside
  the captured `.data` section. All 512 sampled u32 values match the disk image.
  Neither function-address semantics nor the `+0x28` field's meaning is proven.
  This is not evidence of a dynamically generated Warcraft native handler table.
- Player `0x2066dbfb018 + 0xf78` equals adjacent player
  `0x2066dbfbe28 + 0x168`. The old field search crossed the object boundary and
  assigned the latter player's 14-unit list to the former player.

## Implementation and evidence

`war3_classic_selection.py` reads only `player+0x168` and the manager's primary
list. It checks the count (0–24), tagged end sentinel, tail, unique nodes/units,
two matching traversals and an unchanged manager pointer. In the actual empty
list, head is `(manager+0x10)|1` while tail is `manager+0x10`; an initial fixture
incorrectly tagged both, which live testing caught and corrected.

The production `_classic_selection_candidates` now uses this reader. It does
not rank neighboring fields/control groups by list length, keeps a cached
player's empty selection empty, and checks selection again after resolving unit
identities. Multiple nonempty player lists are reported as ambiguous instead of
silently choosing the largest. Cached results are cleared before a fresh read.

Evidence files:

- `loader-index-live.json`: current module context, PE identity, disk comparison.
- `canonical-player-list-live.json`: ten reads each for the empty player and the
  14-unit player. All results matched. Median list-only time was 0.202 ms for 14.
- `canonical-selection-identity-live.json`: actual production candidate method,
  with the player address supplied explicitly and no background trainer startup.
  All 14 units resolved to full-handle/owner/object identities and matched the
  canonical list. Cold read including the existing owner-index scan: 938 ms;
  second read: 13.6 ms. These are not native/JASS handles or execution timings.
- `test_classic_player_selection.py` and `test_loader_context_probe.py`: 14 tests
  plus 15 subtests passed. Includes relocated pointers, 0/1/14/24 entries,
  adjacent-player ownership, invalid/cyclic/truncated data, same-count mutation,
  stale module bases, PE mismatch and short reads.

## Remaining work, not delivery claims

The product still discovers player/owner candidates using legacy memory scans.
This fails the requested scan-free fast bootstrap goal. Unique nonempty player
selection is a provisional disambiguation rule, not an independently verified
local-player locator. The next integration must obtain the local player and
object identity from a validated 3.0 root, without those scans. The owner-index
force-refresh path still reuses the existing owner dictionary; new-unit handling
requires further repair. No 24-unit live test, cross-device startup, native
execution/clone/skills/resources completion or packaged 3.0 acceptance is claimed.

Next: trace a real 3.0 game/player/object root and identity resolver, keeping the
canonical list reader as the checked traversal. Do not repeat the old loader
context arithmetic or interpret raw .eid values as callable functions.
