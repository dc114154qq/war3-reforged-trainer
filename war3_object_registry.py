"""Read 3.0.0.24268 object identities through the engine's indexed registry.

Matches the two branches of the game's agent resolver at RVA 0x1951b0.
No code execution, process memory scan, handle guessing or cached owner index.
"""
import ctypes
import struct
import time

from war3_game_profile import current_profile, default_profile

# Compatibility constants; runtime code below resolves the active adapter.
_BASE = default_profile()
TIMESTAMP, IMAGE_SIZE = _BASE.fingerprint[1:]
RESOLVER_RVA = _BASE.section('addresses')['object_resolver']
ROOT_RVA = _BASE.section('addresses')['registry_root']
RESOLVER_CODE = _BASE.checks('resolver')[0][1]
UNIT_TAG = _BASE.section('registry')['unit_tag']
PLAYER_TAG = _BASE.section('registry')['player_tag']
GAME_STATE_SLOT_RVA = _BASE.section('addresses')['game_state']
GAME_STATE_CHECKS = _BASE.checks('game_state')


def decode_game_state(encoded, profile=None):
    return (profile or current_profile()).adapter.components.decode_game_state(encoded)


class ObjectIdentityError(RuntimeError):
    pass


class GameModuleNotFoundError(ObjectIdentityError):
    """The target process is alive, but its verified game image is not visible yet."""

    pass


def _ptr(value):
    return 0x10000 <= value < 0x800000000000 and value % 8 == 0


def _read(memory, address, size):
    data = memory.read(address, size)
    if len(data) != size:
        raise ObjectIdentityError("Incomplete object registry read")
    return data


def _registry_table(memory, address, index, count_offset, stride):
    data = _read(memory, address, count_offset + 4)
    table = struct.unpack_from("<Q", data)[0]
    count = struct.unpack_from("<I", data, count_offset)[0]
    if not _ptr(table) or not index < count <= 0x10000000:
        raise ObjectIdentityError("Object index is outside registry bounds")
    if not _ptr(table + index * stride):
        raise ObjectIdentityError("Invalid object slot address")
    return table


def _module_record(base, name, path=""):
    return int(base), str(name or ""), str(path or "")


