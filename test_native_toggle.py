"""Toggle requests use real dispatch, identity checks and guarded visibility."""
import ctypes
import faulthandler
from pathlib import Path
import shutil
import subprocess
from unittest.mock import Mock

import pytest
import war3_reforged_trainer as module
from test_native_identity_guard import HARNESS
from test_native_ability_actions import ACTIONS
from test_native_snapshot_binding import make_candidate,make_snapshot

TOGGLE=r'''
static unsigned toggle_fault,toggle_issues,toggle_hides,toggle_shows,toggle_hidden;
static void toggle_hide(uint64_t unit,int32_t id,uint32_t flag) {
    action_check(unit);if((uint32_t)id!=action_ids[0] || flag>1) ++bad_arguments;
    if(flag) ++toggle_hides;else ++toggle_shows;toggle_hidden=flag;
    if(toggle_fault==31 && !flag) ++*(uint64_t *)(object+0x18);
    if(toggle_fault==32 && !flag) {++*(uint64_t *)(action_data[0]+0x18);++*(uint64_t *)(action_wrappers[0]+0x20);}
    if(toggle_fault==33 && !flag) RaiseException(0xe0000001,0,0,NULL);
    if(toggle_fault==34 && flag) RaiseException(0xe0000001,0,0,NULL);
}
static uint32_t toggle_issue(uint64_t unit,int32_t order) {
    action_check(unit);if(order!=852589 || toggle_hidden) ++bad_arguments;++toggle_issues;
    if(toggle_fault==35) return 0;
    if(toggle_fault==36) RaiseException(0xe0000001,0,0,NULL);
    if(toggle_fault==37) ++*(uint64_t *)(object+0x18);
    if(toggle_fault==38) {++*(uint64_t *)(action_data[0]+0x18);++*(uint64_t *)(action_wrappers[0]+0x20);}
    return 1;
}
__declspec(dllexport) DWORD toggle_test(const wchar_t *directory,unsigned initial,unsigned failure,unsigned twice,unsigned *out) {
    unsigned ignored[7];DWORD error=action_test(directory,1,0,1,0,0,ignored);if(error) return error;
    while(g_managed_toggles) {War3ManagedToggle *old=g_managed_toggles;g_managed_toggles=old->next;HeapFree(GetProcessHeap(),0,old);}
    action_present[0]=initial;action_adds=action_removes=action_lookups=bad_arguments=0;
    action_fault=failure<30?failure:0;toggle_fault=failure;
    toggle_issues=toggle_hides=toggle_shows=toggle_hidden=0;
    for(unsigned n=0;n<sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]);++n) {
        const char *name=g_persistent_natives[n].name;
        if(!strcmp(name,"BlzUnitHideAbility")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)toggle_hide;
        if(!strcmp(name,"IssueImmediateOrderById")) g_persistent_natives[n].handler=failure==39?0:(uint64_t)(uintptr_t)toggle_issue;
    }
    NativeCommand original={0},cmd;wchar_t path[MAX_PATH];DWORD bytes;
    original.magic=WAR3_NATIVE_MAGIC;original.version=WAR3_NATIVE_VERSION;original.status=WAR3_NATIVE_STATUS_PENDING;
    original.op_count=2;original.unit_handle=7;
    original.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;original.ops[0].handler=(uint64_t)(uintptr_t)object;
    original.ops[0].arg0=full;original.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    original.ops[1].kind=WAR3_NATIVE_OP_ENABLE_BOUND_TOGGLE;original.ops[1].rawcode=action_ids[0];
    original.ops[1].handler=failure==40?0:failure==41?0x80000000ULL:852589;
    for(unsigned pass=0;pass<(twice?2u:1u);++pass) {
        if(pass && twice==2) { /* same JASS slot/rawcode, different instance */
            ++*(uint64_t *)(action_data[0]+0x18);++*(uint64_t *)(action_wrappers[0]+0x20);toggle_hidden=0;
        }
        if(pass && twice==3) toggle_fault=35; /* previously hidden, second order rejected */
        cmd=original;command_path(path,MAX_PATH);
        HANDLE file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_ALWAYS,0,NULL);
        if(file==INVALID_HANDLE_VALUE) return GetLastError();
        BOOL ok=WriteFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);if(!ok) return ERROR_WRITE_FAULT;
        run_command();file=CreateFileW(path,GENERIC_READ,0,NULL,OPEN_EXISTING,0,NULL);
        if(file==INVALID_HANDLE_VALUE) return GetLastError();
        ok=ReadFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);if(!ok) return ERROR_READ_FAULT;
        if(!pass) out[10]=cmd.status;
        if(cmd.status!=WAR3_NATIVE_STATUS_OK) break;
    }
    out[0]=cmd.status;out[1]=cmd.last_error;out[2]=cmd.ops[1].reserved;
    out[3]=action_adds;out[4]=action_removes;out[5]=toggle_shows;out[6]=toggle_issues;out[7]=toggle_hides;
    out[8]=action_present[0];out[9]=bad_arguments;out[11]=toggle_hidden;
    return 0;
}
'''

