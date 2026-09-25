import struct
from types import SimpleNamespace
import pytest
from war3_selection_protocol import SIGNATURES as SELECTION
from war3_talent_order_protocol import SIGNATURES, WORK_SIZE, build_work, validate_work, decode_work


def request(order=0xd0311):
    entries = {name: SimpleNamespace(name=name, signature=signature, handler=0x300000+i*0x100)
               for i, (name, signature) in enumerate(SELECTION + SIGNATURES)}
    return build_work(entries, 0x200000, 0x101400, 0x41547567, order, 0x55543161)


def test_native_order_request_contains_no_output_or_unbound_target():
    payload = request()
    assert len(payload) == WORK_SIZE
    assert struct.unpack_from("<Q", payload, 504)[0] == 0x101400
    malformed = bytearray(payload)
    struct.pack_into("<I", malformed, 532, 1)
    with pytest.raises(ValueError):
        validate_work(bytes(malformed))


def test_native_order_cannot_send_other_game_commands():
    with pytest.raises(ValueError):
        request(851972)


def test_native_order_rejects_false_success_without_effect():
    response = bytearray(request())
    struct.pack_into("<5I", response, 524, 0, 0, 1, 0, 1)
    with pytest.raises(ValueError):
        decode_work(bytes(response), 1)
    struct.pack_into("<I", response, 528, 1)
    assert decode_work(bytes(response), 1)["accepted"] == 1
