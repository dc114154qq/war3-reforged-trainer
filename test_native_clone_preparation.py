"""Prepare clone descriptors from one native snapshot, never component scans."""
from dataclasses import replace
import threading
from unittest.mock import Mock
import pytest
import war3_reforged_trainer as module
from test_native_selected_context import trainer
from test_native_snapshot_binding import make_candidate


@pytest.mark.parametrize('mask',[0,1,2,3,12,15])
@pytest.mark.parametrize('preserve',[False,True])
def test_clone_uses_bound_component_mask_and_one_transaction(trainer,mask,preserve):
    initial=trainer.persistent_native_selected_snapshots.return_value[0]
    original=replace(initial,component_mask=mask,hero_level=5 if mask&2 else 0)
    trainer.persistent_native_selected_snapshots.return_value=(original,)
    trainer._selected_components=Mock(side_effect=AssertionError('External component lookup'))
    trainer._elephant_handlers=Mock(side_effect=AssertionError('Legacy handler preparation'))
    def query(names):
        # A changing selection during preparation must not change either flags
        # or the already selected handle.
        trainer.persistent_native_selected_snapshots.return_value=(replace(initial,handle=17,component_mask=15-mask),)
        return {name:module.NativeHandler(name,0,0x200000+n*0x100) for n,name in enumerate(names)}
    trainer._query_native_table_handlers=Mock(side_effect=query)
    trainer._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(118,0x9900)]+[module.NativeHelperOpResult(trainer.NATIVE_HELPER_OP_JASS_MULTI_ARG,0)]*13)
    assert trainer.create_local_unit(None,(12,-4),preserve_owner=preserve)==(original.type_id,0x9900)
    handle,ops=trainer._run_native_helper_ops.call_args.args
    assert handle==original.handle and len(ops)==15 and ops[1][0]==118
    flags=(1 if mask&2 else 0)|(2 if mask&1 else 0)|(4 if preserve else 0)
    assert ops[2][1]==flags
    assert ops[0]==(136,0,original.unit_address,original.full_handle,original.owner_address)
    names=trainer._query_native_table_handlers.call_args.args[0]
    assert ('GetOwningPlayer' in names)==preserve and ('GetLocalPlayer' in names)!=preserve
    assert ('UnitAddItemById' in names)==bool(mask&1)
    trainer.persistent_native_selected_snapshots.assert_called_once_with()
    trainer._process_memory.assert_not_called();trainer._selected_components.assert_not_called()
    trainer._elephant_handlers.assert_not_called()
    trainer._native_helper_command_path=Mock(return_value='offline-command');trainer._write_native_helper_command=Mock()
    trainer._native_helper_batch_hook=1;trainer._native_helper_batch_thread_id=threading.get_ident();trainer._wait_native_helper_result=Mock(return_value=[])
    trainer._run_native_helper_ops_locked(handle,ops)
    payload=trainer._write_native_helper_command.call_args.args[1]
    base=trainer.NATIVE_HELPER_HEADER_STRUCT.size;size=trainer.NATIVE_HELPER_OP_STRUCT.size
    assert [trainer.NATIVE_HELPER_OP_STRUCT.unpack_from(payload,base+i*size)[:5] for i in range(15)]==list(ops)


@pytest.mark.parametrize('mismatch',[False,True])
def test_absent_or_mismatched_native_identity_does_not_silently_downgrade_clone(trainer,mismatch):
    original=trainer.persistent_native_selected_snapshots.return_value[0]
    candidate=make_candidate(original)
    if not mismatch:candidate=replace(candidate,native_snapshot=None,selection_source='memory')
    trainer._direct_selected_context=Mock(return_value=(candidate,17 if mismatch else original.handle))
    trainer._query_native_table_handlers=Mock(side_effect=AssertionError('Do not query after invalid source'))
    trainer._run_native_helper_ops=Mock(side_effect=AssertionError('Do not create'))
    with pytest.raises(RuntimeError,match='original native unit snapshot'):trainer.create_local_unit(None,(12,-4))
    trainer._run_native_helper_ops.assert_not_called()


def test_explicit_creation_needs_no_selection_or_external_context(trainer):
    trainer.persistent_native_selected_snapshots.side_effect=AssertionError('Unrequested source selection')
    trainer._query_native_table_handlers=Mock(return_value={name:module.NativeHandler(name,0,0x200000+n*0x100)
                                                         for n,name in enumerate(('GetLocalPlayer','CreateUnit'))})
    trainer._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(trainer.NATIVE_HELPER_OP_JASS_CREATE_LOCAL_UNIT,0x9900)])
    assert trainer.create_local_unit('hfoo',(12,-4))==(0x68666f6f,0x9900)
    trainer._query_native_table_handlers.assert_called_once_with(('GetLocalPlayer','CreateUnit'))
    assert trainer._run_native_helper_ops.call_args.args[0]==0
    trainer._process_memory.assert_not_called()


@pytest.mark.parametrize('failure',['short','wrong_kind','error','empty_target'])
def test_clone_rejects_incomplete_or_failed_helper_results(trainer,failure):
    trainer._query_native_table_handlers=Mock(side_effect=lambda names:{
        name:module.NativeHandler(name,0,0x200000+n*0x100) for n,name in enumerate(names)})
    response=[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(118,0x9900)]+[
        module.NativeHelperOpResult(trainer.NATIVE_HELPER_OP_JASS_MULTI_ARG,0)]*13
    if failure=='short':response.pop()
    elif failure=='wrong_kind':response[1]=module.NativeHelperOpResult(80,0x9900)
    elif failure=='error':response[-1]=module.NativeHelperOpResult(trainer.NATIVE_HELPER_OP_JASS_MULTI_ARG,0,last_error=6)
    else:response[1]=module.NativeHelperOpResult(118,0)
    trainer._run_native_helper_ops=Mock(return_value=response)
    with pytest.raises(RuntimeError):trainer.create_local_unit(None,(12,-4))
