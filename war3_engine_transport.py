"""Standalone Windows loader-backed 24268 bridge transport. No analysis-script dependency."""
import ctypes as c
import hashlib,json,os,struct,time,traceback,uuid
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
get_exit_code=api(k,'GetExitCodeThread',c.c_int,P,c.POINTER(U))
get_mitigation=api(k,'GetProcessMitigationPolicy',c.c_int,P,c.c_int,P,Z)
get_module=api(k,'GetModuleHandleExW',c.c_int,U,P,c.POINTER(P))
current_process=api(k,'GetCurrentProcess',P)
module_name=api(k,'K32GetModuleBaseNameW',U,P,P,c.c_wchar_p,U)
module_path=api(k,'K32GetModuleFileNameExW',U,P,P,c.c_wchar_p,U)
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

def module_base(memory,name,refresh=False):
    if refresh and hasattr(memory,'modules'):
        delattr(memory,'modules')
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
    create_thread=create_thread,wait=wait,get_exit_code=get_exit_code,
    get_module=get_module,current_process=current_process,module_path=module_path,
    bytes_at=bytes_at)
h=dict(u=u,module_name=module_name,module_base=module_base,send=send_message_timeout)
x=dict(create_file=create_file,create_mapping=create_mapping,map_section=map_section,unmap_section=unmap_section)

def remote_entry_valid(data):
    return len(data)==16 and any(data)

def resolve(memory,library,name):
    fn=getattr(c.WinDLL(library),name);local=c.cast(fn,P).value
    owner=P();text=c.create_unicode_buffer(1024)
    if not p['get_module'](6,local,c.byref(owner)):raise c.WinError(c.get_last_error())
    if not h['module_name'](p['current_process'](),owner,text,len(text)):raise c.WinError(c.get_last_error())
    remote=h['module_base'](memory,text.value)
    if not remote:raise RuntimeError('Missing remote module '+text.value)
    address=remote+local-owner.value
    # The owning-module RVA is stable across processes on the same host.
    # Windows hotpatching and security software may legitimately instrument
    # only one process, so byte equality is not a valid compatibility gate.
    if not remote_entry_valid(p['bytes_at'](memory.handle,address,16)):
        raise RuntimeError('Remote entry is unreadable: '+name)
    return address


def fields(handle,address):
    v=struct.unpack('<7QIIQ6I',p['bytes_at'](handle,address,96))
    state=dict(zip(('hook','target_tid','message','nonce','stage','last_error','callback_tid','callback_count','detached','active'),v[6:]))
    extra=struct.unpack('<9Q6I',p['bytes_at'](handle,address+112,96))
    state.update(query_result=hex(extra[6]),bridge_install_trace=hex(extra[6]),tls_value=hex(extra[7]),query_stage=extra[11],exception_code=hex(extra[12]),unwind_registered=extra[13],unwind_removed=extra[14])
    return state


def remote_module_path(handle,address):
    buffer=c.create_unicode_buffer(32768)
    length=p['module_path'](handle,address,buffer,len(buffer))
    if not length:
        raise c.WinError(c.get_last_error())
    return buffer.value


def normalized_path(value):
    text=os.path.normpath(os.path.abspath(str(value)))
    if text.startswith("\\\\?\\"):
        text=text[4:]
    return os.path.normcase(text)


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


class FaultMemoryRegion(c.Structure):
    _fields_=[('base',P),('allocation_base',P),('allocation_protect',U),
              ('partition',c.c_ushort),('size',Z),('state',U),('protect',U),('type',U)]


def describe_fault_instruction(handle, fault):
    """Attribute a captured fault before unmapping; never replace its error."""
    if not fault:
        return None
    description={}
    try:
        address=int(fault['instruction'],16)
        query=api(k,'VirtualQueryEx',Z,P,P,c.POINTER(FaultMemoryRegion),Z)
        region=FaultMemoryRegion()
        if query(handle,address,c.byref(region),c.sizeof(region))!=c.sizeof(region):
            raise c.WinError(c.get_last_error())
        base=int(region.allocation_base or 0)
        description.update(allocation_base=hex(base),region_base=hex(region.base or 0),
                           region_size=int(region.size),state=hex(region.state),
                           protect=hex(region.protect),type=hex(region.type))
        if base and address>=base:
            description['allocation_offset']=hex(address-base)
        if region.type in (0x1000000,0x40000):
            mapped=api(k,'K32GetMappedFileNameW',U,P,P,c.c_wchar_p,U)
            name=c.create_unicode_buffer(32768)
            if mapped(handle,address,name,len(name)):
                description['mapped_file']=name.value
                if region.type==0x1000000:
                    description['module_rva']=hex(address-base)
            else:
                description['mapped_file_error']=c.get_last_error()
    except Exception as exc:
        description['lookup_error']=repr(exc)
    return description


