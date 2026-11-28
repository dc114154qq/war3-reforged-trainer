"""Optional native equipment slots for recognisable legacy items in archive copies."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
import re
from secrets import choice
import struct

from war3_map_catalog_reference import reference
from war3_map_objects import decode_text, object_records, plain_text, profile, resolve_string, strings
from war3_mpq import Archive, unknown_member_name
from war3_object_tables import DefinitionError, _tokens, _value, map_data_mode, parse_slk, validate_game_slk

BACKPACK_ONLY = 'backpack_only'
WITH_LEGACY_EQUIPMENT = 'legacy_equipment'

LEGACY_CLASSES = {'permanent', 'artifact', 'miscellaneous', 'purchasable'}
EMPTY = {'', '-', '_', 'none', '0'}
ITEM_FIELDS = {
    'icla': 'class', 'iequ': 'equipment', 'iabi': 'abilList', 'iusa': 'usable',
    'iper': 'perishable', 'ipow': 'powerup', 'iuse': 'uses', 'idro': 'droppable',
    'unam': 'name', 'ides': 'description', 'utub': 'ubertip',
}
SLOT_WORDS = {
    'Head': ('头盔|头环|头冠|王冠|兜帽|面罩|面具|帽子', r'helm(?:et)?|circlet|crown|hood|mask|headband'),
    'Chest': ('胸甲|铠甲|护甲|锁甲|鳞甲|披风|斗篷|长袍|战袍|法袍', r'chestplate|breastplate|armor|armour|cloak|cape|robe|mail|cuirass'),
    'Gloves': ('手套|护手|拳套|护腕|攻击之爪', r'gloves?|gauntlets?|bracers?|claws? of attack'),
    'Boots': ('靴|便鞋|战鞋|长鞋', r'boots?|slippers?|sandals?|greaves|shoes'),
    'Ring': ('戒指|指环|之戒|王戒|魔戒', r'rings?|signet|band'),
    'Primary': ('战刃|长剑|短剑|巨剑|宝剑|军刀|弯刀|匕首|战斧|巨斧|长弓|短弓|弩|长矛|长枪|战锤|重锤|法杖|权杖|魔杖', r'swords?|blades?|glaives?|daggers?|axes?|bows?|crossbows?|spears?|hammers?|staff|staves|wand|mace'),
    'Offhand': ('盾牌|护盾|圆盾|塔盾|之盾', r'shields?|bucklers?'),
    'Trinket': ('饰品|护符|坠饰|吊坠|项链|勋章|徽记|烟斗', r'amulets?|talismans?|pendants?|necklaces?|trinkets?|medallions?|pipe of insight'),
}
GEAR_NAME = re.compile('|'.join(rf'{zh}|\b(?:{en})\b' for zh, en in SLOT_WORDS.values()), re.I)
QUEST_TEXT = re.compile(
    r'(?:任务|任務|剧情|劇情)(?:物品|道具|专用|專用|用品|所需)|钥匙|鑰匙|密钥|密鑰|交给|交給|'
    r'交予|交付|上交|交还|交還|归还|歸還|信件|给.{1,12}的信|給.{1,12}的信|信物|'
    r'(?:用于|用於|用来|用來|可用来|可用來)(?:开启|開啟|打开|打開|解锁|解鎖)|'
    r'\b(?:quest[- ](?:item|object|token)|key|letter|proof of (?:identity|passage)|'
    r'(?:deliver|return|bring|hand over) (?:it|this)|turn (?:it|this) in|(?:used|needed|required) to unlock)\b|'
    r'квестов\w+|ключ|письмо|objeto de misi[oó]n|objet de qu[eê]te', re.I)
RAWCODE_WORD = re.compile(r'(?<![A-Za-z0-9])[A-Za-z0-9]{4}(?![A-Za-z0-9])')
SCRIPT_TOKEN = re.compile(
    r"(?P<comment>/\*[\s\S]*?\*/|--\[(?P<comment_eq>=*)\[[\s\S]*?\](?P=comment_eq)\]|//[^\r\n]*|--[^\r\n]*)"
    r"|(?P<longstring>\[(?P<string_eq>=*)\[[\s\S]*?\](?P=string_eq)\])"
    r"""|(?P<string>"(?:\\.|[^"\\\r\n])*"|'(?:\\.|[^'\\\r\n])*')"""
    r"|(?P<number>(?<![\w.])(?:0x[0-9a-f]+|\$[0-9a-f]+|[0-9]{9,})(?![\w.]))", re.I)
