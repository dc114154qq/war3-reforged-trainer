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
import pefile
import time
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
    if '--stall' in sys.argv:time.sleep(15)
    msg=c.create_string_buffer(64)
    get=t.api(t.u,'GetMessageW',c.c_int,t.P,t.P,t.U,t.U)
    dispatch=t.api(t.u,'DispatchMessageW',c.c_ssize_t,t.P)
    while get(msg,None,0,0)>0:dispatch(msg)


def run(image, mode):
    environment=dict(os.environ)
    if mode=='shim':environment['__COMPAT_LAYER']='WIN7RTM'
    child=subprocess.Popen([sys.executable,__file__,'--host']+(['--stall'] if mode=='native_timeout' else []),stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE,text=True,creationflags=0x08000000,env=environment)
    try:
        target=json.loads(child.stdout.readline())
        real_call=t.remote_thread_call
        real_diagnostic=t.diagnose_mapped_loader
        real_dispatch=t._dispatch_once
        real_write=t.p['write']
        calls=0
        install_attempts=0
        image_pe=pefile.PE(str(image))
        exports={s.name:s.address for s in image_pe.DIRECTORY_ENTRY_EXPORT.symbols}
        def call(*args,**kwargs):
            nonlocal calls
            calls+=1
            if mode=='recovery_fault' and args[1]==load_address[0]:
                return 0,0
            if mode not in ('normal','native_loaded') and calls==1:
                return 0,0 # explicit primary-load failure injection only
            return real_call(*args,**kwargs)
        def diagnostic(handle,entry,path,load,error,ldr,free,**kwargs):
            if mode in ('manual','native','shim','recovery_fault','native_timeout'):
                # This real target API returns NULL for an unregistered SEC_IMAGE.
                memory=type('M',(),{'handle':handle,'pid':target['pid']})()
                load=t.resolve(memory,'kernel32','GetModuleHandleW');ldr=0
            return real_diagnostic(handle,entry,path,load,error,ldr,free,**kwargs)
        load_address=[0]
        mem=type('M',(),{'pid':target['pid'],'handle':t.open_process(0x410,False,target['pid'])})()
        try:load_address[0]=t.resolve(mem,'kernel32','LoadLibraryW')
        finally:t.close(mem.handle)
        def write(handle,address,buffer,size,written):
            nonlocal install_attempts
            if mode=='recovery_fault' and size==216:
                install_attempts+=1
                if install_attempts==1:
                    command=bytearray(c.string_at(buffer,size))
                    base=struct.unpack_from('<Q',command,144)[0]
                    struct.pack_into('<Q',command,8,base+exports[b'BridgeTestShimInstallFault'])
                    buf=c.create_string_buffer(bytes(command))
                    return real_write(handle,address,buf,size,written)
            return real_write(handle,address,buffer,size,written)
        def dispatch_once(*args,**kwargs):
            r=real_dispatch(*args,**kwargs)
            if mode=='recovery_fault' and kwargs.get('attempt')==1:
                assert r['after_cleanup']['bridge_install_trace']=='0x105',r
                assert r['fault']['access']==0 and r['fault']['address']=='0x108',r
                assert r['safe_to_release'] and not r['callback_verified'],r
                r['test_original_fault_mapping']=r['fault']['instruction_mapping']
                # Only the module attribution is supplied from captured external
                # evidence. The actual C access violation/cleanup was executed.
                r['fault']['instruction_mapping']={'mapped_file':r'C:\Windows\System32\apphelp.dll'}
            return r
        payload=struct.pack('<12Q',*[0x20000+i*0x100 for i in range(11)],0x10000)+bytes(160)
        with patch.object(t,'remote_thread_call',call),patch.object(t,'diagnose_mapped_loader',diagnostic),patch.dict(t.p,write=write),patch.object(t,'_dispatch_once',dispatch_once):
            if mode=='recovery_fault':
                report=t.dispatch(target['pid'],target['hwnd'],target['tid'],Path(image).resolve(),0,payload,kind='camera')
                assert install_attempts==2,install_attempts
                assert report['same_route_retry']['reason']=='clean_apphelp_install_read_fault',report
            else:
                report=t._dispatch_once(target['pid'],target['hwnd'],target['tid'],Path(image).resolve(),0,payload,kind='camera',hook_api='win32u' if mode in ('native','native_timeout','native_loaded') else 'user32')
        if mode=='native_timeout':
            assert not report.get('safe_to_release') and report.get('allocations_retained'),report
            assert not report.get('callback_verified') and not t._retryable_hook_install_failure(report),report
            report['test_scope']='real native hook plus unresponsive disposable window; no callback/replay; allocations retained until host termination'
            report['passed']=True
            return report
        expected={'normal':'target_loadlibrary','native_loaded':'target_loadlibrary','recovered':'target_loader_recovered','manual':'sec_image_fallback','native':'sec_image_fallback','shim':'sec_image_fallback','recovery_fault':'sec_image_fallback'}[mode]
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
