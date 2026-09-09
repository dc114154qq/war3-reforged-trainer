# Real component metadata in group snapshots (protocol 48)

The persistent selected/targeted/identity snapshot now contains 154 qwords per
unit. The appended word is a component mask: inventory=1, hero=2, move=4,
attack=8. Existing offsets and ability overflow ordering are unchanged.

The DLL reads the four direct component slots and resolves each full generation
through the agent object table. It validates component type, unit/owner
backlinks, wrapper/data identity, and unit identity before publishing the mask.
The final component pass makes no engine callbacks, so it also detects a
previously empty slot populated while resolving another component. An invalid
component fails the entire snapshot instead of returning a partial group or
guessing capabilities from stats.

Group summaries now use the mask instead of assuming every unit attacks,
inferring movement from move speed, or inferring inventory from hero status or
existing items. They still use the original immutable selection snapshot and
make no extra DLL calls or external process reads. The payload grows by eight
bytes per unit; the maximum 12-unit group adds 96 bytes.

Validation:

- Real C selection snapshots cover all 16 component combinations and a mixed
  12-unit group, then pass through the production Python parser, candidate
  mapping and group summary builder with extra IPC/external reads prohibited.
- Eleven failure cases cover component generation, owner/type/data backlinks,
  invalid data and resolver pointers, removal/addition during resolution, unit
  recycling, and a component changed by the final unit validator. No partial
  group escapes and all snapshot allocations are freed.
- Existing overflow-ability, regeneration and identity snapshot fixtures were
  updated for the appended word. Unknown component bits are rejected.
- Full regression: **708 tests and 103 subtests passed** (32.87 s).
- The optimized DLL compiled. In live read-only validation (PID 15028), nine
  selected units produced two heroes with mask 15, six nonheroes with mask 12,
  and one nonhero with mask 13 (inventory present). Group-summary construction
  used zero extra IPC calls. Two sampled masks matched the full field reader's
  component list. See `native-snapshot-components-readonly.json`.
- Two nine-unit snapshot calls after initialization took 24.30 and 19.21 ms.
  These are local observations, excluding DLL/bootstrap initialization, not a
  cross-machine latency guarantee or a gameplay mutation benchmark.

The old group-summary guessing gap is closed. Gameplay mutation and a new EXE
test were not performed. Version remains 1.0.19 and the validated EXE stays
untouched. Remaining ability lifecycle and legacy discovery entry points still
need the final reachability audit against the DLL-only objective.
