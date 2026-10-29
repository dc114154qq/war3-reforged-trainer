"""Bounded V1 hash-directory growth without inventing unknown filenames.

Replicating the original probe array preserves successful unknown lookups:
modulo r*N, a start initially sees the same original N-slot sequence. Known
entries become tombstones and are inserted once at their actual full hash;
insertion never adds an earlier empty slot to a successful probe. File blocks,
their offsets, encryption keys and the block table are not moved or rewritten.
"""
from pathlib import Path
import struct

MAX_SLOTS = 262144
MASK = 0xffffffff
EMPTY = MASK
DELETED = MASK-1
ROW = struct.Struct('<IIHHI')


def _crypt_table():
    values = [0]*1280
    seed = 0x100001
    for low in range(256):
        for high in range(5):
            seed = (seed*125+3) % 0x2aaaab
            first = (seed & 65535) << 16
            seed = (seed*125+3) % 0x2aaaab
            values[high*256+low] = first | (seed & 65535)
    return tuple(values)


CRYPT = _crypt_table()


def name_hash(name, kind):
    first, second = 0x7fed7fed, 0xeeeeeeee
    for char in name.encode('utf8').replace(b'/', b'\\').upper():
        first = (CRYPT[(kind << 8)+char] ^ ((first+second) & MASK)) & MASK
        second = (char+first+second+(second << 5)+3) & MASK
    return first


def crypt_hash_table(raw, *, encrypt=False):
    if len(raw) % 4:
        raise ValueError('MPQ hash table length is not DWORD aligned')
    key, seed = name_hash('(hash table)', 3), 0xeeeeeeee
    result = bytearray(len(raw))
    for offset in range(0, len(raw), 4):
        value = struct.unpack_from('<I', raw, offset)[0]
        seed = (seed+CRYPT[0x400+(key & 255)]) & MASK
        encoded = (value ^ ((key+seed) & MASK)) & MASK
        struct.pack_into('<I', result, offset, encoded)
        key = (((~key << 21)+0x11111111) | (key >> 11)) & MASK
        plain = value if encrypt else encoded
        seed = (plain+seed+(seed << 5)+3) & MASK
    return bytes(result)


def read_directory(path, offset):
    path = Path(path)
    with path.open('rb') as stream:
        stream.seek(offset); raw = stream.read(32)
        if len(raw) != 32:
            raise ValueError('MPQ header is incomplete')
        header = struct.unpack('<IIIHHIIII', raw)
        magic, length, size, version, sectors, hashes, blocks, count, block_count = header
        if (magic != 0x1a51504d or length != 32 or version != 0 or sectors > 16
                or not 0 < count <= MAX_SLOTS or count & (count-1)
                or not 0 < block_count <= 100000 or size > path.stat().st_size-offset
                or hashes < 32 or blocks < 32 or hashes+count*16 > size
                or blocks+block_count*16 > size
                or not (hashes+count*16 <= blocks or blocks+block_count*16 <= hashes)):
            raise ValueError('MPQ directory does not have a bounded classic V1 layout')
        stream.seek(offset+hashes); encoded = stream.read(count*16)
    if len(encoded) != count*16:
        raise ValueError('MPQ hash table is incomplete')
    rows = tuple(ROW.iter_unpack(crypt_hash_table(encoded)))
    if any(row[4] < DELETED and row[4] >= block_count for row in rows):
        raise ValueError('MPQ hash entry refers outside the original block table')
    return header, rows


def growth_plan(path, offset, members, requested, additional, *, check=None):
    from war3_mpq import unknown_member_name
    header, old = read_directory(path, offset)
    known = {}
    for member in members:
        if check: check()
        # Synthetic block-index names are not names to hash or write.
        if unknown_member_name(member.name): continue
        if not 0 <= member.hash_index < len(old):
            raise ValueError('MPQ member has no verified hash-table slot')
        row = old[member.hash_index]
        if (row[0] != name_hash(member.name, 1) or row[1] != name_hash(member.name, 2)
                or row[2] != member.locale or row[4] != member.block_index):
            raise ValueError('MPQ member name does not match its original hash entry')
        if row in known and known[row].casefold() != member.name.casefold():
            raise ValueError('MPQ filename identity is ambiguous')
        known[row] = member.name
    unknown = sum(row[4] < DELETED and row not in known for row in old)
    capacity = max(len(old)*2, requested)
    if capacity & (capacity-1):
        raise ValueError('MPQ requested capacity is not a power of two')
    while capacity <= MAX_SLOTS:
        factor = capacity // len(old)
        occupied = len(known)+unknown*factor
        if occupied+additional+8 <= capacity: break
        capacity *= 2
    if capacity > MAX_SLOTS or capacity // len(old) > 64:
        raise ValueError('MPQ filename-preserving growth exceeds the bounded directory budget')
    tombstone = (MASK, MASK, 65535, 65535, DELETED)
    expanded = [tombstone if row in known else row for row in old]*factor
    probes = 0
    for row, name in known.items():
        start = name_hash(name, 0) & (capacity-1)
        for distance in range(capacity):
            probes += 1
            if probes % 256 == 0 and check: check()
            if probes > 4000000:
                raise ValueError('MPQ hash insertion exceeds the bounded probe budget')
            index = (start+distance) & (capacity-1)
            if expanded[index][4] >= DELETED:
                expanded[index] = row
                break
        else:
            raise ValueError('MPQ hash table has no insertion slot')
    table = crypt_hash_table(b''.join(ROW.pack(*row) for row in expanded), encrypt=True)
    details = dict(strategy='replicated_unknown_probe_chains_known_names_rehashed',
        original_capacity=len(old), actual_capacity=capacity, replication_factor=factor,
        known_hash_entries=len(known), unknown_hash_entries=unknown,
        preserved_unknown_slots=unknown*factor, occupied_slots=occupied,
        file_blocks_moved=False, original_hash_chains_preserved=True)
    return table, details
