"""Read the bounded VEH list using offsets established from this ntdll disassembly."""
import json
from pathlib import Path
import struct
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from war3_reforged_trainer import ProcessMemory
pid=int(sys.argv[1]);head=0x7fffeb3c5590;cookie_address=0x7fffeb3ac490
rows=[]
with ProcessMemory(pid) as p:
    # Fail if the audited encode/list access instructions no longer match this OS build.
    assert p.read(0x7fffeb2bf766,6)==bytes.fromhex('8b0524cd0e00')
    assert p.read(0x7fffeb2306f5,7)==bytes.fromhex('4c8d258c4e1900')
    cookie=struct.unpack('<I',p.read(cookie_address,4))[0]
    shift=cookie&63
    initial=p.read(head,16);node,tail=struct.unpack('<QQ',initial);prior=head;seen=set()
    for index in range(64):
        if node==head: break
        if node in seen: raise ValueError('Cyclic VEH list')
        seen.add(node)
        data=p.read(node,40)
        following,back=struct.unpack_from('<QQ',data)
        if back!=prior: raise ValueError('VEH list changed')
        encoded=struct.unpack_from('<Q',data,32)[0]
        decoded=(((encoded<<shift)|(encoded>>(64-shift if shift else 64)))&0xffffffffffffffff)^cookie
        rows.append({'node':hex(node),'handler':hex(decoded)})
        prior,node=node,following
    else: raise ValueError('VEH list exceeds capture limit')
    assert prior==tail and p.read(head,16)==initial,'VEH list changed'
report={'pid':pid,'read_only':True,'handlers':rows,'scope':'Metadata only; handlers not invoked'}
(ROOT/'analysis/native-bootstrap-24268/exception-handlers.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report,indent=2))
