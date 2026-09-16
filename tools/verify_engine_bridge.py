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

    required = (
        b"BridgeInstall",
        b"BridgeUninstall",
        b"BridgeHeroQuery",
        b"BridgeAbilityQuery",
        b"BridgeAbilityFieldQuery",
        b"BridgeItemQuery",
        b"BridgeItemCatalogQuery",
        b"BridgeItemFieldQuery",
        b"BridgeCloneQuery",
        b"BridgeWorldQuery",
        b"BridgeMapFlagsQuery",
        b"BridgeBulkQuery",
        b"BridgeEffectQuery",
        b"BridgeWorldEffectQuery",
        b"BridgeSpawnQuery",
        b"BridgeMouseQuery",
        b"BridgeScreenMouseQuery",
        b"BridgeCameraQuery",
        b"BridgePositionQuery",
        b"BridgeTerrainQuery",
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
    marker(b"ability_batch_abi", (0x24268011, 216, 832))
    marker(b"ability_field_batch_abi", (0x24268021, 216, 7688))
    marker(b"item_batch_abi", (0x24268014, 216, 5968))
    marker(b"item_catalog_batch_abi", (0x2426802B, 216, 0))
    marker(b"item_field_batch_abi", (0x24268022, 216, 5136))
    marker(b"clone_batch_abi", (0x24268015, 216, 1872))
    marker(b"unit_action_batch_abi", (0x24268016, 216, 1432))
    marker(b"world_batch_abi", (0x24268017, 216, 128))
    marker(b"map_flags_batch_abi", (0x2426802C, 216, 128))
    marker(b"bulk_batch_abi", (0x24268023, 216, 624))
    marker(b"effect_batch_abi", (0x24268027, 216, 1168))
    marker(b"world_effect_batch_abi", (0x24268028, 216, 656))
    marker(b"spawn_batch_abi", (0x24268018, 216, 128))
    marker(b"mouse_batch_abi", (0x24268019, 216, 128))
    marker(b"screen_mouse_batch_abi", (0x2426801A, 216, 128))
    marker(b"camera_batch_abi", (0x2426801B, 216, 256))
    marker(b"position_batch_abi", (0x24268020, 216, 1312))
    marker(b"terrain_batch_abi", (0x2426802A, 216, 128))
    for name in (b"BridgeUnitActionQuery",):
        if name not in exports:
            raise AssertionError("missing export: " + name.decode("ascii"))
    if (b"BridgeTestRun" in exports) != fixture:
        raise AssertionError("fixture export state does not match -Fixture")
    print("x64 bridge ABI verified")


if __name__ == "__main__":
    main()
