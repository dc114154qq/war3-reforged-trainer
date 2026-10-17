# Warcraft III 3.0 Trainer 2.1.10

Create a repaired copy when a campaign reports missing backpack definitions. All passives and All auras now skip an individually rejected skill and continue the remaining skills after execution cleanup is confirmed.

## Changes

- **Add campaign/map backpack definitions**: a new button below Read Extension State in 3.0 Extensions accepts .w3n campaigns and .w3x maps and creates a separate copy, preserving the original.
- Processes every campaign chapter and adds missing backpack, equipment, related talent and dependency definitions. Existing records are preserved; object-ID conflicts are reported. Archives are reopened and verified after writing.
- Complete output paths wrap, scroll and support selection, copying and opening the output folder.
- **All passives / All auras**: a rejected skill is recorded and skipped once callback exit and cleanup are confirmed. The remaining skills continue, with completed/skipped counts and detailed logs. Maximum-level settings are retained.
- Keeps the faster batch reader from 2.1.09, all five game profiles and existing features.

## Why the same campaign behaves differently

An identical Ireland's Soul 1 campaign loaded the base ability table containing the 3.0 definitions in 3.0.0.24268. In the observed 3.0.1.24360 session, it loaded the older custom-data table without those definitions. Loaded data, rather than campaign age alone, determines availability.

## Use

Choose Add backpack definitions → select the input and output folder → Create repaired copy. Put the generated copy in the appropriate game folder and enter the map afresh. Existing saves retain their original map data.

For **Warcraft III 3.0**. Built-in profiles: 3.0.0.24268, 3.0.1.24323, 3.0.1.24332, 3.0.1.24342 and 3.0.1.24360.

Verification: 4,953 distinct offline tests and 120 subtests passed; 29 skipped. Packaged dependency checks and EXE startup self-test passed. All 11 chapters of Chronicles of the Forsaken 1 were processed and reread. Gameplay effects of the processed copy and external-machine execution remain unverified.
