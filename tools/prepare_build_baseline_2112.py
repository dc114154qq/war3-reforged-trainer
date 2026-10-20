"""Prepare the hash-pinned dependency carrier for the current release build."""
from pathlib import Path
import argparse,hashlib,json,os,urllib.request
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--from-file',type=Path,help='Use an already downloaded, identical release EXE')
args=parser.parse_args()
manifest=json.loads((root/'docs/NATIVE_BUILD_BASELINE.json').read_text(encoding='utf8'))
expected='7033B8F4C8D75B085F2C5D015920702D8FE09EAA96CB3906703FC7BCB5DF143C'
assert manifest['kind']=='published_dependency_carrier' and manifest['exe_sha256']==expected
folder=root/'dist-2.1.11-verified';target=folder/manifest['artifact']
assert target.resolve().is_relative_to(folder.resolve())
target.parent.mkdir(parents=True,exist_ok=True)
if args.from_file:data=args.from_file.read_bytes()
elif target.exists():data=target.read_bytes()
else:
    request=urllib.request.Request(manifest['carrier_url'],headers={'User-Agent':'war3-build-baseline/2.1.12'})
    with urllib.request.urlopen(request,timeout=120) as response:data=response.read(30000000)
if hashlib.sha256(data).hexdigest().upper()!=expected:raise RuntimeError('Dependency carrier hash mismatch')
if not target.exists():
    pending=target.with_suffix('.exe.tmp');pending.write_bytes(data);os.replace(pending,target)
elif hashlib.sha256(target.read_bytes()).hexdigest().upper()!=expected:raise RuntimeError('Existing carrier hash mismatch')
(folder/'current.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
print('Verified native/runtime dependency carrier:',target)
