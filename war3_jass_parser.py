"""Byte-preserving JASS boundaries, independent of comments and string content."""
from dataclasses import dataclass
import re
from war3_object_tables import DefinitionError

NEWLINE = re.compile(rb'[\r\n]')


@dataclass(frozen=True)
class Token:
    value: bytes
    start: int
    end: int
    kind: str


def tokens(raw):
    if not isinstance(raw, bytes) or len(raw) > 32*1024*1024:
        raise DefinitionError('章节脚本为空、类型不正确或超过 32 MB。')
    result = []
    i = 3 if raw.startswith(b'\xef\xbb\xbf') else 0
    while i < len(raw):
        if len(result) > 2500000:
            raise DefinitionError('章节脚本标记过多，已停止处理。')
        value = raw[i]
        if value in b' \t\r\n':
            i += 1
            continue
        if raw[i:i+2] == b'//':
            end = NEWLINE.search(raw, i)
            i = end.start() if end else len(raw)
            continue
        start = i
        if value in (34, 39):
            quote = value
            i += 1
            while i < len(raw) and raw[i] != quote:
                if raw[i] in (10, 13):
                    raise DefinitionError('章节脚本有未闭合的文字或代码常量。')
                i += 2 if raw[i] == 92 else 1
            if i >= len(raw):
                raise DefinitionError('章节脚本有未闭合的文字或代码常量。')
            i += 1
            result.append(Token(raw[start:i], start, i, 'string' if quote == 34 else 'rawcode'))
        elif value in b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_':
            i += 1
            while i < len(raw) and raw[i] in b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789':
                i += 1
            result.append(Token(raw[start:i], start, i, 'identifier'))
        else:
            i += 1
            result.append(Token(raw[start:i], start, i, 'symbol'))
    return result


def boundaries(raw):
    ts = tokens(raw)
    globals_start = globals_end = None
    functions = []
    current = None
    depth = False
    for i, t in enumerate(ts):
        if t.kind != 'identifier':
            continue
        if t.value == b'globals' and current is None:
            if globals_start is not None:
                raise DefinitionError('章节脚本包含多个全局声明区。')
            globals_start = t
            depth = True
        elif t.value == b'endglobals' and depth:
            globals_end = t
            depth = False
        elif t.value == b'function' and i+2 < len(ts) and ts[i+2].value == b'takes':
            if current is not None or depth:
                raise DefinitionError('章节脚本的函数声明位置异常。')
            current = dict(name=ts[i+1].value, start=t.start, declaration=i, end=None)
        elif t.value == b'endfunction':
            if current is None:
                raise DefinitionError('章节脚本的函数结束标记没有对应函数。')
            current['end'] = t.end
            current['end_token'] = i
            functions.append(current)
            current = None
    if depth or current or globals_start is None or globals_end is None:
        raise DefinitionError('章节脚本的全局声明或函数边界不完整。')
    names = [f['name'] for f in functions]
    if len(names) != len(set(names)):
        raise DefinitionError('章节脚本存在重复函数，已停止添加。')
    mains = [f for f in functions if f['name'] == b'main']
    if len(mains) != 1:
        raise DefinitionError('章节脚本没有唯一 main 入口，已停止添加。')
    main = mains[0]
    at = main['declaration']
    if [t.value for t in ts[at:at+7]] != [b'function', b'main', b'takes', b'nothing', b'returns', b'nothing', b'local']:
        if [t.value for t in ts[at:at+6]] != [b'function', b'main', b'takes', b'nothing', b'returns', b'nothing']:
            raise DefinitionError('main 入口参数或返回类型不符合普通 JASS 地图格式。')
    first = at+6
    while first < main['end_token'] and ts[first].value == b'local':
        start = ts[first].start
        newline = re.search(rb'[\r\n]', raw[start:])
        if not newline:
            raise DefinitionError('main 的局部变量声明没有结束。')
        line_end = start+newline.start()
        while first < main['end_token'] and ts[first].start < line_end:
            first += 1
    executable_at = ts[first].start
    if globals_end.end > main['start']:
        raise DefinitionError('章节脚本的 main 与全局声明顺序异常。')
    return dict(tokens=ts, functions=functions, globals_at=globals_end.start,
                functions_at=main['start'], initialize_at=executable_at)


def inject(raw, globals_code, functions_code, boot_name):
    b = boundaries(raw)
    insertions = [(b['globals_at'], globals_code), (b['functions_at'], functions_code),
                  (b['initialize_at'], b'call '+boot_name.encode('ascii')+b'()\n')]
    patched = raw
    for at, content in sorted(insertions, reverse=True):
        patched = patched[:at] + b'\n' + content + b'\n' + patched[at:]
    boundaries(patched)
    return patched
