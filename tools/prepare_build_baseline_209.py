"""Fetch and verify the immutable native-module build dependency for 2.1.09."""
from pathlib import Path
import hashlib,json,urllib.request
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'docs/NATIVE_BUILD_BASELINE.json').read_text(encoding='utf8'))
folder=root/'dist-2.1.08-verified'
target=folder/manifest['artifact']
assert target.resolve().is_relative_to(folder.resolve())
target.parent.mkdir(parents=True,exist_ok=True)
expected='49BF0ADAB6FFA3163542EFE3D7963FB6574F6C7718D942E83E897E668012D56F'
assert manifest['exe_sha256']==expected
if not target.exists():
    url='https://twomengxi.xyz/downloads/War3ReforgedTrainer-v2.1.08-49BF0ADAB6FF.exe'
    with urllib.request.urlopen(url,timeout=120) as response:data=response.read(30000000)
    if hashlib.sha256(data).hexdigest().upper()!=expected:raise RuntimeError('Baseline hash mismatch')
    target.write_bytes(data)
if hashlib.sha256(target.read_bytes()).hexdigest().upper()!=expected:raise RuntimeError('Existing baseline hash mismatch')
(folder/'current.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
print('Verified native build dependency:',target)
