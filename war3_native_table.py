"""Read the live 3.0 native registration list without executing a handler."""
from __future__ import annotations

from dataclasses import dataclass

from war3_object_registry import ObjectIdentityError, _ptr, _read

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
        try:
            byte = _read(memory, address + len(result), 1)
        except OSError as exc:
            raise ObjectIdentityError("Native metadata read failed") from exc
        if byte == b"\0":
            value = bytes(result)
            try:
                text = value.decode("ascii")
            except UnicodeDecodeError as exc:
                raise ObjectIdentityError("Native metadata is not ASCII") from exc
            if not text:
                raise ObjectIdentityError("Native metadata is empty")
            return text
        result.extend(byte)
    raise ObjectIdentityError("Native metadata has no bounded terminator")


class NativeTable24268:
    """A frame-bound view of context slot 5's embedded registration list."""

    def __init__(self, memory, context5: int):
        if not _ptr(context5):
            raise ObjectIdentityError("Native context slot 5 is invalid")
        self.context5 = context5
        self.table = context5 + 0x28
        self.head = self._qword(memory, self.table + 0x18)
        self.terminal = (self.table + 0x10) | 1
        self.entries = self._read_entries(memory)
        if self._qword(memory, self.table + 0x18) != self.head:
            raise ObjectIdentityError("Native registration head changed")

    @staticmethod
    def _qword(memory, address):
        import struct
        return struct.unpack("<Q", _read(memory, address, 8))[0]

    def _read_entries(self, memory):
        entries = {}
        node = self.head
        for _ in range(MAX_NODES):
            if node == self.terminal:
                return entries
            if not _ptr(node) or node in entries:
                raise ObjectIdentityError("Native registration list is invalid or cyclic")
            name = _string(memory, self._qword(memory, node + 0x28))
            signature = _string(memory, self._qword(memory, node + 0x40))
            handler = self._qword(memory, node + 0x30)
            if not _ptr(handler) or not signature.startswith("(") or ")" not in signature:
                raise ObjectIdentityError("Native registration ABI metadata is invalid")
            if name in entries:
                raise ObjectIdentityError("Duplicate native registration name")
            entries[name] = LiveNativeEntry(name, signature, node, handler)
            node = self._qword(memory, node + 0x20)
        raise ObjectIdentityError("Native registration list exceeded bound")

    def require(self, *names: str) -> dict[str, LiveNativeEntry]:
        missing = [name for name in names if name not in self.entries]
        if missing:
            raise ObjectIdentityError("Missing native registrations: " + ", ".join(missing))
        return {name: self.entries[name] for name in names}
