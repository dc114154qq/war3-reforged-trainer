"""Reproduce buff ABI evidence from the pinned disk image and runtime text."""
import argparse
import hashlib
import json
from pathlib import Path

import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from war3_native_bootstrap_audit import IMAGE_SHA256, TEXT_SHA256


def audit(image_path, text_path):
    image=image_path.read_bytes();text=text_path.read_bytes()
    if hashlib.sha256(image).hexdigest()!=IMAGE_SHA256 or hashlib.sha256(text).hexdigest()!=TEXT_SHA256:
        raise ValueError('Evidence does not match captured 2.0.4.23745')
    pe=pefile.PE(data=image,fast_load=True);pe.parse_data_directories(directories=[3])
    bounds={(e.struct.BeginAddress,e.struct.EndAddress) for e in pe.DIRECTORY_ENTRY_EXCEPTION}
    md=Cs(CS_ARCH_X86,CS_MODE_64);rows=[];decoded={}
    for name,rva,end in [('buff_data_constructor',0x5b5660,0x5b57d1),('roar_effect',0x91cc20,0x91ceeb)]:
        if (rva,end) not in bounds:raise ValueError('Function extent differs from PE exception table')
        code=text[rva-4096:end-4096];ins=list(md.disasm(code,rva))
        if sum(i.size for i in ins)!=len(code):raise ValueError('Incomplete function decode')
        value=14695981039346656037
        for byte in code:value=((value^byte)*1099511628211)&0xffffffffffffffff
        rows.append(dict(name=name,rva=rva,size=len(code),code=code.hex(),fnv64=value))
        decoded[name]=ins
    effect={i.address:i for i in decoded['roar_effect']}
    required={0x91ce0c:('call','0x5b5660'),0x91ce3c:('mov','rbx, qword ptr [rax + 0xa00]'),
              0x91ce5d:('lea','r8, [rbp - 0x50]'),0x91ce61:('mov','rdx, rdi'),
              0x91ce64:('mov','rcx, rsi'),0x91ce67:('call','rbx')}
    for address,pair in required.items():
        i=effect[address]
        if (i.mnemonic,i.op_str)!=pair:raise ValueError('Buff callback ABI changed')
    result=dict(captured_text_sha256=TEXT_SHA256,contracts=rows,constructor_call_rva=0x91ce0c,buff_call_rva=0x91ce67)
    fixture=json.loads(Path(__file__).with_name('native-buff-contract-23745.json').read_text())
    if result!=fixture:raise ValueError('Tracked buff contract differs from verified capture')
    return dict(verified=True,constructor_rva='0x5b5660',effect_rva='0x91cc20',
                sizes=[r['size'] for r in rows],
                legacy_signature_matches=text.count(bytes.fromhex('c74120ffffffff')),
                image_sha256=IMAGE_SHA256,captured_text_sha256=TEXT_SHA256)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',type=Path,required=True);parser.add_argument('--text',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(audit(args.image,args.text),indent=2))
