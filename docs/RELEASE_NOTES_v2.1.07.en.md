# Warcraft III 3.0 Trainer 2.1.07

Built on the published 2.1.06 source; the trainer version increases by 0.01.

## Changes

- For official backpacks that appear in the inventory but do not open equipment or talent panels, check the abilities on the backpack item itself. New backpacks use the game's normal item acquisition path before their abilities and extended inventory are checked.
- Skill addition now distinguishes an absent skill from an existing inactive instance. It reuses an existing instance, checks the actual skill list when the direct lookup is empty, and preserves existing levels and item records.
- Check the game's return value against the actual instance and level. If an addition reports failure but consistent readback proves that the skill exists, accept that result without adding it again.
- Fullscreen Monsoon (Alt+P) and Starfall (Alt+A) share the same casting and cleanup flow. Temporary mana-cost and cooldown changes are restored afterwards; existing cooldowns account for elapsed game time.
- Both successful and failed backpack and fullscreen skill operations save detailed logs. A changed target or instance, an unknown exception, or uncertain cleanup stops the current operation.

## Verification

At the user's request, this update uses code verification only. No local game interaction was performed. The targeted suite passed 736 tests; the complete suite passed 4,744 tests and 120 subtests, with 29 tests skipped. Production C fixtures cover all four recorded game builds, inactive instances, rejected additions, item ability attachment, changed instances and exception cleanup. Packaged code and the offline executable self-test also passed.

The supplied external-machine log proves that adding AIni was rejected. It does not record the skill instances or item abilities at that moment. The identified code defects have been corrected; the game's final internal rejection reason and the panel-opening result on that machine remain unverified. These tests are not external-machine gameplay evidence.

The four game profiles and earlier external transport fixes remain unchanged from 2.1.06. Previously documented automatic compatibility limits still apply. This release belongs to the Warcraft III 3.0 section; the 2.0/community section and historical downloads remain available.
