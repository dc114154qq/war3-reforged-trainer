"""Read only the known loader .data section for runtime table pointers."""
import hashlib,json,sys
from pathlib import Path
import pefile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from war3_reforged_trainer import ProcessMemory
pid=int(sys.argv[1]);base=int(sys.argv[2],0);image=Path('E:/Warcraft III/_retail_/x86_64/war3_loader.dll')
pe=pefile.PE(str(image),fast_load=True);sec=next(s for s in pe.sections if s.Name.rstrip(b'\0')==b'.data')
data=bytearray();gaps=[]
with ProcessMemory(pid) as memory:
 for offset in range(0,sec.Misc_VirtualSize,4096):
  size=min(4096,sec.Misc_VirtualSize-offset)
  try:data.extend(memory.read(base+sec.VirtualAddress+offset,size))
  except OSError as exc:data.extend(bytes(size));gaps.append({'rva':hex(sec.VirtualAddress+offset),'error':exc.winerror})
out=ROOT/'analysis/native-bootstrap-24268/loader-runtime-data.bin';out.write_bytes(data)
report={'pid':pid,'base':hex(base),'rva':hex(sec.VirtualAddress),'bytes':len(data),'gaps':gaps,'sha256':hashlib.sha256(data).hexdigest(),'scope':'Known loader data section only; read-only'}
(ROOT/'analysis/native-bootstrap-24268/loader-data.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in report.items() if k!='gaps'},indent=2));print('gaps',len(gaps))
