"""Recover stack-constructed native registrations in an isolated x64 emulator.

Inputs are offline files. Only a fixed, audited build is accepted. The emulator
has synthetic memory; native handlers are recorded, never executed. Unknown
calls, unmapped access and instruction limits reject the candidate function.
Requires capstone, pefile and unicorn. Does not belong to the runtime trainer.
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
import hashlib
import json
from pathlib import Path
import struct
import sys

import pefile
from unicorn import (Uc, UcError, UC_ARCH_X86, UC_MODE_64, UC_HOOK_CODE,
                     UC_PROT_READ, UC_PROT_WRITE, UC_PROT_EXEC)
from unicorn.x86_const import (
    UC_X86_REG_RAX, UC_X86_REG_RCX, UC_X86_REG_RDX, UC_X86_REG_R8,
    UC_X86_REG_R9, UC_X86_REG_RSP, UC_X86_REG_RIP,
)

from war3_native_bootstrap_audit import IMAGE_SHA256, TEXT_SHA256


BASE = 0x140000000
STACK = 0x700000000
GETTER = 0x9DC100
WRAPPER = 0xA15A50
DISPATCH = 0x135F4B0
ROOT = BASE + 0x2AA2A70


def extract(image_path: Path, text_path: Path) -> dict:
    image = image_path.read_bytes()
    code = text_path.read_bytes()
    if (hashlib.sha256(image).hexdigest() != IMAGE_SHA256
            or hashlib.sha256(code).hexdigest() != TEXT_SHA256):
        raise ValueError("Inputs differ from audited evidence")
    pe = pefile.PE(data=image, fast_load=True)
    directory = pe.OPTIONAL_HEADER.DATA_DIRECTORY[3]
    functions = list(struct.iter_unpack("<III", pe.get_data(directory.VirtualAddress, directory.Size)))
    starts = [a for a, _, _ in functions]
    candidates = set()
    cursor = -1
    while True:
        cursor = code.find(b"\xe8", cursor+1)
        if cursor < 0 or cursor+5 > len(code):
            break
        call = cursor + 0x1000
        if call+5+struct.unpack_from("<i", code, cursor+1)[0] != GETTER:
            continue
        index = bisect_right(starts, call)-1
        if index >= 0 and functions[index][0] <= call < functions[index][1]:
            begin, end, _ = functions[index]
            # Real native registration functions; excludes placeholder registrar.
            if 0xA20000 <= begin < 0xC40000 or 0x1F40000 <= begin < 0x1FA0000:
                candidates.add((begin, end))

    results, rejected, conflicts = {}, [], {}
    uc = Uc(UC_ARCH_X86, UC_MODE_64)
    code_size = (len(code)+0xFFF) & ~0xFFF
    uc.mem_map(BASE+0x1000, code_size)
    uc.mem_write(BASE+0x1000, code)
    uc.mem_protect(BASE+0x1000, code_size, UC_PROT_READ | UC_PROT_EXEC)
    uc.mem_map(STACK, 0x10000, UC_PROT_READ | UC_PROT_WRITE)
    uc.mem_map(BASE+0x2AEA000, 0x1000, UC_PROT_READ)  # synthetic security cookie
    uc.reg_write(UC_X86_REG_RSP, STACK+0x8000)
    initial_cpu = uc.context_save()
    for begin, end in sorted(candidates):
        # Reset all writable memory and CPU; the shared code is immutable.
        uc.context_restore(initial_cpu)
        uc.mem_write(STACK, bytes(0x10000))
        found = []
        error = []

        def string_at(address):
            if not STACK <= address < STACK+0x10000-256:
                raise ValueError("Registration string is not in the synthetic stack")
            raw = bytes(uc.mem_read(address, 256))
            if b"\0" not in raw:
                raise ValueError("Unterminated registration string")
            return raw.split(b"\0", 1)[0].decode("ascii")

        def on_instruction(uc, address, size, _):
            rva = address-BASE
            if not (begin <= rva < end or WRAPPER <= rva < 0xA15B5D):
                error.append(f"Control flow escaped candidate: {rva:#x}")
                uc.emu_stop()
                return
            opcode = bytes(uc.mem_read(address, size))
            if opcode[0] != 0xE8:
                return
            target = rva+5+struct.unpack_from("<i", opcode, 1)[0]
            if target == GETTER:
                uc.reg_write(UC_X86_REG_RAX, ROOT)
                uc.reg_write(UC_X86_REG_RIP, address+size)
            elif target == WRAPPER:
                pass  # execute the verified wrapper's real branches in the emulator
            elif target == DISPATCH:
                try:
                    if uc.reg_read(UC_X86_REG_RCX) != ROOT:
                        raise ValueError("Wrong registration receiver")
                    handler = uc.reg_read(UC_X86_REG_RDX)-BASE
                    if not 0x1000 <= handler < 0x1000+len(code):
                        raise ValueError("Handler outside captured .text")
                    name = string_at(uc.reg_read(UC_X86_REG_R8))
                    signature = string_at(uc.reg_read(UC_X86_REG_R9))
                    if not name.isidentifier() or not signature.startswith("(") or ")" not in signature:
                        raise ValueError("Invalid name/signature")
                    found.append((name, {"handler_rva": hex(handler), "signature": signature,
                                         "registration_function_rva": hex(begin)}))
                except (ValueError, UcError) as exc:
                    error.append(str(exc))
                uc.emu_stop()  # stop before invoking backend or handler
            else:
                error.append(f"Unknown call {target:#x} at {rva:#x}")
                uc.emu_stop()

        hook = uc.hook_add(UC_HOOK_CODE, on_instruction)
        try:
            uc.emu_start(BASE+begin, BASE+end, timeout=1000000, count=20000)
        except UcError as exc:
            error.append(str(exc))
        finally:
            uc.hook_del(hook)
        if error or len(found) != 1:
            rejected.append({"function_rva": hex(begin), "reason": error or ["No registration before limit/end"]})
        else:
            name, record = found[0]
            if name in conflicts:
                conflicts[name].append(record)
            elif name in results:
                previous = results[name]
                if (previous["handler_rva"], previous["signature"]) == (record["handler_rva"], record["signature"]):
                    previous.setdefault("additional_registration_functions", []).append(hex(begin))
                else:
                    conflicts[name] = [results.pop(name), record]
            else:
                results[name] = record

    return {"status": "offline reconstruction; handlers have not been invoked",
            "image_sha256": IMAGE_SHA256, "captured_text_sha256": TEXT_SHA256,
            "candidate_count": len(candidates), "registrations": dict(sorted(results.items())),
            "conflicts": conflicts, "rejected": rejected}


def audit_trainer_bindings(report: dict, code: bytes) -> dict:
    """Run existing Python resolver discovery against files, never ProcessMemory."""
    if hashlib.sha256(code).hexdigest() != TEXT_SHA256:
        raise ValueError("Unexpected captured text")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import war3_reforged_trainer as trainer_module

    class OfflineMemory:
        def read(self, address, size):
            offset = address-0x1000
            if offset < 0 or offset+size > len(code):
                raise OSError("Read outside captured text")
            return code[offset:offset+size]

        def regions(self):
            return [trainer_module.Region(0x1000, len(code),
                                          trainer_module.PAGE_EXECUTE_READ, trainer_module.MEM_IMAGE)]

    trainer = trainer_module.War3Trainer.__new__(trainer_module.War3Trainer)
    memory = OfflineMemory()
    registrations = report["registrations"]
    missing = set(trainer.PERSISTENT_NATIVE_NAMES)-registrations.keys()
    if missing:
        raise ValueError(f"Persistent native coverage incomplete: {sorted(missing)}")
    address = lambda name: int(registrations[name]["handler_rva"], 16)
    unit = trainer._native_function_calls(memory, address("UnitAddAbility"))[0]
    item = trainer._native_function_calls(memory, address("GetItemTypeId"))[0]
    agent = trainer._discover_agent_resolver(memory, address("GetUnitState"))
    if (unit, item, agent) != (0xA110B0, 0xA0DFF0, 0x31F430):
        raise ValueError("Current source no longer derives the audited resolver chain")
    return {"persistent_native_count": len(trainer.PERSISTENT_NATIVE_NAMES),
            "unit_resolver_rva": hex(unit), "item_resolver_rva": hex(item),
            "agent_resolver_rva": hex(agent), "game_process_accessed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--text", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit-trainer-bindings", action="store_true",
                        help="Also verify current trainer resolver discovery offline (Windows)")
    args = parser.parse_args()
    result = extract(args.image, args.text)
    if args.audit_trainer_bindings:
        result["source_binding_audit"] = audit_trainer_bindings(result, args.text.read_bytes())
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"Recovered {len(result['registrations'])}/{result['candidate_count']} registrations; "
          f"rejected {len(result['rejected'])}, conflicting names {len(result['conflicts'])}. Report: {args.output}")


if __name__ == "__main__":
    main()
