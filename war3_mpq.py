"""Bounded local MPQ access through the bundled, hash-verified StormLib."""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import ctypes as c
import hashlib
import importlib.util
import sys
import threading

DLL_SHA256 = '6cd644f3c091c2fff6430cbf612dbbf6657d8508941fba2e925caadfa7a04da6'
STORAGE_FLAGS = 0x100 | 0x200 | 0x10000 | 0x20000 | 0x1000000 | 0x4000000
MAX_MEMBER = 512 * 1024 * 1024
LOCK = threading.RLock()
H, U, B = c.c_void_p, c.c_uint32, c.c_bool


class MpqError(ValueError):
    pass


class _Find(c.Structure):
    _fields_ = [('name', c.c_char * 260), ('plain', c.c_void_p),
                ('hash_index', U), ('block_index', U), ('size', U), ('flags', U),
                ('compressed_size', U), ('time_lo', U), ('time_hi', U), ('locale', U)]


@dataclass(frozen=True)
class Member:
    name: str
    size: int
    flags: int
    locale: int = 0
    block_index: int = 0


@lru_cache(1)
def library():
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    path = root / 'tools/war3_mpq.dll'
    if not path.is_file() and not getattr(sys, 'frozen', False):
        spec = importlib.util.find_spec('pympq')
        if spec is not None and spec.origin:
            path = Path(spec.origin).parent / 'StormLib.dll'
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != DLL_SHA256:
        raise MpqError('地图处理组件缺失或校验失败，请重新下载完整修改器。')
    dll = c.WinDLL(str(path), use_last_error=True)
    definitions = (
        ('SFileOpenArchive', [c.c_wchar_p, U, U, c.POINTER(H)], B),
        ('SFileCloseArchive', [H], B), ('SFileOpenFileEx', [H, c.c_char_p, U, c.POINTER(H)], B),
        ('SFileCloseFile', [H], B), ('SFileGetFileSize', [H, c.POINTER(U)], U),
        ('SFileReadFile', [H, H, U, c.POINTER(U), H], B),
        ('SFileFindFirstFile', [H, c.c_char_p, c.POINTER(_Find), c.c_wchar_p], H),
        ('SFileFindNextFile', [H, c.POINTER(_Find)], B), ('SFileFindClose', [H], B),
        ('SFileSetLocale', [U], U),
        ('SFileCreateFile', [H, c.c_char_p, c.c_uint64, U, U, U, c.POINTER(H)], B),
        ('SFileWriteFile', [H, H, U, U], B), ('SFileFinishFile', [H], B),
        ('SFileFlushArchive', [H], B),
        ('SFileGetMaxFileCount', [H], U), ('SFileSetMaxFileCount', [H, U], B),
    )
    for name, args, result in definitions:
        function = getattr(dll, name); function.argtypes, function.restype = args, result
    return dll


def canonical_name(name):
    name = str(name).replace('/', '\\')
    if (not name or len(name.encode('utf8')) >= 260 or '\x00' in name
            or name.startswith('\\') or ':' in name or any(p in ('', '.', '..') for p in name.split('\\'))):
        raise MpqError('地图内文件路径不规范，已停止处理。')
    return name


class Archive:
    def __init__(self, path, *, writable=False):
        self.path = Path(path)
        self.dll = library(); self.handle = H(); self.writable = writable
        with LOCK:
            if not self.dll.SFileOpenArchive(str(self.path), 0, 0 if writable else 0x100, c.byref(self.handle)):
                raise MpqError(f'地图归档打开失败（错误 {c.get_last_error()}）：{self.path}')

    def __enter__(self): return self

    def __exit__(self, *_): self.close()

    def close(self):
        if self.handle:
            handle, self.handle = self.handle, H()
            with LOCK:
                if not self.dll.SFileCloseArchive(handle):
                    raise MpqError(f'地图归档关闭失败（错误 {c.get_last_error()}）。')

    def members(self):
        result = []
        with LOCK:
            data = _Find()
            found = self.dll.SFileFindFirstFile(self.handle, b'*', c.byref(data), None)
            if not found or found == H(-1).value:
                raise MpqError('地图文件目录未能读取，已停止处理。')
            try:
                while True:
                    try: name = data.name.decode('utf8')
                    except UnicodeDecodeError: name = data.name.decode('cp1252')
                    result.append(Member(name, data.size, data.flags, data.locale, data.block_index))
                    if len(result) > 100000:
                        raise MpqError('地图内文件数量超出处理范围，已停止处理。')
                    if not self.dll.SFileFindNextFile(found, c.byref(data)):
                        if c.get_last_error() != 18:
                            raise MpqError('地图文件目录读取中断，已停止处理。')
                        break
            finally: self.dll.SFileFindClose(found)
        return tuple(result)

    def read(self, member, *, optional=False):
        name = member.name if isinstance(member, Member) else canonical_name(member)
        locale = member.locale if isinstance(member, Member) else 0
        with LOCK:
            previous = self.dll.SFileSetLocale(locale)
            handle = H()
            try:
                if not self.dll.SFileOpenFileEx(self.handle, name.encode('utf8'), 0, c.byref(handle)):
                    if optional and c.get_last_error() in (2, 3): return None
                    raise MpqError(f'地图内文件读取失败（错误 {c.get_last_error()}）：{name}')
                high = U(); size = self.dll.SFileGetFileSize(handle, c.byref(high))
                if high.value or size > MAX_MEMBER:
                    raise MpqError(f'地图内文件过大，已停止处理：{name}')
                buffer = c.create_string_buffer(size); count = U()
                if size and not self.dll.SFileReadFile(handle, buffer, size, c.byref(count), None):
                    raise MpqError(f'地图内文件读取不完整：{name}')
                if count.value != size: raise MpqError(f'地图内文件长度不符：{name}')
                return buffer.raw
            finally:
                if handle: self.dll.SFileCloseFile(handle)
                self.dll.SFileSetLocale(previous)

    def write(self, name, payload, *, original=None):
        if not self.writable: raise MpqError('归档仅以只读方式打开。')
        name = canonical_name(name)
        if not isinstance(payload, bytes) or len(payload) > MAX_MEMBER:
            raise MpqError('待写入的地图数据大小异常。')
        flags = original.flags & STORAGE_FLAGS if original else 0x200
        locale = original.locale if original else 0
        with LOCK:
            handle = H()
            if not self.dll.SFileCreateFile(self.handle, name.encode('utf8'), 0, len(payload), locale,
                                           flags | 0x80000000, c.byref(handle)):
                raise MpqError(f'地图内文件创建失败（错误 {c.get_last_error()}）：{name}')
            try:
                buffer = c.create_string_buffer(payload)
                if payload and not self.dll.SFileWriteFile(handle, buffer, len(payload), 2):
                    raise MpqError(f'地图内文件写入失败：{name}')
            finally:
                if not self.dll.SFileFinishFile(handle): raise MpqError(f'地图内文件提交失败：{name}')

    def flush(self):
        with LOCK:
            if not self.dll.SFileFlushArchive(self.handle): raise MpqError('地图数据保存失败。')

    def reserve(self, additional):
        if not self.writable or not 0 <= additional <= 4096:
            raise MpqError('地图新增文件数量异常。')
        with LOCK:
            current = self.dll.SFileGetMaxFileCount(self.handle)
            required = len(self.members()) + additional + 8
            if required > current:
                capacity = 1 << (required - 1).bit_length()
                if not self.dll.SFileSetMaxFileCount(self.handle, capacity):
                    raise MpqError('地图文件目录扩容失败，已保留原文件。')
