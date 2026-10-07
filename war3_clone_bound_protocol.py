"""Bound clone ABI: the unchanged clone prefix plus immutable source identities."""
import struct

import war3_clone_protocol as clone
from war3_game_session import FullHandle, NativeHandle, ObjectAddress, SessionIdentity, UnitRef

PREFIX_SIZE = 1888
HEADER_SIZE = 24
SOURCES_OFFSET = PREFIX_SIZE + HEADER_SIZE
SOURCE_SIZE = 32
MAX_SOURCES = 24
WORK_SIZE = 2680
ABI = struct.pack("<3I", 0x24268064, 216, WORK_SIZE)
SIGNATURES = clone.SIGNATURES


def validate_expected_sources(expected_sources):
    """Handle namespaces are deliberately not interchangeable."""
    if type(expected_sources) is not tuple or not 1 <= len(expected_sources) <= MAX_SOURCES:
        raise ValueError("Bound clone sources must be a tuple containing 1..24 bindings")
    seen_native, seen_full, seen_object = set(), set(), set()
    identity = None
    for binding in expected_sources:
        if type(binding) is not tuple or len(binding) != 2:
            raise TypeError("Bound clone binding must contain NativeHandle and UnitRef")
        native, ref = binding
        if type(native) is not NativeHandle or type(ref) is not UnitRef:
            raise TypeError("Bound clone binding requires NativeHandle and UnitRef")
        if (type(ref.handle) is not FullHandle or type(ref.address) is not ObjectAddress
                or type(ref.session) is not SessionIdentity
                or type(ref.epoch) is not int or ref.epoch < 0
                or not ref.handle.value
                or type(ref.rawcode) is not int or not 0 < ref.rawcode <= 0xFFFFFFFF):
            raise ValueError("Bound clone source identity is invalid")
        current = (ref.session, ref.epoch)
        if identity is not None and current != identity:
            raise ValueError("Bound clone sources belong to different sessions or epochs")
        identity = current
        if (native.value in seen_native or ref.handle.value in seen_full
                or ref.address.value in seen_object):
            raise ValueError("Bound clone contains duplicate source identities")
        seen_native.add(native.value)
        seen_full.add(ref.handle.value)
        seen_object.add(ref.address.value)
    return expected_sources


def _source_values(expected_sources):
    return tuple((native.value, ref.handle.value, ref.address.value, ref.rawcode, 0)
                 for native, ref in validate_expected_sources(expected_sources))


def _binding(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError("CloneBoundWork must contain exactly 2680 bytes")
    base, resolver, count, reserved = struct.unpack_from("<2Q2I", payload, PREFIX_SIZE)
    if (not 0x10000 <= base < 0x800000000000 or base % 8
            or not base < resolver < 0x800000000000
            or not 1 <= count <= MAX_SOURCES or reserved):
        raise ValueError("CloneBoundWork contains an invalid resolver or source count")
    sources = []
    for index in range(count):
        values = struct.unpack_from("<3Q2I", payload, SOURCES_OFFSET + index * SOURCE_SIZE)
        native, full, address, rawcode, reserved_row = values
        if (not native or not full or not rawcode or reserved_row
                or not 0x10000 <= address < 0x800000000000 or address % 8):
            raise ValueError("CloneBoundWork contains an invalid source identity")
        if any(native == row[0] or full == row[1] or address == row[2] for row in sources):
            raise ValueError("CloneBoundWork contains duplicate source identities")
        sources.append(values)
    if any(payload[SOURCES_OFFSET + count * SOURCE_SIZE:]):
        raise ValueError("CloneBoundWork unused sources must be zero-initialized")
    return tuple(sources)


def build_work(entries, tls, *, base, unit_resolver, expected_sources,
               flags=clone.CLONE_COPY_ABILITIES | clone.CLONE_COPY_ITEMS,
               spawn_x_bits=0, spawn_y_bits=0):
    sources = _source_values(expected_sources)
    if (type(base) is not int or type(unit_resolver) is not int
            or not 0x10000 <= base < unit_resolver < 0x800000000000 or base % 8):
        raise ValueError("Bound clone requires a valid module base and unit resolver")
    prefix = clone.build_work(entries, tls, flags=flags,
                              spawn_x_bits=spawn_x_bits, spawn_y_bits=spawn_y_bits)
    payload = (prefix + struct.pack("<2Q2I", base, unit_resolver, len(sources), 0)
               + b"".join(struct.pack("<3Q2I", *source) for source in sources)
               + bytes((MAX_SOURCES - len(sources)) * SOURCE_SIZE))
    validate_work(payload)
    return payload


def validate_work(payload):
    _binding(payload)
    clone.validate_work(payload[:PREFIX_SIZE])


def decode_work(payload, expected_count, *, expected_sources=None):
    sources = _binding(payload)
    if type(expected_count) is not int or expected_count != len(sources):
        raise ValueError("Bound clone result source count differs from request")
    if expected_sources is not None and sources != _source_values(expected_sources):
        raise ValueError("Bound clone result binding differs from request")
    result = clone.decode_work(payload[:PREFIX_SIZE], expected_count)
    for row, source in zip(result["rows"], sources):
        if (row["handle"], row["rawcode"]) != (source[0], source[3]):
            raise ValueError("Bound clone result selection differs from initial sources")
    return result


def failure_status(payload):
    """The clone prefix owns rollback/exception evidence, even on a bound failure."""
    if len(payload) != WORK_SIZE:
        return None
    return clone.failure_status(payload[:PREFIX_SIZE])
