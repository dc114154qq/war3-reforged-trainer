"""Test local SetWindowsHookEx delivery with an inert DLL, then unhook."""

import ctypes as c
import sys
import tempfile
import time
from pathlib import Path

import psutil


P = c.c_void_p
U = c.c_uint32
Z = c.c_size_t
user32 = c.WinDLL("user32", use_last_error=True)
kernel32 = c.WinDLL("kernel32", use_last_error=True)


def api(library, name, restype, *argtypes):
    function = getattr(library, name)
    function.argtypes = argtypes
    function.restype = restype
    return function


enum_windows = api(user32, "EnumWindows", c.c_int, P, P)
window_thread = api(user32, "GetWindowThreadProcessId", U, P, c.POINTER(U))
set_hook = api(user32, "SetWindowsHookExW", P, c.c_int, P, P, U)
unhook = api(user32, "UnhookWindowsHookEx", c.c_int, P)
send = api(user32, "SendMessageTimeoutW", P, P, U, Z, c.c_ssize_t, U, U, c.POINTER(Z))
load = api(kernel32, "LoadLibraryW", P, c.c_wchar_p)
get_proc = api(kernel32, "GetProcAddress", P, P, c.c_char_p)
free = api(kernel32, "FreeLibrary", c.c_int, P)


def main(pid: int, dll: Path, requested_hwnd: int) -> None:
    matches = []
    callback_type = c.WINFUNCTYPE(c.c_int, P, P)

    @callback_type
    def collect(hwnd, _):
        owner = U()
        tid = window_thread(hwnd, c.byref(owner))
        if owner.value == pid and tid:
            matches.append((int(hwnd), int(tid)))
        return 1

    enum_windows(collect, None)
    targets = [(hwnd, tid) for hwnd, tid in matches if hwnd == requested_hwnd]
    if len(targets) != 1:
        raise RuntimeError(f"Target window not found: hwnd=0x{requested_hwnd:x}, windows={matches}")
    hwnd, tid = targets[0]
    module = load(str(dll.resolve()))
    if not module:
        raise c.WinError(c.get_last_error())
    hook = None
    try:
        proc = get_proc(module, b"ProbeHook")
        if not proc:
            raise c.WinError(c.get_last_error())
        hook = set_hook(4, proc, module, tid)
        print(f"pid={pid} hwnd=0x{hwnd:x} tid={tid} hook={hex(hook or 0)} error={c.get_last_error()}")
        if not hook:
            return
        reply = Z()
        nonce = time.time_ns() & 0x7FFFFFFFFFFFFFFF
        marker = Path(tempfile.gettempdir()) / f"war3-hook-probe-{nonce}.txt"
        c.set_last_error(0)
        delivered = send(hwnd, 0x8000 + 0x451, nonce, 0, 2, 1000, c.byref(reply))
        time.sleep(0.1)
        loaded = [entry.path for entry in psutil.Process(pid).memory_maps()
                  if Path(entry.path).name.lower() == dll.name.lower()]
        print(f"probe_delivered={bool(delivered)} send_error={c.get_last_error()} target_module={loaded}")
        print(f"callback_marker={marker.read_text().strip() if marker.is_file() else None}")
    finally:
        if hook:
            print(f"unhooked={bool(unhook(hook))} error={c.get_last_error()}")
        print(f"local_module_released={bool(free(module))}")


if __name__ == "__main__":
    main(int(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3], 0))
