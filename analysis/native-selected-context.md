# One selected-unit context for both controller editions

The compatibility subclass returned `candidate.handle` as the executable JASS
handle. Native candidates store the full object generation there, while the
attached snapshot's `handle` is the JASS handle. The inherited ability action
and direct-effect entry points reject this mismatch, so mocked context tests
alone had missed a real integration error.

Both classes now obtain the pair from `_selected_candidates_snapshot`, using
the same native snapshot. The context no longer opens a controller-side memory
backend just to convert the already-complete native payload. Mixed-selection
overrides preserve the pair for each member without rereading selection.

`test_native_selected_context.py` exercises the real context and snapshot
mapping, mocking only the DLL boundary. It uses deliberately different JASS
handles and full generations, verifies a reused object address after a target
switch, rejects empty selection, and runs ability add and mixed hero/nonhero
direct effects. Eight cases failed before the fix; all ten pass afterward.
The combined context/action/source-routing suite passed 83 tests (5.20 s).

Full regression: **804 tests and 103 subtests passed** (39.26 s), recorded in
`analysis/native-context-regression.log`. No DLL change, EXE build, live game
call, or user gameplay acceptance is part of this increment.

Remaining direct-effect audit:

- The sustained-area path has separate create/read-field/write-field/effect/
  wait/stop/restore/remove commands. Cleanup uses previously captured ability
  handles across a wait. It needs an identity-bound lifecycle, including stop
  and field restoration, not just delegation to a transaction that immediately
  removes temporary abilities.
- Its standalone ability-field setter also lacks the op 136/142/143 binding
  descriptors required by the current C dispatcher. This is a concrete
  integration mismatch to resolve in that migration.
- The roar/buff path discovers the buff-data constructor by following calls
  from the effect callback. The captured native-call contract JSON currently
  has no buff-constructor contract. That callback must be established from
  the current build before moving its discovery into the DLL.
