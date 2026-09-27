"""Isolated Windows SEC_IMAGE smoke. Never opens or writes a game process.

Run each case in a disposable Python process so a native failure cannot affect
the trainer or the user's game. Uses real mapping, imports, SEH and loader APIs.
"""
import ctypes as c
import json
import os
from pathlib import Path
import struct
import sys
from types import SimpleNamespace as S
import pefile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import war3_engine_transport as t


def run(image, scenario):
    image=Path(image).resolve()
    pe=pefile.PE(str(image))
    exports={s.name:s.address for s in pe.DIRECTORY_ENTRY_EXPORT.symbols}
    process=t.current_process()
    memory=S(handle=process,pid=os.getpid())
    file=t.create_file(str(image),0x80000000,5,None,3,0x80,None)
    if file==t.P(-1).value: raise c.WinError(c.get_last_error())
    section=None; view=t.P(); releasable=True
    try:
        section=t.create_mapping(file,None,0x1000002,0,0,None)
        if not section:raise c.WinError(c.get_last_error())
        size=t.Z()
        status=t.map_section(section,process,c.byref(view),0,0,None,c.byref(size),2,0,2)
        if status<0:raise RuntimeError(hex(status&0xffffffff))
        base=view.value
        imports=t.initialize_mapped_imports(memory,base,pe)
        region=t.describe_fault_instruction(process,{'instruction':hex(base+pe.OPTIONAL_HEADER.DATA_DIRECTORY[12].VirtualAddress)})
        assert region['protect'] in ('0x2','0x20','0x80','0x8'),region
        query=c.WINFUNCTYPE(t.U,t.P)(base+exports[b'BridgeTestMappedImport'])
        assert query(base)==1, 'Real VirtualQuery import call failed'
        path=c.create_unicode_buffer(str(image) if scenario=='success' else str(image.parent/'does-not-exist-loader-test.dll'))
        load=t.resolve(memory,'kernel32','LoadLibraryW')
        if scenario=='fault':load=base+exports[b'BridgeTestLoaderFault']
        d=pe.OPTIONAL_HEADER.DATA_DIRECTORY[3]
        result=t.diagnose_mapped_loader(process,base+exports[b'BridgeDiagnoseLoadSafe'],
            c.addressof(path),load,t.resolve(memory,'kernel32','GetLastError'),
            t.resolve(memory,'ntdll','LdrLoadDll'),t.resolve(memory,'kernel32','FreeLibrary'),
            unwind=(t.resolve(memory,'ntdll','RtlAddFunctionTable'),t.resolve(memory,'ntdll','RtlDeleteFunctionTable'),
                    t.resolve(memory,'ntdll','__C_specific_handler'),base+d.VirtualAddress,base,d.Size//12),
            keep_loaded=True)
        releasable=not result.get('allocations_retained') and not result.get('image_must_remain_mapped')
        assert result.get('unwind',{}).get('registered_manually'),result
        assert result['unwind']['removed'],result
        if scenario=='fault':
            assert result['unwind']['exception_code']=='0xc0000005',result
            assert result['stage']==3 and not result['completed'],result
            fault=t.decode_fault(t.bytes_at(process,base+exports[b'bridge_fault'],96))
            assert fault['address']=='0x108' and fault['access']==0,fault
            result['fault']=fault
        elif scenario=='missing':
            assert result['completed'] and result['module']=='0x0',result
            assert result['last_error']!=0 and result['ldr_status']!='0x0',result
        else:
            assert result['completed'] and result['ownership_transferred'],result
            loaded=int(result['module'],16)
            assert t.module_base(memory,image.name,refresh=True)==loaded
            assert t.normalized_path(t.remote_module_path(process,loaded))==t.normalized_path(image)
            cleanup=t.remote_free_library(memory,loaded,t.resolve(memory,'kernel32','FreeLibrary'))
            assert cleanup['unloaded'],cleanup
            assert not t.module_base(memory,image.name,refresh=True)
            result['cleanup']=cleanup
        return {'scenario':scenario,'passed':True,'imports':imports,'iat_mapping':region,'diagnostic':result}
    finally:
        if view.value and releasable:
            assert t.unmap_section(process,view)==0
        if section:t.close(section)
        t.close(file)


if __name__=='__main__':
    print(json.dumps(run(sys.argv[1],sys.argv[2]),ensure_ascii=False))
