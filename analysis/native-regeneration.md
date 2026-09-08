# Native unit properties and regeneration (2.0.4.23745)

Protocol 41 extends each persistent snapshot from 149 to 153 qwords with HP/MP
property addresses and regeneration values. The native reader traverses only
the owner's two lists at 0xa0/0xb0, using their byte lengths at 0xa8/0xb8.
Lengths must be aligned and at most 0x400; invalid lengths are rejected instead
of substituting a guessed length. No process-wide or wrapper-neighborhood scan
is involved, and no previous property's address is reused.

Property tags, kinds, full identities, owner backlinks and object-table results
must agree. Duplicate entries for the same property are allowed; two distinct
properties for the same kind are rejected. List contents and property identities
are rechecked before return. The snapshot also validates its unit identity after
all fields have been collected, so Python constructs the candidate directly
from the immutable native result. Targeted refresh replaces property metadata
as well as values. Targeted reads and mutations retain their DLL identity guards.

Op 148 writes either or both regeneration fields, following op 136. It resolves
current properties on the game thread and checks all requested fields and their
write permissions before changing either. Native field-editor and basic-value
operations route here and read back through the targeted native snapshot; they
do not use external property writes. CLI regeneration display uses native values.

Validation:

- Real C snapshot reader, command dispatcher and Python parser exercised with
  missing properties, invalid/unaligned/oversized lists, bad pointers, wrong
  owner/generation, duplicate kinds, changed unit/list identities, read-only
  memory, non-finite input, and one/two-field writes. A missing second property
  cannot leave a successful write to the first property behind.
- Candidate mapping traps every external memory access. Field-editor tests
  verify native setter routing and readback with no external writes. Refresh
  tests replace property addresses while preserving the unit generation.
- Full regression: 453 tests and 108 subtests passed.
- Current-game read-only check: 11 selected units, 22 regeneration values
  matching direct memory reads, no missing previous field keys. Mapping took
  0.242 ms with external identity/property/component lookups trapped. Snapshot
  acquisition took 49.944 ms in that audit instance. Complete field reads were
  33.427–37.727 ms in this run; this is not evidence of an overall latency
  improvement over the previous audit. See `native-regeneration-live.json`.

The validated EXE remains untouched and version stays 1.0.19. No gameplay
mutation was performed in the live game. Remaining work includes inventory
metadata/creation routes and generic component field writes; the complete
DLL-only goal is not yet achieved.
