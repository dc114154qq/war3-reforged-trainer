# In-map agility and item-charge writeback — 2026-09-14

- Target PID: 38352.
- Base agility same-value write: `13 -> 13`, success at `0x225fff98ff8`.
- Inventory slot 1 charges same-value write: `1 -> 1`, success at `0x22596043b98`; item flag readback remained `0x2757`.
- The item native handler was unavailable, so the guarded direct item-property fallback was used and verified by readback.
- Regression: 60 passed.
- No gameplay value changed; no skill replacement, clone, or elephant operation was run.
