"""Production action dispatcher with fake native resources and full identities."""
import ctypes
from contextlib import nullcontext
import faulthandler
import os
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import war3_reforged_trainer as module
from test_native_identity_guard import HARNESS
from test_native_snapshot_binding import make_candidate,make_snapshot


ACTIONS=r'''
static uint8_t action_data[2][0xa8],action_wrappers[2][0x98];
static unsigned action_fault,action_present[2],action_levels[2],action_adds,action_removes,action_sets,action_lookups;
static const uint32_t action_ids[2]={0x41303031u,0x41303039u};
static uint64_t action_full(unsigned n) {return 0x554400000001ULL+n;}
static void action_check(uint64_t unit) {
    if(unit!=7 || *(uint64_t *)(object+0x18)!=full) ++bad_arguments;
}
static unsigned action_index(uint32_t id) {
    if(id==action_ids[1]) return 1;
    if(id!=action_ids[0]) ++bad_arguments;
    return 0;
}
static uint64_t action_agent(uint32_t slot,uint32_t serial) {
    uint64_t value=((uint64_t)serial<<32)|slot;
    for(unsigned n=0;n<2;++n) if(value==*(uint64_t *)(action_data[n]+0x18))
        return (uint64_t)(uintptr_t)action_wrappers[n];
    return fake_agent(slot,serial);
}
static uint64_t action_lookup(uint64_t unit,uint32_t id) {
    action_check(unit);++action_lookups;
    unsigned n=action_index(id);
    if(action_fault==26 && action_lookups==2) {
        ++*(uint64_t *)(action_data[n]+0x18);++*(uint64_t *)(action_wrappers[n]+0x20);
    }
    return action_present[n]?100+n:0;
}
static uint64_t action_resolve(uint64_t handle) {
    if(action_fault==19) return 1;
    return handle>=100 && handle<102 && action_present[handle-100]?(uint64_t)(uintptr_t)action_data[handle-100]:0;
}
static uint32_t action_id(uint64_t handle) {return handle>=100 && handle<102?action_ids[handle-100]:0;}
static int32_t action_level(uint64_t unit,uint32_t id) {
    action_check(unit);unsigned n=action_index(id);return action_present[n]?action_levels[n]:0;
}
static uint32_t action_add(uint64_t unit,uint32_t id) {
    action_check(unit);unsigned n=action_index(id);++action_adds;
    if(action_present[n]) ++bad_arguments;
    if(action_fault==5) return 0;
    action_present[n]=1;action_levels[n]=1;
    if(action_fault==6) ++*(uint64_t *)(object+0x18);
    if(action_fault==7) RaiseException(0xe0000001,0,0,NULL);
    return action_fault==8?0:1;
}
static uint32_t action_remove(uint64_t unit,uint32_t id) {
    action_check(unit);unsigned n=action_index(id);++action_removes;
    if(!action_present[n]) ++bad_arguments;
    if(action_fault==9) return 0;
    if(action_fault==11) RaiseException(0xe0000001,0,0,NULL);
    action_present[n]=0;
    if(action_fault==10) ++*(uint64_t *)(object+0x18);
    if(action_fault==12) RaiseException(0xe0000001,0,0,NULL);
    return 1;
}
static uint32_t action_set(uint64_t unit,uint32_t id,int32_t level) {
    action_check(unit);unsigned n=action_index(id);++action_sets;
    if(!action_present[n]) ++bad_arguments;
    if(action_fault!=14) action_levels[n]=action_fault==13?level-1:level;
    if(action_fault==15) {
        ++*(uint64_t *)(action_data[n]+0x18);++*(uint64_t *)(action_wrappers[n]+0x20);
    }
    if(action_fault==16) ++*(uint64_t *)(object+0x18);
    if(action_fault==17) RaiseException(0xe0000001,0,0,NULL);
    return action_fault==14?level:action_levels[n];
}
__declspec(dllexport) DWORD action_test(const wchar_t *directory,unsigned action,unsigned failure,unsigned initial,
                                        unsigned target,unsigned batch,unsigned *out) {
    NativeCommand cmd={0};DWORD bytes;HANDLE file;wchar_t path[MAX_PATH];
    wcscpy(test_directory,directory);command_path(path,MAX_PATH);DeleteFileW(path);
    ZeroMemory(object,sizeof(object));ZeroMemory(owner,sizeof(owner));
    ZeroMemory(action_data,sizeof(action_data));ZeroMemory(action_wrappers,sizeof(action_wrappers));
    action_fault=failure;action_adds=action_removes=action_sets=action_lookups=bad_arguments=fault=0;
    action_present[0]=initial;action_present[1]=0;action_levels[0]=3;action_levels[1]=0;
    *(uint64_t *)(object+0x18)=full;*(uint64_t *)(owner+0x20)=full;
    *(uint64_t *)(owner+0x18)=0x2b7733752b61676cULL;*(uint64_t *)(owner+0x90)=(uint64_t)(uintptr_t)object;
    for(unsigned n=0;n<2;++n) {
        uint8_t *data=action_data[n],*wrapper=action_wrappers[n];
        *(uint64_t *)(data+0x18)=*(uint64_t *)(wrapper+0x20)=action_full(n);
        *(uint64_t *)(data+0x68)=(uint64_t)(uintptr_t)object;
        *(uint32_t *)(data+0x70)=*(uint32_t *)(data+0x78)=action_ids[n];
        *(uint64_t *)(wrapper+0x18)=((uint64_t)action_ids[n]<<32)|0x2b61676cULL;
        *(uint64_t *)(wrapper+0x50)=(uint64_t)(uintptr_t)owner;
        *(uint64_t *)(wrapper+0x90)=(uint64_t)(uintptr_t)data;
    }
    g_persistent_agent_resolver=(uint64_t)(uintptr_t)action_agent;
    g_persistent_unit_resolver=(uint64_t)(uintptr_t)fake_unit;
    g_persistent_ability_resolver=(uint64_t)(uintptr_t)action_resolve;
    for(unsigned n=0;n<sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]);++n) {
        const char *name=g_persistent_native_names[n];g_persistent_natives[n].name=name;g_persistent_natives[n].handler=0;
        if(!strcmp(name,"BlzGetUnitAbility")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)action_lookup;
        if(!strcmp(name,"BlzGetAbilityId")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)action_id;
        if(!strcmp(name,"GetUnitAbilityLevel")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)action_level;
        if(!strcmp(name,"UnitAddAbility")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)action_add;
        if(!strcmp(name,"UnitRemoveAbility")) g_persistent_natives[n].handler=(uint64_t)(uintptr_t)action_remove;
        if(!strcmp(name,"SetUnitAbilityLevel")) g_persistent_natives[n].handler=failure==20?0:(uint64_t)(uintptr_t)action_set;
    }
    if(failure==1) ++*(uint64_t *)(object+0x18);
    if(failure==18) *(uint64_t *)(action_wrappers[0]+0x50)=0;
    if(failure==27) *(uint64_t *)(action_wrappers[0]+0x18)=0x41496e762b61676cULL;
    if(failure==29) *(uint64_t *)(action_wrappers[0]+0x18)&=0xffffffff00000000ULL;
    cmd.magic=WAR3_NATIVE_MAGIC;cmd.version=WAR3_NATIVE_VERSION;cmd.status=WAR3_NATIVE_STATUS_PENDING;
    cmd.op_count=batch?3:2;cmd.unit_handle=7;
    cmd.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;cmd.ops[0].handler=(uint64_t)(uintptr_t)object;
    cmd.ops[0].arg0=full;cmd.ops[0].arg1=(uint64_t)(uintptr_t)owner;
    cmd.ops[1].kind=WAR3_NATIVE_OP_MANAGE_BOUND_ABILITY;cmd.ops[1].rawcode=failure==24?0:action_ids[0];
    cmd.ops[1].handler=failure==22?5:action;cmd.ops[1].arg0=failure==23?100001:target;
    cmd.ops[1].arg1=failure==21?action_full(0)+100:failure==28?action_full(0):0;
    if(batch) {cmd.ops[2].kind=WAR3_NATIVE_OP_MANAGE_BOUND_ABILITY;cmd.ops[2].rawcode=action_ids[1];cmd.ops[2].handler=1;}
    file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_ALWAYS,0,NULL);
    if(file==INVALID_HANDLE_VALUE) return GetLastError();
    BOOL ok=WriteFile(file,&cmd,sizeof(cmd),&bytes,NULL);CloseHandle(file);
    if(!ok || bytes!=sizeof(cmd)) return ERROR_WRITE_FAULT;
    run_command();out[0]=action_adds;out[1]=action_removes;out[2]=action_sets;
    out[3]=action_present[0];out[4]=action_levels[0];out[5]=action_present[1];out[6]=bad_arguments;
    return 0;
}
'''


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler:pytest.skip('clang required')
    root=tmp_path_factory.mktemp('ability_actions');source=root/'test.c';library=root/'test.dll'
    source.write_text(HARNESS.replace('HELPER_SOURCE',(Path(__file__).parent/'tools/war3_native_helper.c').as_posix())+ACTIONS,encoding='utf8')
    subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(library),
                    '-luser32','-lkernel32'],check=True,capture_output=True,timeout=60)
    lib=ctypes.CDLL(str(library));lib.action_test.argtypes=[ctypes.c_wchar_p]+[ctypes.c_uint]*5+[ctypes.POINTER(ctypes.c_uint)]
    lib.action_test.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)


