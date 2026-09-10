# Native read entrypoints and primary-path audit

2026-09-10; branch `codex/v1.0.19-native-read-entrypoints`, parent e787000.
Application 1.0.19 and helper protocol 65 are unchanged. The last accepted EXE
remains 1.0.19-924dd59. No new package or game attachment in this step.

## Change and verification

Selected panel reads, current selection reads, prewarming, full selected fields
and pinned-identity field reads now pass directly through native selection or
identity resolution without opening an unused external ProcessMemory context.
Native candidates already include type IDs, so current/pinned read entrypoints
also avoid the redundant type-enrichment wrapper. Full reads publish selection
summaries only after field decoding succeeds, rather than publishing new summaries
before a failing field response. A failed call raises; it does not return old data.
The last completed summaries remain accessible as historical last-read state.

`test_native_public_field_read.py` routes actual production C op-147 payloads
through public Python reads for both trainer classes, heroes, nonheroes and
zero-component units. It checks armor, attack, hero and ability display, while
external memory, old component lookup and heap heuristics are forbidden. The
selection/identity reply uses a synthetic fixture; this is not a real in-game
selection or bootstrap test. Two controller commands suffice: selection/identity
snapshot, then bound full fields. Panel-only reads use one selection snapshot.
Warmup decodes fields without external access. Existing inventory-display tests
cover items and quantities, while compatibility tests cover mixed selection,
new generations, empty selection and native failure.

Final targeted regression: **125 tests and 12 subtests passed in 10.20 seconds**
across public field reads, compatibility reads, selected write routing, GUI read
failures, display identities, C unit field dispatch, inventory and ability display.
An initial panel test used a nonexistent property; it was corrected to assert the
actual displayed hp_text. The preceding commit passed the full 1454-test suite;
this narrow Python read change was verified with the affected suites, without
repeating all unrelated C builds. DLL bytes were not changed.

## Requirements checked against current code

| Requirement | Evidence and remaining limits |
| --- | --- |
| First read without repeated process-wide scans | `persistent_native_init` submits op 139. `war3_bootstrap_context` gets the module and context function, then table at context+0x28. `war3_bootstrap_query` hashes exact names and finds table entries. Persistent hook installation uses the window thread. No heap search in this traced path. Cold in-game latency has not been measured by this step. |
| Current/new selection, mixed unit types | `_selected_candidates_snapshot` maps full native identities and publishes only after the entire selection maps. Existing compatibility tests cover mixed groups, changed generation and failed/empty selection. New public tests cover full-field decoding with different component masks. |
| Complete fields and quantities | Selection payload supplies basic/hero/ability/item values; op 147 supplies 346 qwords including component identity and inventory metadata. Tests validate representative fields, all attack fields in the C dispatch suite, ability display and six-slot quantities. This is not proof that every map-specific object state is supported. |
| Stable writes to original unit | Guards and native transactions exist for basic values, components, skills and items; accepted 924dd59 covers the requested inventory/transform gameplay checks. Generic field dispatch still has legacy external-write branches; audit which native field descriptors could reach them before removing the remaining public write-memory contexts. |
| No ordinary/backup dependency | Public full-read compatibility methods delegate to the same native path. Both classes are tested with external context access forbidden. Other legacy methods still exist and their UI reachability must be accounted for before claiming complete removal. |
| Current game build, layout independence | Bootstrap uses a validated 2.0.4.23745 module-relative profile and object-table resolvers, not fixed heap addresses. Tests and user acceptance do not by themselves prove every Windows version or game state. |

## Next concrete gaps

`run_command` invokes `war3_bootstrap_refresh` before each normal command, and that
refresh rebinds all 55 required functions. It is bounded table lookup, not a heap
scan, but its cost and reload validation deserve focused review before any change.
Preserving correctness across a changed context is required; caching without
context validation is not a solution. Separately, inspect native field descriptor
coverage through `_write_unit_fields_to_candidate`, whose public generic writers
still open write-enabled ProcessMemory contexts. Keep that work focused on the
original selected-unit goal rather than expanding into unrelated global actions.
