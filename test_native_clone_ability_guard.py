"""Production clone dispatch with independent unit and ability generations."""
import pytest
from test_native_clone_unit_guard import native, dispatch, parse


@pytest.mark.parametrize('hero',[64,65,128,129,256,257])
def test_multiple_maximum_and_essential_abilities(native,tmp_path,hero):
    out,payload=dispatch(native,tmp_path,hero=hero)
    assert parse(payload)[1].result==8 and list(out[2:5])==[1,0,1]
    assert out[12]==(256 if hero&128 else 1 if hero&256 else 3)
    assert out[9]==3


@pytest.mark.parametrize('failure',[33,34,38,39,40])
def test_absent_alias_wrong_level_and_late_recycled_target_are_not_success(native,tmp_path,failure):
    out,payload=dispatch(native,tmp_path,hero=3,failure=failure)
    with pytest.raises(RuntimeError):parse(payload)
    assert list(out[2:5])==[1,1,0]


@pytest.mark.parametrize('failure',[35,37,43])
def test_actual_add_readback_existing_target_and_duplicate_rawcode_are_supported(native,tmp_path,failure):
    out,payload=dispatch(native,tmp_path,hero=3,failure=failure)
    assert parse(payload)[1].result==8 and list(out[2:5])==[1,0,1]
    assert out[12]==(0 if failure==37 else 1) and out[9]==3


@pytest.mark.parametrize('failure',[36,41,42,45,46,49])
def test_invalid_source_list_and_missing_resolvers_fail_before_create(native,tmp_path,failure):
    out,payload=dispatch(native,tmp_path,hero=3,failure=failure)
    with pytest.raises(RuntimeError):parse(payload)
    assert list(out[2:5])==[0,0,0]


def test_ability_added_to_source_during_creation_invalidates_frozen_list(native,tmp_path):
    out,payload=dispatch(native,tmp_path,hero=3,failure=44)
    with pytest.raises(RuntimeError):parse(payload)
    assert list(out[2:5])==[1,1,0]
    assert out[12]==0


@pytest.mark.parametrize('failure',[47,48])
def test_unreadable_ability_memory_is_handled_by_production_seh(native,tmp_path,failure):
    out,payload=dispatch(native,tmp_path,hero=3,failure=failure)
    with pytest.raises(RuntimeError):parse(payload)
    assert out[10]==1 and out[3]==out[2] and out[4]==0


@pytest.mark.parametrize('hero',[64,65])
@pytest.mark.parametrize('failure',range(25,33))
def test_every_callback_detects_recycled_detached_or_replaced_ability(native,tmp_path,hero,failure):
    baseline,payload=dispatch(native,tmp_path/'baseline',hero=hero)
    parse(payload)
    injected=0
    for at in range(1,baseline[1]+1):
        out,payload=dispatch(native,tmp_path/str(at),hero=hero,at=at,failure=failure)
        if not out[10]:
            parse(payload)
            continue
        injected+=1
        with pytest.raises(RuntimeError):parse(payload)
        # dispatch independently rejects stale ability native access.
        assert out[3]==out[2] and out[4]==0
    assert injected>0
