"""Indexed player-state properties for build 24268 (no region scanning)."""
import struct


SOURCE = "3.0 indexed player properties"
PROPERTY_TAG = 0x60666C675E70726F
PLAYER_TAG = 0x2B706C792B61676C
REQUIRED_STATES = (0, 1, 2, 4, 5, 6)


def read_player_properties(memory, registry, player, player_id):
    def pointer(value):
        return 0x10000 <= value < 0x800000000000 and value % 8 == 0

    handle = memory.read_u64(player + 0x18)
    owner = registry.resolve_handle(memory, handle)
    if (memory.read_u64(owner + 0x18) != PLAYER_TAG
            or memory.read_u64(owner + 0x90) != player):
        raise RuntimeError("Resource player identity mismatches registry")
    descriptor = memory.read(owner + 0xA0, 0x30)
    array, capacity, mirror, mirror_capacity, stride, slots, count = struct.unpack_from("<QQQQIII", descriptor)
    if (not pointer(array) or not 0 < capacity <= 0x4000 or capacity % 8
            or mirror != array or mirror_capacity != capacity or stride != 8
            or slots * 8 != capacity or not 0 < count <= slots):
        raise RuntimeError("Invalid player property array")
    raw = memory.read(array, count * 8)
    states = {}
    identity_records = []
    for prop in struct.unpack(f"<{count}Q", raw):
        if not pointer(prop):
            continue
        record = memory.read(prop + 0x18, 0xBC)
        if struct.unpack_from("<Q", record)[0] != PROPERTY_TAG:
            continue
        packed = struct.unpack_from("<Q", record, 0x08)[0]
        backlink = struct.unpack_from("<Q", record, 0x38)[0]
        state = struct.unpack_from("<I", record, 0x64)[0]
        if backlink != owner:
            raise RuntimeError("Player property owner changed")
        # The packed ID names the object; +0x7c identifies its player state.
        # Gold=1, lumber=2, food cap=4, food used=5, food limit=6.
        kind = 1 + 0x28 * player_id + state
        if state > 25 or packed != (kind << 32) | kind or state in states:
            raise RuntimeError("Invalid or duplicate player-state property")
        states[state] = (prop + 0xD0, struct.unpack_from("<i", record, 0xB8)[0])
        identity_records.append((prop, packed, state))
    if any(state not in states for state in REQUIRED_STATES):
        raise RuntimeError("Incomplete player-state property list")
    if (memory.read(owner + 0xA0, 0x30) != descriptor
            or memory.read(array, count * 8) != raw
            or registry.resolve_handle(memory, handle) != owner
            or memory.read_u64(player + 0x18) != handle
            or memory.read_u64(owner + 0x90) != player):
        raise RuntimeError("Player property array changed while reading")
    for prop, packed, state in identity_records:
        if (memory.read_u64(prop + 0x18) != PROPERTY_TAG
                or memory.read_u64(prop + 0x20) != packed
                or memory.read_u64(prop + 0x50) != owner
                or memory.read_i32(prop + 0x7C) != state):
            raise RuntimeError("Player property identity changed while reading")
    return owner, handle, states
