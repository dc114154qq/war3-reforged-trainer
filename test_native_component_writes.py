"""Execute production component field batches; reject bad batches before stores."""
import ctypes
from dataclasses import replace
import os
from pathlib import Path
import shutil
import struct
import subprocess
from unittest.mock import Mock

import pytest
import war3_reforged_trainer as module
from test_native_identity_guard import HARNESS
from test_native_unit_field_dispatch import FIELDS_HARNESS
from test_native_snapshot_binding import make_candidate, make_snapshot


WRITE_HARNESS=r'''
__declspec(dllexport) DWORD write_fields(const wchar_t *directory,unsigned count,const unsigned *ids,
                                        const unsigned *bits,const unsigned *offsets,unsigned failure,unsigned *out) {
    DWORD error=field_snapshot(directory,15,0),bytes;HANDLE file;wchar_t path[MAX_PATH];
    NativeCommand cmd={0};uint64_t targets[15];
    if(error) return error;
    if(!count || count>15) return ERROR_INVALID_PARAMETER;
    command_path(path,MAX_PATH);DeleteFileW(path);field_unit_calls=0;field_fault=0;
    cmd.magic=WAR3_NATIVE_MAGIC;cmd.version=WAR3_NATIVE_VERSION;cmd.status=WAR3_NATIVE_STATUS_PENDING;
    cmd.op_count=count+1;cmd.unit_handle=7;
    cmd.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;
    cmd.ops[0].handler=(uint64_t)(uintptr_t)object;cmd.ops[0].arg0=full;cmd.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    for(unsigned n=0;n<count;++n) {
        unsigned id=ids[n];uint8_t *base=id<2?object:id==9?field_data[2]:id<10 || id>=80?field_data[1]:field_data[3];
        cmd.ops[n+1].kind=WAR3_NATIVE_OP_WRITE_COMPONENT_FIELDS;cmd.ops[n+1].rawcode=id;
        cmd.ops[n+1].handler=(uint64_t)(uintptr_t)base;
        cmd.ops[n+1].arg0=id<2?full:*(uint64_t *)(base+0x18);cmd.ops[n+1].arg1=bits[n];
        targets[n]=(uint64_t)(uintptr_t)(base+offsets[n]);
        out[n]=*(uint32_t *)(uintptr_t)targets[n];
    }
    if(failure==1) ++cmd.ops[count].arg0;
    if(failure==2) cmd.ops[count].rawcode=999;
    if(failure==3) cmd.ops[count].arg1=0x7fc00000;
    if(failure==4) cmd.ops[count].rawcode=16+17; /* unlisted/read-only attack field */
    if(failure==5) field_fault=6; /* component removed by final unit resolver */
    if(failure==6) field_fault=5; /* unit recycled by final unit resolver */
    if(failure==7) *(uint64_t *)(field_wrappers[3]+0x50)=0;
    if(failure==8) cmd.ops[count].kind=WAR3_NATIVE_OP_JASS_SET_UNIT_INT;
    if(failure==9) cmd.ops[count].handler=1;
    if(failure==10) *(uint64_t *)(field_data[3]+0x638)=0;
    if(failure==11) cmd.ops[count].arg1=0x100000000ULL;
    file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();
    BOOL ok=WriteFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);
    if(!ok || bytes!=sizeof(cmd)) return ERROR_WRITE_FAULT;
    run_command();
    for(unsigned n=0;n<count;++n) out[15+n]=*(uint32_t *)(uintptr_t)targets[n];
    return 0;
}
'''


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler:pytest.skip('clang required')
    root=tmp_path_factory.mktemp('component-write');source=root/'test.c';library=root/'test.dll'
    harness=HARNESS.replace('static uint8_t object[0x20]','static uint8_t object[0x600]')
    source.write_text(harness.replace('HELPER_SOURCE',(Path(__file__).parent/'tools/war3_native_helper.c').as_posix())
                      +FIELDS_HARNESS+WRITE_HARNESS,encoding='utf8')
    subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(library),
                    '-luser32','-lkernel32'],check=True,capture_output=True,timeout=60)
    lib=ctypes.CDLL(str(library));ptr=ctypes.POINTER(ctypes.c_uint)
    lib.write_fields.argtypes=[ctypes.c_wchar_p,ctypes.c_uint,ptr,ptr,ptr,ctypes.c_uint,ptr]
    lib.write_fields.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)


