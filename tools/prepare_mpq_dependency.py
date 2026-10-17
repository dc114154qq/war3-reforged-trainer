"""Prepare the pinned StormLib DLL used by offline campaign/map processing."""
from pathlib import Path
import hashlib,subprocess,sys,tempfile,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from war3_mpq import DLL_SHA256


def prepare():
    target=ROOT/'tools/war3_mpq.dll'
    if target.is_file():
        if hashlib.sha256(target.read_bytes()).hexdigest()!=DLL_SHA256:
            raise RuntimeError('Existing MPQ dependency hash differs')
        return target
    with tempfile.TemporaryDirectory(prefix='war3-mpq-dependency-') as folder:
        subprocess.run([sys.executable,'-m','pip','download','--only-binary=:all:','--no-deps',
                        '--dest',folder,'pympq==0.2.2'],check=True)
        candidates=[]
        for wheel in Path(folder).glob('*.whl'):
            with zipfile.ZipFile(wheel) as archive:
                for name in archive.namelist():
                    if name.endswith('/StormLib.dll'):
                        raw=archive.read(name)
                        if hashlib.sha256(raw).hexdigest()==DLL_SHA256:candidates.append(raw)
        if len(candidates)!=1:raise RuntimeError('Pinned x64 StormLib dependency was not found')
        target.write_bytes(candidates[0])
    return target


if __name__=='__main__':print(prepare())
