# Warcraft III 3.0 Trainer 2.1.12

Adds a dedicated adapter for **Warcraft III 3.0.1.24371**, included directly in the EXE. No separate adapter installation is needed. Listed in the website's Warcraft III 3.0 section.

## Changes

- Updates the unit, player, selection and ability-call dependencies for the new build, including the reviewed attack-speed query functions.
- Includes the previous local preview's **Ctrl+X cursor teleport precision fix**, improving terrain intersection on slopes. Actual in-game landing still needs confirmation.
- Fixes premature object-identity confirmation in automatic discovery. The builder now checks that every bundled game profile has matching discovery source data.
- Retains batch editing, campaign backpack definitions, individual failure handling for All passives / All auras, and the previous six game profiles.

## Current limits

For **3.0.1.24371**, **3.0 detailed attributes, fog operations and alternate local-player mode** remain disabled because their dependencies have not been independently verified in full. Ability leveling retains its existing error handling without a guessed old exception-recovery address.

This is a dedicated 24371 adapter. Complete automatic support for future unknown builds remains unverified.

## Verification

Live read-only checks covered 28 players, the selected hero and another registry unit, 19 components and 1,857 Native registrations. Camera, armor, intelligence and attack-speed queries completed with readback and cleanup. No game business data was changed.

Across separate runs, **5,013 distinct offline tests and 120 subtests passed; 29 skipped**. One existing Tk initialization failure in the full process passed unchanged in a fresh process; this is not a claim of a single error-free full run. EXE archive checks and startup self-test passed. Game mutation effects, actual Ctrl+X landing and external-machine execution remain unverified.

Bundled profiles: 3.0.0.24268, 3.0.1.24323, 3.0.1.24332, 3.0.1.24342, 3.0.1.24360, 3.0.1.24365 and 3.0.1.24371. Available features depend on each build's profile.
