# 2026-09-14 regression audit

## Observation
- Current branch: codex/war3-3.0.0.24268-adaptation.
- No `Warcraft III.exe` process was present at audit time; no live write test was executed.
- Targeted pytest command 1: 84 passed, 186 errors.
- Targeted pytest command 2: 157 passed, 238 errors, 3 subtests passed.
- The repeated setup error is `fatal error: .../tools/war3_native_helper.c file not found`.

## Interpretation
The errors are test-fixture construction failures, not evidence that the corresponding 3.0 feature works or fails in-game. The product tree removed the legacy helper source, but multiple tests still compile by including that path. Packaging is therefore blocked until the test fixtures are migrated to a 3.0-specific harness or explicitly separated as historical-contract tests.

## Commands
- `python -m pytest -q test_24268_product_boundary.py test_24268_skill_replacement_integrity.py test_native_clone_preparation.py test_native_clone_item_guard.py test_native_clone_unit_guard.py test_native_hero_progress.py test_native_hero_skill_transaction.py test_native_group_move.py test_native_ability_actions.py`
- `python -m pytest -q test_24268_product_boundary.py test_24268_skill_replacement_integrity.py test_native_hero_base.py test_native_all_hero_stats.py test_native_player_resources.py test_native_selected_context.py test_native_snapshot_binding.py test_native_item_create.py test_native_inventory_batch.py test_native_unit_transform.py test_native_table_bootstrap.py`
