import struct
from unittest.mock import Mock

import pytest

from war3_bulk_protocol import (
    BULK_COMPLETE_LOCAL_STRUCTURES,
    SELECTION_SIZE,
    SIGNATURES,
    WORK_SIZE,
    build_work,
    decode_work,
)
from war3_native_table import LiveNativeEntry
from war3_selection_protocol import SIGNATURES as SELECTION_SIGNATURES
from war3_engine_24268 import Engine24268
import war3_reforged_trainer as product


def entries():
    signatures = dict(SELECTION_SIGNATURES)
    signatures.update(dict(SIGNATURES))
    return {
        name: LiveNativeEntry(name, signature, 0x300000 + index * 80, 0x500000 + index * 256)
        for index, (name, signature) in enumerate(signatures.items())
    }


def completed_payload(changed):
    payload = bytearray(build_work(
        entries(), 0x10000000, BULK_COMPLETE_LOCAL_STRUCTURES,
    ))
    struct.pack_into(
        "<6I", payload, SELECTION_SIZE + 152,
        BULK_COMPLETE_LOCAL_STRUCTURES, 0, changed, 0, 1, 0,
    )
    return bytes(payload)


def test_rapid_build_protocol_accepts_empty_and_nonempty_rounds():
    assert len(completed_payload(0)) == WORK_SIZE
    assert decode_work(completed_payload(0))["changed"] == 0
    assert decode_work(completed_payload(3))["changed"] == 3


def test_rapid_build_protocol_rejects_unknown_action():
    with pytest.raises(ValueError, match="bulk action"):
        build_work(entries(), 0x10000000, BULK_COMPLETE_LOCAL_STRUCTURES + 1)


def test_product_rapid_build_uses_current_engine_bulk_batch():
    trainer = object.__new__(product.War3Trainer)
    trainer._native_selection_unavailable = True
    trainer.bulk_batch_24268 = Mock(return_value={"changed": 4})
    assert trainer.complete_local_player_structures() == 4
    trainer.bulk_batch_24268.assert_called_once_with(BULK_COMPLETE_LOCAL_STRUCTURES)


def test_product_rapid_build_does_not_fall_back_to_legacy_helper():
    trainer = object.__new__(product.War3Trainer)
    trainer._native_selection_unavailable = False
    trainer.bulk_batch_24268 = Mock(side_effect=AssertionError("current engine called"))
    with pytest.raises(RuntimeError, match="Warcraft III 3.0"):
        trainer.complete_local_player_structures()
    trainer.bulk_batch_24268.assert_not_called()


def test_engine_requests_selection_and_bulk_natives_together():
    engine = object.__new__(Engine24268)
    engine._execute = Mock(return_value={"changed": 0})
    engine.bulk_batch(BULK_COMPLETE_LOCAL_STRUCTURES)
    names = engine._execute.call_args.args[1]
    assert set(dict(SELECTION_SIGNATURES)).issubset(names)
    assert set(dict(SIGNATURES)).issubset(names)
