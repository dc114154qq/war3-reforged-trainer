"""Build-24268 basic property writes with complete preflight and identity checks."""
import math
import struct

from war3_adapter_properties import BasicFieldCatalog

# Compatibility catalog; offsets are resolved from the active profile.
FIELDS = BasicFieldCatalog()
REAL_TAG = 0x6072656C5E70726F
POSITION_TAG = 0x607063755E70726F


def property_snapshot(memory, registry, candidate):
    from war3_game_profile import current_profile
    profile = getattr(registry, "profile", None) or current_profile()
    return profile.adapter.properties.property_snapshot(
        memory, registry, candidate, REAL_TAG, POSITION_TAG,
    )


def write_basic_fields(memory, registry, candidate, requested):
    values = {key: struct.unpack("<f", struct.pack("<f", float(value)))[0]
              for key, value in requested.items() if value is not None}
    if any(key not in FIELDS or not math.isfinite(value) for key, value in values.items()):
        raise ValueError("Invalid basic field request")
    if not values:
        return {}
    from war3_game_profile import current_profile
    profile = getattr(registry, "profile", None) or current_profile()
    adapter = profile.adapter.properties
    snapshot = property_snapshot(memory, registry, candidate)
    properties = snapshot[2]

    def address(key):
        kind, offset, attribute = FIELDS[key]
        if kind not in properties:
            raise RuntimeError("Unit has no property for field: " + key)
        result = adapter.basic_value_address(properties[kind][0], key)
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
