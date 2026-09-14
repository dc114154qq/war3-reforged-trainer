"""Compare an image-backed telemetry entry with the private-page marker.

Only the probe's import-independent export executes. The image is mapped with
SEC_IMAGE by Windows, not manually reconstructed. No target code is patched.
"""
import argparse
import ctypes as c
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import runpy
import struct
import subprocess
import pefile

ROOT=Path(__file__).resolve().parents[1]
probe=runpy.run_path(str(ROOT/'analysis/verify-loader-thread.py'))
api,k=probe['api'],probe['k']
P,U,Z=c.c_void_p,c.c_ulong,c.c_size_t
create_file=api(k,'CreateFileW',P,c.c_wchar_p,U,U,P,U,U,P)
create_mapping=api(k,'CreateFileMappingW',P,P,P,U,U,U,c.c_wchar_p)
nt=c.WinDLL('ntdll')
map_section=api(nt,'NtMapViewOfSection',c.c_long,P,P,c.POINTER(P),Z,Z,P,c.POINTER(Z),U,U,U)
unmap_section=api(nt,'NtUnmapViewOfSection',c.c_long,P,P)
query_memory=api(nt,'NtQueryVirtualMemory',c.c_long,P,P,U,P,Z,c.POINTER(Z))


def image_loader(image,handle,path,load_address,error_address,timeout,capture_startup=False):
    pe=pefile.PE(str(image))
    export=next(s for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name==b'ProbeLoaderEntry')
    file=section=block=None
    view=P();view_size=Z();pending=False
    result={'created':False,'completed':False,'stage':None,'marker_memory_kind':'SEC_IMAGE'}
    try:
        file=create_file(str(image),0x80000000,5,None,3,0x80,None)
        if file==P(-1).value:
            file=None
            raise c.WinError(c.get_last_error())
        section=create_mapping(file,None,0x1000002,0,0,None)
        if not section:raise c.WinError(c.get_last_error())
        status=map_section(section,handle,c.byref(view),0,0,None,c.byref(view_size),2,0,2)
        result['map_status']=hex(status&0xffffffff)
        if status<0:raise RuntimeError('NtMapViewOfSection failed '+hex(status&0xffffffff))
        entry=view.value+export.address
        mbi=c.create_string_buffer(48);returned=Z()
        status=query_memory(handle,entry,0,mbi,48,c.byref(returned))
        if status<0 or returned.value!=48:raise RuntimeError('Memory kind query failed')
        result.update(image_base=hex(view.value),entry=hex(entry),memory_type=hex(struct.unpack_from('<I',mbi.raw,40)[0]))
        if result['memory_type']!='0x1000000':raise RuntimeError('Expected MEM_IMAGE')
        if probe['bytes_at'](handle,entry,16)!=pe.get_data(export.address,16):raise RuntimeError('Mapped entry bytes differ')
        block=probe['alloc'](handle,None,48,0x3000,4)
        if not block:raise c.WinError(c.get_last_error())
        payload=struct.pack('<QQQIIQII',path,load_address,error_address,0,0,0,0,0)
        buffer,written=c.create_string_buffer(payload),Z()
        if not probe['write'](handle,block,buffer,48,c.byref(written)) or written.value!=48:raise c.WinError(c.get_last_error())
        result.update(probe['invoke'](handle,entry,block,timeout,capture_startup))
        pending=result['created'] and not result['completed']
        values=struct.unpack('<QQQIIQII',probe['bytes_at'](handle,block,48))
        result.update(stage=values[3],module_result=hex(values[5]),loader_last_error=values[6],marker_block_address=hex(block))
    except Exception as exc:
        result['marker_error']=str(exc)
    finally:
        if not pending:
            if block:result['marker_block_freed']=bool(probe['free'](handle,block,0,0x8000))
            if view.value:result['image_unmap_status']=hex(unmap_section(handle,view)&0xffffffff)
        else:
            result['pending_allocations_retained']=True
        if section:probe['close'](section)
        if file:probe['close'](file)
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    target=ap.add_mutually_exclusive_group(required=True)
    target.add_argument('--pid',type=int)
    target.add_argument('--local-host',type=Path)
    ap.add_argument('--dll',type=Path,required=True)
    ap.add_argument('--entry-image',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();child=None
    try:
        if args.local_host:
            child=subprocess.Popen([str(args.local_host.resolve())],stdout=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
            pid,tid,hwnd=map(int,child.stdout.readline().split())
            assert pid==child.pid
        else:pid=args.pid
        def marked(*a,**kw):return image_loader(args.entry_image.resolve(),*a,**kw)
        probe['inspect'].__globals__['marked_load']=marked
        report=probe['inspect'](pid,args.dll.resolve(),3000,marker=True,capture_startup=True)
        report.update(entry_image=str(args.entry_image.resolve()),captured_utc=datetime.now(timezone.utc).isoformat(),local_host=bool(child))
        tmp=args.output.with_suffix('.tmp');tmp.write_text(json.dumps(report,indent=2),encoding='utf-8');os.replace(tmp,args.output)
        print(json.dumps({k:v for k,v in report.items() if k!='load_thread'}|{'load_thread':{k:v for k,v in report.get('load_thread',{}).items() if k!='startup'}}))
        if child:
            assert report.get('attach_pid_matches')
            assert report['load_thread']['stage']==2 and report['load_thread']['image_unmap_status']=='0x0'
            assert report['allocation_freed'] and report.get('module_after_unload') is None
    finally:
        if child:
            probe['helper']['post_thread'](tid,0x12,0,0)
            child.wait(timeout=5)


if __name__=='__main__':main()
