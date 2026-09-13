# Warcraft III 3.0.0.24268 capability matrix

Evidence status is per current branch and current process tests; “readback” does not mean engine notification.

| Capability | Current path | Status |
|---|---|---|
| Player resources | Indexed player property chain | Verified read/write/readback on 28 slots |
| Selection | Canonical CPlayer+0x168 list | Verified up to 24 schema; current live samples 13–14 |
| HP/MP/position fields | Verified unit property addresses | Verified direct field roundtrip |
| Hero base attributes | Hero component fields | Verified direct field roundtrip |
| Hero skill points | Hero component +0x104 | Verified direct field roundtrip |
| Unit scale | Unit +0x290 | Verified 14-unit direct roundtrip |
| Item charges | Inventory component and item charge field | Verified selected batch direct roundtrip |
| Hero level | Engine Get/SetHeroLevel callback required | Not completed; cache-only write removed |
| Runtime skill replacement | Ability instance + engine notification | Not completed; ambiguous instances rejected |
| Unit cloning/creation | CreateUnit/clone engine callbacks | Not completed |
| Add/remove abilities | UnitAddAbility/UnitRemoveAbility callbacks | Not completed |
| Engine-level movement | SetUnitPosition/space-index update | Not completed; raw coordinate field not treated as proof |
| Cross-device | Profile guards and no fixed heap addresses | Static guards present; second-device live proof pending |
| 1.0.19 baseline | Separate release/tag | Preserved; 3.0 branch independent |

The product must not claim the incomplete rows as successful operations.