@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler:pytest.skip('clang required')
    root=tmp_path_factory.mktemp('toggle');source=root/'test.c';dll=root/'test.dll'
    source.write_text(HARNESS.replace('HELPER_SOURCE',(Path(__file__).parent/'analysis/fixtures/legacy-native-helper.c').as_posix())+ACTIONS+TOGGLE,encoding='utf8')
    build=subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(dll),'-luser32','-lkernel32'],capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    lib=ctypes.CDLL(str(dll));lib.toggle_test.argtypes=[ctypes.c_wchar_p]+[ctypes.c_uint]*3+[ctypes.POINTER(ctypes.c_uint)];lib.toggle_test.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)

def run(native,tmp_path,initial=0,fault=0,twice=0):
    out=(ctypes.c_uint*12)();enabled=faulthandler.is_enabled()
    if enabled:faulthandler.disable()
    try:assert native.toggle_test(str(tmp_path)+'\\',initial,fault,twice,out)==0
    finally:
        if enabled:faulthandler.enable()
    assert out[9]==0,'wrong arguments, issuing while hidden, or stale unit mutation'
    return list(out)

@pytest.mark.parametrize('initial,twice,counts',[
    (0,0,[1,0,1,1,1]),(1,0,[0,0,0,1,0]),(0,1,[1,0,2,2,2]),(1,1,[0,0,0,2,0]),
    (0,2,[1,0,1,2,1]),
])
def test_enable_always_issues_and_only_hides_its_own_instance(native,tmp_path,initial,twice,counts):
    out=run(native,tmp_path,initial=initial,twice=twice)
    assert out[0]==2 and out[1]==out[2]==0 and out[8]==1
    assert out[3:8]==counts

@pytest.mark.parametrize('fault,counts,cleanup',[
    (5,[1,0,0,0,0],False),(6,[1,0,0,0,0],True),(7,[1,0,0,0,0],True),(8,[1,0,0,0,0],True),
    (31,[1,0,1,0,0],True),(32,[1,0,1,0,0],True),(33,[1,1,1,0,0],False),
    (34,[1,1,1,1,1],False),(35,[1,1,1,1,0],False),(36,[1,1,1,1,0],False),
    (37,[1,0,1,1,0],True),(38,[1,0,1,1,0],True),
    (39,[0,0,0,0,0],False),(40,[0,0,0,0,0],False),(41,[0,0,0,0,0],False),
])
def test_failure_stops_chain_and_cleans_only_created_ability(native,tmp_path,fault,counts,cleanup):
    out=run(native,tmp_path,fault=fault)
    assert out[0]==3 and out[1]!=0 and bool(out[2])==cleanup
    assert out[3:8]==counts

def test_existing_owned_toggle_is_rehidden_when_repeated_order_fails(native,tmp_path):
    out=run(native,tmp_path,twice=3)
    assert out[10]==2 and out[0]==3 and out[2]==0
    assert out[3:8]==[1,0,2,2,2] and out[8]==out[11]==1

def test_existing_user_ability_is_not_deleted_after_order_failure(native,tmp_path):
    out=run(native,tmp_path,initial=1,fault=35)
    assert out[0]==3 and out[3:8]==[0,0,0,1,0] and out[8]==1

def test_python_entry_sends_one_bound_command_each_time():
    t=module.War3Trainer.__new__(module.War3Trainer);c=make_candidate(make_snapshot())
    t._direct_selected_context=Mock(return_value=(c,c.native_snapshot.handle))
    t._process_memory=Mock(side_effect=AssertionError('external discovery'))
    t._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(161,1)])
    for _ in range(2):assert t._enable_selected_toggle_ability_locked('ANms',852589)==1
    assert t._run_native_helper_ops.call_count==2
    assert t._run_native_helper_ops.call_args.args==(c.native_snapshot.handle,(
        (136,0,c.unit_address,c.handle,c.owner_address),(161,0x414e6d73,852589,0,0)))

@pytest.mark.parametrize('order',[0,-1,0x80000000])
def test_invalid_order_is_rejected_before_reading_selection(order):
    t=module.War3Trainer.__new__(module.War3Trainer);t._direct_selected_context=Mock()
    with pytest.raises(ValueError):t._enable_selected_toggle_ability_locked('ANms',order)
    t._direct_selected_context.assert_not_called()
