import struct

from war3_extension_protocol import WORK_SIZE, build_work, decode_work, validate_work
from war3_extension_protocol import SIGNATURES as EXTENSION_SIGNATURES
from war3_native_table import LiveNativeEntry
from war3_selection_protocol import SIGNATURES as SELECTION_SIGNATURES


def entries():
    return {
        name: LiveNativeEntry(name, signature, 0x300000 + index * 0x80, 0x500000 + index * 0x100)
        for index, (name, signature) in enumerate(SELECTION_SIGNATURES + EXTENSION_SIGNATURES)
    }


def test_extension_snapshot_decodes_bag_equipment_and_talents():
    controller = int.from_bytes(b"ATua", "big")
    choice = int.from_bytes(b"AT1b", "big")
    payload = bytearray(build_work(entries(), 0x10000000, (controller, choice)))
    unit = 0x200000
    struct.pack_into("<2Q4I", payload, 64, 0x110000, 0x120000, 1, 0, 1, 0)
    struct.pack_into("<QIi", payload, 96, unit, int.from_bytes(b"HERO", "big"), 8)
    struct.pack_into("<Q", payload, 624, unit)
    struct.pack_into("<10I", payload, 640, 0, 0, 0, 2, 0, 1, 0, 30, 0, 0)
    struct.pack_into("<2i", payload, 776, 6, 1)
    struct.pack_into("<QIiII", payload, 872, 0x210000, int.from_bytes(b"ckng", "big"), 3, 0, 0)
    struct.pack_into("<QIiII", payload, 1592, 0x220000, int.from_bytes(b"eeh3", "big"), 0, 1, 0)

    result = decode_work(bytes(payload), 1)

    assert len(payload) == WORK_SIZE
    assert result["bag_size"] == 30
    assert result["bag"][0]["rawcode"] == int.from_bytes(b"ckng", "big")
    assert result["equipment"][0]["rawcode"] == int.from_bytes(b"eeh3", "big")
    assert result["abilities"] == {controller: 6, choice: 1}


def test_extension_protocol_rejects_more_than_24_ability_probes():
    try:
        build_work(entries(), 0x10000000, range(1, 26))
    except ValueError as exc:
        assert "exceeds 24" in str(exc)
    else:
        raise AssertionError("oversized ability probe was accepted")


def test_extension_protocol_input_validation():
    payload = build_work(entries(), 0x10000000, (int.from_bytes(b"ATua", "big"),))
    validate_work(payload)


def test_extension_protocol_accepts_identity_bound_internal_cleanup():
    payload = build_work(
        entries(), 0x10000000, action=8, target_unit=0x200000,
        item_rawcode=int.from_bytes(b"pman", "big"), item_handle=0x210000,
    )

    validate_work(payload)
