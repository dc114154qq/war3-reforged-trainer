import struct
import sys
import pefile

image=pefile.PE(sys.argv[1])
exports={entry.name:entry.address for entry in image.DIRECTORY_ENTRY_EXPORT.symbols}
assert image.FILE_HEADER.Machine==0x8664
assert image.get_data(exports[b'speed_clock_abi'],16)==struct.pack('<4I',0x57435331,1,88,1000)
assert b'SpeedControl' in exports
assert not getattr(image,'DIRECTORY_ENTRY_DELAY_IMPORT',())
assert all(entry.dll.lower()==b'kernel32.dll' for entry in image.DIRECTORY_ENTRY_IMPORT)
assert image.OPTIONAL_HEADER.DATA_DIRECTORY[3].Size>0
print('Speed clock x64 ABI and dependencies verified')
