import argparse
import ctypes
import struct
import time
from dataclasses import dataclass


PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
MEM_COMMIT = 0x1000
PAGE_NOACCESS = 0x01
PAGE_GUARD = 0x100
READABLE_PROTECTS = {0x02, 0x04, 0x08, 0x20, 0x40, 0x80}


class MEMORY_BASIC_INFORMATION64(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_ulonglong),
        ("AllocationBase", ctypes.c_ulonglong),
        ("AllocationProtect", ctypes.c_ulong),
        ("__alignment1", ctypes.c_ulong),
        ("RegionSize", ctypes.c_ulonglong),
        ("State", ctypes.c_ulong),
        ("Protect", ctypes.c_ulong),
        ("Type", ctypes.c_ulong),
        ("__alignment2", ctypes.c_ulong),
    ]


@dataclass(frozen=True)
class Region:
    base: int
    size: int
    protect: int
    type: int


class ProcessMemory:
    def __init__(self, pid: int, write: bool = False):
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        access = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
        if write:
            access |= PROCESS_VM_WRITE | PROCESS_VM_OPERATION
        self.handle = self.kernel32.OpenProcess(access, False, pid)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())

    def regions(self):
        mbi = MEMORY_BASIC_INFORMATION64()
        addr = 0
        max_addr = 0x7FFFFFFFFFFF
        out = []
        while addr < max_addr:
            res = self.kernel32.VirtualQueryEx(
                self.handle, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)
            )
            if not res:
                break
            prot = mbi.Protect & 0xFF
            if (
                mbi.State == MEM_COMMIT
                and not (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD))
                and prot in READABLE_PROTECTS
            ):
                out.append(Region(mbi.BaseAddress, mbi.RegionSize, mbi.Protect, mbi.Type))
            addr = mbi.BaseAddress + mbi.RegionSize
        return out

    def read(self, address: int, size: int) -> bytes:
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t()
        ok = self.kernel32.ReadProcessMemory(
            self.handle, ctypes.c_void_p(address), buf, size, ctypes.byref(got)
        )
        if not ok:
            raise ctypes.WinError(ctypes.get_last_error())
        return buf.raw[: got.value]

    def write_i32(self, address: int, value: int):
        data = struct.pack("<i", value)
        written = ctypes.c_size_t()
        ok = self.kernel32.WriteProcessMemory(
            self.handle, ctypes.c_void_p(address), data, len(data), ctypes.byref(written)
        )
        if not ok or written.value != len(data):
            raise ctypes.WinError(ctypes.get_last_error())

    def write_f32(self, address: int, value: float):
        data = struct.pack("<f", value)
        written = ctypes.c_size_t()
        ok = self.kernel32.WriteProcessMemory(
            self.handle, ctypes.c_void_p(address), data, len(data), ctypes.byref(written)
        )
        if not ok or written.value != len(data):
            raise ctypes.WinError(ctypes.get_last_error())

    def scan_i32(self, value: int, max_region_size: int = 256 * 1024 * 1024):
        pat = struct.pack("<i", value)
        return self.scan_bytes(pat, max_region_size)

    def scan_f32(self, value: float, max_region_size: int = 256 * 1024 * 1024):
        pat = struct.pack("<f", value)
        return self.scan_bytes(pat, max_region_size)

    def scan_f64(self, value: float, max_region_size: int = 256 * 1024 * 1024):
        pat = struct.pack("<d", value)
        return self.scan_bytes(pat, max_region_size)

    def scan_bytes(self, pattern: bytes, max_region_size: int = 256 * 1024 * 1024):
        hits = []
        tail_len = max(0, len(pattern) - 1)
        for region in self.regions():
            if region.size > max_region_size:
                continue
            offset = 0
            tail = b""
            while offset < region.size:
                size = min(4 * 1024 * 1024, region.size - offset)
                try:
                    data = tail + self.read(region.base + offset, size)
                except OSError:
                    offset += size
                    tail = b""
                    continue
                start = 0
                while True:
                    idx = data.find(pattern, start)
                    if idx < 0:
                        break
                    address = region.base + offset - len(tail) + idx
                    if address >= region.base:
                        hits.append((address, region.protect, region.type))
                    start = idx + 1
                tail = data[-tail_len:] if tail_len else b""
                offset += size
        return hits


def dump_context(pm: ProcessMemory, address: int, radius: int = 96):
    start = address - radius
    data = pm.read(start, radius * 2 + 4)
    rows = []
    for rel in range(0, len(data) - 3, 4):
        value = struct.unpack_from("<i", data, rel)[0]
        rows.append((start + rel, value))
    return rows


def send_text_to_window(pid: int, text: str):
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    SW_RESTORE = 9
    KEYEVENTF_KEYUP = 0x0002

    hwnd = None

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def enum_proc(candidate, _):
        nonlocal hwnd
        proc_id = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(candidate, ctypes.byref(proc_id))
        if proc_id.value == pid and user32.IsWindowVisible(candidate):
            hwnd = candidate
            return False
        return True

    user32.EnumWindows(enum_proc, None)
    if not hwnd:
        raise RuntimeError(f"No visible top-level window for pid {pid}")
    user32.ShowWindow(hwnd, SW_RESTORE)
    time.sleep(0.2)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.4)

    def press_vk(vk: int):
        user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.025)
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.025)

    press_vk(0x0D)
    for ch in text:
        vk_scan = user32.VkKeyScanW(ord(ch))
        if vk_scan == -1:
            continue
        vk = vk_scan & 0xFF
        shift_state = (vk_scan >> 8) & 0xFF
        if shift_state & 1:
            user32.keybd_event(0x10, 0, 0, 0)
        press_vk(vk)
        if shift_state & 1:
            user32.keybd_event(0x10, 0, KEYEVENTF_KEYUP, 0)
    press_vk(0x0D)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pid", type=int)
    parser.add_argument("value", type=int)
    parser.add_argument("--contexts", type=int, default=40)
    parser.add_argument("--send-cheat", help="Send text between Enter key presses before scanning.")
    args = parser.parse_args()

    if args.send_cheat:
        send_text_to_window(args.pid, args.send_cheat)
        time.sleep(1)

    pm = ProcessMemory(args.pid)
    hits = pm.scan_i32(args.value)
    print(f"hits={len(hits)}")
    for address, protect, typ in hits[: args.contexts]:
        print(f"\n@ {address:#x} protect={protect:#x} type={typ:#x}")
        rows = dump_context(pm, address)
        for row_addr, value in rows:
            mark = "*" if row_addr == address else " "
            print(f"{mark} {row_addr:#018x} {value:12d} {value & 0xFFFFFFFF:08x}")


if __name__ == "__main__":
    main()
