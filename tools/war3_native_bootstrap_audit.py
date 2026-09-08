"""Audit one captured game build's native registration path, entirely offline.

This is a research verifier, NOT a runtime address profile or native resolver.
It reads a saved .text section and the matching on-disk PE. No process access,
injection, function invocation, or memory scan of a running game is performed.
Addresses below identify evidence in this build, not cross-version constants.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import capstone
import pefile


IMAGE_SHA256 = "682c12552ca05e43c5fed2340ea132d3b06fe068e676db7d1f5623d8d4633229"
TEXT_SHA256 = "0b62fa80e351e996e70addb66c5d3c8a818304ec6aa8dcf5fe6c0886cca4127c"


def audit(image_path: Path, text_path: Path) -> dict:
    image = image_path.read_bytes()
    code = text_path.read_bytes()
    if hashlib.sha256(image).hexdigest() != IMAGE_SHA256:
        raise ValueError("Unsupported image: this audit covers only the recorded build")
    if hashlib.sha256(code).hexdigest() != TEXT_SHA256:
        raise ValueError("Capture differs from recorded evidence; do not reuse its conclusions")
    pe = pefile.PE(data=image, fast_load=True)
    section = next(s for s in pe.sections if s.Name.rstrip(b"\0") == b".text")
    start = section.VirtualAddress
    if len(code) != section.Misc_VirtualSize:
        raise ValueError("Expected exactly the captured virtual .text section")
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True

    def at(rva: int):
        if not start <= rva < start + len(code):
            raise ValueError(f"Instruction outside .text: {rva:#x}")
        return next(md.disasm(code[rva-start:rva-start+15], rva, count=1))

    def expect(rva: int, mnemonic: str, operands: str):
        ins = at(rva)
        if (ins.mnemonic, ins.op_str) != (mnemonic, operands):
            raise ValueError(f"Unexpected instruction at {rva:#x}: {ins.mnemonic} {ins.op_str}")
        return ins

    def rip(rva: int, mnemonic: str, dest: str) -> int:
        ins = at(rva)
        if (ins.mnemonic != mnemonic or len(ins.operands) != 2
                or ins.reg_name(ins.operands[0].reg) != dest
                or ins.operands[1].type != capstone.x86.X86_OP_MEM
                or ins.operands[1].mem.base != capstone.x86.X86_REG_RIP):
            raise ValueError(f"Expected RIP-relative {mnemonic} {dest} at {rva:#x}")
        return ins.address + ins.size + ins.operands[1].mem.disp

    names = {}
    for name, ref in (("GroupEnumUnitsSelected", 0x1FB2072),
                      ("GetUnitState", 0x1FB37E4),
                      ("GetHeroStr", 0x1FB5215),
                      ("UnitAddAbility", 0x1FB7330)):
        expect(ref-15, "call", "0x9dc100")
        signature = rip(ref-10, "lea", "r9")
        expect(ref-3, "mov", "rcx, rax")
        name_rva = rip(ref, "lea", "r8")
        if pe.get_string_at_rva(name_rva) != name.encode("ascii"):
            raise ValueError(f"Name mismatch: {name}")
        handler = rip(ref+7, "lea", "rdx")
        expect(ref+14, "call", "0x1fa6ef0")
        expect(handler, "xor", "eax, eax")
        expect(handler+2, "ret", "")
        names[name] = {"reference_rva": hex(ref), "name_rva": hex(name_rva),
                       "signature": pe.get_string_at_rva(signature).decode("ascii"),
                       "initial_stub_rva": hex(handler)}

    # Prove the getter's branches, rather than linear-decoding unreachable bytes.
    expect(0x9DC111, "jns", "0x9dc160")
    expect(0x9DC113, "sal", "cl, 0")  # preserves SF
    expect(0x9DC116, "js", "0x9dc160")
    expect(0x9DC160, "nop", "")
    expect(0x9DC161, "test", "al, 0xea")  # clears OF
    expect(0x9DC163, "jno", "0x9dc195")
    expect(0x9DC195, "nop", "word ptr [rax + rax]")
    expect(0x9DC1A0, "nop", "")
    expect(0x9DC1A1, "or", "al, 0")  # clears OF, leaves AL unchanged
    expect(0x9DC1A3, "mov", "al, al")
    expect(0x9DC1A5, "jno", "0x9dc1fc")
    root = rip(0x9DC1FC, "lea", "rax")
    expect(0x9DC203, "ret", "")

    # Registration wrapper reaches a two-backend virtual dispatch.
    for addr, mn, op in (
        (0x1FA6F01, "clc", ""), (0x1FA6F02, "sar", "dh, 0"),
        (0x1FA6F05, "jae", "0x1fa6f78"),
        (0x1FA6F78, "call", "0x135f4b0"),
        (0x1FA6F81, "test", "esp, edx"), (0x1FA6F83, "jno", "0x1fa6ff8"),
        (0x1FA6FF8, "add", "rsp, 0x28"), (0x1FA6FFC, "ret", ""),
        (0x135F4CA, "lea", "rbx, [rcx + 8]"),
        (0x135F4D1, "lea", "rdi, [rcx + 0x18]"),
        (0x135F4E0, "mov", "rcx, qword ptr [rbx]"),
        (0x135F4EF, "call", "qword ptr [rax + 0x10]"),
        (0x135F464, "call", "0x135fd70"),
        (0x135F46E, "mov", "qword ptr [rbx + 8], rax"),
    ):
        expect(addr, mn, op)
    vtable = rip(0x135FD7D, "lea", "rax")
    backend = int.from_bytes(pe.get_data(vtable+0x10, 8), "little") - pe.OPTIONAL_HEADER.ImageBase
    if backend != 0x13614A0:
        raise ValueError("Backend vtable changed")
    expect(0x13615FA, "call", "0x15ac140")

    # The lower registration layer obtains context slot 5, looks up its table,
    # and stores the supplied handler/signature in the returned node.
    for addr, mn, op in (
        (0x15AC171, "ja", "0x15ac1c7"), (0x15AC173, "jbe", "0x15ac1c7"),
        (0x15AC1C7, "mov", "ecx, 5"), (0x15AC1CC, "call", "0x30d360"),
        (0x15AC1E0, "lea", "rbp, [rax + 0x28]"),
        (0x15AC1E4, "mov", "rdx, rsi"), (0x15AC1E7, "mov", "rcx, rbp"),
        (0x15AC1EA, "call", "0x15ad560"),
        (0x15AC23D, "mov", "qword ptr [rdi + 0x28], rax"),
        (0x15AC241, "mov", "qword ptr [rdi + 0x30], r15"),
        (0x15AC257, "mov", "qword ptr [rdi + 0x40], rax"),
        (0x15AD57D, "call", "0x2e6940"),
        (0x15AD582, "mov", "r8d, dword ptr [rbx + 0x40]"),
        (0x15AD586, "mov", "rcx, qword ptr [rbx + 0x30]"),
        (0x15AD59E, "mov", "rcx, qword ptr [rbx + 0x10]"),
        (0x15AD5CB, "movsxd", "rax, dword ptr [rbx]"),
        (0x15AD5CE, "mov", "r10, qword ptr [rax + r8 + 8]"),
        (0x15AD5D8, "mov", "rax, qword ptr [r8 + 0x28]"),
        (0x15AD5FE, "mov", "rax, r8"),
        (0x30D3CE, "mov", "rax, qword ptr [rax + rbx*8 + 0x38]"),
    ):
        expect(addr, mn, op)

    return {
        "status": "offline evidence only; not validated for runtime address use",
        "image_sha256": IMAGE_SHA256, "captured_text_sha256": TEXT_SHA256,
        "registrations": names,
        "dispatcher_root_rva": hex(root), "first_backend_vtable_rva": hex(vtable),
        "first_backend_register_rva": hex(backend),
        "context_getter_rva": "0x30d360", "context_slot": 5,
        "context_table_offset": "0x28", "table_find_rva": "0x15ad560",
        "node_name_offset": "0x28", "node_handler_offset": "0x30",
        "node_signature_offset": "0x40",
        "unproven": [
            "Imported context accessor is not identified from the saved text section.",
            "Current map context and real (non-stub) native values require a read-only game-thread probe.",
            "JASS table handlers must be compared with current handler ABI before replacing the old route.",
            "No evidence yet supports other game builds or process states.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--text", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.image, args.text)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"Verified offline registration path; report: {args.output}")


if __name__ == "__main__":
    main()
