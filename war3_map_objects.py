"""Read-only, bounded Warcraft object modifications and localized text."""
from __future__ import annotations
import csv
import math
import re
import struct
from war3_object_tables import Reader, DefinitionError


def decode_text(raw):
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        return raw.decode('utf-16')
    try:return raw.decode('utf-8-sig')
    except UnicodeDecodeError:pass
    recovered=raw.decode('utf-8-sig',errors='replace')
    if any(ord(c)>127 and c!='\ufffd' for c in recovered) and recovered.count('\ufffd')<=max(2,len(raw)//1000):
        return recovered
    for encoding in ('gb18030', 'cp1252'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return recovered


def object_records(raw, *, extended=False):
    if len(raw)>64*1024*1024:
        raise DefinitionError('物编文件超过 64 MB，已停止读取该文件。')
    r=Reader(raw);version=r.integer();result=[];total=0
    if version not in (1,2,3):
        raise DefinitionError(f'暂不支持物编格式版本 {version}。')
    for table in range(2):
        for _ in range(r.count(50000)):
            old,new=r.take(4),r.take(4)
            if any(not 32<=b<=126 for b in old) or (new!=bytes(4) and any(not 32<=b<=126 for b in new)):
                raise DefinitionError('物编对象代码含有无法识别的字节。')
            if version==3:r.take(r.count(1024)*4)
            changes=[]
            for _ in range(r.count(50000)):
                total+=1
                if total>500000:raise DefinitionError('物编字段数量超过读取上限。')
                field=r.take(4).decode('latin1');kind=r.integer()
                level,index=(r.integer(),r.integer()) if extended else (0,0)
                if not 0<=level<=100000 or not 0<=index<=100000:
                    raise DefinitionError('物编等级或数据列编号异常。')
                if kind==0:value=r.integer()
                elif kind in (1,2):
                    value=struct.unpack('<f',r.take(4))[0]
                    if not math.isfinite(value):raise DefinitionError('物编包含无效浮点数。')
                elif kind==3:value=decode_text(r.string())
                else:raise DefinitionError(f'物编字段类型 {kind} 尚未适配。')
                # Renamed objects may retain a source object's trailer. Consume
                # its exact position, without guessed byte resynchronization.
                trailer=r.take(4)
                changes.append(dict(field=field,type=kind,level=level,index=index,value=value,
                                    trailer=trailer.hex()))
            result.append(dict(rawcode=(new if new!=bytes(4) else old).decode('ascii'),
                base=old.decode('ascii'),custom=table==1 or new!=bytes(4),changes=changes))
    if r.at!=len(raw):raise DefinitionError('物编文件存在未识别的尾部数据。')
    return result


def strings(raw, *, diagnostics=None, tolerant=False):
    if raw is None:return {}
    if len(raw)>32*1024*1024:raise DefinitionError('地图文字表超过读取上限。')
    issues=diagnostics if diagnostics is not None else []
    if raw.startswith((b'\xff\xfe',b'\xfe\xff')):
        raw=raw.decode('utf-16').encode('utf8')
    bom=3 if raw.startswith(b'\xef\xbb\xbf') else 0
    # Determine the file's encoding once, but decode every string separately.
    # A truncated character in quest text must not discard other string IDs.
    decoded=decode_text(raw)
    try:raw.decode('utf-8-sig');encoding='utf8'
    except UnicodeDecodeError:
        encoding='utf8' if '\ufffd' in decoded else next((enc for enc in ('gb18030','cp1252') if _decodes(raw,enc)), 'utf8')
    data=raw[bom:];result={};conflicted=set()
    headers=list(re.finditer(rb'(?m)^[ \t]*STRING[ \t]+(\d+)[ \t]*(?://[^\r\n]*)?(?:\r?\n|(?=\{))',data))
    def clean_gap(value):return re.sub(rb'(?m)//[^\r\n]*',b'',value).strip()
    def issue(message,key=None,offset=0,code='text_structure',**extra):
        if not tolerant:raise DefinitionError(message)
        issues.append(dict(code=code,message=message,stringId=key,byteOffset=offset,**extra))
    if clean_gap(data[:headers[0].start()] if headers else data):
        issue('文字表中有无法识别的段落，已继续读取后面的有效文字。',offset=bom)
    for i,match in enumerate(headers):
        key=str(int(match[1]));end=headers[i+1].start() if i+1<len(headers) else len(data)
        chunk=data[match.end():end]
        opening=re.match(rb'(?:[ \t\r\n]|//[^\r\n]*(?:\r?\n|$))*\{[ \t]*\r?\n',chunk)
        closings=list(re.finditer(rb'(?m)^[ \t]*\}[ \t]*(?=\r?$)',chunk))
        closing=next((v for v in reversed(closings) if not clean_gap(chunk[v.end():])),None)
        if not opening or closing is None or closing.start()<opening.end():
            issue('文字条目 '+key+' 的括号或结尾不完整，其他条目已继续读取。',key,match.start()+bom)
            continue
        payload=chunk[opening.end():closing.start()].rstrip(b'\r\n')
        value=payload.decode(encoding,errors='replace')
        # Preserve exact failed bytes and positions; never invent the missing
        # character or reinterpret an otherwise UTF-8 paragraph as ANSI.
        offset=0;faults=[]
        while offset<len(payload):
            try:payload[offset:].decode(encoding);break
            except UnicodeDecodeError as exc:
                start=offset+exc.start;finish=offset+exc.end
                faults.append(dict(byteOffset=bom+match.end()+opening.end()+start,rawHex=payload[start:finish].hex()))
                offset=finish
        if faults:
            issues.append(dict(code='text_encoding',message='文字条目 '+key+' 含有不完整的 '+encoding.upper()+' 字符；其余文字已保留。',
                stringId=key,byteOffset=faults[0]['byteOffset'],faults=faults))
        if key in conflicted:continue
        if key in result:
            if result[key]!=value:
                result.pop(key);conflicted.add(key)
                issue('文字编号 '+key+' 对应多个不同内容，未猜选其中一个。',key,match.start()+bom,code='text_duplicate')
            continue
        result[key]=value
    return result


def _decodes(raw,encoding):
    try:raw.decode(encoding);return True
    except UnicodeDecodeError:return False


def resolve_string(value, table):
    if not isinstance(value,str):return value
    match=re.fullmatch(r'TRIGSTR_(\d+)',value.strip(),re.I)
    return table.get(str(int(match[1])),value) if match else value


def profile(raw):
    result={};current=None
    for line in decode_text(raw).splitlines():
        line=line.strip()
        if not line or line.startswith(('//',';')):continue
        if line.startswith('[') and line.endswith(']'):
            current=result.setdefault(line[1:-1],{})
        elif current is not None and '=' in line:
            key,value=line.split('=',1)
            try:values=next(csv.reader([value],skipinitialspace=True))
            except (csv.Error,StopIteration):raise DefinitionError('地图配置文字格式异常。')
            current[key.strip().casefold()]=values
    return result


def plain_text(value):
    value=re.sub(r'\|[cC][0-9a-fA-F]{8}|\|[rR]','',str(value))
    return value.replace('|n','\n').replace('|N','\n')
