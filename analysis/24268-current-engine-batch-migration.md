# Warcraft III 3.0.0.24268 current-engine batch migration

Date: 2026-09-15
Branch: `codex/war3-3.0.0.24268-adaptation`

## Verified locally

- Unit actions remain ABI `0x24268016`, 24-unit capacity, and now include mixed-selection hero skill-point modification. Nonheroes are acknowledged as skipped rows.
- Item batch actions now cover query, add, charge write, diagnostic add, clear, duplicate, and drop. Duplicate preserves original slot identities and accepts full-inventory ground creation semantics.
- Ability batch actions now include add, remove, level, diagnostic, and reset. Reset removes and recreates the requested ability in one game-thread batch.
- World batch ABI `0x24268017` covers local technology, XP rate, fog query/toggle, pause, and end-game calls.
- Product and fixture bridge ABI checks passed. Product bridge SHA-256: `787DFFB77EDF851AC5FD6615625DF3BD228366F35D98858587B1E39371601FD4`.
- Focused current-engine suites passed: `208 passed`.
- `git diff --check` passed; only line-ending normalization warnings were emitted.

## Live process note

PID `26796` was still the only responding Warcraft III process when checked. A current-engine item query reached the dispatch path once, but the follow-up attempt stopped before dispatch because the game context exact-byte page was temporarily unreadable (`WinError 299`). No live mutation is recorded as successful from that attempt.

A later read-only world-fog probe reached the current native callback and returned bridge `error=84` from a game-side exception. The dispatch cleaned up successfully and performed no write; this indicates the process was not in a stable map/UI context for that query, not a successful world-state read.

## Release policy

This work remains on the 3.0 adaptation branch. Later builds are not synchronized to the personal website; website sync is reserved for an explicit future request.
