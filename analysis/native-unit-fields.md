# Game-thread unit component fields (2.0.4.23745)

Protocol 40 adds op 147, accepted only after a complete unit identity guard
(op 136) in a two-operation command. It follows the unit's inventory, hero,
movement and attack slots and resolves each component's full identity through
the engine object table. Wrapper tag, generation, owner and data backlinks must
agree before copying fields; membership and identity are checked again after
the copy. Present but invalid components cause an error, not a partial result.

The fixed 293-qword response includes unit identity, component membership and
addresses, armor, hero fields from 0x100 through 0x21f, and both attack records.
The second attack requires a readable vtable with an executable function and
the matching record identifier. No high-address vtable heuristic or component
cache is used. The Python field builder reads this response locally and never
fills absent component bytes with external process reads.

Validation:

- Production C dispatcher, binary parser and field builder exercised together.
  Cases include hero/nonhero and absent components, both attacks, stale unit
  and component generations, changed membership, invalid pointers, and a
  readable header whose fields cross into a PAGE_NOACCESS page. Failures publish
  no partial field payload. Invalid-pointer checks cannot rely on SEH alone:
  the optimized compiler used here allowed an unguarded invalid load to escape
  the handler; the reader now verifies each complete range before loading it.
- Full regression: 417 tests and 108 subtests passed.
- Read-only game check: 11 selected units (2 heroes, 9 nonheroes), 304 field
  values compared with direct memory reads, zero mismatches, no missing keys
  against the previous field audit. Full field reads took 21.51–26.06 ms.
  See `native-unit-fields-live.json`; these are current-process observations,
  not a new EXE or a gameplay mutation test.

Protocol 41 subsequently moved candidate construction/property metadata and
HP/MP regeneration into the native chain (see `native-regeneration.md`).
Inventory write metadata and generic field writes still retain external-memory
work. In particular, reading a component snapshot does not
establish that later writes validate the same component generation. The full
DLL-only goal remains unfinished. The validated 1.0.19 EXE is preserved.
