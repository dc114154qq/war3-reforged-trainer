"""Fixed operation catalog: protocol ABI, capability and success semantics.

Compiled wrappers still own the native machine ABI. Packs cannot import modules.
"""

from dataclasses import dataclass
from functools import lru_cache
from importlib import import_module
import struct


@dataclass(frozen=True)
class OperationSpec:
    kind: str
    protocol: str | None
    marker: bytes
    query: bytes
    diagnostic: bool = False
    readback: bool = False
    backend: str = "game_thread"
    replay: str = "only_if_callback_never_started_and_cleanup_complete"


OPERATIONS = {
    "talent_icon_control": OperationSpec(
        "talent_icon_control",
        "war3_talent_icon_control_protocol",
        b"talent_icon_control_abi",
        b"BridgeTalentIconControl",
        False,
        False,
    ),
    "hero": OperationSpec(
        "hero", "war3_hero_protocol", b"bridge_abi", b"BridgeHeroQuery", False, True
    ),
    "hero_attributes": OperationSpec(
        "hero_attributes",
        "war3_hero_attributes_protocol",
        b"hero_attributes_batch_abi",
        b"BridgeHeroAttributesQuery",
        False,
        True,
    ),
    "attack_speed": OperationSpec(
        "attack_speed",
        "war3_attack_speed_protocol",
        b"attack_speed_batch_abi",
        b"BridgeAttackSpeedQuery",
        False,
        True,
    ),
    "unit_stats": OperationSpec(
        "unit_stats",
        "war3_unit_stats_protocol",
        b"unit_stats_batch_abi",
        b"BridgeUnitStatsQuery",
        False,
        True,
    ),
    "talent_order": OperationSpec(
        "talent_order",
        "war3_talent_order_protocol",
        b"talent_order_abi",
        b"BridgeTalentOrderQuery",
        False,
        False,
    ),
    "talent_probe": OperationSpec(
        "talent_probe",
        "war3_talent_probe_protocol",
        b"talent_probe_abi",
        b"BridgeTalentProbeQuery",
        True,
        False,
    ),
    "stat_details": OperationSpec(
        "stat_details",
        "war3_stat_details_protocol",
        b"stat_details_batch_abi",
        b"BridgeStatDetailsQuery",
        False,
        True,
    ),
    "ability": OperationSpec(
        "ability",
        "war3_ability_protocol",
        b"ability_batch_abi",
        b"BridgeAbilityQuery",
        False,
        False,
    ),
    "ability_field": OperationSpec(
        "ability_field",
        "war3_ability_field_protocol",
        b"ability_field_batch_abi",
        b"BridgeAbilityFieldQuery",
        False,
        True,
    ),
    "item": OperationSpec(
        "item",
        "war3_item_protocol",
        b"item_batch_abi",
        b"BridgeItemQuery",
        False,
        False,
    ),
    "item_catalog": OperationSpec(
        "item_catalog",
        "war3_item_catalog_protocol",
        b"item_catalog_batch_abi",
        b"BridgeItemCatalogQuery",
        False,
        False,
    ),
    "item_field": OperationSpec(
        "item_field",
        "war3_item_field_protocol",
        b"item_field_batch_abi",
        b"BridgeItemFieldQuery",
        False,
        True,
    ),
    "clone": OperationSpec(
        "clone",
        "war3_clone_protocol",
        b"clone_batch_abi",
        b"BridgeCloneQuery",
        False,
        False,
    ),
    "unit_action": OperationSpec(
        "unit_action",
        "war3_unit_action_protocol",
        b"unit_action_batch_abi",
        b"BridgeUnitActionQuery",
        False,
        False,
    ),
    "world": OperationSpec(
        "world",
        "war3_world_protocol",
        b"world_batch_abi",
        b"BridgeWorldQuery",
        False,
        True,
    ),
    "bulk": OperationSpec(
        "bulk",
        "war3_bulk_protocol",
        b"bulk_batch_abi",
        b"BridgeBulkQuery",
        False,
        False,
    ),
    "effect": OperationSpec(
        "effect",
        "war3_effect_protocol",
        b"effect_batch_abi",
        b"BridgeEffectQuery",
        False,
        False,
    ),
    "world_effect": OperationSpec(
        "world_effect",
        "war3_world_effect_protocol",
        b"world_effect_batch_abi",
        b"BridgeWorldEffectQuery",
        False,
        False,
    ),
    "world_cast": OperationSpec(
        "world_cast",
        "war3_world_cast_protocol",
        b"world_cast_abi",
        b"BridgeWorldCastQuery",
        False,
        False,
    ),
    "spawn": OperationSpec(
        "spawn",
        "war3_spawn_protocol",
        b"spawn_batch_abi",
        b"BridgeSpawnQuery",
        False,
        False,
    ),
    "mouse": OperationSpec(
        "mouse",
        "war3_mouse_protocol",
        b"mouse_batch_abi",
        b"BridgeMouseQuery",
        False,
        True,
    ),
    "screen_mouse": OperationSpec(
        "screen_mouse",
        "war3_screen_protocol",
        b"screen_mouse_batch_abi",
        b"BridgeScreenMouseQuery",
        False,
        True,
    ),
    "camera": OperationSpec(
        "camera",
        "war3_camera_protocol",
        b"camera_batch_abi",
        b"BridgeCameraQuery",
        False,
        True,
    ),
    "position": OperationSpec(
        "position",
        "war3_position_protocol",
        b"position_batch_abi",
        b"BridgePositionQuery",
        False,
        True,
    ),
    "position_target": OperationSpec(
        "position_target",
        "war3_position_target_protocol",
        b"position_batch_abi",
        b"BridgePositionQuery",
        False,
        True,
    ),
    "terrain": OperationSpec(
        "terrain",
        "war3_terrain_protocol",
        b"terrain_batch_abi",
        b"BridgeTerrainQuery",
        False,
        True,
    ),
    "equipment": OperationSpec(
        "equipment",
        "war3_equipment_protocol",
        b"equipment_batch_abi",
        b"BridgeEquipmentQuery",
        False,
        True,
    ),
    "equipment_probe": OperationSpec(
        "equipment_probe",
        None,
        b"equipment_probe_abi",
        b"BridgeEquipmentProbeQuery",
        True,
        False,
    ),
    "cooldown_probe": OperationSpec(
        "cooldown_probe",
        None,
        b"cooldown_probe_abi",
        b"BridgeCooldownProbeQuery",
        True,
        False,
    ),
    "extension": OperationSpec(
        "extension",
        "war3_extension_protocol",
        b"extension_batch_abi",
        b"BridgeExtensionQuery",
        False,
        True,
    ),
    "map_bounds": OperationSpec(
        "map_bounds",
        "war3_map_bounds_protocol",
        b"map_bounds_batch_abi",
        b"BridgeMapBoundsQuery",
        False,
        True,
    ),
}


@lru_cache(maxsize=None)
def protocol(kind):
    spec = OPERATIONS.get(kind)
    if spec is None:
        raise ValueError("Unknown current-engine batch kind")
    return spec, import_module(spec.protocol) if spec.protocol else None


def prepare_operation(kind, payload):
    spec, module = protocol(kind)
    if module is not None:
        module.validate_work(payload)
        abi = module.ABI
    else:
        # Diagnostic probes have a separate fixed ABI; no runtime code loading.
        magic, size = {
            "equipment_probe": (0x24268043, 3816),
            "cooldown_probe": (0x24268044, 648),
        }[kind]
        if len(payload) != size:
            raise ValueError("Invalid diagnostic payload size")
        abi = struct.pack("<3I", magic, 216, size)
    return abi, spec.marker, spec.query
