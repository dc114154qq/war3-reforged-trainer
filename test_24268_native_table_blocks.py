from unittest.mock import Mock
import struct
import pytest
from war3_native_table import NativeTable24268,_string
from war3_object_registry import ObjectIdentityError
from test_native_table_live import fixture

def test_registration_metadata_read_count_is_bounded():
    m,c=fixture()
    for base in (0x500000,0x500100,0x510000,0x510100):
        for offset in range(64):m.data.setdefault(base+offset,0)
    read=Mock(wraps=m.read);m.read=read
    table=NativeTable24268(m,c)
    assert len(table.entries)==2
    assert read.call_count<=10

def test_no_read_crosses_page_boundary():
    address=0x50fff8;raw=b'Abcdefghijklmnop\0';requests=[]
    def read(a,n):
        requests.append((a,n));assert a//4096==(a+n-1)//4096
        return (raw[a-address:]+bytes(n))[:n]
    assert _string(Mock(read=read),address)=='Abcdefghijklmnop'
    assert requests==[(address,8),(address+8,64)]

def test_bytes_after_terminator_not_decoded():
    assert _string(Mock(read=lambda a,n:(b'Fn\0'+b'\xff'*n)[:n]),0x500000)=='Fn'

def test_256_byte_unterminated_name_rejected():
    read=Mock(side_effect=lambda a,n:b'A'*n)
    with pytest.raises(ObjectIdentityError,match='terminator'):_string(Mock(read=read),0x500000)
    assert read.call_count==4

def test_sparse_reader_can_read_exact_bytes():
    raw=b'Fn\0';base=0x500000
    def read(a,n):
        if a-base+n>len(raw):raise OSError('extent')
        return raw[a-base:a-base+n]
    assert _string(Mock(read=read),base)=='Fn'

def test_cycle_detected_without_reading_same_node_metadata_again():
    m,c=fixture();m.put(0x400000+0x20,struct.pack('<Q',0x400000));read=Mock(wraps=m.read);m.read=read
    with pytest.raises(ObjectIdentityError,match='cyclic'):NativeTable24268(m,c)
    assert sum(1 for call in read.call_args_list if call.args[0]==0x400020)==1

@pytest.mark.parametrize('raw',[b'\0',b'\xff\0'])
def test_invalid_metadata_rejected(raw):
    with pytest.raises(ObjectIdentityError):_string(Mock(read=lambda a,n:(raw+bytes(n))[:n]),0x500000)
