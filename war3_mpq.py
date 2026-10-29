"""Bounded local MPQ access through the bundled, hash-verified StormLib."""
from __future__ import annotations
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
import ctypes as c
import hashlib
import importlib.util
import os
import re
import shutil
import struct
import sys
import tempfile
import threading
from war3_mpq_names import STANDARD_RESOURCE_NAMES

DLL_SHA256 = '6cd644f3c091c2fff6430cbf612dbbf6657d8508941fba2e925caadfa7a04da6'
STORAGE_FLAGS = 0x100 | 0x200 | 0x10000 | 0x20000 | 0x1000000 | 0x4000000
MAX_MEMBER = 512 * 1024 * 1024
WRITE_REVISION = 'classic-header-preserved-hash-v1-20261028'
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
    hash_index: int = field(default=-1, compare=False)


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
        seen = {}; directory = None; redundant = 0; enumerated = 0
        with LOCK:
            data = _Find()
            found = self.dll.SFileFindFirstFile(self.handle, b'*', c.byref(data), None)
            if not found or found == H(-1).value:
                raise MpqError('地图文件目录未能读取，已停止处理。')
            try:
                while True:
                    try: name = data.name.decode('utf8')
                    except UnicodeDecodeError: name = data.name.decode('cp1252')
                    member = Member(name, data.size, data.flags, data.locale, data.block_index, data.compressed_size, data.hash_index)
                    key = (name.casefold(), data.locale, data.block_index)
                    duplicate = False
                    if key in seen:
                        if directory is None:
                            from war3_mpq_directory import read_directory
                            offset = c.c_uint64(); returned = U()
                            if not self.dll.SFileGetFileInfo(self.handle,5,c.byref(offset),c.sizeof(offset),c.byref(returned)):
                                raise MpqError('地图重复文件记录的目录位置未能读取。')
                            try: _, directory = read_directory(self.path,offset.value)
                            except ValueError:
                                # Unsupported layouts retain the old duplicate
                                # policy; only proven identical hash rows merge.
                                directory = ()
                        previous = seen[key]
                        duplicate = (0 <= previous.hash_index < len(directory)
                            and data.hash_index < len(directory)
                            and directory[previous.hash_index] == directory[data.hash_index])
                    if duplicate: redundant += 1
                    else:
                        result.append(member); seen[key] = member
                    enumerated += 1
                    if enumerated > 362144:
                        raise MpqError('地图文件目录记录数量超出处理范围。')
                    if len(result) > 100000:
                        raise MpqError('地图内文件数量超出处理范围，已停止处理。')
                    if not self.dll.SFileFindNextFile(found, c.byref(data)):
                        if c.get_last_error() != 18:
                            raise MpqError('地图文件目录读取中断，已停止处理。')
                        break
            finally: self.dll.SFileFindClose(found)
        self.redundant_hash_entries = redundant
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
            aliases=getattr(self,'redundant_hash_entries',0)
            if unknown or aliases:
                evidence.update(performed=False,bytes_after=before,unknown_member_count=len(unknown),
                    unknown_member_examples=unknown[:16],redundant_hash_entries=aliases,
                    reason='original_unknown_storage_and_hash_chains_preserved')
                if force:
                    raise MpqError('部分资源没有真实文件名，不能强制移动其原始存储，原文件已保留。',details=evidence)
                if progress:progress('archive_compaction_skipped',evidence)
                return evidence
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

    def reserve(self, additional, *, progress=None, check=None):
        if not self.writable or not 0 <= additional <= 4096:
            raise MpqError('地图新增文件数量异常。')
        with LOCK:
            current = self.dll.SFileGetMaxFileCount(self.handle)
            members = self.members()
            required = len(members) + getattr(self,'redundant_hash_entries',0) + additional + 8
            unknown = [m.name for m in members if unknown_member_name(m.name)]
            evidence = dict(archive=self.path.name,current_capacity=current,member_count=len(members),
                additional=additional,required_capacity=required,identified_names=list(self.identified_names),
                unknown_member_count=len(unknown),unknown_member_examples=unknown[:16],
                strategy='exact_warcraft_names_before_directory_growth',write_revision=WRITE_REVISION)
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
                        return self._preserve_unknown_directory(capacity,additional,evidence,progress,check)
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

    def _preserve_unknown_directory(self, capacity, additional, evidence, progress, check):
        """Keep unnamed blocks in place; verify a separate candidate before swap."""
        from war3_mpq_directory import growth_plan
        def checkpoint():
            if check: check()
        def emit(stage):
            if progress: progress(stage,dict(evidence))
        def identities(archive):
            return sorted((m.name.casefold(),m.locale,m.block_index,m.size,m.flags,m.compressed_size)
                for m in archive.members())
        def prefix_digest(path, length, offset):
            digest=hashlib.sha256(); position=0
            with Path(path).open('rb') as stream:
                while position<length:
                    checkpoint(); raw=bytearray(stream.read(min(4*1024*1024,length-position)))
                    if not raw: raise MpqError('地图目录扩容副本长度不符。')
                    for start in (offset+8,offset+16,offset+24):
                        left=max(start,position); right=min(start+4,position+len(raw))
                        if left<right: raw[left-position:right-position]=bytes(right-left)
                    digest.update(raw); position+=len(raw)
            return digest.hexdigest()
        members=self.members(); before=identities(self)
        names=[]
        for m in members:
            if unknown_member_name(m.name): continue
            try: names.append(canonical_name(m.name))
            except MpqError: pass
        offset=c.c_uint64(); returned=U()
        if not self.dll.SFileGetFileInfo(self.handle,5,c.byref(offset),c.sizeof(offset),c.byref(returned)):
            raise MpqError('地图目录扩容前的归档位置未能读取。',details=evidence)
        self.close()
        pending=backup=None; swapped=False
        def reopen():
            if not self.dll.SFileOpenArchive(str(self.path),0,0,c.byref(self.handle)):
                raise MpqError(f'扩容后的地图归档重新打开失败（错误 {c.get_last_error()}）。')
            self.identify_names(names)
        try:
            checkpoint()
            payload,details=growth_plan(self.path,offset.value,members,capacity,additional,check=check)
            evidence.update(details)
            size=self.path.stat().st_size
            padding=(-size)%16
            if size+padding+len(payload)-offset.value > 0xffffffff:
                raise ValueError('classic MPQ directory would exceed the 32-bit archive range')
            for purpose in ('pending','backup'):
                descriptor,temp=tempfile.mkstemp(prefix='war3-directory-'+purpose+'-',suffix='.tmp',dir=self.path.parent)
                os.close(descriptor)
                if purpose=='pending':pending=Path(temp)
                else:backup=Path(temp)
            emit('archive_capacity_preserving_begin')
            digest=prefix_digest(self.path,size,offset.value)
            shutil.copyfile(self.path,pending)
            with pending.open('r+b') as stream:
                stream.seek(0,2); stream.write(bytes(padding)); position=stream.tell()-offset.value
                stream.write(payload); end=stream.tell()-offset.value
                for at,value in ((8,end),(16,position),(24,evidence['actual_capacity'])):
                    stream.seek(offset.value+at); stream.write(struct.pack('<I',value))
                stream.flush(); os.fsync(stream.fileno())
            if prefix_digest(pending,size,offset.value)!=digest or prefix_digest(self.path,size,offset.value)!=digest:
                raise MpqError('地图目录扩容时原始资源存储发生变化，已停止采用副本。')
            with Archive(pending) as candidate:
                candidate.identify_names(names)
                if identities(candidate)!=before or candidate.dll.SFileGetMaxFileCount(candidate.handle)!=evidence['actual_capacity']:
                    raise MpqError('地图目录扩容后成员身份或容量读回不一致。')
            checkpoint(); shutil.copyfile(self.path,backup)
            os.replace(pending,self.path); swapped=True
            reopen()
            evidence.update(growth_verified=True,original_storage_bytes_verified=True,
                logical_members_verified=True,header_fields_changed=[8,16,24],error_code_before_fallback=10007)
            evidence.pop('error_code',None)
            emit('archive_capacity_preserving_verified')
            return evidence
        except BaseException as exc:
            if self.handle:self.close()
            if swapped and backup and backup.exists():os.replace(backup,self.path)
            reopen()
            evidence.update(growth_verified=False,fallback_error=str(exc))
            emit('archive_capacity_preserving_failed')
            if not isinstance(exc,Exception):raise
            if isinstance(exc,(MpqError,InterruptedError)):raise
            if check:check()
            raise MpqError('地图缺失资源文件名，保留原始查找关系的目录扩容未通过校验（原错误 10007）。原文件已保留。',details=evidence) from exc
        finally:
            for temp in (pending,backup):
                if temp:temp.unlink(missing_ok=True)