def dispatch(native,tmp_path,ids,bits,offsets,failure=0):
    out=(ctypes.c_uint*30)();array=ctypes.c_uint*len(ids)
    assert native.write_fields(str(tmp_path)+'\\',len(ids),array(*ids),array(*bits),array(*offsets),failure,out)==0
    payload=(tmp_path/f'war3_reforged_native_{os.getpid()}.bin').read_bytes()
    return tuple(out)[:len(ids)],tuple(out)[15:15+len(ids)],payload


OFFSETS=[0x2e8,0x2f0,0x104,0x188,0x198,0x1a8,0x100,0x108,0x130,0xd8]
ATTACK=[0xf8,0xfc,0x100,0x104,0x108,0x10c,0x110,0x114,0x118,0x16c,0x178,
        0x200,0x228,0x370,0x398,0x3a8,0x3c0]
CASES=list(enumerate(OFFSETS))+[(16+n,offset) for n,offset in enumerate(ATTACK)]+[
    (48+n,offset+0x638) for n,offset in enumerate(ATTACK)]+[(80+n,0x1d4+n*4) for n in range(5)]+[
    (85+n,0x1ec+n*4) for n in range(5)]


@pytest.mark.parametrize('id,offset',CASES)
def test_each_exposed_component_field_writes_and_reads_back(native,tmp_path,id,offset):
    _,after,payload=dispatch(native,tmp_path,[id],[0x41280000],[offset])
    trainer=module.War3Trainer.__new__(module.War3Trainer)
    results=trainer._parse_native_helper_results(payload,2)
    assert after==(0x41280000,) and results[1].result==after[0]


@pytest.mark.parametrize('failure',range(1,12))
def test_invalid_second_field_prevents_first_write(native,tmp_path,failure):
    before,after,payload=dispatch(native,tmp_path,[0,59],[0x41000000,0x40000000],[0x2e8,0x838],failure)
    with pytest.raises(RuntimeError):module.War3Trainer.__new__(module.War3Trainer)._parse_native_helper_results(payload,3)
    assert after==before


def test_duplicate_address_batch_rejected(native,tmp_path):
    before,after,payload=dispatch(native,tmp_path,[0,0],[0x41000000,0x40000000],[0x2e8,0x2e8])
    with pytest.raises(RuntimeError):module.War3Trainer.__new__(module.War3Trainer)._parse_native_helper_results(payload,3)
    assert after==before


def test_python_field_editor_batches_components_without_process_access():
    trainer=module.War3Trainer.__new__(module.War3Trainer);candidate=make_candidate(make_snapshot());memory=Mock()
    fields=[module.UnitMemoryField('armor','armor','f32',1,0,'defense',native_write=True,
                                   native_component_identity=(candidate.unit_address,candidate.handle)),
            module.UnitMemoryField('attack1_base1','attack','i32',5,0,'attack',native_write=True,
                                   native_component_identity=(0x123000,0x456000))]
    trainer._unit_fields_from_candidate=Mock(return_value=fields)
    def run(handle,ops):
        assert handle==candidate.native_snapshot.handle and [op[0] for op in ops]==[136,152,152]
        assert ops[1][1:4]==(0,candidate.unit_address,candidate.handle)
        assert ops[2][1:4]==(19,0x123000,0x456000)
        return [module.NativeHelperOpResult(136,1)]+[module.NativeHelperOpResult(152,op[4]) for op in ops[1:]]
    trainer._run_native_helper_ops=Mock(side_effect=run)
    result=trainer._write_unit_fields_to_candidate(memory,candidate,[module.MemoryWriteSpec('armor',0,'',8.0),
        module.MemoryWriteSpec('attack1_base1',0,'',-100)])
    assert [field.value for field in result]==[8.0,-100]
    assert memory.mock_calls==[];trainer._run_native_helper_ops.assert_called_once()


@pytest.mark.parametrize('value',[float('nan'),float('inf')])
def test_nonfinite_request_never_submits(value):
    trainer=module.War3Trainer.__new__(module.War3Trainer)
    field=module.UnitMemoryField('armor','armor','f32',1,0,'defense',native_write=True,native_component_identity=(1,2))
    with pytest.raises(ValueError):trainer._component_field_write_op(field,value)
