from pathlib import Path
import struct
from unittest.mock import Mock
import pytest
from test_game_thread_dispatch_cleanup import m as dispatch
from war3_code_observation import inspect_code_observation

@pytest.mark.parametrize('mode',['post','send','',None])
def test_unknown_delivery_mode_rejected_before_image_access(mode):
    with pytest.raises(ValueError,match='delivery mode'):
        dispatch.inspect(1,2,3,Path('missing.dll'),delivery_mode=mode)

def test_old_image_cannot_accept_posted_mode(monkeypatch):
    pe=Mock();pe.DIRECTORY_ENTRY_EXPORT.symbols=[]
    monkeypatch.setattr(dispatch.pefile,'PE',Mock(return_value=pe))
    open_process=Mock(side_effect=AssertionError('process must not be opened'))
    monkeypatch.setitem(dispatch.p,'open_process',open_process)
    with pytest.raises(ValueError,match='Posted-message probe ABI'):
        dispatch.inspect(1,2,3,Path('old.dll'),delivery_mode='posted')
    open_process.assert_not_called()

@pytest.mark.parametrize('size',[0,24,407,409])
def test_code_read_rejected_before_process(size):
    with pytest.raises(ValueError):dispatch.inspect(1,2,3,Path('missing.dll'),query_mode='code_read',work_payload=bytes(size))

def payload():return struct.pack('<2Q2I',0x100000,0x200000,384,0)+bytes(384)
@pytest.mark.parametrize('byte',[0,0x90,0x60,0x70,0xcc,0xff])
def test_uniform_read_never_accepted_as_instruction_bytes(byte):
    result=struct.pack('<2Q2I',0x100000,0x200000,384,384)+bytes([byte])*384
    with pytest.raises(ValueError,match='Uniform'):inspect_code_observation(payload(),result)

def test_readable_different_bytes_still_not_authenticated():
    result=struct.pack('<2Q2I',0x100000,0x200000,384,384)+bytes(range(256))+bytes(range(128))
    assert inspect_code_observation(payload(),result)['code_authenticity']=='unverified'

@pytest.mark.parametrize('offset,fmt,value',[(0,'Q',0x300000),(8,'Q',0x300000),(16,'I',128),(20,'I',383)])
def test_code_read_identity_checked(offset,fmt,value):
    result=bytearray(struct.pack('<2Q2I',0x100000,0x200000,384,384)+bytes(range(256))+bytes(range(128)))
    struct.pack_into('<'+fmt,result,offset,value)
    with pytest.raises(ValueError):inspect_code_observation(payload(),result)

@pytest.mark.parametrize('index,value',[(0,0),(1,0x100000),(2,0x4a2e0000394b),(3,0),(3,100001),(4,2)])
def test_hero_abi_rejected_before_access(index,value):
    args=[0x100000,0x200000,0x10082d,2,0];args[index]=value
    with pytest.raises(ValueError):dispatch.inspect(1,2,3,Path('missing.dll'),query_mode='hero_level',work_payload=struct.pack('<5Q',*args))
