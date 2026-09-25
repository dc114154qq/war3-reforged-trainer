"""Generate a read-only, source-traceable catalog from extracted campaign data."""
from __future__ import annotations

import argparse
from collections import defaultdict
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_war3_casc_catalog import _split_slk, _cell_value


def slk(path):
    cells = defaultdict(dict)
    x = y = 0
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.startswith("C;"):
            continue
        value = None
        for token in _split_slk(line)[1:]:
            if token.startswith("X"):
                x = int(token[1:])
            elif token.startswith("Y"):
                y = int(token[1:])
            elif token.startswith("K"):
                value = _cell_value(token)
        if value is not None:
            cells[y][x] = value
    header = cells.pop(1)
    return [{header[x]: value for x, value in row.items() if x in header} for _, row in sorted(cells.items())]


def sections(path):
    result, current = {}, None
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            current = result.setdefault(line[1:-1], {})
        elif current is not None and "=" in line and not line.startswith("//"):
            key, value = line.split("=", 1)
            current[key] = value.strip().strip('"')
    return result


def objects(path, extended=False):
    data, offset = path.read_bytes(), 0

    def integer():
        nonlocal offset
        value = struct.unpack_from("<i", data, offset)[0]
        offset += 4
        return value

    def fourcc():
        nonlocal offset
        value = data[offset:offset + 4].decode("ascii")
        offset += 4
        return value

    version = integer()
    if version not in (1, 2, 3):
        raise ValueError(f"Unsupported object version {version}: {path}")
    result = []
    for _table in range(2):
        count = integer()
        if not 0 <= count <= 100000:
            raise ValueError("Invalid object count")
        for _ in range(count):
            old, new = fourcc(), fourcc()
            if version == 3:
                extra = integer()
                if not 0 <= extra <= 1024:
                    raise ValueError("Invalid object metadata count")
                for _ in range(extra):
                    integer()
            mods = []
            for _ in range(integer()):
                field, typ = fourcc(), integer()
                level, pointer = (integer(), integer()) if extended else (0, 0)
                if typ == 0:
                    value = integer()
                elif typ in (1, 2):
                    value = struct.unpack_from("<f", data, offset)[0]
                    offset += 4
                elif typ == 3:
                    end = data.index(0, offset)
                    value = data[offset:end].decode("utf-8")
                    offset = end + 1
                else:
                    raise ValueError(f"Unknown modification type {typ}")
                end_id = fourcc()
                if end_id not in (old, new, "\0" * 4):
                    raise ValueError("Object modification terminator differs")
                mods.append((field, value, level, pointer))
            result.append((old, new if new.strip("\0") else old, mods))
    if offset != len(data):
        raise ValueError(f"Unparsed object bytes: {path}: {offset}/{len(data)}")
    return result


def wts(path):
    if not path.exists():
        return {}
    return dict(re.findall(r"STRING\s+(\d+)\s*\{\r?\n(.*?)\r?\n\}", path.read_text(encoding="utf-8-sig"), re.S))


REFERENCE = re.compile(r"<([^,<>]+),([^,<>]+)(,%)?>")


def text(raw, values):
    def substitute(match):
        obj, field, percent = match.groups()
        value = values.get(obj, {}).get(field)
        if value is None:
            return f"【未解析:{obj},{field}{percent or ''}】"
        try:
            number = Decimal(str(value)) * (100 if percent else 1)
            return format(number.quantize(Decimal('0.000001')).normalize(), 'f')
        except InvalidOperation:
            return str(value)
    result = REFERENCE.sub(substitute, str(raw))
    result = re.sub(r"\|c[0-9a-fA-F]{8}|\|r", "", result)
    result = result.replace("|n", "\n").replace("\\n", "\n")
    return result.strip()


