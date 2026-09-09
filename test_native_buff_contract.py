"""Exact captured buff ABI plus isolated native invocation and identity checks."""
import ctypes
import faulthandler
import json
from pathlib import Path
import shutil
import subprocess
from unittest.mock import Mock

import pytest
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
import war3_reforged_trainer as module
from test_native_identity_guard import HARNESS
from test_native_ability_actions import ACTIONS
from test_native_snapshot_binding import make_candidate, make_snapshot

ROOT=Path(__file__).parent
CONTRACT=json.loads((ROOT/'tools/native-buff-contract-23745.json').read_text())


@pytest.mark.parametrize('base',[0,0x7ff700000000])
def test_captured_effect_proves_constructor_and_four_argument_call(base):
    ctor,effect=CONTRACT['contracts'];md=Cs(CS_ARCH_X86,CS_MODE_64)
    ins=list(md.disasm(bytes.fromhex(effect['code']),base+effect['rva']))
    call=next(i for i in ins if i.address==base+CONTRACT['constructor_call_rva'])
    assert call.mnemonic=='call' and int(call.op_str,16)==base+ctor['rva']
    idx=next(n for n,i in enumerate(ins) if i.address==base+CONTRACT['buff_call_rva'])
    assert [(i.mnemonic,i.op_str) for i in ins[idx-3:idx+1]]==[
        ('lea','r8, [rbp - 0x50]'),('mov','rdx, rdi'),('mov','rcx, rsi'),('call','rbx')]
    assert any(i.mnemonic=='mov' and i.op_str=='rbx, qword ptr [rax + 0xa00]' for i in ins[:idx])


def test_profiles_cover_entire_captured_bodies():
    header=(ROOT/'tools/war3_native_buff_profile.h').read_text()
    for row in CONTRACT['contracts']:
        code=bytes.fromhex(row['code']);value=14695981039346656037
        for byte in code:value=((value^byte)*1099511628211)&0xffffffffffffffff
        assert len(code)==row['size'] and value==row['fnv64']
        assert f'0x{value:016x}ULL' in header
        assert f"SIZE {len(code)}u" in header