CASES=[ # action, fault, initial, level, batch, ok, adds, removes, sets
    (1,0,0,0,0,True,1,0,0),(1,0,1,0,0,True,0,0,0),(1,0,0,5,0,True,1,0,1),
    (1,0,1,5,0,True,0,0,1),(2,0,1,0,0,True,0,1,0),(2,0,0,0,0,True,0,0,0),
    (3,0,1,7,0,True,0,0,1),(3,0,0,7,0,False,0,0,0),(4,0,1,0,0,True,1,1,0),
    (4,0,0,0,0,True,1,0,0),(1,5,0,0,0,True,1,0,0),(4,5,1,0,0,True,1,1,0),
    (3,0,1,7,1,True,1,0,1),
] + [(1,f,0,0,1,False,1,0,0) for f in (6,7,8)] + [
    (2,f,1,0,1,False,0,1,0) for f in (9,10,11,12)
] + [(3,f,1,7,1,False,0,0,1) for f in (13,14,15,16,17)] + [
    (3,f,1,7,1,False,0,0,0) for f in (1,18,19,20,21,22,23,24,26,27,29)
] + [(2,28,0,0,1,False,0,0,0)]


@pytest.mark.parametrize('action,fault,initial,level,batch,ok,adds,removes,sets',CASES)
def test_native_action_identity_lifecycle_and_batch_stop(native,tmp_path,action,fault,initial,level,batch,ok,adds,removes,sets):
    out=(ctypes.c_uint*7)();enabled=faulthandler.is_enabled()
    if fault in (7,11,12,17) and enabled:faulthandler.disable()
    try:assert native.action_test(str(tmp_path)+'\\',action,fault,initial,level,batch,out)==0
    finally:
        if fault in (7,11,12,17) and enabled:faulthandler.enable()
    assert out[:3]==[adds,removes,sets] and out[6]==0
    payload=(tmp_path/f'war3_reforged_native_{os.getpid()}.bin').read_bytes()
    trainer=module.War3Trainer.__new__(module.War3Trainer)
    if ok:
        result=trainer._parse_native_helper_results(payload,3 if batch else 2)[1]
        expected=level if action==3 else initial if action==2 else 0 if fault==5 else int(not initial or action==4)
        assert result.result==expected
        if level:assert result.arg1==out[4]==level
        if action==4:assert out[3]==(fault!=5)
    else:
        with pytest.raises(RuntimeError):trainer._parse_native_helper_results(payload,3 if batch else 2)
        assert out[5]==0 # a failed operation never starts the following add
        if fault in (13,14):
            with pytest.raises(RuntimeError,match='requested_level=7 actual_level='):
                trainer._parse_native_helper_results(payload,3)
        if fault in (16,17):
            with pytest.raises(RuntimeError,match='actual_level=unavailable'):
                trainer._parse_native_helper_results(payload,3)


