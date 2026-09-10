# Native table refresh: measured cost and reload behavior

2026-09-10; production source 3bb9e63, audit branch
`codex/v1.0.19-bootstrap-refresh-audit`. No production changes, DLL rebuild or
EXE packaging in this step. App stays 1.0.19, helper protocol 66. Last accepted
gameplay artifact is still 1.0.19-924dd59.

## Decision

Keep the current per-command refresh. There is no evidence here that its bounded
55-native lookup is responsible for perceptible action latency, and skipping
refresh would weaken validation when the game context/table changes. Do not add
a pointer-only cache or lengthen validation intervals on the basis of speculation.

Five samples of 1000 successful refreshes each measured 90.9321, 96.6377, 99.0554,
96.0976 and 93.6797 microseconds per refresh; median **96.0976 microseconds**.
The test runs the production context lookup, binding loop, native-table search,
signature/RVA/executable checks, code fingerprint and transactional publication.
Native fingerprints are the actual captured 23745 .text bytes, whose SHA-256 is
verified before use. The context getter and name hash are deterministic test
callbacks, the table has no hash collisions, and memory is local/test allocated.
Therefore this is neither real game latency nor a bound on a collision-heavy
game table. It does not include IPC, hook scheduling, native actions or cold
image validation. No test uses a fragile latency pass/fail threshold.

## Reload and failure evidence

The new fixture executes production `war3_bootstrap_refresh` on two separately
allocated context/table layouts with the same loaded-image base. A switch to a
valid second table rebinds all 55 functions. Null context, missing first/middle/
last native, wrong signature, changed handler address, changed code, malformed
bucket mask and a collision cycle all cause failure and clear ready state.

Before failure tests, existing handlers are replaced with distinct sentinel
values. A late failing binding must leave every sentinel unchanged, proving
that no prefix of new results was published. Restoring the original context
and code must restore all 55 validated handlers and ready state. Source review
confirms `run_command` exits on refresh error before dispatching its operation;
this test directly exercises refresh, rather than claiming to inject a real
map reload into a running command.

The synthetic image models a previously image-validated module, as in repeated
commands in one game process. Native code bytes are read for validation, not
executed. Existing `test_native_table_bootstrap.py` separately checks captured
PE/code validation, wrong build and malformed bucket lookup. The combined run
passed **42 tests in 5.46 seconds**. All production code remained unchanged, so
the preceding full 1524-test regression was not repeated. Fixture setup requires
the locally preserved captured .text evidence and explicitly skips if absent.

Evidence: `test_native_bootstrap_refresh.py`,
`analysis/native-bootstrap-refresh-measurement.json`, local ignored log
`analysis/native-bootstrap-refresh-audit.log`.

## Next action toward the original goal

Continue auditing selected-unit action paths and required field coverage. Treat
the old Python machine-code inspection found in item replacement as the model of
a demonstrated dependency worth migrating; do not substitute cosmetic caching
for the DLL architecture. The pending native slot resolver and entrypoint changes
remain distinct from the accepted gameplay EXE. The full goal is not complete.
