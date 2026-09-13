"""Read only the specified executable's .text for offline adaptation research.

No injection, game function calls, writes, heap enumeration or process scan.
The product runtime does not import this script. Raw evidence stays local.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

import pefile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from war3_reforged_trainer import ProcessMemory

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--pid',type=int,required=True)
parser.add_argument('--base',type=lambda x:int(x,0),required=True)
parser.add_argument('--image',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
raw=args.image.read_bytes()
pe=pefile.PE(data=raw,fast_load=True)
section=next(s for s in pe.sections if s.Name.rstrip(b'\0')==b'.text')
assert 0 < section.Misc_VirtualSize < 128*1024*1024
with ProcessMemory(args.pid) as memory:
    header=memory.read(args.base,4096)
    assert header[:2]==b'MZ'
    nt=struct.unpack_from('<I',header,0x3c)[0]
    assert 0x40 <= nt <= 0x800 and header[nt:nt+4]==b'PE\0\0'
    assert struct.unpack_from('<I',header,nt+8)[0]==pe.FILE_HEADER.TimeDateStamp
    assert struct.unpack_from('<I',header,nt+24+56)[0]==pe.OPTIONAL_HEADER.SizeOfImage
    chunks=[]
    gaps=[]
    for offset in range(0,section.Misc_VirtualSize,65536):
        size=min(65536,section.Misc_VirtualSize-offset)
        try:
            chunks.append(memory.read(args.base+section.VirtualAddress+offset,size))
        except OSError:
            for page in range(offset,offset+size,4096):
                count=min(4096,offset+size-page)
                try:
                    chunks.append(memory.read(args.base+section.VirtualAddress+page,count))
                except OSError as exc:
                    gaps.append(dict(rva=hex(section.VirtualAddress+page),size=count,error=exc.winerror))
                    chunks.append(bytes(count))  # Explicit holes, never accepted as code evidence.
    assert memory.read(args.base,4096)==header, 'Module header changed during capture'
data=b''.join(chunks)
args.output.parent.mkdir(parents=True,exist_ok=True)
with args.output.open('xb') as out: out.write(data)
report=dict(pid=args.pid,base=hex(args.base),text_rva=hex(section.VirtualAddress),
            bytes=len(data),image_sha256=hashlib.sha256(raw).hexdigest(),
            captured_text_sha256=hashlib.sha256(data).hexdigest(),
            gaps=gaps,complete=not gaps,
            read_only=True,scope='Specified module header and .text only; zero-filled gaps are NOT code evidence')
args.output.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in report.items() if k!='gaps'},indent=2))
print('unreadable_pages=',len(gaps))