@pytest.fixture
def trainer():
    trainer=module.War3Trainer.__new__(module.War3Trainer);candidate=make_candidate(make_snapshot())
    trainer._direct_selected_context=Mock(return_value=(candidate,candidate.native_snapshot.handle))
    trainer._elephant_handlers=Mock(side_effect=AssertionError('legacy discovery'))
    trainer._process_memory=Mock(side_effect=AssertionError('external memory'))
    def respond(handle,ops):
        return [module.NativeHelperOpResult(136,1)]+[module.NativeHelperOpResult(156,level if action==3 else 1,arg1=level or 1)
                                                   for _,_,action,level,_ in ops[1:]]
    trainer._run_native_helper_ops=Mock(side_effect=respond)
    return trainer,candidate


def test_ui_actions_and_bundles_pin_one_unit_without_scans_or_waits(trainer):
    t,c=trainer
    with patch.object(module.time,'sleep',side_effect=AssertionError('fixed wait')):
        t.add_ability_to_selected_unit('A001');t.remove_ability_from_selected_unit('A001')
        t.reset_selected_unit_ability('A001');assert t.set_selected_unit_ability_level('A001',7)==7
        assert t.add_ability_bundle_to_selected_unit([('A001',3)]*32)==(32,32)
    calls=t._run_native_helper_ops.call_args_list
    assert [len(call.args[1])-1 for call in calls]==[1,1,1,1,15,15,2]
    assert t._direct_selected_context.call_count==5
    for call in calls:
        handle,ops=call.args
        assert handle==c.native_snapshot.handle and ops[0]==(136,0,c.unit_address,c.handle,c.owner_address)
    assert [call.args[1][1][2] for call in calls[:4]]==[1,2,4,3]