LUA_ESCAPE = re.compile(r'\\(?:x([0-9a-fA-F]{2})|([0-9]{1,3})|u\{([0-9a-fA-F]{1,8})\}|(.))')
CATEGORY = re.compile(r'\bITEM_TYPE_([A-Z_]+)\b')
CATEGORY_API = re.compile(r'\b(?:ChooseRandomItemEx(?:WithFilter)?|GetItemType|IsItemIdType|IsItemType|ConvertItemType)\s*\(')
DYNAMIC_SCRIPT = re.compile(r'\b(?:dofile|loadfile|require|loadstring|load)\s*\(')
SCRIPT_SUFFIXES = ('.j', '.lua', '.ai', '.vj', '.zn', '.jass')
MAP_SCRIPTS = ('war3map.j', 'war3map.lua', 'war3map.wct')
CAMPAIGN_SCRIPTS = ('war3campaign.j', 'war3campaign.lua', 'war3campaign.wct')


def validate_mode(mode):
    if mode not in (BACKPACK_ONLY, WITH_LEGACY_EQUIPMENT):
        raise DefinitionError('请选择有效的背包定义处理方式。')
    return mode


@dataclass
class Scope:
    tables: dict[str, bytes] = field(default_factory=dict)
    records: dict[str, list] = field(default_factory=lambda: defaultdict(list))
    profiles: dict[str, dict] = field(default_factory=dict)
    texts: dict = field(default_factory=dict)
    ambiguous: set[str] = field(default_factory=set)
    script_readable: bool = True
    script_items: set[str] = field(default_factory=set)
    script_categories: set[str] = field(default_factory=set)


def item_scope(archive, prefix, parent_texts=None):
    scope = Scope(texts={**(parent_texts or {}), **strings(archive.read(prefix+'.wts', optional=True), tolerant=True)})
    for stem in (prefix, prefix+'Skin'):
        filename = stem+'.w3t'
        raw = archive.read(filename, optional=True)
        if raw is None:
            continue
        scope.tables[filename] = raw
        seen = set()
        for record in object_records(raw):
            code = record['rawcode']
            if code in seen:
                scope.ambiguous.add(code)
            seen.add(code)
            scope.records[code].append((filename, record))
    for filename in ('Units\\ItemFunc.txt', 'Units\\ItemSkin.txt'):
        raw = archive.read(filename, optional=True)
        if raw is not None:
            for code, fields in profile(raw).items():
                scope.profiles.setdefault(code, {}).update(fields)
    if prefix == 'war3campaign':
        scope.script_readable, scope.script_items, scope.script_categories = script_protection(archive, None)
    return scope


def _lua_escape(match):
    hex_byte, decimal, unicode_code, escaped = match.groups()
    if escaped is not None:
        return escaped
    number = int(decimal) if decimal else int(hex_byte or unicode_code, 16)
    return chr(number) if number <= 0x10ffff else '\ufffd'


@lru_cache(maxsize=64)
def _script_references(raw, lua):
    text = decode_text(raw)
    # Covers literal text too, including comments and editor names such as
    # gg_item_I001_0001. Rawcodes are case-sensitive in object data.
    protected = set(RAWCODE_WORD.findall(text))
    clean = []
    start = 0
    for match in SCRIPT_TOKEN.finditer(text):
        if match.lastgroup == 'number':
            value = match[0].lower()
            digits = value.removeprefix('0x').removeprefix('$').lstrip('0')
            base = 16 if value.startswith(('0x', '$')) else 10
            if digits and len(digits) <= (8 if base == 16 else 10):
                number = int(digits, base)
                if number <= 0xffffffff:
                    protected.add(number.to_bytes(4, 'big').decode('latin1'))
            continue
        if match.lastgroup == 'string':
            inner = match[0][1:-1]
            if lua and '\\' in inner:
                inner = LUA_ESCAPE.sub(_lua_escape, inner)
            if len(inner) == 4:
                protected.add(inner)
            protected.update(RAWCODE_WORD.findall(inner))
        clean.append(text[start:match.start()])
        # Keep line boundaries for item category checks.
        clean.append(' ' + '\n' * match[0].count('\n'))
        start = match.end()
    clean.append(text[start:])
    script = ''.join(clean)
    categories = set()
    for match in CATEGORY_API.finditer(script):
        end = script.find('\n', match.end())
        line = script[script.rfind('\n', 0, match.start())+1:end if end >= 0 else len(script)]
        categories.update({category.casefold() for category in CATEGORY.findall(line)} or {'any'})
    return frozenset(protected), frozenset(categories), lua and DYNAMIC_SCRIPT.search(script) is not None


