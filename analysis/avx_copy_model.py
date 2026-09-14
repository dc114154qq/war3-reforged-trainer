"""Narrow VEX move model for copied-memory emulation, not a game patch.

Semantics: Intel SDM Vol 2 VMOVDQU/VMOVDQA and VZEROUPPER.
https://cdrdv2-public.intel.com/843829/325383-sdm-vol-2abcd-dec-24.pdf
Unsupported forms fail closed. No CPU/environment state is fabricated here.
"""
from capstone.x86 import X86_OP_MEM, X86_OP_REG, X86_REG_RIP
from unicorn import x86_const as x


def apply(vm, ins, ensure_memory=lambda address, size: None):
    if ins.mnemonic not in ('vmovdqu', 'vmovdqa', 'vzeroupper'):
        return False
    if not ins.bytes or ins.bytes[0] not in (0xc4, 0xc5):
        raise ValueError('Only VEX encodings supported')
    if ins.mnemonic == 'vzeroupper':
        for n in range(16):
            reg = getattr(x, 'UC_X86_REG_YMM' + str(n))
            vm.reg_write(reg, vm.reg_read(reg) & ((1 << 128) - 1))
        vm.reg_write(x.UC_X86_REG_RIP, ins.address + ins.size)
        return True
    if len(ins.operands) != 2 or ins.operands[0].size not in (16, 32):
        raise ValueError('Unsupported vector move size')
    width = ins.operands[0].size
    if ins.operands[1].size != width:
        raise ValueError('Mismatched vector operands')

    def vector(op):
        name = ins.reg_name(op.reg)
        if name[:3] not in ('xmm', 'ymm') or not name[3:].isdigit() or int(name[3:]) >= 16:
            raise ValueError('Unsupported vector register')
        return getattr(x, 'UC_X86_REG_YMM' + name[3:])

    def address(op):
        m = op.mem
        if m.segment:
            raise ValueError('Segment addressing not modeled')
        def register(reg):
            if not reg:
                return 0
            if reg == X86_REG_RIP:
                return ins.address + ins.size
            return vm.reg_read(getattr(x, 'UC_X86_REG_' + ins.reg_name(reg).upper()))
        result = (register(m.base) + register(m.index) * m.scale + m.disp) & ((1 << 64) - 1)
        if ins.mnemonic == 'vmovdqa' and result % width:
            raise ValueError('Unaligned VMOVDQA operand')
        ensure_memory(result, width)
        return result

    dst, src = ins.operands
    if src.type == X86_OP_REG:
        data = (vm.reg_read(vector(src)) & ((1 << (width * 8)) - 1)).to_bytes(width, 'little')
    elif src.type == X86_OP_MEM:
        data = bytes(vm.mem_read(address(src), width))
    else:
        raise ValueError('Unsupported source')
    if dst.type == X86_OP_REG:
        # VEX.128 clears bits 255:128, unlike legacy SSE MOVDQU.
        vm.reg_write(vector(dst), int.from_bytes(data, 'little'))
    elif dst.type == X86_OP_MEM:
        vm.mem_write(address(dst), data)
    else:
        raise ValueError('Unsupported destination')
    vm.reg_write(x.UC_X86_REG_RIP, ins.address + ins.size)
    return True
