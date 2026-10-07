"""selection compatibility API; host primitives are explicitly bound once at composition."""
from __future__ import annotations
from contextlib import contextmanager

class SelectionFacade:
    @staticmethod
    def _looks_like_unit_handle(value: int) -> bool:
        low = value & 0xFFFFFFFF
        high = (value >> 32) & 0xFFFFFFFF
        return (
            0x100 <= low <= 0x0FFFFFFF
            and 0x100 <= high <= 0x0FFFFFFF
            and abs(high - low) <= 0x01000000
        )


    @staticmethod
    def _looks_like_vtable(value: int) -> bool:
        return 0x700000000000 <= value <= 0x7FFFFFFFFFFF


    def _iter_owner_property_list(self, pm: ProcessMemory, owner: int) -> Iterable[int]:
        for list_offset, size_offset in ((0xA0, 0xA8), (0xB0, 0xB8)):
            try:
                list_address = pm.read_u64(owner + list_offset)
                size_bytes = pm.read_u64(owner + size_offset)
            except OSError:
                continue
            # These pointers come from a known owner, not a heap scan. Windows
            # may place valid 64-bit allocations below 4 GiB on another PC.
            if not (0x10000 <= list_address < 0x800000000000 and list_address % 8 == 0):
                continue
            if not 0 < size_bytes <= 0x400:
                size_bytes = 0x100
            for entry_offset in range(0, int(size_bytes), 8):
                try:
                    prop = pm.read_u64(list_address + entry_offset)
                except OSError:
                    continue
                if 0x10000 <= prop < 0x800000000000 and prop % 8 == 0:
                    yield prop


    def _property_from_owner(self, pm: ProcessMemory, owner: int, kind: int) -> int | None:
        return self._owner_properties(pm, owner).get(int(kind))


    def _position_property_from_owner(self, pm: ProcessMemory, owner: int) -> int | None:
        return self._owner_properties(pm, owner).get(-1)


    def _owner_properties(self, pm: ProcessMemory, owner: int) -> dict[int, int]:
        owner = int(owner)
        # Property membership can change without changing the owner address.
        # Read its bounded pointer lists; never reuse another read's mapping.
        properties: dict[int, int] = {}
        seen: set[int] = set()
        for prop in self._iter_owner_property_list(pm, owner):
            if prop in seen:
                continue
            seen.add(prop)
            try:
                tag = pm.read_u64(prop + 0x18)
                if pm.read_u64(prop + 0x50) != owner:
                    continue
                if tag == self.PROP_TAG:
                    prop_kind = (pm.read_u64(prop + 0x78) >> 32) & 0xFFFFFFFF
                    properties.setdefault(int(prop_kind), prop)
                elif tag == self.POSITION_PROP_TAG:
                    properties.setdefault(-1, prop)
            except OSError:
                continue
        return properties


    def _unit_object_from_owner(self, pm: ProcessMemory, owner: int, handle: int) -> int:
        from war3_game_profile import current_profile
        layout = current_profile().section("registry")
        try:
            unit = pm.read_u64(owner + layout["owner_data"])
        except OSError:
            return 0
        if not (0x10000 <= unit < 0x800000000000 and unit % 8 == 0):
            return 0
        try:
            if handle and pm.read_u64(unit + layout["object_handle"]) != handle:
                return 0
        except OSError:
            return 0
        return unit


    @staticmethod
    def _valid_current_limit(current: float, limit: float) -> bool:
        return (
            math.isfinite(current)
            and math.isfinite(limit)
            and limit >= 0.0
        )


    def _candidate_from_owner(
        self,
        pm: ProcessMemory,
        owner: int,
        score: int,
        note: str,
        handle: int = 0,
        selection_source: str = "",
        selection_slot_address: int = 0,
    ) -> UnitCandidate | None:
        hp_prop = self._property_from_owner(pm, owner, 1)
        if hp_prop is None:
            self._last_selection_candidate_failure = {"stage": "hp_missing", "owner": owner}
            return None
        hp_current_address = hp_prop + self.SELECTED_HP_VALUE_OFFSET
        hp_regen_address = hp_current_address + 0x04
        hp_max_address = hp_current_address + 0x10
        try:
            hp_current = pm.read_f32(hp_current_address)
            hp_limit = pm.read_f32(hp_max_address)
        except OSError as exc:
            self._last_selection_candidate_failure = {
                "stage": "hp_unreadable", "owner": owner, "property": hp_prop,
                "winerror": getattr(exc, "winerror", None),
            }
            return None
        if not self._valid_current_limit(hp_current, hp_limit):
            self._last_selection_candidate_failure = {
                "stage": "hp_invalid", "owner": owner, "property": hp_prop,
                "current": hp_current, "maximum": hp_limit,
            }
            return None

        mp_current_address = 0
        mp_regen_address = 0
        mp_max_address = 0
        mp_prop = self._property_from_owner(pm, owner, 2)
        if mp_prop is not None:
            candidate_current = mp_prop + self.SELECTED_HP_VALUE_OFFSET
            candidate_max = candidate_current + 0x10
            try:
                mp_current = pm.read_f32(candidate_current)
                mp_limit = pm.read_f32(candidate_max)
            except OSError:
                mp_current = math.nan
                mp_limit = math.nan
            if self._valid_current_limit(mp_current, mp_limit):
                mp_current_address = candidate_current
                mp_regen_address = candidate_current + 0x04
                mp_max_address = candidate_max

        suffix = f" owner=0x{owner:x} hp_kind=1"
        if mp_current_address:
            suffix += " mp_kind=2"
        else:
            suffix += " mp_kind=missing"
        position_property = self._position_property_from_owner(pm, owner) or 0
        x_address = position_property + 0xD0 if position_property else 0
        y_address = position_property + 0xD4 if position_property else 0
        if position_property:
            suffix += " pos=prop^ucp"
        unit_address = self._unit_object_from_owner(pm, owner, handle)
        unit_type_id = 0
        if unit_address:
            suffix += f" unit=0x{unit_address:x}"
            try:
                unit_type_id = pm.read_u32(unit_address + 0x70)
            except (OSError, AttributeError):
                unit_type_id = 0
        return UnitCandidate(
            base=hp_prop,
            score=score,
            hp_current_address=hp_current_address,
            hp_max_address=hp_max_address,
            mp_current_address=mp_current_address,
            mp_max_address=mp_max_address,
            note=note + suffix,
            hp_regen_address=hp_regen_address,
            mp_regen_address=mp_regen_address,
            owner_address=owner,
            handle=handle,
            unit_address=unit_address,
            unit_type_id=unit_type_id,
            x_address=x_address,
            y_address=y_address,
            position_property_address=position_property,
            selection_source=selection_source,
            selection_slot_address=selection_slot_address,
        )


    def _unit_owner_index_from_tag_addresses(
        self,
        pm: ProcessMemory,
        tag_addresses: Iterable[int],
    ) -> dict[int, int]:
        index: dict[int, int] = {}
        for tag_address in tag_addresses:
            owner = tag_address - 0x18
            try:
                vtable = pm.read_u64(owner)
                handle = pm.read_u64(owner + 0x20)
                list_address = pm.read_u64(owner + 0xA0)
            except OSError:
                continue
            if not self._looks_like_vtable(vtable):
                continue
            if not self._looks_like_unit_handle(handle):
                continue
            if not self._sane_heap_ptr(list_address):
                continue
            if self._property_from_owner(pm, owner, 1) is None:
                continue
            index[handle] = owner
        return index


    def _build_unit_owner_index(self, pm: ProcessMemory) -> dict[int, int]:
        with self._unit_owner_index_lock:
            if self._unit_owner_index:
                return self._unit_owner_index
            tag = struct.pack("<Q", self.UNIT_OWNER_TAG)
            tag_addresses = pm.scan_bytes_private_parallel(
                tag,
                max_region_size=1024 * 1024,
            )
            index = self._unit_owner_index_from_tag_addresses(pm, tag_addresses)
            self._unit_owner_index = index
            self._unit_object_index_cache = None
            return index


    def _owner_for_handle(self, pm: ProcessMemory, handle: int) -> int | None:
        index = self._unit_owner_index
        owner = index.get(handle)
        if owner is not None:
            try:
                if pm.read_u64(owner + 0x20) == handle and self._property_from_owner(pm, owner, 1):
                    return owner
            except OSError:
                pass
        index = self._build_unit_owner_index(pm)
        return index.get(handle)


    def _owner_for_unit_pointer(self, pm: ProcessMemory, unit: int, handle: int) -> int | None:
        if not self._sane_heap_ptr(unit) or not self._looks_like_unit_handle(handle):
            return None

        indexed = self._unit_owner_index.get(handle)
        if indexed is not None:
            try:
                if pm.read_u64(indexed + 0x20) == handle and pm.read_u64(indexed + 0x90) == unit:
                    return indexed
            except OSError:
                pass

        pattern = struct.pack("<Q", unit)
        start_address = unit - self.UNIT_OWNER_POINTER_SEARCH_RADIUS
        end_address = unit + self.UNIT_OWNER_POINTER_SEARCH_RADIUS
        for region in pm.regions():
            if region.typ != MEM_PRIVATE or region.size > 1024 * 1024:
                continue
            if region.base + region.size < start_address or region.base > end_address:
                continue
            try:
                data = pm.read(region.base, region.size)
            except OSError:
                continue
            start = 0
            while True:
                hit = data.find(pattern, start)
                if hit < 0:
                    break
                owner = region.base + hit - 0x90
                try:
                    if (
                        self._looks_like_vtable(pm.read_u64(owner))
                        and pm.read_u64(owner + 0x18) == self.UNIT_OWNER_TAG
                        and pm.read_u64(owner + 0x20) == handle
                        and pm.read_u64(owner + 0x90) == unit
                        and self._property_from_owner(pm, owner, 1) is not None
                    ):
                        self._unit_owner_index[handle] = owner
                        return owner
                except OSError:
                    pass
                start = hit + 1
        return None


    def _owner_for_unit_pointer_win10(
        self,
        pm: ProcessMemory,
        unit: int,
        handle: int,
    ) -> int | None:
        owner = self._owner_for_unit_pointer(pm, unit, handle)
        if owner is not None:
            return owner

        pattern = struct.pack("<Q", unit)
        start_address = unit - self.UNIT_OWNER_POINTER_SEARCH_RADIUS
        end_address = unit + self.UNIT_OWNER_POINTER_SEARCH_RADIUS
        for region in pm.regions():
            if region.typ != MEM_PRIVATE or region.size > 64 * 1024 * 1024:
                continue
            if region.base + region.size < start_address or region.base > end_address:
                continue
            for block_address, data in self._iter_readable_blocks_win10(
                pm,
                region.base,
                region.size,
            ):
                start = 0
                while True:
                    hit = data.find(pattern, start)
                    if hit < 0:
                        break
                    candidate_owner = block_address + hit - 0x90
                    try:
                        if (
                            self._looks_like_vtable(pm.read_u64(candidate_owner))
                            and pm.read_u64(candidate_owner + 0x18) == self.UNIT_OWNER_TAG
                            and pm.read_u64(candidate_owner + 0x20) == handle
                            and pm.read_u64(candidate_owner + 0x90) == unit
                            and self._property_from_owner(pm, candidate_owner, 1) is not None
                        ):
                            self._unit_owner_index[handle] = candidate_owner
                            return candidate_owner
                    except OSError:
                        pass
                    start = hit + 1

        tag_addresses = self._scan_bytes_private_win10(
            pm,
            struct.pack("<Q", self.UNIT_OWNER_TAG),
        )
        broad_index = self._unit_owner_index_from_tag_addresses(pm, tag_addresses)
        self._unit_owner_index.update(broad_index)
        owner = broad_index.get(handle)
        if owner is None:
            return None
        try:
            if pm.read_u64(owner + 0x90) != unit:
                return None
        except OSError:
            return None
        return owner


    def _build_unit_object_index(self, pm: ProcessMemory, force_refresh: bool = False) -> dict[int, tuple[int, int]]:
        with self._unit_owner_index_lock:
            if self._unit_object_index_cache is not None and not force_refresh:
                return self._unit_object_index_cache
            unit_index: dict[int, tuple[int, int]] = {}
            owners = (
                self._build_unit_owner_index(pm)
                if force_refresh or not self._unit_owner_index
                else self._unit_owner_index
            )
            for handle, owner in owners.items():
                unit = self._unit_object_from_owner(pm, owner, handle)
                if unit:
                    unit_index[unit] = (handle, owner)
            if not unit_index and self._unit_owner_index and not force_refresh:
                return self._build_unit_object_index(pm, force_refresh=True)
            self._unit_object_index_cache = unit_index
            return unit_index


    def _score_selected_handle_address(self, pm: ProcessMemory, address: int, handle: int, owner: int) -> int:
        if owner <= address < owner + 0x200:
            return -1000
        score = 0
        if 0x8000000000 <= address <= 0xFFFFFFFFFF:
            score += 120
        try:
            if pm.read_u64(address + 0x5F) == handle:
                score += 35
            if pm.read_u64(address + 0x6D) == handle:
                score += 35
        except OSError:
            pass
        if address % 4 == 0:
            score += 5
        return score


    def _remember_selected_handle_addresses(self, pm: ProcessMemory, handle: int, owner: int) -> None:
        pattern = struct.pack("<Q", handle)
        scored: list[tuple[int, int]] = []

        def collect_from_regions(regions: list[Region]) -> None:
            for region in regions:
                try:
                    data = pm.read(region.base, region.size)
                except OSError:
                    continue
                start = 0
                while True:
                    offset = data.find(pattern, start)
                    if offset < 0:
                        break
                    address = region.base + offset
                    score = self._score_selected_handle_address(pm, address, handle, owner)
                    if score > 0:
                        scored.append((score, address))
                    start = offset + 1

        collect_from_regions(self._selection_state_regions(pm, preferred_only=True))
        if not scored:
            collect_from_regions(self._selection_state_regions(pm, preferred_only=False))
        scored.sort(reverse=True)
        for score, address in scored[:8]:
            if score <= 0:
                continue
            if address in self._selected_handle_addresses:
                self._selected_handle_addresses.remove(address)
            self._selected_handle_addresses.insert(0, address)


    def _selection_state_regions(self, pm: ProcessMemory, preferred_only: bool = True) -> list[Region]:
        regions: list[Region] = []
        for region in pm.regions():
            if region.typ != MEM_PRIVATE or region.size > 4 * 1024 * 1024:
                continue
            if not (0x8000000000 <= region.base <= 0xFFFFFFFFFF):
                continue
            if preferred_only and (region.base & 0xFFFFF) != self.SELECTION_STATE_REGION_LOW20:
                continue
            regions.append(region)
        return regions


    def _known_selected_handle_address_candidates(self, pm: ProcessMemory) -> list[int]:
        candidates: list[int] = []
        seen: set[int] = set()

        def add(address: int) -> None:
            if address not in seen:
                seen.add(address)
                candidates.append(address)

        for address in self.KNOWN_SELECTED_HANDLE_ADDRESSES:
            add(address)

        for region in self._selection_state_regions(pm, preferred_only=True):
            for offset in self.KNOWN_SELECTED_REGION_OFFSETS:
                if 0 <= offset <= region.size - 8:
                    add(region.base + offset)
        return candidates


    def _known_selected_unit_pointer_address_candidates(self, pm: ProcessMemory) -> list[int]:
        candidates: list[int] = []
        seen: set[int] = set()

        def add(address: int) -> None:
            if address not in seen:
                seen.add(address)
                candidates.append(address)

        for address in self.KNOWN_SELECTED_UNIT_POINTER_ADDRESSES:
            add(address)

        for region in self._selection_state_regions(pm, preferred_only=True):
            for offset in self.KNOWN_SELECTED_UNIT_POINTER_REGION_OFFSETS:
                if 0 <= offset <= region.size - 8:
                    add(region.base + offset)
        return candidates


    def _discover_selected_handle_addresses(self, pm: ProcessMemory) -> list[int]:
        owners = self._unit_owner_index or self._build_unit_owner_index(pm)
        if not owners:
            return []

        def scan_regions(regions: list[Region]) -> list[tuple[int, int]]:
            scored: list[tuple[int, int]] = []
            for region in regions:
                try:
                    data = pm.read(region.base, region.size)
                except OSError:
                    continue
                for offset in range(0, max(0, len(data) - 7), 4):
                    handle = struct.unpack_from("<Q", data, offset)[0]
                    owner = owners.get(handle)
                    if owner is None:
                        continue
                    address = region.base + offset
                    score = self._score_selected_handle_address(pm, address, handle, owner)
                    if score > 0:
                        scored.append((score, address))
            return scored

        scored = scan_regions(self._selection_state_regions(pm, preferred_only=True))
        if not scored:
            scored = scan_regions(self._selection_state_regions(pm, preferred_only=False))
        scored.sort(reverse=True)
        addresses: list[int] = []
        for _score, address in scored[:8]:
            if address not in addresses:
                addresses.append(address)
        return addresses


    def _locate_selected_unit_by_unit_pointer(self, pm: ProcessMemory) -> UnitCandidate | None:
        unit_index = self._build_unit_object_index(pm, force_refresh=True)
        if not unit_index:
            return None

        def scan_regions(regions: list[Region]) -> dict[int, list[int]]:
            matches: dict[int, list[int]] = {}
            for region in regions:
                try:
                    data = pm.read(region.base, region.size)
                except OSError:
                    continue
                for offset in range(0, max(0, len(data) - 7), 8):
                    unit = struct.unpack_from("<Q", data, offset)[0]
                    if unit in unit_index:
                        matches.setdefault(unit, []).append(region.base + offset)
            return matches

        matches = scan_regions(self._selection_state_regions(pm, preferred_only=True))
        if not matches:
            matches = scan_regions(self._selection_state_regions(pm, preferred_only=False))
        if not matches:
            return None

        ranked = sorted(
            matches.items(),
            key=lambda item: (len(item[1]), -min(item[1])),
            reverse=True,
        )
        best_unit, best_addresses = ranked[0]
        best_count = len(best_addresses)
        if len(ranked) > 1 and len(ranked[1][1]) == best_count:
            return None
        if best_count < 2 and len(ranked) > 1:
            return None

        handle, owner = unit_index[best_unit]
        slot_address = min(best_addresses)
        candidate = self._candidate_from_owner(
            pm,
            owner,
            880 + min(best_count, 20) * 5,
            f"selected_unit_ptr=0x{best_unit:x} refs={best_count} slot=0x{slot_address:x}",
            handle,
            "memory",
            slot_address,
        )
        if candidate is None or candidate.unit_address != best_unit:
            return None
        return candidate


    def _selection_unit_pointer_groups(
        self,
        pm: ProcessMemory,
    ) -> list[tuple[tuple[int, int], list[int], int]]:
        unit_index = self._build_unit_object_index(pm, force_refresh=True)
        if not unit_index:
            return []
        regions = pm.regions()
        known_offsets = set(self.KNOWN_SELECTED_UNIT_POINTER_REGION_OFFSETS)
        groups: dict[tuple[int, int], list[int]] = {}

        def add_pointer(address: int, unit: int) -> None:
            if unit not in unit_index:
                return
            region = self._region_for_address(regions, address)
            region_base = region.base if region is not None else address & ~0xFFFFF
            groups.setdefault((region_base, unit), []).append(address)

        for address in self._known_selected_unit_pointer_address_candidates(pm):
            try:
                add_pointer(address, pm.read_u64(address))
            except OSError:
                continue

        for region in self._selection_state_regions(pm, preferred_only=True):
            try:
                data = pm.read(region.base, region.size)
            except OSError:
                continue
            for offset in range(0, max(0, len(data) - 7), 8):
                unit = struct.unpack_from("<Q", data, offset)[0]
                if unit in unit_index:
                    add_pointer(region.base + offset, unit)

        if not groups:
            return []

        ranked: list[tuple[tuple[int, int], list[int], int]] = []
        for key, addresses in groups.items():
            region_base, _unit = key
            unique_addresses = sorted(set(addresses))
            known_hits = sum(1 for address in unique_addresses if (address - region_base) in known_offsets)
            ranked.append((key, unique_addresses, known_hits))
        ranked.sort(
            key=lambda item: (item[2], len(item[1]), -item[0][0], -min(item[1])),
            reverse=True,
        )
        return ranked


    def _locate_selected_unit_by_known_unit_pointer(self, pm: ProcessMemory) -> UnitCandidate | None:
        unit_index = self._build_unit_object_index(pm, force_refresh=True)
        if not unit_index:
            return None

        ranked = self._selection_unit_pointer_groups(pm)
        if not ranked:
            return None
        (region_base, unit), unique_addresses, known_hits = ranked[0]
        if known_hits < 2:
            return None
        if len(ranked) > 1 and ranked[1][2] == known_hits and len(ranked[1][1]) == len(unique_addresses) and ranked[1][0][1] != unit:
            return None

        handle, owner = unit_index[unit]
        slot_address = min(unique_addresses)
        candidate = self._candidate_from_owner(
            pm,
            owner,
            870 + known_hits * 20 + min(len(unique_addresses), 20) * 5,
            (
                f"selected_unit_slot=0x{unit:x} region=0x{region_base:x} "
                f"refs={len(unique_addresses)} known={known_hits} slot=0x{slot_address:x}"
            ),
            handle,
            "memory",
            slot_address,
        )
        if candidate is not None and candidate.unit_address == unit:
            return candidate
        return None


    def _selection_unit_pointer_groups_win10(
        self,
        pm: Win10ProcessMemory,
        diagnostics: Win10ReadLogger,
    ) -> tuple[
        list[tuple[tuple[int, int], list[int], int]],
        dict[int, tuple[int, int]],
    ]:
        unit_index = self._build_unit_object_index(pm, force_refresh=False)
        if not unit_index:
            diagnostics.log("selection_unit_pointer_groups_win10", unit_index=0)
            return [], {}
        regions = pm.regions()
        known_offsets = set(self.KNOWN_SELECTED_UNIT_POINTER_REGION_OFFSETS)
        groups: dict[tuple[int, int], list[int]] = {}
        known_total = 0
        known_skipped = 0
        known_read_errors = 0

        def add_pointer(address: int, unit: int) -> None:
            if unit not in unit_index:
                return
            region = self._region_for_address(regions, address)
            region_base = region.base if region is not None else address & ~0xFFFFF
            groups.setdefault((region_base, unit), []).append(address)

        for address in self._known_selected_unit_pointer_address_candidates(pm):
            known_total += 1
            if not pm.is_readable_range(address, 8):
                known_skipped += 1
                continue
            try:
                add_pointer(address, pm.read_u64(address))
            except OSError:
                known_read_errors += 1

        selection_regions = self._selection_state_regions(pm, preferred_only=True)
        for region in selection_regions:
            try:
                data = pm.read(region.base, region.size)
            except OSError:
                continue
            for offset in range(0, max(0, len(data) - 7), 8):
                unit = struct.unpack_from("<Q", data, offset)[0]
                if unit in unit_index:
                    add_pointer(region.base + offset, unit)

        ranked: list[tuple[tuple[int, int], list[int], int]] = []
        for key, addresses in groups.items():
            region_base, _unit = key
            unique_addresses = sorted(set(addresses))
            known_hits = sum(1 for address in unique_addresses if (address - region_base) in known_offsets)
            ranked.append((key, unique_addresses, known_hits))
        ranked.sort(
            key=lambda item: (item[2], len(item[1]), -item[0][0], -min(item[1])),
            reverse=True,
        )
        diagnostics.log(
            "selection_unit_pointer_groups_win10",
            unit_index=len(unit_index),
            known_total=known_total,
            known_skipped=known_skipped,
            known_read_errors=known_read_errors,
            selection_regions=len(selection_regions),
            groups=len(ranked),
        )
        return ranked, unit_index


    def _locate_selected_unit_by_known_unit_pointer_win10(
        self,
        pm: Win10ProcessMemory,
        diagnostics: Win10ReadLogger,
    ) -> UnitCandidate | None:
        ranked, unit_index = self._selection_unit_pointer_groups_win10(pm, diagnostics)
        if not ranked:
            return None
        (region_base, unit), unique_addresses, known_hits = ranked[0]
        if known_hits < 2:
            return None
        if (
            len(ranked) > 1
            and ranked[1][2] == known_hits
            and len(ranked[1][1]) == len(unique_addresses)
            and ranked[1][0][1] != unit
        ):
            return None
        handle, owner = unit_index[unit]
        slot_address = min(unique_addresses)
        candidate = self._candidate_from_owner(
            pm,
            owner,
            870 + known_hits * 20 + min(len(unique_addresses), 20) * 5,
            (
                f"selected_unit_slot=0x{unit:x} region=0x{region_base:x} "
                f"refs={len(unique_addresses)} known={known_hits} slot=0x{slot_address:x}"
            ),
            handle,
            "win10",
            slot_address,
        )
        if candidate is not None and candidate.unit_address == unit:
            return candidate
        return None


    def _selection_manager_unit_slots(
        self,
        pm: ProcessMemory,
        list_base: int,
    ) -> list[tuple[int, int]]:
        try:
            root = pm.read_u64(list_base + 0x18)
            count = pm.read_u32(list_base + 0x20)
        except OSError:
            return []
        if not 0 < count <= self.SELECTION_MANAGER_MAX_UNITS:
            return []
        if (root & 1) or not self._sane_heap_ptr(root):
            return []

        out: list[tuple[int, int]] = []
        node = root
        seen: set[int] = set()
        for _index in range(int(count)):
            if (node & 1) or not self._sane_heap_ptr(node) or node in seen:
                break
            seen.add(node)
            try:
                next_node = pm.read_u64(node + 0x08)
                unit = pm.read_u64(node + 0x10)
            except OSError:
                break
            if self._sane_heap_ptr(unit):
                out.append((unit, node + 0x10))
            node = next_node
        return out


    def _remember_selection_player_from_resource_owner(
        self,
        pm: ProcessMemory,
        resource_owner: int,
        resource_caches: Iterable[ResourceCache],
    ) -> None:
        if not self._sane_heap_ptr(resource_owner):
            return
        players_by_owner: dict[int, int] = {}
        for cache in resource_caches:
            owner = cache.owner_key
            if not self._sane_heap_ptr(owner) or owner in players_by_owner:
                continue
            try:
                player = pm.read_u64(owner + 0x90)
                vtable = pm.read_u64(player)
                selection_manager = pm.read_u64(player + self._selection_manager_offset)
            except OSError:
                continue
            if not self._looks_like_vtable(vtable) or not self._sane_heap_ptr(selection_manager):
                continue
            players_by_owner[owner] = player
        player = players_by_owner.get(resource_owner, 0)
        if not player or len(players_by_owner) < 2:
            return
        if len(set(players_by_owner.values())) != len(players_by_owner):
            return
        if player in self._selection_player_candidates:
            self._selection_player_candidates.remove(player)
        self._selection_player_candidates.insert(0, player)


    def _selection_player_pointer_candidates(self, pm: ProcessMemory, discover: bool = True) -> list[int]:
        candidates: list[int] = []
        seen: set[int] = set()

        def add(value: int) -> None:
            if value in seen or not self._sane_heap_ptr(value):
                return
            seen.add(value)
            candidates.append(value)

        for value in self._selection_player_candidates:
            add(value)
        if not discover:
            return candidates

        discovered_from_player_components = False
        tag = struct.pack("<Q", self.PLAYER_COMPONENT_TAG)
        for tag_address in pm.scan_bytes_private(tag, max_region_size=1024 * 1024):
            owner = tag_address - 0x18
            for offset in (0x90, 0x88):
                try:
                    value = pm.read_u64(owner + offset)
                    vtable = pm.read_u64(value)
                    selection_manager = pm.read_u64(value + self._selection_manager_offset)
                except OSError:
                    continue
                if not self._looks_like_vtable(vtable):
                    continue
                if not self._sane_heap_ptr(selection_manager):
                    continue
                discovered_from_player_components = True
                add(value)
        if discovered_from_player_components:
            return candidates

        try:
            resource_owner_groups = self._resource_property_groups(pm)
        except OSError:
            resource_owner_groups = {}
        for owner in resource_owner_groups:
            if not self._sane_heap_ptr(owner):
                continue
            for offset in range(0, 0x220, 8):
                try:
                    value = pm.read_u64(owner + offset)
                    vtable = pm.read_u64(value)
                    selection_manager = pm.read_u64(value + self._selection_manager_offset)
                except OSError:
                    continue
                if not self._looks_like_vtable(vtable):
                    continue
                if not self._sane_heap_ptr(selection_manager):
                    continue
                add(value)
        return candidates


    def _selection_player_pointer_candidates_win10(
        self,
        pm: Win10ProcessMemory,
        diagnostics: Win10ReadLogger,
        *,
        discover: bool,
        scan_components: bool,
    ) -> list[int]:
        candidates: list[int] = []
        seen: set[int] = set()
        stats = {
            "cached_inputs": 0,
            "resource_owners": 0,
            "component_tags": 0,
            "pointer_values": 0,
            "duplicate_values": 0,
            "rejected_unsane": 0,
            "rejected_unreadable": 0,
            "rejected_vtable": 0,
            "rejected_manager": 0,
            "read_errors": 0,
            "accepted": 0,
        }

        def remember(value: int) -> None:
            if value in self._selection_player_candidates:
                self._selection_player_candidates.remove(value)
            self._selection_player_candidates.append(value)

        def add(value: int, source: str) -> None:
            stats["pointer_values"] += 1
            if value in seen:
                stats["duplicate_values"] += 1
                return
            seen.add(value)
            if not self._sane_heap_ptr(value):
                stats["rejected_unsane"] += 1
                return
            manager_field = value + self._selection_manager_offset
            if not pm.is_readable_range(value, 8) or not pm.is_readable_range(manager_field, 8):
                stats["rejected_unreadable"] += 1
                return
            try:
                vtable = pm.read_u64(value)
                selection_manager = pm.read_u64(manager_field)
            except OSError:
                stats["read_errors"] += 1
                return
            if not self._looks_like_vtable(vtable):
                stats["rejected_vtable"] += 1
                return
            if not self._sane_heap_ptr(selection_manager):
                stats["rejected_manager"] += 1
                return
            if not any(
                pm.is_readable_range(selection_manager + list_offset + 0x18, 0x0C)
                for list_offset in self._selection_list_offsets
            ):
                stats["rejected_unreadable"] += 1
                return
            candidates.append(value)
            stats["accepted"] += 1
            remember(value)
            diagnostics.log(
                "selection_player_candidate_accepted",
                source=source,
                player=f"0x{value:x}",
                manager=f"0x{selection_manager:x}",
            )

        for value in list(self._selection_player_candidates):
            stats["cached_inputs"] += 1
            add(value, "cached")

        if discover:
            resource_owners: list[int] = []
            resource_owner_seen: set[int] = set()
            for caches in self._resource_candidates_by_start.values():
                for cache in caches:
                    owner = int(cache.owner_key)
                    if owner in resource_owner_seen or not self._sane_heap_ptr(owner):
                        continue
                    resource_owner_seen.add(owner)
                    resource_owners.append(owner)
            stats["resource_owners"] = len(resource_owners)
            for owner in resource_owners:
                for offset in (0x90, 0x88):
                    pointer_address = owner + offset
                    if not pm.is_readable_range(pointer_address, 8):
                        stats["rejected_unreadable"] += 1
                        continue
                    try:
                        value = pm.read_u64(pointer_address)
                    except OSError:
                        stats["read_errors"] += 1
                        continue
                    add(value, f"resource_owner+0x{offset:x}")

        if discover and scan_components:
            tag = struct.pack("<Q", self.PLAYER_COMPONENT_TAG)
            tag_addresses = self._scan_bytes_private_win10(
                pm,
                tag,
                max_region_size=1024 * 1024,
            )
            stats["component_tags"] = len(tag_addresses)
            for tag_address in tag_addresses:
                owner = tag_address - 0x18
                if not self._sane_heap_ptr(owner) or not pm.is_readable_range(owner, 8):
                    stats["rejected_unreadable"] += 1
                    continue
                try:
                    owner_vtable = pm.read_u64(owner)
                except OSError:
                    stats["read_errors"] += 1
                    continue
                if not self._looks_like_vtable(owner_vtable):
                    stats["rejected_vtable"] += 1
                    continue
                for offset in (0x90, 0x88):
                    pointer_address = owner + offset
                    if not pm.is_readable_range(pointer_address, 8):
                        stats["rejected_unreadable"] += 1
                        continue
                    try:
                        value = pm.read_u64(pointer_address)
                    except OSError:
                        stats["read_errors"] += 1
                        continue
                    add(value, f"player_component+0x{offset:x}")

        diagnostics.log(
            "selection_player_candidates_win10",
            discover=discover,
            scan_components=scan_components,
            stats=stats,
            candidates=[f"0x{value:x}" for value in candidates],
        )
        return candidates


    def _candidate_from_selected_unit_pointer_win10(
        self,
        pm: Win10ProcessMemory,
        unit: int,
        note: str,
        score: int,
        selection_slot_address: int,
    ) -> UnitCandidate | None:
        if not self._sane_heap_ptr(unit) or not pm.is_readable_range(unit + 0x18, 8):
            return None
        try:
            handle = pm.read_u64(unit + 0x18)
        except OSError:
            return None
        if not self._looks_like_unit_handle(handle):
            return None
        owner = self._owner_for_unit_pointer_win10(pm, unit, handle)
        if owner is None:
            owner = self._owner_for_handle(pm, handle)
        if owner is None:
            return None
        return self._candidate_from_identity(
            pm,
            handle,
            owner,
            unit,
            note,
            score,
            selection_slot_address,
        )


    def _candidate_from_selection_player_win10(
        self,
        pm: Win10ProcessMemory,
        player: int,
    ) -> UnitCandidate | None:
        manager_field = player + self._selection_manager_offset
        if not pm.is_readable_range(manager_field, 8):
            return None
        try:
            selection_manager = pm.read_u64(manager_field)
        except OSError:
            return None
        if not self._sane_heap_ptr(selection_manager):
            return None

        for list_offset in self._selection_list_offsets:
            list_base = selection_manager + list_offset
            if not pm.is_readable_range(list_base + 0x18, 0x0C):
                continue
            for unit, slot_address in self._selection_manager_unit_slots(pm, list_base):
                candidate = self._candidate_from_selected_unit_pointer_win10(
                    pm,
                    unit,
                    (
                        f"selected_unit_slot=0x{unit:x} via=selection_manager "
                        f"player=0x{player:x} manager=0x{selection_manager:x} list=0x{list_base:x}"
                    ),
                    990 if list_offset == 0 else 980,
                    slot_address,
                )
                if candidate is None:
                    continue
                if player in self._selection_player_candidates:
                    self._selection_player_candidates.remove(player)
                self._selection_player_candidates.insert(0, player)
                return replace(candidate, selection_source="win10")
        return None


    def _locate_selected_unit_by_selection_manager_win10(
        self,
        pm: Win10ProcessMemory,
        diagnostics: Win10ReadLogger,
        *,
        discover: bool,
    ) -> UnitCandidate | None:
        cached_players = self._selection_player_pointer_candidates_win10(
            pm,
            diagnostics,
            discover=False,
            scan_components=False,
        )
        for player in cached_players:
            candidate = self._candidate_from_selection_player_win10(pm, player)
            if candidate is not None:
                return candidate
        if not discover:
            return None

        resource_players = self._selection_player_pointer_candidates_win10(
            pm,
            diagnostics,
            discover=True,
            scan_components=False,
        )
        cached_set = set(cached_players)
        for player in resource_players:
            if player in cached_set:
                continue
            candidate = self._candidate_from_selection_player_win10(pm, player)
            if candidate is not None:
                return candidate

        component_players = self._selection_player_pointer_candidates_win10(
            pm,
            diagnostics,
            discover=True,
            scan_components=True,
        )
        tried = set(resource_players)
        for player in component_players:
            if player in tried:
                continue
            candidate = self._candidate_from_selection_player_win10(pm, player)
            if candidate is not None:
                return candidate
        return None


    def _candidate_from_selected_unit_pointer(
        self,
        pm: ProcessMemory,
        unit: int,
        note: str,
        score: int,
        selection_slot_address: int,
    ) -> UnitCandidate | None:
        if not self._sane_heap_ptr(unit):
            return None
        try:
            handle = pm.read_u64(unit + 0x18)
        except OSError:
            return None
        if not self._looks_like_unit_handle(handle):
            return None
        owner = self._owner_for_unit_pointer(pm, unit, handle) or self._owner_for_handle(pm, handle)
        if owner is None:
            return None
        return self._candidate_from_identity(pm, handle, owner, unit, note, score, selection_slot_address)


    def _candidate_from_selection_player(self, pm: ProcessMemory, player: int) -> UnitCandidate | None:
        try:
            selection_manager = pm.read_u64(player + self._selection_manager_offset)
        except OSError:
            return None
        if not self._sane_heap_ptr(selection_manager):
            return None

        for list_offset in self._selection_list_offsets:
            list_base = selection_manager + list_offset
            for unit, slot_address in self._selection_manager_unit_slots(pm, list_base):
                candidate = self._candidate_from_selected_unit_pointer(
                    pm,
                    unit,
                    (
                        f"selected_unit_slot=0x{unit:x} via=selection_manager "
                        f"player=0x{player:x} manager=0x{selection_manager:x} list=0x{list_base:x}"
                    ),
                    990 if list_offset == 0 else 980,
                    slot_address,
                )
                if candidate is None:
                    continue
                if player in self._selection_player_candidates:
                    self._selection_player_candidates.remove(player)
                self._selection_player_candidates.insert(0, player)
                return candidate
        return None


    def _locate_selected_unit_by_player_component_scan(self, pm: ProcessMemory) -> UnitCandidate | None:
        del pm
        raise RuntimeError("selection component scan is disabled; use persistent native selection")


    @staticmethod
    def _selection_manager_offsets_from_code(code: bytes) -> list[int]:
        offsets: list[int] = []
        for index in range(0, max(0, len(code) - 6)):
            if code[index : index + 2] != b"\x48\x8b":
                continue
            # mov r64, qword ptr [rax + disp32], used after player-handle resolver.
            if code[index + 2] not in {0x88, 0x98}:
                continue
            disp = struct.unpack_from("<I", code, index + 3)[0]
            if 0x40 <= disp <= 0x800 and disp not in offsets:
                offsets.append(disp)
        return offsets


    @staticmethod
    def _selection_list_offsets_from_code(code: bytes) -> list[int]:
        offsets: list[int] = [0]
        for index in range(0, max(0, len(code) - 6)):
            # add rcx, disp32
            if code[index : index + 3] != b"\x48\x81\xc1":
                continue
            disp = struct.unpack_from("<I", code, index + 3)[0]
            if 0 < disp <= 0x1000 and disp not in offsets:
                offsets.append(disp)
        return offsets


    def _discover_native_selection_layout(self, pm: ProcessMemory) -> tuple[int, int, int, dict[str, NativeHandler]]:
        handlers = self._discover_native_handlers(pm, self.NATIVE_SELECTION_HANDLER_NAMES)
        manager_votes: dict[int, int] = {}
        for handler in handlers.values():
            try:
                code = pm.read(handler.handler_address, 0x240)
            except OSError:
                continue
            for offset in self._selection_manager_offsets_from_code(code):
                manager_votes[offset] = manager_votes.get(offset, 0) + 1
        if not manager_votes:
            raise RuntimeError("native selection handler 中没有找到 CPlayer selection manager 偏移")
        selection_manager_offset = max(
            manager_votes,
            key=lambda offset: (manager_votes[offset], offset == self.CPLAYER_SELECTION_MANAGER_OFFSET),
        )

        list_offsets: list[int] = [0]
        for call in self._rel32_calls_in_function(pm, handlers["IsUnitSelected"].handler_address, max_bytes=0x120):
            try:
                code = pm.read(call, 0x80)
            except OSError:
                continue
            for offset in self._selection_list_offsets_from_code(code):
                if offset not in list_offsets:
                    list_offsets.append(offset)
            for jump in self._rel32_jumps_in_function(pm, call, max_bytes=0x80):
                try:
                    jump_code = pm.read(jump, 0x80)
                except OSError:
                    continue
                for offset in self._selection_list_offsets_from_code(jump_code):
                    if offset not in list_offsets:
                        list_offsets.append(offset)
        alternate = self.SELECTION_MANAGER_ALT_LIST_OFFSET
        if alternate not in list_offsets:
            alternate = next((offset for offset in list_offsets if offset), self.SELECTION_MANAGER_ALT_LIST_OFFSET)
        return selection_manager_offset, 0, alternate, handlers


    def _prepare_win10_selection_layout(
        self,
        pm: Win10ProcessMemory,
        diagnostics: Win10ReadLogger,
    ) -> bool:
        started = time.perf_counter()
        previous_manager = self._selection_manager_offset
        previous_lists = tuple(self._selection_list_offsets)
        try:
            manager_offset, primary_offset, alternate_offset, handlers = (
                self._discover_native_selection_layout(pm)
            )
        except Exception as exc:
            diagnostics.log(
                "win10_selection_layout_failure",
                elapsed_ms=(time.perf_counter() - started) * 1000.0,
                previous_manager=f"0x{previous_manager:x}",
                previous_lists=[f"0x{offset:x}" for offset in previous_lists],
                exception=repr(exc),
            )
            return False
        self._selection_manager_offset = manager_offset
        self._selection_list_offsets = tuple(
            dict.fromkeys((primary_offset, alternate_offset))
        )
        diagnostics.log(
            "win10_selection_layout",
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
            previous_manager=f"0x{previous_manager:x}",
            manager=f"0x{manager_offset:x}",
            previous_lists=[f"0x{offset:x}" for offset in previous_lists],
            lists=[f"0x{offset:x}" for offset in self._selection_list_offsets],
            handlers={
                name: f"0x{handler.handler_address:x}"
                for name, handler in handlers.items()
            },
        )
        return True


    def _locate_selected_unit_by_selection_manager(self, pm: ProcessMemory) -> UnitCandidate | None:
        for player in self._selection_player_pointer_candidates(pm, discover=False):
            candidate = self._candidate_from_selection_player(pm, player)
            if candidate is not None:
                return candidate
        for player in self._selection_player_pointer_candidates(pm, discover=True):
            candidate = self._candidate_from_selection_player(pm, player)
            if candidate is not None:
                return candidate
        return None


    def _selected_candidates_from_selection_manager(
        self,
        pm: ProcessMemory,
    ) -> tuple[UnitCandidate, ...]:
        """Read the live selection list without JASS group enumeration."""
        candidates: list[UnitCandidate] = []
        seen: set[int] = set()
        players = self._selection_player_pointer_candidates(pm, discover=False)
        for player in players:
            try:
                selection_manager = pm.read_u64(player + self._selection_manager_offset)
            except OSError:
                continue
            if not self._sane_heap_ptr(selection_manager):
                continue
            for list_offset in self._selection_list_offsets:
                for unit, slot_address in self._selection_manager_unit_slots(
                    pm, selection_manager + list_offset
                ):
                    candidate = self._candidate_from_selected_unit_pointer(
                        pm,
                        unit,
                        f"selected_unit_slot=0x{unit:x} via=selection_manager",
                        990 if list_offset == 0 else 980,
                        slot_address,
                    )
                    if candidate is None or candidate.unit_address in seen:
                        continue
                    seen.add(candidate.unit_address)
                    candidates.append(candidate)
        return tuple(candidates)


    def probe_native_selection_manager(self) -> NativeSelectionProbeResult:
        # The persistent native snapshot is the sole selection source. Keep
        # this compatibility-shaped result for the UI without rediscovering
        # offsets or walking process memory.
        selected = self._selected_candidates_snapshot(None)
        candidate = selected[0][0] if selected else None
        return NativeSelectionProbeResult(
            0,
            0,
            0,
            0,
            0,
            candidate,
            "persistent_native_snapshot",
        )


    def prewarm_selected_unit_cache(self) -> UnitCandidate:
        candidate = self.locate_selected_unit_by_handle()
        self._unit_fields_from_candidate(None, candidate)
        return candidate


    def _locate_selected_unit_by_panel(self, pm: ProcessMemory) -> UnitCandidate:
        raise RuntimeError("OCR/面板数值定位已禁用；当前选中单位只能通过内存 selected-handle 定位")


    def _read_jass_selected_unit_raw(self, pm: ProcessMemory) -> tuple[int, int, int]:
        handlers = self._discover_native_handlers(pm, self.JASS_SELECTION_NATIVE_NAMES)
        results = self._run_native_helper_ops(
            0,
            (
                (
                    self.NATIVE_HELPER_OP_JASS_SELECTED_UNIT,
                    0,
                    handlers["CreateGroup"].handler_address,
                    handlers["SyncSelections"].handler_address,
                    handlers["GetLocalPlayer"].handler_address,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_SELECTED_UNIT_ARG,
                    0,
                    handlers["GroupEnumUnitsSelected"].handler_address,
                    handlers["FirstOfGroup"].handler_address,
                    handlers["GetHandleId"].handler_address,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_SELECTED_UNIT_ARG,
                    0,
                    handlers["DestroyGroup"].handler_address,
                    0,
                    0,
                ),
            ),
            timeout_ms=1000,
        )
        unit_handle = results[0].result
        handle_id = results[1].result & 0xFFFFFFFF
        player_handle = results[2].result
        return unit_handle, handle_id, player_handle


    def _read_jass_selected_unit_raw_win10(
        self,
        pm: ProcessMemory,
    ) -> tuple[int, int, int]:
        handlers = self._discover_native_handlers(pm, self.WIN10_SELECTION_NATIVE_NAMES)
        results = self._run_native_helper_ops(
            0,
            (
                (
                    self.NATIVE_HELPER_OP_JASS_SELECTED_UNIT,
                    0,
                    handlers["CreateGroup"].handler_address,
                    0,
                    handlers["GetLocalPlayer"].handler_address,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_SELECTED_UNIT_ARG,
                    0,
                    handlers["GroupEnumUnitsSelected"].handler_address,
                    handlers["FirstOfGroup"].handler_address,
                    handlers["GetHandleId"].handler_address,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_SELECTED_UNIT_ARG,
                    0,
                    handlers["DestroyGroup"].handler_address,
                    0,
                    0,
                ),
            ),
            timeout_ms=1000,
        )
        return results[0].result, results[1].result & 0xFFFFFFFF, results[2].result


    def _is_jass_unit_selected_win10(
        self,
        pm: ProcessMemory,
        unit_handle: int,
        player_handle: int,
    ) -> bool:
        handlers = self._discover_native_handlers(pm, ("IsUnitSelected",))
        result = self._run_native_helper_ops(
            unit_handle,
            (
                (
                    self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE,
                    player_handle & 0xFFFFFFFF,
                    handlers["IsUnitSelected"].handler_address,
                    0,
                    0,
                ),
            ),
        )[0].result
        return bool(result & 0xFFFFFFFF)


    def _read_selected_unit_type_id(self, pm: ProcessMemory, candidate: UnitCandidate) -> int:
        native = self._native_snapshot_for_candidate(candidate)
        if native is not None:
            return native.type_id
        if not candidate.unit_address:
            return 0
        primary = pm.read_u32(candidate.unit_address + 0x70)
        mirror = pm.read_u32(candidate.unit_address + 0x178)
        if primary != mirror or not self._looks_like_item_rawcode(primary):
            return 0
        return primary


    def _candidate_with_selected_unit_type_id(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
    ) -> UnitCandidate:
        try:
            unit_type_id = self._read_selected_unit_type_id(pm, candidate)
        except (OSError, RuntimeError):
            return candidate
        if not unit_type_id:
            return candidate
        return replace(candidate, unit_type_id=unit_type_id)


    def _candidate_from_jass_selection_result(
        self,
        pm: ProcessMemory,
        unit_value: int,
        handle_id: int,
        player_handle: int,
        unit_index: dict[int, tuple[int, int]] | None = None,
    ) -> UnitCandidate | None:
        note = f"jass_selected unit=0x{unit_value:x} handle_id=0x{handle_id:x} player=0x{player_handle:x}"
        if unit_index is None:
            unit_index = self._build_unit_object_index(pm, force_refresh=True)
        entry = unit_index.get(unit_value)
        if entry is not None:
            handle, owner = entry
            candidate = self._candidate_from_owner(pm, owner, 980, note + " mode=unit_ptr", handle, "jass", 0)
            if candidate is not None and candidate.unit_address == unit_value:
                return candidate

        if self._looks_like_unit_handle(unit_value):
            owner = self._owner_for_handle(pm, unit_value)
            if owner is not None:
                candidate = self._candidate_from_owner(pm, owner, 970, note + " mode=unit_handle", unit_value, "jass", 0)
                if candidate is not None:
                    return candidate

        if self._sane_heap_ptr(unit_value):
            try:
                nested_handle = pm.read_u64(unit_value + 0x18)
            except OSError:
                nested_handle = 0
            if self._looks_like_unit_handle(nested_handle):
                owner = self._owner_for_handle(pm, nested_handle)
                if owner is not None:
                    candidate = self._candidate_from_owner(
                        pm,
                        owner,
                        960,
                        note + f" mode=handle_at_unit+0x18 nested=0x{nested_handle:x}",
                        nested_handle,
                        "jass",
                        0,
                    )
                    if candidate is not None and candidate.unit_address == unit_value:
                        return candidate

        if handle_id:
            matches: list[UnitCandidate] = []
            for handle, owner in (self._unit_owner_index or self._build_unit_owner_index(pm)).items():
                low = handle & 0xFFFFFFFF
                high = (handle >> 32) & 0xFFFFFFFF
                if handle_id not in {low, high}:
                    continue
                candidate = self._candidate_from_owner(
                    pm,
                    owner,
                    940,
                    note + f" mode=handle_id_match full_handle=0x{handle:x}",
                    handle,
                    "jass",
                    0,
                )
                if candidate is not None:
                    matches.append(candidate)
            unique_by_unit = {candidate.unit_address: candidate for candidate in matches if candidate.unit_address}
            if len(unique_by_unit) == 1:
                return next(iter(unique_by_unit.values()))
        return None


    def _candidate_from_jass_selection_result_win10(
        self,
        pm: ProcessMemory,
        unit_value: int,
        handle_id: int,
        player_handle: int,
        unit_index: dict[int, tuple[int, int]] | None = None,
    ) -> UnitCandidate | None:
        note = (
            f"win10_jass_selected unit=0x{unit_value:x} "
            f"handle_id=0x{handle_id:x} player=0x{player_handle:x}"
        )

        def candidate_for(handle: int, owner: int, expected_unit: int = 0) -> UnitCandidate | None:
            candidate = self._candidate_from_owner(
                pm,
                owner,
                1000,
                note,
                handle,
                "win10_jass",
                0,
            )
            if candidate is None:
                return None
            if expected_unit and candidate.unit_address != expected_unit:
                return None
            return candidate

        if unit_index is not None:
            entry = unit_index.get(unit_value)
            if entry is not None:
                candidate = candidate_for(entry[0], entry[1], unit_value)
                if candidate is not None:
                    return candidate

        owner = self._unit_owner_index.get(unit_value)
        if owner is not None:
            candidate = candidate_for(unit_value, owner)
            if candidate is not None:
                return candidate

        if self._sane_heap_ptr(unit_value):
            try:
                nested_handle = pm.read_u64(unit_value + 0x18)
            except OSError:
                nested_handle = 0
            owner = self._unit_owner_index.get(nested_handle)
            if (
                owner is None
                and isinstance(pm, Win10ProcessMemory)
                and self._looks_like_unit_handle(nested_handle)
            ):
                owner = self._owner_for_unit_pointer_win10(
                    pm,
                    unit_value,
                    nested_handle,
                )
            if owner is not None:
                candidate = candidate_for(nested_handle, owner, unit_value)
                if candidate is not None:
                    return candidate

        if handle_id:
            matches: dict[int, UnitCandidate] = {}
            for handle, candidate_owner in self._unit_owner_index.items():
                low = handle & 0xFFFFFFFF
                high = (handle >> 32) & 0xFFFFFFFF
                if handle_id not in {low, high}:
                    continue
                candidate = candidate_for(handle, candidate_owner)
                if candidate is not None and candidate.unit_address:
                    matches[candidate.unit_address] = candidate
            if len(matches) == 1:
                return next(iter(matches.values()))
        return None


    def locate_selected_unit_by_jass_native_win10(
        self,
        pm: ProcessMemory,
        diagnostics: Win10ReadLogger,
    ) -> UnitCandidate:
        del pm, diagnostics
        return self.locate_selected_unit_by_handle()
        # Historical Win10/JASS resolution is intentionally unreachable.
        started = time.perf_counter()
        self._last_win10_jass_unit_handle = 0
        self._last_win10_jass_player_handle = 0
        self._last_win10_jass_handle_id = 0
        unit_value, handle_id, player_handle = self._read_jass_selected_unit_raw_win10(pm)
        diagnostics.log(
            "win10_jass_selection_raw",
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
            unit=f"0x{unit_value:x}",
            handle_id=f"0x{handle_id:x}",
            player=f"0x{player_handle:x}",
        )
        if not unit_value and not handle_id:
            raise RuntimeError("JASS 当前选择为空")
        resolved_unit = self._resolve_jass_unit_handle_win10(
            pm,
            unit_value,
            allow_missing=True,
        )
        resolved_region = self._region_for_address(pm.regions(), resolved_unit)
        diagnostics.log(
            "win10_jass_selection_resolved",
            jass_handle=f"0x{unit_value:x}",
            unit=f"0x{resolved_unit:x}",
            resolver=f"0x{self._jass_unit_resolver_address:x}",
            unit_readable=(
                pm.is_readable_range(resolved_unit, 0x20)
                if isinstance(pm, Win10ProcessMemory) and resolved_unit
                else False
            ),
            region_base=(
                f"0x{resolved_region.base:x}" if resolved_region is not None else ""
            ),
            region_size=(
                f"0x{resolved_region.size:x}" if resolved_region is not None else ""
            ),
            region_type=(
                f"0x{resolved_region.typ:x}" if resolved_region is not None else ""
            ),
        )
        if not resolved_unit:
            raise RuntimeError(
                f"JASS 当前选择句柄无法解析：0x{unit_value:x}"
            )
        if not self._is_jass_unit_selected_win10(pm, unit_value, player_handle):
            raise RuntimeError(
                "JASS 返回的单位已不在当前单选中，拒绝复用历史单位："
                f"handle=0x{unit_value:x} unit=0x{resolved_unit:x}"
            )
        candidate = self._candidate_from_jass_selection_result_win10(
            pm,
            resolved_unit,
            handle_id,
            player_handle,
        )
        if candidate is None:
            raise RuntimeError(
                "JASS 已取得当前选择，但无法映射到可信单位对象："
                f"handle=0x{unit_value:x} unit=0x{resolved_unit:x} "
                f"handle_id=0x{handle_id:x}"
            )
        self._last_win10_jass_unit_handle = unit_value
        self._last_win10_jass_player_handle = player_handle
        self._last_win10_jass_handle_id = handle_id
        diagnostics.log(
            "selection_candidate_found",
            route="jass_no_sync_verified",
            handle=f"0x{candidate.handle:x}",
            owner=f"0x{candidate.owner_address:x}",
            unit=f"0x{candidate.unit_address:x}",
            note=candidate.note,
        )
        return candidate


    def probe_jass_selected_unit(self) -> JassSelectionProbeResult:
        selected = self._selected_candidates_snapshot(None)
        if not selected:
            return JassSelectionProbeResult(0, 0, 0, None, "empty")
        candidate, unit_handle = selected[0]
        return JassSelectionProbeResult(
            unit_handle,
            candidate.handle & 0xFFFFFFFF,
            0,
            candidate,
            "persistent_native_snapshot",
        )


    def locate_selected_unit_by_jass_native(self, pm: ProcessMemory | None = None) -> UnitCandidate:
        del pm
        selected = self._selected_candidates_snapshot(None)
        if not selected:
            raise RuntimeError("游戏当前没有可操作的选中单位")
        return selected[0][0]


    def locate_selected_unit_by_handle(
        self,
        pm: ProcessMemory | None = None,
        allow_panel_fallback: bool = False,
        allow_deep_scan: bool = False,
    ) -> UnitCandidate:
        # Retain the old public signature for callers, but this locator now
        # uses the engine selection and its complete identity on every call.
        # Neither compatibility flag enables historical slots or heap scans.
        selected = self._selected_candidates_snapshot(pm)
        if not selected:
            raise RuntimeError("游戏当前没有可操作的选中单位")
        return selected[0][0]


    def locate_selected_unit_win10(
        self,
        pm: ProcessMemory | None = None,
        diagnostics: Win10ReadLogger | None = None,
    ) -> UnitCandidate:
        del pm, diagnostics
        return self.locate_selected_unit_by_handle()
        # Historical Win10 slot probing is intentionally unreachable.
        close_pm = False
        close_diagnostics = False
        if diagnostics is None and isinstance(pm, Win10ProcessMemory):
            diagnostics = pm.diagnostics
        if pm is None:
            if diagnostics is None:
                diagnostics = Win10ReadLogger(self.pid)
                close_diagnostics = True
            pm = Win10ProcessMemory(self.pid, diagnostics)
            close_pm = True

        def log(event: str, **values: object) -> None:
            if diagnostics is not None:
                diagnostics.log(event, **values)

        try:
            last_error: str | None = None
            tried: set[int] = set()

            def try_slot(address: int, min_score: int = 0) -> UnitCandidate | None:
                nonlocal last_error
                tried.add(address)
                if isinstance(pm, Win10ProcessMemory) and not pm.is_readable_range(address, 8):
                    log(
                        "selection_slot_skipped_unreadable",
                        address=f"0x{address:x}",
                    )
                    return None
                try:
                    handle = pm.read_u64(address)
                except OSError as exc:
                    last_error = str(exc)
                    log(
                        "selection_slot_read_error",
                        address=f"0x{address:x}",
                        exception=repr(exc),
                    )
                    return None
                if not self._looks_like_unit_handle(handle):
                    last_error = f"0x{address:x} 不是单位 handle"
                    log(
                        "selection_slot_invalid_handle",
                        address=f"0x{address:x}",
                        value=f"0x{handle:x}",
                    )
                    return None
                owner = self._owner_for_handle(pm, handle)
                if owner is None:
                    last_error = f"0x{handle:x} 没有匹配单位对象"
                    log(
                        "selection_slot_owner_missing",
                        address=f"0x{address:x}",
                        handle=f"0x{handle:x}",
                    )
                    return None
                score = self._score_selected_handle_address(pm, address, handle, owner)
                if score < min_score:
                    last_error = f"0x{address:x} 像历史选择槽，不是当前选择槽"
                    log(
                        "selection_slot_score_rejected",
                        address=f"0x{address:x}",
                        handle=f"0x{handle:x}",
                        owner=f"0x{owner:x}",
                        score=score,
                        min_score=min_score,
                    )
                    return None
                candidate = self._candidate_from_owner(
                    pm,
                    owner,
                    900 + score,
                    f"selected_handle=0x{handle:x} slot=0x{address:x}",
                    handle,
                    "win10",
                    address,
                )
                if candidate is None:
                    last_error = f"0x{handle:x} 没有生命属性"
                    log(
                        "selection_slot_candidate_invalid",
                        address=f"0x{address:x}",
                        handle=f"0x{handle:x}",
                        owner=f"0x{owner:x}",
                    )
                    return None
                if address in self._selected_handle_addresses:
                    self._selected_handle_addresses.remove(address)
                self._selected_handle_addresses.insert(0, address)
                log(
                    "selection_candidate_found",
                    route="handle_slot",
                    address=f"0x{address:x}",
                    handle=f"0x{handle:x}",
                    owner=f"0x{owner:x}",
                    unit=f"0x{candidate.unit_address:x}",
                    score=score,
                )
                return candidate

            retry_delays = (0.0, 0.08, 0.20)
            for attempt, delay in enumerate(retry_delays, start=1):
                if delay:
                    time.sleep(delay)
                tried.clear()
                log(
                    "selection_attempt_begin",
                    attempt=attempt,
                    delay=delay,
                    discover_players=attempt == 1,
                )

                try:
                    selection_manager_candidate = self._locate_selected_unit_by_selection_manager_win10(
                        pm,
                        diagnostics,
                        discover=attempt == 1,
                    )
                except Exception as exc:
                    selection_manager_candidate = None
                    last_error = str(exc)
                    log(
                        "selection_manager_error",
                        attempt=attempt,
                        exception=repr(exc),
                    )
                if selection_manager_candidate is not None:
                    log(
                        "selection_candidate_found",
                        route="selection_manager",
                        handle=f"0x{selection_manager_candidate.handle:x}",
                        owner=f"0x{selection_manager_candidate.owner_address:x}",
                        unit=f"0x{selection_manager_candidate.unit_address:x}",
                        note=selection_manager_candidate.note,
                    )
                    return selection_manager_candidate
                log("selection_manager_miss", attempt=attempt)

                if attempt == 1:
                    try:
                        unit_pointer_candidate = self._locate_selected_unit_by_known_unit_pointer_win10(
                            pm,
                            diagnostics,
                        )
                    except Exception as exc:
                        unit_pointer_candidate = None
                        last_error = str(exc)
                        log(
                            "known_unit_pointer_error",
                            attempt=attempt,
                            exception=repr(exc),
                        )
                    if unit_pointer_candidate is not None:
                        log(
                            "selection_candidate_found",
                            route="known_unit_pointer",
                            handle=f"0x{unit_pointer_candidate.handle:x}",
                            owner=f"0x{unit_pointer_candidate.owner_address:x}",
                            unit=f"0x{unit_pointer_candidate.unit_address:x}",
                            note=unit_pointer_candidate.note,
                        )
                        return unit_pointer_candidate
                    log("known_unit_pointer_miss", attempt=attempt)

                try:
                    known_addresses = self._known_selected_handle_address_candidates(pm)
                except Exception as exc:
                    known_addresses = []
                    last_error = str(exc)
                    log(
                        "known_selection_slots_error",
                        attempt=attempt,
                        exception=repr(exc),
                    )
                log(
                    "known_selection_slots",
                    attempt=attempt,
                    count=len(known_addresses),
                    readable_count=sum(
                        1
                        for address in known_addresses
                        if not isinstance(pm, Win10ProcessMemory)
                        or pm.is_readable_range(address, 8)
                    ),
                    addresses=[f"0x{address:x}" for address in known_addresses],
                )
                for address in known_addresses:
                    candidate = try_slot(
                        address,
                        min_score=self.WIN10_STRONG_SELECTION_SCORE,
                    )
                    if candidate is not None:
                        return candidate

                cached_addresses = list(dict.fromkeys(self._selected_handle_addresses))
                log(
                    "cached_selection_slots",
                    attempt=attempt,
                    count=len(cached_addresses),
                    addresses=[f"0x{address:x}" for address in cached_addresses],
                )
                for address in cached_addresses:
                    if address in tried:
                        continue
                    candidate = try_slot(
                        address,
                        min_score=self.WIN10_STRONG_SELECTION_SCORE,
                    )
                    if candidate is not None:
                        return candidate

            try:
                discovered_addresses = self._discover_selected_handle_addresses(pm)
            except Exception as exc:
                discovered_addresses = []
                last_error = str(exc)
                log("deep_selection_slots_error", exception=repr(exc))
            log(
                "deep_selection_slots",
                count=len(discovered_addresses),
                addresses=[f"0x{address:x}" for address in discovered_addresses],
            )
            for address in discovered_addresses:
                if address in tried:
                    continue
                candidate = try_slot(
                    address,
                    min_score=self.WIN10_STRONG_SELECTION_SCORE,
                )
                if candidate is not None:
                    return candidate
            detail = f"；最后错误：{last_error}" if last_error else ""
            log("selection_failed", last_error=last_error, tried=len(tried))
            raise RuntimeError(
                f"没有找到当前选中单位 handle，请在游戏里左键选中一个单位后重试{detail}"
            )
        finally:
            if close_pm:
                pm.close()
            if close_diagnostics and diagnostics is not None:
                diagnostics.close()


    def locate_selected_unit(
        self,
        current_hp: float,
        current_mp: float | None = None,
        max_hp: float | None = None,
        max_mp: float | None = None,
    ) -> UnitCandidate:
        # Keep the legacy signature for old CLI callers, but never infer identity
        # from HP/MP/stat values. Identical units and changing hero stats must
        # still resolve through the live selected-unit handle.
        return self.locate_selected_unit_by_handle(allow_panel_fallback=False)


    def _candidate_from_identity(
        self,
        pm: ProcessMemory,
        handle: int,
        owner: int,
        unit: int,
        note: str,
        score: int = 0,
        selection_slot_address: int = 0,
    ) -> UnitCandidate | None:
        self._last_selection_candidate_failure = {}
        try:
            from war3_game_profile import current_profile
            layout = current_profile().section("registry")
            for address, expected, stage in (
                (owner + layout["owner_handle"], handle, "owner_handle"),
                (owner + layout["owner_data"], unit, "owner_unit"),
                (unit + layout["object_handle"], handle, "unit_handle"),
            ):
                actual = pm.read_u64(address)
                if actual != expected:
                    self._last_selection_candidate_failure = {
                        "stage": stage, "address": address, "expected": expected, "actual": actual,
                    }
                    return None
        except OSError as exc:
            self._last_selection_candidate_failure = {
                "stage": "identity_unreadable", "owner": owner, "unit": unit,
                "winerror": getattr(exc, "winerror", None),
            }
            return None
        candidate = self._candidate_from_owner(pm, owner, score, note, handle, "memory", selection_slot_address)
        if candidate is None:
            return None
        if candidate.unit_address != unit:
            self._last_selection_candidate_failure = {
                "stage": "unit_changed", "expected": unit, "actual": candidate.unit_address,
            }
            return None
        return candidate


    def _candidate_from_display_identity(
        self, pm: ProcessMemory | None, handle: int, owner: int, unit: int,
        note: str, score: int = 0, *, registry_required: bool = True,
    ) -> UnitCandidate | None:
        # Resolve the full object identity in the DLL, including its current
        # JASS handle. This also works after the selection cache was replaced.
        if not handle or not owner or not unit:
            return None
        if getattr(self, "_native_selection_unavailable", False):
            from war3_object_registry import ObjectRegistry24268
            close_pm = pm is None
            memory = pm or self._process_memory()
            try:
                if registry_required:
                    registry = self._classic_object_registry or ObjectRegistry24268.attach(memory)
                    self._classic_object_registry = registry
                    if registry.resolve_unit(memory, unit) != (handle, owner):
                        raise RuntimeError("Requested unit identity is stale")
                candidate = self._candidate_from_identity(
                    memory, handle, owner, unit, note, score,
                )
                if candidate is None:
                    raise RuntimeError("Requested unit identity is stale")
                return candidate
            finally:
                if close_pm:
                    memory.close()
        self.persistent_native_init()
        results = self._run_native_helper_ops(0, (
            (self.NATIVE_HELPER_OP_IDENTITY_UNIT_SNAPSHOT, 0, unit, handle, owner),
        ))
        if len(results) != 1 or results[0].last_error:
            raise RuntimeError("Incomplete native identity snapshot")
        snapshots = self._parse_persistent_native_snapshots(results[0])
        if len(snapshots) != 1 or (snapshots[0].full_handle, snapshots[0].owner_address,
                                   snapshots[0].unit_address) != (handle, owner, unit):
            raise RuntimeError("Native identity snapshot does not match the requested unit")
        candidate = self._candidate_from_native_snapshot(None, snapshots[0])
        return replace(candidate, note=note, score=score) if candidate is not None else None


    def _selection_summary_from_candidate(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        refs: int,
        known_hits: int,
        region_base: int,
        components: dict[str, tuple[int, int]] | None = None,
        include_inventory: bool = True,
        include_abilities: bool = True,
    ) -> UnitSelectionSummary:
        if pm is None and self._native_snapshot_for_candidate(candidate) is None:
            # Read-only 3.0 selection identities are produced without keeping
            # a ProcessMemory object alive. Reopen the read handle for the
            # summary fields instead of dereferencing None during GUI startup.
            with self._process_memory() as summary_memory:
                return self._selection_summary_from_candidate(
                    summary_memory, candidate, refs, known_hits, region_base,
                    components=components, include_inventory=include_inventory,
                    include_abilities=include_abilities,
                )
        native = self._native_snapshot_for_candidate(candidate)
        if native is not None:
            memory = self._native_unit_field_memory(candidate)
            return UnitSelectionSummary(
                candidate=candidate, refs=refs, known_hits=known_hits, region_base=region_base,
                hp_text=f"{int(round(native.hp))}/{int(round(native.hp_max))}",
                mp_text=f"{int(round(native.mp))}/{int(round(native.mp_max))}",
                position=(native.x, native.y), components=tuple(sorted(memory.components)),
                inventory=tuple(f"{item.slot}:{item.rawcode_text}" for item in memory.inventory_items
                                if item.rawcode) if include_inventory else (),
                ability_count=len(native.ability_ids) if include_abilities else 0,
                hero="hero" in memory.components,
            )
        panel = self._panel_from_candidate(pm, candidate)
        position = self._position_from_candidate(pm, candidate)
        components = components if components is not None else self._selected_components(pm, candidate.owner_address)
        inventory: list[str] = []
        if include_inventory:
            for item in self._inventory_items_from_candidate(pm, candidate, components):
                if item.rawcode:
                    inventory.append(f"{item.slot}:{item.rawcode_text}")
        ability_count = len(self._ability_instances_from_candidate(pm, candidate)) if include_abilities else 0
        return UnitSelectionSummary(
            candidate=candidate,
            refs=refs,
            known_hits=known_hits,
            region_base=region_base,
            hp_text=panel.hp_text,
            mp_text=panel.mp_text,
            position=position,
            components=tuple(sorted(components)),
            inventory=tuple(inventory),
            ability_count=ability_count,
            hero="hero" in components,
        )


    def selection_summary_from_identity(
        self,
        handle: int,
        owner: int,
        unit: int,
        note: str = "",
    ) -> UnitSelectionSummary:
        candidate = self._candidate_from_display_identity(
            None, handle, owner, unit,
            note or f"remembered_identity=0x{handle:x},0x{owner:x},0x{unit:x}",
            860,
        )
        if candidate is None:
            raise RuntimeError("候选单位已经失效，请重新读取候选列表")
        return self._selection_summary_from_candidate(None, candidate, refs=0, known_hits=2, region_base=0)


    @staticmethod
    def _selection_summary_priority(summary: UnitSelectionSummary) -> tuple[int, int, int, int, int]:
        note = summary.candidate.note
        if note.startswith("remembered_identity=") or note.startswith("manual_candidate"):
            base = 100000
        elif note.startswith("selected_handle=") or note.startswith("selected_unit_slot=") or summary.known_hits >= 2:
            base = 90000
        elif note.startswith("global_unit_scan"):
            base = 20000
        else:
            base = 30000
        if summary.hero:
            base += 30000
        if "inventory" in summary.components:
            base += 10000
        if "move" in summary.components:
            base += 500
        return (
            base,
            len(summary.inventory),
            summary.known_hits,
            summary.refs,
            summary.candidate.score,
        )


    def list_selection_candidates(
        self,
        limit: int = 80,
        extra_identities: Iterable[tuple[int, int, int]] | None = None,
    ) -> list[UnitSelectionSummary]:
        # Remembered identities need their own bound snapshot after selection
        # changes; resolving them from external addresses loses that binding.
        if getattr(self, "_native_selection_unavailable", False):
            with self._process_memory() as memory:
                selected = self._classic_selection_candidates(memory)
                summaries = list(self._selected_summaries_from_snapshot(memory, selected))
        else:
            self.persistent_native_init()
            selected = self._selected_candidates_snapshot(None)
            summaries = list(self._selected_summaries_from_snapshot(None, selected))
        if extra_identities is not None:
            for handle, owner, unit in extra_identities:
                summaries.append(self.selection_summary_from_identity(handle, owner, unit))
        return summaries[:max(0, int(limit))]


    def selection_candidate_line(self, summary: UnitSelectionSummary, index: int) -> str:
        pos = summary.position
        pos_text = f" x={pos[0]:.1f} y={pos[1]:.1f}" if pos is not None else ""
        components = ",".join(summary.components) if summary.components else "-"
        inventory = ",".join(summary.inventory) if summary.inventory else "-"
        confidence = selection_confidence_text(summary)
        return (
            f"#{index} [{confidence}] hp={summary.hp_text} mp={summary.mp_text}{pos_text} "
            f"refs={summary.refs} known={summary.known_hits} "
            f"handle=0x{summary.candidate.handle:x} owner=0x{summary.candidate.owner_address:x} "
            f"unit=0x{summary.candidate.unit_address:x} components={components} "
            f"abilities={summary.ability_count} inventory={inventory} note={summary.candidate.note}"
        )


    @staticmethod
    def _sane_heap_ptr(value: int) -> bool:
        return 0x100000000 <= value <= 0x7FFFFFFFFFFF


    def _panel_from_candidate(self, pm: ProcessMemory | None, candidate: UnitCandidate) -> VisibleUnitPanel:
        if pm is None and self._native_snapshot_for_candidate(candidate) is None:
            with self._process_memory() as panel_memory:
                return self._panel_from_candidate(panel_memory, candidate)
        native = self._native_snapshot_for_candidate(candidate)
        actual_hp = int(round(native.hp if native is not None else pm.read_f32(candidate.hp_current_address)))
        actual_hp_max = int(round(native.hp_max if native is not None else pm.read_f32(candidate.hp_max_address)))
        actual_mp = 0
        actual_mp_max = 0
        if native is not None:
            actual_mp = int(round(native.mp))
            actual_mp_max = int(round(native.mp_max))
        elif candidate.mp_current_address and candidate.mp_max_address:
            actual_mp = int(round(pm.read_f32(candidate.mp_current_address)))
            actual_mp_max = int(round(pm.read_f32(candidate.mp_max_address)))
        return VisibleUnitPanel(
            actual_hp,
            actual_hp_max,
            actual_mp,
            actual_mp_max,
            f"{actual_hp}/{actual_hp_max}",
            f"{actual_mp}/{actual_mp_max}",
        )


    def _position_from_candidate(self, pm: ProcessMemory, candidate: UnitCandidate) -> tuple[float, float] | None:
        if pm is None and self._native_snapshot_for_candidate(candidate) is None:
            with self._process_memory() as position_memory:
                return self._position_from_candidate(position_memory, candidate)
        native = self._native_snapshot_for_candidate(candidate)
        if native is not None:
            return native.x, native.y
        if not candidate.x_address or not candidate.y_address:
            return None
        return pm.read_f32(candidate.x_address), pm.read_f32(candidate.y_address)


    @staticmethod
    def _read_memory_value(pm: ProcessMemory, address: int, value_type: str) -> int | float:
        if value_type == "f32":
            return pm.read_f32(address)
        if value_type == "i32":
            return pm.read_i32(address)
        if value_type in {"u64", "ptr"}:
            return pm.read_u64(address)
        if value_type in {"u32", "rawcode"}:
            return pm.read_u32(address)
        raise ValueError(f"不支持的字段类型：{value_type}")


    @staticmethod
    def _coerce_memory_value(value_type: str, value: int | float | str) -> int | float:
        if value_type == "f32":
            return coerce_finite_float32(value)
        if value_type in {"i32", "u32"}:
            return parse_integer_number(value)
        if value_type in {"u64", "ptr"}:
            return parse_integer_number(value)
        if value_type == "rawcode":
            if isinstance(value, str):
                text = value.strip()
                if len(text) == 4 and not text.lower().startswith("0x"):
                    return struct.unpack(">I", text.encode("ascii"))[0]
                return parse_integer_number(text)
            return parse_integer_number(value)
        raise ValueError(f"不支持的字段类型：{value_type}")


    @classmethod
    def _write_memory_value(
        cls,
        pm: ProcessMemory,
        address: int,
        value_type: str,
        value: int | float | str,
    ) -> None:
        coerced = cls._coerce_memory_value(value_type, value)
        if value_type == "f32":
            pm.write_f32(address, float(coerced))
            return
        if value_type == "i32":
            pm.write_i32(address, int(coerced))
            return
        if value_type in {"u32", "rawcode"}:
            pm.write_u32(address, int(coerced))
            return
        if value_type in {"u64", "ptr"}:
            data = struct.pack("<Q", int(coerced))
            written = ctypes.c_size_t()
            ok = kernel32.WriteProcessMemory(
                pm.handle, ctypes.c_void_p(address), data, len(data), ctypes.byref(written)
            )
            if not ok or written.value != len(data):
                raise ctypes.WinError(ctypes.get_last_error())
            return
        raise ValueError(f"不支持的字段类型：{value_type}")


    def _iter_owner_component_wrappers(
        self,
        pm: ProcessMemory,
        owner: int,
    ) -> Iterable[tuple[str, int, int]]:
        start = owner - self.COMPONENT_WRAPPER_SCAN_BACK
        end = owner + self.COMPONENT_WRAPPER_SCAN_FORWARD
        for region in pm.regions():
            region_start = max(start, region.base)
            region_end = min(end, region.base + region.size)
            if region_end <= region_start:
                continue
            try:
                block = pm.read(region_start, region_end - region_start)
            except OSError:
                continue
            for tag, name in self.COMPONENT_NAMES.items():
                pattern = struct.pack("<Q", tag)
                search = 0
                while True:
                    index = block.find(pattern, search)
                    if index < 0:
                        break
                    search = index + 1
                    wrapper = region_start + index - 0x18
                    if wrapper < start or wrapper >= end:
                        continue
                    try:
                        vtable = pm.read_u64(wrapper)
                        wrapper_owner = pm.read_u64(wrapper + 0x50)
                        data = pm.read_u64(wrapper + 0x90)
                    except OSError:
                        continue
                    if wrapper_owner != owner:
                        continue
                    if not self._looks_like_vtable(vtable) or not self._sane_heap_ptr(data):
                        continue
                    try:
                        data_vtable = pm.read_u64(data)
                    except OSError:
                        continue
                    if not self._looks_like_vtable(data_vtable):
                        continue
                    yield name, wrapper, data


    def _iter_indexed_owner_component_wrappers(
        self,
        pm: ProcessMemory,
        owner: int,
    ) -> Iterable[tuple[str, int, int]]:
        from war3_object_registry import ObjectRegistry24268
        from war3_unit_components import read_unit_components
        if not owner:
            return
        registry = self._classic_object_registry or ObjectRegistry24268.attach(pm)
        self._classic_object_registry = registry
        for name, (wrapper, data) in read_unit_components(pm, registry, owner, self.COMPONENT_NAMES).items():
            yield name, wrapper, data


    def _components_from_unit_object(
        self,
        pm: ProcessMemory,
        owner: int,
    ) -> dict[str, tuple[int, int]]:
        identity = self._owner_component_identity(pm, owner)
        if identity is None:
            return {}
        _owner, _handle, unit = identity

        components: dict[str, tuple[int, int]] = {}
        for name, offset in self.UNIT_COMPONENT_DATA_OFFSETS.items():
            try:
                data = pm.read_u64(unit + offset)
                data_vtable = pm.read_u64(data) if self._sane_heap_ptr(data) else 0
            except OSError:
                continue
            if self._looks_like_vtable(data_vtable):
                components[name] = (0, data)
        return components


    def _unit_component_layout_matches_process(self, pm: ProcessMemory) -> bool:
        if self._unit_component_layout_confirmed:
            return True
        found_names: set[str] = set()
        for owner in self._unit_owner_index.values():
            direct = self._components_from_unit_object(pm, owner)
            if not direct:
                continue
            wrappers = {
                name: (wrapper, data)
                for name, wrapper, data in self._iter_owner_component_wrappers(pm, owner)
            }
            for name, (_wrapper, data) in direct.items():
                if wrappers.get(name, (0, 0))[1] == data:
                    found_names.add(name)
            if len(found_names) >= 2:
                self._unit_component_layout_confirmed = True
                return True
        return False


    def _owner_component_identity(
        self,
        pm: ProcessMemory,
        owner: int,
    ) -> tuple[int, int, int] | None:
        try:
            if pm.read_u64(owner + 0x18) != self.UNIT_OWNER_TAG:
                return None
            handle = pm.read_u64(owner + 0x20)
            unit = pm.read_u64(owner + 0x90)
            if not self._sane_heap_ptr(unit) or pm.read_u64(unit + 0x18) != handle:
                return None
        except OSError:
            return None
        return owner, handle, unit
