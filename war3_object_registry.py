"""Read 3.0.0.24268 object identities through the engine's indexed registry.

Matches the two branches of the game's agent resolver at RVA 0x1951b0.
No code execution, process memory scan, handle guessing or cached owner index.
"""
import ctypes
import struct

TIMESTAMP = 0x6AA4DE70
IMAGE_SIZE = 0xE155000
RESOLVER_RVA = 0x1951B0
ROOT_RVA = 0x2F807F0
RESOLVER_CODE = bytes.fromhex(
    "8bc1448bcac1e81f84c0752a488b052db6de023b48307357488b40188bc94803c9"
    "833cc8fe7548488b4cc80833c0395124480f44c1c3488b1503b6de028bc10fbaf01f"
    "3b426873274c8b42504803c041833cc0fe75198bc10fbaf01f4803c0498b4cc00833c0"
    "44394924480f44c1c333c0c3")
UNIT_TAG = 0x2B7733752B61676C
PLAYER_TAG = 0x2B706C792B61676C
GAME_STATE_SLOT_RVA = 0x2E9AD00
GAME_STATE_CHECKS = (
    (0xCA741C, bytes.fromhex("488b1ddd381f02")),
    (0xCA7475, bytes.fromhex("48d1cb48b8295b9bfc376fe05b48c1c31e4803d848b82b1367efb7c7113a4833d848b83d5d7f3e90272c2d4803d8")),
    (0x8BBF50, bytes.fromhex("4883ec2883fa1b761683faff740ab957000000e8f8e489ff33c04883c428c33b919826000073f14863c2488b84c1a02600004883c428c3")),
)


def decode_game_state(encoded):
    mask = 0xFFFFFFFFFFFFFFFF
    value = ((encoded >> 1) | (encoded << 63)) & mask
    value = ((value << 30) | (value >> 34)) & mask
    value = ((value + 0x5BE06F37FC9B5B29) & mask) ^ 0x3A11C7B7EF67132B
    return (value + 0x2D2C27903E7F5D3D) & mask


class ObjectIdentityError(RuntimeError):
    pass


def _ptr(value):
    return 0x10000 <= value < 0x800000000000 and value % 8 == 0


def _read(memory, address, size):
    data = memory.read(address, size)
    if len(data) != size:
        raise ObjectIdentityError("Incomplete object registry read")
    return data


