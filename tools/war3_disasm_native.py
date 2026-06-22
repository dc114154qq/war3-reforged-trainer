# -*- coding: utf-8 -*-
"""Read-only disassembly helper for selected Warcraft III native handlers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from war3_reforged_trainer import ProcessMemory, War3Trainer  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("names", nargs="*", default=["GetItemTypeId", "GetUnitTypeId", "UnitAddAbility"])
    parser.add_argument("--bytes", type=lambda value: int(value, 0), default=0x240)
    parser.add_argument("--follow-first-call", action="store_true")
    args = parser.parse_args()

    trainer = War3Trainer()
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    with ProcessMemory(trainer.pid) as pm:
        handlers = trainer._discover_native_handlers(pm, args.names)
        for name in args.names:
            handler = handlers[name].handler_address
            print(f"{name} handler=0x{handler:x}")
            try:
                call_offset = 4 if name in {"GetItemTypeId", "GetUnitTypeId"} else 0x0C
                resolver = trainer._read_rel32_call(pm, handler + call_offset)
                print(f"{name} first_call=0x{resolver:x}")
            except Exception as exc:
                resolver = 0
                print(f"{name} first_call unavailable: {exc}")
            target = resolver if args.follow_first_call and resolver else handler
            print(f"{name} disasm=0x{target:x}")
            code = pm.read(target, min(args.bytes, 0x400))
            for index, ins in enumerate(md.disasm(code, target)):
                if index >= 80:
                    break
                print(f"  {ins.address:x}: {ins.mnemonic:8s} {ins.op_str}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
