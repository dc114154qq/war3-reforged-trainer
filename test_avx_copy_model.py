from pathlib import Path
import sys
import importlib.util
sys.path.insert(0,str(Path(__file__).parent/'analysis/offline-runtime'))
import capstone
from unicorn import Uc, UC_ARCH_X86, UC_MODE_64
from unicorn import x86_const as x
import pytest
spec=importlib.util.spec_from_file_location('avx_model',Path(__file__).parent/'analysis/avx_copy_model.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def machine():
 vm=Uc(UC_ARCH_X86,UC_MODE_64);vm.mem_map(0x100000,0x4000)
 vm.reg_write(x.UC_X86_REG_RDX,0x101003);vm.reg_write(x.UC_X86_REG_RCX,0x102007)
 vm.reg_write(x.UC_X86_REG_R8,58)
 vm.mem_write(0x101003,bytes(range(58)))
 return vm


def instruction(raw):
 md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64);md.detail=True
 return next(md.disasm(bytes.fromhex(raw),0x100000))


def test_exact_observed_58_byte_overlapping_edge_copy():
 vm=machine()
 for raw in ('c5fe6f02','c4a17e6f6c02e0','c5fe7f01','c4a17e7f6c01e0'):
  assert m.apply(vm,instruction(raw))
 assert bytes(vm.mem_read(0x102007,58))==bytes(range(58))


def test_vex128_clears_upper_half():
 vm=machine();vm.reg_write(x.UC_X86_REG_YMM0,(1<<256)-1)
 assert m.apply(vm,instruction('c5fa6f02'))
 assert vm.reg_read(x.UC_X86_REG_YMM0)==int.from_bytes(bytes(range(16)),'little')


def test_vzeroupper_preserves_all_low_halves():
 vm=machine()
 for n in range(16):vm.reg_write(getattr(x,'UC_X86_REG_YMM'+str(n)),(n+1)|((n+99)<<128))
 assert m.apply(vm,instruction('c5f877'))
 for n in range(16):assert vm.reg_read(getattr(x,'UC_X86_REG_YMM'+str(n)))==n+1


def test_unaligned_aligned_move_is_not_silently_accepted():
 vm=machine()
 with pytest.raises(ValueError,match='Unaligned'):m.apply(vm,instruction('c5fd6f02'))


def test_unrelated_instruction_not_changed():
 vm=machine();vm.reg_write(x.UC_X86_REG_RIP,0x100000)
 assert m.apply(vm,instruction('90')) is False
 assert vm.reg_read(x.UC_X86_REG_RIP)==0x100000
