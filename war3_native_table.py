"""Read the live 3.0 native registration list without executing a handler."""
from __future__ import annotations

from dataclasses import dataclass

from war3_object_registry import ObjectIdentityError, _ptr, _read

from war3_game_profile import current_profile

MAX_NODES = 8192
MAX_STRING = 256


@dataclass(frozen=True)
class LiveNativeEntry:
    name: str
    signature: str
    node: int
    handler: int


def _string(memory, address: int) -> str:
    if not _ptr(address):
        raise ObjectIdentityError("Native metadata pointer is invalid")
    result = bytearray()
    while len(result) < MAX_STRING:
        current = address + len(result)
        # Never read beyond this page or the metadata-string bound. A null
        # terminator is interpreted before decoding any trailing page bytes.
        count = min(64, MAX_STRING-len(result), 0x1000-(current & 0xfff))
        try:
            chunk = _read(memory, current, count)
        except OSError:
            # Some readers expose only the exact string extent. Retry that
            # same position once at byte granularity; no pointer/region scan.
            try: chunk = _read(memory, current, 1)
            except OSError as exc:
                raise ObjectIdentityError("Native metadata read failed") from exc
        end = chunk.find(b"\0")
        result.extend(chunk if end < 0 else chunk[:end])
        if end >= 0:
            try: text = result.decode("ascii")
            except UnicodeDecodeError as exc:
                raise ObjectIdentityError("Native metadata is not ASCII") from exc
            if not text: raise ObjectIdentityError("Native metadata is empty")
            return text
    raise ObjectIdentityError("Native metadata has no bounded terminator")



class NativeTable24268:
    """A frame-bound view of context slot 5's embedded registration list."""

    def __init__(self, memory, context5: int):
        if not _ptr(context5):
            raise ObjectIdentityError("Native context slot 5 is invalid")
        self.layout = current_profile().section("native_table")
        self.context5 = context5
        self.table = context5 + self.layout["table"]
        self.head = self._qword(memory, self.table + self.layout["head"])
        self.terminal = (self.table + self.layout["terminal"]) | 1
        self.entries = self._read_entries(memory)
        if self._qword(memory, self.table + self.layout["head"]) != self.head:
            raise ObjectIdentityError("Native registration head changed")

    @staticmethod
    def _qword(memory, address):
        import struct
        return struct.unpack("<Q", _read(memory, address, 8))[0]

    def _read_entries(self, memory):
        entries = {}
        node = self.head
        visited = set()
        for _ in range(MAX_NODES):
            if node == self.terminal:
                return entries
            if not _ptr(node) or node in visited:
                raise ObjectIdentityError("Native registration list is invalid or cyclic")
            visited.add(node)
            import struct
            offsets = tuple(self.layout[k] for k in ("next", "name", "handler"))
            if offsets == (offsets[0], offsets[0]+8, offsets[0]+16):
                nxt, name_ptr, handler = struct.unpack('<3Q', _read(memory, node+offsets[0], 24))
            else:
                nxt, name_ptr, handler = (self._qword(memory, node+offset) for offset in offsets)
            signature_ptr = self._qword(memory,node+self.layout["signature"])
            name = _string(memory, name_ptr)
            signature = _string(memory, signature_ptr)
            if not _ptr(handler) or not signature.startswith("(") or ")" not in signature:
                raise ObjectIdentityError("Native registration ABI metadata is invalid")
            if name in entries:
                raise ObjectIdentityError("Duplicate native registration name")
            entries[name] = LiveNativeEntry(name, signature, node, handler)
            node = nxt
        raise ObjectIdentityError("Native registration list exceeded bound")

    def require(self, *names: str) -> dict[str, LiveNativeEntry]:
        missing = [name for name in names if name not in self.entries]
        if missing:
            raise ObjectIdentityError("Missing native registrations: " + ", ".join(missing))
        return {name: self.entries[name] for name in names}


def validate_cached_entries(memory, entries):
    """Recheck selected handler/signature pairs even if the table head is unchanged."""
    import struct
    layout=current_profile().section('native_table')
    for name,entry in entries.items():
        handler=struct.unpack('<Q',_read(memory,entry.node+layout['handler'],8))[0]
        signature=struct.unpack('<Q',_read(memory,entry.node+layout['signature'],8))[0]
        if handler!=entry.handler or _string(memory,signature)!=entry.signature:
            raise ObjectIdentityError('Cached native registration changed: '+name)
