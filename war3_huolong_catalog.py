"""Resolve chapter object data for the self-contained HKE main-menu catalogue."""
from copy import deepcopy
import re

from war3_map_objects import plain_text
from war3_map_catalog_reference import reference
from war3_services.map_catalog import baseline, get_value, location, put_value

KINDS = ('item', 'ability', 'unit', 'upgrade')


def _number(value, default=1):
    try:
        return max(0, min(100000, int(float(value))))
    except (TypeError, ValueError, OverflowError):
        return default


def catalogue_entries(catalogue, scope, mode, known, protected_items, protected_abilities):
    """Apply shared, chapter and skin differences in their resolved source order."""
    state = deepcopy(baseline(mode))
    custom = set()
    for area in ('战役共用', scope):
        pending = [r for r in catalogue['rows'] if r['scope'] == area and r['kind'] in KINDS]
        while pending:
            available = {(r['kind'], r['rawcode']) for r in pending}
            ready = [r for r in pending if r['base'] == r['rawcode'] or
                     (r['kind'], r['base']) not in available or r['base'] in state[r['kind']]]
            if not ready:
                raise ValueError('火龙目录的物编继承存在循环，未输出副本。')
            for row in ready:
                kind, code = row['kind'], row['rawcode']
                attrs = state[kind].setdefault(code, deepcopy(state[kind].get(row['base'], {})))
                custom.add((kind, code))
                for change in row['changes']:
                    if change['storage'] == 'table':
                        attrs[change['field'].casefold()] = deepcopy(change['value'])
                    else:
                        meta = reference()['metadata'][kind].get(change['field'])
                        if meta:
                            key, index = location(meta, change['level'])
                            put_value(attrs, key, index, change['value'])
                pending.remove(row)

    def expand(match):
        fields = next((objects[match[1]] for objects in state.values() if match[1] in objects), {})
        value = get_value(fields, match[2].casefold())
        if value is None:
            return match[0]
        if match[3]:
            try:
                value = format(float(value) * 100, '.8g')
            except (TypeError, ValueError):
                return match[0]
        return str(value)

    result = []
    gold = []
    for kind in KINDS:
        for code, attrs in sorted(state[kind].items()):
            if not re.fullmatch(r'[A-Za-z0-9_]{4}', code):
                continue
            if kind == 'ability' and attrs.get('code') in ('Agld', 'Abgm'):
                gold.append(code)
            if code not in known.get(kind, ()):
                continue
            if kind == 'item' and code in protected_items or kind == 'ability' and code in protected_abilities:
                continue
            name = plain_text(get_value(attrs, 'name', 0) or code).strip()
            description = ''
            for key in ('ubertip', 'description', 'researchubertip', 'tip'):
                values = attrs.get(key)
                if values:
                    values = values if isinstance(values, list) else [values]
                    description = '\n'.join((str(i+1)+'级：' if len(values) > 1 else '') +
                        plain_text(re.sub(r'<([^,<>]+),([^,<>]+)(,%)?>', expand, str(v)))
                        for i, v in enumerate(values) if v)
                    if description:
                        break
            if kind == 'unit' and code[0].isupper():
                names = attrs.get('propernames')
                if names:
                    description += '\n英雄本名：' + '、'.join(names if isinstance(names, list) else [str(names)])
            level = _number(attrs.get('levels') if kind == 'ability' else attrs.get('maxlevel'), 1)
            abilities = str(get_value(attrs, 'abillist') or '').split(',')
            unsafe_unit = kind == 'unit' and any(a.strip() in set(protected_abilities)-
                set(known.get('ordinary_inventory', ())) or a.strip() == 'Aloc' for a in abilities)
            result.append(dict(kind=kind, rawcode=code, name=name, description=description.strip(),
                maxLevel=level if kind in ('ability', 'upgrade') else 1,
                custom=(kind, code) in custom, powerup=_number(get_value(attrs, 'powerup'), 0) > 0,
                charges=_number(get_value(attrs, 'uses'), 0), droppable=_number(get_value(attrs, 'droppable'), 1) > 0,
                unsafe=unsafe_unit))
    known['gold_mines'] = sorted(set(gold) | {'Agld', 'Abgm'})
    return result
