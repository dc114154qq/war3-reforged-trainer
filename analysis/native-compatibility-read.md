# Compatibility read entry consolidation

Date: 2026-09-09. Development branch: `codex/v1.0.19-property-identity`.
Application version remains 1.0.19. Native protocol remains 56; DLL unchanged.

## Finding and change

The main selected-unit locator already uses persistent DLL selection snapshots;
its historical `allow_deep_scan` parameter does not enable scanning. This audit
did not establish a scan fallback in the main read path.

However, the public `read_selected_unit_fields_win10` entry still constructed an
isolated compatibility trainer, enumerated memory regions, recovered handlers,
and attempted older selection routes. It could also substitute a single candidate
when full selection enumeration failed. Its nested GUI callback is not bound to
the current product buttons, so this finding does not explain historical user
reports of operation latency.

The compatibility entry now delegates to `read_selected_unit_fields`, as the
identity read/write compatibility entries already do. Its GUI callback delegates
to the main callback, including clearing the candidate list on read failure.
No compatibility session or diagnostics setup is needed by this entry.

Prior native ability effects, lifecycle, buff, toggle and world-effect experiments
remain intact. Removed code belongs to this obsolete alternate read path.

## Verification

- Targeted suite: 33 passed, 8 subtests passed.
- Full suite: 942 passed, 105 subtests passed, 52.19 seconds.
- Log: `analysis/native-compatibility-read-regression.log`.
- New tests execute both public read APIs with real selection mapping, panel
  decoding and summaries. They inject native snapshots and stub field decoding
  (covered separately), disallow legacy lookup/discovery/region enumeration, and
  cover mixed selection, address reuse with a new generation, empty selection,
  duplicate/incomplete snapshots and native errors after a successful read.
- GUI callback tests verify both attachment and native failures clear the old
  displayed selection without scanning or offering recovery candidates.

These are isolated code tests, not live gameplay acceptance. No EXE was packaged,
no game mutation was performed, and no recent user acceptance is inferred.
Other historical private diagnostic routines remain; this change does not claim
to remove every scan routine from the source or complete the overall goal.
