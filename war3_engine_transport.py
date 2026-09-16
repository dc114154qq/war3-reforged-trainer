"""Standalone Windows image-backed 24268 bridge transport. No analysis-script dependency."""
import ctypes as c
import hashlib,json,os,struct,time,uuid
from pathlib import Path
import pefile
from war3_hero_protocol import ABI,validate_work
P,U,Z=c.c_void_p,c.c_ulong,c.c_size_t
k=c.WinDLL('kernel32',use_last_error=True)
u=c.WinDLL('user32',use_last_error=True)
nt=c.WinDLL('ntdll',use_last_error=True)
def api(lib,name,result,*args):
    f=getattr(lib,name);f.restype=result;f.argtypes=args;return f
open_process=api(k,'OpenProcess',P,U,c.c_int,U)
close=api(k,'CloseHandle',c.c_int,P)
read=api(k,'ReadProcessMemory',c.c_int,P,P,P,Z,c.POINTER(Z))
write=api(k,'WriteProcessMemory',c.c_int,P,P,P,Z,c.POINTER(Z))
alloc=api(k,'VirtualAllocEx',P,P,P,Z,U,U)
free=api(k,'VirtualFreeEx',c.c_int,P,P,Z,U)
create_thread=api(k,'CreateRemoteThread',P,P,P,Z,P,P,U,c.POINTER(U))
wait=api(k,'WaitForSingleObject',U,P,U)
get_module=api(k,'GetModuleHandleExW',c.c_int,U,P,c.POINTER(P))
current_process=api(k,'GetCurrentProcess',P)
module_name=api(k,'K32GetModuleBaseNameW',U,P,P,c.c_wchar_p,U)
create_file=api(k,'CreateFileW',P,c.c_wchar_p,U,U,P,U,U,P)
create_mapping=api(k,'CreateFileMappingW',P,P,P,U,U,U,c.c_wchar_p)
map_section=api(nt,'NtMapViewOfSection',c.c_long,P,P,c.POINTER(P),Z,Z,P,c.POINTER(Z),U,U,U)
unmap_section=api(nt,'NtUnmapViewOfSection',c.c_long,P,P)
register_message=api(u,'RegisterWindowMessageW',U,c.c_wchar_p)
window_thread=api(u,'GetWindowThreadProcessId',U,P,c.POINTER(U))
send_message_timeout=api(u,'SendMessageTimeoutW',Z,P,U,Z,c.c_ssize_t,U,U,c.POINTER(Z))

def bytes_at(handle,address,size):
    data=c.create_string_buffer(size);actual=Z()
    if not read(handle,address,data,size,c.byref(actual)) or actual.value!=size:
        raise c.WinError(c.get_last_error())
    return data.raw

def module_base(memory,name):
    if not hasattr(memory,'modules'):
        class Entry(c.Structure):
            _fields_=[('size',U),('id',U),('pid',U),('global_usage',U),('usage',U),
                ('base',P),('module_size',U),('module',P),('name',c.c_wchar*256),('path',c.c_wchar*260)]
        snapshot=api(k,'CreateToolhelp32Snapshot',P,U,U)(8,memory.pid)
        if snapshot==P(-1).value:raise c.WinError(c.get_last_error())
        try:
            first=api(k,'Module32FirstW',c.c_int,P,c.POINTER(Entry))
            next_entry=api(k,'Module32NextW',c.c_int,P,c.POINTER(Entry))
            e=Entry();e.size=c.sizeof(e);modules={}
            if not first(snapshot,c.byref(e)):raise c.WinError(c.get_last_error())
            for _ in range(4096):
                modules[e.name.lower()]=int(e.base)
                if not next_entry(snapshot,c.byref(e)):break
            else:raise RuntimeError('System module enumeration exceeded bound')
            memory.modules=modules
        finally:close(snapshot)
    return memory.modules.get(name.lower())

# Transport uses only Windows exports and fresh process-local module bases.
p=dict(api=api,open_process=open_process,close=close,read=read,write=write,alloc=alloc,free=free,
    create_thread=create_thread,wait=wait,get_module=get_module,current_process=current_process,bytes_at=bytes_at)
h=dict(u=u,module_name=module_name,module_base=module_base,send=send_message_timeout)
x=dict(create_file=create_file,create_mapping=create_mapping,map_section=map_section,unmap_section=unmap_section)

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


