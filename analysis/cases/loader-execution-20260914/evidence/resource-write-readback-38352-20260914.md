# In-map resource write/readback — 2026-09-14

- Target PID: 38352.
- Operation: set gold to its current value 997469 with current-gold/current-lumber guards.
- Result: `gold set delta=+0`.
- Independent readback: gold 997469, lumber 999839, food 38/72.
- Source: `3.0 indexed player properties`.
- This verifies the indexed resource write route without changing the game value.
- No unit, skill, item, clone, or elephant mutation was run in this step.
