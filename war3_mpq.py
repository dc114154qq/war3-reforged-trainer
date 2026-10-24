"""Bounded local MPQ access through the bundled, hash-verified StormLib."""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import ctypes as c
import hashlib
import importlib.util
import re
import sys
import threading
from war3_mpq_names import STANDARD_RESOURCE_NAMES

DLL_SHA256 = '6cd644f3c091c2fff6430cbf612dbbf6657d8508941fba2e925caadfa7a04da6'
STORAGE_FLAGS = 0x100 | 0x200 | 0x10000 | 0x20000 | 0x1000000 | 0x4000000
MAX_MEMBER = 512 * 1024 * 1024
LOCK = threading.RLock()
H, U, B = c.c_void_p, c.c_uint32, c.c_bool

# MPQ editors can remove most of (listfile) while keeping all game files.
# Probe exact, documented Warcraft member names before taking a fingerprint:
# StormLib learns a real name only when that name matches an existing hash.
# This changes its in-memory name cache; it creates no archive members.
WARCRAFT_MEMBER_NAMES = (
    *(f'war3map.{suffix}' for suffix in ('w3i','w3e','wpm','shd','mmp','doo',
        'w3r','w3c','w3s','w3a','w3t','w3u','w3b','w3d','w3h','w3q','wtg','wct','wts','imp','j','lua')),
    *(f'war3mapSkin.{suffix}' for suffix in ('w3a','w3t','w3u','w3b','w3d','w3h','w3q')),
    'war3mapUnits.doo','war3mapMap.blp','war3mapMap.tga','war3mapPreview.tga',
    'war3mapMisc.txt','war3mapSkin.txt','war3mapExtra.txt',
    'scripts\\war3map.j','scripts\\war3map.lua','war3campaign.w3f','war3campaign.wts',
    *(f'war3campaign.{suffix}' for suffix in ('w3a','w3t','w3u','w3b','w3d','w3h','w3q')),
    *(f'war3campaignSkin.{suffix}' for suffix in ('w3a','w3t','w3u','w3b','w3d','w3h','w3q')),
    *(f'UI\\Cursor\\{race}Cursor.blp' for race in ('Human','Orc','Undead','NightElf')),
)


def unknown_member_name(name):
    return bool(re.fullmatch(r'File[0-9a-fA-F]{8}\.[^\\/]+', name, re.IGNORECASE))