def decode_fault(data):
    if len(data)!=96:raise ValueError('Incomplete bridge fault record')
    magic,version,code,access,*regs=struct.unpack('<4I10Q',data)
    if not magic:return None
    if magic!=0x24268012 or version!=1:raise ValueError('Bridge fault ABI differs')
    return dict(code=hex(code),access=access,**dict(zip(
        ('instruction','address','rcx','rdx','r8','r9','rax','rbx','rsp','rbp'),map(hex,regs))))

def query_completed(state):
    return state.get('query_stage') == 2 and state.get('exception_code') == '0x0'


def dispatch(pid,hwnd,tid,image,tls_index,work_payload,kind="hero"):
    if kind=='hero':
        validate_work(work_payload);expected_abi=ABI;marker_name=b'bridge_abi';query_name=b'BridgeHeroQuery'
    elif kind=='ability':
        from war3_ability_protocol import ABI as expected_abi,validate_work as validate_ability
        validate_ability(work_payload);marker_name=b'ability_batch_abi';query_name=b'BridgeAbilityQuery'
    elif kind=='ability_field':
        from war3_ability_field_protocol import ABI as expected_abi,validate_work as validate_ability_field
        validate_ability_field(work_payload);marker_name=b'ability_field_batch_abi';query_name=b'BridgeAbilityFieldQuery'
    elif kind=='item':
        from war3_item_protocol import ABI as expected_abi,validate_work as validate_item
        validate_item(work_payload);marker_name=b'item_batch_abi';query_name=b'BridgeItemQuery'
    elif kind=='item_catalog':
        from war3_item_catalog_protocol import ABI as expected_abi,validate_work as validate_item_catalog
        validate_item_catalog(work_payload);marker_name=b'item_catalog_batch_abi';query_name=b'BridgeItemCatalogQuery'
    elif kind=='item_field':
        from war3_item_field_protocol import ABI as expected_abi,validate_work as validate_item_field
        validate_item_field(work_payload);marker_name=b'item_field_batch_abi';query_name=b'BridgeItemFieldQuery'
    elif kind=='clone':
        from war3_clone_protocol import ABI as expected_abi,validate_work as validate_clone
        validate_clone(work_payload);marker_name=b'clone_batch_abi';query_name=b'BridgeCloneQuery'
    elif kind=='unit_action':
        from war3_unit_action_protocol import ABI as expected_abi,validate_work as validate_unit_action
        validate_unit_action(work_payload);marker_name=b'unit_action_batch_abi';query_name=b'BridgeUnitActionQuery'
    elif kind=='world':
        from war3_world_protocol import ABI as expected_abi,validate_work as validate_world
        validate_world(work_payload);marker_name=b'world_batch_abi';query_name=b'BridgeWorldQuery'
    elif kind=='map_flags':
        from war3_map_flags_protocol import ABI as expected_abi,validate_work as validate_map_flags
        validate_map_flags(work_payload);marker_name=b'map_flags_batch_abi';query_name=b'BridgeMapFlagsQuery'
    elif kind=='bulk':
        from war3_bulk_protocol import ABI as expected_abi,validate_work as validate_bulk
        validate_bulk(work_payload);marker_name=b'bulk_batch_abi';query_name=b'BridgeBulkQuery'
    elif kind=='effect':
        from war3_effect_protocol import ABI as expected_abi,validate_work as validate_effect
        validate_effect(work_payload);marker_name=b'effect_batch_abi';query_name=b'BridgeEffectQuery'
    elif kind=='world_effect':
        from war3_world_effect_protocol import ABI as expected_abi,validate_work as validate_world_effect
        validate_world_effect(work_payload);marker_name=b'world_effect_batch_abi';query_name=b'BridgeWorldEffectQuery'
    elif kind=='spawn':
        from war3_spawn_protocol import ABI as expected_abi,validate_work as validate_spawn
        validate_spawn(work_payload);marker_name=b'spawn_batch_abi';query_name=b'BridgeSpawnQuery'
    elif kind=='mouse':
        from war3_mouse_protocol import ABI as expected_abi,validate_work as validate_mouse
        validate_mouse(work_payload);marker_name=b'mouse_batch_abi';query_name=b'BridgeMouseQuery'
    elif kind=='screen_mouse':
        from war3_screen_protocol import ABI as expected_abi,validate_work as validate_screen
        validate_screen(work_payload);marker_name=b'screen_mouse_batch_abi';query_name=b'BridgeScreenMouseQuery'
    elif kind=='camera':
        from war3_camera_protocol import ABI as expected_abi,validate_work as validate_camera
        validate_camera(work_payload);marker_name=b'camera_batch_abi';query_name=b'BridgeCameraQuery'
    elif kind=='position':
        from war3_position_protocol import ABI as expected_abi,validate_work as validate_position
        validate_position(work_payload);marker_name=b'position_batch_abi';query_name=b'BridgePositionQuery'
    elif kind=='terrain':
        from war3_terrain_protocol import ABI as expected_abi,validate_work as validate_terrain
        validate_terrain(work_payload);marker_name=b'terrain_batch_abi';query_name=b'BridgeTerrainQuery'
    else:raise ValueError('Unknown current-engine batch kind')
    owner=U()
    if window_thread(hwnd,c.byref(owner))!=tid or owner.value!=pid:
        raise RuntimeError('Bridge target window/thread identity changed')
    # Synchronous CallWndProc delivery is the validated route for the current
    # build. A posted message can remain queued while the render thread is
    # busy, which leaves the remote hook allocation live and quarantines the
    # session before the game native is called.
    query_mode=kind;delivery_mode='send'
    pe=pefile.PE(str(image));exports={s.name:s.address for s in pe.DIRECTORY_ENTRY_EXPORT.symbols}
    marker=exports.get(marker_name)
    if marker is None or pe.get_data(marker,len(expected_abi))!=expected_abi:
        raise ValueError('24268 bridge ABI differs; rebuild the current-engine module')
    install_rva=exports[b'BridgeInstall'];uninstall_rva=exports[b'BridgeUninstall']
    report={'pid':pid,'hwnd':hex(hwnd),'expected_callback_tid':tid,'image':str(image),
            'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'calls_game_handlers':True,'query_mode':query_mode,'delivery_mode':delivery_mode}
    handle=file=section=block=thread=work=None;view=P();safe=True
    try:
        handle=p['open_process'](0x43a,False,pid)
        if not handle:raise c.WinError(c.get_last_error())
        memory=type('Memory',(),{'handle':handle,'pid':pid})()
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
        payload=struct.pack('<7QIIQ6IQII', hwnd, *addresses, 0, tid, message, nonce,
            0, 0, 0, 0, 0, 0, sleep_address, 0, 3 if delivery_mode == "posted" else 4)
        query=view.value+exports[query_name]
        directory=pe.OPTIONAL_HEADER.DATA_DIRECTORY[3]
        if not directory.Size or directory.Size%12:raise RuntimeError('Unwind table missing')
        payload+=struct.pack('<9Q6I',resolve(memory,'kernel32','TlsGetValue'),
            resolve(memory,'ntdll','RtlAddFunctionTable'),resolve(memory,'ntdll','RtlDeleteFunctionTable'),
            view.value+directory.VirtualAddress,view.value,query,0,0,
            resolve(memory,'ntdll','__C_specific_handler'),directory.Size//12,tls_index,0,0,0,0)
        if work_payload:
            if len(work_payload) > 1024 * 1024:raise ValueError('Current-engine work block exceeds bound')
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
            if delivery_mode == 'posted':
                post=p['api'](h['u'],'PostMessageW',c.c_int,P,U,Z,c.c_ssize_t)
                delivered=bool(post(hwnd,message,nonce,0))
                report['post']={'enqueued':delivered,'error':c.get_last_error()}
                deadline=time.monotonic()+1.5
                while delivered and state['stage']!=3 and time.monotonic()<deadline:
                    time.sleep(.005);state=fields(handle,block)
            else:
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
        if b'bridge_fault' in exports:
            report['fault']=decode_fault(bytes_at(handle,view.value+exports[b'bridge_fault'],96))
        if b'bridge_recovered_faults' in exports:
            report['recovered_tail_faults']=struct.unpack('<I',bytes_at(handle,view.value+exports[b'bridge_recovered_faults'],4))[0]
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
