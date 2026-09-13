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
from war3_reforged_trainer import ProcessMemory,kernel32

pid=int(sys.argv[1]); base=int(sys.argv[2],0); entry=int(sys.argv[3],0)
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
mapped=set(); rows=[]; calls=[]; last=collections.deque(maxlen=12); halt=[]
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
    allowed_thunk=0x29237eb0000
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
        if not (base<=address<base+0x2660000 or allowed_thunk<=address<allowed_thunk+4096):
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
report={'pid':pid,'loader_base':hex(base),'entry':hex(entry),'scope':'Emulation only; OS calls not executed',
        'halt':halt,'registers':registers,'pages':rows,'calls':calls[-30:],'last_addresses':[hex(a) for a in last]}
(ROOT/'analysis/native-bootstrap-24268/thread-gate-trace.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in report.items() if k!='pages'},indent=2));print('captured_pages',len(rows))
