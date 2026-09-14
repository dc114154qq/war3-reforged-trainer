# In-map hero skill replacement guard — 2026-09-14

- Target PID: 38352.
- Attempted same-value write `skill1_name=AHhb`.
- The trainer rejected it before mutation because 3.0 engine ability create/replace is not connected when the native executor is unavailable.
- Error: `3.0 技能替换尚未接通引擎创建/替换接口；原技能及配置未修改`.
- This confirms the refusal path preserves the existing ability; it does not verify skill replacement.
- Skill replacement, cloning, and elephant ability operations remain unverified.
