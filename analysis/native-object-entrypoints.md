# Native ability/item entrypoints

2026-09-10, branch `codex/v1.0.19-native-object-entrypoints`, based on 6a81f05.
Application 1.0.19, helper protocol 66 and DLL bytes remain unchanged. The last
user-accepted EXE is 1.0.19-924dd59; this change is independently code-verified.

Ability field context for current selection and pinned identity, pinned item
field context, removal of all abilities and inventory bundle replacement no
longer open unused external ProcessMemory contexts. Their native branches already
use DLL metadata/list queries and bound operations; the exact-slot resolver was
migrated in 3bb9e63. Compatibility UI paths keep the same identity resolution.

Inventory bundles capture `_direct_selected_context` once and reuse the same
candidate for every original slot. Each operation still submits original item
handle/generation/object data. No refresh silently substitutes a replacement
item. Failure stops later submissions; earlier successful replacements are not
rolled back as a whole. Existing per-slot transaction recovery is unchanged.

Removal of all abilities enumerates the bound unit through op 146, then submits
op 156 with each enumerated full ability generation. Tests change the apparent
current selection after enumeration and verify the original unit stays bound.
The requested removals do not follow a newer selection. Native generation failure
propagates rather than triggering a controller scan.

New tests cover both trainer classes with external memory forbidden, actual
Python metadata/list decoding and command construction, pinned ability identity,
inventory bundle failure ordering and original slot identity. Existing ability
metadata and item-field tests now explicitly reject external memory contexts.
The initial new removal test used the wrong enum opcode; it was corrected to use
the named constant before the successful regression.

Verification: **136 tests passed in 11.37 seconds** across object entrypoints,
ability actions/metadata/fields/list dispatch and binding, item field binding and
the production slot resolver. That includes C fixtures for list dispatch and
slot replacement. The preceding production DLL passed 1524 full-suite tests;
this Python-only entrypoint change used the affected suites rather than repeating
all unrelated builds. No running game or EXE was opened.

This removes the audited dependencies in these entrypoints, not every legacy
private implementation in the source. Remaining selected-unit creation/copy
setup should be traced for external code discovery before claiming complete
independence of all actions. Preserve the accepted EXE and gather further changes
before requesting another gameplay test.