def script_protection(archive, script_language):
    standard = CAMPAIGN_SCRIPTS if script_language is None else MAP_SCRIPTS
    paths = set(standard) | {'scripts\\' + name for name in standard}
    primary = None if script_language is None else standard[int(bool(script_language))]
    entrypoints = {primary, 'scripts\\'+primary} if primary else set()
    names = {member.name.casefold().replace('/', '\\') for member in archive.members()
             if not unknown_member_name(member.name) and member.name.casefold().endswith(SCRIPT_SUFFIXES)}
    present, external = primary is None, False
    protected, categories = set(), set()
    for name in sorted(paths | names):
        raw = archive.read(name, optional=True)
        if raw is None:
            external |= name in names
            continue
        if not raw.strip():
            continue
        present |= name in entrypoints
        if name.endswith('.wct'):
            # Trigger source is a binary container. The compiled script is
            # checked separately, and rawcode words in disabled triggers
            # and trigger comments are still protected.
            protected.update(RAWCODE_WORD.findall(raw.decode('latin1')))
            continue
        codes, kinds, loads_script = _script_references(raw, name.endswith('.lua'))
        protected.update(codes)
        categories.update(kinds)
        external |= loads_script
    return present and not external, protected, categories


def scope_values(layers, tables, code):
    """Resolve one item's inherited data while respecting map and skin overrides."""
    entries = [entry for scope in layers for entry in scope.records.get(code, ())]
    row = tables.get(code)
    if row is None:
        bases = {item['base'] for _, item in entries if item['base'] != code}
        if len(bases) == 1:
            base, = bases
            # A custom parent can itself have map-dependent overrides. Only
            # promote objects with a direct and identifiable base template.
            if not any(any(r['base'] != base for _, r in scope.records.get(base, ())) for scope in layers):
                row = tables.get(base)
            if row is not None:
                # A renamed custom object can intentionally use a completely
                # different slot. The inherited stock name is not evidence.
                values = scope_values(layers, tables, base)
                for key in ('name', 'description', 'ubertip', 'comment'):
                    values.pop(key, None)
            else:
                return {}
        else:
            return {}
    else:
        values = {key: _value(token) for key, token in row.items()}
        names = reference()['profiles']['enUS']['item'].get(code, {})
        for key in ('name', 'description', 'ubertip'):
            text = names.get(key, [])
            if text:
                values[key] = text[0]
    for scope in layers:
        for key, text in scope.profiles.get(code, {}).items():
            if key in ('name', 'description', 'ubertip') and text:
                values[key] = resolve_string(text[0], scope.texts)
        for _, record in scope.records.get(code, ()):
            for change in record['changes']:
                key = ITEM_FIELDS.get(change['field'])
                if key:
                    values[key] = resolve_string(change['value'], scope.texts)
    return values


def equipment_exclusion(values, protected, categories):
    def get(field_name):
        return str(values.get(field_name, '')).strip().casefold()

    classification = get('class')
    if get('equipment') not in EMPTY or classification == 'equipment':
        return 'already_equipment'
    if protected:
        return 'script_item_reference'
    text = [plain_text(values.get(key, '')) for key in ('name', 'description', 'ubertip', 'comment')]
    if classification in ('campaign', 'quest') or get('droppable') in ('0', 'false') or any(QUEST_TEXT.search(value) for value in text):
        return 'quest_or_restricted_item'
    if classification in ('charged', 'powerup') or any(
        get(key) not in ('', '0', 'false', '-', '_') for key in ('usable', 'perishable', 'powerup', 'uses')
    ):
        return 'active_or_consumable'
    if classification not in LEGACY_CLASSES or get('abilList') in EMPTY:
        return 'unrecognised'
    if 'any' in categories or classification in categories:
        return 'script_item_category'
    if any(re.fullmatch(r'TRIGSTR_\d+', value.strip(), re.I) for value in text):
        return 'unresolved_item_text'
    if not GEAR_NAME.search((text[0] or text[-1]).split('\n',1)[0]):
        return 'unrecognised_gear_name'
    return ''


