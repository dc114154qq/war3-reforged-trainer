"""Distinguish hook delivery from game command execution. No game functions are called."""
import argparse
import ctypes as c
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from war3_reforged_trainer import ProcessMemory, find_war3

k = c.WinDLL("kernel32", use_last_error=True)
u = c.WinDLL("user32", use_last_error=True)
P, U, Z = c.c_void_p, c.c_ulong, c.c_size_t


def api(lib, name, restype, *args):
    fn = getattr(lib, name)
    fn.argtypes, fn.restype = args, restype
    return fn


create_mapping = api(k, "CreateFileMappingW", P, P, P, U, U, U, c.c_wchar_p)
map_view = api(k, "MapViewOfFile", P, P, U, U, U, Z)
unmap = api(k, "UnmapViewOfFile", c.c_int, P)
close = api(k, "CloseHandle", c.c_int, P)
load = api(k, "LoadLibraryW", P, c.c_wchar_p)
free = api(k, "FreeLibrary", c.c_int, P)
symbol = api(k, "GetProcAddress", P, P, c.c_char_p)
hook = api(u, "SetWindowsHookExW", P, c.c_int, P, P, U)
unhook = api(u, "UnhookWindowsHookEx", c.c_int, P)
post = api(u, "PostMessageW", c.c_int, P, U, Z, c.c_ssize_t)
post_thread = api(u, "PostThreadMessageW", c.c_int, U, U, Z, c.c_ssize_t)
send = api(u, "SendMessageTimeoutW", Z, P, U, Z, c.c_ssize_t, U, U, c.POINTER(Z))
window_thread = api(u, "GetWindowThreadProcessId", U, P, c.POINTER(U))
mitigation = api(k, "GetProcessMitigationPolicy", c.c_int, P, c.c_int, P, Z)
enum_modules = api(k, "K32EnumProcessModulesEx", c.c_int, P, c.POINTER(P), U, c.POINTER(U), U)
module_name = api(k, "K32GetModuleBaseNameW", U, P, P, c.c_wchar_p, U)
FIELDS = ("magic", "version", "requested_pid", "reserved", "attach_pid", "attach_tid",
          "callback_pid", "callback_tid", "getmessage_count", "callwnd_count", "last_message", "last_error")


def telemetry(address):
    return dict(zip(FIELDS, struct.unpack("<12I", c.string_at(address, 48))))


def module_base(memory, name):
    modules, needed = (P * 1024)(), U()
    if not enum_modules(memory.handle, modules, c.sizeof(modules), c.byref(needed), 2):
        raise c.WinError(c.get_last_error())
    if needed.value > c.sizeof(modules):
        raise RuntimeError("Module list exceeded probe capacity")
    for value in modules[:needed.value // c.sizeof(P)]:
        buffer = c.create_unicode_buffer(1024)
        if module_name(memory.handle, value, buffer, len(buffer)) and buffer.value.lower() == name.lower():
            return value
    return None


def inspect(pid, tid, hwnd, dll, duration):
    mapping = view = library = installed = None
    report = dict(pid=pid, tid=tid, hwnd=hex(hwnd), dll_sha256=hashlib.sha256(dll.read_bytes()).hexdigest())
    try:
        c.set_last_error(0)
        mapping = create_mapping(P(-1), None, 4, 0, 4096, f"Local\\War3EngineHookProbe-{pid}")
        if not mapping:
            raise c.WinError(c.get_last_error())
        if c.get_last_error() == 183:
            raise RuntimeError("A probe mapping already exists for this PID")
        view = map_view(mapping, 0xF001F, 0, 0, 4096)
        if not view:
            raise c.WinError(c.get_last_error())
        initial = struct.pack("<12I", 0x24268002, 1, pid, *([0] * 9))
        c.memmove(view, initial, len(initial))
        library = load(str(dll))
        if not library:
            raise c.WinError(c.get_last_error())
        local_state = symbol(library, b"probe_local_state")
        report["local_dll_attach"] = telemetry(local_state)
        export_rva = local_state - library
        report["hooks"] = []
        with ProcessMemory(pid) as memory:
            report["mitigation_flags"] = {}
            for name, policy in (("dynamic_code", 2), ("extension_points", 6), ("cfg", 7), ("signature", 8), ("image_load", 10)):
                flags = U()
                c.set_last_error(0)
                ok = mitigation(memory.handle, policy, c.byref(flags), c.sizeof(flags))
                report["mitigation_flags"][name] = dict(ok=bool(ok), flags=flags.value, error=c.get_last_error())
            for kind, name in ((3, b"ProbeGetMessage"), (4, b"ProbeCallWndProc")):
                proc = symbol(library, name)
                c.set_last_error(0)
                installed = hook(kind, proc, library, tid)
                row = dict(kind=kind, installed=bool(installed), install_error=c.get_last_error())
                report["hooks"].append(row)
                if not installed:
                    continue
                try:
                    deadline = time.monotonic() + duration
                    counter = "getmessage_count" if kind == 3 else "callwnd_count"
                    row["before"] = telemetry(view)
                    while time.monotonic() < deadline:
                        c.set_last_error(0)
                        if kind == 3:
                            ok = post(hwnd, 0, 0, 0)
                        else:
                            reply = Z()
                            ok = send(hwnd, 0, 0, 0, 2, 200, c.byref(reply))
                        row["last_dispatch"] = dict(ok=bool(ok), error=c.get_last_error())
                        time.sleep(0.02)
                        if telemetry(view)[counter] > row["before"][counter]:
                            break
                    row["after"] = telemetry(view)
                    base = module_base(memory, dll.name)
                    row["module_listed_while_hook_installed"] = hex(base) if base else None
                    if base:
                        row["remote_dll_state"] = dict(zip(FIELDS, struct.unpack("<12I", memory.read(base + export_rva, 48))))
                    row["callback_observed"] = row["after"][counter] > row["before"][counter]
                finally:
                    row["unhooked"] = bool(unhook(installed))
                    installed = None
    finally:
        if installed:
            unhook(installed)
        if library:
            free(library)
        if view:
            unmap(view)
        if mapping:
            close(mapping)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--local-host", type=Path)
    mode.add_argument("--pid", type=int)
    parser.add_argument("--dll", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=1.0)
    args = parser.parse_args()
    child = None
    try:
        if args.local_host:
            child = subprocess.Popen([str(args.local_host.resolve())], stdout=subprocess.PIPE,
                                     text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            pid, tid, hwnd = map(int, child.stdout.readline().split())
            assert child.pid == pid
        else:
            hwnd, pid = find_war3(args.pid)
            actual = U()
            tid = window_thread(hwnd, c.byref(actual))
            assert actual.value == pid
        report = inspect(pid, tid, hwnd, args.dll.resolve(), args.duration)
        report.update(captured_utc=datetime.now(timezone.utc).isoformat(),
                      local_host=bool(child), calls_game_functions=False, writes_game_objects=False)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
        print(json.dumps(report, indent=2))
        if child:
            assert all(row["callback_observed"] for row in report["hooks"])
    finally:
        if child:
            post_thread(tid, 0x12, 0, 0)
            child.wait(timeout=5)


if __name__ == "__main__":
    main()
