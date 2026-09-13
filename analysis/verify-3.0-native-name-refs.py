"""Verify common RIP-relative pointer forms against the 3.0 native name directory."""
import json
from pathlib import Path
import struct
ROOT=Path(__file__).resolve().parents[1]
blob=(ROOT/'analysis/native-bootstrap-24268/section-text.bin').read_bytes()
image=0x7ff6b8830000
targets={image+0x2260000+o:n for n,o in {
    'GroupEnumUnitsSelected':0x6c04b8,'GetUnitState':0x6c0d08,
    'GetHeroStr':0x6c1488,'UnitAddAbility':0x6c1d48,
    'BlzGetUnitAbilityByIndex':0x6c9870}.items()}
patterns=(b'\x48\x8d\x05',b'\x48\x8b\x05',b'\x4c\x8d\x05',b'\x4c\x8b\x05',
          b'\x48\x8d\x0d',b'\x48\x8d\x15',b'\x4c\x8d\x0d',b'\x4c\x8d\x15')
hits=[]
for pattern in patterns:
    pos=blob.find(pattern)
    while pos>=0:
        if pos+7<=len(blob):
            target=image+0x1000+pos+7+struct.unpack_from('<i',blob,pos+3)[0]
            if target in targets:
                hits.append({'opcode':pattern.hex(),'offset':hex(image+0x1000+pos),
                             'target':hex(target),'name':targets[target]})
        pos=blob.find(pattern,pos+1)
report={'build':'3.0.0.24268','text_sha256':'597a67135a58f8662cab111d1d2551fe518c690b5fccc8a8eaa70c5971e29305',
        'checked_forms':[p.hex() for p in patterns],'hits':hits,
        'scope':'Raw byte check only; no handler execution or runtime writes'}
(ROOT/'analysis/native-bootstrap-24268/native-name-riprefs.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report,indent=2))
