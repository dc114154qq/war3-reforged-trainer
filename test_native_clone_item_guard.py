"""Compiled clone dispatch: item changes while both units remain valid."""
import pytest
from test_native_clone_unit_guard import native, dispatch, parse


@pytest.mark.parametrize('hero',[0,1])
@pytest.mark.parametrize('layout',[8,16])
@pytest.mark.parametrize('reverse',[0,32])
def test_full_or_sparse_inventory_tracks_actual_target_slots(native,tmp_path,hero,layout,reverse):
    out,payload=dispatch(native,tmp_path,hero=hero|layout|reverse|2)
    assert parse(payload)[1].result==8 and list(out[2:5])==[1,0,1]
    count=6 if layout==8 else 2
    assert out[8]==4*count
    assert out[11]==(63 if count==6 else 0x30 if reverse else 3)


@pytest.mark.parametrize('hero',[2,3])
@pytest.mark.parametrize('failure',[9,10,11,12,13,14])
def test_item_generation_membership_and_wrapper_faults_abort_without_stale_access(native,tmp_path,hero,failure):
    baseline,payload=dispatch(native,tmp_path/'baseline',hero)
    parse(payload)
    injected=0
    for at in range(1,baseline[1]+1):
        out,payload=dispatch(native,tmp_path/str(at),hero,at,failure)
        if not out[10]:
            parse(payload)
            continue
        injected+=1
        with pytest.raises(RuntimeError):parse(payload)
        # dispatch also checks no stale item field/charge callback was called.
        # Unit identity is unchanged, so cleanup must remove the created unit.
        assert list(out[2:5])==[1,1,0]
    assert injected>0


@pytest.mark.parametrize('failure',[15,16,17])
def test_added_item_alias_detachment_or_wrong_type_is_rejected_before_copy(native,tmp_path,failure):
    out,payload=dispatch(native,tmp_path,hero=3,failure=failure)
    with pytest.raises(RuntimeError):parse(payload)
    assert list(out[2:5])==[1,1,0]
    assert out[8]==0


@pytest.mark.parametrize('failure',[18,19])
def test_missing_item_resolver_or_duplicate_source_fails_before_create(native,tmp_path,failure):
    out,payload=dispatch(native,tmp_path,hero=3,failure=failure)
    with pytest.raises(RuntimeError):parse(payload)
    assert list(out[2:5])==[0,0,0]


@pytest.mark.parametrize('failure',[20,21,22])
def test_duplicate_target_changed_empty_source_slot_and_late_detachment_fail(native,tmp_path,failure):
    out,payload=dispatch(native,tmp_path,hero=3,failure=failure)
    with pytest.raises(RuntimeError):parse(payload)
    assert list(out[2:5])==[1,1,0]


@pytest.mark.parametrize('failure',[23,24])
def test_item_page_losing_read_permission_is_caught_by_production_seh(native,tmp_path,failure):
    out,payload=dispatch(native,tmp_path,hero=3,failure=failure)
    with pytest.raises(RuntimeError):parse(payload)
    assert out[10]==1 and list(out[2:5])==[1,1,0]