def remote_thread_call(handle,address,parameter,timeout_ms):
    """Run a target-process API and return its DWORD result and thread id."""
    worker_tid=U()
    thread=p['create_thread'](handle,None,0,address,parameter,0,c.byref(worker_tid))
    if not thread:
        raise c.WinError(c.get_last_error())
    try:
        wait_result=int(p['wait'](thread,timeout_ms))
        if wait_result != 0:
            if wait_result == 0x102:
                raise TimeoutError('Remote thread did not finish within the timeout')
            raise RuntimeError('Remote thread wait failed: '+hex(wait_result))
        exit_code=U()
        if not p['get_exit_code'](thread,c.byref(exit_code)):
            raise c.WinError(c.get_last_error())
        return int(exit_code.value),int(worker_tid.value)
    finally:
        p['close'](thread)


def remote_free_library(memory,module,address,timeout_ms=1500):
    result,thread_id=remote_thread_call(memory.handle,address,module,timeout_ms)
    return dict(result=result,thread_id=thread_id,unloaded=bool(result))


def target_mitigation_policies(handle):
    policies={}
    for name,number in (('dynamic_code',2),('extension_point',6),
                        ('signature',8),('image_load',10)):
        flags=U()
        if get_mitigation(handle,number,c.byref(flags),c.sizeof(flags)):
            policies[name]=hex(flags.value)
        else:
            policies[name+'_error']=c.get_last_error()
    return policies


def diagnose_mapped_loader(handle,entry,path,load,error,ldr_load,free_library):
    block=p['alloc'](handle,None,56,0x3000,4)
    if not block:raise c.WinError(c.get_last_error())
    completed=False;started=False
    try:
        value=c.create_string_buffer(struct.pack('<4QIIQi4x',path,load,error,0,0,0,ldr_load,0),56)
        written=Z()
        if not p['write'](handle,block,value,56,c.byref(written)) or written.value!=56:
            raise c.WinError(c.get_last_error())
        started=True
        exit_code,tid=remote_thread_call(handle,entry,block,5000)
        completed=True
        data=p['bytes_at'](handle,block,56)
        module,last_error,stage=struct.unpack_from('<QII',data,24)
        ntstatus=struct.unpack_from('<I',data,48)[0]
        result={'thread_id':tid,'exit_code':hex(exit_code),'module':hex(module),
                'last_error':last_error,'ldr_status':hex(ntstatus),
                'stage':stage,'completed':exit_code==1 and stage==2}
        if module:
            try:
                result['cleanup']=remote_free_library(type('Memory',(),{'handle':handle})(),module,free_library)
            except Exception as exc:
                result['cleanup_error']=repr(exc)
        return result
    except Exception as exc:
        return {'completed':False,'error':repr(exc),'allocations_retained':started and not completed}
    finally:
        if completed or not started:p['free'](handle,block,0,0x8000)