def test_remove_all_pins_each_enumerated_ability_generation(trainer):
    t,c=trainer;t._process_memory=Mock(return_value=nullcontext(Mock()))
    t._ability_instances_from_candidate=Mock(return_value=[SimpleNamespace(rawcode=0x41303031,handle=0x123456789)])
    assert t.remove_all_selected_unit_abilities()==1
    assert t._run_native_helper_ops.call_args.args[1][1]==(156,0x41303031,2,0,0x123456789)


def test_bad_later_entry_and_failed_batch_do_not_start_more_work(trainer):
    t,c=trainer
    with pytest.raises(ValueError):t.add_ability_bundle_to_selected_unit([('A001',2),('A002',0)])
    t._direct_selected_context.assert_not_called();t._run_native_helper_ops.assert_not_called()
    t._run_native_helper_ops.side_effect=RuntimeError('recycled unit')
    with pytest.raises(RuntimeError):t.add_abilities_to_selected_unit(['A001']*32)
    assert t._run_native_helper_ops.call_count==1


def test_direct_effect_uses_bound_native_identity_and_no_controller_discovery(trainer):
    t,c=trainer
    t._run_native_helper_ops=Mock(return_value=[
        module.NativeHelperOpResult(136,1),
        module.NativeHelperOpResult(157,1),
    ])
    assert t._run_direct_selected_ability_locked(
        'A001',t.NATIVE_HELPER_OP_DIRECT_ABILITY_IMMEDIATE,0x998,0
    )==1
    t._process_memory.assert_not_called()
    t._elephant_handlers.assert_not_called()
    handle,ops=t._run_native_helper_ops.call_args.args
    assert handle==c.native_snapshot.handle
    assert ops==(
        (136,0,c.unit_address,c.handle,c.owner_address),
        (157,0x41303031,2,0,0),
    )


@pytest.mark.parametrize('kind,offset,packed,effect,x,y',[
    (101,0xA70,0,1,0,0),(102,0x998,0,2,0,0),
    (103,0xA58,0xC080000041400000,3,0x41400000,0xC0800000),(104,0xA78,0,4,0,0),
])
def test_direct_effect_arguments_preserve_pointer_free_payload(trainer,kind,offset,packed,effect,x,y):
    t,c=trainer
    t._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(157,1)])
    with patch.object(module.time,'sleep',side_effect=AssertionError('fixed wait')):
        assert t._run_direct_selected_ability_locked('A001',kind,offset,packed)==1
    assert t._run_native_helper_ops.call_args.args[1][1]==(157,0x41303031,effect,x,y)


@pytest.mark.parametrize('result',[
    [],[module.NativeHelperOpResult(136,1)],
    [module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(157,0)],
    [module.NativeHelperOpResult(136,0),module.NativeHelperOpResult(157,1)],
    [module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(102,1)],
    [module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(157,1,last_error=13)],
])
def test_direct_effect_rejects_incomplete_response(trainer,result):
    t,c=trainer;t._run_native_helper_ops=Mock(return_value=result)
    with pytest.raises(RuntimeError,match='Incomplete direct'):
        t._run_direct_selected_ability_locked('A001',102,0x998,0)


def test_direct_effect_rejects_wrong_callback_type_before_query(trainer):
    t,c=trainer
    with pytest.raises(ValueError):t._run_direct_selected_ability_locked('A001',102,0xA70,0)
    t._direct_selected_context.assert_not_called()