BUFF=r'''
static uint64_t buff_vtable[0xa08/8];
static unsigned buff_fault,buff_calls,buff_constructs;
static void buff_construct(War3BuffData *data,uint64_t ability,uint32_t index) {
    if(ability!=(uint64_t)(uintptr_t)action_data[0] || index) ++bad_arguments;
    ++buff_constructs;data->alias=0x42303031;data->duration=4;data->hero_duration=8;data->addon=-1;
    if(buff_fault==1) ++*(uint64_t *)(object+0x18);
    if(buff_fault==2) {++*(uint64_t *)(action_data[0]+0x18);++*(uint64_t *)(action_wrappers[0]+0x20);}
    if(buff_fault==3) buff_vtable[0xa00/8]=0;
    if(buff_fault==4) RaiseException(0xe0000001,0,0,NULL);
    if(buff_fault==5) ++action_levels[0];
    if(buff_fault==6) {data->duration=0;data->hero_duration=0;}
    if(buff_fault==7) data->hero_duration=5000;
}
static void buff_apply(uint64_t ability,uint64_t target,War3BuffData *data,float *duration) {
    if(ability!=(uint64_t)(uintptr_t)action_data[0] || target!=(uint64_t)(uintptr_t)object ||
       data->alias!=0x42303031 || data->addon!=-1 || *duration!=(buff_fault==6?10:buff_fault==7?3600:8)) ++bad_arguments;
    ++buff_calls;
}
__declspec(dllexport) DWORD buff_test(const wchar_t *directory,unsigned failure,unsigned *out) {
    unsigned ignored[7];DWORD error=action_test(directory,1,0,1,0,0,ignored);if(error) return error;
    buff_fault=failure;buff_calls=buff_constructs=bad_arguments=0;
    ZeroMemory(buff_vtable,sizeof(buff_vtable));buff_vtable[0xa00/8]=(uint64_t)(uintptr_t)buff_apply;
    *(uint64_t *)action_data[0]=(uint64_t)(uintptr_t)buff_vtable;
    NativeCommand cmd={0};cmd.op_count=2;cmd.unit_handle=7;
    cmd.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;cmd.ops[0].handler=(uint64_t)(uintptr_t)object;
    cmd.ops[0].arg0=full;cmd.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    uint64_t values[10];error=war3_action_ability_state(&cmd,action_ids[0],values);if(error) return error;
    __try {error=war3_invoke_bound_buff(&cmd,action_ids[0],values,(uint64_t)(uintptr_t)buff_construct,(uint64_t)(uintptr_t)buff_apply);}
    __except(EXCEPTION_EXECUTE_HANDLER) {error=GetExceptionCode();}
    out[0]=buff_constructs;out[1]=buff_calls;out[2]=bad_arguments;return error;
}
__declspec(dllexport) DWORD buff_contract_test(const unsigned char *ctor,const unsigned char *effect,unsigned failure) {
    size_t size=WAR3_ROAR_EFFECT_RVA+WAR3_ROAR_EFFECT_SIZE;
    uint8_t *image=VirtualAlloc(NULL,size,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE);
    if(!image) return ERROR_OUTOFMEMORY;
    memcpy(image+WAR3_BUFF_DATA_CONSTRUCTOR_RVA,ctor,WAR3_BUFF_DATA_CONSTRUCTOR_SIZE);
    memcpy(image+WAR3_ROAR_EFFECT_RVA,effect,WAR3_ROAR_EFFECT_SIZE);
    if(failure==1) image[WAR3_BUFF_DATA_CONSTRUCTOR_RVA+100]^=1;
    if(failure==2) image[WAR3_ROAR_EFFECT_RVA+100]^=1;
    uint64_t out=0;DWORD old,error;
    if(failure==4) VirtualProtect(image,size,PAGE_READWRITE,&old);
    error=war3_buff_constructor((uint64_t)(uintptr_t)image,(uint64_t)(uintptr_t)(image+WAR3_ROAR_EFFECT_RVA+(failure==3?1:0)),&out);
    if(!error && out!=(uint64_t)(uintptr_t)(image+WAR3_BUFF_DATA_CONSTRUCTOR_RVA)) error=ERROR_INVALID_DATA;
    if(error && out) error=0; /* failure must not publish a callback */
    VirtualFree(image,0,MEM_RELEASE);return error;
}
'''


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler:pytest.skip('clang required')
    root=tmp_path_factory.mktemp('buff');source=root/'test.c';dll=root/'test.dll'
    source.write_text(HARNESS.replace('HELPER_SOURCE',(ROOT/'tools/war3_native_helper.c').as_posix())+ACTIONS+BUFF,encoding='utf8')
    build=subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(dll),'-luser32','-lkernel32'],capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    lib=ctypes.CDLL(str(dll));lib.buff_test.argtypes=[ctypes.c_wchar_p,ctypes.c_uint,ctypes.POINTER(ctypes.c_uint)]
    lib.buff_test.restype=ctypes.c_uint;lib.buff_contract_test.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_uint];lib.buff_contract_test.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)


@pytest.mark.parametrize('fault',range(8))
def test_constructor_callback_checks_and_buff_arguments(native,tmp_path,fault):
    out=(ctypes.c_uint*3)();enabled=faulthandler.is_enabled()
    if enabled:faulthandler.disable()
    try:error=native.buff_test(str(tmp_path)+'\\',fault,out)
    finally:
        if enabled:faulthandler.enable()
    assert bool(error)==(fault in (1,2,3,4,5))
    assert list(out)==[1,0 if error else 1,0]


@pytest.mark.parametrize('fault',range(5))
def test_exact_runtime_contract_validates_all_bytes_and_execute_access(native,fault):
    ctor,effect=[bytes.fromhex(r['code']) for r in CONTRACT['contracts']]
    assert bool(native.buff_contract_test(ctor,effect,fault))==bool(fault)


def test_roar_entry_uses_native_transaction_without_controller_memory():
    t=module.War3Trainer.__new__(module.War3Trainer);c=make_candidate(make_snapshot())
    t._direct_selected_context=Mock(return_value=(c,c.native_snapshot.handle))
    t._process_memory=Mock(side_effect=AssertionError('external vtable discovery'))
    t._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(157,1)])
    assert t._apply_direct_roar_buff_to_selected_unit_locked('ANht')==1
    assert t._run_native_helper_ops.call_args.args==(c.native_snapshot.handle,(
        (136,0,c.unit_address,c.handle,c.owner_address),(157,0x414e6874,5,0,0)))
