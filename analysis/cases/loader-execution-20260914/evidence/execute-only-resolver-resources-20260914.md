# 3.0 execute-only resolver compatibility — 2026-09-14

- PID: `38352`, executable `E:\Warcraft III\_retail_\x86_64\Warcraft III.exe`.
- Current resolver page is execute-only (`PAGE_EXECUTE`), so external code-byte verification returns ERROR_PARTIAL_COPY (299).
- `ObjectRegistry24268` now accepts this case only after exact PE fingerprint validation and still performs the readable player-accessor code check; no process scan fallback was added.
- Regression: `17 passed` (`test_24268_product_boundary.py`, `test_native_selected_context.py`).
- Live CLI `--status --list-resources`: batch resource enumeration succeeded with 28 resource groups; group 1 reported gold 997469, lumber 999839, food 38/72; group 2 reported gold 997329, lumber 999571, food 37/41. Remaining groups were enumerated through player 27.
- The single local-resource shortcut still returned ERROR_PARTIAL_COPY 299; it is not marked passed.
- No memory write, native mutation, clone, skill, item, or elephant operation was executed.
