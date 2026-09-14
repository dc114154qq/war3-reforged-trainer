"""Bounded native-entry mapping checks; protected-image calls are diagnostic opt-in."""
import ctypes as c
import pefile
from war3_object_registry import TIMESTAMP, IMAGE_SIZE

class Mapping(c.Structure):
    _fields_ = [('base', c.c_void_p), ('allocation', c.c_void_p),
                ('allocation_protect', c.c_ulong), ('partition', c.c_ushort),
                ('size', c.c_size_t), ('state', c.c_ulong),
                ('protect', c.c_ulong), ('type', c.c_ulong)]

def classify_entry(address, image_base, executable_ranges, region, allow_noaccess=False, span=16):
    if not 1<=span<=4096:raise ValueError("Invalid bounded native observation span")
    if not any(lo <= address and address + span <= hi for lo, hi in executable_ranges):
        raise ValueError('Native entry is outside declared executable image sections')
    if (region.allocation != image_base or region.state != 0x1000
            or region.type not in (0x40000, 0x1000000)
            or not region.base <= address < address + span <= region.base + region.size):
        raise ValueError('Native entry mapping does not belong to the verified game image')
    if region.protect in (0x20, 0x40, 0x80):
        return 'readable-executable'
    if allow_noaccess and region.protect == 1:
        return 'image-noaccess-diagnostic-only'
    raise ValueError('Native entry has no verified readable executable mapping')

def inspect_entries(memory, image_base, entries, allow_noaccess=False, span=16):
    # PE headers, not a process-wide region scan or an old handler-RVA list.
    header = memory.read(image_base, 4096)
    pe = pefile.PE(data=header, fast_load=True)
    if (pe.FILE_HEADER.Machine != 0x8664 or pe.FILE_HEADER.TimeDateStamp != TIMESTAMP
            or pe.OPTIONAL_HEADER.SizeOfImage != IMAGE_SIZE):
        raise ValueError('Native preflight image profile differs')
    ranges = [(image_base+s.VirtualAddress, image_base+s.VirtualAddress+s.Misc_VirtualSize)
              for s in pe.sections if s.Characteristics & 0x20000000
              and s.VirtualAddress+s.Misc_VirtualSize <= IMAGE_SIZE]
    query = c.WinDLL('kernel32', use_last_error=True).VirtualQueryEx
    query.argtypes = (c.c_void_p, c.c_void_p, c.POINTER(Mapping), c.c_size_t)
    query.restype = c.c_size_t
    result = {}
    for name, entry in entries.items():
        region = Mapping()
        if query(memory.handle, entry.handler, c.byref(region), c.sizeof(region)) != c.sizeof(region):
            raise c.WinError(c.get_last_error())
        kind = classify_entry(entry.handler, image_base, ranges, region, allow_noaccess, span)
        result[name] = dict(address=hex(entry.handler), kind=kind,
                            protection=hex(region.protect), allocation=hex(region.allocation),
                            code_hex=memory.read(entry.handler, span).hex()
                            if kind == 'readable-executable' else None)
    return result
