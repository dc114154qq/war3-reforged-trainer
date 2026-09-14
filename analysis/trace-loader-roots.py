"""Bounded offline CFG walk. Never loads the DLL or follows an OS import."""
import argparse
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import struct

import capstone
from capstone.x86 import X86_OP_IMM
import pefile


def walk(pe, rva, max_instructions=320):
    base = pe.OPTIONAL_HEADER.ImageBase
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    decoder.detail = True
    pending, seen, rows, calls, stops = deque([rva]), set(), [], set(), []
    ranges = [(e.struct.BeginAddress, e.struct.EndAddress)
              for e in getattr(pe, 'DIRECTORY_ENTRY_EXCEPTION', [])]
    bound = next(((a, b) for a, b in ranges if a <= rva < b), None)
    while pending and len(rows) < max_instructions:
        pc = pending.popleft()
        if pc in seen:
            continue
        seen.add(pc)
        if bound and not bound[0] <= pc < bound[1]:
            stops.append({'rva': hex(pc), 'reason': 'outside_function_range'})
            continue
        section = pe.get_section_by_rva(pc)
        if section is None or not section.Characteristics & 0x20000000:
            stops.append({'rva': hex(pc), 'reason': 'nonexecutable'})
            continue
        ins = next(decoder.disasm(pe.get_data(pc, 15), base + pc, count=1), None)
        if ins is None:
            stops.append({'rva': hex(pc), 'reason': 'decode_failed'})
            continue
        row = {'rva': hex(pc), 'bytes': ins.bytes.hex(),
               'instruction': ins.mnemonic + ' ' + ins.op_str}
        rows.append(row)
        if ins.group(capstone.CS_GRP_RET) or ins.mnemonic in ('int3', 'ud2'):
            stops.append({'rva': hex(pc), 'reason': ins.mnemonic})
            continue
        if ins.group(capstone.CS_GRP_CALL):
            if ins.operands[0].type == X86_OP_IMM:
                target = ins.operands[0].imm - base
                calls.add(target)
                row['direct_call_rva'] = hex(target)
            else:
                row['unresolved_indirect_call'] = True
        if ins.group(capstone.CS_GRP_JUMP):
            if ins.operands[0].type == X86_OP_IMM:
                target = ins.operands[0].imm - base
                pending.append(target)
            else:
                stops.append({'rva': hex(pc), 'reason': 'indirect_branch'})
            if ins.mnemonic == 'jmp':
                continue
        pending.append(pc + ins.size)
    return {'rva': hex(rva), 'range': [hex(x) for x in bound] if bound else None,
            'instruction_count': len(rows), 'budget_exhausted': bool(pending),
            'calls': [hex(x) for x in sorted(calls)], 'stops': stops,
            'instructions': sorted(rows, key=lambda x: int(x['rva'], 16))}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--image', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    data = args.image.read_bytes()
    pe = pefile.PE(data=data)
    roots = {'entry': pe.OPTIONAL_HEADER.AddressOfEntryPoint}
    for export in getattr(pe, 'DIRECTORY_ENTRY_EXPORT', type('E', (), {'symbols': []})).symbols:
        if not export.forwarder:
            roots['export_' + str(export.ordinal)] = export.address
    if hasattr(pe, 'DIRECTORY_ENTRY_TLS'):
        table = pe.DIRECTORY_ENTRY_TLS.struct.AddressOfCallBacks - pe.OPTIONAL_HEADER.ImageBase
        for n in range(32):
            value = struct.unpack('<Q', pe.get_data(table + n * 8, 8))[0]
            if not value:
                break
            roots['tls_' + str(n)] = value - pe.OPTIONAL_HEADER.ImageBase
        else:
            raise ValueError('Unterminated TLS callback table')
    result = {name: walk(pe, rva) for name, rva in roots.items()}
    # Expand only explicitly resolved direct calls / tail targets one level.
    targets = {int(v, 16) for row in result.values() for v in row['calls']}
    targets.update(int(s['rva'], 16) for row in result.values() for s in row['stops']
                   if s['reason'] == 'outside_function_range')
    expanded = {hex(v): walk(pe, v) for v in sorted(targets)}
    report = {'image': str(args.image.resolve()), 'sha256': hashlib.sha256(data).hexdigest(),
              'mode': 'offline_cfg_only', 'calls_executed': False,
              'roots': result, 'direct_targets': expanded}
    tmp = args.output.with_suffix('.tmp')
    tmp.write_text(json.dumps(report, indent=2), encoding='utf-8')
    os.replace(tmp, args.output)
    print(json.dumps({name: {k: v for k, v in row.items() if k != 'instructions'}
                      for name, row in result.items()}))
    print('direct_targets=' + ','.join(expanded))


if __name__ == '__main__':
    main()
