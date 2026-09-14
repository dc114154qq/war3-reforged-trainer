# Product boundary smoke — 2026-09-14

- Command: `python -m pytest -q test_24268_product_boundary.py test_24268_skill_replacement_integrity.py test_native_compatibility_read.py test_native_read_failure_routing.py test_native_table_bootstrap.py --maxfail=1`
- Result: `52 passed, 8 subtests passed in 4.39s`.
- `python -m py_compile war3_reforged_trainer.py war3_runtime_check.py` completed successfully.
- The dedicated 3.0 spec contains no retired helper binary; this is a static/package-boundary check, not a live game test.
