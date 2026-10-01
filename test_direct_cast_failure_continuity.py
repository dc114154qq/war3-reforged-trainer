import struct

import war3_engine_24268 as module


def _direct_result(error=353, completed=0, cleanup=0):
    payload = bytearray(824)
    struct.pack_into(
        "<16I", payload, 696, 1, 0x41457362, 1, 1, 0, 0, 1, 0,
        error, completed, 0, 0, 0, 0, 0, 0,
    )
    struct.pack_into("<I", payload, 820, cleanup)
    return bytes(payload)


def _evidence(payload):
    return {
        "callback_verified": True,
        "callback_exited": True,
        "query_completed": True,
        "work_freed": True,
        "block_freed": True,
        "image_unmap_status": "0x0",
        "work_result_hex": payload.hex(),
    }


def test_direct_cast_business_rejection_is_continuable():
    result = module.classify_direct_cast_failure(
        "direct_cast", _evidence(_direct_result()), _direct_result()
    )
    assert result == {
        "error": 353, "completed": 0, "cleanup": 0,
        "session_continuable": True,
    }


def test_direct_cast_cleanup_failure_is_not_continuable():
    result = module.classify_direct_cast_failure(
        "direct_cast", _evidence(_direct_result(cleanup=331)),
        _direct_result(cleanup=331),
    )
    assert result == {
        "error": 353, "completed": 0, "cleanup": 331,
        "session_continuable": False,
    }


def test_direct_cast_incomplete_transport_is_not_reclassified():
    evidence = _evidence(_direct_result())
    evidence["callback_exited"] = False
    assert module.classify_direct_cast_failure(
        "direct_cast", evidence, _direct_result()
    ) is None