def _edit_w3t(raw, slots):
    positions = []
    before = object_records(raw, positions=positions)
    edits = []
    for record, position in zip(before, positions, strict=True):
        code = record['rawcode']
        if code not in slots:
            continue
        count_at, end, spans = position
        desired = {'icla': 'Equipment', 'iequ': slots[code]}
        inserted = []
        for field_name, value in desired.items():
            old = [i for i, change in enumerate(record['changes']) if change['field'] == field_name]
            if not old:
                inserted.append(field_name.encode()+struct.pack('<i',3)+value.encode()+bytes(5))
                continue
            for index in old:
                start, stop = spans[index]
                terminator = raw[stop-4:stop]
                edits.append((start, stop, field_name.encode()+struct.pack('<i',3)+value.encode()+b'\0'+terminator))
        if inserted:
            edits.append((count_at, count_at+4, struct.pack('<i',len(spans)+len(inserted))))
            edits.append((end, end, b''.join(inserted)))
    chunks = []
    offset = 0
    for start, stop, replacement in sorted(edits):
        if start < offset:
            raise DefinitionError('装备字段的位置冲突，已停止修改物品数据。')
        chunks.extend((raw[offset:start], replacement))
        offset = stop
    chunks.append(raw[offset:])
    result = b''.join(chunks)
    right = object_records(result)
    def without_slots(record):
        return {**record, 'changes':[c for c in record['changes'] if c['field'] not in ('icla','iequ')]}
    if len(right)!=len(before):
        raise DefinitionError('补完装备部位后，物品记录数量不一致。')
    for old, new in zip(before, right, strict=True):
        code = old['rawcode']
        if code in slots:
            fields = {c['field']:c['value'] for c in new['changes']}
            valid = (without_slots(old)==without_slots(new)
                     and fields.get('icla')=='Equipment' and fields.get('iequ')==slots[code])
        else:
            valid = old==new
        if not valid:
            raise DefinitionError('补完装备部位后，物品原有字段校验失败。')
    return result


def slot_table(raw, slots):
    if not slots:
        return raw
    before = parse_slk(raw)
    names = {name:col for col,name in before.columns.items()}
    col = names.get('equipment', before.max_x+1)
    positions = {before.row_numbers[key]:key for key in slots}
    class_col = names.get('class')
    if class_col is None:
        raise DefinitionError('物品表缺少物品分类，无法补写装备部位。')
    x = y = 0
    lines, changed = [], defaultdict(set)
    for line in raw.decode('latin1').splitlines():
        if line.startswith('C;'):
            tokens = _tokens(line)
            for token in tokens[1:]:
                if token.startswith('X'):
                    x = int(token[1:])
                elif token.startswith('Y'):
                    y = int(token[1:])
            if y in positions and x in (col, class_col):
                value = slots[positions[y]] if x == col else 'Equipment'
                for index, token in enumerate(tokens):
                    if token.startswith('K'):
                        tokens[index] = f'K"{value}"'
                        changed[y].add(x)
                line = ';'.join(tokens)
        lines.append(line)
    extra = []
    if 'equipment' not in names:
        extra.append(f'C;X{col};Y1;K"equipment"')
        bounds = [index for index,line in enumerate(lines) if line.startswith('B;')]
        if len(bounds)!=1:
            raise DefinitionError('物品表边界不明确，无法补写装备部位。')
        i, = bounds
        lines[i] = re.sub(r';X\d+', f';X{col}', lines[i])
    for number, code in positions.items():
        if class_col not in changed[number]:
            extra.append(f'C;X{class_col};Y{number};K"Equipment"')
        if col not in changed[number]:
            extra.append(f'C;X{col};Y{number};K"{slots[code]}"')
    newline = '\r\n' if b'\r\n' in raw else '\n'
    result = (newline.join(lines[:-1]+extra+['E'])+newline).encode('latin1')
    after = validate_game_slk(result)
    expected = {code:dict(row) for code,row in before.rows.items()}
    for code, slot in slots.items():
        expected[code].update({'class':'K"Equipment"', 'equipment':f'K"{slot}"'})
    if after.rows!=expected or after.opaque!=before.opaque:
        raise DefinitionError('补完装备部位后，原物品表字段校验失败。')
    return result


