"""Object entrypoints preserve native identities with external access forbidden."""
from dataclasses import replace
from unittest.mock import Mock
import pytest
import war3_reforged_trainer as module
from test_native_selected_context import trainer
from test_native_snapshot_binding import snapshot_result


@pytest.mark.parametrize('failure',[False,True])
def test_item_bundle_binds_original_selection_once_and_stops_on_failure(trainer,failure):
    snapshot=trainer.persistent_native_selected_snapshots.return_value[0]
    handles=list(snapshot.item_handles);handles[2]=102
    fulls=list(snapshot.item_full_handles);fulls[2]=0x123400000066
    objects=list(snapshot.item_addresses);objects[2]=0x500000
    ids=list(snapshot.item_ids);ids[2]=0x49303033
    snapshot=replace(snapshot,item_handles=tuple(handles),item_full_handles=tuple(fulls),item_addresses=tuple(objects),item_ids=tuple(ids))
    trainer.persistent_native_selected_snapshots.return_value=(snapshot,)
    calls=[]
    def run(handle,ops):
        calls.append(ops)
        assert handle==snapshot.handle
        slot=ops[2][1]
        assert ops[0]==(136,0,snapshot.unit_address,snapshot.full_handle,snapshot.owner_address)
        assert ops[1][2:]==(0,snapshot.item_handles[slot],snapshot.item_full_handles[slot])
        if failure and slot==2:raise RuntimeError('original item replaced')
        return [module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(150,0x990000+slot*0x100),
                module.NativeHelperOpResult(151,ops[1][1])]
    trainer._run_native_helper_ops=Mock(side_effect=run)
    if failure:
        with pytest.raises(RuntimeError,match='original item replaced'):
            trainer.replace_selected_inventory_items([(0,'I002'),(2,'I004'),(5,'I006')])
        assert len(calls)==2
    else:
        assert trainer.replace_selected_inventory_items([(0,'I002'),(2,'I004')])==2
    trainer.persistent_native_selected_snapshots.assert_called_once_with()
    trainer._process_memory.assert_not_called()


@pytest.mark.parametrize('replacement',[False,True])
def test_remove_all_enumerates_native_generations_then_mutates_same_target(trainer,replacement):
    trainer._persistent_native_initialized=True
    original=trainer.persistent_native_selected_snapshots.return_value[0]
    trainer._query_native_table_handlers=Mock(side_effect=lambda names:{name:module.NativeHandler(name,0,0x100000+n*0x100)
                                                               for n,name in enumerate(names)})
    rows=(200,0x200000,0x300000,0x987600005432,0x4148737430303030,0x400000,0x500000,0x41303031,1,0,
          201,0x210000,0x310000,0x987600005433,0x4148737430303030,0x400000,0x500000,0x41303032,1,0)
    calls=[]
    def run(handle,ops):
        calls.append(ops);assert handle==original.handle
        if ops[1][0]==trainer.NATIVE_HELPER_OP_BOUND_ABILITY_LIST:
            trainer.persistent_native_selected_snapshots.return_value=(replace(original,handle=17,full_handle=0x1700000001),)
            return [module.NativeHelperOpResult(136,1,extra_results=rows),
                    module.NativeHelperOpResult(trainer.NATIVE_HELPER_OP_BOUND_ABILITY_LIST,2)]
        assert ops[1:]==((156,0x41303031,2,0,rows[3]),(156,0x41303032,2,0,rows[13]))
        if replacement:raise RuntimeError('ability generation changed')
        return [module.NativeHelperOpResult(136,1),module.NativeHelperOpResult(156,1),module.NativeHelperOpResult(156,1)]
    trainer._run_native_helper_ops=Mock(side_effect=run)
    if replacement:
        with pytest.raises(RuntimeError,match='ability generation changed'):trainer.remove_all_selected_unit_abilities()
    else:assert trainer.remove_all_selected_unit_abilities()==2
    assert len(calls)==2
    trainer.persistent_native_selected_snapshots.assert_called_once_with();trainer._process_memory.assert_not_called()


@pytest.mark.parametrize('pinned',[False,True])
def test_ability_context_uses_native_metadata_without_memory_context(trainer,pinned):
    snapshot=trainer.persistent_native_selected_snapshots.return_value[0]
    trainer.persistent_native_init=Mock()
    trainer._query_native_table_handlers=Mock(side_effect=lambda names:{name:module.NativeHandler(name,0,0x100000+n*0x100)
                                                               for n,name in enumerate(names)})
    metadata=(200,0x200000,0x300000,0x987600005432,0x4148737430303030,0x400000,0x500000,0x41303031,4,0)
    def run(handle,ops):
        if ops[0][0]==155:return [snapshot_result(snapshot)]
        assert handle==snapshot.handle and ops[1][0]==141
        return [module.NativeHelperOpResult(136,1,extra_results=metadata),module.NativeHelperOpResult(141,200)]
    trainer._run_native_helper_ops=Mock(side_effect=run)
    identity=(snapshot.full_handle,snapshot.owner_address,snapshot.unit_address)
    result=trainer._ability_field_context_by_identity_locked('A001',1,identity,True) if pinned else trainer._selected_ability_field_context_locked('A001',1)
    assert result.unit_identity==identity and result.ability_identity==(200,0x200000,0x987600005432)
    assert result.effect_class_verified and result.current_level==4
    trainer._process_memory.assert_not_called()
    if pinned:trainer.persistent_native_selected_snapshots.assert_not_called()
