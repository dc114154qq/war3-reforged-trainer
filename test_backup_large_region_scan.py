from types import SimpleNamespace

import war3_reforged_trainer as trainer


def _bare_trainer():
    instance = object.__new__(trainer.War3Trainer)
    instance._native_table_regions = []
    instance._native_table_region = None
    instance._native_table_blob = None
    instance._unit_owner_index = {}
    return instance


def test_backup_native_table_expands_beyond_64mb(monkeypatch):
    instance = _bare_trainer()
    large_region = trainer.Region(
        0x200000000,
        96 * 1024 * 1024,
        trainer.PAGE_READWRITE,
        trainer.MEM_PRIVATE,
    )
    limits = []

    monkeypatch.setattr(
        instance,
        "_find_native_table_regions",
        lambda _pm, _regions: (_ for _ in ()).throw(
            RuntimeError("未找到 Warcraft III native 函数表")
        ),
    )

    def scan(_pm, _regions, max_region_size):
        limits.append(max_region_size)
        return [large_region] if max_region_size is None else []

    monkeypatch.setattr(
        instance,
        "_scan_native_table_region_candidates_win10",
        scan,
    )

    found = instance._find_native_table_regions_win10(object(), [large_region])

    assert found == [large_region]
    assert limits == [64 * 1024 * 1024, None]
    assert instance._native_table_regions == [
        (large_region.base, large_region.size)
    ]
    assert instance._native_table_blob is None


def test_backup_resource_scan_expands_in_stages(monkeypatch):
    instance = _bare_trainer()
    resource_tag = trainer.struct.pack("<Q", trainer.War3Trainer.RESOURCE_PROP_TAG)
    owner_tag = trainer.struct.pack("<Q", trainer.War3Trainer.UNIT_OWNER_TAG)
    resource_address = 0x210000018
    owner_address = 0x220000018
    limits = []

    def scan(_pm, patterns, max_region_size):
        limits.append(max_region_size)
        result = {pattern: [] for pattern in patterns}
        if max_region_size is None:
            result[resource_tag] = [resource_address]
            result[owner_tag] = [owner_address]
        return result

    monkeypatch.setattr(instance, "_scan_bytes_private_many_win10", scan)
    monkeypatch.setattr(
        instance,
        "_unit_owner_index_from_tag_addresses",
        lambda _pm, addresses: {0x30: addresses[0]},
    )
    monkeypatch.setattr(
        instance,
        "_iter_resource_properties",
        lambda _pm, addresses: (
            trainer.ResourceProperty(3, addresses[0] - 0x28, 5000, 0x30),
        ),
    )

    groups = instance._resource_property_groups_win10(
        object(),
        warm_unit_owner_index=True,
    )

    assert limits == [1024 * 1024, 64 * 1024 * 1024, None]
    assert groups[0x30][3].value == 5000
    assert instance._unit_owner_index == {0x30: owner_address}


def test_backup_component_scan_keeps_existing_fast_path(monkeypatch):
    instance = _bare_trainer()
    expected = {0x1000: {"hero": (0x2000, 0x3000)}}

    monkeypatch.setattr(
        trainer.War3Trainer,
        "_scan_component_index",
        lambda _self, _pm: expected,
    )
    monkeypatch.setattr(
        instance,
        "_iter_readable_blocks_win10",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("fast-path success must not start a full-region scan")
        ),
    )

    result = instance._scan_component_index_win10(
        SimpleNamespace(regions=lambda: [])
    )

    assert result == expected
