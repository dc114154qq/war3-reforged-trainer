"""Generate offline object descriptions from pinned, extracted Warcraft III data."""
from pathlib import Path
from decimal import Decimal,InvalidOperation
import argparse,base64,hashlib,json,re,zlib
from tools.generate_forsaken_equipment_catalog import slk,sections

REFERENCE=re.compile(r'<([^,<>]+),([^,<>]+)(,[%.])?>')

def values_from(folder):
    result={}
    for path in sorted(folder.glob('*.slk')):
        if 'MetaData' in path.name or path.name=='MiscData.slk':continue
        for row in slk(path):
            key=row.get('alias') or next(iter(row.values()),'')
            if len(key)==4:result.setdefault(key,{}).update(row)
    return result

def clean_text(raw,values):
    raw=re.sub(r'<([!-~]{4})","([A-Za-z][A-Za-z0-9]*)>',r'<\1,\2>',raw)
    # Tooltip arrays are kept in their original order, with explicit level labels.
    parts=raw.split('","')
    if len(parts)>1:raw='\n\n'.join(f'{i+1}级：'+part.strip('"') for i,part in enumerate(parts))
    notes=[]
    def reference(match):
        obj,field,percent=match.groups();record=values.get(obj,{})
        value=record.get(field)
        if value is None:
            folded={k.casefold():v for k,v in record.items()};value=folded.get(field.casefold())
        if value is None:notes.append(match[0]);return '（数值见游戏内）'
        try:
            n=Decimal(value)*(100 if percent==',%' else 1)
            return format(n.quantize(Decimal('.000001')).normalize(),'f')
        except InvalidOperation:return value
    result=REFERENCE.sub(reference,raw)
    result=re.sub(r'\|[cC][0-9a-fA-F]{8}|\|[rR]','',result).replace('|n','\n').replace('\\n','\n')
    result=re.sub(r'\|[Tt].*?\|[tT]','',result)
    result=result.replace('%d','当前等级').strip('" \n\t')
    if 'TRIGSTR_' in result or result.startswith('WESTRING_'):return '',tuple(notes)
    return result,tuple(notes)

def data_description(kind,code,record,metadata,labels,zh):
    if not record:return ''
    if kind=='unit':
        values=[]
        for field,label,en in [('HP','生命值','Hit points'),('manaN','魔法值','Mana'),('def','护甲','Armor'),('spd','移动速度','Movement speed'),('rangeN1','攻击距离','Attack range')]:
            value=record.get(field,'').strip()
            if value and value not in ('-','_'):values.append((label if zh else en)+'：'+value)
        low,high=record.get('mindmg1','').strip(),record.get('maxdmg1','').strip()
        if low not in ('','-','_') and high not in ('','-','_'):values.append(('攻击力：' if zh else 'Attack damage: ')+low+'–'+high)
        return ('单位基础资料：' if zh else 'Base unit data: ')+'；'.join(values) if values else ''
    if kind!='ability':return ''
    effect=record.get('code',code);specific=[]
    for meta in metadata:
        if meta.get('field')!='Data' or effect not in meta.get('useSpecific','').split(',') or meta.get('type') not in ('int','real','unreal','bool'):continue
        try:letter=chr(64+int(meta['data']))
        except (ValueError,KeyError):continue
        label=labels.get(meta.get('displayName',''),'')
        if not label or label.startswith('WESTRING_'):continue
        specific.append((meta,letter,label))
    output=[]
    try:levels=min(100,int(record.get('levels','1')))
    except ValueError:levels=1
    for level in range(1,levels+1):
        line=[]
        for meta,letter,label in specific:
            value=record.get('Data'+letter+str(level),'').strip()
            if value in ('','-','_'):continue
            if meta['type']=='bool':value=('是' if value=='1' else '否') if zh else ('Yes' if value=='1' else 'No')
            line.append(label+'：'+value)
        for field,label,en in [('Cost','魔法消耗','Mana cost'),('Cool','冷却时间（秒）','Cooldown (seconds)'),('Dur','持续时间（秒）','Duration (seconds)'),('HeroDur','对英雄持续时间（秒）','Hero duration (seconds)'),('Rng','施法距离','Cast range'),('Area','影响范围','Area of effect')]:
            value=record.get(field+str(level),'').strip()
            if value not in ('','-','_','0'):line.append((label if zh else en)+'：'+value)
        if line:output.append((f'{level}级：' if zh else f'Level {level}: ')+'；'.join(line))
    return ('游戏基础效果数据：\n' if zh else 'Base ability effect data:\n')+'\n'.join(output) if output else ''

