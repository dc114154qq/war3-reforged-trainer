import ctypes as c
from unittest.mock import patch

import war3_engine_transport as t


def test_fault_address_is_attributed_to_its_remote_image_not_local_modules():
    def query(handle,address,output,size):
        assert handle==123 and address==0x70001234
        r=c.cast(output,c.POINTER(t.FaultMemoryRegion)).contents
        r.base=0x70001000;r.allocation_base=0x70000000
        r.size=0x1000;r.state=0x1000;r.protect=0x20;r.type=0x1000000
        return size
    def mapped(handle,address,buffer,length):
        buffer.value=r'\Device\HarddiskVolume2\Windows\System32\user32.dll'
        return len(buffer.value)
    with patch.object(t,'api',side_effect=[query,mapped]):
        result=t.describe_fault_instruction(123,{'instruction':'0x70001234'})
    assert result['module_rva']=='0x1234'
    assert result['mapped_file'].endswith('user32.dll')


def test_mapping_failure_preserves_the_original_fault():
    fault={'instruction':'0x70001234','code':'0xc0000005'}
    with patch.object(t,'api',side_effect=OSError('query denied')):
        result=t.describe_fault_instruction(123,fault)
    assert 'query denied' in result['lookup_error']
    assert fault=={'instruction':'0x70001234','code':'0xc0000005'}
    assert t.describe_fault_instruction(123,None) is None


def test_real_local_image_mapping_has_allocation_relative_offset():
    address=c.cast(t.k.GetCurrentProcess,c.c_void_p).value
    result=t.describe_fault_instruction(t.current_process(),{'instruction':hex(address)})
    assert 'lookup_error' not in result
    assert result['mapped_file'].lower().endswith('.dll')
    assert int(result['allocation_base'],16)+int(result['module_rva'],16)==address
