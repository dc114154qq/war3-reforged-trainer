"""Emulate the loader's thread gate in synthetic memory; never execute its calls in game."""
import collections
import ctypes
import hashlib
import json
from pathlib import Path
import struct
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'analysis/native-bootstrap-20260907/_deps')]
import capstone
from unicorn import Uc,UcError,UC_ARCH_X86,UC_MODE_64,UC_HOOK_MEM_UNMAPPED,UC_HOOK_CODE
from unicorn.x86_const import *
from war3_reforged_trainer import ProcessMemory,kernel32,user32,find_war3

pid=int(sys.argv[1]); base=int(sys.argv[2],0); entry=int(sys.argv[3],0)
mode=sys.argv[4] if len(sys.argv)>4 else 'stop'
assert mode in ('stop','private','image','query-failure','exception')
directory=ROOT/'analysis/native-bootstrap-24268/_pages'
directory.mkdir(exist_ok=True)
uc=Uc(UC_ARCH_X86,UC_MODE_64)
stack=0x700000000; stop=0x710000000; procedure=0x720000000; parameter=0x730000000; teb=0x740000000
for address,size in ((stack,0x20000),(stop,4096),(procedure,4096),(parameter,4096),(teb,4096)):
    uc.mem_map(address,size)
uc.mem_write(procedure,b'\xc3')
rsp=stack+0x18000-8
uc.mem_write(rsp,struct.pack('<Q',stop))
for reg,value in ((UC_X86_REG_RSP,rsp),(UC_X86_REG_RCX,0),(UC_X86_REG_RDX,procedure),
                  (UC_X86_REG_R8,parameter)):
    uc.reg_write(reg,value)
if mode=='exception':
    fault=0x7ff6b8833000
    exception=bytearray(152);struct.pack_into('<I',exception,0,0xc0000005)
    struct.pack_into('<Q',exception,16,fault);struct.pack_into('<I',exception,24,2)
    struct.pack_into('<QQ',exception,32,8,fault)
    uc.mem_write(procedure,bytes(exception))
    context=bytearray(1232);struct.pack_into('<I',context,48,0x10000b)
    struct.pack_into('<I',context,68,0x202);struct.pack_into('<Q',context,248,fault)
    struct.pack_into('<Q',context,152,stack+0x8000)
    uc.mem_write(parameter,bytes(context))
    uc.reg_write(UC_X86_REG_RCX,procedure);uc.reg_write(UC_X86_REG_RDX,parameter)
