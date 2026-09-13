"""Both controller editions use one native selection and the actual JASS handle."""
from dataclasses import replace
from contextlib import nullcontext
import threading
from unittest.mock import Mock

import pytest
import war3_reforged_trainer as module
from test_native_snapshot_binding import make_snapshot


@pytest.fixture(params=[module.War3Trainer, module.BackupReadWar3Trainer])
def trainer(request):
    t=request.param.__new__(request.param)
    t._elephant_selection_override=None
    t._unit_owner_index={}
    t._last_persistent_native_snapshots=()
    t._process_memory=Mock(side_effect=AssertionError('selection must not open an external memory backend'))
    t._candidate_from_identity=Mock(side_effect=AssertionError('legacy object lookup'))
    t.persistent_native_selected_snapshots=Mock(return_value=(make_snapshot(),))
    return t


def test_context_returns_jass_handle_and_generation_from_same_snapshot(trainer):
    candidate,handle=trainer._direct_selected_context()
    native=make_snapshot()
    assert handle==native.handle and handle!=native.full_handle
    assert candidate.handle==native.full_handle and candidate.native_snapshot==native
    trainer.persistent_native_selected_snapshots.assert_called_once_with()
    trainer._process_memory.assert_not_called()


def test_new_unit_and_reused_address_use_fresh_identity(trainer):
    first=make_snapshot()
    second=replace(first,handle=9,full_handle=0x900000001,owner_address=0x9900,hero_level=0,component_mask=12)
    trainer.persistent_native_selected_snapshots.side_effect=[(first,),(second,)]
    old,old_handle=trainer._direct_selected_context()
    fresh,new_handle=trainer._direct_selected_context()
    assert old.unit_address==fresh.unit_address
    assert (old.handle,old_handle)==(first.full_handle,first.handle)
    assert (fresh.handle,new_handle,fresh.owner_address)==(second.full_handle,second.handle,second.owner_address)
    assert old.native_snapshot==first


def test_empty_selection_does_not_reuse_last_unit(trainer):
    trainer._direct_selected_context()
    trainer.persistent_native_selected_snapshots.return_value=()
    with pytest.raises(RuntimeError): trainer._direct_selected_context()


def test_mixed_selection_bound_action_uses_selected_member_without_reread(trainer):
    hero=make_snapshot()
    ordinary=replace(hero,handle=17,full_handle=0x900000017,owner_address=0x7700,
                     unit_address=0x8800,hero_level=0,component_mask=12)
    trainer.persistent_native_selected_snapshots.return_value=(hero,ordinary)
    selected=trainer._selected_candidates_snapshot(None)
    trainer._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(157,1)])
    for candidate,handle in selected:
        with trainer._bound_elephant_selection(candidate,handle):
            assert trainer._run_direct_selected_ability_locked('A001',102,0x998,0)==1
        args=trainer._run_native_helper_ops.call_args.args
        assert args==(handle,((136,0,candidate.unit_address,candidate.handle,candidate.owner_address),
                             (157,0x41303031,2,0,0)))
    trainer.persistent_native_selected_snapshots.assert_called_once_with()
    assert trainer._elephant_selection_override is None


def test_ability_add_uses_actual_selection_context(trainer):
    trainer._run_native_helper_ops=Mock(return_value=[module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(156,1)])
    trainer.add_ability_to_selected_unit('A001')
    native=make_snapshot()
    assert trainer._run_native_helper_ops.call_args.args==(native.handle,(
        (136,0,native.unit_address,native.full_handle,native.owner_address),(156,0x41303031,1,0,0)))


@pytest.mark.parametrize('count', [13, 24])
def test_large_mixed_batch_keeps_every_display_and_action_target(trainer, count):
    initial = make_snapshot()
    snapshots = tuple(replace(initial, handle=i, full_handle=(i << 32) | i,
        owner_address=0x100000+i*0x1000, unit_address=0x200000+i*0x1000,
        hero_level=5 if i % 2 else 0, component_mask=15 if i % 2 else 12)
        for i in range(1, count+1))
    trainer.persistent_native_selected_snapshots.return_value = snapshots
    trainer._native_helper_lock = threading.RLock()
    trainer._native_helper_batch_transaction = Mock(side_effect=nullcontext)
    trainer._run_native_helper_ops = Mock(return_value=[module.NativeHelperOpResult(136,1),
                                                       module.NativeHelperOpResult(156,1)])
    selected = trainer._selected_candidates_snapshot(None)
    summaries = trainer._selected_summaries_from_snapshot(None, selected)
    assert len(summaries) == count
    assert [s.candidate.unit_address for s in summaries] == [s.unit_address for s in snapshots]
    assert [s.hero for s in summaries] == [bool(i % 2) for i in range(1,count+1)]
    trainer.persistent_native_selected_snapshots.reset_mock()
    succeeded, failed, results, errors = trainer.run_for_selected_units(
        lambda: trainer.add_ability_to_selected_unit('A001'))
    assert (succeeded, failed, len(results), errors) == (count, 0, count, ())
    assert [call.args[0] for call in trainer._run_native_helper_ops.call_args_list] == list(range(1,count+1))
    trainer.persistent_native_selected_snapshots.assert_called_once_with()
    trainer._native_helper_batch_transaction.assert_called_once_with()
    assert trainer._elephant_selection_override is None
