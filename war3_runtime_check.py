"""Offline verification executed by the packaged trainer, without a game hook."""

import ctypes
import hashlib
import json
from pathlib import Path
import sys
import traceback


def run(output_path):
    report = {"ok": False, "frozen": bool(getattr(sys, "frozen", False))}
    try:
        import capstone

        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        decoder = Path(capstone._cs._name).resolve()
        report["decoder"] = str(decoder)
        report["decoder_sha256"] = hashlib.sha256(decoder.read_bytes()).hexdigest()
        if report["frozen"] and not decoder.is_relative_to(base.resolve()):
            raise RuntimeError("Decoder was loaded from outside the executable bundle")
        # C3 inside a mov instruction is not a return; E8 inside an immediate
        # is not a call. Both caused false instruction boundaries previously.
        code = bytes.fromhex("448bc3b8e8000000e803000000c3")
        decoded = list(capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64).disasm(code, 0x1000))
        if [ins.mnemonic for ins in decoded] != ["mov", "mov", "call", "ret"]:
            raise RuntimeError("Decoder instruction-boundary check failed")
        report["instructions"] = [ins.mnemonic for ins in decoded]
        helper = base / "tools" / "war3_native_helper.dll"
        library = ctypes.WinDLL(str(helper))
        getattr(library, "War3HookProc")
        report["helper_sha256"] = hashlib.sha256(helper.read_bytes()).hexdigest()
        report["ok"] = True
    except Exception:
        report["error"] = traceback.format_exc()
    Path(output_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1
