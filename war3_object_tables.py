"""Lossless additions to Warcraft object tables and bounded map metadata reads."""
from __future__ import annotations
from dataclasses import dataclass
import re
import struct


class DefinitionError(ValueError):
    pass


def _tokens(line):
    result, start, quoted, index = [], 0, False, 0
    while index < len(line):
        char = line[index]
        if char == '"':
            if quoted and index + 1 < len(line) and line[index + 1] == '"':
                index += 2; continue
            quoted = not quoted
        elif char == ';' and not quoted:
            result.append(line[start:index]); start = index + 1
        index += 1
    if quoted: raise DefinitionError('地图数据表引号不完整，已停止处理。')
    result.append(line[start:]); return result


def _value(token):
    value = token[1:]
    return value[1:-1].replace('""', '"') if value.startswith('"') and value.endswith('"') else value


@dataclass
class Slk:
    raw: bytes
    columns: dict
    rows: dict
    row_numbers: dict
    max_y: int
    max_x: int
    opaque: dict


def parse_slk(raw):
    if len(raw) > 32 * 1024 * 1024 or not raw.startswith(b'ID;'):
        raise DefinitionError('地图数据表格式异常，已停止处理。')
    cells, x, y = {}, 0, 0
    lines = raw.decode('latin1').splitlines()
    if sum(line == 'E' for line in lines) != 1 or lines[-1] != 'E':
        raise DefinitionError('地图数据表结尾异常，已停止处理。')
    for line in lines:
        if not line.startswith('C;'): continue
        value = None
        for token in _tokens(line)[1:]:
            if token.startswith('X'): x = int(token[1:])
            elif token.startswith('Y'): y = int(token[1:])
            elif token.startswith('K'):
                if value is not None: raise DefinitionError('地图数据表存在重复单元格。')
                value = token
        if not 1 <= x <= 4096 or not 1 <= y <= 100000:
            raise DefinitionError('地图数据表坐标超出处理范围。')
        if value is not None:
            row = cells.setdefault(y, {})
            if x in row: raise DefinitionError('地图数据表存在重复单元格。')
            row[x] = value
    columns = {x: _value(token) for x, token in cells.get(1, {}).items()}
    if not columns or min(columns) != 1 or len(set(columns.values())) != len(columns):
        raise DefinitionError('地图数据表字段名称异常。')
    rows, numbers = {}, {}
    for y, row in cells.items():
        if y == 1: continue
        # Blizzard's tables contain spacer rows filled with '-' / '_'. Keep
        # their source lines, but do not treat them as object definitions.
        if 1 not in row:
            if any(_value(token) not in ('', '-', '_') for token in row.values()):
                raise DefinitionError('地图数据表存在缺少编号的记录。')
            continue
        key = _value(row[1])
        if key in rows: raise DefinitionError('地图数据表存在重复编号：' + key)
        rows[key] = {columns[x]: token for x, token in row.items() if x in columns}; numbers[key] = y
    opaque = {y: {x: t for x, t in row.items() if x not in columns or 1 not in row}
              for y, row in cells.items()}
    return Slk(raw, columns, rows, numbers, max(cells, default=1),
               max(x for row in cells.values() for x in row), {y:r for y,r in opaque.items() if r})