def _enumerate_process_modules(memory):
    """Return loaded module metadata using PSAPI plus a Toolhelp cross-check."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    records = {}

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
            break
        if needed.value > ctypes.sizeof(modules):
            capacity = (needed.value + ctypes.sizeof(ctypes.c_void_p) - 1) // ctypes.sizeof(ctypes.c_void_p)
            if capacity > 4096:
                raise ObjectIdentityError("Unexpected module count")
            continue
        for module in modules[:needed.value // ctypes.sizeof(ctypes.c_void_p)]:
            if not module:
                continue
            text = ctypes.create_unicode_buffer(1024)
            module_name = text.value if name(memory.handle, module, text, len(text)) else ""
            records[int(module)] = _module_record(module, module_name)
        break

    # Some 3.0 installations reject PSAPI enumeration or module-name queries
    # with ERROR_PARTIAL_COPY while Toolhelp still exposes module metadata.
    kernel.CreateToolhelp32Snapshot.argtypes = (ctypes.c_ulong, ctypes.c_ulong)
    kernel.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    snap = kernel.CreateToolhelp32Snapshot(0x00000018, memory.pid)
    if snap != ctypes.c_void_p(-1).value:
        class ModuleEntry(ctypes.Structure):
            _fields_ = [("size", ctypes.c_ulong), ("module_id", ctypes.c_ulong),
                        ("pid", ctypes.c_ulong), ("global_usage", ctypes.c_ulong),
                        ("process_usage", ctypes.c_ulong),
                        ("base", ctypes.c_void_p), ("module_size", ctypes.c_ulong),
                        ("handle", ctypes.c_void_p), ("name", ctypes.c_wchar * 256),
                        ("path", ctypes.c_wchar * 260)]
        first, nxt = kernel.Module32FirstW, kernel.Module32NextW
        first.argtypes = (ctypes.c_void_p, ctypes.POINTER(ModuleEntry)); first.restype = ctypes.c_int
        nxt.argtypes = (ctypes.c_void_p, ctypes.POINTER(ModuleEntry)); nxt.restype = ctypes.c_int
        entry = ModuleEntry(); entry.size = ctypes.sizeof(ModuleEntry)
        try:
            if first(snap, ctypes.byref(entry)):
                while True:
                    base = int(entry.base or 0)
                    if base:
                        records[base] = _module_record(base, entry.name, entry.path)
                    if not nxt(snap, ctypes.byref(entry)):
                        break
        finally:
            kernel.CloseHandle(snap)
    return list(records.values())


def _verified_image_header(memory, base):
    fingerprint = current_profile().fingerprint
    try:
        header = _read(memory, base, 0x40)
        if header[:2] != b"MZ":
            return False
        nt_offset = struct.unpack_from("<I", header, 0x3C)[0]
        if not 0x40 <= nt_offset <= 0x1000:
            return False
        nt = _read(memory, base + nt_offset, 0x58)
        return (
            nt[:4] == b"PE\0\0"
            and struct.unpack_from("<H", nt, 4)[0] == 0x8664
            and struct.unpack_from("<I", nt, 8)[0] == fingerprint[1]
            and struct.unpack_from("<I", nt, 0x50)[0] == fingerprint[2]
        )
    except (OSError, ObjectIdentityError, struct.error):
        return False


def _module_summary(records):
    rows = []
    for base, name, path in records[:96]:
        label = name or "<unnamed>"
        if path and path.casefold() != label.casefold():
            label = f"{label}@{path}"
        rows.append(f"0x{base:x}:{label}")
    suffix = "..." if len(records) > 96 else ""
    return ",".join(rows) + suffix


def game_module_base(memory):
    """Find the verified game image from loaded modules, independent of its filename."""
    records = _enumerate_process_modules(memory)
    named = [record for record in records if record[1].casefold() == "warcraft iii.exe"]
    ordered = named + [record for record in records if record not in named]
    for base, _name, _path in ordered:
        if _verified_image_header(memory, base):
            return base
    # Preserve the precise profile error for a normally named image whose
    # header is readable but belongs to another build.
    if named:
        return named[0][0]
    raise GameModuleNotFoundError(
        f"Warcraft III module not found; pid={getattr(memory, 'pid', 0)} "
        f"enumerated_modules={_module_summary(records)}"
    )


class ObjectRegistry24268:
    def __init__(self, memory, module_base):
        self.base = module_base
        self.profile = current_profile()
        (self.layout, self.players_layout, self.addresses,
         fingerprint, resolver_bytes, state_check,
         self._handle_layout, self._unit_layout) = self.profile.registry_metadata
        header = _read(memory, module_base, 0x40)
        if header[:2] != b"MZ":
            raise ObjectIdentityError("Game image has no DOS header")
        nt_offset = struct.unpack_from("<I", header, 0x3C)[0]
        if not 0x40 <= nt_offset <= 0x1000:
            raise ObjectIdentityError("Unexpected game PE header offset")
        nt = _read(memory, module_base + nt_offset, 0x58)
        if (nt[:4], struct.unpack_from("<H", nt, 4)[0],
            struct.unpack_from("<I", nt, 8)[0], struct.unpack_from("<I", nt, 0x50)[0]) != (
                b"PE\0\0", *fingerprint):
            raise ObjectIdentityError("Game build has no verified object registry profile")
        self.resolver_code_unreadable = False
        self.state_code_unreadable = False
        try:
            resolver_code = _read(memory, module_base + self.addresses["object_resolver"], len(resolver_bytes))
        except OSError as exc:
            if not self.profile.adapter.components.allows_unreadable_code_check("resolver", exc):
                raise
            resolver_code = None
            self.resolver_code_unreadable = True
        if resolver_code is not None and resolver_code != resolver_bytes:
            raise ObjectIdentityError("Game object resolver code differs from verified profile")
        if resolver_code is not None:
            self.resolver_code_unreadable = False
        # The native's decoder page is not externally readable in this build.
        # Its arithmetic was recovered from the captured shared image section.
        # Verify the readable player accessor in addition to PE + agent code;
        # players() independently validates every resulting object identity.
        rva, code = state_check
        try:
            state_code = _read(memory, module_base + rva, len(code))
        except OSError as exc:
            if not self.profile.adapter.components.allows_unreadable_code_check("game_state", exc):
                raise
            state_code = None
            self.state_code_unreadable = True
        if state_code is not None and state_code != code:
            raise ObjectIdentityError("Game player-array code differs from verified profile")

    @classmethod
    def attach(cls, memory, attempts=8, delay_seconds=0.1):
        """Attach after the visible game window has finished loading its image."""
        last_error = None
        for attempt in range(max(1, int(attempts))):
            try:
                return cls(memory, game_module_base(memory))
            except GameModuleNotFoundError as exc:
                last_error = exc
                if attempt + 1 >= max(1, int(attempts)):
                    raise
                time.sleep(max(0.0, float(delay_seconds)))
        assert last_error is not None
        raise last_error

    def _qword(self, memory, address):
        return struct.unpack("<Q", _read(memory, address, 8))[0]

    def resolve_handle(self, memory, full_handle):
        if not 0 <= full_handle <= 0xFFFFFFFFFFFFFFFF:
            raise ObjectIdentityError("Full object handle is outside uint64")
        low = full_handle & 0xFFFFFFFF
        index = low & 0x7FFFFFFF
        primary, alternate, count_offset, stride, owner_offset, handle_offset = self._handle_layout
        root_address = self.base + self.addresses["registry_root"]
        qword = self._qword
        offset = alternate if low & 0x80000000 else primary
        root = qword(memory, root_address)
        if not _ptr(root):
            raise ObjectIdentityError("Object registry is not initialized")

        table_address = root + offset
        table = _registry_table(memory, table_address, index, count_offset, stride)
        slot_address = table + index * stride
        slot = _read(memory, slot_address, stride)
        marker = struct.unpack_from("<I", slot)[0]
        owner = struct.unpack_from("<Q", slot, owner_offset)[0]
        if marker != 0xFFFFFFFE or not _ptr(owner):
            raise ObjectIdentityError("Object slot is not live")
        if qword(memory, owner + handle_offset) != full_handle:
            raise ObjectIdentityError("Object handle generation changed")
        if (_registry_table(memory, table_address, index, count_offset, stride) != table or _read(memory, slot_address, stride) != slot
                or qword(memory, owner + handle_offset) != full_handle
                or qword(memory, root_address) != root):
            raise ObjectIdentityError("Object registry changed while reading")
        return owner

    def resolve_unit(self, memory, unit):
        if not _ptr(unit):
            raise ObjectIdentityError("Invalid unit pointer")
        qword = self._qword
        object_handle_offset, owner_tag_offset, owner_data_offset, unit_tag, owner_handle_offset = self._unit_layout
        handle = qword(memory, unit + object_handle_offset)
        owner = self.resolve_handle(memory, handle)
        if (qword(memory, owner + owner_tag_offset) != unit_tag
                or qword(memory, owner + owner_data_offset) != unit
                or qword(memory, owner + owner_handle_offset) != handle
                or qword(memory, unit + object_handle_offset) != handle):
            raise ObjectIdentityError("Unit identity changed or mismatches registry")
        return handle, owner

    def players(self, memory):
        """Read the actual game-state player array; this does not pick a local player."""
        slot = self.base + self.addresses["game_state"]
        encoded = self._qword(memory, slot)
        state = decode_game_state(encoded, self.profile)
        if not _ptr(state):
            raise ObjectIdentityError("Game state pointer is invalid")
        count_raw = _read(memory, state + self.players_layout["count"], 4)
        count = struct.unpack("<I", count_raw)[0]
        if not 0 < count <= self.players_layout["max_count"]:
            raise ObjectIdentityError("Game state player count is invalid")
        raw = _read(memory, state + self.players_layout["array"], count * 8)
        players = struct.unpack(f"<{count}Q", raw)
        if len(set(players)) != count or any(not _ptr(player) for player in players):
            raise ObjectIdentityError("Player array contains duplicate or invalid pointers")
        for player in players:
            full = self._qword(memory, player + self.layout["object_handle"])
            owner = self.resolve_handle(memory, full)
            if (self._qword(memory, owner + self.layout["owner_tag"]) != self.layout["player_tag"]
                    or self._qword(memory, owner + self.layout["owner_data"]) != player
                    or self._qword(memory, player + self.layout["object_handle"]) != full):
                raise ObjectIdentityError("Player identity mismatches registry")
        if (_read(memory, state + self.players_layout["array"], len(raw)) != raw
                or _read(memory, state + self.players_layout["count"], 4) != count_raw
                or self._qword(memory, slot) != encoded):
            raise ObjectIdentityError("Player array changed while reading")
        return list(players)

    def local_player_for_mode(self, memory, mode):
        """Mirror GetLocalPlayer's exact predicate, including alternate mode."""
        encoded = self._qword(memory, self.base + self.addresses["game_state"])
        state = decode_game_state(encoded, self.profile)
        players = self.players(memory)
        index_address = state + (self.players_layout["alternate_index"] if mode == 1 else self.players_layout["normal_index"])
        raw = _read(memory, index_address, 2)
        index = struct.unpack("<H", raw)[0]
        if index >= len(players):
            raise ObjectIdentityError("Current game mode has no valid local player")
        if (self._qword(memory, self.base + self.addresses["game_state"]) != encoded
                or _read(memory, index_address, 2) != raw
                or self._qword(memory, state + self.players_layout["array"] + index * 8) != players[index]):
            raise ObjectIdentityError("Local player changed while reading")
        return players[index]
