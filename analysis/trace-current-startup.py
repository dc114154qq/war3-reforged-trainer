"""Current startup-hook emulation; synthetic startup inputs, no API results invented."""
import argparse
from collections import deque
import ctypes as c
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'analysis/offline-runtime')]
from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_64, UC_HOOK_CODE, UC_HOOK_MEM_UNMAPPED
from unicorn.x86_const import *
import capstone
from war3_reforged_trainer import ProcessMemory


def run(pid, root_file, symbol, output, procedure_va=None, query_current=False):
    roots = json.loads(root_file.read_text(encoding='utf-8'))
    if roots['pid'] != pid:
        raise ValueError('Capture PID does not match')
    row = roots['roots'][symbol]
    entry = int(row['address'], 16)
    uc = Uc(UC_ARCH_X86, UC_MODE_64)
    stack, context, procedure, parameter, teb, sentinel = (0x700000000 + n * 0x100000 for n in range(6))
    for address in (stack, context, procedure, parameter, teb, sentinel):
        uc.mem_map(address, 0x20000)
    rsp = stack + 0x18000 - 8
    uc.mem_write(rsp, struct.pack('<Q', sentinel))
    uc.mem_write(procedure, bytes.fromhex('31c0c3'))
    if procedure_va is not None:
        procedure = procedure_va
    uc.reg_write(UC_X86_REG_RSP, rsp)
    uc.reg_write(UC_X86_REG_GS_BASE, teb)
    uc.mem_write(teb + 0x30, struct.pack('<Q', teb))
    uc.mem_write(teb + 0x40, struct.pack('<QQ', pid, 0xeeee))
    if symbol == 'BaseThreadInitThunk':
        uc.reg_write(UC_X86_REG_RCX, 0)
        uc.reg_write(UC_X86_REG_RDX, procedure)
        uc.reg_write(UC_X86_REG_R8, parameter)
    else:
        ctx = bytearray(0x4d0)
        struct.pack_into('<I', ctx, 0x30, 0x10000b)
        struct.pack_into('<I', ctx, 0x44, 0x202)
        struct.pack_into('<Q', ctx, 0x80, procedure)
        struct.pack_into('<Q', ctx, 0x88, parameter)
        struct.pack_into('<Q', ctx, 0x98, rsp)
        struct.pack_into('<Q', ctx, 0xf8, int(roots['roots']['BaseThreadInitThunk']['address'], 16))
        uc.mem_write(context, bytes(ctx))
        uc.reg_write(UC_X86_REG_RCX, context)
    report = {'pid': pid, 'symbol': symbol, 'entry': hex(entry),
              'scope': 'Copied current pages; synthetic TEB, stack, context and thread procedure. No live return inference.',
              'stop': 'budget_or_timeout', 'instructions': 0, 'calls_executed_in_target': 0,
              'procedure': hex(procedure), 'synthetic_teb': hex(teb)}
    recent, calls, pages = deque(maxlen=24), deque(maxlen=24), {}
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    with ProcessMemory(pid) as memory:
        # Recheck every previously observed hook-prefix byte before using saved addresses.
        for item in row['chain']:
            expected = bytes.fromhex(item['bytes'])
            if memory.read(int(item['address'], 16), len(expected)) != expected:
                raise ValueError('Startup entry changed; recapture roots')
        query = c.WinDLL('ntdll').NtQueryInformationProcess
        query.argtypes = [c.c_void_p, c.c_ulong, c.c_void_p, c.c_ulong, c.c_void_p]
        query.restype = c.c_long
        info = (c.c_ulonglong * 6)()
        status = query(memory.handle, 0, c.byref(info), c.sizeof(info), None)
        if status < 0:
            raise RuntimeError('PEB query failed ' + hex(status & 0xffffffff))
        uc.mem_write(teb + 0x60, struct.pack('<Q', info[1]))
        query_vm = c.WinDLL('ntdll').NtQueryVirtualMemory
        query_vm.argtypes = [c.c_void_p, c.c_void_p, c.c_int, c.c_void_p, c.c_size_t, c.POINTER(c.c_size_t)]
        query_vm.restype = c.c_long
        local_ldr = c.cast(c.WinDLL('ntdll').LdrInitializeThunk, c.c_void_p).value
        remote_query = int(roots['roots']['LdrInitializeThunk']['address'], 16) + c.cast(query_vm, c.c_void_p).value - local_ldr
        if query_current and (procedure_va is None or memory.read(remote_query, 24) != c.string_at(query_vm, 24)):
            raise ValueError('Explicit current procedure and matching query function required')
        report['observed_query_substitutions'] = []


        def unmapped(vm, access, address, size, value, user):
            page = address & ~4095
            if not 0x10000 <= page < 0x800000000000 or len(pages) >= 256:
                report.update(stop='invalid_address_or_page_limit', fault_address=hex(address))
                return False
            try:
                blob = memory.read(page, 4096)
                if len(blob) != 4096:
                    raise ValueError('Short page read')
                vm.mem_map(page, 4096)
                vm.mem_write(page, blob)
                pages[page] = blob
                return True
            except (OSError, ValueError, UcError) as exc:
                report.update(stop='snapshot_read_failed', fault_address=hex(address), fault=str(exc))
                return False

        def instruction(vm, address, size, user):
            report['instructions'] += 1
            if query_current and address == remote_query:
                process, target, kind, destination = (vm.reg_read(r) for r in
                    (UC_X86_REG_RCX, UC_X86_REG_RDX, UC_X86_REG_R8, UC_X86_REG_R9))
                current_rsp = vm.reg_read(UC_X86_REG_RSP)
                out_size, returned_pointer = struct.unpack('<QQ', vm.mem_read(current_rsp + 0x28, 16))
                if (process != 0xffffffffffffffff or target != procedure or kind != 0 or
                    not 48 <= out_size <= 64 or not stack <= destination < stack + 0x20000 - 64 or
                    returned_pointer and not stack <= returned_pointer < stack + 0x20000 - 8):
                    report['stop'] = 'unmodeled_memory_query'
                    vm.emu_stop()
                    return
                buffer, returned = c.create_string_buffer(out_size), c.c_size_t()
                status = query_vm(memory.handle, target, 0, buffer, out_size, c.byref(returned))
                report['observed_query_substitutions'].append({'target': hex(target),
                    'status': hex(status & 0xffffffff), 'bytes_returned': returned.value,
                    'data': buffer.raw.hex(), 'source': 'Read-only NtQueryVirtualMemory on current target, not invented'})
                if status < 0:
                    report['stop'] = 'current_memory_query_failed'
                    vm.emu_stop()
                    return
                vm.mem_write(destination, buffer.raw)
                if returned_pointer:
                    vm.mem_write(returned_pointer, struct.pack('<Q', returned.value))
                return_address = struct.unpack('<Q', vm.mem_read(current_rsp, 8))[0]
                vm.reg_write(UC_X86_REG_RAX, status & 0xffffffff)
                vm.reg_write(UC_X86_REG_RSP, current_rsp + 8)
                vm.reg_write(UC_X86_REG_RIP, return_address)
                return
            # Unicorn may pass an oversized sentinel for an unsupported opcode.
            raw = bytes(vm.mem_read(address, min(size, 15)))
            ins = next(md.disasm(raw, address), None)
            if ins is None:
                report['stop'] = 'decode_failed'
                vm.emu_stop()
                return
            if ins.mnemonic == 'rdpid':
                report.update(stop='unmodeled_cpu_environment_instruction', unsupported_instruction='rdpid',
                              fault_address=hex(address))
                vm.emu_stop()
                return
            line = {'address': hex(address), 'instruction': ins.mnemonic + ' ' + ins.op_str}
            recent.append(line)
            if ins.group(capstone.CS_GRP_CALL):
                calls.append(line | {'arguments': [hex(vm.reg_read(reg)) for reg in
                    (UC_X86_REG_RCX, UC_X86_REG_RDX, UC_X86_REG_R8, UC_X86_REG_R9)]})
            if ins.mnemonic in ('syscall', 'sysenter', 'int', 'int3', 'iretq'):
                report['stop'] = 'before_syscall_or_interrupt'
                vm.emu_stop()
            elif address == procedure:
                report['stop'] = 'before_synthetic_procedure'
                vm.emu_stop()

        uc.hook_add(UC_HOOK_MEM_UNMAPPED, unmapped)
        uc.hook_add(UC_HOOK_CODE, instruction)
        try:
            uc.emu_start(entry, sentinel, timeout=3000000, count=100000)
        except (UcError, capstone.CsError) as exc:
            report['emulator_error'] = str(exc)
            if report['stop'] == 'budget_or_timeout':
                report['stop'] = 'emulator_error'
        if uc.reg_read(UC_X86_REG_RIP) == sentinel:
            report['stop'] = 'returned_to_synthetic_caller'
    report['registers'] = {name: hex(uc.reg_read(reg)) for name, reg in (
        ('rip', UC_X86_REG_RIP), ('rax', UC_X86_REG_RAX), ('rcx', UC_X86_REG_RCX),
        ('rdx', UC_X86_REG_RDX), ('r8', UC_X86_REG_R8), ('r9', UC_X86_REG_R9),
        ('r10', UC_X86_REG_R10), ('rsp', UC_X86_REG_RSP))}
    report['stack_at_stop'] = bytes(uc.mem_read(uc.reg_read(UC_X86_REG_RSP), 0x40)).hex()
    report.update(recent=list(recent), calls=list(calls), captured_utc=datetime.now(timezone.utc).isoformat())
    archive = output.with_suffix('.pages.zip')
    temporary = archive.with_suffix('.tmp')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as z:
        for page, blob in pages.items():
            z.writestr(f'{page:x}.bin', blob)
    os.replace(temporary, archive)
    report['page_archive'] = str(archive)
    report['pages'] = [{'address': hex(p), 'sha256': hashlib.sha256(b).hexdigest()} for p, b in pages.items()]
    temporary = output.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, indent=2), encoding='utf-8')
    os.replace(temporary, output)
    print(json.dumps({k: v for k, v in report.items() if k not in ('recent', 'pages', 'calls')}))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pid', type=int, required=True)
    ap.add_argument('--roots', type=Path, required=True)
    ap.add_argument('--symbol', choices=['BaseThreadInitThunk', 'LdrInitializeThunk'], required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--procedure-va', type=lambda x: int(x, 0))
    ap.add_argument('--query-current', action='store_true')
    a = ap.parse_args()
    run(a.pid, a.roots, a.symbol, a.output, a.procedure_va, a.query_current)
