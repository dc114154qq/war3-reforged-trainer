# In-map hero base-attribute writeback — 2026-09-14

- Target PID: 38352.
- Read-only field audit found base strength 22, base agility 13, intelligence-total candidate 22, skill points 0, and runtime ability/item instances.
- Same-value write: base strength `22 -> 22`.
- Result: `unit field written base_strength 力量(基础)=22 type=i32 addr=0x225fff98fd0`.
- No value change was introduced.
- Skill and item instance reads were observed but no skill/item mutation was attempted.