def generate(case, base, destination):
    items = {r['itemID']: r for r in slk(base / 'ItemData.slk') if r.get('itemID')}
    abilities = {r['alias']: r for r in slk(base / 'AbilityData.slk') if r.get('alias')}
    names = sections(case / 'casc/ItemStrings.txt')
    grouped = defaultdict(dict)
    source_files = [base / 'ItemData.slk', base / 'AbilityData.slk', case / 'casc/ItemStrings.txt']
    for chapter in sorted((case / 'maps').iterdir()):
        local = {key: dict(value) for key, value in items.items()}
        local_names = {key: dict(value) for key, value in names.items()}
        strings = wts(chapter / 'war3map.wts')
        strings.update(wts(chapter / '_Locales/zhCN.w3mod/war3map.wts'))
        referenced = set()
        for script in chapter.glob('*.lua'):
            referenced.update(re.findall(r'''["']([!-~]{4})["']''', script.read_text(encoding='utf-8-sig')))
            source_files.append(script)
        for filename in ('war3map.w3t', 'war3mapSkin.w3t'):
            path = chapter / filename
            if not path.exists():
                continue
            source_files.append(path)
            for old, code, mods in objects(path):
                referenced.add(code)
                if code not in local:
                    local[code] = dict(local.get(old, {}))
                    local_names[code] = dict(local_names.get(old, {}))
                for field, value, _level, _pointer in mods:
                    if isinstance(value, str) and value.startswith('TRIGSTR_'):
                        value = strings.get(value[8:], f'【未解析:{value}】')
                    key = {'unam': 'Name', 'utip': 'Tip', 'utub': 'Ubertip', 'ides': 'Description'}.get(field)
                    if key:
                        local_names.setdefault(code, {})[key] = value
                    if field == 'iabi':
                        local[code]['abilList'] = value
        values = {**local, **abilities}
        # Never substitute global ability values if a chapter overrides a
        # referenced ability. Extend the resolver first in that case.
        used_refs = {m[0] for code in referenced if local.get(code, {}).get('class') == 'Equipment'
                     for m in REFERENCE.findall(local_names.get(code, {}).get('Ubertip', ''))}
        for ability_file in ('war3map.w3a', 'war3mapSkin.w3a'):
            path = chapter / ability_file
            if not path.exists():
                continue
            source_files.append(path)
            for _old, code, mods in objects(path, extended=True):
                if code in used_refs and mods:
                    raise ValueError(f'Unresolved chapter ability override: {chapter.name}/{code}')
        for code in sorted(referenced):
            item = local.get(code, {})
            if item.get('class') != 'Equipment':
                continue
            entry = local_names.get(code, {})
            name = text(entry.get('Name', item.get('comment', code)), values)
            description = text(entry.get('Ubertip', entry.get('Description', '效果说明缺失')), values)
            key = (name, description, item.get('equipment', ''))
            grouped[code].setdefault(key, []).append(chapter.name)
        source_files.extend(chapter.rglob('*.wts'))
    rows = []
    for code, variants in sorted(grouped.items()):
        for (name, description, slot), chapters in variants.items():
            rows.append(dict(code=code, name=name, description=description, slot=slot, chapters=chapters))
    report = dict(campaign_sha256=json.loads((case / 'extraction.json').read_text(encoding='utf-8'))['source_sha256'],
                  count=len(rows), distinct_codes=len(grouped), unresolved=[r['code'] for r in rows if '【未解析:' in r['description']],
                  sources={str(p.relative_to(case)) if p.is_relative_to(case) else str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files})
    body = '"""Generated campaign equipment, not a claim of availability in every map."""\n\n'
    body += 'CAMPAIGN_SHA256 = ' + repr(report['campaign_sha256']) + '\n'
    body += 'EQUIPMENT = (\n' + ''.join('    ' + repr(row) + ',\n' for row in rows) + ')\n'
    for path, data in ((destination, body), (case / 'catalog-audit.json', json.dumps(report, ensure_ascii=False, indent=2))):
        tmp = path.with_name(path.name + '.tmp')
        tmp.write_text(data, encoding='utf-8')
        os.replace(tmp, path)
    print(json.dumps({k: report[k] for k in ('count', 'distinct_codes', 'unresolved')}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('case', type=Path)
    parser.add_argument('base', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    generate(args.case, args.base, args.destination)
