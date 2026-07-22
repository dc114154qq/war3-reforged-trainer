"""Generate the bundled Warcraft III rawcode catalog from community snapshots.

This is a developer tool. The trainer ships the generated catalog so lookup is
offline and does not depend on a network connection or a local game install.
"""

from __future__ import annotations

import argparse
import ast
import base64
import json
import re
import zlib
from pathlib import Path
from typing import Any


SECTION_RE = re.compile(r"^\[([^]]+)\]$")


def parse_prebuilt_ini(path: Path) -> dict[str, dict[str, str]]:
    """Read only the four-character object sections and their display names."""

    objects: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        section_match = SECTION_RE.match(line)
        if section_match:
            rawcode = section_match.group(1)
            current = objects.setdefault(rawcode, {}) if len(rawcode) == 4 else None
            continue
        if current is None or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key != "name" or key in current:
            continue
        value = value.strip()
        if value.startswith('"') and value.endswith('"'):
            try:
                value = str(ast.literal_eval(value))
            except (SyntaxError, ValueError):
                value = value[1:-1].replace('\\"', '"')
        current[key] = value
    return objects


def load_flow_objects(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {str(rawcode): value for rawcode, value in raw.items()}


def category_for(kind: str, rawcode: str, english: dict[str, Any]) -> tuple[str, str]:
    if kind == "item":
        value = str(english.get("classification") or "")
        labels = {
            "Artifact": ("神器", "Artifact"),
            "Charged": ("充能物品", "Charged"),
            "Permanent": ("永久物品", "Permanent"),
            "PowerUp": ("增益物品", "Power-up"),
            "Purchasable": ("可购买物品", "Purchasable"),
            "Campaign": ("战役物品", "Campaign"),
        }
        return labels.get(value, ("其他物品", value or "Item"))
    if kind == "ability":
        if english.get("heroAbility"):
            return "英雄技能", "Hero Ability"
        if english.get("itemAbility"):
            return "物品技能", "Item Ability"
        return "普通技能", "Standard Ability"
    if english.get("isABuilding"):
        return "建筑", "Building"
    if english.get("heroSkin"):
        return "英雄", "Hero"
    return "单位", "Unit"


def make_catalog(
    zh_dir: Path,
    en_dir: Path,
    flow_dir: Path,
) -> dict[str, list[dict[str, str]]]:
    catalog: dict[str, list[dict[str, str]]] = {}
    for kind, flow_name in (
        ("item", "itemsdata.json"),
        ("ability", "abilitiesdata.json"),
        ("unit", "unitsdata.json"),
    ):
        zh = parse_prebuilt_ini(zh_dir / f"{kind}.ini")
        en = parse_prebuilt_ini(en_dir / f"{kind}.ini")
        flow = load_flow_objects(flow_dir / flow_name)
        rawcodes = set(zh) | set(en) | set(flow)
        rows: list[dict[str, str]] = []
        for rawcode in sorted(rawcodes):
            flow_object = flow.get(rawcode, {})
            name_zh = zh.get(rawcode, {}).get("name", "").strip()
            name_en = str(flow_object.get("name") or en.get(rawcode, {}).get("name", "")).strip()
            name_zh = name_zh or "（未命名/内部对象）"
            name_en = name_en or "(Unnamed / internal object)"
            category_zh, category_en = category_for(kind, rawcode, flow_object)
            rows.append(
                {
                    "rawcode": rawcode,
                    "name_zh": name_zh,
                    "name_en": name_en,
                    "category_zh": category_zh,
                    "category_en": category_en,
                }
            )
        catalog[kind] = rows
    return catalog


def write_module(output: Path, catalog: dict[str, list[dict[str, str]]]) -> None:
    payload = json.dumps(catalog, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encoded = base64.b85encode(zlib.compress(payload, level=9)).decode("ascii")
    chunks = "\n".join(f'    "{encoded[index:index + 100]}"' for index in range(0, len(encoded), 100))
    text = f'''"""Offline Warcraft III object rawcode catalog.

Generated from the fixed community snapshots below. The catalog is lookup-only;
it never writes to the game process.

- W3x2LNI zhCN-1.32.8: https://github.com/sumneko/w3x2lni/tree/82916514a12b7edb15252d42225cd8cc8ce61cfd/data/zhCN-1.32.8/prebuilt
- war3-objectdata MIT snapshot: https://github.com/flowtsohg/war3-objectdata/tree/dc5e2da21217dba8e5f750c1e867d691ab193ec1/objectdata
"""

from __future__ import annotations

import base64
import json
import zlib
from dataclasses import dataclass
from functools import lru_cache


CATALOG_SOURCE = "W3x2LNI zhCN-1.32.8 + war3-objectdata English community snapshots"
CATALOG_SOURCE_URLS = (
    "https://github.com/sumneko/w3x2lni/tree/82916514a12b7edb15252d42225cd8cc8ce61cfd/data/zhCN-1.32.8/prebuilt",
    "https://github.com/flowtsohg/war3-objectdata/tree/dc5e2da21217dba8e5f750c1e867d691ab193ec1/objectdata",
)


@dataclass(frozen=True, slots=True)
class War3IdEntry:
    rawcode: str
    name_zh: str
    name_en: str
    category_zh: str
    category_en: str


_CATALOG_B85 = (
{chunks}
)


@lru_cache(maxsize=1)
def get_id_catalog() -> dict[str, tuple[War3IdEntry, ...]]:
    raw = zlib.decompress(base64.b85decode("".join(_CATALOG_B85)))
    decoded = json.loads(raw.decode("utf-8"))
    return {{
        kind: tuple(War3IdEntry(**entry) for entry in entries)
        for kind, entries in decoded.items()
    }}


ID_CATALOG = get_id_catalog()
CATALOG_COUNTS = {{kind: len(entries) for kind, entries in ID_CATALOG.items()}}


def search_id_entries(kind: str, query: str = "") -> tuple[War3IdEntry, ...]:
    entries = ID_CATALOG.get(kind, ())
    needle = query.strip().casefold()
    if not needle:
        return entries
    return tuple(
        entry
        for entry in entries
        if needle in entry.rawcode.casefold()
        or needle in entry.name_zh.casefold()
        or needle in entry.name_en.casefold()
        or needle in entry.category_zh.casefold()
        or needle in entry.category_en.casefold()
    )
'''
    output.write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zh-dir", type=Path, required=True)
    parser.add_argument("--en-dir", type=Path, required=True)
    parser.add_argument("--flow-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    catalog = make_catalog(args.zh_dir, args.en_dir, args.flow_dir)
    write_module(args.output, catalog)
    print({kind: len(entries) for kind, entries in catalog.items()})


if __name__ == "__main__":
    main()
