"""Actual mapped-image loading against an owned disposable process, never Warcraft."""
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
import pefile

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def probe(tmp_path_factory):
    compiler=shutil.which('clang')
    assert compiler
    directory=tmp_path_factory.mktemp('image probe')
    bridge=directory/'bridge.dll'; controller=directory/'controller.exe'
    subprocess.run([compiler,'-shared','-O2','-nostdlib','-Wl,/noentry','-Wl,/nodefaultlib',
                    str(ROOT/'analysis/image_probe_bridge.c'),'-o',str(bridge)],check=True,capture_output=True,timeout=60)
    subprocess.run([compiler,'-O2',str(ROOT/'analysis/map-image-probe.c'),'-o',str(controller)],
                   check=True,capture_output=True,timeout=60)
    pe=pefile.PE(str(bridge))
    assert not hasattr(pe,'DIRECTORY_ENTRY_IMPORT')
    assert pe.OPTIONAL_HEADER.AddressOfEntryPoint==0
    assert [e.name for e in pe.DIRECTORY_ENTRY_EXPORT.symbols]==[b'ImageProbe']
    pe.close()
    return controller,bridge

@pytest.mark.parametrize('exists',[True,False])
def test_mapped_entry_runs_loader_and_preserves_host(probe,exists):
    controller,bridge=probe
    target=bridge if exists else bridge.parent/'missing library.dll'
    child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],
                           creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        result=subprocess.run([str(controller),str(child.pid),str(bridge),str(target)],
                              capture_output=True,text=True,timeout=25)
        assert result.returncode==(0 if exists else 6),result.stdout+result.stderr
        assert 'stage=2' in result.stdout,result.stdout
        assert 'exit=0x0' in result.stdout,result.stdout
        if not exists: assert 'error=126' in result.stdout,result.stdout
        assert child.poll() is None,'Probe crashed its host process'
    finally:
        if child.poll() is None: child.terminate()
        child.wait(timeout=10)
