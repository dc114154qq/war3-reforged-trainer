"""Download and verify the fixed native build baseline for 2.1.10."""
from pathlib import Path
import hashlib,json,urllib.request
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'docs/NATIVE_BUILD_BASELINE.json').read_text(encoding='utf8'))
folder=root/'dist-2.1.09-verified';target=folder/manifest['artifact']
assert target.resolve().is_relative_to(folder.resolve())
expected='B6606E389F0B334432EF12B18C4CF19A78B159009F8A2E55FE29330600112D95'
assert manifest['exe_sha256']==expected
target.parent.mkdir(parents=True,exist_ok=True)
if not target.exists():
    request=urllib.request.Request('https://twomengxi.xyz/downloads/War3ReforgedTrainer-v2.1.09-B6606E389F0B.exe',headers={'User-Agent':'war3-build-baseline/2.1.10'})
    with urllib.request.urlopen(request,timeout=120) as response:data=response.read(30000000)
    if hashlib.sha256(data).hexdigest().upper()!=expected:raise RuntimeError('Baseline hash mismatch')
    target.write_bytes(data)
if hashlib.sha256(target.read_bytes()).hexdigest().upper()!=expected:raise RuntimeError('Existing baseline hash mismatch')
(folder/'current.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
print('Verified native build baseline:',target)
