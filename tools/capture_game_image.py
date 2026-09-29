"""Capture a target game's shared image locally, without remote memory writes."""
import argparse, ctypes as c, hashlib, json, os, struct
from pathlib import Path
import pefile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid',type=int,required=True)
    parser.add_argument('--image',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    k=c.WinDLL('kernel32',use_last_error=True);nt=c.WinDLL('ntdll')
    P=c.c_void_p;U=c.c_ulong
    def api(lib,name,result,*types):
        fn=getattr(lib,name);fn.restype=result;fn.argtypes=types;return fn
    open_process=api(k,'OpenProcess',P,U,c.c_bool,U)
    close=api(k,'CloseHandle',c.c_bool,P)
    current=api(k,'GetCurrentProcess',P)
    duplicate=api(k,'DuplicateHandle',c.c_bool,P,P,P,P,U,c.c_bool,U)
    query_path=api(k,'QueryFullProcessImageNameW',c.c_bool,P,U,c.c_wchar_p,c.POINTER(U))
    query_process=api(nt,'NtQueryInformationProcess',c.c_long,P,U,P,U,P)
    query_object=api(nt,'NtQueryObject',c.c_long,P,U,P,U,P)
    query_section=api(nt,'NtQuerySection',c.c_long,P,U,P,U,P)
    map_view=api(k,'MapViewOfFile',P,P,U,U,U,c.c_size_t)
    unmap=api(k,'UnmapViewOfFile',c.c_bool,P)
    class Entry(c.Structure):
        _fields_=[('handle',P),('handles',c.c_size_t),('pointers',c.c_size_t),('access',U),('type',U),('attributes',U),('reserved',U)]
    class String(c.Structure):
        _fields_=[('length',c.c_ushort),('maximum',c.c_ushort),('buffer',P)]
    class Section(c.Structure):
        _fields_=[('base',P),('attributes',U),('size',c.c_longlong)]
    process=open_process(0x440,False,args.pid)
    if not process:raise c.WinError(c.get_last_error())
    report={'pid':args.pid,'image':str(args.image.resolve()),'scope':'read-only local shared-section view; no remote writes or protection changes','sections':[]}
    try:
        path=c.create_unicode_buffer(32768);size=U(len(path))
        if not query_path(process,0,path,c.byref(size)):raise c.WinError(c.get_last_error())
        if Path(path.value).resolve()!=args.image.resolve():raise ValueError('Process image identity differs')
        pe=pefile.PE(str(args.image),fast_load=True)
        expected=(pe.FILE_HEADER.Machine,pe.FILE_HEADER.TimeDateStamp,pe.OPTIONAL_HEADER.SizeOfImage)
        report['fingerprint']=expected
        length=65536
        for _ in range(5):
            buffer=c.create_string_buffer(length);needed=U()
            status=query_process(process,51,buffer,length,c.byref(needed))
            if status>=0:break
            if status&0xffffffff not in (0xc0000004,0x80000005):raise RuntimeError(hex(status&0xffffffff))
            length=max(length*2,needed.value)
        else:raise RuntimeError('Unstable process handle list')
        count=c.c_size_t.from_buffer(buffer).value
        assert 16+count*c.sizeof(Entry)<=length
        for i in range(count):
            item=Entry.from_buffer_copy(buffer,16+i*c.sizeof(Entry));dup=P();view=None
            if not duplicate(process,item.handle,current(),c.byref(dup),0,False,2):continue
            try:
                namebuf=c.create_string_buffer(2048)
                if query_object(dup,2,namebuf,len(namebuf),None)<0:continue
                name=String.from_buffer(namebuf)
                if c.wstring_at(name.buffer,name.length//2)!='Section':continue
                info=Section()
                if query_section(dup,0,c.byref(info),c.sizeof(info),None)<0 or info.size!=expected[2]:continue
                view=map_view(dup,4,0,0,info.size)
                if not view:continue
                header=c.string_at(view,4096)
                if header[:2]!=b'MZ':continue
                offset=struct.unpack_from('<I',header,0x3c)[0]
                if not 0x40<=offset<=0x800 or header[offset:offset+4]!=b'PE\0\0':continue
                actual=(struct.unpack_from('<H',header,offset+4)[0],struct.unpack_from('<I',header,offset+8)[0],struct.unpack_from('<I',header,offset+80)[0])
                if actual!=expected:continue
                args.output.mkdir(parents=True,exist_ok=True)
                report['section_handle']=hex(item.handle)
                for s in pe.sections:
                    name=s.Name.rstrip(b'\0').decode()
                    if name not in ('.text','.rdata','.pdata'):continue
                    if s.VirtualAddress+s.Misc_VirtualSize>info.size:raise ValueError('Section bounds exceed image')
                    data=c.string_at(view+s.VirtualAddress,s.Misc_VirtualSize)
                    out=args.output/('section-'+name[1:]+'.bin');tmp=out.with_suffix('.tmp');tmp.write_bytes(data);os.replace(tmp,out)
                    report['sections'].append({'name':name,'rva':s.VirtualAddress,'size':len(data),'sha256':hashlib.sha256(data).hexdigest(),'file':out.name})
                break
            finally:
                if view:unmap(view)
                close(dup)
        else:raise RuntimeError('No shared section with matching game image fingerprint')
    finally:close(process)
    p=args.output/'capture.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(report,indent=2),encoding='utf-8');os.replace(tmp,p)
    print(json.dumps(report))


if __name__=='__main__':main()
