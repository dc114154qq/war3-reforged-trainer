# Warcraft III 3.0 Trainer 2.1.07 — Backpack ability checks

This replaces the previous 2.1.07 build and retains its detailed diagnostics.

- Reuse the historical bound ability-list compatibility check for backpack items. If the direct query is empty but the same item already has the ability in its list, preserve that instance instead of adding it again.
- Verify new attachments through both lookups. A false native return is accepted only when the exact item has a matching instance; the addition is called at most once.
- Stop when IDs are ambiguous, handles repeat, or the direct query disagrees with the list. Preserve the item, inventory slots, charges and original capabilities.
- Record the direct/list lookup evidence before and after attachment, with concise error explanations.

The existing activation, external loader recovery, Monsoon and Starfall fixes remain available. All four exact profiles and discovery rules match the previous release.

The published production C reproduced duplicate attachment and incorrect failure reporting with identical offline fixtures; the corrected C passes. Targeted verification passed 774 tests. Full verification passed 4,782 tests and 120 subtests, with 29 skipped. Bridge compilation, adapter audits, package checks and offline self-test passed. No local game interaction was performed.

The earlier external log proves AIni addition was rejected, but does not contain the ability instance lists. This repairs confirmed code omissions; the final internal rejection cause and the panel-opening result on that machine remain unverified.

This release belongs to the Warcraft III 3.0 section. Historical builds remain available. No version email is sent for this update.
