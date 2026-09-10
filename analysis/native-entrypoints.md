# Native public entrypoints — 1.0.19 / 2.0.4.23745

Branch `codex/v1.0.19-native-entrypoints`, based on accepted package source
924dd59 and delivery documentation e1aa789. The user's 2026-09-10 feedback accepts
924dd59 and requests continued development with independent code verification.

The compatibility `_elephant_handlers` entrypoint now queries exactly the
deduplicated requested names using the shared DLL table API. Previously it
appended the 84-name Elephant set on every request, forcing unrelated cold native
lookups and making an operation depend on unused functions. Existing missing-name
errors are retained. An actual controller serializer test permits only the two
requested indices in a cold lookup and proves a warm repeat sends no lookup
command. Both trainer classes use the same API, with no external memory access.

The native selected-unit locator now returns its engine snapshot directly even
when no ProcessMemory argument is supplied. Public vital/position write entrypoints
for current selection and pinned full identity no longer open an external write
handle: selection, identity resolution, guarded setters and readback already run
through native commands. Optional memory arguments are retained for compatibility;
they do not enable an old selector. Native function verification similarly calls
the table API directly. DLL code, protocol 65 and application 1.0.19 are unchanged.

New tests exercise the real public writer for both trainer classes with external
memory and old object mapping forbidden. Current selection is queried once;
pinned identity performs native object-table resolution without querying current
selection. Generation mismatch prevents all setter submissions. A successful
write returns the targeted native readback. Existing routing tests retain changed
selection, empty selection and invalid-group checks.

Targeted verification: 83 tests and 20 subtests passed in 4.55 seconds across
entrypoints, selected write routing, basic writes, large numeric rereads, helper
runtime features and source routing. No game process was attached and no EXE was
rebuilt. These changes remove real lookup/open-handle work; they do not establish
a measured in-game latency reduction or completion of the entire migration.

Full regression passed **1454 tests and 113 subtests** in 103.41 seconds on
2026-09-10. Local log: `analysis/native-entrypoints-regression.log` (ignored).
The next audit should map remaining gaps in first read, selection changes and
complete selected-unit field read/write paths against the original goal, before
expanding into additional world/player operations outside those primary paths.
