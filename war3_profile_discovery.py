"""Read-only discovery infrastructure. Imported only after an exact profile miss.

No process writes, game callbacks, protection changes or implicit operation replay.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import os
import struct
import tempfile
import time

from war3_game_profile import ProfileError, _no_duplicates

RECIPE_VERSION = 26
CACHE_VERSION = 1
CHUNK = 256 * 1024
MAX_SCAN_BYTES = 256 * 1024 * 1024


class DiscoveryError(ProfileError):
    def __init__(self, reason, *, code="unresolved", evidence=()):
        super().__init__(reason)
        self.discovery_report = {"code": code, "reason": reason,
                                 "evidence": [e.to_dict() for e in evidence]}
        self.report = {"operation": "adapter", "automatic_discovery": self.discovery_report}


@dataclass(frozen=True)
class DiscoveryEvidence:
    dependency: str
    state: str
    method: str
    candidates: tuple = ()
    anchors: tuple = ()
    detail: str = ""

    def __post_init__(self):
        def immutable(value):
            if isinstance(value,(list,tuple)):return tuple(immutable(item) for item in value)
            if isinstance(value,dict):raise ValueError('Evidence anchors must be immutable scalar/sequence data')
            return value
        object.__setattr__(self, "candidates", immutable(self.candidates))
        object.__setattr__(self, "anchors", immutable(self.anchors))

    def to_dict(self):
        return dict(dependency=self.dependency, state=self.state, method=self.method,
                    candidates=list(self.candidates), anchors=list(self.anchors), detail=self.detail)


class ScanBudget:
    def __init__(self, seconds=30, cancel=None, progress=None, clock=time.monotonic):
        self.clock = clock
        self.deadline = clock() + seconds
        self.cancel = cancel
        self.progress = progress
        self.bytes_read = 0
        self.last_progress = -1.0

    def check(self, stage="", fraction=None):
        if self.cancel is not None and self.cancel.is_set():
            raise DiscoveryError("已取消自动定位；未修改游戏，可重新连接后重试。", code="cancelled")
        now = self.clock()
        if now >= self.deadline:
            raise DiscoveryError("自动定位已达到本轮时间限制；未修改游戏，可重新连接后重试。", code="timeout")
        if self.progress is not None and (fraction == 1 or now - self.last_progress >= .15):
            self.progress(stage, fraction)
            self.last_progress = now

    def read(self, memory, address, size):
        self.check()
        self.bytes_read += size
        if self.bytes_read > MAX_SCAN_BYTES:
            raise DiscoveryError("本轮定位已达到读取范围限制；未修改游戏。", code="budget")
        value = memory.read(address, size)
        if len(value) != size:
            raise OSError("partial discovery read")
        return value


@dataclass(frozen=True)
class ImageSegment:
    rva: int
    data: bytes
    executable: bool
    name: str = ""


class DiscoveryImage:
    def __init__(self, base, size, segments, fingerprint, unreadable=()):
        self.base, self.size = base, size
        self.segments = tuple(sorted(segments, key=lambda s: s.rva))
        self.fingerprint = tuple(fingerprint)
        self.unreadable = tuple(unreadable)

    def read(self, rva, size):
        if rva < 0 or size <= 0 or rva + size > self.size:
            raise OSError("image range exceeds bounds")
        for segment in self.segments:
            if segment.rva <= rva and rva + size <= segment.rva + len(segment.data):
                return segment.data[rva-segment.rva:rva-segment.rva+size]
        raise OSError("image page unavailable")

    def executable(self, rva):
        return any(s.executable and s.rva <= rva < s.rva + len(s.data) for s in self.segments)

    def function_size(self, rva, maximum=4096):
        if not hasattr(self, '_runtime_functions'):
            functions = {}
            for segment in self.segments:
                if segment.name != '.pdata':
                    continue
                for offset in range(0, len(segment.data)-11, 12):
                    begin, end, unwind = struct.unpack_from('<3I', segment.data, offset)
                    if 0 < begin < end <= self.size and 0 < unwind < self.size:
                        if begin in functions and functions[begin] != end:
                            functions[begin] = 0
                        else:
                            functions.setdefault(begin, end)
            self._runtime_functions = functions
        end = self._runtime_functions.get(rva, 0)
        return end-rva if rva < end <= rva+maximum else None

    def canonical_digest(self, rva, size, *, pointers=False, budget=None):
        data = self.read(rva, size)
        if pointers:
            normalized = bytearray(data)
            for offset in range(0, len(data)-7, 8):
                if budget is not None and offset % 65536 == 0:
                    budget.check("正在核对只读数据布局")
                value = struct.unpack_from('<Q', data, offset)[0]
                if self.base <= value < self.base+self.size:
                    struct.pack_into('<Q', normalized, offset, value-self.base)
            data = normalized
        return hashlib.sha256(data).hexdigest()

    def find(self, needle, budget, executable=None, limit=4096):
        matches = []
        for segment in self.segments:
            if executable is not None and segment.executable != executable:
                continue
            pos = 0
            while True:
                budget.check()
                pos = segment.data.find(needle, pos)
                if pos < 0:
                    break
                matches.append(segment.rva + pos)
                if len(matches) > limit:
                    raise DiscoveryError("定位特征过于常见，无法唯一确定当前版本的数据。", code="ambiguous")
                pos += 1
        return matches

    @classmethod
    def capture(cls, memory, base, fingerprint, budget):
        # Parse only bounded PE metadata. No pefile or executable loading needed.
        dos = budget.read(memory, base, 64)
        if dos[:2] != b"MZ":
            raise DiscoveryError("目标不是有效的游戏主程序。", code="identity")
        offset = struct.unpack_from("<I", dos, 60)[0]
        if not 64 <= offset <= 4096:
            raise DiscoveryError("游戏映像头不完整。", code="identity")
        nt = budget.read(memory, base + offset, 264)
        actual = (struct.unpack_from("<H", nt, 4)[0], struct.unpack_from("<I", nt, 8)[0],
                  struct.unpack_from("<I", nt, 80)[0])
        if nt[:4] != b"PE\0\0" or actual != tuple(fingerprint):
            raise DiscoveryError("定位期间游戏主程序身份发生变化，请重新连接。", code="identity")
        count, optsize = struct.unpack_from("<H", nt, 6)[0], struct.unpack_from("<H", nt, 20)[0]
        if not 1 <= count <= 96 or not 112 <= optsize <= 4096:
            raise DiscoveryError("游戏映像节表不完整。", code="identity")
        headers = budget.read(memory, base + offset + 24 + optsize, count * 40)
        sections = []
        for index in range(count):
            row = headers[index*40:index*40+40]
            size, rva = struct.unpack_from("<II", row, 8)
            flags = struct.unpack_from("<I", row, 36)[0]
            name = row[:8].split(b"\0", 1)[0].decode("ascii", "replace")
            if size and flags & 0x40000000 and not flags & 0x80000000:
                if rva < 4096 or rva + size > actual[2]:
                    raise DiscoveryError("游戏映像节超出边界。", code="identity")
                sections.append((rva, size, bool(flags & 0x20000000), name))
        total = sum(s[1] for s in sections)
        if total > MAX_SCAN_BYTES // 2:
            raise DiscoveryError("游戏映像超出本轮定位范围。", code="budget")
        segments, holes, done = [], [], 0
        for rva, size, executable, name in sections:
            pending, start = bytearray(), rva
            def flush():
                nonlocal pending
                if pending:
                    segments.append(ImageSegment(start, bytes(pending), executable, name))
                    pending = bytearray()
            for relative in range(0, size, CHUNK):
                budget.check("正在读取新版本定位数据", done / max(total, 1))
                at, count = rva + relative, min(CHUNK, size-relative)
                try:
                    data = budget.read(memory, base + at, count)
                    if not pending: start = at
                    pending.extend(data)
                except OSError:
                    # Page fallback preserves holes; never synthesize zero-filled code.
                    for page in range(at, at+count, 4096):
                        length = min(4096, at+count-page)
                        try:
                            data = budget.read(memory, base+page, length)
                            if not pending: start = page
                            pending.extend(data)
                        except OSError:
                            flush()
                            holes.append((page, length))
                done += count
            flush()
        return cls(base, actual[2], segments, actual, holes)


def unique_evidence(dependency, method, values, anchors=()):
    values = tuple(sorted(set(values)))
    return DiscoveryEvidence(dependency, "confirmed" if len(values) == 1 else
                             "ambiguous" if values else "unresolved", method,
                             values, tuple(anchors))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".discovery-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf8") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def executable_digest(path, fingerprint, budget):
    # Full hashing is unknown-build only, once per connection; never a hot path.
    digest = hashlib.sha256()
    try:
        stream = open(path, "rb")
    except OSError as exc:
        raise DiscoveryError("未能读取当前游戏文件来确认版本身份，请检查文件是否仍在原路径。", code="identity") from exc
    with stream:
        header = stream.read(4096)
        if len(header) < 64 or header[:2] != b"MZ":
            raise DiscoveryError("游戏文件身份校验失败。", code="identity")
        offset = struct.unpack_from("<I", header, 60)[0]
        if offset + 88 > len(header) or header[offset:offset+4] != b"PE\0\0":
            raise DiscoveryError("游戏文件映像头不完整。", code="identity")
        actual = (struct.unpack_from("<H", header, offset+4)[0],
                  struct.unpack_from("<I", header, offset+8)[0],
                  struct.unpack_from("<I", header, offset+80)[0])
        if actual != tuple(fingerprint):
            raise DiscoveryError("游戏磁盘文件与已运行的版本不同，请重新启动游戏后连接。", code="identity")
        digest.update(header)
        while chunk := stream.read(1024*1024):
            budget.check("正在识别新版本游戏文件")
            digest.update(chunk)
    return digest.hexdigest()


class DiscoveryCache:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else (
            Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "War3Trainer" / "discovery")

    @staticmethod
    def key(identity):
        return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()

    def load(self, identity):
        path = self.directory / (self.key(identity) + ".json")
        try:
            if path.stat().st_size > 2*1024*1024: return None
            data = json.loads(path.read_text(encoding="utf8"), object_pairs_hook=_no_duplicates)
            if data.get("identity") != identity or data.get("cache_version") != CACHE_VERSION:
                return None
            digest = data.pop("payload_sha256", None)
            if digest != hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest():
                return None
            return data
        except (OSError, ValueError, TypeError):
            return None

    def save(self, identity, payload):
        data = dict(payload, identity=identity, cache_version=CACHE_VERSION)
        data["payload_sha256"] = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        atomic_json(self.directory / (self.key(identity)+".json"), data)
