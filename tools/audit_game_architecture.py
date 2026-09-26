"""Emit source-derived call dependencies, explicit dynamic edges and migration boundaries."""

import ast, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from game_adapter import atomic_json
from war3_operations import OPERATIONS

ROOT = Path(__file__).resolve().parents[1]


def calls(node):
    direct = set()
    dynamic = []
    for n in ast.walk(node):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if (
            isinstance(f, ast.Attribute)
            and isinstance(f.value, ast.Name)
            and f.value.id == "self"
        ):
            direct.add(f.attr)
        elif isinstance(f, ast.Call) or isinstance(f, ast.Subscript):
            dynamic.append(ast.unparse(f))
    return sorted(direct), sorted(set(dynamic))


def main():
    source = (ROOT / "war3_reforged_trainer.py").read_text(encoding="utf8")
    tree = ast.parse(source)
    trainer = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "War3Trainer"
    )
    methods = {n.name: n for n in trainer.body if isinstance(n, ast.FunctionDef)}
    rows = {
        name: {
            "file": "war3_reforged_trainer.py",
            "line": n.lineno,
            "calls": calls(n)[0],
            "dynamic_edges": calls(n)[1],
        }
        for name, n in methods.items()
    }
    for path in sorted((ROOT / "war3_services").glob("facade_*.py")):
        for cls in ast.parse(path.read_text(encoding="utf8")).body:
            if isinstance(cls, ast.ClassDef):
                for n in cls.body:
                    if isinstance(n, ast.FunctionDef):
                        rows[n.name] = {
                            "file": path.relative_to(ROOT).as_posix(),
                            "line": n.lineno,
                            "calls": calls(n)[0],
                            "dynamic_edges": calls(n)[1],
                        }
    services = {}
    for path in sorted((ROOT / "war3_services").glob("*.py")):
        services[path.name] = [
            n.name
            for c in ast.parse(path.read_text(encoding="utf8")).body
            if isinstance(c, ast.ClassDef)
            for n in c.body
            if isinstance(n, ast.FunctionDef)
        ]
    report = {
        "baseline": "70446ba",
        "services": services,
        "methods": rows,
        "operation_catalog": {
            name: {
                "protocol": v.protocol,
                "backend": v.backend,
                "diagnostic": v.diagnostic,
                "readback_contract": v.readback,
                "replay": v.replay,
            }
            for name, v in OPERATIONS.items()
        },
        "historical": {
            "transport": "diagnostics/war3_engine_persistent_transport.py",
            "native_index": "diagnostics/war3_native_profile.py",
            "product_guard": "War3Trainer._run_native_helper_ops rejects a managed GameSession",
        },
        "remaining_version_modules": [
            "legacy_layout",
            "talents",
            "talent_icons",
            "equipment",
            "stat_details",
            "direct_effect",
        ],
        "limitations": [
            "Static call edges include compatibility branches; dynamic edges require call-site review.",
            "Legacy facade field layouts remain a pinned compiled adapter, not portable JSON-only functionality.",
            "No external-machine or real new-game-version compatibility asserted.",
        ],
    }
    atomic_json(ROOT / "build/architecture-dependencies.json", report)
    print(
        json.dumps(
            {
                "methods": len(rows),
                "services": services,
                "operations": len(OPERATIONS),
                "report": "build/architecture-dependencies.json",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
