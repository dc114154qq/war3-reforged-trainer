"""Offline campaign/map object catalogue. Opens source archives read-only."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime,timezone
from functools import lru_cache
from pathlib import Path
import csv,hashlib,io,json,re,struct,tempfile,threading
from war3_mpq import Archive,canonical_name
from war3_object_tables import parse_slk,map_data_mode,campaign_maps,DefinitionError
from war3_map_objects import object_records,strings,resolve_string,profile,plain_text,decode_text
from war3_map_catalog_reference import reference
from war3_services.extension_definitions import definition_pack,file_hash

KINDS=('item','ability','unit')
TABLES={'item':('ItemData.slk',),'ability':('AbilityData.slk',),
        'unit':('UnitData.slk','UnitBalance.slk','UnitAbilities.slk','unitUI.slk','UnitWeapons.slk')}
SUFFIX={'item':'w3t','ability':'w3a','unit':'w3u'}
MAX_ROWS=50000


def table_kind(name):
    name=name.casefold()
    for kind,names in TABLES.items():
        if name in {n.casefold() for n in names}:return kind
    if not name.endswith('.txt'):return None
    if 'ability' in name and not any(t in name for t in ('buff','metadata')):return 'ability'
    if name.startswith('item'):return 'item'
    if 'unit' in name and not any(t in name for t in ('global','metadata','command')):return 'unit'
    return None


def slk_rows(raw):
    result={}
    for code,row in parse_slk(raw).rows.items():
        if len(code)!=4:continue
        result[code]={k.casefold():decode_text(v[2:-1].replace('""','"').encode('latin1'))
                      if v.startswith('K"') and v.endswith('"') else v[1:] for k,v in row.items()}
    return result


@lru_cache(64)
def stock_table(mode,name):
    _,files=definition_pack()
    key=next((k for k in files if k.casefold()==('baseline/'+mode+'/'+name).casefold()),None)
    return slk_rows(files[key]) if key else {}


@lru_cache(4)
def baseline(mode):
    _,files=definition_pack();result={kind:{} for kind in KINDS}
    for name,raw in files.items():
        if not name.startswith('baseline/'+mode+'/'):continue
        kind=table_kind(name.rsplit('/',1)[1])
        if kind is None:continue
        rows=slk_rows(raw) if name.endswith('.slk') else profile(raw)
        for code,fields in rows.items():
            if len(code)==4:result[kind].setdefault(code,{}).update(fields)
    for kind in KINDS:
        for code,fields in reference()['profiles']['zhCN'][kind].items():
            if code in result[kind]:result[kind][code].update(fields)
    return result


def location(meta,level=0):
    field=meta.get('field','');is_profile=meta.get('slk','').casefold()=='profile'
    repeated=int(meta.get('repeat','0') or 0)>0
    if field=='Data':field+=''+chr(64+int(meta.get('data','0') or 0))
    if repeated and not is_profile:field+=str(max(1,level))
    index=int(meta.get('index','-1') or -1)
    if is_profile and repeated:index=max(0,index)+max(0,level-1)
    return field.casefold(),index


def get_value(attrs,key,index=-1):
    if key not in attrs:return None
    value=attrs[key]
    if isinstance(value,list):
        if index<0:return ','.join(value)
        return value[index] if index<len(value) else None
    return value


def put_value(attrs,key,index,value):
    if index<0:attrs[key]=value
    else:
        values=attrs.get(key,[])
        if not isinstance(values,list):values=[values]
        else:values=list(values)
        if index>10000:raise DefinitionError('物编列表索引超过读取上限。')
        values.extend(['']*max(0,index+1-len(values)));values[index]=value;attrs[key]=values


def equal(a,b):
    if b is None:return False
    if isinstance(a,float):
        try:return struct.pack('<f',a)==struct.pack('<f',float(b))
        except (ValueError,TypeError,OverflowError):return False
    if isinstance(a,int):
        try:return float(a)==float(b)
        except (ValueError,TypeError):return False
    return a==b or isinstance(b,list) and a==','.join(str(value) for value in b)


def decode_attrs(fields,wts):
    return {k:[resolve_string(v,wts) for v in value] if isinstance(value,list) else resolve_string(value,wts)
            for k,value in fields.items()}


def scan_map_catalog(source,*,progress=None,cancel=None):
    source=Path(str(source).strip().strip('"')).expanduser().resolve(strict=True)
    if source.suffix.casefold() not in ('.w3n','.w3x','.w3m') or not source.is_file():
        raise DefinitionError('请选择 w3n 战役、w3x 或 w3m 地图。')
    if source.stat().st_size>8*1024**3:raise DefinitionError('文件超过 8 GB，已停止读取。')
    cancel=cancel or threading.Event();warnings=[];text_issues=[];rows=[];scopes=[];members_read=[]
    def tick(stage,**data):
        if cancel.is_set():raise InterruptedError('目录读取已停止，原文件未修改。')
        if progress:progress(stage,data)
    def warning(scope,file,exc):warnings.append(dict(scope=scope,file=file,message=str(exc)))
    def read_optional(archive,name,scope):
        raw=archive.read(name,optional=True)
        if raw is not None:members_read.append(dict(scope=scope,file=name,sha256=hashlib.sha256(raw).hexdigest()))
        return raw
    def wts_for(archive,prefix,scope):
        try:
            issues=[];values=strings(read_optional(archive,prefix+'.wts',scope),diagnostics=issues,tolerant=True)
            text_issues.extend({**issue,'scope':scope,'file':prefix+'.wts','usedBy':[]} for issue in issues)
            return values
        except (ValueError,UnicodeError) as exc:warning(scope,prefix+'.wts',exc);return {}
    def raw_scope(archive,prefix,scope,parent_wts=None):
        local_wts=wts_for(archive,prefix,scope)
        wts={**(parent_wts or {}),**local_wts};blobs=[];records={kind:[] for kind in KINDS}
        for issue in text_issues:
            if issue['scope']==scope and issue.get('stringId') and issue['stringId'] not in local_wts:
                wts.pop(issue['stringId'],None)
        issue_index={}
        for issue in text_issues:issue_index.setdefault((issue['scope'],issue.get('stringId')),[]).append(issue)
        missing={}
        def resolve(value,used_by):
            if isinstance(value,str):
                match=re.fullmatch(r'TRIGSTR_(\d+)',value.strip(),re.I)
                if match:
                    key=str(int(match[1]))
                    owner=scope if key in local_wts or (scope,key) in issue_index else '战役共用' if parent_wts and key in parent_wts else scope
                    for issue in issue_index.get((owner,key),[]):
                        if used_by not in issue['usedBy']:
                            issue['usedBy'].append(used_by)
                    if key not in wts:
                        if key not in missing:
                            diagnostic=dict(scope=scope,file=prefix+'.wts',code='text_missing',stringId=key,
                                message='文字编号 '+key+' 没有有效内容；已保留原编号。',usedBy=[])
                            missing[key]=diagnostic;text_issues.append(diagnostic)
                        if used_by not in missing[key]['usedBy']:missing[key]['usedBy'].append(used_by)
            return resolve_string(value,wts)
        for kind in KINDS:
            for stem in (prefix,prefix+'Skin'):
                name=stem+'.'+SUFFIX[kind]
                tick('objects',scope=scope,file=name)
                try:
                    raw=read_optional(archive,name,scope)
                    if raw is not None:
                        for record in object_records(raw,extended=kind=='ability'):
                            for change in record['changes']:
                                change['rawValue']=change['value'];change['value']=resolve(change['value'],record['rawcode']+' / '+change['field'])
                            records[kind].append((name,record))
                except (ValueError,UnicodeError) as exc:warning(scope,name,exc)
        # Exact names handle archives with stripped listfiles; enumeration also
        # finds locale-specific table variants, without extracting arbitrary paths.
        names={'Units\\'+n for values in TABLES.values() for n in values}
        _,stock_files=definition_pack()
        names.update('Units\\'+n.rsplit('/',1)[-1] for n in stock_files if table_kind(n.rsplit('/',1)[-1]))
        names.update('Units\\'+n for n in reference()['files'])
        try:names.update(m.name for m in archive.members() if m.name.replace('/','\\').casefold().startswith('units\\') and table_kind(m.name.replace('/','\\').rsplit('\\',1)[-1]))
        except ValueError as exc:warning(scope,'归档目录',exc)
        for name in sorted(names,key=str.casefold):
            kind=table_kind(name.rsplit('\\',1)[-1])
            if kind is None:continue
            tick('tables',scope=scope,file=name)
            try:
                raw=read_optional(archive,name,scope)
                if raw is not None:
                    data=slk_rows(raw) if name.casefold().endswith('.slk') else profile(raw)
                    blobs.append((name,kind,{code:{field:[resolve(v,code+' / '+field) for v in value] if isinstance(value,list) else resolve(value,code+' / '+field) for field,value in fields.items()} for code,fields in data.items() if len(code)==4}))
            except (ValueError,UnicodeError) as exc:warning(scope,name,exc)
        return dict(records=records,blobs=blobs),wts

    def apply_scope(raw,state,scope,stock,emit,mode='Custom_V1'):
        changed={}
        def row_for(kind,code,base_code):
            key=(kind,code)
            if key not in changed:
                changed[key]=dict(kind=kind,rawcode=code,base=base_code,scope=scope,
                    changeType='modified' if code in stock[kind] else 'added',changes=[],files=[])
            return changed[key]
        for name,kind,data in raw['blobs']:
            tick('compare',scope=scope,file=name)
            native_table=stock_table(mode,name.rsplit('\\',1)[-1]) if name.casefold().endswith('.slk') else None
            for code,attrs in data.items():
                old=state[kind].setdefault(code,{})
                for field,value in attrs.items():
                    if field in ('comment(s)','comments','comment'):continue
                    native_value=native_table.get(code,{}).get(field) if native_table is not None else None
                    if native_table is not None and equal(value,native_value):continue
                    previous=deepcopy(old.get(field))
                    # A localized stock string is native data too.
                    stock_variants=[reference()['profiles'][locale][kind].get(code,{}).get(field) for locale in ('zhCN','enUS')]
                    if equal(value,previous) or any(value==v for v in stock_variants if v is not None):continue
                    old[field]=value
                    row=row_for(kind,code,code)
                    row['changes'].append(dict(field=field,label=field,level=0,index=0,value=value,rawValue=value,
                        baseValue=previous,baseKnown=previous is not None,file=name,storage='table'))
                    if name not in row['files']:row['files'].append(name)
        # Object records can derive from another custom object. Resolve their
        # dependencies independently of serialization order, then apply skins.
        for kind in KINDS:
            pending=list(raw['records'][kind]);rounds=0
            while pending:
                ready=[];remaining=[];defined={rec['rawcode'] for _,rec in pending}
                for name,rec in pending:
                    (remaining if rec['base']!=rec['rawcode'] and rec['base'] in defined and rec['base'] not in state[kind] else ready).append((name,rec))
                if not ready:
                    warning(scope,'物编继承','发现循环继承或缺失的基础对象，保留字段，名称可能不完整。');ready=remaining;remaining=[]
                for name,rec in ready:
                    if cancel.is_set():raise InterruptedError('目录读取已停止，原文件未修改。')
                    code=rec['rawcode'];base_code=rec['base']
                    attrs=state[kind].get(code)
                    if attrs is None:attrs=deepcopy(state[kind].get(base_code,{}));state[kind][code]=attrs
                    if not attrs and base_code not in state[kind]:warning(scope,name,'基础对象未收录：'+base_code)
                    row=None
                    for change in rec['changes']:
                        meta=reference()['metadata'][kind].get(change['field'],{})
                        key,index=location(meta,change['level']) if meta else ('@'+change['field']+':'+str(change['level'])+':'+str(change['index']),-1)
                        old=get_value(attrs,key,index);value=change['value'];put_value(attrs,key,index,value)
                        if equal(value,old):continue
                        row=row or row_for(kind,code,base_code)
                        row['changes'].append({**change,'label':meta.get('zhCN',change['field']),
                            'labelEn':meta.get('enUS',change['field']),'baseValue':old,'baseKnown':old is not None,
                            'file':name,'storage':'object'})
                        if name not in row['files']:row['files'].append(name)
                    if code not in stock[kind] and rec['custom']:
                        row=row or row_for(kind,code,base_code)
                        if name not in row['files']:row['files'].append(name)
                pending=remaining;rounds+=1
                if rounds>1000:raise DefinitionError('物编继承层数超过读取上限。')
        if not emit:return
        for (kind,code),row in changed.items():
            attrs=state[kind][code]
            name=get_value(attrs,'name',0) or get_value(attrs,'editorsuffix',0) or code
            desc=[]
            for field in ('ubertip','description','tip'):
                value=attrs.get(field)
                if value:
                    values=value if isinstance(value,list) else [value]
                    def expand(match):
                        target=state[kind].get(match[1]) or next((state[k].get(match[1]) for k in ('ability','item','unit') if match[1] in state[k]),{})
                        value=get_value(target,match[2].casefold())
                        if value is None:return match[0]
                        if match[3]:
                            try:return format(float(value)*100,'.8g')
                            except (TypeError,ValueError):return match[0]
                        return str(value)
                    text='\n'.join((f'{i+1}级：' if len(values)>1 else '')+plain_text(re.sub(r'<([^,<>]+),([^,<>]+)(,%)?>',expand,str(v))) for i,v in enumerate(values) if str(v))
                    if text and text not in desc:desc.append(text)
            is_hero=kind=='unit' and code[:1].isupper()
            proper=attrs.get('propernames',[]) if is_hero else []
            proper=proper if isinstance(proper,list) else [proper]
            hero_names=list(dict.fromkeys(plain_text(v.strip()) for item in proper for v in str(item).split(',') if v.strip() and v.strip() not in ('_','-')))
            row.update(name=plain_text(name),heroNames=hero_names,isHero=is_hero,
                description='\n\n'.join(desc),id=str(len(rows)),changeCount=len(row['changes']))
            rows.append(row)
            if len(rows)>MAX_ROWS:raise DefinitionError('目录超过 50000 条，请按单张章节地图读取。')

    tick('hash',scope=source.name,file=str(source));initial=(source.stat().st_size,source.stat().st_mtime_ns);digest=file_hash(source)
    with tempfile.TemporaryDirectory(prefix='war3-map-catalog-') as temp:
        with Archive(source) as archive:
            if source.suffix.casefold()=='.w3n':
                global_raw,global_wts=raw_scope(archive,'war3campaign','战役共用')
                scopes.append('战役共用')
                members={m.name.casefold():m for m in archive.members() if m.name.casefold().endswith(('.w3x','.w3m')) and m.locale==0}
                w3f=read_optional(archive,'war3campaign.w3f','战役共用')
                try:referenced=campaign_maps(w3f) if w3f else ()
                except ValueError as exc:warning('战役共用','war3campaign.w3f',exc);referenced=()
                for name in referenced:
                    if name.casefold() not in members:
                        raw=archive.read(name,optional=True)
                        if raw is None:warning(name,name,'战役目录引用的章节没有找到。')
                        else:members[name.casefold()]=name
                chapters=list(members.values())
                if not chapters:raise DefinitionError('战役中没有找到可读取的章节地图。')
                if len(chapters)>1000:raise DefinitionError('战役章节数量超过读取上限。')
                # Shared object records depend on a chapter's stock data set.
                # Show shared records once using the first readable chapter's mode.
                shared_shown=False
                for i,member in enumerate(chapters):
                    name=member if isinstance(member,str) else member.name
                    canonical_name(name);scopes.append(name);tick('chapter',scope=name,index=i+1,total=len(chapters),file=name)
                    try:
                        payload=archive.read(member);path=Path(temp)/f'chapter-{i}.w3x';path.write_bytes(payload)
                        with Archive(path) as chapter:
                            mode_raw=read_optional(chapter,'war3map.w3i',name)
                            mode=map_data_mode(mode_raw)['mode'] if mode_raw else 'Custom_V1'
                            stock=baseline(mode);state=deepcopy(stock)
                            apply_scope(global_raw,state,'战役共用',stock,not shared_shown,mode);shared_shown=True
                            local,_=raw_scope(chapter,'war3map',name,global_wts)
                            apply_scope(local,state,name,stock,True,mode)
                    except (ValueError,OSError) as exc:warning(name,name,exc)
                    tick('chapter_complete',scope=name,index=i+1,total=len(chapters),file=name)
            else:
                scopes.append(source.name);tick('chapter',scope=source.name,index=1,total=1,file=source.name)
                info=read_optional(archive,'war3map.w3i',source.name)
                mode=map_data_mode(info)['mode'] if info else 'Custom_V1'
                stock=baseline(mode);state=deepcopy(stock)
                local,_=raw_scope(archive,'war3map',source.name)
                apply_scope(local,state,source.name,stock,True,mode)
    tick('verify',scope=source.name,file=str(source))
    if (source.stat().st_size,source.stat().st_mtime_ns)!=initial or file_hash(source)!=digest:
        raise DefinitionError('读取期间源文件发生变化，请重新读取目录。')
    diagnostics=[]
    for issue in text_issues:
        affected=bool(issue['usedBy']) or issue.get('stringId') is None
        diagnostic={**issue,'severity':'warning' if affected else 'info',
            'impact':'关联目录字段：'+'、'.join(issue['usedBy']) if issue['usedBy'] else '未被本次目录的对象字段引用，不影响已读取的物品、技能和单位。'}
        diagnostics.append(diagnostic)
        if affected:warnings.append(diagnostic)
    diagnostics.extend({**w,'severity':'warning'} for w in warnings if w not in diagnostics)
    return dict(schema=1,source=str(source),sourceSha256=digest,capturedAt=datetime.now(timezone.utc).isoformat(),
        rows=rows,scopes=scopes,warnings=warnings,diagnostics=diagnostics,complete=not warnings,members=members_read,
        counts={k:sum(r['kind']==k for r in rows) for k in KINDS},
        notice='战役共用数据只列一次；章节记录表示该章节自己的修改。目录读取静态物编和数据表，脚本运行后临时修改的内容不在此目录中。')


def filter_rows(result,kind='',query='',scope='',change_type='',search_index=None):
    if kind and kind not in KINDS:raise ValueError('目录分类无效。')
    if change_type and change_type not in ('added','modified'):raise ValueError('改动类型无效。')
    words=str(query).casefold().split()
    for row in result['rows']:
        if kind and row['kind']!=kind or scope and row['scope']!=scope or change_type and row['changeType']!=change_type:continue
        if not words:yield row;continue
        if search_index is not None:text=search_index[row['id']]
        else:
            text=' '.join(str(row[k]) for k in ('rawcode','base','name','description','scope'))+' '+' '.join(row.get('heroNames',[]))
            text+=' '+json.dumps(row['changes'],ensure_ascii=False)
            text=text.casefold()
        if all(word in text for word in words):yield row


def export_catalog(path,result,*,kind='',query='',scope='',change_type=''):
    path=Path(path).expanduser().resolve()
    source=Path(result['source']).resolve()
    if path==source or path.suffix.casefold() not in ('.csv','.json'):
        raise ValueError('导出文件请使用 CSV 或 JSON，不能覆盖地图。')
    selected=list(filter_rows(result,kind,query,scope,change_type))
    if path.suffix.casefold()=='.json':
        raw=(json.dumps({**result,'rows':selected,'exportedCount':len(selected),'sourceCounts':result['counts'],
            'counts':{k:sum(row['kind']==k for row in selected) for k in KINDS},
            'filters':dict(kind=kind,query=query,scope=scope,changeType=change_type)},ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8')
    else:
        stream=io.StringIO(newline='');writer=csv.writer(stream)
        writer.writerow(('分类','改动类型','对象代码','原型代码','名称','英雄本名','描述／效果／单位介绍','来源章节','修改字段数','具体修改','物编文件'))
        for row in selected:
            cells=[{'item':'物品','ability':'技能','unit':'单位'}[row['kind']], '新增' if row['changeType']=='added' else '修改',
                row['rawcode'],row['base'],row['name'],'、'.join(row.get('heroNames',[])),row['description'],row['scope'],row['changeCount'],json.dumps(row['changes'],ensure_ascii=False),'；'.join(row['files'])]
            writer.writerow(["'"+str(v) if str(v).lstrip().startswith(('=','+','-','@','\t','\r')) else v for v in cells])
        raw=stream.getvalue().encode('utf-8-sig')
    # Never overwrite user files; the save dialog is only a path selector.
    from war3_services.save_extraction import _atomic_new_file
    _atomic_new_file(path,raw)
    return str(path),len(selected)
