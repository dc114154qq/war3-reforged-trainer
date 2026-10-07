"""Read executable version resources for automatic adapter selection."""
from __future__ import annotations
import ctypes
from functools import lru_cache
from pathlib import Path
import struct


def file_fingerprint(path):
    with Path(path).open("rb") as source:
        header = source.read(64)
        if len(header) != 64 or header[:2] != b"MZ":
            raise ValueError("Executable has no DOS header")
        offset = struct.unpack_from("<I", header, 0x3C)[0]
        if not 64 <= offset <= 0x100000:
            raise ValueError("Executable PE header offset is invalid")
        source.seek(offset)
        header = source.read(0x58)
        if len(header) != 0x58 or header[:4] != b"PE\0\0":
            raise ValueError("Executable has no PE header")
        return (struct.unpack_from("<H", header, 4)[0],
                struct.unpack_from("<I", header, 8)[0],
                struct.unpack_from("<I", header, 0x50)[0])


@lru_cache(maxsize=32)
def _version_resource(path, modified_ns, size):
    # Timestamp and size are cache keys; they are not substituted for PE identity.
    version = ctypes.WinDLL("version", use_last_error=True)
    get_size = version.GetFileVersionInfoSizeW
    get_size.argtypes = (ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_uint32))
    get_size.restype = ctypes.c_uint32
    get_info = version.GetFileVersionInfoW
    get_info.argtypes = (ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p)
    get_info.restype = ctypes.c_int
    query = version.VerQueryValueW
    query.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p),
                     ctypes.POINTER(ctypes.c_uint32))
    query.restype = ctypes.c_int
    unused = ctypes.c_uint32()
    length = get_size(path, ctypes.byref(unused))
    if not length:
        raise ctypes.WinError(ctypes.get_last_error())
    block = ctypes.create_string_buffer(length)
    if not get_info(path, 0, length, block):
        raise ctypes.WinError(ctypes.get_last_error())
    pointer, length = ctypes.c_void_p(), ctypes.c_uint32()
    if not query(block, "\\", ctypes.byref(pointer), ctypes.byref(length)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not pointer.value or length.value < 52:
        raise ValueError("Executable fixed version resource is incomplete")
    words = ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32 * 13)).contents
    if words[0] != 0xFEEF04BD:
        raise ValueError("Executable fixed version resource signature differs")
    return ".".join(str(part) for part in (words[2] >> 16, words[2] & 0xFFFF,
                                         words[3] >> 16, words[3] & 0xFFFF))


def read_executable_version(path, expected_fingerprint):
    path = Path(path)
    stat = path.stat()
    if file_fingerprint(path) != tuple(expected_fingerprint):
        raise ValueError("Loaded game identity differs from executable version source")
    result = _version_resource(str(path), stat.st_mtime_ns, stat.st_size)
    after = path.stat()
    if (stat.st_mtime_ns, stat.st_size) != (after.st_mtime_ns, after.st_size):
        raise ValueError("Game executable changed while reading its version")
    return result
