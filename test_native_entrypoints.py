"""Cold native lookup and public vital writes without external memory contexts."""
from dataclasses import replace
from unittest.mock import Mock

import pytest
import war3_reforged_trainer as module
from test_native_snapshot_binding import make_snapshot, snapshot_result


@pytest.mark.parametrize('cls',[module.War3Trainer,module.BackupReadWar3Trainer])
def test_cold_compatibility_lookup_requests_only_missing_required_names(cls):
    subject=cls.__new__(cls)
    subject._native_handlers={}
    subject.persistent_native_init=Mock()
    subject._process_memory=Mock(side_effect=AssertionError('External lookup'))
    wanted=('CreateUnit','BlzGetItemIntegerField')
    indices={module.NATIVE_INDEX[name] for name in wanted}
    def query(handle,ops):
        assert handle==0 and len(ops)==2
        assert {op[1] for op in ops}==indices
        assert all(op[0]==140 and op[2:]==(0,module.NATIVE_PROFILE_ID,0) for op in ops)
        return [module.NativeHelperOpResult(140,0x200000+op[1]*0x100) for op in ops]
    subject._run_native_helper_ops=Mock(side_effect=query)
    for _ in range(2):
        found=subject._elephant_handlers(None,iter((*wanted,wanted[0])))
        assert tuple(found)==wanted
        assert all(found[name].handler_address==0x200000+module.NATIVE_INDEX[name]*0x100 for name in wanted)
    subject._run_native_helper_ops.assert_called_once() # warm lookup does not resubmit
    subject._process_memory.assert_not_called()


@pytest.mark.parametrize('cls',[module.War3Trainer,module.BackupReadWar3Trainer])
@pytest.mark.parametrize('pinned',[False,True])
@pytest.mark.parametrize('changed',[False,True])
def test_public_vital_write_keeps_full_native_identity_without_opening_memory(cls,pinned,changed):
    subject=cls.__new__(cls);snapshot=make_snapshot();state=[snapshot]
    subject._unit_owner_index={};subject._last_persistent_native_snapshots=()
    subject._process_memory=Mock(side_effect=AssertionError('External memory'))
    subject._candidate_from_identity=Mock(side_effect=AssertionError('Old object scan'))
    subject.persistent_native_init=Mock()
    subject.persistent_native_selected_snapshots=Mock(return_value=(snapshot,))
    subject._query_native_table_handlers=Mock(side_effect=lambda names:{
        name:module.NativeHandler(name,0,0x200000+n*0x100) for n,name in enumerate(names)})
    mutations=[]
    def run(handle,ops):
        if ops[0][0] in (133,155):
            assert handle==(0 if ops[0][0]==155 else snapshot.handle)
            assert ops[0][2:]==(snapshot.unit_address,snapshot.full_handle,snapshot.owner_address)
            current=replace(state[0],full_handle=snapshot.full_handle+1) if changed else state[0]
            return [snapshot_result(current)]
        assert handle==snapshot.handle
        assert ops[0]==(136,0,snapshot.unit_address,snapshot.full_handle,snapshot.owner_address)
        mutations.append(ops)
        state[0]=replace(snapshot,hp=150)
        return [module.NativeHelperOpResult(op[0],1) for op in ops]
    subject._run_native_helper_ops=Mock(side_effect=run)
    def action():
        if pinned:
            return subject.set_unit_by_identity_win10(snapshot.full_handle,snapshot.owner_address,snapshot.unit_address,
                                                      snapshot.hp,snapshot.mp,150,None)
        return subject.set_selected_unit(snapshot.hp,snapshot.mp,150,None)
    if changed:
        with pytest.raises(RuntimeError):action()
        assert not mutations
    else:
        candidate=action()
        assert candidate.native_snapshot.hp==150 and len(mutations)==1
        assert (candidate.handle,candidate.owner_address,candidate.unit_address)==(
            snapshot.full_handle,snapshot.owner_address,snapshot.unit_address)
    if pinned:subject.persistent_native_selected_snapshots.assert_not_called()
    else:subject.persistent_native_selected_snapshots.assert_called_once_with()
    subject._process_memory.assert_not_called();subject._candidate_from_identity.assert_not_called()


def test_native_function_verification_does_not_open_memory():
    subject=module.War3Trainer.__new__(module.War3Trainer)
    subject._process_memory=Mock(side_effect=AssertionError('External context'))
    subject._query_native_table_handlers=Mock(return_value={})
    assert subject.verify_native_handlers()=={}
    subject._query_native_table_handlers.assert_called_once_with(subject.NATIVE_HANDLER_NAMES)
    subject._process_memory.assert_not_called()


@pytest.mark.parametrize('cls', [module.War3Trainer, module.BackupReadWar3Trainer])
@pytest.mark.parametrize('failure', ['none', 'reused', 'helper'])
def test_candidate_refresh_resolves_remembered_identity_without_external_reads(cls, failure):
    subject = cls.__new__(cls)
    selected = make_snapshot()
    remembered = replace(selected, handle=2, full_handle=0x200000002,
                         owner_address=0x5000, unit_address=0x4000, hp=75)
    subject._unit_owner_index = {}
    subject._last_persistent_native_snapshots = ()
    subject.persistent_native_init = Mock()
    subject.persistent_native_selected_snapshots = Mock(return_value=(selected,))
    subject._process_memory = Mock(side_effect=AssertionError('external memory'))
    subject._candidate_from_identity = Mock(side_effect=AssertionError('legacy identity'))
    subject._selected_components = Mock(side_effect=AssertionError('component scan'))
    subject._native_unit_field_memory = Mock(return_value=Mock(components={}, inventory_items=[]))
    returned = replace(remembered, full_handle=remembered.full_handle + 1) if failure == 'reused' else remembered
    subject._run_native_helper_ops = Mock(return_value=[snapshot_result(returned)])
    if failure == 'helper':
        subject._run_native_helper_ops.side_effect = RuntimeError('helper unavailable')
    identity = (remembered.full_handle, remembered.owner_address, remembered.unit_address)
    if failure == 'none':
        summaries = subject.list_selection_candidates(extra_identities=[identity])
        assert [summary.hp_text for summary in summaries] == ['100/200', '75/200']
        assert summaries[1].candidate.native_snapshot == remembered
    else:
        with pytest.raises(RuntimeError):
            subject.list_selection_candidates(extra_identities=[identity])
    subject._run_native_helper_ops.assert_called_once_with(
        0, ((subject.NATIVE_HELPER_OP_IDENTITY_UNIT_SNAPSHOT, 0,
             remembered.unit_address, remembered.full_handle, remembered.owner_address),))
    subject._process_memory.assert_not_called()
    subject._candidate_from_identity.assert_not_called()
    subject._selected_components.assert_not_called()
