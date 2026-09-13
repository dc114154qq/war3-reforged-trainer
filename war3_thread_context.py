"""Read the game's frame-scoped TLS context without entering the game thread."""
import ctypes
from dataclasses import dataclass
import struct
import time

from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_MEM, X86_OP_REG, X86_REG_GS, X86_REG_RCX
from war3_object_registry import ObjectIdentityError, _ptr, _read

TLS_INDEX_RVA = 0x2F5B528
CONTEXT_CODE_CHECKS = (
    (0x1838FD, bytes.fromhex("8b0d257cdd02e8d86dcf01")),
    (0x18395E, bytes.fromhex("4885c9740b488b44d9104883c4205bc333c04883c4205bc3")),
    (0x152A690, bytes.fromhex("4883ec28b90d000000e81292c5fe488b4020488b88b800000083b9e8300000010f94c04883c428c3")),
)


def infer_tls_layout(code):
    """Recognize direct-GS and TEB-base forms of x64 Windows TlsGetValue.

    Derive offsets from this OS's function instead of fixing a TEB layout in
    the game profile. Reject missing/ambiguous forms; there is no region scan.
    """
    decoder = Cs(CS_ARCH_X86, CS_MODE_64)
    decoder.detail = True
    primary, expansion, teb_registers = set(), set(), set()
    for ins in decoder.disasm(code, 0):
        if len(ins.operands) != 2 or ins.operands[1].type != X86_OP_MEM:
            continue
        mem = ins.operands[1].mem
        direct = mem.segment == X86_REG_GS and mem.base == 0
        indirect = mem.base in teb_registers and mem.segment == 0
        if direct and not mem.index and mem.disp == 0x30 and ins.operands[0].type == X86_OP_REG:
            teb_registers.add(ins.operands[0].reg)
        if not (direct or indirect) or not 0x1000 <= mem.disp <= 0x4000:
            continue
        if mem.index == X86_REG_RCX and mem.scale == 8:
            primary.add(mem.disp)
        elif not mem.index:
            expansion.add(mem.disp)
    if len(primary) != 1 or len(expansion) != 1:
        raise ObjectIdentityError("Windows TLS accessor layout is not recognized")
    return next(iter(primary)), next(iter(expansion))


@dataclass(frozen=True)
class LocalPlayerMode:
    value: int
    thread_id: int
    teb: int
    tls_index: int
    tls: int
    context: int
    mode_object: int
    attempts: int
    elapsed_ms: float


class GameThreadContext24268:
    def __init__(self, memory, game_base, hwnd, pid):
        self.base, self.hwnd, self.pid = game_base, hwnd, pid
        for rva, code in CONTEXT_CODE_CHECKS:
            if _read(memory, game_base + rva, len(code)) != code:
                raise ObjectIdentityError("Game context accessor differs from verified profile")
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.user.GetWindowThreadProcessId.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong))
        self.user.GetWindowThreadProcessId.restype = ctypes.c_ulong
        self.kernel.OpenThread.argtypes = (ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong)
        self.kernel.OpenThread.restype = ctypes.c_void_p
        self.kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
        self.kernel.CloseHandle.restype = ctypes.c_int
        self.tid = self._window_thread()
        thread = self.kernel.OpenThread(0x40, False, self.tid)
        if not thread:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            query = ctypes.WinDLL("ntdll").NtQueryInformationThread
            query.argtypes = (ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p)
            query.restype = ctypes.c_long
            basic = (ctypes.c_ulonglong * 6)()
            status = query(thread, 0, ctypes.byref(basic), ctypes.sizeof(basic), None)
            if status < 0 or (basic[2], basic[3]) != (pid, self.tid) or not _ptr(basic[1]):
                raise ObjectIdentityError("Game window thread identity query failed")
            self.teb = basic[1]
        finally:
            self.kernel.CloseHandle(thread)
        # Use the current OS implementation. KernelBase also exports the
        # implementation on systems where Kernel32 starts with a forwarder.
        errors = []
        for dll in (self.kernel, ctypes.WinDLL("kernelbase")):
            address = ctypes.cast(dll.TlsGetValue, ctypes.c_void_p).value
            try:
                self.primary_offset, self.expansion_offset = infer_tls_layout(ctypes.string_at(address, 128))
                break
            except ObjectIdentityError as exc:
                errors.append(str(exc))
        else:
            raise ObjectIdentityError("; ".join(errors))

    def _window_thread(self):
        owner = ctypes.c_ulong()
        tid = self.user.GetWindowThreadProcessId(self.hwnd, ctypes.byref(owner))
        if not tid or owner.value != self.pid:
            raise ObjectIdentityError("Game window belongs to a different process")
        return int(tid)

    @staticmethod
    def _qword(memory, address):
        return struct.unpack("<Q", _read(memory, address, 8))[0]

    def sample_mode(self, memory):
        """Return None for an inactive/changed frame; never choose a player by guess."""
        index = struct.unpack("<I", _read(memory, self.base + TLS_INDEX_RVA, 4))[0]
        if index >= 1088:
            raise ObjectIdentityError("Game TLS index is outside Windows TLS bounds")
        expansion = 0
        if index < 64:
            slot = self.teb + self.primary_offset + index * 8
        else:
            expansion = self._qword(memory, self.teb + self.expansion_offset)
            if not expansion:
                return None
            if not _ptr(expansion):
                raise ObjectIdentityError("Invalid TLS expansion pointer")
            slot = expansion + (index - 64) * 8
        tls = self._qword(memory, slot)
        if not tls:
            return None
        if not _ptr(tls):
            raise ObjectIdentityError("Invalid game TLS context")
        context = self._qword(memory, tls + 0x78)
        if not _ptr(context):
            return None
        bridge = self._qword(memory, context + 0x20)
        if not _ptr(bridge):
            return None
        mode_object = self._qword(memory, bridge + 0xB8)
        if not _ptr(mode_object):
            return None
        value = struct.unpack("<I", _read(memory, mode_object + 0x30E8, 4))[0]
        if (self._qword(memory, bridge + 0xB8) != mode_object
                or struct.unpack("<I", _read(memory, mode_object + 0x30E8, 4))[0] != value
                or self._qword(memory, context + 0x20) != bridge
                or self._qword(memory, tls + 0x78) != context
                or self._qword(memory, slot) != tls
                or struct.unpack("<I", _read(memory, self.base + TLS_INDEX_RVA, 4))[0] != index
                or (index >= 64 and self._qword(memory, self.teb + self.expansion_offset) != expansion)):
            return None
        return value, index, tls, context, mode_object

    def read_mode(self, memory, timeout_ms=250):
        if self._window_thread() != self.tid:
            raise ObjectIdentityError("Game window thread changed; reconnect required")
        start = time.perf_counter()
        attempts = 0
        last_read_error = None
        while True:
            attempts += 1
            try:
                result = self.sample_mode(memory)
            except OSError as exc:
                if getattr(exc, "winerror", None) not in (299, 487):
                    raise
                # A frame context may retire between two remote reads. Retry
                # the whole sample; preserve the cause if the deadline expires.
                last_read_error = exc
                result = None
            elapsed = (time.perf_counter() - start) * 1000
            if result is not None:
                value, index, tls, context, mode_object = result
                return LocalPlayerMode(value, self.tid, self.teb, index, tls, context,
                                       mode_object, attempts, elapsed)
            if elapsed >= timeout_ms:
                raise ObjectIdentityError(
                    f"Game frame context inactive after {elapsed:.1f} ms ({attempts} attempts)"
                ) from last_read_error
            time.sleep(min(0.001, (timeout_ms - elapsed) / 1000))
