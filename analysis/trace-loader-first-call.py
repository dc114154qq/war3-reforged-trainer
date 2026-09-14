"""Execute only an isolated copy of a PE prefix; stop BEFORE every call.

Disk initial state is not the initialized process. No OS API or game code is
invoked in the host. Unmapped reads and budgets stop the trace, not fabricate data.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).parent / 'offline-runtime'))
from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_64, UC_HOOK_CODE, UC_HOOK_MEM_INVALID
from unicorn.x86_const import (UC_X86_REG_RAX, UC_X86_REG_RCX, UC_X86_REG_RDX,
                              UC_X86_REG_R8, UC_X86_REG_R9, UC_X86_REG_RSP,
                              UC_X86_REG_RIP)
import capstone
from capstone.x86 import X86_OP_IMM, X86_OP_REG, X86_OP_MEM, X86_REG_RIP
import pefile


def trace(image, base, rva, reason, limit=20000):
    uc = Uc(UC_ARCH_X86, UC_MODE_64)
    uc.mem_map(base, (len(image) + 4095) & ~4095)
    uc.mem_write(base, image)
    stack = 0x700000000000
    uc.mem_map(stack, 0x10000)
    rsp = stack + 0x8008
    uc.reg_write(UC_X86_REG_RSP, rsp)
    uc.mem_write(rsp, struct.pack('<Q', 0))
    uc.reg_write(UC_X86_REG_RCX, base)
    uc.reg_write(UC_X86_REG_RDX, reason)
    uc.reg_write(UC_X86_REG_R8, 0)
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    decoder.detail = True
    report = {'rva': hex(rva), 'reason_argument': reason, 'instruction_count': 0,
              'stop': 'budget_or_timeout', 'calls_executed': 0, 'recent_instructions': []}

    def instruction(vm, address, size, user):
        report['instruction_count'] += 1
        ins = next(decoder.disasm(bytes(vm.mem_read(address, size)), address, count=1), None)
        if ins is None:
            report['stop'] = 'decode_failed'
            vm.emu_stop()
            return
        report['recent_instructions'].append({'rva': hex(address - base),
                                               'instruction': ins.mnemonic + ' ' + ins.op_str})
        report['recent_instructions'] = report['recent_instructions'][-16:]
        if ins.group(capstone.CS_GRP_CALL):
            report['stop'] = 'before_call'
            operand = ins.operands[0]
            if operand.type == X86_OP_IMM:
                report['call_target_rva'] = hex(operand.imm - base)
            elif operand.type == X86_OP_MEM and operand.mem.base == X86_REG_RIP:
                slot = address + size + operand.mem.disp
                report['indirect_slot_rva'] = hex(slot - base)
                # Record the stored value only; it is not assumed resolved or executable.
                try:
                    report['indirect_slot_value'] = hex(struct.unpack('<Q', vm.mem_read(slot, 8))[0])
                except UcError:
                    report['indirect_slot_unreadable'] = True
            vm.emu_stop()
        elif ins.group(capstone.CS_GRP_RET):
            report['stop'] = 'before_return'
            vm.emu_stop()

    def invalid(vm, access, address, size, value, user):
        report.update(stop='unmapped_or_protected_memory', fault_address=hex(address),
                      fault_access=access, fault_size=size)
        return False

    uc.hook_add(UC_HOOK_CODE, instruction)
    uc.hook_add(UC_HOOK_MEM_INVALID, invalid)
    try:
        uc.emu_start(base + rva, 0, timeout=2000000, count=limit)
    except UcError as exc:
        report['emulator_error'] = str(exc)
        if report['stop'] == 'budget_or_timeout':
            report['stop'] = 'emulator_error'
    report['registers'] = {name: hex(uc.reg_read(reg)) for name, reg in (
        ('rax', UC_X86_REG_RAX), ('rcx', UC_X86_REG_RCX), ('rdx', UC_X86_REG_RDX),
        ('r8', UC_X86_REG_R8), ('r9', UC_X86_REG_R9), ('rip', UC_X86_REG_RIP))}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--rva', type=lambda s: int(s, 0), action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = args.image.read_bytes()
    pe = pefile.PE(data=data)
    # Include all virtual sections, but do not resolve imports or run TLS/entry code.
    image = pe.get_memory_mapped_image()
    image = image.ljust(pe.OPTIONAL_HEADER.SizeOfImage, b'\0')
    report = {'image': str(args.image.resolve()), 'sha256': hashlib.sha256(data).hexdigest(),
              'state': 'disk_initial_state_without_import_resolution',
              'runtime_proof': False, 'traces': [
                  trace(image, pe.OPTIONAL_HEADER.ImageBase, rva, reason)
                  for rva in args.rva for reason in (1, 2)]}
    temp = args.output.with_suffix('.tmp')
    temp.write_text(json.dumps(report, indent=2), encoding='utf-8')
    os.replace(temp, args.output)
    print(json.dumps([{k: v for k, v in row.items() if k != 'recent_instructions'}
                      for row in report['traces']]))


if __name__ == '__main__':
    main()