@dataclass
class PromotionPlan:
    tables: dict[str, bytes] = field(default_factory=dict)
    slots: dict[str, str] = field(default_factory=dict)


def plan_legacy_equipment(chapters, campaign, inherited, definition_files, journal):
    """Draw one slot per ID for the entire campaign copy."""
    chapter_scopes = []
    protected, categories = set(campaign.script_items), set(campaign.script_categories)
    missing_scripts = [] if campaign.script_readable else ['war3campaign']
    @lru_cache(maxsize=16)
    def table_rows(raw):
        return parse_slk(raw).rows

    for name, path in chapters:
        journal.event('legacy_equipment_scan', name=name)
        with Archive(path) as archive:
            metadata = map_data_mode(archive.read('war3map.w3i'))
            raw = archive.read('Units\\ItemData.slk', optional=True) or inherited.get('units\\itemdata.slk')
            if raw is None:
                raw = definition_files['baseline/'+metadata['mode']+'/ItemData.slk']
            table = table_rows(raw)
            local = item_scope(archive, 'war3map', campaign.texts)
            readable, by_id, by_category = script_protection(archive, metadata['script_language'])
            if not readable:
                missing_scripts.append(name)
            protected.update(by_id)
            categories.update(by_category)
            chapter_scopes.append((name, table, local))
    if missing_scripts:
        item_ids = set(campaign.records)
        for _, table, local in chapter_scopes:
            item_ids.update(table)
            item_ids.update(local.records)
        referenced_items = sorted(item_ids & protected)
        return {}, {}, dict(converted={}, skipped=dict.fromkeys(referenced_items, 'script_item_reference'),
                            reason='script_unavailable', chapters=missing_scripts,
                            script_protected=referenced_items, assignment='random_per_item_id')

    parent_ids = {
        record['base']
        for scope in (campaign, *(local for _, _, local in chapter_scopes))
        for code, records in scope.records.items()
        for _, record in records
        if record['base'] != code
    }
    eligible, skips = {}, {}
    for _, table, local in chapter_scopes:
        journal.check()
        for code in dict.fromkeys((*table, *campaign.records, *local.records)):
            if code in skips:
                continue
            if code in protected:
                skips[code] = 'script_item_reference'
                continue
            values = scope_values((campaign, local), table, code)
            # A campaign can contain maps using another data set, with no
            # stock row for this ID. A map-local ID may also be absent elsewhere.
            if not values and code not in local.records:
                continue
            reason = equipment_exclusion(values, False, categories)
            if code in campaign.ambiguous or code in local.ambiguous:
                reason = 'duplicate_object'
            if not reason and code in parent_ids:
                reason = 'used_as_template'
            if not reason and any(
                entries and (all(name.endswith('Skin.w3t') for name, _ in entries)
                             or any(name.endswith('Skin.w3t') and any(
                                 c['field'] in ('icla','iequ') for c in record['changes'])
                                    for name, record in entries))
                for entries in (campaign.records.get(code), local.records.get(code))
            ):
                reason = 'skin_override'
            if reason:
                skips[code] = reason
            else:
                eligible.setdefault(code, values.get('name') or values.get('comment') or code)
    slots = tuple(SLOT_WORDS)
    approved = {code:choice(slots) for code in sorted(eligible.keys() - skips.keys())}
    def patches(scope, codes):
        by_file = defaultdict(dict)
        for code in codes & approved.keys():
            filename = next(name for name, _ in scope.records[code] if not name.endswith('Skin.w3t'))
            by_file[filename][code] = approved[code]
        return {path: _edit_w3t(scope.tables[path], slots) for path,slots in by_file.items()}
    campaign_tables = patches(campaign, campaign.records.keys())
    chapter_plans = {}
    for name, table, local in chapter_scopes:
        slk_slots = {code:approved[code] for code in table.keys() & approved.keys()
                     if code not in campaign.records and code not in local.records}
        chapter_plans[name] = PromotionPlan(patches(local, local.records.keys()), slk_slots)
    return campaign_tables, chapter_plans, dict(
        converted={code:dict(slot=slot, name=eligible[code]) for code,slot in sorted(approved.items())},
        skipped=dict(sorted(skips.items())), script_protected=sorted(protected & skips.keys()),
        protected_categories=sorted(categories), assignment='random_per_item_id')

