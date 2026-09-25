"""Verify the exported ABI markers of the current engine bridge."""
import struct
import sys

import pefile


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: verify_engine_bridge.py <dll> <fixture>")
    path = sys.argv[1]
    fixture = sys.argv[2] == "True"
    pe = pefile.PE(path)
    exports = {
        symbol.name: symbol.address
        for symbol in pe.DIRECTORY_ENTRY_EXPORT.symbols
        if symbol.name is not None
    }
    if pe.FILE_HEADER.Machine != 0x8664:
        raise AssertionError("bridge must be x64")
    if not fixture:
        reloc = pe.OPTIONAL_HEADER.DATA_DIRECTORY[5]
        if not reloc.VirtualAddress or not reloc.Size:
            raise AssertionError("production bridge is missing loader relocations")
        if not any(
            entry.type == 10
            for block in getattr(pe, "DIRECTORY_ENTRY_BASERELOC", ())
            for entry in block.entries
        ):
            raise AssertionError("production bridge has no DIR64 relocation")

    required = (
        b"BridgeInstall",
        b"BridgeUninstall",
        b"BridgeDiagnoseLoad",
        b"BridgeHeroQuery",
        b"BridgeHeroAttributesQuery",
        b"BridgeAttackSpeedQuery",
        b"BridgeAbilityQuery",
        b"BridgeAbilityFieldQuery",
        b"BridgeItemQuery",
        b"BridgeItemCatalogQuery",
        b"BridgeItemFieldQuery",
        b"BridgeCloneQuery",
        b"BridgeWorldQuery",
        b"BridgeBulkQuery",
        b"BridgeEffectQuery",
        b"BridgeWorldEffectQuery",
        b"BridgeSpawnQuery",
        b"BridgeMouseQuery",
        b"BridgeScreenMouseQuery",
        b"BridgeCameraQuery",
        b"BridgePositionQuery",
        b"BridgeTerrainQuery",
        b"BridgeMapBoundsQuery",
        b"BridgeEquipmentQuery",
        b"BridgeExtensionQuery",
        b"BridgeStatDetailsQuery",
    )
    missing = [name.decode("ascii") for name in required if name not in exports]
    if missing:
        raise AssertionError("missing exports: " + ", ".join(missing))

    def marker(name: bytes, values: tuple[int, int, int]) -> None:
        address = exports[name]
        actual = pe.get_data(address, 12)
        expected = struct.pack("<3I", *values)
        if actual != expected:
            raise AssertionError(f"{name.decode('ascii')} ABI mismatch: {actual.hex()}")

    marker(b"bridge_abi", (0x2426801C, 216, 632))
    marker(b"hero_attributes_batch_abi", (0x24268030, 216, 1144))
    marker(b"attack_speed_batch_abi", (0x24268032, 216, 640))
    marker(b"ability_batch_abi", (0x24268012, 216, 840))
    marker(b"ability_field_batch_abi", (0x24268021, 216, 7688))
    marker(b"item_batch_abi", (0x2426802D, 216, 6008))
    marker(b"item_catalog_batch_abi", (0x2426802B, 216, 0))
    marker(b"item_field_batch_abi", (0x24268022, 216, 5136))
    marker(b"clone_batch_abi", (0x24268015, 216, 1872))
    marker(b"unit_action_batch_abi", (0x24268016, 216, 1432))
    marker(b"world_batch_abi", (0x24268017, 216, 128))
    marker(b"bulk_batch_abi", (0x2426803A, 216, 656))
    marker(b"effect_batch_abi", (0x24268027, 216, 1168))
    marker(b"world_effect_batch_abi", (0x24268028, 216, 656))
    marker(b"spawn_batch_abi", (0x24268018, 216, 128))
    marker(b"mouse_batch_abi", (0x24268019, 216, 128))
    marker(b"screen_mouse_batch_abi", (0x2426801A, 216, 128))
    marker(b"camera_batch_abi", (0x2426801B, 216, 256))
    marker(b"position_batch_abi", (0x24268020, 216, 1312))
    marker(b"terrain_batch_abi", (0x2426802A, 216, 128))
    marker(b"map_bounds_batch_abi", (0x2426802C, 216, 128))
    marker(b"equipment_batch_abi", (0x2426802E, 216, 872))
    marker(b"extension_batch_abi", (0x2426803A, 216, 1848))
    marker(b"stat_details_batch_abi", (0x2426803E, 216, 1032))
    marker(b"talent_order_abi", (0x24268041, 216, 544))
    if b"equipment_probe_abi" in exports:
        if b"BridgeEquipmentProbeQuery" not in exports:
            raise AssertionError("missing diagnostic equipment probe export")
        marker(b"equipment_probe_abi", (0x24268043, 216, 3816))
    for name in (b"BridgeUnitActionQuery",):
        if name not in exports:
            raise AssertionError("missing export: " + name.decode("ascii"))
    if (b"BridgeTestRun" in exports) != fixture:
        raise AssertionError("fixture export state does not match -Fixture")
    print("x64 bridge ABI verified")


if __name__ == "__main__":
    main()
