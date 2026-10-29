"""Fetch the pinned upstream BSD pjass binary; no installer or game access."""
from pathlib import Path
import hashlib
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://github.com/lep/pjass/releases/download/release-2026-10-13/pjass.exe'
SHA256 = '45911ae998b23155c8d408597c616cf080a3fa16b4cf2e1bacb239757c704d5c'


def prepare():
    path = ROOT/'tools/map-script-pjass.exe'
    if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == SHA256:
        return path
    with urllib.request.urlopen(urllib.request.Request(URL, headers={'User-Agent':'War3MapTools'}), timeout=45) as response:
        raw = response.read(4*1024*1024+1)
    if hashlib.sha256(raw).hexdigest() != SHA256:
        raise RuntimeError('JASS 检查器下载校验失败。')
    pending = path.with_suffix('.pending')
    pending.write_bytes(raw)
    pending.replace(path)
    return path


if __name__ == '__main__':
    print(prepare())
