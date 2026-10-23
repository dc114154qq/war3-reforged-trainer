"""Explicit production-operation dependency inventory for discovered profiles.

Exact, maintained profiles do not execute this inventory in their hot path.
"""
COMMON = frozenset({"registry", "decoder", "context", "native_table",
                    "addresses.registry_root", "addresses.object_resolver",
                    "addresses.game_state", "addresses.tls_index", "checks"})
NATIVE = COMMON | {"native_abi"}
FIELDS = COMMON | {"players", "layouts", "selection", "modules.legacy_layout"}
EQUIPMENT = NATIVE
EQUIPMENT_RUNTIME = NATIVE | {
    "equipment_runtime", "layouts.ability", "layouts.component_list",
    "layouts.inventory", "layouts.equipment_record", "layouts.item", "modules.equipment"}
TALENTS = NATIVE | {"layouts.talent", "layouts.ability", "modules.talents"}
EFFECT = NATIVE | {"layouts.effect", "layouts.ability", "layouts.component_list", "modules.direct_effect"}
ATTACK = NATIVE | {"addresses.unit_resolver", "addresses.speed_factor",
                   "addresses.effective_interval", "bridge_layout.unit_attack"}
PROPERTY_IDENTITY = COMMON | {"modules.legacy_layout"} | {
    "layouts.property."+key for key in (
        "owner_descriptor", "descriptor_size", "array", "capacity", "mirror",
        "mirror_capacity", "stride", "slots", "count", "tag", "handle", "owner", "kind")}
PROPERTY_FIELDS = {"hp_current": "value", "mp_current": "value", "hp_max": "maximum",
                   "mp_max": "maximum", "hp_regen": "regen", "mp_regen": "regen",
                   "x": "position_x", "y": "position_y"}
SELECTED_READ = COMMON | {"players.count", "players.array", "players.max_count",
                          "selection.read_only", "modules.legacy_layout"}
DEPENDENCIES = {
    'clone_state': EQUIPMENT_RUNTIME | TALENTS | {'addresses.unit_resolver','bridge_layout.ability_level_tail'},
    "gold_mine": NATIVE,
    "item_safety": NATIVE, "equipment_effect": EQUIPMENT_RUNTIME,
    "legacy_equipment_probe": EQUIPMENT_RUNTIME, "game_speed": NATIVE,
    "direct_cast": EFFECT | {"bridge_layout.ability_level_tail"}, "talent_icon_control": TALENTS | {"modules.talent_icons", "module_addresses"},
    "hero": NATIVE, "hero_attributes": NATIVE,
    "attack_speed": ATTACK, "unit_stats": NATIVE,
    "talent_order": NATIVE, "talent_probe": NATIVE,
    "stat_details": NATIVE | {"stat_runtime", "layouts.ability", "layouts.component_list", "modules.stat_details"},
    "ability": NATIVE | {"layouts.ability", "bridge_layout.ability_level_tail"},
    "ability_field": NATIVE,
    "item": NATIVE, "item_catalog": NATIVE | {"equipment_runtime"},
    "item_effect": NATIVE | {"layouts.item", "layouts.ability", "layouts.component_list", "layouts.equipment_record", "equipment_runtime", "addresses.unit_resolver"},
    "item_field": NATIVE, "item_ability": NATIVE | {"layouts.item","equipment_runtime.item_rawcode_mirror"},
    "clone": NATIVE | {"bridge_layout.ability_level_tail"},
    "unit_action": NATIVE, "clone_bound": NATIVE | {"addresses.unit_resolver", "bridge_layout.ability_level_tail"},
    "unit_bindings": NATIVE | {"addresses.unit_resolver"},
    "world": NATIVE | {"fog_recovery"}, "bulk": NATIVE,
    "effect": EFFECT, "world_effect": EFFECT, "world_cast": NATIVE,
    "spawn": NATIVE, "mouse": NATIVE, "screen_mouse": NATIVE,
    "camera": NATIVE, "position": NATIVE, "position_target": NATIVE,
    "terrain": NATIVE, "equipment": EQUIPMENT, "equipment_probe": EQUIPMENT,
    "cooldown_probe": NATIVE, "extension": EQUIPMENT | TALENTS,
    "map_bounds": NATIVE,
    # External reads / writes and continuous services also participate.
    "basic_fields": FIELDS,
    "property_write": PROPERTY_IDENTITY | {"layouts.property."+value for value in PROPERTY_FIELDS.values()},
    "resources": PROPERTY_IDENTITY | {"layouts.property.resource_snapshot_start", "layouts.property.resource_snapshot_size",
                                       "layouts.property.state_identity_stride", "layouts.property.value"},
    "selected_units": SELECTED_READ | {"players.normal_index", "players.alternate_index"},
    "external_items": FIELDS | EQUIPMENT_RUNTIME,
    "speed_clock": NATIVE,
}


def dependencies_for(name, request=None):
    if name in ('clone', 'clone_bound') and request is not None:
        # The native copy helper calls the checked level setter indirectly.
        # Copying no abilities does not consume its version-specific fault site.
        required = NATIVE | ({'addresses.unit_resolver'} if name == 'clone_bound' else set())
        if request.get('copy_abilities', True) is not False:
            required |= {'bridge_layout.ability_level_tail'}
        return required
    if name == 'ability' and request is not None:
        action = request.get('action')
        if action in (0, 2):
            return NATIVE
        if action in (1, 3, 4, 5):
            return NATIVE | {'bridge_layout.ability_level_tail'}
        raise ValueError('Invalid ability action')
    if name == 'world' and request is not None:
        action = request.get('action')
        if action in (1, 2, 5, 6):
            return NATIVE
        if action==3:
            return NATIVE | {'fog_recovery.enabled_gate','fog_recovery.masked_gate'}
        if action==4:return NATIVE | {'fog_recovery'}
        raise ValueError('Invalid world action')
    if name == 'selected_units' and request is not None:
        mode = request.get('mode')
        if mode not in (0, 1):
            raise ValueError('Invalid selection mode')
        return SELECTED_READ | {'players.' + ('alternate_index' if mode else 'normal_index')}
    if name == 'property_write' and request is not None:
        fields = tuple(key for key, value in request.items() if value is not None)
        if any(key not in PROPERTY_FIELDS for key in fields):
            raise ValueError('Invalid basic field request')
        required = PROPERTY_IDENTITY | {'layouts.property.'+PROPERTY_FIELDS[key] for key in fields}
        # Raising current health/mana may also raise its maximum; declare the
        # implicit write before executing either write, not after a partial update.
        if any(key in ('hp_current','mp_current') for key in fields):
            required |= {'layouts.property.maximum'}
        return required
    if name == "extension" and request is not None:
        action = request.get("action", 0)
        if action == 10: return TALENTS
        if action in (11, 12): return EQUIPMENT_RUNTIME
        if action in range(10): return NATIVE
    if name not in DEPENDENCIES:
        raise ValueError("Operation missing discovery dependency inventory: " + name)
    return DEPENDENCIES[name]


def missing_dependencies(evidence, required):
    confirmed = {name for name, value in evidence.items() if value.state == "confirmed"}
    # A group proof covers its leaves; a leaf never proves its whole parent.
    return tuple(sorted(name for name in required if not any(
        name == parent or name.startswith(parent+".") for parent in confirmed)))


def audit_inventory():
    from war3_operations import OPERATIONS
    missing = sorted(set(OPERATIONS) - DEPENDENCIES.keys())
    if missing: raise AssertionError("Uninventoried operations: " + repr(missing))
    return {name: sorted(dependencies_for(name)) for name in OPERATIONS}