def _dispatch_once(pid,hwnd,tid,image,tls_index,work_payload,kind="hero",attempt=1,delivery_mode=None):
    if kind=='talent_icon_control':
        from war3_talent_icon_control_protocol import ABI as expected_abi,validate_work as validate_icon
        validate_icon(work_payload);marker_name=b'talent_icon_control_abi';query_name=b'BridgeTalentIconControl'
    elif kind=='hero':
        validate_work(work_payload);expected_abi=ABI;marker_name=b'bridge_abi';query_name=b'BridgeHeroQuery'
    elif kind=='hero_attributes':
        from war3_hero_attributes_protocol import ABI as expected_abi,validate_work as validate_hero_attributes
        validate_hero_attributes(work_payload);marker_name=b'hero_attributes_batch_abi';query_name=b'BridgeHeroAttributesQuery'
    elif kind=='attack_speed':
        from war3_attack_speed_protocol import ABI as expected_abi,validate_work as validate_attack_speed
        validate_attack_speed(work_payload);marker_name=b'attack_speed_batch_abi';query_name=b'BridgeAttackSpeedQuery'
    elif kind=='unit_stats':
        from war3_unit_stats_protocol import ABI as expected_abi,validate_work as validate_unit_stats
        validate_unit_stats(work_payload);marker_name=b'unit_stats_batch_abi';query_name=b'BridgeUnitStatsQuery'
    elif kind=='talent_order':
        from war3_talent_order_protocol import validate_work as validate_talent, ABI as expected_abi
        validate_talent(work_payload);marker_name=b'talent_order_abi';query_name=b'BridgeTalentOrderQuery'
    elif kind=='talent_probe':
        from war3_talent_probe_protocol import validate_work as validate_probe, ABI as expected_abi
        validate_probe(work_payload);marker_name=b'talent_probe_abi';query_name=b'BridgeTalentProbeQuery'
    elif kind=='stat_details':
        from war3_stat_details_protocol import ABI as expected_abi,validate_work as validate_stat_details
        validate_stat_details(work_payload);marker_name=b'stat_details_batch_abi';query_name=b'BridgeStatDetailsQuery'
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
    elif kind=='position_target':
        from war3_position_target_protocol import ABI as expected_abi,validate_work as validate_position_target
        validate_position_target(work_payload);marker_name=b'position_batch_abi';query_name=b'BridgePositionQuery'
    elif kind=='terrain':
        from war3_terrain_protocol import ABI as expected_abi,validate_work as validate_terrain
        validate_terrain(work_payload);marker_name=b'terrain_batch_abi';query_name=b'BridgeTerrainQuery'
    elif kind=='equipment':
        from war3_equipment_protocol import ABI as expected_abi,validate_work as validate_equipment
        validate_equipment(work_payload);marker_name=b'equipment_batch_abi';query_name=b'BridgeEquipmentQuery'
    elif kind=='equipment_probe':
        expected_abi=struct.pack('<3I',0x24268043,216,3816)
        marker_name=b'equipment_probe_abi';query_name=b'BridgeEquipmentProbeQuery'
    elif kind=='cooldown_probe':
        expected_abi=struct.pack('<3I',0x24268044,216,648)
        marker_name=b'cooldown_probe_abi';query_name=b'BridgeCooldownProbeQuery'
    elif kind=='extension':
        from war3_extension_protocol import ABI as expected_abi,validate_work as validate_extension
        validate_extension(work_payload);marker_name=b'extension_batch_abi';query_name=b'BridgeExtensionQuery'
    elif kind=='map_bounds':
        from war3_map_bounds_protocol import ABI as expected_abi,validate_work as validate_bounds
        validate_bounds(work_payload);marker_name=b'map_bounds_batch_abi';query_name=b'BridgeMapBoundsQuery'
    else:raise ValueError('Unknown current-engine batch kind')
    owner=U()
    if window_thread(hwnd,c.byref(owner))!=tid or owner.value!=pid:
        raise RuntimeError('Bridge target window/thread identity changed')
    # Synchronous CallWndProc delivery is the validated route for the current
    # build. A posted message can remain queued while the render thread is
    # busy, which leaves the remote hook allocation live and quarantines the
    # session before the game native is called.
    query_mode=kind
    if delivery_mode is None:
        delivery_mode = 'send'
    hook_kind = 3 if delivery_mode == 'posted' else 4
    hook_name = 'WH_GETMESSAGE' if delivery_mode == 'posted' else 'WH_CALLWNDPROC'
    pe=pefile.PE(str(image));exports={s.name:s.address for s in pe.DIRECTORY_ENTRY_EXPORT.symbols}
    marker=exports.get(marker_name)
    if marker is None or pe.get_data(marker,len(expected_abi))!=expected_abi:
        raise ValueError('24268 bridge ABI differs; rebuild the current-engine module')
    install_rva=exports[b'BridgeInstall'];uninstall_rva=exports[b'BridgeUninstall']
    report={'pid':pid,'hwnd':hex(hwnd),'expected_callback_tid':tid,
            'target_window':{'hwnd':hex(hwnd),'pid':pid,'thread_id':tid},
            'process_access':'0x43a','hook_kind':hook_name,
            'message_delivery':delivery_mode,
            'route_policy':('target_LoadLibraryW+WH_GETMESSAGE+PostMessage'
                            if delivery_mode == 'posted'
                            else 'target_LoadLibraryW+WH_CALLWNDPROC+SendMessageTimeout'),
            'image':str(image),
            'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),
            'calls_game_handlers':True,'query_mode':query_mode,'delivery_mode':delivery_mode,
            'image_route':'target_loadlibrary','route_attempt':attempt}
    handle=file=section=block=thread=work=None
    load_path=None;memory=None
    image_base=0;remote_module=0;free_library_address=0
    view=P();manual_mapped=False;image_unmapped=False
    loader_completed=False;loader_succeeded=False
    remote_thread_active=False;safe=True
    try:
        handle=p['open_process'](0x43a,False,pid)
        if not handle:raise c.WinError(c.get_last_error())
        memory=type('Memory',(),{'handle':handle,'pid':pid})()
        addresses=[resolve(memory,lib,name) for lib,name in [('user32','SetWindowsHookExW'),
            ('user32','UnhookWindowsHookEx'),('user32','CallNextHookEx'),
            ('kernel32','GetCurrentThreadId'),('kernel32','GetLastError')]]
        sleep_address=resolve(memory,'kernel32','Sleep')
        load_library_address=resolve(memory,'kernel32','LoadLibraryW')
        free_library_address=resolve(memory,'kernel32','FreeLibrary')
        # Load the bridge through the target's normal loader. The previous
        # SEC_IMAGE/manual-map route could execute its first instruction but
        # die before SetWindowsHookEx on some Windows configurations, leaving
        # the command permanently at stage 1. A normal module load supplies
        # the loader's relocation, import, CFG and unwind bookkeeping.
        image_path=c.create_unicode_buffer(str(image))
        load_path=p['alloc'](handle,None,c.sizeof(image_path),0x3000,4)
        if not load_path:raise c.WinError(c.get_last_error())
        written=Z()
        if not p['write'](handle,load_path,image_path,c.sizeof(image_path),c.byref(written)) or written.value!=c.sizeof(image_path):
            raise c.WinError(c.get_last_error())
        report['image_loader']={'method':'LoadLibraryW','completed':False}
        remote_thread_active=True
        try:
            load_exit,load_tid=remote_thread_call(handle,load_library_address,load_path,5000)
        except Exception:
            report['image_loader']['thread_completed']=False
            safe=False
            raise
        remote_thread_active=False
        loader_completed=True
        report['image_loader']={'method':'LoadLibraryW','thread_id':load_tid,'exit_code':hex(load_exit),'completed':True}
        if not load_exit:
            report['target_mitigations']=target_mitigation_policies(handle)
        loader_succeeded=bool(load_exit)
        if not load_exit:
            # Some game launches reject unsigned remote DLL loads even when
            # trainer and game have the same integrity level. Fall back only
            # after a completed LoadLibraryW call returned NULL; this keeps
            # the loader route primary while retaining the validated SEC_IMAGE
            # compatibility path.
            report['image_loader']['fallback'] = 'SEC_IMAGE'
            file=x['create_file'](str(image),0x80000000,5,None,3,0x80,None)
            if file==P(-1).value:
                file=None
                raise c.WinError(c.get_last_error())
            section=x['create_mapping'](file,None,0x1000002,0,0,None)
            if not section:
                raise c.WinError(c.get_last_error())
            size=Z()
            status=x['map_section'](section,handle,c.byref(view),0,0,None,c.byref(size),2,0,2)
            if status < 0:
                raise RuntimeError('Image map failed '+hex(status & 0xffffffff))
            image_base=int(view.value or 0)
            if not image_base:
                raise RuntimeError('Image map returned a null base')
            manual_mapped=True
            report['image_route']='sec_image_fallback'
            report['image_map']={'method':'NtMapViewOfSection','status':hex(status & 0xffffffff),
                                 'size':int(size.value),'completed':True}
            diagnostic_rva=exports.get(b'BridgeDiagnoseLoad')
            if diagnostic_rva:
                diagnostic=diagnose_mapped_loader(
                    handle,image_base+diagnostic_rva,load_path,load_library_address,
                    addresses[4],resolve(memory,'ntdll','LdrLoadDll'),free_library_address)
                report['image_loader']['diagnostic']=diagnostic
                if diagnostic.get('allocations_retained') or diagnostic.get('module') not in (None,'0x0') and not diagnostic.get('cleanup',{}).get('unloaded'):
                    remote_thread_active=True
                    loader_completed=False
                    safe=False
                    raise RuntimeError('Remote loader diagnostic resources must remain allocated')
        else:
            report['image_route']='target_loadlibrary'
        # module_base caches the initial module list while resolving the API
        # addresses above; force a fresh snapshot after LoadLibraryW.
        if not manual_mapped:
            image_base=h['module_base'](memory,image.name,refresh=True) or 0
            if not image_base:
                safe=False
                raise RuntimeError('Target loader returned but bridge module is absent from the target module list')
            remote_module=image_base
        report['image_base']=hex(image_base)
        if not manual_mapped:
            loaded_path=remote_module_path(handle,image_base)
            report['loaded_image_path']=loaded_path
            if normalized_path(loaded_path)!=normalized_path(image):
                raise RuntimeError('Loaded bridge path differs from the requested image')
        if not p['free'](handle,load_path,0,0x8000):
            report['image_path_freed']=False
            raise c.WinError(c.get_last_error())
        else:
            report['image_path_freed']=True
            load_path=None
        report['loaded_exports' if not manual_mapped else 'mapped_exports']={
            'BridgeInstall':p['bytes_at'](handle,image_base+install_rva,16).hex(),
            'BridgeUninstall':p['bytes_at'](handle,image_base+uninstall_rva,16).hex(),
        }
        block=p['alloc'](handle,None,216,0x3000,4)
        if not block:raise c.WinError(c.get_last_error())
        report['command_address']=hex(block)
        message=register_message('Codex.War3.DispatchProbe.'+str(uuid.uuid4()))
        if not message:raise c.WinError(c.get_last_error())
        nonce=int.from_bytes(os.urandom(8),'little') & 0x7fffffffffffffff
        payload=struct.pack('<7QIIQ6IQII', hwnd, *addresses, 0, tid, message, nonce,
            0, 0, 0, 0, 0, 0, sleep_address, 0, hook_kind)
        query=image_base+exports[query_name]
        # The normal loader has already registered the image's .pdata. Keep
        # the old fields in the wire ABI, but set unwind_count to zero so the
        # bridge does not register/delete the same table a second time.
        if manual_mapped:
            directory=pe.OPTIONAL_HEADER.DATA_DIRECTORY[3]
            if not directory.Size or directory.Size % 12:
                raise RuntimeError('Unwind table missing')
            payload+=struct.pack('<9Q6I',resolve(memory,'kernel32','TlsGetValue'),
                resolve(memory,'ntdll','RtlAddFunctionTable'),
                resolve(memory,'ntdll','RtlDeleteFunctionTable'),
                image_base+directory.VirtualAddress,image_base,query,0,0,
                resolve(memory,'ntdll','__C_specific_handler'),directory.Size//12,
                tls_index,0,0,0,0)
            report['image_unwind']={'method':'RtlAddFunctionTable',
                                    'count':directory.Size//12,
                                    'registered_by_loader':False}
        else:
            payload+=struct.pack('<9Q6I',resolve(memory,'kernel32','TlsGetValue'),
                0,0,0,image_base,query,0,0,
                resolve(memory,'ntdll','__C_specific_handler'),0,tls_index,0,0,0,0)
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
        remote_thread_active=True
        worker_tid=U()
        thread=p['create_thread'](handle,None,0,image_base+install_rva,block,0,c.byref(worker_tid))
        if not thread:
            remote_thread_active=False
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
        remote_thread_active=not completed
        report['install_thread']['completed']=completed
        state=fields(handle,block);report['after_cleanup']=state
        safe=can_release(completed, delivered, state) and not remote_thread_active
        report['callback_verified']=bool(safe and state['callback_tid']==tid and state['callback_count']==1)
        report['query_completed']=query_completed(state)
        if b'bridge_fault' in exports:
            report['fault']=decode_fault(bytes_at(handle,image_base+exports[b'bridge_fault'],96))
            if report['fault']:
                report['fault']['instruction_mapping']=describe_fault_instruction(handle,report['fault'])
        if b'bridge_recovered_faults' in exports:
            report['recovered_tail_faults']=struct.unpack('<I',bytes_at(handle,image_base+exports[b'bridge_recovered_faults'],4))[0]
        if work:report['work_result_hex']=p['bytes_at'](handle,work,len(work_payload)).hex()
    except Exception as exc:
        report['error']=repr(exc)
        report['traceback']=traceback.format_exc()
    finally:
        module_unloaded=not remote_module
        if manual_mapped:
            if safe and handle and not remote_thread_active:
                try:
                    status=int(x['unmap_section'](handle,view)) & 0xffffffff
                    report['image_unmap_status']=hex(status)
                    image_unmapped=(status == 0)
                    module_unloaded=image_unmapped
                    if not image_unmapped:
                        report['image_mapping_retained']=True
                        report['allocations_retained']=True
                        safe=False
                except Exception as exc:
                    report['image_unmap_error']=repr(exc)
                    report['image_mapping_retained']=True
                    report['allocations_retained']=True
                    module_unloaded=False
                    safe=False
            else:
                report['image_mapping_retained']=True
                report['allocations_retained']=True
                module_unloaded=False
        if loader_succeeded and not remote_module:
            # LoadLibraryW succeeded but the module could not be identified;
            # do not claim that the target image was released.
            module_unloaded=False
            report['image_module_unknown']=True
            report['allocations_retained']=True
            safe=False
        if remote_thread_active:
            # A timed-out remote thread may still be executing after its
            # handle is closed. Keep all target allocations quarantined.
            report['remote_thread_retained']=True
            report['allocations_retained']=True
            safe=False
        if handle and memory is not None and remote_module and safe:
            try:
                module_report=remote_free_library(memory,remote_module,free_library_address)
                report['image_unload']=module_report
                module_unloaded=bool(module_report['unloaded'])
                if module_unloaded:
                    try:
                        remaining=h['module_base'](memory,image.name,refresh=True) or 0
                    except Exception as exc:
                        report['image_unload_verify_error']=repr(exc)
                        remaining=1
                    report['image_unload']['remaining_base']=hex(remaining)
                    module_unloaded=not remaining
            except Exception as exc:
                report['image_unload_error']=repr(exc)
                module_unloaded=False
        if load_path and loader_completed and handle:
            try:
                path_freed=bool(p['free'](handle,load_path,0,0x8000))
            except Exception as exc:
                report['image_path_free_error']=repr(exc)
                path_freed=False
            report['image_path_freed_on_cleanup']=path_freed
            if path_freed:
                load_path=None
        if load_path:
            report['image_path_retained']=True
            report['allocations_retained']=True
            safe=False
        if remote_module and not module_unloaded:
            report['image_module_retained']=True
            report['allocations_retained']=True
        if file:
            p['close'](file)
        if section:
            p['close'](section)
        if thread:p['close'](thread)
        if handle:
            if safe and not remote_thread_active and module_unloaded:
                for label,address in (('work_freed',work),('block_freed',block)):
                    if address:
                        try:
                            released=bool(p['free'](handle,address,0,0x8000))
                        except Exception as exc:
                            report[label+'_error']=repr(exc)
                            released=False
                        report[label]=released
                        if not released:
                            safe=False
                            report['allocations_retained']=True
                if safe:
                    report['image_unmap_status']='0x0'
            elif work or block:
                report['allocations_retained']=True
            p['close'](handle)
        report['safe_to_release']=bool(
            safe and not remote_thread_active and module_unloaded and
            not load_path and not report.get('allocations_retained'))
    return report
