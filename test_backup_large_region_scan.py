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


def test_backup_native_table_keeps_existing_fast_path(monkeypatch):
    instance = _bare_trainer()
    expected = trainer.Region(
        0x200000000,
        0x20000,
        trainer.PAGE_READWRITE,
        trainer.MEM_PRIVATE,
    )

    monkeypatch.setattr(
        instance,
        "_find_native_table_regions",
        lambda _pm, _regions: [expected],
    )
    monkeypatch.setattr(
        instance,
        "_scan_native_table_region_candidates_win10",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("fast-path success must not start backup scanning")
        ),
    )
    monkeypatch.setattr(
        instance,
        "_scan_native_table_reference_candidates_win10",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("fast-path success must not start reference scanning")
        ),
    )

    assert instance._find_native_table_regions_win10(object(), [expected]) == [expected]


def test_backup_resource_scan_expands_in_stages(monkeypatch):
    instance = _bare_trainer()
    resource_tag = trainer.struct.pack("<Q", trainer.War3Trainer.RESOURCE_PROP_TAG)
    owner_tag = trainer.struct.pack("<Q", trainer.War3Trainer.UNIT_OWNER_TAG)
    resource_address = 0x210000018
    owner_address = 0x220000018
    limits = []

    class Memory:
        refreshes = 0

        def regions(self, force_refresh=False):
            if force_refresh:
                self.refreshes += 1
            return []

    pm = Memory()

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
        pm,
        warm_unit_owner_index=True,
    )

    assert limits == [1024 * 1024, 64 * 1024 * 1024, None]
    assert pm.refreshes == 1
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


def test_backup_component_fallback_refreshes_regions(monkeypatch):
    instance = _bare_trainer()

    class Memory:
        refreshes = 0

        def regions(self, force_refresh=False):
            if force_refresh:
                self.refreshes += 1
            return []

    pm = Memory()
    monkeypatch.setattr(
        trainer.War3Trainer,
        "_scan_component_index",
        lambda _self, _pm: {},
    )

    assert instance._scan_component_index_win10(pm) == {}
    assert pm.refreshes == 1


def test_backup_scan_skips_region_that_became_unreadable():
    instance = _bare_trainer()

    class Memory:
        @staticmethod
        def _query_region(_address):
            return {
                "base": 0x200000,
                "size": 0x4000,
                "state": 0x10000,
                "protect": trainer.PAGE_NOACCESS,
                "type": 0,
            }

        @staticmethod
        def read(_address, _size):
            raise AssertionError("an address confirmed as free must not be read")

    assert list(
        instance._iter_readable_blocks_win10(
            Memory(),
            0x200000,
            0x4000,
        )
    ) == []


def test_backup_scan_keeps_stable_readable_region_behavior():
    instance = _bare_trainer()
    payload = b"stable backup region"

    class Memory:
        @staticmethod
        def _query_region(address):
            return {
                "base": address,
                "size": len(payload),
                "state": trainer.MEM_COMMIT,
                "protect": trainer.PAGE_READWRITE,
                "type": trainer.MEM_PRIVATE,
            }

        @staticmethod
        def read(_address, size):
            return payload[:size]

    assert list(
        instance._iter_readable_blocks_win10(
            Memory(),
            0x300000,
            len(payload),
        )
    ) == [(0x300000, payload)]


def test_backup_scan_keeps_old_read_behavior_when_live_query_fails():
    instance = _bare_trainer()
    payload = b"query unavailable"

    class Memory:
        @staticmethod
        def _query_region(_address):
            return {}

        @staticmethod
        def read(_address, size):
            return payload[:size]

    assert list(
        instance._iter_readable_blocks_win10(
            Memory(),
            0x400000,
            len(payload),
        )
    ) == [(0x400000, payload)]