mapped=set(); rows=[]; calls=[]; last=collections.deque(maxlen=12); halt=[]; synthetic=[]
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64)
with ProcessMemory(pid) as memory:
    nt=ctypes.WinDLL('ntdll')
    nt.NtQueryInformationProcess.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_void_p,ctypes.c_ulong,ctypes.c_void_p]
    info=ctypes.create_string_buffer(48)
    assert nt.NtQueryInformationProcess(memory.handle,0,info,48,None)>=0
    peb=struct.unpack_from('<Q',info.raw,8)[0]
    uc.reg_write(UC_X86_REG_GS_BASE,teb)
    uc.mem_write(teb+0x30,struct.pack('<Q',teb))
    uc.mem_write(teb+0x40,struct.pack('<QQ',pid,0xeeee))
    uc.mem_write(teb+0x60,struct.pack('<Q',peb))
    # One observed PEB-masked import trampoline, discovered by the previous trace.
    # Exception scenario's thunk allocation was bounded by VirtualQueryEx.
    allowed_thunk=0x2df52571000 if mode=='exception' else 0x29237eb0000
    allowed_thunk_size=0xff000 if mode=='exception' else 4096
    last_error_fn=kernel32.GetProcAddress(kernel32._handle,b'GetLastError')
    fiber_fn=kernel32.GetProcAddress(kernel32._handle,b'IsThreadAFiber')
    convert_fiber_fn=kernel32.GetProcAddress(kernel32._handle,b'ConvertThreadToFiber')
    tls_get_fn=kernel32.GetProcAddress(kernel32._handle,b'TlsGetValue')
    real_teb=0
    if mode=='exception':
        hwnd,_=find_war3(pid);thread_id=user32.GetWindowThreadProcessId(hwnd,None)
        kernel32.OpenThread.argtypes=[ctypes.c_ulong,ctypes.c_bool,ctypes.c_ulong]
        kernel32.OpenThread.restype=ctypes.c_void_p
        nt.NtQueryInformationThread.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_void_p,ctypes.c_ulong,ctypes.c_void_p]
        handle=kernel32.OpenThread(0x40,False,thread_id)
        if not handle: raise ctypes.WinError(ctypes.get_last_error())
        try:
            thread_info=ctypes.create_string_buffer(48)
            assert nt.NtQueryInformationThread(handle,0,thread_info,48,None)>=0
            real_teb=struct.unpack_from('<Q',thread_info.raw,8)[0]
        finally: kernel32.CloseHandle(handle)
    query_virtual=kernel32.GetProcAddress(nt._handle,b'NtQueryVirtualMemory')
    def unmapped(uc,access,address,size,value,user):
        page=address&~4095
        if page<0x10000 or page>=0x800000000000:
            halt.append(f'Invalid synthetic memory access {address:#x}');return False
        try:
            data=memory.read(page,4096)
            uc.mem_map(page,4096);uc.mem_write(page,data);mapped.add(page)
            (directory/f'{page:x}.bin').write_bytes(data)
            rows.append({'address':hex(page),'sha256':hashlib.sha256(data).hexdigest()})
            return True
        except OSError as exc:
            halt.append(f'Cannot capture requested page {page:#x}: {exc.winerror}');return False
    def instruction(uc,address,size,user):
        last.append(address)
        if mode=='exception' and address==tls_get_fn:
            index=uc.reg_read(UC_X86_REG_RCX)
            if index>=64: halt.append('Unmodeled expanded TLS index');uc.emu_stop();return
            result=struct.unpack('<Q',memory.read(real_teb+0x1480+index*8,8))[0]
            call_stack=uc.reg_read(UC_X86_REG_RSP);return_address=struct.unpack('<Q',uc.mem_read(call_stack,8))[0]
            uc.reg_write(UC_X86_REG_RAX,result);uc.reg_write(UC_X86_REG_RSP,call_stack+8);uc.reg_write(UC_X86_REG_RIP,return_address)
            synthetic.append({'api':'TlsGetValue','index':index,'source':'Read-only main-thread TLS snapshot','value':hex(result)});return
        if mode=='exception' and address in (last_error_fn,fiber_fn,convert_fiber_fn):
            call_stack=uc.reg_read(UC_X86_REG_RSP)
            return_address=struct.unpack('<Q',uc.mem_read(call_stack,8))[0]
            result=0x750000000 if address==convert_fiber_fn else 0
            if address==convert_fiber_fn:
                uc.mem_map(result,4096)
                uc.mem_write(result,struct.pack('<Q',uc.reg_read(UC_X86_REG_RCX)))
                uc.mem_write(teb+0x20,struct.pack('<Q',result))
            uc.reg_write(UC_X86_REG_RAX,result);uc.reg_write(UC_X86_REG_RSP,call_stack+8)
            uc.reg_write(UC_X86_REG_RIP,return_address)
            synthetic.append({'api':{last_error_fn:'GetLastError',fiber_fn:'IsThreadAFiber',convert_fiber_fn:'ConvertThreadToFiber'}[address],
                              'value':hex(result)});return
        if address==query_virtual and mode in ('private','image','query-failure'):
            process=uc.reg_read(UC_X86_REG_RCX); target=uc.reg_read(UC_X86_REG_RDX)
            info_class=uc.reg_read(UC_X86_REG_R8); out=uc.reg_read(UC_X86_REG_R9)
            call_stack=uc.reg_read(UC_X86_REG_RSP)
            out_size,returned_ptr=struct.unpack('<QQ',uc.mem_read(call_stack+0x28,16))
            if process!=0xffffffffffffffff or target!=procedure or info_class!=0 or out_size<48 or not stack<=out<stack+0x20000-48:
                halt.append('Unmodeled virtual-memory query');uc.emu_stop();return
            result=0xc0000001 if mode=='query-failure' else 0
            if result==0:
                record=struct.pack('<QQIIQIIII',procedure,procedure,0x20,0,4096,0x1000,0x20,
                                   0x20000 if mode=='private' else 0x1000000,0)
                uc.mem_write(out,record)
                if returned_ptr:
                    if not stack<=returned_ptr<stack+0x20000-8:
                        halt.append('Unexpected returned-length pointer');uc.emu_stop();return
                    uc.mem_write(returned_ptr,struct.pack('<Q',48))
            synthetic.append({'api':'NtQueryVirtualMemory','scenario':mode,'address':hex(target),'status':hex(result)})
            return_address=struct.unpack('<Q',uc.mem_read(call_stack,8))[0]
            uc.reg_write(UC_X86_REG_RAX,result);uc.reg_write(UC_X86_REG_RSP,call_stack+8)
            uc.reg_write(UC_X86_REG_RIP,return_address);return
        if not (base<=address<base+0x2660000 or allowed_thunk<=address<allowed_thunk+allowed_thunk_size):
            halt.append(f'External call reached {address:#x}; stopped before execution')
            uc.emu_stop();return
        opcode=bytes(uc.mem_read(address,size))
        if opcode[0] in (0xe8,0xff) or opcode[:2]==b'\x0f\x05':
            ins=next(md.disasm(opcode,address),None)
            if ins and ins.mnemonic in ('call','syscall'):
                calls.append(f'{address:#x}: {ins.mnemonic} {ins.op_str}')
                if ins.mnemonic=='syscall': halt.append('Syscall refused');uc.emu_stop()
    uc.hook_add(UC_HOOK_MEM_UNMAPPED,unmapped)
    uc.hook_add(UC_HOOK_CODE,instruction)
    try: uc.emu_start(entry,stop,timeout=20000000,count=250000)
    except UcError as exc: halt.append(str(exc))
registers={name:hex(uc.reg_read(reg)) for name,reg in [('rip',UC_X86_REG_RIP),('rax',UC_X86_REG_RAX),
    ('rcx',UC_X86_REG_RCX),('rdx',UC_X86_REG_RDX),('r8',UC_X86_REG_R8),('r9',UC_X86_REG_R9)]}
report={'pid':pid,'loader_base':hex(base),'entry':hex(entry),'scenario':mode,'synthetic_api_results':synthetic,
        'scope':'Emulation only; OS calls not executed; synthetic scenarios are not live compatibility validation',
        'halt':halt,'registers':registers,'pages':rows,'calls':calls[-30:],'last_addresses':[hex(a) for a in last]}
(ROOT/'analysis/native-bootstrap-24268'/f'thread-gate-trace-{mode}.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in report.items() if k!='pages'},indent=2));print('captured_pages',len(rows))