def game_module_base(memory):
    """Enumerate loaded modules, not virtual memory regions."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    enum = kernel.K32EnumProcessModulesEx
    enum.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_ulong,
                     ctypes.POINTER(ctypes.c_ulong), ctypes.c_ulong)
    enum.restype = ctypes.c_int
    name = kernel.K32GetModuleBaseNameW
    name.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_ulong)
    name.restype = ctypes.c_ulong
    capacity = 128
    for _ in range(3):
        modules = (ctypes.c_void_p * capacity)()
        needed = ctypes.c_ulong()
        if not enum(memory.handle, modules, ctypes.sizeof(modules), ctypes.byref(needed), 2):
            raise ctypes.WinError(ctypes.get_last_error())
        if needed.value > ctypes.sizeof(modules):
            capacity = (needed.value + ctypes.sizeof(ctypes.c_void_p) - 1) // ctypes.sizeof(ctypes.c_void_p)
            if capacity > 4096:
                raise ObjectIdentityError("Unexpected module count")
            continue
        for module in modules[:needed.value // ctypes.sizeof(ctypes.c_void_p)]:
            text = ctypes.create_unicode_buffer(1024)
            if name(memory.handle, module, text, len(text)) and text.value.lower() == "warcraft iii.exe":
                return int(module)
        break
    raise ObjectIdentityError("Warcraft III module not found")


class ObjectRegistry24268:
    def __init__(self, memory, module_base):
        self.base = module_base
        header = _read(memory, module_base, 0x40)
        if header[:2] != b"MZ":
            raise ObjectIdentityError("Game image has no DOS header")
        nt_offset = struct.unpack_from("<I", header, 0x3C)[0]
        if not 0x40 <= nt_offset <= 0x1000:
            raise ObjectIdentityError("Unexpected game PE header offset")
        nt = _read(memory, module_base + nt_offset, 0x58)
        if (nt[:4], struct.unpack_from("<H", nt, 4)[0],
            struct.unpack_from("<I", nt, 8)[0], struct.unpack_from("<I", nt, 0x50)[0]) != (
                b"PE\0\0", 0x8664, TIMESTAMP, IMAGE_SIZE):
            raise ObjectIdentityError("Game build has no verified object registry profile")
        if _read(memory, module_base + RESOLVER_RVA, len(RESOLVER_CODE)) != RESOLVER_CODE:
            raise ObjectIdentityError("Game object resolver code differs from verified profile")
        # The native's decoder page is not externally readable in this build.
        # Its arithmetic was recovered from the captured shared image section.
        # Verify the readable player accessor in addition to PE + agent code;
        # players() independently validates every resulting object identity.
        rva, code = GAME_STATE_CHECKS[-1]
        if _read(memory, module_base + rva, len(code)) != code:
            raise ObjectIdentityError("Game player-array code differs from verified profile")

    @classmethod
    def attach(cls, memory):
        return cls(memory, game_module_base(memory))

    def _qword(self, memory, address):
        return struct.unpack("<Q", _read(memory, address, 8))[0]

    def resolve_handle(self, memory, full_handle):
        if not 0 <= full_handle <= 0xFFFFFFFFFFFFFFFF:
            raise ObjectIdentityError("Full object handle is outside uint64")
        low = full_handle & 0xFFFFFFFF
        index = low & 0x7FFFFFFF
        offset = 0x50 if low & 0x80000000 else 0x18
        root = self._qword(memory, self.base + ROOT_RVA)
        if not _ptr(root):
            raise ObjectIdentityError("Object registry is not initialized")

        def table_state():
            data = _read(memory, root + offset, 0x1C)
            table = struct.unpack_from("<Q", data)[0]
            count = struct.unpack_from("<I", data, 0x18)[0]
            if not _ptr(table) or not index < count <= 0x10000000:
                raise ObjectIdentityError("Object index is outside registry bounds")
            if not _ptr(table + index * 16):
                raise ObjectIdentityError("Invalid object slot address")
            return table

        table = table_state()
        slot = _read(memory, table + index * 16, 16)
        marker, _, owner = struct.unpack("<IIQ", slot)
        if marker != 0xFFFFFFFE or not _ptr(owner):
            raise ObjectIdentityError("Object slot is not live")
        if self._qword(memory, owner + 0x20) != full_handle:
            raise ObjectIdentityError("Object handle generation changed")
        if (table_state() != table or _read(memory, table + index * 16, 16) != slot
                or self._qword(memory, owner + 0x20) != full_handle
                or self._qword(memory, self.base + ROOT_RVA) != root):
            raise ObjectIdentityError("Object registry changed while reading")
        return owner

    def resolve_unit(self, memory, unit):
        if not _ptr(unit):
            raise ObjectIdentityError("Invalid unit pointer")
        handle = self._qword(memory, unit + 0x18)
        owner = self.resolve_handle(memory, handle)
        if (self._qword(memory, owner + 0x18) != UNIT_TAG
                or self._qword(memory, owner + 0x90) != unit
                or self._qword(memory, owner + 0x20) != handle
                or self._qword(memory, unit + 0x18) != handle):
            raise ObjectIdentityError("Unit identity changed or mismatches registry")
        return handle, owner

    def players(self, memory):
        """Read the actual game-state player array; this does not pick a local player."""
        slot = self.base + GAME_STATE_SLOT_RVA
        encoded = self._qword(memory, slot)
        state = decode_game_state(encoded)
        if not _ptr(state):
            raise ObjectIdentityError("Game state pointer is invalid")
        count_raw = _read(memory, state + 0x2698, 4)
        count = struct.unpack("<I", count_raw)[0]
        if not 0 < count <= 28:
            raise ObjectIdentityError("Game state player count is invalid")
        raw = _read(memory, state + 0x26A0, count * 8)
        players = struct.unpack(f"<{count}Q", raw)
        if len(set(players)) != count or any(not _ptr(player) for player in players):
            raise ObjectIdentityError("Player array contains duplicate or invalid pointers")
        for player in players:
            full = self._qword(memory, player + 0x18)
            owner = self.resolve_handle(memory, full)
            if (self._qword(memory, owner + 0x18) != PLAYER_TAG
                    or self._qword(memory, owner + 0x90) != player
                    or self._qword(memory, player + 0x18) != full):
                raise ObjectIdentityError("Player identity mismatches registry")
        if (_read(memory, state + 0x26A0, len(raw)) != raw
                or _read(memory, state + 0x2698, 4) != count_raw
                or self._qword(memory, slot) != encoded):
            raise ObjectIdentityError("Player array changed while reading")
        return list(players)
