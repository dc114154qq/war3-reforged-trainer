# Warcraft III 3.0 Trainer 2.1.08 — Batch editing

This update builds on the current website release, 2.1.07, and adds a Batch edit tab next to Selected unit.

- Read all selected units and list each unit code separately. Units with the same code remain independently selectable.
- Click a unit row to check or uncheck it, or use Select all and Deselect all.
- Show all writable unit fields found in the selection, with a target input for each field. Leave an input blank to keep that field unchanged.
- Apply each field to each checked unit. Missing, read-only or failed fields are recorded and skipped while the remaining fields and units continue.
- Show individual results and write detailed text and JSONL diagnostics.
- Stop an old batch when the game process or map changes; read the selection again before continuing.

The previous backpack, ability and diagnostic work is retained, including maximum levels for the all-auras and all-passives presets. The four game profiles, discovery data and native DLLs match the current 2.1.07 website build.

Supported game builds: 3.0.0.24268, 3.0.1.24323, 3.0.1.24332 and 3.0.1.24342. This update belongs to the Warcraft III 3.0 download section.

Offline verification passed 4,808 tests and 120 subtests, with 29 skipped. Package source checks, offline executable startup and the four-build performance comparison passed. This release was verified without operating the game; these checks do not establish actual gameplay or external-machine results.
