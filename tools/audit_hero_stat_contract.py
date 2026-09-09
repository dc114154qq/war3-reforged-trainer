"""Audit hero stat getters/setters in the captured 2.0.4.23745 image offline."""
import argparse
import hashlib
import json
from pathlib import Path

import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from war3_native_bootstrap_audit import IMAGE_SHA256, TEXT_SHA256


FUNCTIONS = {
    'GetHeroStr': 0xc50800, 'GetHeroAgi': 0xc504f0,
    'SetHeroStr': 0xc9bc20, 'SetHeroAgi': 0xc9b8e0,
    'query_strength': 0x116eb40, 'query_agility': 0x116e140,
    'set_strength': 0x116f880, 'set_agility': 0x116f440,
    'adjust_strength_component': 0x6adf10, 'adjust_agility_component': 0x6addd0,
}
REQUIRED = {
    0xc50850: ('jmp', '0x116eb40'), 0xc50540: ('jmp', '0x116e140'),
    0xc9bc70: ('call', '0x116f880'), 0xc9b930: ('call', '0x116f440'),
    0x116eb75: ('mov', 'eax, dword ptr [rbx + 0x188]'),
    0x116ebb3: ('add', 'esi, dword ptr [rbx + 0x108]'),
    0x116ebb9: ('test', 'dil, dil'), 0x116ebbc: ('jne', '0x116ec7a'),
    0x116ec72: ('call', '0x1173140'),
    0x116ec77: ('sub', 'esi, dword ptr [rbp - 0x39]'),
    0x116e175: ('mov', 'eax, dword ptr [rbx + 0x1a8]'),
    0x116e1b3: ('add', 'esi, dword ptr [rbx + 0x130]'),
    0x116e1b9: ('test', 'dil, dil'), 0x116e1bc: ('jne', '0x116e27a'),
    0x116e272: ('call', '0x1173140'),
    0x116e277: ('sub', 'esi, dword ptr [rbp - 0x35]'),
    0x116f9bb: ('sub', 'r14d, ebx'), 0x116f9c4: ('call', '0x6adf10'),
    0x116f57b: ('sub', 'r14d, ebx'), 0x116f584: ('call', '0x6addd0'),
    0x6adf19: ('add', 'dword ptr [rcx + 0x108], edx'),
    0x6addda: ('add', 'dword ptr [rcx + 0x130], edx'),
    0x6ade27: ('call', '0x6b10b0'), 0x6ade4c: ('call', '0x6b18c0'),
    0x6ae066: ('call', '0x115e630'),
}


def audit(image_path, text_path):
    image = image_path.read_bytes()
    text = text_path.read_bytes()
    if hashlib.sha256(image).hexdigest() != IMAGE_SHA256 or hashlib.sha256(text).hexdigest() != TEXT_SHA256:
        raise ValueError('Evidence does not match captured 2.0.4.23745')
    pe = pefile.PE(data=image, fast_load=True)
    pe.parse_data_directories(directories=[3])
    bounds = {entry.struct.BeginAddress: entry.struct.EndAddress for entry in pe.DIRECTORY_ENTRY_EXCEPTION}
    decoder = Cs(CS_ARCH_X86, CS_MODE_64)
    rows, instructions = [], {}
    for name, rva in FUNCTIONS.items():
        end = bounds[rva]
        code = text[rva - 4096:end - 4096]
        decoded = list(decoder.disasm(code, rva))
        if sum(i.size for i in decoded) != len(code):
            raise ValueError(f'Incomplete decode: {name}')
        instructions.update({i.address: (i.mnemonic, i.op_str) for i in decoded})
        rows.append(dict(name=name, rva=rva, end_rva=end,
                         sha256=hashlib.sha256(code).hexdigest(), code=code.hex(),
                         instructions=[f'{i.address:#x}: {i.mnemonic} {i.op_str}' for i in decoded]))
    for address, expected in REQUIRED.items():
        actual = instructions.get(address)
        if actual != expected:
            raise ValueError(f'{address:#x}: {actual!r} differs from {expected!r}')
    return dict(verified=True, image_sha256=IMAGE_SHA256, text_sha256=TEXT_SHA256,
                checked_instructions=len(REQUIRED), functions=rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--text', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.image, args.text)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf8')
    print(f"Verified {len(result['functions'])} functions and {result['checked_instructions']} instructions")
