# Resource read boundary investigation — 2026-09-14

- Source CLI against PID 38352 still returned WinError 299 for status/resource reads after page-split reads.
- Full traceback identifies `ObjectRegistry24268.attach()` reading the fixed resolver at module RVA `0x1951b0`.
- Module DOS header was readable, but reads at `base+0x1951b0` and `base+0xca741c` failed with partial-copy; this is not evidence that resource values are invalid.
- The page-split `ProcessMemory.read` change passed `test_process_access.py` and product-boundary tests, but did not eliminate this resolver-specific failure.
- No live write or mutation was executed.