def normalize_classic_header(path, *, names=(), progress=None, check=None):
    """Normalize only a verified V1 header length, on a caller-owned copy.

    Some protectors replace dwHeaderSize with an unrelated value. StormLib
    reads those archives but marks them read-only. Never rebuild their tables:
    change the four-byte length only after every payload is readable, then
    reopen and compare every entry. Callers must pass their staged copy.
    """
    path = Path(path)
    names = tuple(names)
    def emit(stage, data):
        if progress: progress(stage, dict(data))
    def checkpoint():
        if check: check()
    def snapshot(archive):
        hints = []
        for name in names:
            if unknown_member_name(name): continue
            try: hints.append(canonical_name(name))
            except MpqError: continue
        archive.identify_names(hints)
        result = []
        for member in archive.members():
            checkpoint()
            if member.name.casefold() == '(signature)':
                raise MpqError('带签名的地图不能自动修复归档头部，原文件已保留。')
            result.append((member.name.casefold(), member.locale, member.block_index,
                member.size, member.flags, hashlib.sha256(archive.read(member)).hexdigest()))
        return sorted(result)
    checkpoint()
    with LOCK:
        with Archive(path) as archive:
            offset = c.c_uint64(); returned = U()
            if not archive.dll.SFileGetFileInfo(archive.handle, 5, c.byref(offset), c.sizeof(offset), c.byref(returned)):
                raise MpqError(f'地图归档头部位置读取失败（错误 {c.get_last_error()}）。')
            size = path.stat().st_size
            with path.open('rb') as stream:
                stream.seek(offset.value); raw = stream.read(32)
            if len(raw) != 32 or raw[:4] != b'MPQ\x1a':
                raise MpqError('地图归档头部不完整，不能可靠修复，原文件已保留。')
            signature, header_size, archive_size, version, sectors, hashes, blocks, hash_count, block_count = struct.unpack('<IIIHHIIII', raw)
            if version != 0 or header_size == 32:
                return dict(performed=False, reason='header_length_unchanged')
            evidence = dict(archive=path.name, header_offset=offset.value, format_version=version,
                header_size_before=header_size, header_size_after=32, file_bytes=size,
                archive_bytes=archive_size, hash_table_offset=hashes, block_table_offset=blocks,
                hash_table_count=hash_count, block_table_count=block_count, header_before_hex=raw.hex(),
                strategy='v1_length_only_full_member_readback',write_revision=WRITE_REVISION)
            valid = (sectors <= 16 and 0 < hash_count <= 1048576
                and hash_count & (hash_count-1) == 0 and 0 < block_count <= 100000
                and 32 <= archive_size <= size-offset.value and hashes >= 32 and blocks >= 32
                and hashes+hash_count*16 <= archive_size and blocks+block_count*16 <= archive_size
                and (hashes+hash_count*16 <= blocks or blocks+block_count*16 <= hashes)
                and archive.dll.SFileGetMaxFileCount(archive.handle) == hash_count)
            if not valid:
                emit('archive_header_repair_rejected', evidence)
                raise MpqError('地图归档头部和文件目录边界不一致，不能可靠修复，原文件已保留。', details=evidence)
            before = snapshot(archive)
        evidence['verified_members'] = len(before)
        checkpoint(); emit('archive_header_repair_begin', evidence)
        attempted = False
        try:
            with path.open('r+b') as stream:
                stream.seek(offset.value+4)
                attempted = True
                if stream.write(struct.pack('<I', 32)) != 4:
                    raise MpqError('地图归档头部写入不完整。')
                stream.flush(); os.fsync(stream.fileno())
            checkpoint()
            with Archive(path) as archive:
                after = snapshot(archive)
            if path.stat().st_size != size or before != after:
                raise MpqError('地图归档头部修复后原资源校验失败。')
            evidence.update(performed=True, all_members_verified=True)
            emit('archive_header_repair_verified', evidence)
            return evidence
        except BaseException:
            if attempted:
                with path.open('r+b') as stream:
                    stream.seek(offset.value+4); stream.write(raw[4:8])
                    stream.flush(); os.fsync(stream.fileno())
            emit('archive_header_repair_rolled_back', evidence)
            raise

