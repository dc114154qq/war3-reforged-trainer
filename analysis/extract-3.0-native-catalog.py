"""Extract the 3.0 native name/signature string directory without executing it."""
import json
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
data=(ROOT/'analysis/native-bootstrap-24268/section-rdata.bin').read_bytes()
names=('GroupEnumUnitsSelected','GetUnitState','GetHeroStr','UnitAddAbility','BlzGetUnitAbilityByIndex')
rows=[]
for name in names:
    positions=[m.start() for m in re.finditer(re.escape(name.encode())+rb'\0',data)]
    for pos in positions:
        window=data[max(0,pos-0x180):min(len(data),pos+0x180)]
        strings=[m.group(1).decode('ascii',errors='ignore') for m in re.finditer(rb'([^\0]{1,120})\0',window)]
        signatures=[s for s in strings if s.startswith('(') and ')' in s]
        rows.append({'name':name,'rdata_offset':hex(pos),'rva':hex(0x2260000+pos),
                     'near_signatures':signatures})
report={'build':'3.0.0.24268','source':'runtime shared .rdata read-only mapping',
        'rdata_sha256':'2e0e663dd53bb4ed6c87acc93f478844df0c49ea8f2562d9d3c00b78ee2aceaa',
        'names':rows,'scope':'Directory evidence only; no handlers invoked'}
(ROOT/'analysis/native-bootstrap-24268/native-catalog.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report,indent=2))
