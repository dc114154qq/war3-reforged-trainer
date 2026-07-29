import math
import struct
from unittest.mock import patch

import pytest

import war3_reforged_trainer as trainer


def _f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


class FakeProcessMemory:
    def __init__(self, values: dict[int, float]):
        self.values = dict(values)
        self.writes: list[tuple[int, float]] = []

    def read_f32(self, address: int) -> float:
        return self.values[address]

    def write_f32(self, address: int, value: float) -> None:
        stored = _f32(value)
        self.values[address] = stored
        self.writes.append((address, stored))


@pytest.fixture
def large_numeric_context():
    subject = object.__new__(trainer.War3Trainer)
    owner = 0x2000
    hp_prop = 0x3000
    mp_prop = 0x4000
    unit = 0x5000
    offset = trainer.War3Trainer.SELECTED_HP_VALUE_OFFSET
    hp_current = hp_prop + offset
    hp_max = hp_current + 0x10
    mp_current = mp_prop + offset
    mp_max = mp_current + 0x10
    pm = FakeProcessMemory(
        {
            hp_current: _f32(1000.0),
            hp_max: _f32(1000.0),
            mp_current: _f32(500.0),
            mp_max: _f32(500.0),
        }
    )

    def candidate():
        def property_for_owner(_pm, candidate_owner, kind):
            assert candidate_owner == owner
            return hp_prop if kind == 1 else mp_prop if kind == 2 else None

        with (
            patch.object(
                subject,
                "_property_from_owner",
                side_effect=property_for_owner,
            ),
            patch.object(subject, "_position_property_from_owner", return_value=None),
            patch.object(subject, "_unit_object_from_owner", return_value=unit),
        ):
            return subject._candidate_from_owner(
                pm,
                owner,
                1000,
                "test",
                handle=0x1234,
            )

    return subject, pm, candidate, hp_current, mp_current


def test_large_vitals_can_be_reread_after_successful_write(large_numeric_context):
    subject, pm, candidate, hp_current, mp_current = large_numeric_context
    before = candidate()
    assert before is not None
    stored = _f32(1.0e20)

    subject._write_basic_unit_values_to_candidate(
        pm,
        before,
        target_hp=stored,
        target_mp=stored,
        max_hp=stored,
        max_mp=stored,
    )

    after = candidate()
    assert after is not None
    assert after.mp_current_address == mp_current
    panel = subject._panel_from_candidate(pm, after)
    assert panel.current_hp == int(round(stored))
    assert panel.current_mp == int(round(stored))

    fields = []
    subject._append_unit_field(
        pm,
        fields,
        "hp_current",
        "hp",
        "f32",
        hp_current,
        "test",
    )
    assert len(fields) == 1
    assert "e" not in fields[0].value_text().lower()
    assert _f32(float(fields[0].value_text())) == stored


@pytest.mark.parametrize("invalid", ("nan", "inf", "1e500"))
def test_invalid_float32_values_are_rejected_before_any_write(
    large_numeric_context,
    invalid,
):
    subject, pm, candidate, _hp_current, _mp_current = large_numeric_context
    selected = candidate()
    assert selected is not None

    with pytest.raises(ValueError, match="float32"):
        subject._write_basic_unit_values_to_candidate(
            pm,
            selected,
            target_hp=invalid,
            target_mp=None,
            max_hp=None,
            max_mp=None,
        )

    assert pm.writes == []


def test_large_finite_values_pass_vital_validation():
    assert trainer.War3Trainer._valid_current_limit(_f32(1.0e20), _f32(1.0e20))
    assert not trainer.War3Trainer._valid_current_limit(math.inf, _f32(1.0e20))
    assert not trainer.War3Trainer._valid_current_limit(1.0, -1.0)
