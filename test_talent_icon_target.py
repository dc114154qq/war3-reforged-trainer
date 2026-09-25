from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from war3_reforged_trainer import War3Trainer


def test_icon_refresh_binds_second_selected_hero():
    trainer = War3Trainer.__new__(War3Trainer)
    first, second = SimpleNamespace(name='first'), SimpleNamespace(name='second')
    trainer._selected_candidates_snapshot = Mock(return_value=((first, 101), (second, 202)))
    assert trainer._talent_icon_candidate_24268(202) is second


@pytest.mark.parametrize('rows', [(), ((object(), 101),), ((object(), 202), (object(), 202))])
def test_icon_refresh_rejects_missing_or_ambiguous_target(rows):
    trainer = War3Trainer.__new__(War3Trainer)
    trainer._selected_candidates_snapshot = Mock(return_value=rows)
    with pytest.raises(RuntimeError):
        trainer._talent_icon_candidate_24268(202)


def test_icon_refresh_honors_bound_batch_target_without_reselecting():
    trainer = War3Trainer.__new__(War3Trainer)
    candidate = object()
    trainer._elephant_selection_override = (candidate, 202)
    trainer._selected_candidates_snapshot = Mock(side_effect=AssertionError('Bound target was lost'))
    assert trainer._talent_icon_candidate_24268(202) is candidate
    with pytest.raises(RuntimeError):
        trainer._talent_icon_candidate_24268(101)
    trainer._selected_candidates_snapshot.assert_not_called()


def test_classic_full_handle_is_not_compared_to_jass_id():
    trainer = War3Trainer.__new__(War3Trainer)
    trainer._native_selection_unavailable = True
    candidate = SimpleNamespace(unit_type_id=0x48363038)
    trainer._selected_candidates_snapshot = Mock(return_value=((candidate, 0x8ce100008cd5),))
    engine = Mock()
    engine.ability_batch.return_value = {'rows': [{'handle': 0x100f8c, 'rawcode': candidate.unit_type_id}]}
    trainer._engine_instance_24268 = Mock(return_value=engine)
    assert trainer._talent_icon_candidate_24268(0x100f8c) is candidate
    engine.ability_batch.return_value['rows'].append({'handle': 0x100f8d, 'rawcode': candidate.unit_type_id})
    with pytest.raises(RuntimeError):
        trainer._talent_icon_candidate_24268(0x100f8c)
