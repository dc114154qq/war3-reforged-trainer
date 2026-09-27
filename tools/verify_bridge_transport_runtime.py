"""Real Windows transport checks against a disposable hidden window, not a game.

The camera work intentionally has unmatched TLS and cannot invoke its placeholder
handlers. This proves delivery/cleanup only, never game capability success.
"""
import ctypes as c
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import war3_engine_transport as t


def host():
    create=t.api(t.u,'CreateWindowExW',t.P,t.U,c.c_wchar_p,c.c_wchar_p,t.U,
                 c.c_int,c.c_int,c.c_int,c.c_int,t.P,t.P,t.P,t.P)
    hwnd=create(0,'STATIC','loader transport fixture',0,0,0,1,1,None,None,None,None)
    if not hwnd:raise c.WinError(c.get_last_error())
    owner=t.U();tid=t.window_thread(hwnd,c.byref(owner))
    print(json.dumps({'pid':os.getpid(),'hwnd':hwnd,'tid':tid}),flush=True)
    msg=c.create_string_buffer(64)
    get=t.api(t.u,'GetMessageW',c.c_int,t.P,t.P,t.U,t.U)
    dispatch=t.api(t.u,'DispatchMessageW',c.c_ssize_t,t.P)
    while get(msg,None,0,0)>0:dispatch(msg)


def run(image, mode):
    child=subprocess.Popen([sys.executable,__file__,'--host'],stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE,text=True,creationflags=0x08000000)
    try:
        target=json.loads(child.stdout.readline())
        real_call=t.remote_thread_call
        real_diagnostic=t.diagnose_mapped_loader
        calls=0
        def call(*args,**kwargs):
            nonlocal calls
            calls+=1
            if mode!='normal' and calls==1:
                return 0,0 # explicit primary-load failure injection only
            return real_call(*args,**kwargs)
        def diagnostic(handle,entry,path,load,error,ldr,free,**kwargs):
            if mode=='manual':
                # This real target API returns NULL for an unregistered SEC_IMAGE.
                memory=type('M',(),{'handle':handle,'pid':target['pid']})()
                load=t.resolve(memory,'kernel32','GetModuleHandleW');ldr=0
            return real_diagnostic(handle,entry,path,load,error,ldr,free,**kwargs)
        payload=struct.pack('<12Q',*[0x20000+i*0x100 for i in range(11)],0x10000)+bytes(160)
        with patch.object(t,'remote_thread_call',call),patch.object(t,'diagnose_mapped_loader',diagnostic):
            report=t._dispatch_once(target['pid'],target['hwnd'],target['tid'],Path(image).resolve(),0,payload,kind='camera')
        expected={'normal':'target_loadlibrary','recovered':'target_loader_recovered','manual':'sec_image_fallback'}[mode]
        assert report.get('image_route')==expected,report
        assert report.get('callback_verified') and report.get('query_completed'),report
        assert report.get('safe_to_release') and not report.get('allocations_retained'),report
        work=bytes.fromhex(report['work_result_hex'])
        assert struct.unpack_from('<I',work,180)[0]!=0, 'TLS mismatch did not reject placeholder work'
        report['test_scope']='real Windows callback and cleanup; intentional TLS rejection; no game API invoked'
        report['failure_injection']=mode
        report['passed']=True
        return report
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)


if __name__=='__main__':
    if sys.argv[1]=='--host':host()
    else:print(json.dumps(run(sys.argv[1],sys.argv[2]),ensure_ascii=False))