def generate(source,destination,audit):
    data={};files={};stats={};missing=[]
    for locale in ('zhCN','enUS'):
        folder=source/locale;values=values_from(folder)
        metadata=slk(folder/'AbilityMetaData.slk')
        labels=sections(folder/'WorldEditStrings.txt').get('WorldEditStrings',{})
        for p in folder.iterdir():
            if p.is_file():files[locale+'/'+p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
        for kind,patterns in [('item',('ItemStrings.txt',)),('ability',('*AbilityStrings.txt',)),('unit',('*UnitStrings.txt',))]:
            entries={}
            for pattern in patterns:
                for path in sorted(folder.glob(pattern)):
                    for code,record in sections(path).items():entries.setdefault(code,{}).update({k.casefold():v for k,v in record.items()})
            covered=0;unresolved=0
            for code,entry in entries.items():
                if len(code)!=4:continue
                keys=('researchubertip','ubertip','description') if kind=='ability' else ('ubertip','description')
                raw=next((entry[k] for k in keys if entry.get(k)), '')
                description,notes=clean_text(raw,values)
                if description:
                    row=data.setdefault(kind,{}).setdefault(code,{})
                    row['description_zh' if locale=='zhCN' else 'description_en']=description
                    if notes:row['partial_zh' if locale=='zhCN' else 'partial_en']=True;unresolved+=len(notes)
                    covered+=1
            fallback=0
            if kind in ('ability','unit'):
                for code,record in values.items():
                    if kind=='ability' and 'alias' not in record:continue
                    if kind=='unit' and 'unitID' not in record:continue
                    field='description_zh' if locale=='zhCN' else 'description_en'
                    if data.get(kind,{}).get(code,{}).get(field):continue
                    description=data_description(kind,code,record,metadata,labels,locale=='zhCN')
                    if description:
                        entry=data.setdefault(kind,{}).setdefault(code,{})
                        entry[field]=description
                        entry['data_zh' if locale=='zhCN' else 'data_en']=True;fallback+=1
            stats[locale+'/'+kind]={'descriptions':covered,'data_summaries':fallback,'unresolved_variables':unresolved}
    encoded=base64.b85encode(zlib.compress(json.dumps(data,ensure_ascii=False,separators=(',',':')).encode(),9)).decode()
    chunks='\n'.join('    '+repr(encoded[i:i+100]) for i in range(0,len(encoded),100))
    module='''"""Offline descriptions from Warcraft III 3.0.1.24371 base object tables.

Map overrides and campaign scripts are not reflected in this reference data.
Generated by tools/generate_war3_id_descriptions.py; runtime uses no local game files.
"""
import base64,json,zlib
from functools import lru_cache
SOURCE = 'Warcraft III 3.0.1.24371 基础资料（游戏自带中文 / 英文）'
SOURCE_SHA256 = '''+repr(files)+'''
_DATA = (
'''+chunks+'''
)
@lru_cache(1)
def get_descriptions():
    return json.loads(zlib.decompress(base64.b85decode(''.join(_DATA))).decode('utf8'))
def description_for(kind, rawcode):
    row = get_descriptions().get(kind, {}).get(rawcode, {})
    return dict(description_zh=row.get('description_zh', ''), description_en=row.get('description_en', ''),
                description_source=SOURCE if row else '', description_partial=bool(row.get('partial_zh') or row.get('partial_en')))
'''
    destination.write_text(module,encoding='utf8');audit.write_text(json.dumps(dict(stats=stats,files=files,bytes=len(module.encode())),ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(stats))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('destination',type=Path);parser.add_argument('audit',type=Path);a=parser.parse_args();generate(a.source,a.destination,a.audit)
