"""Fetch the immutable published build used for native DLL reuse in 2.1.08."""
from pathlib import Path
import hashlib, json, urllib.request
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'docs/BUILD_BASELINE_v2.1.07.json').read_text(encoding='utf8'))
folder=root/'dist-2.1.07-bundle-max-level-20261012'
target=folder/manifest['artifact']
target.parent.mkdir(parents=True,exist_ok=True)
if not target.exists():
    url='https://twomengxi.xyz/downloads/War3ReforgedTrainer-v2.1.07-A113817A00B8.exe'
    with urllib.request.urlopen(url,timeout=120) as stream:
        data=stream.read(30000000)
    if hashlib.sha256(data).hexdigest().upper()!=manifest['exe_sha256']:
        raise RuntimeError('Published baseline hash mismatch')
    target.write_bytes(data)
if hashlib.sha256(target.read_bytes()).hexdigest().upper()!=manifest['exe_sha256']:
    raise RuntimeError('Existing baseline hash mismatch')
(folder/'current.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
print('Verified baseline ready:',target)
