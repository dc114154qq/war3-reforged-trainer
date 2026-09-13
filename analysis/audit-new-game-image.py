"""Offline PE inventory; compares old build fingerprints without invoking game code."""
import hashlib
import json
from pathlib import Path
import re
import sys
import pefile

root = Path(__file__).resolve().parents[1]
path = Path(sys.argv[1])
blob = path.read_bytes()
pe = pefile.PE(data=blob)
fixed = pe.VS_FIXEDFILEINFO[0]
version = '.'.join(str(n) for n in (fixed.FileVersionMS >> 16, fixed.FileVersionMS & 65535,
                                  fixed.FileVersionLS >> 16, fixed.FileVersionLS & 65535))
profile = (root/'tools/war3_native_bootstrap_profile.h').read_text()
checks = re.search(r'g_bootstrap_checks\[\] = \{(.*?)\};', profile, re.S).group(1)
def fnv(data):
    value = 14695981039346656037
    for byte in data: value = ((value ^ byte) * 1099511628211) & 0xffffffffffffffff
    return value
rows = []
for rva, size, expected in re.findall(r'\{0x([0-9a-f]+)u, (\d+)u, 0x([0-9a-f]+)ULL\}', checks):
    rva, size, expected = int(rva,16), int(size), int(expected,16)
    data = pe.get_data(rva,size)
    rows.append(dict(rva=hex(rva), size=size, old_hash=hex(expected),
                     disk_hash=hex(fnv(data)), old_fingerprint_matches=fnv(data)==expected))
report = dict(version=version, image_sha256=hashlib.sha256(blob).hexdigest(),
              timestamp=hex(pe.FILE_HEADER.TimeDateStamp), image_size=hex(pe.OPTIONAL_HEADER.SizeOfImage),
              machine=hex(pe.FILE_HEADER.Machine),
              sections=[dict(name=s.Name.rstrip(b'\0').decode(),rva=hex(s.VirtualAddress),
                             virtual_size=s.Misc_VirtualSize,raw_size=s.SizeOfRawData)
                        for s in pe.sections], old_checks=rows,
              note='Disk-only fingerprints. Protected live code may differ; mismatch does not identify a replacement.')
out=root/'analysis'/f'game-image-{version}.json'
out.write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report,indent=2))
