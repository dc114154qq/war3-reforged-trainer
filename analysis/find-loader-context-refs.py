"""Record loader RIP-relative references near the known game-context fields."""
import json
from pathlib import Path
import re
import struct
ROOT=Path(__file__).resolve().parents[1]
b=(ROOT/'analysis/native-bootstrap-24268/loader-runtime-text.bin').read_bytes()
base=0x7fff0ea40000; targets=(0x7fff10bf6c70,0x7fff10bf6c78,0x7fff10bf7c40)
hits=[]
for match in re.finditer(rb'[\x40-\x4f][\x8b\x8d\x89][\x05\x0d\x15\x1d\x25\x2d\x35\x3d]',b):
    pos=match.start()
    if pos+7>len(b):continue
    target=base+0x10000+pos+7+struct.unpack_from('<i',b,pos+3)[0]
    if any(abs(target-t)<=32 for t in targets):
        hits.append({'offset':hex(base+0x10000+pos),'target':hex(target),'bytes':b[pos:pos+7].hex()})
report={'build':'3.0.0.24268','loader_text_sha256':'9c366fce157819e5b628a56d499fd6af64c356d29d57f9c6c2f56849b24d133b',
        'targets':[hex(x) for x in targets],'references':hits,'scope':'Raw reference evidence; no loader call'}
(ROOT/'analysis/native-bootstrap-24268/loader-context-refs.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report,indent=2))
