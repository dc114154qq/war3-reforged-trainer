import ctypes as c
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from war3_hero_attributes_protocol import build_work, decode_work
from war3_native_table import LiveNativeEntry
from war3_selection_protocol import SIGNATURES
from war3_reforged_trainer import War3Trainer


ATTRIBUTE_SIGNATURES = (
    ("GetHeroStr", "(Hunit;B)I"),
    ("GetHeroAgi", "(Hunit;B)I"),
    ("GetHeroInt", "(Hunit;B)I"),
    ("SetHeroStr", "(Hunit;IB)V"),
    ("SetHeroAgi", "(Hunit;IB)V"),
    ("SetHeroInt", "(Hunit;IB)V"),
)


def entries():
    signatures = SIGNATURES + ATTRIBUTE_SIGNATURES
    return {
        name: LiveNativeEntry(name, signature, 0x300000 + index * 80, 0x500000 + index * 256)
        for index, (name, signature) in enumerate(signatures)
    }


def work(target=77):
    return build_work(entries(), 0x10000000, target)


@pytest.fixture(scope="module")
def fixture_dll():
    path = Path(__file__).parent / "analysis/bridge-build-hero-attributes-20260919/engine-hero-fixture.dll"
    assert path.is_file()
    dll = c.WinDLL(str(path))
    dll.BridgeHeroAttributesTestRun.argtypes = [c.c_void_p, c.c_int, c.c_int]
    dll.BridgeHeroAttributesTestRun.restype = c.c_uint64
    dll.BridgeHeroAttributesTestStat.argtypes = [c.c_int, c.c_int]
    dll.BridgeHeroAttributesTestStat.restype = c.c_int
    return dll


def run_fixture(dll, count=15, target=77, scenario=0):
    buffer = c.create_string_buffer(work(target))
    actual = dll.BridgeHeroAttributesTestRun(buffer, count, scenario)
    return buffer.raw[:1144], actual


def test_c_transaction_sets_all_three_attributes_for_every_selected_hero(fixture_dll):
    data, actual = run_fixture(fixture_dll)
    result = decode_work(data, actual)
    assert len(result["rows"]) == 5
    assert result["changed"] == result["selection_count"] - result["skipped"] == 5
    assert all(row["after"] == (77, 77, 77) for row in result["rows"])
    for index in range(0, 15, 3):
        assert [fixture_dll.BridgeHeroAttributesTestStat(kind, index) for kind in (1, 2, 3)] == [77, 77, 77]


def test_c_transaction_rolls_back_when_one_native_does_not_apply(fixture_dll):
    data, actual = run_fixture(fixture_dll, scenario=1)
    with pytest.raises(ValueError, match="Hero attribute batch incomplete"):
        decode_work(data, actual)
    assert [fixture_dll.BridgeHeroAttributesTestStat(kind, 0) for kind in (1, 2, 3)] == [10, 20, 30]


def test_c_query_and_distinct_noop_targets_do_not_change_attributes(fixture_dll):
    query = c.create_string_buffer(build_work(entries(), 0x10000000, None))
    actual = fixture_dll.BridgeHeroAttributesTestRun(query, 1, 0)
    result = decode_work(query.raw[:1144], actual)
    assert result["mode"] == "query" and result["rows"][0]["before"] == (10, 20, 30)
    noop = c.create_string_buffer(build_work(entries(), 0x10000000, (10, 20, 30)))
    actual = fixture_dll.BridgeHeroAttributesTestRun(noop, 1, 0)
    result = decode_work(noop.raw[:1144], actual)
    assert result["changed"] == 0 and result["rows"][0]["after"] == (10, 20, 30)


def test_product_attribute_button_uses_one_engine_transaction_only():
    trainer = object.__new__(War3Trainer)
    trainer._native_selection_unavailable = True
    trainer.hero_attributes_24268 = Mock(return_value={"rows": [{"after": (55, 55, 55)}], "changed": 1})
    trainer._direct_selected_context = Mock(side_effect=AssertionError("raw candidate path used"))
    trainer._process_memory = Mock(side_effect=AssertionError("raw memory write used"))
    assert trainer.set_selected_hero_attributes(55) == 55
    trainer.hero_attributes_24268.assert_called_once_with(55)


class AttackMemory:
    def __init__(self, base):
        self.base = base

    def read_i32(self, address):
        return 0

    def read_f32(self, address):
        values = {
            self.base + 0x228: 2.0,
            self.base + 0x2B8: 1.5,
            self.base + 0x2D0: -0.1,
        }
        return values.get(address, 1.0)


def test_3_0_attack_fields_show_effective_speed_and_keep_them_read_only():
    trainer = object.__new__(War3Trainer)
    base = 0x200000
    fields = []
    trainer._append_attack_fields(
        AttackMemory(base), fields, "attack1", "攻击1", base,
        current_24268=True,
        timing_24268={
            "speed_factor": 1.4,
            "after_effective_interval": 2.0 / 1.4,
            "after_true_aps": 0.7,
        },
        expected_speed_24268=0.75,
    )
    by_key = {field.key: field for field in fields}
    assert by_key["attack1_interval"].address == base + 0x228
    assert "attack1_first_delay" not in by_key
    assert by_key["attack1_speed_factor"].value == pytest.approx(1.4)
    assert by_key["attack1_effective_interval"].value == pytest.approx(2.0 / 1.4)
    assert by_key["attack1_expected_speed"].value == pytest.approx(0.75)
    assert by_key["attack1_true_speed"].value == pytest.approx(0.7)
    assert not by_key["attack1_speed_factor"].writable
    assert not by_key["attack1_effective_interval"].writable
    assert not by_key["attack1_expected_speed"].writable
    assert by_key["attack1_true_speed"].writable
