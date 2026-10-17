"""Build a deterministic, data-only 3.0 definition pack from extracted game tables."""
from __future__ import annotations
import argparse, hashlib, json, re, sys, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from war3_object_tables import parse_slk, parse_profile, _value
from war3_3_extension_catalog import OFFICIAL_BACKPACKS, TALENT_PROBE_RAWCODES
from war3_new_equipment_catalog import EQUIPMENT

SLKS=('AbilityData.slk','AbilityBuffData.slk','ItemData.slk','UnitAbilities.slk',
      'UnitBalance.slk','UnitData.slk','unitUI.slk','UnitWeapons.slk','UpgradeData.slk')
TOKEN=re.compile(r'(?<![A-Za-z0-9_])[A-Za-z0-9_]{4}(?![A-Za-z0-9_])')


def subset_slk(table, wanted):
    lines=['ID;PWXL;N;E',f'B;X{max(table.columns)};Y{len(wanted)+1}']
    lines.extend(f'C;X{x};Y1;K"{name}"' for x,name in table.columns.items())
    columns={v:k for k,v in table.columns.items()}
    for y,key in enumerate(wanted,2):
        lines.extend(f'C;X{columns[name]};Y{y};{token}' for name,token in table.rows[key].items())
    return ('\r\n'.join(lines+['E'])+'\r\n').encode('latin1')


def generate(folder, output):
    modern=folder/'reference-24360'
    names=list(SLKS)+sorted(p.name for p in modern.glob('*.txt')
                           if p.name.endswith(('Func.txt','Skin.txt','Addons.txt'))
                           or p.name=='AbilityStatModifiers.txt')
    tables={name:parse_slk((modern/name).read_bytes()) for name in SLKS}
    profiles={name:parse_profile((modern/name).read_bytes()) for name in names if name.endswith('.txt')}
    known={key for table in tables.values() for key in table.rows}
    seeds=set(OFFICIAL_BACKPACKS)|set(TALENT_PROBE_RAWCODES)|{e['code'] for e in EQUIPMENT}
    seeds.update(('AIni','AInx','AEqu','ASpc','ASde','ATal'))
    missing=seeds-known
    if missing:raise ValueError('Required stock definitions absent: '+repr(sorted(missing)))
    selected=set();pending=list(sorted(seeds));edges={}
    while pending:
        key=pending.pop()
        if key in selected:continue
        selected.add(key);text=[]
        for table in tables.values():
            text.extend(_value(value) for name,value in table.rows.get(key,{}).items()
                        if name not in ('comments','comment','scriptname'))
        for sections in profiles.values():
            if key in sections:text.append(sections[key].decode('latin1'))
        refs=set(TOKEN.findall('\n'.join(text)))&known-{key}
        edges[key]=sorted(refs);pending.extend(sorted(refs-selected))
    files={};required={}
    for name in names:
        if name in tables:
            ids=[key for key in tables[name].rows if key in selected]
            if not ids:continue
            raw=subset_slk(tables[name],ids)
        else:
            ids=[key for key in profiles[name] if key in selected]
            # Stat modifier labels are a tiny shared interface dictionary.
            if name=='AbilityStatModifiers.txt':ids=list(profiles[name])
            if not ids:continue
            raw=b'\r\n'.join(profiles[name][key] for key in ids)
        files['additions/'+name]=raw;required[name]=ids
        for mode in ('reference','Custom_V0','Custom_V1','Melee_V0'):
            source=modern/name if mode=='reference' else folder/(mode+'-24360')/name
            if not source.is_file():source=modern/name
            baseline=source.read_bytes()
            (parse_slk if name in tables else parse_profile)(baseline)
            files['baseline/'+mode+'/'+name]=baseline
    manifest=dict(schema=1,pack_id='war3-extension-definitions-24360-v1',
                  source_game='3.0.1.24360',source_build_key='5507d175bb77c49e221cb8d9502aeaa8',
                  policy='append_missing_rows_and_sections_preserve_existing_balance',
                  critical_abilities=sorted(set(TALENT_PROBE_RAWCODES)|{'AIni','AInx','AEqu','ASpc','ASde','ATal'}),
                  critical_items=sorted(OFFICIAL_BACKPACKS),required=required,dependencies=edges,
                  files={name:dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()) for name,raw in sorted(files.items())})
    files['manifest.json']=json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,raw in sorted(files.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,10,17,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,raw,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    result=dict(path=str(output),bytes=output.stat().st_size,sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                selected_objects=len(selected),tables={name:len(ids) for name,ids in required.items()})
    print(json.dumps(result,ensure_ascii=False))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('extracted',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();generate(args.extracted,args.output)
