# Live probe crash root cause and guard — 2026-09-14

## Verified observations
- PID 38352 was a responsive visible Warcraft III client.
- `verify-game-thread-dispatch.py --query-mode selection` entered the game callback on TID 35668.
- The callback then raised `0xc0000005`; no write operation was issued.
- Source inspection showed the CLI called `inspect(..., query_mode="selection")` without a `work_payload`. The native probe dereferenced `g_dispatch->work` as `SelectionWork *`, so it was null.
- The probe cleanup completed and unmapped its image/block.
- PID 38352 subsequently exited; a later process identity must not reuse its addresses.

## Fix
`analysis/verify-game-thread-dispatch.py` now rejects selection/selection_fixture modes without an initialized SelectionWork payload before opening or dispatching to the target process.

Commit: `aa76e7d`

## Remaining gap
A complete 3.0 SelectionWork payload must be rebuilt from the current PID's native table and independently validated before any further live call. No live write, clone, ability, item, or elephant operation was attempted in this turn.
