"""Find offline RIP-relative references to selected native registration names."""
import json
from pathlib import Path
import struct
import sys
import capstone
import pefile

root=Path(__file__).resolve().parents[1]
pe=pefile.PE(sys.argv[1],fast_load=True)
text=next(s for s in pe.sections if s.Name.rstrip(b'\0')==b'.text')
captured=(root/'analysis/native-bootstrap-24268/module-text.bin').read_bytes()
shared=(root/'analysis/native-bootstrap-24268/section-text.bin').read_bytes()
metadata=json.loads((root/'analysis/native-bootstrap-24268/module-text.json').read_text())
gaps={int(r['rva'],16) for r in metadata['gaps']}
code=text.get_data()
names=('GroupEnumUnitsSelected','GetUnitState','GetHeroStr','UnitAddAbility')
targets={}
for section in pe.sections:
    data=(root/'analysis/native-bootstrap-24268/section-rdata.bin').read_bytes() if section.Name.rstrip(b'\0')==b'.rdata' else section.get_data()
    for name in names:
        start=0
        while (pos:=data.find(name.encode()+b'\0',start))>=0:
            targets[section.VirtualAddress+pos]=name
            start=pos+1
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64)
records=[]
for origin,blob in (('disk',code),('captured',captured),('shared-section',shared)):
    pos=-1
    while (pos:=blob.find(b'\x4c\x8d\x05',pos+1))>=0:
        if pos+7>len(blob): break
        ref=text.VirtualAddress+pos
        dest=ref+7+struct.unpack_from('<i',blob,pos+3)[0]
        if dest not in targets: continue
        start=pos-20
        # Registration sequence begins with a call 15 bytes before name LEA.
        if blob[pos-15]==0xe8: start=pos-15
        end=pos+24
        if origin=='captured' and any(page in gaps for page in range((text.VirtualAddress+start)&~4095,
                                                                   text.VirtualAddress+end,4096)): continue
        ins=[f'{i.address:x}: {i.mnemonic} {i.op_str}' for i in md.disasm(blob[start:end],text.VirtualAddress+start)]
        records.append(dict(origin=origin,name=targets[dest],rva=hex(ref),instructions=ins))
(root/'analysis/native-bootstrap-24268/registration-references.json').write_text(json.dumps(records,indent=2),encoding='utf8')
print('name_addresses', {hex(k):v for k,v in targets.items()})
print(json.dumps(records,indent=2))