def merge_slk(original, reference):
    """Append missing rows/columns; original rows and all original cell bytes stay intact."""
    old = parse_slk(original); new = reference if isinstance(reference, Slk) else parse_slk(reference)
    if old.columns[1].casefold() != new.columns[1].casefold():
        raise DefinitionError('地图数据表编号字段与补齐资料不一致。')
    missing = [key for key in new.rows if key not in old.rows]
    if not missing: return original, ()
    columns = dict(old.columns); indexes = {name: index for index, name in columns.items()}
    extra = []
    max_x = old.max_x
    for name in new.columns.values():
        if name not in indexes:
            max_x += 1; x = max_x; columns[x] = name; indexes[name] = x
            extra.append(f'C;X{x};Y1;K"{name}"')
    y = old.max_y
    for key in missing:
        y += 1
        for name, token in new.rows[key].items():
            extra.append(f'C;X{indexes[name]};Y{y};{token}')
    lines = original.decode('latin1').splitlines()
    bounds = [index for index, line in enumerate(lines) if line.startswith('B;')]
    if len(bounds) != 1: raise DefinitionError('地图数据表边界异常。')
    index = bounds[0]
    lines[index] = re.sub(r';X\d+', ';X' + str(max(columns)), lines[index])
    lines[index] = re.sub(r';Y\d+', ';Y' + str(y), lines[index])
    newline = '\r\n' if b'\r\n' in original else '\n'
    result = (newline.join(lines[:-1] + extra + ['E']) + newline).encode('latin1')
    parsed = parse_slk(result)
    if any(parsed.opaque.get(y) != row for y, row in old.opaque.items()):
        raise DefinitionError('原有地图附加单元格校验失败。')
    if any(parsed.rows[key] != row for key, row in old.rows.items()):
        raise DefinitionError('原有地图记录校验失败，已放弃本次处理。')
    if any(parsed.rows[key] != new.rows[key] for key in missing):
        raise DefinitionError('补齐记录校验失败，已放弃本次处理。')
    return result, tuple(missing)


def parse_profile(raw):
    if len(raw) > 32 * 1024 * 1024 or b'\x00' in raw:
        raise DefinitionError('地图文字资料格式异常。')
    sections, start, key = {}, None, None
    lines = raw.splitlines(keepends=True)
    for index, line in enumerate(lines):
        match = re.fullmatch(rb'\s*\[([^\]\r\n]+)\]\s*', line)
        if match:
            if key is not None:
                sections[key] = sections.get(key, b'') + b''.join(lines[start:index])
            # FourCC object identifiers are case sensitive (Axxx != axxx).
            key = match[1].decode('latin1')
            start = index
    if key is not None:
        sections[key] = sections.get(key, b'') + b''.join(lines[start:])
    return sections


def merge_profile(original, reference):
    old, new = parse_profile(original), parse_profile(reference)
    missing, additions = [], []
    for key, section in new.items():
        if key not in old:
            additions.append(section); missing.append(key)
        else:
            previous, wanted = profile_fields(old[key]), profile_fields(section)
            fields = [line for name, line in wanted.items() if name not in previous]
            if fields:
                additions.append(('['+key+']\r\n').encode('latin1') + b'\r\n'.join(fields)+b'\r\n')
                missing.extend(key+'.'+name for name in wanted if name not in previous)
    if not additions: return original, ()
    # Keep the full original byte prefix, including comments, code page and EOLs.
    result = original + b'\r\n' + b'\r\n'.join(additions)
    parsed = parse_profile(result)
    if set(parsed) != set(old) | set(new) or any(
            any(profile_fields(parsed[key]).get(name) != line for name,line in profile_fields(section).items())
            for key,section in old.items()):
        raise DefinitionError('地图文字资料补齐校验失败。')
    return result, tuple(missing)


def profile_fields(section):
    fields = {}
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith((b'//', b';', b'[')) or b'=' not in stripped: continue
        name = stripped.split(b'=', 1)[0].strip().lower()
        if name: fields[name.decode('latin1')] = line
    return fields


class Reader:
    def __init__(self, raw): self.raw, self.at = raw, 0
    def take(self, count):
        end = self.at + count
        if count < 0 or end > len(self.raw): raise DefinitionError('地图信息文件不完整。')
        result = self.raw[self.at:end]; self.at = end; return result
    def integer(self): return struct.unpack('<i', self.take(4))[0]
    def count(self, maximum=100000):
        count = self.integer()
        if not 0 <= count <= maximum: raise DefinitionError('地图对象记录数量异常。')
        return count
    def string(self):
        end = self.raw.find(b'\x00', self.at, min(len(self.raw), self.at + 1024 * 1024))
        if end < 0: raise DefinitionError('地图信息文字不完整。')
        value = self.raw[self.at:end]; self.at = end + 1; return value


