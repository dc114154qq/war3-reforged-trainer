"""Research-only: inspect this game's section handles, without scanning its address space."""
import ctypes as c
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from war3_reforged_trainer import kernel32
pid=int(sys.argv[1])
nt=c.WinDLL('ntdll')
nt.NtQueryInformationProcess.argtypes=[c.c_void_p,c.c_ulong,c.c_void_p,c.c_ulong,c.c_void_p]
nt.NtQueryObject.argtypes=[c.c_void_p,c.c_ulong,c.c_void_p,c.c_ulong,c.c_void_p]
nt.NtQuerySection.argtypes=[c.c_void_p,c.c_ulong,c.c_void_p,c.c_ulong,c.c_void_p]
kernel32.DuplicateHandle.argtypes=[c.c_void_p,c.c_void_p,c.c_void_p,c.c_void_p,c.c_ulong,c.c_bool,c.c_ulong]
class Entry(c.Structure):
    _fields_=[('handle',c.c_void_p),('handles',c.c_size_t),('pointers',c.c_size_t),
              ('access',c.c_ulong),('type',c.c_ulong),('attributes',c.c_ulong),('reserved',c.c_ulong)]
class UString(c.Structure):
    _fields_=[('length',c.c_ushort),('maximum',c.c_ushort),('buffer',c.c_void_p)]
class SectionInfo(c.Structure):
    _fields_=[('base',c.c_void_p),('attributes',c.c_ulong),('size',c.c_longlong)]
process=kernel32.OpenProcess(0x440,False,pid)
if not process: raise c.WinError(c.get_last_error())
rows=[]
try:
    length=65536
    for attempt in range(4):
        buffer=c.create_string_buffer(length);needed=c.c_ulong()
        status=nt.NtQueryInformationProcess(process,51,buffer,length,c.byref(needed))
        if status>=0: break
        if status&0xffffffff not in (0xc0000004,0x80000005): raise RuntimeError(hex(status&0xffffffff))
        length=max(length*2,needed.value)
    else: raise RuntimeError('Unstable handle list')
    count=c.c_size_t.from_buffer(buffer).value
    assert 16+count*c.sizeof(Entry)<=length
    for index in range(count):
        item=Entry.from_buffer_copy(buffer,16+index*c.sizeof(Entry))
        duplicate=c.c_void_p()
        if not kernel32.DuplicateHandle(process,item.handle,kernel32.GetCurrentProcess(),c.byref(duplicate),0,False,2): continue
        try:
            typename=c.create_string_buffer(2048)
            if nt.NtQueryObject(duplicate,2,typename,len(typename),None)<0: continue
            name=UString.from_buffer(typename)
            if c.wstring_at(name.buffer,name.length//2)!='Section': continue
            info=SectionInfo()
            result=nt.NtQuerySection(duplicate,0,c.byref(info),c.sizeof(info),None)
            if result<0: continue
            rows.append({'handle':hex(item.handle),'access':hex(item.access),'size':info.size,'attributes':hex(info.attributes)})
        finally: kernel32.CloseHandle(duplicate)
finally: kernel32.CloseHandle(process)
report={'pid':pid,'scope':'Section metadata only; no game writes or address-space scans','sections':rows}
(ROOT/'analysis/native-bootstrap-24268/module-sections.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print('section_count',len(rows));print(json.dumps([r for r in rows if r['size']>16*1024*1024],indent=2))
