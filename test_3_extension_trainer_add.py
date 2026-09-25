from pathlib import Path
from unittest.mock import Mock

from war3_reforged_trainer import War3Trainer


def test_add_extension_item_uses_dedicated_bag_action():
    trainer = object.__new__(War3Trainer)
    engine = Mock()
    trainer._engine_instance_24268 = Mock(return_value=engine)
    trainer._coerce_memory_value = lambda _kind, value: int.from_bytes(value.encode("ascii"), "big")
    empty = tuple(dict(slot=index, handle=0, rawcode=0, charges=0, equipment_type=0)
                  for index in range(30))
    before = {"target_unit": 0x101400, "bag_size": 30, "bag": empty,
              "equipment": (), "abilities": {}}
    added = list(empty)
    added[0] = dict(slot=0, handle=0x101500, rawcode=int.from_bytes(b"eeh3", "big"),
                    charges=0, equipment_type=1)
    after = {**before, "bag": tuple(added)}
    trainer.extension_snapshot_24268 = Mock(side_effect=[before, after])

    trainer.add_extension_item_24268("eeh3")

    engine.extension.assert_called_once_with(
        action=1,
        target_unit=0x101400,
        item_rawcode=int.from_bytes(b"eeh3", "big"),
    )


def test_extension_tab_exposes_six_official_backpacks_without_generic_template():
    import war3_reforged_trainer as product

    source = Path(product.__file__).read_text(encoding="utf-8")
    assert 'text="添加官方背包装备"' in source
    assert "command=lambda: call_async(extension_add_backpack_equipment)" in source
    catalog = Path(product.__file__).with_name("war3_3_extension_catalog.py").read_text(
        encoding="utf-8"
    )
    for rawcode in ("ebhg", "ebhl", "ebhi", "ebug", "ebua", "ebul"):
        assert rawcode in catalog
    assert "通用天赋模板" not in source
