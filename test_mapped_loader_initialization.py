"""Import fixups and ownership rules; native Windows smoke runs separately."""
import ctypes as c
import struct
from types import SimpleNamespace as S
from unittest.mock import Mock
import pytest
import war3_engine_transport as t


def image(imports=None):
    return S(OPTIONAL_HEADER=S(ImageBase=0x180000000, SizeOfImage=0x10000),
             DIRECTORY_ENTRY_IMPORT=imports if imports is not None else [
                 S(dll=b'KERNEL32.dll', imports=[S(name=b'VirtualQuery', address=0x180002000)])])


@pytest.mark.parametrize('failure', [None, 'write', 'readback', 'restore'])
def test_mapped_iat_restores_page_even_after_failure(monkeypatch, failure):
    calls = []
    def protect(handle, slot, size, flags, previous):
        calls.append(flags)
        c.cast(previous, c.POINTER(t.U))[0] = 0x20
        return not (failure == 'restore' and len(calls) == 2)
    def write(handle, slot, value, size, actual):
        c.cast(actual, c.POINTER(t.Z))[0] = size
        return failure != 'write'
    monkeypatch.setattr(t, 'api', lambda *args: protect)
    monkeypatch.setattr(t, 'resolve', lambda *args: 0x7fff12340000)
    monkeypatch.setitem(t.p, 'write', write)
    monkeypatch.setitem(t.p, 'bytes_at', lambda *args: struct.pack('<Q', 1 if failure == 'readback' else 0x7fff12340000))
    if failure:
        with pytest.raises(RuntimeError):
            t.initialize_mapped_imports(S(handle=1), 0x200000, image())
    else:
        rows=t.initialize_mapped_imports(S(handle=1), 0x200000, image())
        assert rows[0]['slot'] == '0x202000'
        assert rows[0]['target'] == '0x7fff12340000'
        assert rows[0]['protection_restored']
    assert calls == [4, 0x20]


@pytest.mark.parametrize('kind', ['ordinal','bounds','duplicate','dependency','delay'])
def test_import_preflight_never_writes_incomplete_plan(monkeypatch, kind):
    pe=image()
    item=pe.DIRECTORY_ENTRY_IMPORT[0].imports[0]
    if kind=='ordinal': item.name=None
    if kind=='bounds': item.address=pe.OPTIONAL_HEADER.ImageBase+0x10000
    if kind=='duplicate': pe.DIRECTORY_ENTRY_IMPORT[0].imports.append(item)
    if kind=='dependency': pe.DIRECTORY_ENTRY_IMPORT[0].dll=b'custom.dll'
    if kind=='delay': pe.DIRECTORY_ENTRY_DELAY_IMPORT=[object()]
    monkeypatch.setattr(t,'resolve',lambda *args:0x700000)
    write=Mock(); monkeypatch.setitem(t.p,'write',write)
    with pytest.raises(RuntimeError):t.initialize_mapped_imports(S(handle=1),0x200000,pe)
    write.assert_not_called()


@pytest.mark.parametrize('registered,removed,exception,module,transfer', [
    (1,1,0,0x700000,True), (1,1,0,0,False),
    (1,0,0,0x700000,False), (1,1,0xc0000005,0,False), (0,0,0,0,False)])
def test_protected_diagnostic_ownership_and_unwind(monkeypatch,registered,removed,exception,module,transfer):
    def write(handle,slot,value,size,actual):
        assert size==112
        c.cast(actual,c.POINTER(t.Z))[0]=size
        return True
    payload=struct.pack('<4QIIQi4x5Q4I',1,2,3,module,570,3 if exception else 2,4,-1073741514,
                        5,6,7,8,9,10,registered,removed,exception)
    monkeypatch.setitem(t.p,'alloc',lambda *args:0x10000)
    freed=Mock(return_value=True);monkeypatch.setitem(t.p,'free',freed)
    monkeypatch.setitem(t.p,'write',write)
    monkeypatch.setitem(t.p,'bytes_at',lambda *args:payload)
    monkeypatch.setattr(t,'remote_thread_call',lambda *args:(0 if exception else 1,99))
    cleanup=Mock(return_value={'unloaded':True});monkeypatch.setattr(t,'remote_free_library',cleanup)
    r=t.diagnose_mapped_loader(1,2,3,4,5,6,7,unwind=(5,6,7,8,9,10),keep_loaded=True)
    assert bool(r.get('ownership_transferred')) == transfer
    assert r['image_must_remain_mapped'] == bool(registered and not removed)
    assert cleanup.call_count == int(bool(module) and not transfer)
    assert r['completed'] == bool(registered and removed and not exception)
    freed.assert_called_once()


def test_diagnostic_free_failure_cannot_claim_clean_release(monkeypatch):
    def write(handle,slot,value,size,actual):
        c.cast(actual,c.POINTER(t.Z))[0]=size
        return True
    monkeypatch.setitem(t.p,'alloc',lambda *args:0x10000)
    monkeypatch.setitem(t.p,'write',write)
    monkeypatch.setitem(t.p,'free',lambda *args:False)
    monkeypatch.setitem(t.p,'bytes_at',lambda *args:struct.pack('<4QIIQi4x',1,2,3,0,126,2,4,-1073741515))
    monkeypatch.setattr(t,'remote_thread_call',lambda *args:(1,99))
    result=t.diagnose_mapped_loader(1,2,3,4,5,6,7)
    assert result['completed'] and result['allocations_retained']
    assert not result['command_freed']
