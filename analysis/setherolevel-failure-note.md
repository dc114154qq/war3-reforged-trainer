# SetHeroLevel failure — 2026-09-14

Observation: current native selection returned 15 and fresh first JASS handle 0x10082d. Calling SetHeroLevel(Hunit, 2, true) through the parameterized image wrapper caught 0xc0000005; wrapper cleanup completed. This is not a successful write and is not included in capability acceptance. GetHeroLevel(Hunit) had previously returned 1 with the same selection shape. Hypotheses remaining: handler ABI/boolean representation, required game-thread state beyond window-thread dispatch, or an invalid hero selection mapping. No further writes executed after this failure.


## Static contract recovered
From historical commit `532d809:tools/war3_native_helper.c`:
`typedef void (__fastcall *JassSetHeroLevelFn)(uint64_t unit, int32_t level, uint32_t show_eye_candy);`
The prior 3.0 wrapper used the matching x64 register layout `(uint64_t, int32_t, int32_t)`, so the failure is not currently explained by boolean width. Historical transaction code first validates hero identity, reads current level/XP state, temporarily handles `SuspendHeroXP`, calls `SetHeroLevel`, validates the hero component, and restores XP state. This sequence has not yet been ported to the 3.0 window-thread executor.
