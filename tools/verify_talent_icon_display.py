"""Validate the dedicated UI module without loading it into a game."""
import struct
import sys
import pefile

pe=pefile.PE(sys.argv[1])
assert pe.FILE_HEADER.Machine==0x8664
assert not getattr(pe,'DIRECTORY_ENTRY_IMPORT',()),'UI module must not need unmapped imports'
exports={s.name:s.address for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name}
for name in (b'icon_config',b'icon_resume',b'IconInstall',b'IconRemove',b'icon_display_abi'):
    assert name in exports,name
assert struct.unpack('<4I',pe.get_data(exports[b'icon_display_abi'],16))==(0x24268045,1,120,36)
assert pe.OPTIONAL_HEADER.DATA_DIRECTORY[3].Size>0,'SEH unwind table required'
assert any(e.type==10 for b in pe.DIRECTORY_ENTRY_BASERELOC for e in b.entries)
print('x64 talent icon module ABI, unwind, relocation and import checks passed')
