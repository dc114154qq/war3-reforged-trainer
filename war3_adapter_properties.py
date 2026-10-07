"""Property-record adapter. Business write semantics remain in war3_basic_fields."""
from functools import cached_property
from operator import itemgetter
import struct
from collections.abc import Mapping

_BASIC_FIELDS = {"hp_current": "value", "mp_current": "value", "hp_max": "maximum",
                 "mp_max": "maximum", "hp_regen": "regen", "mp_regen": "regen",
                 "x": "position_x", "y": "position_y"}


class BasicFieldCatalog(Mapping):
    """Preserve the old (kind, offset, attribute) API without fixed offsets."""
    def __iter__(self):
        return iter(_BASIC_FIELDS)

    def __len__(self):
        return len(_BASIC_FIELDS)

    def __getitem__(self, key):
        from war3_game_profile import current_profile
        field = _BASIC_FIELDS[key]
        kind = 1 if key.startswith("hp_") else 2 if key.startswith("mp_") else -1
        return kind, current_profile().section("layouts")["property"][field], key + "_address"

class PropertyAdapter:
    def __init__(self, profile):
        self.profile = profile

    @cached_property
    def layout(self):
        return self.profile.section("layouts")["property"]

    @cached_property
    def descriptor_decoder(self):
        names = ("array", "capacity", "mirror", "mirror_capacity", "stride", "slots", "count")
        ordered = sorted(names, key=self.layout.__getitem__)
        parts, cursor = ["<"], 0
        for name in ordered:
            gap = self.layout[name] - cursor
            if gap:
                parts.append(str(gap) + "x")
            wide = name in names[:4]
            parts.append("Q" if wide else "I")
            cursor = self.layout[name] + (8 if wide else 4)
        indices = tuple(ordered.index(name) for name in names)
        return struct.Struct("".join(parts)), None if indices == tuple(range(len(names))) else itemgetter(*indices)

    def descriptor(self, block):
        decoder, reorder = self.descriptor_decoder
        values = decoder.unpack_from(block)
        return reorder(values) if reorder else values

    def basic_value_address(self, property_address, key):
        name = _BASIC_FIELDS[key]
        return property_address + self.layout[name]

    def property_snapshot(self, memory, registry, candidate, REAL_TAG, POSITION_TAG):
        layout = self.layout
        owner, unit = candidate.owner_address, candidate.unit_address
        if registry.resolve_unit(memory, unit) != (candidate.handle, owner):
            raise RuntimeError("Basic field unit identity changed")
        descriptor = memory.read(owner + layout["owner_descriptor"], layout["descriptor_size"])
        array, capacity, mirror, mirror_capacity, stride, slots, count = self.descriptor(descriptor)
        if (not 0x10000 <= array < 0x800000000000 or array % 8
                or not 0 < capacity <= 0x4000 or capacity != slots * 8
                or mirror != array or mirror_capacity != capacity or stride != 8
                or not 0 < count <= slots):
            raise RuntimeError("Basic field property list is invalid")
        pointers = memory.read(array, count * 8)
        properties = {}
        for prop in struct.unpack(f"<{count}Q", pointers):
            if not 0x10000 <= prop < 0x800000000000 or prop % 8:
                raise RuntimeError("Basic field property pointer is invalid")
            tag = memory.read_u64(prop + layout["tag"])
            if tag not in (REAL_TAG, POSITION_TAG):
                continue
            kind = -1 if tag == POSITION_TAG else memory.read_u32(prop + layout["kind"])
            if kind not in (-1, 1, 2):
                continue
            if memory.read_u64(prop + layout["owner"]) != owner or kind in properties:
                raise RuntimeError("Basic field property ownership is inconsistent")
            properties[kind] = (prop, memory.read_u64(prop + layout["handle"]), tag)
        if (memory.read(owner + layout["owner_descriptor"], layout["descriptor_size"]) != descriptor
                or memory.read(array, count * 8) != pointers
                or registry.resolve_unit(memory, unit) != (candidate.handle, owner)):
            raise RuntimeError("Basic field property list changed while reading")
        return descriptor, pointers, properties

    def player_properties(self, memory, registry, player, player_id, PROPERTY_TAG, PLAYER_TAG, REQUIRED_STATES):
        layout, object_layout = self.layout, self.profile.section("registry")
        def pointer(value):
            return 0x10000 <= value < 0x800000000000 and value % 8 == 0

        handle = memory.read_u64(player + object_layout["object_handle"])
        owner = registry.resolve_handle(memory, handle)
        if (memory.read_u64(owner + object_layout["owner_tag"]) != PLAYER_TAG
                or memory.read_u64(owner + object_layout["owner_data"]) != player):
            raise RuntimeError("Resource player identity mismatches registry")
        descriptor = memory.read(owner + layout["owner_descriptor"], layout["descriptor_size"])
        array, capacity, mirror, mirror_capacity, stride, slots, count = self.descriptor(descriptor)
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
            record = memory.read(prop + layout["resource_snapshot_start"], layout["resource_snapshot_size"])
            if struct.unpack_from("<Q", record, layout["tag"] - layout["resource_snapshot_start"])[0] != PROPERTY_TAG:
                continue
            packed = struct.unpack_from("<Q", record, layout["handle"] - layout["resource_snapshot_start"])[0]
            backlink = struct.unpack_from("<Q", record, layout["owner"] - layout["resource_snapshot_start"])[0]
            state = struct.unpack_from("<I", record, layout["kind"] - layout["resource_snapshot_start"])[0]
            if backlink != owner:
                raise RuntimeError("Player property owner changed")
            # The packed ID names the object; +0x7c identifies its player state.
            # Gold=1, lumber=2, food cap=4, food used=5, food limit=6.
            kind = 1 + layout["state_identity_stride"] * player_id + state
            if state > 25 or packed != (kind << 32) | kind or state in states:
                raise RuntimeError("Invalid or duplicate player-state property")
            states[state] = (prop + layout["value"], struct.unpack_from("<i", record, layout["value"] - layout["resource_snapshot_start"])[0])
            identity_records.append((prop, packed, state))
        if any(state not in states for state in REQUIRED_STATES):
            raise RuntimeError("Incomplete player-state property list")
        if (memory.read(owner + layout["owner_descriptor"], layout["descriptor_size"]) != descriptor
                or memory.read(array, count * 8) != raw
                or registry.resolve_handle(memory, handle) != owner
                or memory.read_u64(player + object_layout["object_handle"]) != handle
                or memory.read_u64(owner + object_layout["owner_data"]) != player):
            raise RuntimeError("Player property array changed while reading")
        for prop, packed, state in identity_records:
            if (memory.read_u64(prop + layout["tag"]) != PROPERTY_TAG
                    or memory.read_u64(prop + layout["handle"]) != packed
                    or memory.read_u64(prop + layout["owner"]) != owner
                    or memory.read_i32(prop + layout["kind"]) != state):
                raise RuntimeError("Player property identity changed while reading")
        return owner, handle, states