def object_ids(raw, *, extended=False):
    """Read .w3a/.w3t/etc identifiers without editing custom object records."""
    reader = Reader(raw); version = reader.integer(); result = set()
    if version not in (1, 2, 3): raise DefinitionError('地图自定义对象格式尚未适配。')
    for _ in range(2):
        for _ in range(reader.count()):
            old, new = reader.take(4), reader.take(4)
            result.add((new if new != bytes(4) else old).decode('latin1'))
            if version == 3: reader.take(reader.count(1024)*4)
            for _ in range(reader.count()):
                reader.take(4); kind = reader.integer()
                if extended: reader.take(8)
                if kind in (0, 1, 2): reader.take(4)
                elif kind == 3: reader.string()
                else: raise DefinitionError('地图自定义对象字段格式异常。')
                if reader.take(4) not in (old, new, bytes(4)):
                    raise DefinitionError('地图自定义对象结束标识异常。')
    if reader.at != len(raw): raise DefinitionError('地图自定义对象包含额外数据。')
    return result


def map_data_mode(raw):
    """Read w3i selectors for the 3.0.1 target loader; never rewrite metadata."""
    reader = Reader(raw); version = reader.integer()
    if version not in (18, 23, 24, 25, 26, 27, 28, 31, 32, 33, 39):
        raise DefinitionError('这个地图信息版本尚未适配，已保留原文件。')
    reader.take(8)
    game_version = tuple(reader.integer() for _ in range(4)) if version >= 27 else ()
    for _ in range(4): reader.string()
    reader.take(32 + 16 + 8); flags = reader.integer(); reader.take(1 + 4)
    if version == 18:
        for _ in range(3): reader.string()
        reader.take(4)
        return dict(format=version,game_version=game_version,data_set=0,data_version=None,flags=flags,
                    mode='reference' if flags & 4 else 'Custom_V1')
    if version >= 39: reader.take(4)
    for _ in range(4): reader.string()
    data_set = reader.integer()
    for _ in range(4): reader.string()
    reader.take(20)
    if version >= 39: reader.take(24)
    if version >= 25: reader.take(4)
    reader.string(); reader.take(1 + 4)
    if version >= 28: reader.take(4)
    data_version = None
    if version >= 31:
        reader.take(4); data_version = reader.integer()
    if data_set not in (-1, 0, 1, 2) or data_version not in (None, 0, 1, 2):
        raise DefinitionError('地图游戏资料设置不明确，已保留原文件。')
    # The observed 24360 loader defaults an absent version field to 1. An
    # explicit Unset=2 selects the base table, as in the working 24268 session.
    effective_version = 1 if data_version is None else data_version
    melee = data_set == 2 or (data_set in (-1, 0) and flags & 4)
    mode = ('reference' if effective_version == 2 or melee and effective_version == 1 else
            'Melee_V0' if melee else 'Custom_V'+str(effective_version))
    return dict(format=version,game_version=game_version,data_set=data_set,data_version=data_version,flags=flags,mode=mode)


def campaign_maps(raw):
    reader = Reader(raw); version = reader.integer()
    if version not in (1, 2, 3): raise DefinitionError('这个战役信息版本尚未适配。')
    reader.take(8)
    for _ in range(4): reader.string()
    reader.take(8); reader.string(); reader.string(); reader.take(4); reader.string(); reader.take(24)
    if version >= 3: reader.take(24)
    if version >= 2: reader.take(4)
    count = reader.integer()
    if not 0 <= count <= 1000: raise DefinitionError('战役章节数量异常。')
    paths = []
    for _ in range(count):
        reader.take(4); reader.string(); reader.string(); paths.append(reader.string().decode('utf8'))
    count = reader.integer()
    if not 0 <= count <= 1000: raise DefinitionError('战役地图数量异常。')
    for _ in range(count):
        reader.string(); paths.append(reader.string().decode('utf8'))
    if reader.at != len(raw): raise DefinitionError('战役信息包含未识别的尾部数据。')
    return tuple(dict.fromkeys(path.replace('/', '\\') for path in paths if path))
