"""Emit a conservative capability matrix for the 3.0 branch."""
from __future__ import annotations
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "war3_reforged_trainer.py"


def main() -> None:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    methods: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods[node.name] = node.lineno
    matrix = [
        {"feature": "24-unit selection", "status": "14 live; 24 structural fixture", "evidence": "canonical-player-list-live.json; test_classic_player_selection.py"},
        {"feature": "resource read/write", "status": "read validated; live write pending", "evidence": "3.0 indexed player properties; test_indexed_resources.py"},
        {"feature": "coordinate write", "status": "code-routed", "evidence": "set_selected_unit_position"},
        {"feature": "hero attribute write", "status": "code-routed; live write pending", "evidence": "set_selected_hero_attributes"},
        {"feature": "inventory read", "status": "6 live items; new-unit live pending", "evidence": "3.0 slot-array pointer + registry item identities"},
        {"feature": "inventory charge write", "status": "code-routed; live write pending", "evidence": "set_selected_inventory_charges"},
        {"feature": "existing ability enumeration", "status": "validated read-only", "evidence": "ability-instances-live.json; 15/7/12 instances in live heroes"},
        {"feature": "ability field read/write", "status": "legacy native blocked", "evidence": "3.0 handler table not reconstructed"},
        {"feature": "ability add/remove/clone", "status": "legacy native blocked", "evidence": "old 2.0.4.23745 helper internals"},
        {"feature": "unit clone/copy", "status": "legacy native blocked", "evidence": "old helper create path"},
        {"feature": "mouse group move", "status": "legacy native blocked", "evidence": "group move op uses old handler"},
        {"feature": "cross-device EXE", "status": "not packaged", "evidence": "3.0 branch incomplete"},
    ]
    report = {
        "build": "3.0.0.24268",
        "branch": "codex/war3-3.0.0.24268-adaptation",
        "source": str(SOURCE),
        "methods": {name: methods[name] for name in sorted(methods) if name in {
            "_classic_selection_candidates", "read_resource_cache", "write_resource_cache",
            "set_selected_unit_position", "set_selected_hero_attributes",
            "set_selected_inventory_charges", "_ability_instances_from_candidate",
            "set_selected_unit_ability_level", "create_local_unit", "move_selected_group_to_mouse",
        }},
        "capabilities": matrix,
        "release_ready": False,
    }
    output = ROOT / "analysis" / "native-bootstrap-24268" / "capability-matrix.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
