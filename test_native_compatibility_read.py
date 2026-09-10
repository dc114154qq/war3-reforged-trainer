"""Exercise both public reads through real selection mapping, without Warcraft."""
from dataclasses import replace
from unittest.mock import Mock, patch

import pytest
import war3_reforged_trainer as module
from test_native_snapshot_binding import make_snapshot


@pytest.fixture(params=["read_selected_unit_fields", "read_selected_unit_fields_win10"])
def reader(request):
    t = module.War3Trainer.__new__(module.War3Trainer)
    t._unit_owner_index = {}
    t._last_persistent_native_snapshots = ()
    t._last_selected_summaries = ()
    pm = Mock()
    pm.regions.side_effect = AssertionError("No process-wide region enumeration")
    pm.read_f32.side_effect = AssertionError("No external panel read")
    t._process_memory = Mock(side_effect=AssertionError("No external memory context"))
    t._candidate_from_identity = Mock(side_effect=AssertionError("No legacy identity lookup"))
    t._recover_win10_native_handlers = Mock(side_effect=AssertionError("No legacy discovery"))
    t._selected_components = Mock(side_effect=AssertionError("No legacy components"))
    # Field decoding has separate native C/Python tests; retain the actual
    # selection mapper, panel decoder and multi-unit summaries here.
    t._unit_fields_from_candidate = Mock(return_value=[])
    t.persistent_native_selected_snapshots = Mock(return_value=(make_snapshot(),))
    with patch.object(module, "Win10ProcessMemory", side_effect=AssertionError("No compatibility backend")), patch.object(
        module, "Win10ReadLogger", side_effect=AssertionError("No compatibility diagnostics")
    ):
        yield t, getattr(t, request.param)


def test_read_mixed_selection_then_reused_address_tracks_new_generation(reader):
    t, read = reader
    hero = make_snapshot()
    ordinary = replace(hero, handle=17, full_handle=0x900000017, owner_address=0x7700,
                       unit_address=0x8800, hero_level=0, component_mask=12)
    new_unit = replace(hero, handle=23, full_handle=0xA00000001, hp=7, owner_address=0x9900)
    t.persistent_native_selected_snapshots.side_effect = [(hero, ordinary), (new_unit,)]
    panel, candidate, fields = read()
    assert candidate.native_snapshot == hero
    assert panel.hp_text == "100/200" and fields == []
    summaries = t.selected_unit_summaries()
    assert len(summaries) == 2 and summaries[0].hero and not summaries[1].hero
    panel, candidate, _ = read()
    assert candidate.unit_address == hero.unit_address
    assert candidate.handle == new_unit.full_handle and candidate.owner_address == new_unit.owner_address
    assert panel.hp_text == "7/200"
    assert len(t.selected_unit_summaries()) == 1
    assert t._unit_fields_from_candidate.call_args.args[1].native_snapshot == new_unit
    assert t.persistent_native_selected_snapshots.call_count == 2
    t._process_memory.assert_not_called()


@pytest.mark.parametrize("failure", [(), "native failure", "incomplete", "duplicate"])
def test_failed_second_read_never_returns_previous_or_partial_selection(reader, failure):
    t, read = reader
    read()
    if failure == "native failure":
        t.persistent_native_selected_snapshots.side_effect = RuntimeError(failure)
    elif failure == "incomplete":
        t.persistent_native_selected_snapshots.return_value = (make_snapshot(), replace(make_snapshot(), owner_address=0))
    elif failure == "duplicate":
        t.persistent_native_selected_snapshots.return_value = (make_snapshot(), make_snapshot())
    else:
        t.persistent_native_selected_snapshots.return_value = failure
    with pytest.raises(RuntimeError):
        read()
    assert t._unit_fields_from_candidate.call_count == 1
    t._candidate_from_identity.assert_not_called()
    t._recover_win10_native_handlers.assert_not_called()
