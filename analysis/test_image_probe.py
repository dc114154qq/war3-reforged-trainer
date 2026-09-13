"""Actual mapped-image loading against an owned disposable process, never Warcraft."""
from pathlib import Path
import shutil
import subprocess
import sys
import struct
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


def test_mapped_read_preserves_bytes_and_reports_unreadable_page(probe,tmp_path):
    controller,bridge=probe
    code='''import ctypes,time
k=ctypes.WinDLL('kernel32');k.VirtualAlloc.restype=ctypes.c_void_p
k.VirtualProtect.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_ulong,ctypes.c_void_p]
p=k.VirtualAlloc(None,8192,0x3000,4);assert p
ctypes.memset(p,0x5a,8192);old=ctypes.c_ulong()
assert k.VirtualProtect(p+4096,4096,1,ctypes.byref(old))
print(p,flush=True);time.sleep(60)
'''
    child=subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.PIPE,text=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        address=int(child.stdout.readline())
        capture=tmp_path/'read.bin'
        result=subprocess.run([str(controller),str(child.pid),str(bridge),'--read',str(address),'8192',str(capture)],
                              capture_output=True,text=True,timeout=25)
        assert result.returncode==0,result.stdout+result.stderr
        data=capture.read_bytes()
        assert struct.unpack_from('<4I',data)==(0x52494d47,8192,2,1)
        assert struct.unpack_from('<2I',data,16)==(0,4096)
        assert struct.unpack_from('<I',data,24)[0]!=0
        assert data[32:32+4096]==b'Z'*4096
        assert len(data)==32+8192
        assert child.poll() is None,'Read probe crashed its host'
        rejected=subprocess.run([str(controller),str(child.pid),str(bridge),'--read',str(address),'67108865',str(tmp_path/'bad.bin')],
                                capture_output=True,text=True,timeout=5)
        assert rejected.returncode==3 and not (tmp_path/'bad.bin').exists()
    finally:
        if child.poll() is None: child.terminate()
        child.wait(timeout=10)
