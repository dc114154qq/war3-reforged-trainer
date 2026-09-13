"""Read-only, build-specific loader context inspection; no game code is called."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import sys
import pefile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CONTEXT_RVA = 0x21B6C40
SAMPLE_U32_COUNT = 512
SUPPORTED_LOADER_SHA256 = "e32431e26f58d1201be3f48baed485114227864d8c6b871eae8e9528241ec8e9"

def read_exact(memory, address, size):
    data = memory.read(address, size)
    if len(data) != size:
        raise ValueError(f"Short read at {address:#x}: {len(data)}/{size}")
    return data

def inspect_context(memory, loader_base, game_base, pe):
    header = read_exact(memory, loader_base, 0x40)
    if header[:2] != b"MZ":
        raise ValueError("Loader base does not reference a PE image")
    nt_offset = struct.unpack_from("<I", header, 0x3C)[0]
    if not 0x40 <= nt_offset <= 0x1000:
        raise ValueError("Unexpected PE header offset")
    nt = read_exact(memory, loader_base + nt_offset, 0x58)
    identity = (nt[:4], struct.unpack_from("<H", nt, 4)[0],
                struct.unpack_from("<I", nt, 8)[0],
                struct.unpack_from("<I", nt, 0x50)[0])
    expected = (b"PE\0\0", pe.FILE_HEADER.Machine,
                pe.FILE_HEADER.TimeDateStamp, pe.OPTIONAL_HEADER.SizeOfImage)
    if identity != expected:
        raise ValueError("Live loader PE identity differs from supplied image")
    context = loader_base + CONTEXT_RVA
    raw = read_exact(memory, context, 0x50)
    values = struct.unpack("<10Q", raw)
    if values[1] != loader_base or values[6] != game_base:
        raise ValueError("Context module bases disagree with current process")
    if not game_base < values[7] <= game_base + 0x40000000:
        raise ValueError("Context game range is invalid")
    table = values[4]
    table_rva = table - loader_base
    section = next((s for s in pe.sections
                    if s.VirtualAddress <= table_rva
                    and table_rva + SAMPLE_U32_COUNT * 4 <=
                    s.VirtualAddress + s.Misc_VirtualSize), None)
    if section is None:
        raise ValueError("Sample range is outside loader sections")
    sample = read_exact(memory, table, SAMPLE_U32_COUNT * 4)
    if read_exact(memory, context, len(raw)) != raw:
        raise ValueError("Context changed during capture; discard this sample")
    entries = struct.unpack(f"<{SAMPLE_U32_COUNT}I", sample)
    disk = pe.get_data(table_rva, len(sample))
    return {
        "loader_base": hex(loader_base), "game_base": hex(game_base),
        "context_rva": hex(CONTEXT_RVA), "context": hex(context),
        "context_qwords": {hex(i * 8): hex(v) for i, v in enumerate(values)},
        "table": hex(table), "table_rva": hex(table_rva),
        "table_section": section.Name.rstrip(b"\0").decode("ascii"),
        "context_0x28_raw": hex(values[5]),
        "sample_u32_count": len(entries),
        "sample_sha256": hashlib.sha256(sample).hexdigest(),
        "sample_matches_disk": len(disk) == len(sample) and disk == sample,
        "sample_min": hex(min(entries)), "sample_max": hex(max(entries)),
        "sample_nondecreasing": all(a <= b for a, b in zip(entries, entries[1:])),
        "sample_u32": [hex(v) for v in entries],
        "scope": "Read-only sample; element meaning and count field are unverified. "
                 "No native function or selection API identified or called.",
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pid", type=int)
    parser.add_argument("loader_base", type=lambda x: int(x, 0))
    parser.add_argument("game_base", type=lambda x: int(x, 0))
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from war3_reforged_trainer import ProcessMemory
    image_sha256 = hashlib.sha256(args.image.read_bytes()).hexdigest()
    if image_sha256 != SUPPORTED_LOADER_SHA256:
        raise ValueError("Loader image has no verified context RVA in this probe")
    pe = pefile.PE(str(args.image), fast_load=True)
    with ProcessMemory(args.pid) as memory:
        report = inspect_context(memory, args.loader_base, args.game_base, pe)
    report.update(pid=args.pid, captured_utc=datetime.now(timezone.utc).isoformat(),
                  loader_file_sha256=image_sha256)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "sample_u32"}, indent=2))

if __name__ == "__main__":
    main()
