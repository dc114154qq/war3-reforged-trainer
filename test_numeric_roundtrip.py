import struct

import pytest

import war3_reforged_trainer as trainer


def _f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def _f32_bits(value: float) -> bytes:
    return struct.pack("<f", value)


@pytest.mark.parametrize(
    "value",
    (
        12_345_678.0,
        1.0e20,
        1.0e-10,
        -98_765_432.0,
        1.401298464324817e-45,
    ),
)
def test_editable_float32_text_is_plain_decimal_and_round_trips(value):
    stored = _f32(value)

    text = trainer.format_editable_float32(stored)

    assert "e" not in text.lower()
    assert _f32_bits(float(text)) == _f32_bits(stored)


def test_unit_field_large_float_uses_exact_editable_text():
    stored = _f32(12_345_678.0)
    field = trainer.UnitMemoryField(
        key="test",
        label="test",
        value_type="f32",
        value=stored,
        address=1,
        category="test",
        write_address=1,
        write_type="f32",
    )

    assert field.value_text() == "12345678"
    assert _f32_bits(float(field.value_text())) == _f32_bits(stored)


@pytest.mark.parametrize(
    ("text", "expected"),
    (
        ("1e6", 1_000_000),
        ("-2.5e2", -250),
        ("0x10", 16),
        ("4294967295", 4_294_967_295),
    ),
)
def test_integer_fields_accept_exact_scientific_notation(text, expected):
    assert trainer.parse_integer_number(text) == expected
    assert trainer.War3Trainer._coerce_memory_value("i32", text) == expected


@pytest.mark.parametrize("text", ("1e-1", "nan", "inf", "not-a-number"))
def test_integer_fields_reject_non_integral_or_non_finite_values(text):
    with pytest.raises(ValueError):
        trainer.parse_integer_number(text)
