"""Public native reads decode production C field payloads without process access."""
from dataclasses import replace
import os
from unittest.mock import Mock

import pytest
import war3_reforged_trainer as module
from test_native_snapshot_binding import make_snapshot, snapshot_result
from test_native_unit_field_dispatch import dispatcher


@pytest.mark.parametrize('cls',[module.War3Trainer,module.BackupReadWar3Trainer])
@pytest.mark.parametrize('mask',[0,13,15])
@pytest.mark.parametrize('entry',['read_selected_unit_fields','read_selected_unit_fields_win10',
    'read_unit_fields_by_identity','read_unit_fields_by_identity_win10','prewarm_selected_unit_cache'])
def test_public_read_decodes_real_c_fields_without_external_memory(dispatcher,tmp_path,cls,mask,entry):
    assert dispatcher.field_snapshot(str(tmp_path)+'\\',mask,0)==0
    payload=(tmp_path/f'war3_reforged_native_{os.getpid()}.bin').read_bytes()
    subject=cls.__new__(cls)
    results=subject._parse_native_helper_results(payload,2);values=results[0].extra_results
    snapshot=replace(make_snapshot(),handle=7,unit_address=values[0],full_handle=values[1],
        owner_address=values[2],component_mask=mask,hero_level=5 if mask&2 else 0,
        item_ids=(0,)*6,item_charges=(0,)*6,item_handles=(0,)*6,item_addresses=(0,)*6,item_full_handles=(0,)*6)
    subject._unit_owner_index={};subject._last_persistent_native_snapshots=();subject._last_selected_summaries=()
    subject.persistent_native_init=Mock()
    for name in ('_process_memory','_selected_components','_candidate_from_identity','_inventory_items_from_candidate',
                 '_looks_like_vtable','_recover_win10_native_handlers'):
        setattr(subject,name,Mock(side_effect=AssertionError('Unexpected external path: '+name)))
    selection_kind=subject.NATIVE_HELPER_OP_PERSISTENT_SELECTED_SNAPSHOT
    seen=[]
    def run(handle,ops,**kwargs):
        seen.append((handle,ops))
        if ops[0][0]==selection_kind:
            assert handle==0
            return [snapshot_result(snapshot)]
        if ops[0][0]==155:
            assert handle==0 and ops[0][2:]==(snapshot.unit_address,snapshot.full_handle,snapshot.owner_address)
            return [snapshot_result(snapshot)]
        assert handle==7 and ops==((136,0,snapshot.unit_address,snapshot.full_handle,snapshot.owner_address),(147,0,0,0,0))
        return subject._parse_native_helper_results(payload,2)
    subject._run_native_helper_ops=Mock(side_effect=run)
    if 'by_identity' in entry:
        output=getattr(subject,entry)(snapshot.full_handle,snapshot.owner_address,snapshot.unit_address)
    else:output=getattr(subject,entry)()
    if entry=='prewarm_selected_unit_cache':
        candidate=output
    else:
        panel,candidate,fields=output
        assert panel.hp_text=='100/200' and panel.mp_text=='50/60'
        fields={f.key:f for f in fields}
        assert fields['armor'].value==12.5 and fields['armor_type'].value==4
        assert fields['ability_01_rawcode'].value==snapshot.ability_ids[0]
        assert fields['ability_01_level'].value==2
        assert ('skill_points' in fields)==bool(mask&2)
        assert ('attack1_base1' in fields)==bool(mask&8)
        if mask&2:
            assert fields['skill_points'].value==9 and fields['strength_growth'].value==2.25
            assert fields['skill1_name'].value==0x41303031
        if mask&8:assert fields['attack2_base1'].value==102
    assert candidate.native_snapshot==snapshot
    assert len(seen)==2
    assert seen[0][1][0][0]==(155 if 'by_identity' in entry else selection_kind)
    subject._process_memory.assert_not_called();subject._selected_components.assert_not_called()


@pytest.mark.parametrize('entry',['read_selected_panel','locate_current_selected_unit'])
@pytest.mark.parametrize('cls',[module.War3Trainer,module.BackupReadWar3Trainer])
def test_panel_reads_one_current_snapshot_without_field_or_memory_lookup(cls,entry):
    subject=cls.__new__(cls);subject._unit_owner_index={}
    subject._process_memory=Mock(side_effect=AssertionError('External panel'))
    subject._unit_fields_from_candidate=Mock(side_effect=AssertionError('Unnecessary field read'))
    first=make_snapshot();second=replace(first,full_handle=first.full_handle+1,hp=7,handle=17)
    subject.persistent_native_selected_snapshots=Mock(side_effect=[(first,),(second,)])
    for snapshot in (first,second):
        output=getattr(subject,entry)()
        panel=output if entry=='read_selected_panel' else output[0]
        assert panel.hp_text==f'{int(snapshot.hp)}/{int(snapshot.hp_max)}'
        if entry!='read_selected_panel':assert output[1].handle==snapshot.full_handle
    assert subject.persistent_native_selected_snapshots.call_count==2
    subject._process_memory.assert_not_called()


def test_failed_field_decode_does_not_publish_partial_new_summaries():
    subject=module.War3Trainer.__new__(module.War3Trainer);subject._unit_owner_index={}
    subject._process_memory=Mock(side_effect=AssertionError('External memory'))
    subject.persistent_native_selected_snapshots=Mock(return_value=(make_snapshot(),))
    subject._unit_fields_from_candidate=Mock(return_value=[])
    subject.read_selected_unit_fields();previous=subject.selected_unit_summaries()
    subject.persistent_native_selected_snapshots.return_value=(replace(make_snapshot(),handle=17,full_handle=0x900000001),)
    subject._unit_fields_from_candidate.side_effect=RuntimeError('incomplete native fields')
    with pytest.raises(RuntimeError,match='incomplete native fields'):subject.read_selected_unit_fields()
    assert subject.selected_unit_summaries() is previous
