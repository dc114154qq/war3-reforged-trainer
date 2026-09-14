# Core regression after fixture isolation — 2026-09-14

- Branch: `codex/war3-3.0.0.24268-adaptation`
- Live process: none observed; no live game mutation was run.
- Command: `python -m pytest -q test_native_hero_progress.py test_native_hero_skill_transaction.py test_native_clone_item_guard.py test_native_clone_unit_guard.py test_native_ability_actions.py test_native_group_move.py --maxfail=1`
- Result: `223 passed, 7 subtests passed in 49.91s`.
- Scope: hero progress/skill transaction contracts, clone item/unit guards, ability actions, and group movement test harnesses.
- Product old helper remains absent from the product source/bundle; the restored C source is under `analysis/fixtures` for historical contract tests only.
