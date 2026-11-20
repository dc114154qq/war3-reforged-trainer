"""Bounded, read-only lookup of live map ability definitions."""
import struct

MAX_ROWS = 64
WORK_SIZE = 32 + MAX_ROWS * 16
ABI = struct.pack('<3I', 0x242680a1, 216, WORK_SIZE)
SIGNATURES = (('BlzGetAbilityManaCost', '(II)I'),)


def build_work(entries, tls, codes):
    entry = entries.get(SIGNATURES[0][0])
    if entry is None or (entry.name, entry.signature) != SIGNATURES[0]:
        raise ValueError('Ability definition native signature differs')
    codes = tuple(codes)
    if (not 1 <= len(codes) <= MAX_ROWS or len(set(codes)) != len(codes)
            or any(type(c) is not int or not 0 < c <= 0xffffffff for c in codes)):
        raise ValueError('Invalid ability definition IDs')
    data = struct.pack('<2Q4I', entry.handler, tls, len(codes), 0, 0, 0)
    data += b''.join(struct.pack('<4I', c, 0, 0, 0) for c in codes)
    data += bytes((MAX_ROWS-len(codes))*16)
    validate_work(data)
    return data


def validate_work(data):
    if len(data) != WORK_SIZE:
        raise ValueError('Invalid ability definition payload size')
    fn, tls, count, error, completed, reserved = struct.unpack_from('<2Q4I', data)
    if (any(not 0x10000 <= p < 0x800000000000 for p in (fn, tls)) or tls % 8
            or not 1 <= count <= MAX_ROWS or error or completed or reserved):
        raise ValueError('Invalid ability definition request')
    codes = []
    for i in range(MAX_ROWS):
        code, level, cost, extra = struct.unpack_from('<4I', data, 32+i*16)
        if i < count:
            if not code or level or cost or extra:
                raise ValueError('Invalid ability definition row')
            codes.append(code)
        elif code or level or cost or extra:
            raise ValueError('Trailing ability definition row')
    if len(set(codes)) != count:
        raise ValueError('Duplicate ability definition row')


def decode_work(data, _count):
    if len(data) != WORK_SIZE:
        raise ValueError('Truncated ability definition response')
    count, error, completed, reserved = struct.unpack_from('<4I', data, 16)
    if error or reserved or not 1 <= count <= MAX_ROWS or completed != count:
        raise ValueError(f'Ability definition lookup failed: {error}, {completed}/{count}')
    rows = []
    for i in range(count):
        code, level, cost, extra = struct.unpack_from('<2IiI', data, 32+i*16)
        if not code or level or extra:
            raise ValueError('Invalid ability definition readback')
        rows.append(dict(rawcode=code, mana_cost=cost))
    return dict(rows=rows, completed=completed)
