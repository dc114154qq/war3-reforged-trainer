"""Read a validated game image's shared section through a local read-only mapping.

The game's page protections and memory are not modified. Raw code stays local.
"""
import ctypes as c
import hashlib
import json
from pathlib import Path
import struct
import sys
import pefile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from war3_reforged_trainer import kernel32
pid=int(sys.argv[1]);handle=int(sys.argv[2],0);image=Path(sys.argv[3])
pe=pefile.PE(str(image),fast_load=True)
assert pe.FILE_HEADER.TimeDateStamp==0x6aa4de70 and pe.OPTIONAL_HEADER.SizeOfImage==0xe155000
kernel32.DuplicateHandle.argtypes=[c.c_void_p,c.c_void_p,c.c_void_p,c.c_void_p,c.c_ulong,c.c_bool,c.c_ulong]
kernel32.MapViewOfFile.argtypes=[c.c_void_p,c.c_ulong,c.c_ulong,c.c_ulong,c.c_size_t]
kernel32.MapViewOfFile.restype=c.c_void_p
kernel32.UnmapViewOfFile.argtypes=[c.c_void_p]
nt=c.WinDLL('ntdll');nt.NtQuerySection.argtypes=[c.c_void_p,c.c_ulong,c.c_void_p,c.c_ulong,c.c_void_p]
class SectionInfo(c.Structure):
    _fields_=[('base',c.c_void_p),('attributes',c.c_ulong),('size',c.c_longlong)]
process=kernel32.OpenProcess(0x40,False,pid)
if not process: raise c.WinError(c.get_last_error())
duplicate=c.c_void_p();mapping=None
report={'pid':pid,'handle':hex(handle),'read_only':True,'sections':[],
        'scope':'Locally mapped shared section; no game writes or page protection changes'}
try:
    if not kernel32.DuplicateHandle(process,handle,kernel32.GetCurrentProcess(),c.byref(duplicate),5,False,0):
        raise c.WinError(c.get_last_error())
    info=SectionInfo()
    status=nt.NtQuerySection(duplicate,0,c.byref(info),c.sizeof(info),None)
    if status<0 or info.size!=pe.OPTIONAL_HEADER.SizeOfImage: raise ValueError('Section size mismatch')
    mapping=kernel32.MapViewOfFile(duplicate,4,0,0,info.size)
    if not mapping: raise c.WinError(c.get_last_error())
    header=c.string_at(mapping,4096)
    assert header[:2]==b'MZ'
    offset=struct.unpack_from('<I',header,0x3c)[0]
    assert 0x40<=offset<=0x800 and header[offset:offset+4]==b'PE\0\0'
    assert struct.unpack_from('<I',header,offset+8)[0]==pe.FILE_HEADER.TimeDateStamp
    assert struct.unpack_from('<I',header,offset+24+56)[0]==pe.OPTIONAL_HEADER.SizeOfImage
    for section in pe.sections:
        name=section.Name.rstrip(b'\0').decode()
        if name not in ('.text','.rdata','.data'): continue
        assert section.VirtualAddress+section.Misc_VirtualSize<=info.size
        data=c.string_at(mapping+section.VirtualAddress,section.Misc_VirtualSize)
        output=ROOT/'analysis/native-bootstrap-24268'/f'section-{name[1:]}.bin'
        output.write_bytes(data)
        report['sections'].append({'name':name,'rva':hex(section.VirtualAddress),'bytes':len(data),
                                   'sha256':hashlib.sha256(data).hexdigest()})
    report['header_sha256']=hashlib.sha256(header).hexdigest()
finally:
    if mapping: kernel32.UnmapViewOfFile(mapping)
    if duplicate: kernel32.CloseHandle(duplicate)
    kernel32.CloseHandle(process)
(ROOT/'analysis/native-bootstrap-24268/section-capture.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report,indent=2))
