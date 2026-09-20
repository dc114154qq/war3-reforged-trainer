import pytest

from war3_reforged_trainer import parse_changed_coordinate


def test_unchanged_display_coordinate_is_not_submitted():
    assert parse_changed_coordinate("123.456", "123.456", "目标 X") is None


def test_changed_coordinate_is_submitted():
    assert parse_changed_coordinate("123.457", "123.456", "目标 X") == pytest.approx(123.457)


def test_blank_coordinate_is_not_submitted():
    assert parse_changed_coordinate("", "123.456", "目标 X") is None
