"""Single-message mapped-image hook test. Never calls game handlers."""
import argparse
import ctypes as c
from datetime import datetime, timezone
import hashlib
import traceback
import json
import os
from pathlib import Path
import runpy
import struct
import subprocess
import time
import uuid
import pefile

ROOT=Path(__file__).resolve().parents[1]
x=runpy.run_path(str(ROOT/'analysis/verify-image-thread-entry.py'))
p=x['probe'];h=p['helper'];P,U,Z=c.c_void_p,c.c_ulong,c.c_size_t
register_message=p['api'](h['u'],'RegisterWindowMessageW',U,c.c_wchar_p)


def resolve(memory,library,name):
    fn=getattr(c.WinDLL(library),name);local=c.cast(fn,P).value
    owner=P();text=c.create_unicode_buffer(1024)
    if not p['get_module'](6,local,c.byref(owner)):raise c.WinError(c.get_last_error())
    if not h['module_name'](p['current_process'](),owner,text,len(text)):raise c.WinError(c.get_last_error())
    remote=h['module_base'](memory,text.value)
    if not remote:raise RuntimeError('Missing remote module '+text.value)
    address=remote+local-owner.value
    if p['bytes_at'](memory.handle,address,16)!=c.string_at(local,16):raise RuntimeError('Entry differs: '+name)
    return address


def fields(handle,address):
    v=struct.unpack('<7QIIQ6I',p['bytes_at'](handle,address,96))
    state=dict(zip(('hook','target_tid','message','nonce','stage','last_error','callback_tid','callback_count','detached','active'),v[6:]))
    extra=struct.unpack('<9Q6I',p['bytes_at'](handle,address+112,96))
    state.update(query_result=hex(extra[6]),tls_value=hex(extra[7]),query_stage=extra[11],exception_code=hex(extra[12]),unwind_registered=extra[13],unwind_removed=extra[14])
    return state


def can_release(completed, delivered, state):
    return bool(completed and (not state['hook'] or
        delivered and state['stage'] == 3 and state['detached'] and state['active'] == 0)
        and (not state.get('unwind_registered') or state.get('unwind_removed')))


def query_completed(state):
    return state.get('query_stage') == 2 and state.get('exception_code') == '0x0'