def test_backup_native_table_falls_back_to_external_string_reference(monkeypatch):
    instance = _bare_trainer()
    mapped_table = trainer.Region(
        0x500000,
        0x20000,
        trainer.PAGE_READWRITE,
        trainer.MEM_MAPPED,
    )
    executable = trainer.Region(
        0x140000000,
        0x100000,
        trainer.PAGE_EXECUTE_READ,
        trainer.MEM_IMAGE,
    )
    regions = [mapped_table, executable]
    string_address = 0x510000
    record = 0x51F000
    handler = executable.base + 0x1000

    class Memory:
        refreshes = 0

        def regions(self, force_refresh=False):
            if force_refresh:
                self.refreshes += 1
            return regions

        @staticmethod
        def read_u64(address):
            values = {
                record - 8: handler,
                record: string_address,
                record + 8: len("UnitAddAbility"),
                record + 16: 31,
            }
            return values[address]

    pm = Memory()
    monkeypatch.setattr(
        instance,
        "_find_native_table_regions",
        lambda _pm, _regions: (_ for _ in ()).throw(
            RuntimeError("未找到 Warcraft III native 函数表")
        ),
    )
    monkeypatch.setattr(
        instance,
        "_scan_native_table_region_candidates_win10",
        lambda *_args: [],
    )

    def scan(_pm, pattern, **_kwargs):
        if pattern == b"UnitAddAbility":
            return [string_address]
        return []

    monkeypatch.setattr(instance, "_scan_bytes_regions_win10", scan)
    monkeypatch.setattr(
        instance,
        "_scan_bytes_regions_many_win10",
        lambda _pm, patterns, **_kwargs: {
            pattern: [record]
            for pattern in patterns
        },
    )

    found = instance._find_native_table_regions_win10(pm, regions)

    assert found == [mapped_table]
    assert pm.refreshes >= 1


def test_backup_external_native_name_reads_only_requested_bytes():
    instance = _bare_trainer()
    name = "UnitAddAbility"
    pointer = 0x700001000
    mapped_region = trainer.Region(
        0x700000000,
        2 * 1024 * 1024 * 1024,
        trainer.PAGE_READWRITE,
        trainer.MEM_MAPPED,
    )

    class Memory:
        reads = []

        def read(self, address, size):
            self.reads.append((address, size))
            return name.encode("ascii")

    pm = Memory()
    recovered = instance._recover_native_external_names_win10(
        pm,
        [mapped_region],
        {(pointer, len(name))},
        {name},
    )

    assert recovered == {pointer: name}
    assert pm.reads == [(pointer, len(name))]


def test_exact_native_fallback_resolves_external_name_references():
    instance = _bare_trainer()
    names = (
        "BlzGetItemBooleanField",
        "BlzGetItemIntegerField",
        "BlzGetItemRealField",
        "BlzSetItemBooleanField",
        "BlzSetItemIntegerField",
        "BlzSetItemRealField",
    )
    string_region = trainer.Region(
        0x600000,
        0x20000,
        trainer.PAGE_READWRITE,
        trainer.MEM_PRIVATE,
    )
    table_region = trainer.Region(
        0x900000,
        0x20000,
        trainer.PAGE_READWRITE,
        trainer.MEM_MAPPED,
    )
    executable = trainer.Region(
        0x140000000,
        0x100000,
        trainer.PAGE_EXECUTE_READ,
        trainer.MEM_IMAGE,
    )
    regions = [string_region, table_region, executable]
    string_addresses = {
        name: string_region.base + 0x100 + index * 0x100
        for index, name in enumerate(names)
    }
    records = {
        name: table_region.base + 0x100 + index * 0x88
        for index, name in enumerate(names)
    }

    class Memory:
        @staticmethod
        def scan_bytes_many(patterns, **_kwargs):
            result = {pattern: [] for pattern in patterns}
            for pattern in result:
                if len(pattern) == 8:
                    pointer = trainer.struct.unpack("<Q", pattern)[0]
                    for name, address in string_addresses.items():
                        if pointer == address:
                            result[pattern] = [records[name]]
                else:
                    for name, address in string_addresses.items():
                        if pattern == name.encode("ascii") + b"\0":
                            result[pattern] = [address]
            return result

        @staticmethod
        def read_u64(address):
            for index, name in enumerate(names):
                record = records[name]
                values = {
                    record - 8: executable.base + 0x1000 + index * 0x20,
                    record: string_addresses[name],
                    record + 8: len(name),
                    record + 16: len(name),
                }
                if address in values:
                    return values[address]
            raise OSError(address)

    found = instance._find_native_handlers_by_exact_name_scan(
        Memory(),
        regions,
        names,
    )

    assert set(found) == set(names)
    assert {
        name: handler.record_address
        for name, handler in found.items()
    } == records
