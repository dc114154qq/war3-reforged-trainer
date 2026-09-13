"""Trace an NtOpenFile hook in emulator memory; stop before every syscall."""
import argparse
import collections
import ctypes
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "analysis/native-bootstrap-20260907/_deps")]
import capstone
from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_64, UC_HOOK_MEM_UNMAPPED, UC_HOOK_CODE
from unicorn.x86_const import *
from war3_reforged_trainer import ProcessMemory, find_war3
from war3_object_registry import ObjectRegistry24268
from war3_thread_context import GameThreadContext24268


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pid", type=int)
    parser.add_argument("filename")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    uc = Uc(UC_ARCH_X86, UC_MODE_64)
    stack, data, stop = 0x700000000, 0x710000000, 0x720000000
    for address, size in ((stack, 0x40000), (data, 0x10000), (stop, 0x1000)):
        uc.mem_map(address, size)
    rsp = stack + 0x30000 - 8
    uc.mem_write(rsp, struct.pack("<Q", stop))
    uc.mem_write(rsp + 0x28, struct.pack("<QQ", 7, 0x60))
    filename = ("\\??\\" + str(Path(args.filename).resolve())).encode("utf-16le")
    uc.mem_write(data + 0x400, filename + b"\0\0")
    uc.mem_write(data + 0x200, struct.pack("<HHIQ", len(filename), len(filename) + 2, 0, data + 0x400))
    uc.mem_write(data + 0x100, struct.pack("<IIQQIIQQ", 48, 0, 0, data + 0x200, 0x40, 0, 0, 0))
    for reg, value in ((UC_X86_REG_RSP, rsp), (UC_X86_REG_RCX, data), (UC_X86_REG_RDX, 0x100020),
                       (UC_X86_REG_R8, data + 0x100), (UC_X86_REG_R9, data + 0x20)):
        uc.reg_write(reg, value)
    trace, calls, reason, pages = collections.deque(maxlen=20), [], [], set()
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    with ProcessMemory(args.pid) as memory:
        registry = ObjectRegistry24268.attach(memory)
        hwnd, _ = find_war3(args.pid)
        context = GameThreadContext24268(memory, registry.base, hwnd, args.pid)
        uc.reg_write(UC_X86_REG_GS_BASE, context.teb)
        # System DLL address is verified against the remote image before use.
        local_nt = ctypes.WinDLL("ntdll")
        address = ctypes.cast(local_nt.NtOpenFile, ctypes.c_void_p).value
        branch = memory.read(address, 5)
        if branch[0] != 0xE9:
            raise RuntimeError("NtOpenFile has no expected observed jump")
        entry = address + 5 + struct.unpack_from("<i", branch, 1)[0]
        if memory.read(entry, 6) == b"\xff\x25\0\0\0\0":
            entry = memory.read_u64(entry + 6)

        def unmapped(uc, access, address, size, value, user):
            page = address & ~4095
            if not 0x10000 <= page < 0x800000000000:
                reason.append(f"invalid emulated address {address:#x}")
                return False
            try:
                blob = memory.read(page, 4096)
                uc.mem_map(page, 4096)
                uc.mem_write(page, blob)
                pages.add(page)
                return True
            except OSError as exc:
                reason.append(f"snapshot page {page:#x}: {exc}")
                return False

        def instruction(uc, address, size, user):
            trace.append(address)
            raw = bytes(uc.mem_read(address, size))
            if raw[:2] in (b"\x0f\x05", b"\x0f\x34") or raw[:1] in (b"\xcd", b"\xcc"):
                reason.append(f"stopped before syscall/interrupt at {address:#x}")
                uc.emu_stop()
                return
            if raw[0] in (0xE8, 0xFF):
                ins = next(md.disasm(raw, address), None)
                if ins and ins.mnemonic == "call":
                    calls.append(dict(address=hex(address), instruction=ins.mnemonic + " " + ins.op_str,
                                      rcx=hex(uc.reg_read(UC_X86_REG_RCX)), rdx=hex(uc.reg_read(UC_X86_REG_RDX)),
                                      r8=hex(uc.reg_read(UC_X86_REG_R8)), r9=hex(uc.reg_read(UC_X86_REG_R9))))

        uc.hook_add(UC_HOOK_MEM_UNMAPPED, unmapped)
        uc.hook_add(UC_HOOK_CODE, instruction)
        try:
            uc.emu_start(entry, stop, timeout=10_000_000, count=250_000)
        except UcError as exc:
            reason.append(str(exc))
        report = dict(pid=args.pid, entry=hex(entry), teb=hex(context.teb), filename=args.filename,
                      scope="Emulated copy only, artificial stack and arguments, no syscall or game write. "
                            "The result is not an observed live file-open return status.",
                      reason=reason, captured_pages=len(pages), calls=calls[-15:],
                      last_addresses=[hex(a) for a in trace],
                      registers={name: hex(uc.reg_read(reg)) for name, reg in (
                          ("rip", UC_X86_REG_RIP), ("rax", UC_X86_REG_RAX), ("rcx", UC_X86_REG_RCX),
                          ("rdx", UC_X86_REG_RDX), ("r8", UC_X86_REG_R8), ("r9", UC_X86_REG_R9))})
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(json.dumps({k: report[k] for k in ("filename", "reason", "registers")} if args.quiet else report, indent=2))


if __name__ == "__main__":
    main()
