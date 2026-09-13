"""Build-24268 basic property writes with complete preflight and identity checks."""
import math
import struct

# Key -> (property kind, value offset, UnitCandidate address member)
FIELDS = {
    "hp_current": (1, 0xD0, "hp_current_address"),
    "hp_max": (1, 0xE0, "hp_max_address"),
    "hp_regen": (1, 0xD4, "hp_regen_address"),
    "mp_current": (2, 0xD0, "mp_current_address"),
    "mp_max": (2, 0xE0, "mp_max_address"),
    "mp_regen": (2, 0xD4, "mp_regen_address"),
    "x": (-1, 0xD0, "x_address"),
    "y": (-1, 0xD4, "y_address"),
}
REAL_TAG = 0x6072656C5E70726F
POSITION_TAG = 0x607063755E70726F


def property_snapshot(memory, registry, candidate):
    owner, unit = candidate.owner_address, candidate.unit_address
    if registry.resolve_unit(memory, unit) != (candidate.handle, owner):
        raise RuntimeError("Basic field unit identity changed")
    descriptor = memory.read(owner + 0xA0, 0x30)
    array, capacity, mirror, mirror_capacity, stride, slots, count = struct.unpack_from("<QQQQIII", descriptor)
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
        tag = memory.read_u64(prop + 0x18)
        if tag not in (REAL_TAG, POSITION_TAG):
            continue
        kind = -1 if tag == POSITION_TAG else memory.read_u32(prop + 0x7C)
        if kind not in (-1, 1, 2):
            continue
        if memory.read_u64(prop + 0x50) != owner or kind in properties:
            raise RuntimeError("Basic field property ownership is inconsistent")
        properties[kind] = (prop, memory.read_u64(prop + 0x20), tag)
    if (memory.read(owner + 0xA0, 0x30) != descriptor
            or memory.read(array, count * 8) != pointers
            or registry.resolve_unit(memory, unit) != (candidate.handle, owner)):
        raise RuntimeError("Basic field property list changed while reading")
    return descriptor, pointers, properties


def write_basic_fields(memory, registry, candidate, requested):
    values = {key: struct.unpack("<f", struct.pack("<f", float(value)))[0]
              for key, value in requested.items() if value is not None}
    if any(key not in FIELDS or not math.isfinite(value) for key, value in values.items()):
        raise ValueError("Invalid basic field request")
    if not values:
        return {}
    snapshot = property_snapshot(memory, registry, candidate)
    properties = snapshot[2]

    def address(key):
        kind, offset, attribute = FIELDS[key]
        if kind not in properties:
            raise RuntimeError("Unit has no property for field: " + key)
        result = properties[kind][0] + offset
        if result != getattr(candidate, attribute):
            raise RuntimeError("Basic field address changed: " + key)
        return result

    # Match existing UI behavior: setting current life/mana above its ceiling
    # raises the ceiling as well. Preflight both properties before any write.
    for prefix in ("hp", "mp"):
        current, maximum = prefix + "_current", prefix + "_max"
        if current in values:
            limit = values.get(maximum, memory.read_f32(address(maximum)))
            if values[current] > limit:
                values[maximum] = float(math.ceil(values[current]))
    plan = [(key, address(key), value) for key, value in values.items()]
    for key, addr, value in plan:
        if not math.isfinite(memory.read_f32(addr)):
            raise RuntimeError("Basic field contains a non-finite value: " + key)
        if key in ("hp_max", "mp_max") and not (1 if key == "hp_max" else 0) <= value <= 1e9:
            raise ValueError("Maximum vital is outside supported bounds")
        if key in ("hp_current", "mp_current") and not -1e8 <= value <= 1e8:
            raise ValueError("Current vital is outside supported bounds")
        if key in ("x", "y") and abs(value) > 1e6:
            raise ValueError("Position is outside supported bounds")
    # Write maximums before currents to avoid an intermediate clipped value.
    plan.sort(key=lambda item: item[0] not in ("hp_max", "mp_max"))
    written = []
    try:
        for key, addr, value in plan:
            if property_snapshot(memory, registry, candidate) != snapshot:
                raise RuntimeError("Basic field identity changed before write")
            memory.write_f32(addr, value)
            written.append(key)
            actual = memory.read_f32(addr)
            if not math.isfinite(actual) or actual != value:
                raise RuntimeError("Basic field readback differs from request: " + key)
        if property_snapshot(memory, registry, candidate) != snapshot:
            raise RuntimeError("Basic field identity changed after write")
    except Exception as exc:
        exc.add_note("Completed basic field writes: " + ", ".join(written))
        raise
    return {key: memory.read_f32(addr) for key, addr, _ in plan}
