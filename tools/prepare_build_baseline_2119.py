"""Prepare hash-pinned published native/runtime and Microsoft setup dependencies."""
from pathlib import Path
import argparse,hashlib,json,os,urllib.request
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--from-file',type=Path);parser.add_argument('--webview-from-file',type=Path);args=parser.parse_args()
def sha(b):return hashlib.sha256(b).hexdigest().lower()
def fetch(url,limit):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'War3Trainer-build/2.1.19'}),timeout=120) as r:
        data=r.read(limit+1)
    if len(data)>limit:raise ValueError('Dependency download exceeds its limit')
    return data
def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.read_bytes()!=data:raise ValueError('Existing dependency differs: '+str(path))
        return
    pending=path.with_suffix(path.suffix+'.pending');pending.write_bytes(data);os.replace(pending,path)
manifest=json.loads((ROOT/'docs/NATIVE_BUILD_BASELINE.json').read_text(encoding='utf8'))
assert len(manifest['exe_sha256']) == 64 and manifest['version'] == '2.1.18'
folder=ROOT/'dist-native-baseline';target=folder/manifest['artifact']
assert target.resolve().is_relative_to(folder.resolve())
data=args.from_file.read_bytes() if args.from_file else target.read_bytes() if target.exists() else fetch(manifest['carrier_url'],40*1024*1024)
assert sha(data)==manifest['exe_sha256'].lower()
atomic(target,data);(folder/'current.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
spec=json.loads((ROOT/'docs/WEBVIEW2_BOOTSTRAPPER.json').read_text(encoding='utf8'))
target=ROOT/'assets/webview2-bootstrapper.exe'
data=args.webview_from_file.read_bytes() if args.webview_from_file else target.read_bytes() if target.exists() else fetch(spec['resolved_url'],8*1024*1024)
assert sha(data)==spec['sha256'] and len(data)==spec['bytes']
atomic(target,data)
print('Verified published native/runtime baseline and Microsoft WebView2 setup dependencies.')