class MpqError(ValueError):
    def __init__(self, message, *, details=None):
        super().__init__(message)
        self.mpq_details = details or {}


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
    compressed_size: int = 0


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
        ('SFileCompactArchive', [H, c.c_wchar_p, B], B),
        ('SFileGetFileInfo', [H, U, H, U, c.POINTER(U)], B),
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
            try:
                self.identified_names = self.identify_names(WARCRAFT_MEMBER_NAMES + STANDARD_RESOURCE_NAMES)
            except Exception:
                self.close()
                raise

    def identify_names(self, names):
        """Resolve exact hash matches in StormLib without changing file data."""
        identified = []
        with LOCK:
            previous = self.dll.SFileSetLocale(0)
            try:
                for name in dict.fromkeys(canonical_name(n) for n in names):
                    handle = H()
                    if self.dll.SFileOpenFileEx(self.handle, name.encode('utf8'), 0, c.byref(handle)):
                        if not self.dll.SFileCloseFile(handle):
                            raise MpqError('地图文件名识别后的句柄关闭失败：'+name)
                        identified.append(name)
                    elif c.get_last_error() not in (2, 3):
                        raise MpqError(f'地图文件名识别失败（错误 {c.get_last_error()}）：{name}')
            finally:
                self.dll.SFileSetLocale(previous)
        return tuple(identified)

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
                    result.append(Member(name, data.size, data.flags, data.locale, data.block_index, data.compressed_size))
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

    def compact(self, *, progress=None, force=False):
        """Remove obsolete storage through StormLib, keeping live data and flags.

        Replacing files appends data. A readable archive can otherwise retain
        gigabytes of earlier chapter copies. The estimate is a trigger only;
        caller re-extraction remains the integrity gate after compaction.
        """
        if not self.writable:raise MpqError('归档仅以只读方式打开。')
        with LOCK:
            self.flush();members=self.members();offset=c.c_uint64();returned=U()
            if not self.dll.SFileGetFileInfo(self.handle,5,c.byref(offset),c.sizeof(offset),c.byref(returned)):
                raise MpqError(f'地图归档位置读取失败（错误 {c.get_last_error()}）。')
            unique={m.block_index:m for m in members}
            capacity=self.dll.SFileGetMaxFileCount(self.handle)
            estimate=offset.value+512+capacity*16+(max(unique,default=-1)+1)*16+sum(m.compressed_size for m in unique.values())
            before=self.path.stat().st_size;reclaimable=max(0,before-estimate)
            evidence=dict(archive=self.path.name,bytes_before=before,live_stored_bytes=sum(m.compressed_size for m in unique.values()),
                estimated_reclaimable_bytes=reclaimable,header_offset=offset.value,member_count=len(members))
            if not force and reclaimable<=max(64*1024,before//20):
                evidence.update(performed=False,bytes_after=before,reason='already_dense')
                if progress:progress('archive_compaction_skipped',evidence)
                return evidence
            unknown=[m.name for m in members if unknown_member_name(m.name)]
            if unknown:
                evidence.update(error_code=10007,unknown_member_count=len(unknown),unknown_member_examples=unknown[:16])
                if progress:progress('archive_compaction_failed',evidence)
                raise MpqError('归档整理前仍有资源文件名未识别，已保留原文件。',details=evidence)
            if progress:progress('archive_compaction_begin',evidence)
            c.set_last_error(0)
            if not self.dll.SFileCompactArchive(self.handle,None,False):
                error=c.get_last_error();evidence.update(error_code=error,performed=False)
                if progress:progress('archive_compaction_failed',evidence)
                raise MpqError(f'地图归档整理失败（错误 {error}），已保留原文件。',details=evidence)
            self.flush();evidence.update(performed=True,bytes_after=self.path.stat().st_size)
            evidence['bytes_reclaimed']=before-evidence['bytes_after']
            if progress:progress('archive_compaction_complete',evidence)
            return evidence

    def reserve(self, additional, *, progress=None):
        if not self.writable or not 0 <= additional <= 4096:
            raise MpqError('地图新增文件数量异常。')
        with LOCK:
            current = self.dll.SFileGetMaxFileCount(self.handle)
            members = self.members()
            required = len(members) + additional + 8
            unknown = [m.name for m in members if unknown_member_name(m.name)]
            evidence = dict(archive=self.path.name,current_capacity=current,member_count=len(members),
                additional=additional,required_capacity=required,identified_names=list(self.identified_names),
                unknown_member_count=len(unknown),unknown_member_examples=unknown[:16],
                strategy='exact_warcraft_names_before_directory_growth')
            if progress: progress('archive_capacity_check', evidence)
            if required > current:
                capacity = 1 << (required - 1).bit_length()
                evidence['target_capacity'] = capacity
                c.set_last_error(0)
                if not self.dll.SFileSetMaxFileCount(self.handle, capacity):
                    error = c.get_last_error()
                    evidence.update(error_code=error,growth_verified=False)
                    if progress: progress('archive_capacity_failed', evidence)
                    if error == 10007:
                        raise MpqError(f'地图的内部文件名清单不完整，目录扩容已停止（错误 {error}）。原文件已保留。', details=evidence)
                    if error == 112:
                        raise MpqError(f'地图文件目录容量不足，扩容被归档组件拒绝（错误 {error}）。原文件已保留。', details=evidence)
                    raise MpqError(f'地图文件目录扩容失败（错误 {error}）。原文件已保留。', details=evidence)
                actual = self.dll.SFileGetMaxFileCount(self.handle)
                if actual < capacity:
                    evidence.update(actual_capacity=actual,growth_verified=False)
                    raise MpqError('地图文件目录扩容后的容量校验失败，原文件已保留。', details=evidence)
                evidence.update(actual_capacity=actual,growth_verified=True)
                if progress: progress('archive_capacity_expanded', evidence)
            else:
                evidence.update(actual_capacity=current,growth_verified=True,growth_needed=False)
            return evidence