def _retryable_hook_install_failure(report):
    state=report.get('after_cleanup') or report.get('after_send') or {}
    trace=state.get('bridge_install_trace','')
    return bool(
        report.get('safe_to_release') and not report.get('allocations_retained')
        and state.get('stage') == 2 and not state.get('hook')
        and state.get('callback_count') == 0 and state.get('callback_tid') == 0
        and state.get('query_stage') == 0
        and (trace in ('0x105','0x106') or state.get('last_error') in (126,))
    )


def _retry_summary(report):
    state=report.get('after_cleanup') or report.get('after_send') or {}
    return dict(
        route_attempt=report.get('route_attempt'),
        image_loader=report.get('image_loader'),
        bridge_install_trace=state.get('bridge_install_trace'),
        last_error=state.get('last_error'),
        exception_code=state.get('exception_code'),
        fault=report.get('fault'),
        safe_to_release=report.get('safe_to_release'),
    )


def dispatch(pid,hwnd,tid,image,tls_index,work_payload,kind="hero"):
    first=_dispatch_once(
        pid,hwnd,tid,image,tls_index,work_payload,kind=kind,attempt=1,
        delivery_mode='send',
    )
    if not _retryable_hook_install_failure(first):
        first['same_route_retry']={'attempted':False}
        return first
    # Reinitialize only after the first route proved that no callback ran and
    # every resource was released. The compatibility route changes both the
    # hook delivery mechanism and message delivery; normal calls stay on the
    # synchronous route and pay no fallback cost.
    time.sleep(0.02)
    second=_dispatch_once(
        pid,hwnd,tid,image,tls_index,work_payload,kind=kind,attempt=2,
        delivery_mode='posted',
    )
    second['same_route_retry']={
        'attempted':True,
        'reason':'clean_getmessage_compatibility_fallback',
        'fallback_route':second.get('route_policy'),
        'first_attempt':_retry_summary(first),
    }
    return second
