import struct
from types import SimpleNamespace

import pytest

import war3_reforged_trainer
from war3_selection_protocol import SIGNATURES as SELECTION_SIGNATURES
from war3_world_cast_protocol import (
    CAST_POINT, SIGNATURES, WORK_SIZE, build_work, decode_work, validate_work,
)


def _entries():
    return {
        name: SimpleNamespace(name=name, signature=signature, handler=0x10000 + index * 16)
        for index, (name, signature) in enumerate(SELECTION_SIGNATURES + SIGNATURES)
    }


def test_start_accepts_selected_source_and_requires_clean_output():
    payload = build_work(_entries(), 0x20000, action=1, rawcode=0x41487463,
                         order_id=852096, area=8000.0, source=1053592)
    assert len(payload) == WORK_SIZE
    validate_work(payload)
    corrupt = bytearray(payload)
    corrupt[724] = 1
    with pytest.raises(ValueError, match="request is invalid"):
        validate_work(corrupt)


def test_continuation_requires_exact_identity():
    with pytest.raises(ValueError, match="identity is invalid"):
        build_work(_entries(), 0x20000, action=2, rawcode=0x41487463,
                   source=0, ability_handle=1054896, prior_area=0, added=1)


def test_oversized_area_is_rejected_before_game_dispatch():
    with pytest.raises(ValueError, match="start request is invalid"):
        build_work(_entries(), 0x20000, action=1, rawcode=0x41487463,
                   order_id=852096, area=100001.0)


def test_start_response_decodes_selection_count_not_callback_completion():
    payload = bytearray(build_work(_entries(), 0x20000, action=1,
                                   rawcode=0x41487463, order_id=852096,
                                   cast_kind=CAST_POINT, area=8000.0))
    struct.pack_into('<2Q4I', payload, 64, 1048584, 1058000, 2, 0, 1, 0)
    struct.pack_into('<QIi', payload, 96, 1054455, 0x45303039, 5)
    struct.pack_into('<QIi', payload, 112, 1053592, 0x45303048, 5)
    struct.pack_into('<3Q', payload, 672, 1054455, 1054896, 1053553)
    struct.pack_into('<3I', payload, 724, 1, 0, 1)
    result = decode_work(payload, 1)
    assert result['selection']['count'] == 2
    assert result['source'] == 1054455


@pytest.mark.parametrize('did_cast', [False, True])
def test_native_area_cast_always_cleans_up(monkeypatch, did_cast):
    calls = []

    def world_cast(code, action, **kwargs):
        calls.append(action)
        if action == 1:
            return dict(source=1053592, ability_handle=1054896,
                        target=0, cast_kind=1, prior_area=0,
                        added=1, mana_before=420.0)
        if action == 3:
            return dict(source=1053592, mana_after=330.0 if did_cast else 420.0,
                        cooldown_after=6.0 if did_cast else 0.0)
        return dict(completed=1)

    engine = SimpleNamespace(world_cast=world_cast)
    trainer = SimpleNamespace(
        _coerce_memory_value=lambda kind, value: int.from_bytes(value.encode('ascii'), 'big'),
        _engine_instance_24268=lambda: engine,
    )
    monkeypatch.setattr(war3_reforged_trainer.time, 'sleep', lambda _: None)
    cast = war3_reforged_trainer.War3Trainer.cast_native_area_24268
    if did_cast:
        assert cast(trainer, 'AHtc', 852096)['state']['cooldown_after'] == 6.0
    else:
        with pytest.raises(RuntimeError, match='法力和冷却未变化'):
            cast(trainer, 'AHtc', 852096)
    assert calls == [1, 3, 2]
