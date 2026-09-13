"""Compare a few OS entrypoints and query instrumentation, without executing game code."""
import ctypes
import json
from pathlib import Path
import sys
import struct
import capstone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from war3_reforged_trainer import ProcessMemory,kernel32

pid=int(sys.argv[1])
nt=ctypes.WinDLL('ntdll',use_last_error=True)
nt.NtQueryInformationProcess.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_void_p,ctypes.c_ulong,ctypes.c_void_p]
nt.NtQueryInformationProcess.restype=ctypes.c_long
kernel32.GetModuleHandleW.argtypes=[ctypes.c_wchar_p]
kernel32.GetModuleHandleW.restype=ctypes.c_void_p
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64)
md.detail=True
report={'pid':pid,'read_only':True,'entries':[]}
with ProcessMemory(pid) as memory:
    instrument=ctypes.create_string_buffer(32)
    returned=ctypes.c_ulong()
    status=nt.NtQueryInformationProcess(memory.handle,40,instrument,32,ctypes.byref(returned))
    report['instrumentation_query']={'status':hex(status&0xffffffff),'bytes':returned.value,
                                     'data':instrument.raw.hex() if status>=0 else None}
    for library,name in [('ntdll.dll','RtlUserThreadStart'),('ntdll.dll','LdrInitializeThunk'),
                         ('kernel32.dll','BaseThreadInitThunk'),('kernel32.dll','LoadLibraryW'),
                         ('ntdll.dll','KiUserExceptionDispatcher')]:
        module=kernel32.GetModuleHandleW(library)
        address=kernel32.GetProcAddress(module,name.encode())
        if not address: continue
        own=ctypes.string_at(address,32)
        row={'module':library,'function':name,'address':hex(address),'local':own.hex()}
        try:
            remote=memory.read(address,32)
            row.update(remote=remote.hex(),matches_local=remote==own,
                       disassembly=[f'{i.address:x}: {i.mnemonic} {i.op_str}' for i in md.disasm(remote,address)])
        except OSError as exc: row['read_error']=exc.winerror
        report['entries'].append(row)
    # Follow only direct/indirect unconditional entry jumps, bounded to four hops.
    report['entry_jumps']=[]
    for row in report['entries']:
        address=int(row['address'],16)
        visited=set()
        for depth in range(4):
            if address in visited: break
            visited.add(address)
            try:
                data=memory.read(address,64)
                ins=list(md.disasm(data,address))
                report['entry_jumps'].append(dict(function=row['function'],address=hex(address),
                    bytes=data.hex(),instructions=[f'{i.address:x}: {i.mnemonic} {i.op_str}' for i in ins]))
                first=ins[0]
                if first.mnemonic!='jmp': break
                operand=first.operands[0]
                if operand.type==capstone.x86.X86_OP_IMM: address=operand.imm
                elif operand.type==capstone.x86.X86_OP_MEM and operand.mem.base==capstone.x86.X86_REG_RIP:
                    address=struct.unpack('<Q',memory.read(first.address+first.size+operand.mem.disp,8))[0]
                else: break
            except OSError: break
(ROOT/'analysis/native-bootstrap-24268/execution-entry.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report,indent=2))