def inspect(pid,hwnd,tid,image,query_mode="none",tls_index=0,native_address=0,work_payload=b""):
    pe=pefile.PE(str(image));exports={s.name:s.address for s in pe.DIRECTORY_ENTRY_EXPORT.symbols}
    install_rva=exports[b'ProbeInstallLocalHook'];uninstall_rva=exports[b'ProbeUninstallLocalHook']
    report={'pid':pid,'hwnd':hex(hwnd),'expected_callback_tid':tid,'image':str(image),
            'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'calls_game_handlers':query_mode in ('native','selection','unit'),'query_mode':query_mode}
    handle=file=section=block=thread=work=None;view=P();safe=True
    try:
        p['enable_debug_privilege']();handle=p['open_process'](0x43a,False,pid)
        if not handle:raise c.WinError(c.get_last_error())
        memory=type('Memory',(),{'handle':handle})()
        addresses=[resolve(memory,lib,name) for lib,name in [('user32','SetWindowsHookExW'),
            ('user32','UnhookWindowsHookEx'),('user32','CallNextHookEx'),
            ('kernel32','GetCurrentThreadId'),('kernel32','GetLastError')]]
        sleep_address=resolve(memory,'kernel32','Sleep')
        file=x['create_file'](str(image),0x80000000,5,None,3,0x80,None)
        if file==P(-1).value:file=None;raise c.WinError(c.get_last_error())
        section=x['create_mapping'](file,None,0x1000002,0,0,None)
        if not section:raise c.WinError(c.get_last_error())
        size=Z();status=x['map_section'](section,handle,c.byref(view),0,0,None,c.byref(size),2,0,2)
        if status<0:raise RuntimeError('Image map failed '+hex(status&0xffffffff))
        report['image_base']=hex(view.value)
        for rva in (install_rva,uninstall_rva):
            if p['bytes_at'](handle,view.value+rva,16)!=pe.get_data(rva,16):raise RuntimeError('Image bytes differ')
        block=p['alloc'](handle,None,216,0x3000,4)
        if not block:raise c.WinError(c.get_last_error())
        report['command_address']=hex(block)
        message=register_message('Codex.War3.DispatchProbe.'+str(uuid.uuid4()))
        if not message:raise c.WinError(c.get_last_error())
        nonce=int.from_bytes(os.urandom(8),'little') & 0x7fffffffffffffff
        if query_mode in ('fault','selection_fixture'):nonce=1
        payload=struct.pack('<7QIIQ6IQII', hwnd, *addresses, 0, tid, message, nonce,
            0, 0, 0, 0, 0, 0, sleep_address, 0, 0)
        query = (view.value+exports[b'ProbeSelectionFixtureQuery'] if query_mode=='selection_fixture' else
                 view.value+exports[b'ProbeSelectionQuery'] if query_mode=='selection' else
                 view.value+exports[b'ProbeUnitQuery'] if query_mode=='unit' else
                 view.value+exports[b'ProbeConstantQuery'] if query_mode=='constant' else
                 view.value+exports[b'ProbeFaultQuery'] if query_mode=='fault' else native_address if query_mode=='native' else 0)
        directory=pe.OPTIONAL_HEADER.DATA_DIRECTORY[3]
        if not directory.Size or directory.Size%12:raise RuntimeError('Unwind table missing')
        payload+=struct.pack('<9Q6I',resolve(memory,'kernel32','TlsGetValue'),
            resolve(memory,'ntdll','RtlAddFunctionTable'),resolve(memory,'ntdll','RtlDeleteFunctionTable'),
            view.value+directory.VirtualAddress,view.value,query,0,0,
            resolve(memory,'ntdll','__C_specific_handler'),directory.Size//12,tls_index,0,0,0,0)
        if work_payload:
            if len(work_payload) > 4096:raise ValueError('Diagnostic work block exceeds bound')
            work=p['alloc'](handle,None,len(work_payload),0x3000,4)
            if not work:raise c.WinError(c.get_last_error())
            buf=c.create_string_buffer(bytes(work_payload));n=Z()
            if not p['write'](handle,work,buf,len(work_payload),c.byref(n)) or n.value!=len(work_payload):raise c.WinError(c.get_last_error())
            report['work_address']=hex(work)
        payload+=struct.pack('<Q',work or 0)
        written=Z();buffer=c.create_string_buffer(payload)
        if not p['write'](handle,block,buffer,216,c.byref(written)) or written.value!=216:raise c.WinError(c.get_last_error())
        safe=False
        worker_tid=U()
        thread=p['create_thread'](handle,None,0,view.value+install_rva,block,0,c.byref(worker_tid))
        if not thread:
            safe=True
            raise c.WinError(c.get_last_error())
        report['install_thread']={'tid':worker_tid.value,'created':True}
        deadline=time.monotonic()+1.5
        state=fields(handle,block)
        while state['stage'] < 2 and time.monotonic() < deadline:
            if p['wait'](thread,0)==0:break
            time.sleep(0.005);state=fields(handle,block)
        report['after_install']=state
        delivered=False
        if state['stage']==2 and state['hook']:
            reply=Z();c.set_last_error(0)
            delivered=bool(h['send'](hwnd,message,nonce,0,3,1500,c.byref(reply)))
            report['send']={'completed':delivered,'error':c.get_last_error()}
        state=fields(handle,block);report['after_send']=state
        stop=c.c_ulong(1);written=Z()
        if not p['write'](handle,block+104,c.byref(stop),4,c.byref(written)):
            raise c.WinError(c.get_last_error())
        completed=p['wait'](thread,1500)==0
        report['install_thread']['completed']=completed
        state=fields(handle,block);report['after_cleanup']=state
        safe=can_release(completed, delivered, state)
        report['callback_verified']=bool(safe and state['callback_tid']==tid and state['callback_count']==1)
        report['query_completed']=query_completed(state)
        if work:report['work_result_hex']=p['bytes_at'](handle,work,len(work_payload)).hex()
    except Exception as exc:
        report['error']=repr(exc)
        report['traceback']=traceback.format_exc()
    finally:
        report['safe_to_release']=safe
        if thread:p['close'](thread)
        if handle:
            if safe:
                if work:report['work_freed']=bool(p['free'](handle,work,0,0x8000))
                if block:report['block_freed']=bool(p['free'](handle,block,0,0x8000))
                if view.value:report['image_unmap_status']=hex(x['unmap_section'](handle,view)&0xffffffff)
            else:report['allocations_retained']=True
            p['close'](handle)
        if section:p['close'](section)
        if file:p['close'](file)
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    target=ap.add_mutually_exclusive_group(required=True)
    target.add_argument('--pid',type=int);target.add_argument('--local-host',type=Path)
    ap.add_argument('--image',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument("--query-mode",choices=["none","constant","fault","selection_fixture","selection"],default="none")
    args=ap.parse_args();child=None
    try:
        if args.local_host:
            child=subprocess.Popen([str(args.local_host.resolve())],stdout=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
            pid,tid,hwnd=map(int,child.stdout.readline().split());assert pid==child.pid
        else:
            hwnd,pid=h['find_war3'](args.pid);owner=U();tid=h['window_thread'](hwnd,c.byref(owner));assert owner.value==pid
        r=inspect(pid,hwnd,tid,args.image.resolve(),query_mode=args.query_mode);r.update(captured_utc=datetime.now(timezone.utc).isoformat(),local_host=bool(child))
        tmp=args.output.with_suffix('.tmp');tmp.write_text(json.dumps(r,indent=2),encoding='utf-8');os.replace(tmp,args.output)
        print(json.dumps(r))
        if child:assert r.get('callback_verified') and r.get('image_unmap_status')=='0x0' and r.get('block_freed')
    finally:
        if child:h['post_thread'](tid,0x12,0,0);child.wait(timeout=5)


if __name__=='__main__':main()
