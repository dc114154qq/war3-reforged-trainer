"""SEC_IMAGE diagnostic cleanup tests; all process APIs are mocked."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import Mock
import ctypes as c
import struct
import pytest
spec=importlib.util.spec_from_file_location('image_probe',Path(__file__).parent/'analysis/verify-image-thread-entry.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


@pytest.fixture
def setup(monkeypatch):
 entry_bytes=b'P'*16
 pe=S(DIRECTORY_ENTRY_EXPORT=S(symbols=[S(name=b'ProbeLoaderEntry',address=0x1000)]),get_data=lambda a,n:entry_bytes)
 monkeypatch.setattr(m.pefile,'PE',Mock(return_value=pe))
 monkeypatch.setattr(m,'create_file',Mock(return_value=11))
 monkeypatch.setattr(m,'create_mapping',Mock(return_value=12))
 def mapping(section,handle,base,*a):base._obj.value=0x500000;return 0
 monkeypatch.setattr(m,'map_section',mapping)
 def query(handle,address,kind,buffer,size,returned):
  c.memmove(buffer,struct.pack('<QQIIQIIII',0x500000,0x500000,2,0,0x2000,0x1000,0x20,0x1000000,0),48)
  returned._obj.value=48;return 0
 monkeypatch.setattr(m,'query_memory',query)
 def write(handle,address,buffer,size,written):written._obj.value=size;return 1
 monkeypatch.setitem(m.probe,'write',write)
 monkeypatch.setitem(m.probe,'alloc',Mock(return_value=0x600000))
 monkeypatch.setitem(m.probe,'bytes_at',lambda h,a,n:entry_bytes if n==16 else struct.pack('<QQQIIQII',0,0,0,2,0,0,570,0))
 invoke=Mock(return_value={'created':True,'completed':True})
 free=Mock(return_value=1);close=Mock();unmap=Mock(return_value=0)
 monkeypatch.setitem(m.probe,'invoke',invoke)
 monkeypatch.setitem(m.probe,'free',free)
 monkeypatch.setitem(m.probe,'close',close)
 monkeypatch.setattr(m,'unmap_section',unmap)
 return invoke,free,close,unmap


def test_finished_probe_preserves_loader_error_and_frees_mapping(setup):
 invoke,free,close,unmap=setup
 r=m.image_loader(Path('fixture.dll'),20,30,40,50,300)
 assert r['stage']==2 and r['loader_last_error']==570 and r['memory_type']=='0x1000000'
 assert r['marker_block_freed'] and r['image_unmap_status']=='0x0'
 free.assert_called_once_with(20,0x600000,0,0x8000)
 assert close.call_count==2;unmap.assert_called_once()


def test_pending_thread_keeps_code_and_argument_allocations(setup):
 invoke,free,close,unmap=setup
 invoke.return_value={'created':True,'completed':False}
 r=m.image_loader(Path('fixture.dll'),20,30,40,50,300)
 assert r['pending_allocations_retained']
 free.assert_not_called();unmap.assert_not_called();assert close.call_count==2


def test_thread_creation_failure_still_cleans_own_allocations(setup):
 invoke,free,close,unmap=setup
 invoke.return_value={'created':False,'completed':False,'error':5}
 r=m.image_loader(Path('fixture.dll'),20,30,40,50,300)
 assert not r['created'] and r['marker_block_freed']
 free.assert_called_once();unmap.assert_called_once()


def test_wrong_mapped_bytes_never_start_thread(setup,monkeypatch):
 invoke,free,close,unmap=setup
 monkeypatch.setitem(m.probe,'bytes_at',lambda *args:b'Q'*16)
 r=m.image_loader(Path('fixture.dll'),20,30,40,50,300)
 assert 'bytes differ' in r['marker_error']
 invoke.assert_not_called();unmap.assert_called_once();free.assert_not_called()
