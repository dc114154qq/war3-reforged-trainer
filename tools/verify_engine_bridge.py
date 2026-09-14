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
        b"BridgeItemQuery",
        b"BridgeCloneQuery",
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

    marker(b"bridge_abi", (0x24268010, 216, 608))
    marker(b"ability_batch_abi", (0x24268011, 216, 832))
    marker(b"item_batch_abi", (0x24268014, 216, 5960))
    marker(b"clone_batch_abi", (0x24268015, 216, 1848))
    if (b"BridgeTestRun" in exports) != fixture:
        raise AssertionError("fixture export state does not match -Fixture")
    print("x64 bridge ABI verified")


if __name__ == "__main__":
    main()
