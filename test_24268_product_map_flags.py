from pathlib import Path

import pefile


def test_set_map_flag_route_is_not_packaged_or_dispatchable():
    root = Path(__file__).parent
    bridge_source = (root / "tools" / "war3_bridge_24268.c").read_text(encoding="utf-8")
    transport_source = (root / "war3_engine_transport.py").read_text(encoding="utf-8")
    spec_source = (root / "War3ReforgedTrainer-2.0.3.spec").read_text(encoding="utf-8")
    assert 'war3_bridge_map_flags.h' not in bridge_source
    assert "kind=='map_flags'" not in transport_source
    assert 'war3_map_flags_protocol' not in spec_source

    pe = pefile.PE(str(root / "tools" / "war3_bridge_24268.dll"), fast_load=False)
    exports = {symbol.name for symbol in pe.DIRECTORY_ENTRY_EXPORT.symbols}
    assert b"BridgeMapFlagsQuery" not in exports
    assert b"map_flags_batch_abi" not in exports
