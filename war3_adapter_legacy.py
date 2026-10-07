"""Bundled compatibility memory parsers and code-shape strategies.

These functions accept the existing host as an explicit dependency. They do
not choose a transport or load code from imported profiles. All game layouts
come from the active profile; orchestration remains in the feature services.
"""
from __future__ import annotations

class LegacyAdapterMethods:
    def _validated_owner_components(
        self,
        pm: ProcessMemory,
        owner: int,
        components: dict[str, tuple[int, int]],
    ) -> dict[str, tuple[int, int]]:
        from war3_game_profile import current_profile
        _al = current_profile().section("layouts")
        valid: dict[str, tuple[int, int]] = {}
        unit_components = self._components_from_unit_object(pm, owner)
        for name, (wrapper, data) in components.items():
            if not wrapper:
                if unit_components.get(name) == (0, data):
                    valid[name] = (wrapper, data)
                continue
            try:
                vtable = pm.read_u64(wrapper)
                tag = pm.read_u64(wrapper + _al["component_list"]["tag"])
                wrapper_owner = pm.read_u64(wrapper + _al["component_list"]["owner"])
                wrapper_data = pm.read_u64(wrapper + _al["component_list"]["data"])
                data_vtable = pm.read_u64(data)
            except OSError:
                continue
            if (
                self.COMPONENT_NAMES.get(tag) == name
                and wrapper_owner == owner
                and wrapper_data == data
                and self._looks_like_vtable(vtable)
                and self._looks_like_vtable(data_vtable)
            ):
                valid[name] = (wrapper, data)
        return valid


    def _scan_component_index(
        self,
        pm: ProcessMemory,
    ) -> dict[int, dict[str, tuple[int, int]]]:
        from war3_game_profile import current_profile
        _al = current_profile().section("layouts")
        components_by_owner: dict[int, dict[str, tuple[int, int]]] = {}
        patterns = tuple(
            (struct.pack("<Q", tag), tag, name)
            for tag, name in self.COMPONENT_NAMES.items()
        )
        tail_len = 7
        for region in pm.regions():
            if region.typ != MEM_PRIVATE or region.size > 16 * 1024 * 1024:
                continue
            offset = 0
            tail = b""
            while offset < region.size:
                size = min(4 * 1024 * 1024, region.size - offset)
                try:
                    block = tail + pm.read(region.base + offset, size)
                except OSError:
                    offset += size
                    tail = b""
                    continue
                block_base = region.base + offset - len(tail)
                for pattern, expected_tag, name in patterns:
                    search = 0
                    while True:
                        index = block.find(pattern, search)
                        if index < 0:
                            break
                        search = index + 1
                        tag_address = block_base + index
                        if tag_address < region.base:
                            continue
                        wrapper = tag_address - _al["component_list"]["tag"]
                        try:
                            vtable = pm.read_u64(wrapper)
                            tag = pm.read_u64(wrapper + _al["component_list"]["tag"])
                            owner = pm.read_u64(wrapper + _al["component_list"]["owner"])
                            data = pm.read_u64(wrapper + _al["component_list"]["data"])
                        except OSError:
                            continue
                        if tag != expected_tag or not self._sane_heap_ptr(owner):
                            continue
                        if not self._looks_like_vtable(vtable) or not self._sane_heap_ptr(data):
                            continue
                        try:
                            data_vtable = pm.read_u64(data)
                        except OSError:
                            continue
                        if not self._looks_like_vtable(data_vtable):
                            continue
                        components_by_owner.setdefault(owner, {}).setdefault(name, (wrapper, data))
                tail = block[-tail_len:]
                offset += size
        return components_by_owner


    def _scan_component_index_win10(
        self,
        pm: ProcessMemory,
    ) -> dict[int, dict[str, tuple[int, int]]]:
        from war3_game_profile import current_profile
        _al = current_profile().section("layouts")
        components_by_owner = War3Trainer._scan_component_index(self, pm)
        if components_by_owner:
            return components_by_owner

        pm.regions(force_refresh=True)
        patterns = tuple(
            (struct.pack("<Q", tag), tag, name)
            for tag, name in self.COMPONENT_NAMES.items()
        )
        for region in pm.regions():
            if region.typ != MEM_PRIVATE:
                continue
            tail = b""
            previous_end = 0
            for block_address, block in self._iter_readable_blocks_win10(
                pm,
                region.base,
                region.size,
            ):
                if previous_end != block_address:
                    tail = b""
                data = tail + block
                data_base = block_address - len(tail)
                for pattern, expected_tag, name in patterns:
                    search = 0
                    while True:
                        index = data.find(pattern, search)
                        if index < 0:
                            break
                        search = index + 1
                        tag_address = data_base + index
                        if tag_address < region.base:
                            continue
                        wrapper = tag_address - _al["component_list"]["tag"]
                        try:
                            vtable = pm.read_u64(wrapper)
                            tag = pm.read_u64(wrapper + _al["component_list"]["tag"])
                            owner = pm.read_u64(wrapper + _al["component_list"]["owner"])
                            component_data = pm.read_u64(wrapper + _al["component_list"]["data"])
                        except OSError:
                            continue
                        if tag != expected_tag or not self._sane_heap_ptr(owner):
                            continue
                        if (
                            not self._looks_like_vtable(vtable)
                            or not self._sane_heap_ptr(component_data)
                        ):
                            continue
                        try:
                            data_vtable = pm.read_u64(component_data)
                        except OSError:
                            continue
                        if not self._looks_like_vtable(data_vtable):
                            continue
                        components_by_owner.setdefault(owner, {}).setdefault(
                            name,
                            (wrapper, component_data),
                        )
                tail = data[-7:]
                previous_end = block_address + len(block)
        return components_by_owner


    def _near_ability_instances_from_candidate(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        component_rawcodes: set[int],
    ) -> tuple[list[AbilityInstance], set[int]]:
        from war3_game_profile import current_profile
        _al = current_profile().section("layouts")
        start = candidate.owner_address - self.ABILITY_WRAPPER_SCAN_BACK
        end = candidate.owner_address + self.ABILITY_WRAPPER_SCAN_FORWARD
        instances: list[AbilityInstance] = []
        seen_wrappers: set[int] = set()
        for region in pm.regions():
            region_start = max(start, region.base)
            region_end = min(end, region.base + region.size)
            if region_end - region_start < 0x98:
                continue
            try:
                data = pm.read(region_start, region_end - region_start)
            except OSError:
                continue
            first = (8 - ((region_start - candidate.owner_address) & 7)) & 7
            for offset in range(first, len(data) - (_al["component_list"]["data"] + 7), 8):
                wrapper = region_start + offset
                try:
                    vtable = struct.unpack_from("<Q", data, offset)[0]
                    tag = struct.unpack_from("<Q", data, offset + _al["component_list"]["tag"])[0]
                    owner = struct.unpack_from("<Q", data, offset + _al["component_list"]["owner"])[0]
                    ability_data = struct.unpack_from("<Q", data, offset + _al["component_list"]["data"])[0]
                except struct.error:
                    continue
                if owner != candidate.owner_address:
                    continue
                if not self._looks_like_vtable(vtable) or not self._sane_heap_ptr(ability_data):
                    continue
                class_rawcode = (tag >> 32) & 0xFFFFFFFF
                if class_rawcode in component_rawcodes or not self._looks_like_rawcode(class_rawcode):
                    continue
                instance = self._ability_instance_from_wrapper(pm, candidate, wrapper, component_rawcodes)
                if instance is None:
                    continue
                seen_wrappers.add(wrapper)
                instances.append(instance)
        return instances, seen_wrappers


    def _item_objects_from_handles(
        self,
        pm: ProcessMemory,
        handles: Iterable[int],
        owner: int = 0,
    ) -> dict[int, int]:
        from war3_game_profile import current_profile
        _al = current_profile().section("layouts")
        from war3_game_profile import current_profile
        adapter = current_profile().adapter.items
        item_layout = adapter.layout
        component_layout = adapter.component_layout
        wanted = {
            int(handle)
            for handle in handles
            if int(handle) and int(handle) != 0xFFFFFFFFFFFFFFFF
        }
        if not wanted:
            return {}
        found: dict[int, int] = {}
        session = getattr(self,"_game_session",None)
        if session is not None:
            from war3_game_session import FullHandle
            registry = self._classic_object_registry
            if registry is None:raise RuntimeError("物品解析会话尚未完成校验")
            for handle in wanted:
                try:
                    ref=session.bind_item(pm,registry,FullHandle(handle))
                    found[handle]=session.resolve(pm,registry,ref)
                except (OSError,RuntimeError,ValueError):continue
            return found
        # 3.0 inventory entries contain the full object handle. Resolve it
        # through the verified engine registry before considering any legacy
        # owner-local or process-region search.
        registry = getattr(self, "_classic_object_registry", None)
        if registry is not None:
            for handle in tuple(wanted):
                try:
                    owner_address = registry.resolve_handle(pm, handle)
                    if (
                        pm.read_u64(owner_address + component_layout["tag"]) == self.ITEM_OWNER_TAG
                        and pm.read_u64(owner_address + component_layout["handle"]) == handle
                    ):
                        item = pm.read_u64(owner_address + component_layout["data"])
                        if (
                            self._sane_heap_ptr(item)
                            and self._looks_like_vtable(pm.read_u64(item))
                            and pm.read_u64(item + item_layout["full_handle"]) == handle
                            and self._looks_like_item_rawcode(pm.read_u32(item + item_layout["rawcode"]))
                            and pm.read_u32(item + item_layout["rawcode"]) == pm.read_u32(item + item_layout["rawcode_mirror"])
                        ):
                            found[handle] = item
                            self._item_object_cache[handle] = item
                            wanted.remove(handle)
                except (OSError, RuntimeError):
                    continue
            # A verified 3.0 registry is authoritative. Falling through to
            # legacy region scans would reintroduce stale-handle ambiguity.
            return found
        if not wanted:
            return found
        for handle in list(wanted):
            item = self._item_object_cache.get(handle, 0)
            if not item:
                continue
            try:
                if self._looks_like_vtable(pm.read_u64(item)) and pm.read_u64(item + item_layout["full_handle"]) == handle:
                    found[handle] = item
                else:
                    self._item_object_cache.pop(handle, None)
            except OSError:
                self._item_object_cache.pop(handle, None)
        missing = wanted.difference(found)
        if not missing:
            return found
        if owner:
            start = owner - _al["item"]["owner_scan_radius"]
            end = owner + _al["item"]["owner_scan_radius"]
            for region in pm.regions():
                if not missing:
                    break
                region_start = max(start, region.base)
                region_end = min(end, region.base + region.size)
                if region_end - region_start < 0x98:
                    continue
                try:
                    data = pm.read(region_start, region_end - region_start)
                except OSError:
                    continue
                first = (8 - ((region_start - owner) & 7)) & 7
                for offset in range(first, len(data) - (_al["component_list"]["data"] + 7), 8):
                    if not missing:
                        break
                    try:
                        tag = struct.unpack_from("<Q", data, offset + component_layout["tag"])[0]
                        handle = struct.unpack_from("<Q", data, offset + component_layout["handle"])[0]
                        item = struct.unpack_from("<Q", data, offset + component_layout["data"])[0]
                    except struct.error:
                        continue
                    if tag != self.ITEM_OWNER_TAG or handle not in missing:
                        continue
                    try:
                        if (
                            self._sane_heap_ptr(item)
                            and self._looks_like_vtable(pm.read_u64(item))
                            and pm.read_u64(item + item_layout["full_handle"]) == handle
                            and self._looks_like_rawcode(pm.read_u32(item + item_layout["rawcode"]))
                            and pm.read_u32(item + item_layout["rawcode"]) == pm.read_u32(item + item_layout["rawcode_mirror"])
                        ):
                            found[handle] = item
                            self._item_object_cache[handle] = item
                            missing.remove(handle)
                    except OSError:
                        continue
        if not missing:
            return found
        patterns = {struct.pack("<Q", handle): handle for handle in missing}
        tail_len = 7
        for region in pm.regions():
            if len(found) == len(wanted):
                break
            if region.typ != MEM_PRIVATE or region.size > 1024 * 1024:
                continue
            offset = 0
            tail = b""
            while offset < region.size and len(found) < len(wanted):
                size = min(4 * 1024 * 1024, region.size - offset)
                try:
                    data = tail + pm.read(region.base + offset, size)
                except OSError:
                    offset += size
                    tail = b""
                    continue
                base = region.base + offset - len(tail)
                for pattern, handle in patterns.items():
                    if handle in found:
                        continue
                    start = 0
                    while True:
                        idx = data.find(pattern, start)
                        if idx < 0:
                            break
                        address = base + idx
                        if address >= region.base:
                            item = address - component_layout["tag"]
                            try:
                                if (
                                    self._looks_like_vtable(pm.read_u64(item))
                                    and pm.read_u64(item + item_layout["full_handle"]) == handle
                                    and self._looks_like_rawcode(pm.read_u32(item + item_layout["rawcode"]))
                                    and pm.read_u32(item + item_layout["rawcode"]) == pm.read_u32(item + item_layout["rawcode_mirror"])
                                ):
                                    found[handle] = item
                                    self._item_object_cache[handle] = item
                                    break
                            except OSError:
                                pass
                        start = idx + 1
                tail = data[-tail_len:]
                offset += size
        return found


    def _find_ability_runtime_template(
        self,
        pm: ProcessMemory,
        rawcode: int,
        *,
        excluded_wrappers: set[int] | None = None,
        excluded_data: set[int] | None = None,
    ) -> AbilityInstance | None:
        from war3_game_profile import current_profile
        _al = current_profile().section("layouts")
        excluded_wrappers = excluded_wrappers or set()
        excluded_data = excluded_data or set()
        component_rawcodes = {tag >> 32 for tag in self.COMPONENT_TAGS.values()}
        seen_data: set[int] = set()
        seen_wrappers: set[int] = set()
        rawcode_pattern = struct.pack("<I", rawcode & 0xFFFFFFFF)
        for rawcode_address in pm.scan_bytes_private(rawcode_pattern, max_region_size=8 * 1024 * 1024):
            data = rawcode_address - _al["ability"]["rawcode"]
            if data in seen_data or data in excluded_data:
                continue
            seen_data.add(data)
            try:
                data_vtable = pm.read_u64(data)
                unit = pm.read_u64(data + _al["ability"]["unit_owner"])
                data_rawcode = pm.read_u32(data + _al["ability"]["rawcode"])
                mirror_rawcode = pm.read_u32(data + _al["ability"]["mirror_rawcode"])
                data_cache_pointer = pm.read_u64(data + _al["ability"]["data_cache"])
            except OSError:
                continue
            if data_rawcode != rawcode or mirror_rawcode != rawcode:
                continue
            if not self._looks_like_vtable(data_vtable) or not self._sane_heap_ptr(unit):
                continue
            for data_ref in pm.scan_bytes_private(struct.pack("<Q", data), max_region_size=8 * 1024 * 1024):
                wrapper = data_ref - _al["component_list"]["data"]
                if wrapper in seen_wrappers or wrapper in excluded_wrappers:
                    continue
                seen_wrappers.add(wrapper)
                try:
                    wrapper_vtable = pm.read_u64(wrapper)
                    tag = pm.read_u64(wrapper + _al["component_list"]["tag"])
                    owner = pm.read_u64(wrapper + _al["component_list"]["owner"])
                    wrapper_data = pm.read_u64(wrapper + _al["component_list"]["data"])
                    handle = pm.read_u64(wrapper + _al["component_list"]["handle"])
                except OSError:
                    continue
                if wrapper_data != data:
                    continue
                if not self._looks_like_vtable(wrapper_vtable) or not self._sane_heap_ptr(owner):
                    continue
                source_candidate = self._ability_template_source_candidate(pm, owner, unit)
                if source_candidate is None:
                    continue
                if self._find_engine_ability_data(pm, source_candidate, rawcode) != data:
                    continue
                class_rawcode = (tag >> 32) & 0xFFFFFFFF
                if class_rawcode in component_rawcodes or not self._looks_like_rawcode(class_rawcode):
                    continue
                return AbilityInstance(
                    slot=0,
                    wrapper_address=wrapper,
                    data_address=data,
                    wrapper_vtable=wrapper_vtable,
                    data_vtable=data_vtable,
                    wrapper_tag_address=wrapper + _al["component_list"]["tag"],
                    wrapper_tag=tag,
                    handle=handle,
                    class_rawcode=class_rawcode,
                    rawcode=rawcode,
                    rawcode_address=data + _al["ability"]["rawcode"],
                    mirror_rawcode_address=data + _al["ability"]["mirror_rawcode"],
                    data_cache_address=data + _al["ability"]["data_cache"],
                    data_cache_pointer=data_cache_pointer if self._sane_heap_ptr(data_cache_pointer) else 0,
                )
        return None


    def _iter_owner_property_list(self, pm: ProcessMemory, owner: int) -> Iterable[int]:
        from war3_game_profile import current_profile
        _al = current_profile().section("layouts")
        for list_offset, size_offset in ((_al["property"]["primary_list"], _al["property"]["primary_size"]), (_al["property"]["alternate_list"], _al["property"]["alternate_size"])):
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


    def _owner_properties(self, pm: ProcessMemory, owner: int) -> dict[int, int]:
        from war3_game_profile import current_profile
        _al = current_profile().section("layouts")
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
                tag = pm.read_u64(prop + _al["property"]["tag"])
                if pm.read_u64(prop + _al["property"]["owner"]) != owner:
                    continue
                if tag == self.PROP_TAG:
                    prop_kind = (pm.read_u64(prop + _al["property"]["kind_container"]) >> 32) & 0xFFFFFFFF
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
        from war3_game_profile import current_profile
        _al = current_profile().section("layouts")
        hp_prop = self._property_from_owner(pm, owner, 1)
        if hp_prop is None:
            self._last_selection_candidate_failure = {"stage": "hp_missing", "owner": owner}
            return None
        hp_current_address = hp_prop + self.SELECTED_HP_VALUE_OFFSET
        hp_regen_address = hp_prop + _al["property"]["regen"]
        hp_max_address = hp_prop + _al["property"]["maximum"]
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
            candidate_max = mp_prop + _al["property"]["maximum"]
            try:
                mp_current = pm.read_f32(candidate_current)
                mp_limit = pm.read_f32(candidate_max)
            except OSError:
                mp_current = math.nan
                mp_limit = math.nan
            if self._valid_current_limit(mp_current, mp_limit):
                mp_current_address = candidate_current
                mp_regen_address = mp_prop + _al["property"]["regen"]
                mp_max_address = candidate_max

        suffix = f" owner=0x{owner:x} hp_kind=1"
        if mp_current_address:
            suffix += " mp_kind=2"
        else:
            suffix += " mp_kind=missing"
        position_property = self._position_property_from_owner(pm, owner) or 0
        x_address = position_property + _al["property"]["position_x"] if position_property else 0
        y_address = position_property + _al["property"]["position_y"] if position_property else 0
        if position_property:
            suffix += " pos=prop^ucp"
        unit_address = self._unit_object_from_owner(pm, owner, handle)
        unit_type_id = 0
        if unit_address:
            suffix += f" unit=0x{unit_address:x}"
            try:
                unit_type_id = pm.read_u32(unit_address + _al["unit"]["rawcode"])
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
        from war3_game_profile import current_profile
        _al = current_profile().section("layouts")
        index: dict[int, int] = {}
        for tag_address in tag_addresses:
            owner = tag_address - _al["component_list"]["tag"]
            try:
                vtable = pm.read_u64(owner)
                handle = pm.read_u64(owner + _al["component_list"]["handle"])
                list_address = pm.read_u64(owner + _al["property"]["primary_list"])
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


    def _owner_for_handle(self, pm: ProcessMemory, handle: int) -> int | None:
        from war3_game_profile import current_profile
        _al = current_profile().section("layouts")
        index = self._unit_owner_index
        owner = index.get(handle)
        if owner is not None:
            try:
                if pm.read_u64(owner + _al["component_list"]["handle"]) == handle and self._property_from_owner(pm, owner, 1):
                    return owner
            except OSError:
                pass
        index = self._build_unit_owner_index(pm)
        return index.get(handle)


    def _owner_for_unit_pointer(self, pm: ProcessMemory, unit: int, handle: int) -> int | None:
        from war3_game_profile import current_profile
        _al = current_profile().section("layouts")
        if not self._sane_heap_ptr(unit) or not self._looks_like_unit_handle(handle):
            return None

        indexed = self._unit_owner_index.get(handle)
        if indexed is not None:
            try:
                if pm.read_u64(indexed + _al["component_list"]["handle"]) == handle and pm.read_u64(indexed + _al["component_list"]["data"]) == unit:
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
                owner = region.base + hit - _al["component_list"]["data"]
                try:
                    if (
                        self._looks_like_vtable(pm.read_u64(owner))
                        and pm.read_u64(owner + _al["component_list"]["tag"]) == self.UNIT_OWNER_TAG
                        and pm.read_u64(owner + _al["component_list"]["handle"]) == handle
                        and pm.read_u64(owner + _al["component_list"]["data"]) == unit
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
        from war3_game_profile import current_profile
        _al = current_profile().section("layouts")
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
                    candidate_owner = block_address + hit - _al["component_list"]["data"]
                    try:
                        if (
                            self._looks_like_vtable(pm.read_u64(candidate_owner))
                            and pm.read_u64(candidate_owner + _al["component_list"]["tag"]) == self.UNIT_OWNER_TAG
                            and pm.read_u64(candidate_owner + _al["component_list"]["handle"]) == handle
                            and pm.read_u64(candidate_owner + _al["component_list"]["data"]) == unit
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
            if pm.read_u64(owner + _al["component_list"]["data"]) != unit:
                return None
        except OSError:
            return None
        return owner


    def _score_selected_handle_address(self, pm: ProcessMemory, address: int, handle: int, owner: int) -> int:
        from war3_game_profile import current_profile
        _al = current_profile().section("layouts")
        if owner <= address < owner + _al["selection"]["owner_span"]:
            return -1000
        score = 0
        if 0x8000000000 <= address <= 0xFFFFFFFFFF:
            score += 120
        try:
            if pm.read_u64(address + _al["selection"]["score_handle_a"]) == handle:
                score += 35
            if pm.read_u64(address + _al["selection"]["score_handle_b"]) == handle:
                score += 35
        except OSError:
            pass
        if address % 4 == 0:
            score += 5
        return score


    def _selection_manager_unit_slots(
        self,
        pm: ProcessMemory,
        list_base: int,
    ) -> list[tuple[int, int]]:
        from war3_game_profile import current_profile
        _al = current_profile().section("layouts")
        try:
            root = pm.read_u64(list_base + _al["selection"]["manager_list"])
            count = pm.read_u32(list_base + _al["selection"]["manager_count"])
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
                next_node = pm.read_u64(node + _al["selection"]["node_next"])
                unit = pm.read_u64(node + _al["selection"]["node_unit"])
            except OSError:
                break
            if self._sane_heap_ptr(unit):
                out.append((unit, node + _al["selection"]["node_unit"]))
            node = next_node
        return out


    def _read_selected_unit_type_id(self, pm: ProcessMemory, candidate: UnitCandidate) -> int:
        from war3_game_profile import current_profile
        _al = current_profile().section("layouts")
        native = self._native_snapshot_for_candidate(candidate)
        if native is not None:
            return native.type_id
        if not candidate.unit_address:
            return 0
        primary = pm.read_u32(candidate.unit_address + _al["unit"]["rawcode"])
        mirror = pm.read_u32(candidate.unit_address + _al["unit"]["rawcode_mirror"])
        if primary != mirror or not self._looks_like_item_rawcode(primary):
            return 0
        return primary


    def _iter_owner_component_wrappers(
        self,
        pm: ProcessMemory,
        owner: int,
    ) -> Iterable[tuple[str, int, int]]:
        from war3_game_profile import current_profile
        _al = current_profile().section("layouts")
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
                    wrapper = region_start + index - _al["component_list"]["tag"]
                    if wrapper < start or wrapper >= end:
                        continue
                    try:
                        vtable = pm.read_u64(wrapper)
                        wrapper_owner = pm.read_u64(wrapper + _al["component_list"]["owner"])
                        data = pm.read_u64(wrapper + _al["component_list"]["data"])
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
            if name=='attack' and getattr(self,'_game_session',None) is not None:
                # The shared method consumes the already verified, per-build
                # native attack-component offset rather than the legacy layout.
                offset=self._game_session.profile.section('bridge_layout')['unit_attack']
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
        from war3_game_profile import current_profile
        _al = current_profile().section("layouts")
        try:
            if pm.read_u64(owner + _al["component_list"]["tag"]) != self.UNIT_OWNER_TAG:
                return None
            handle = pm.read_u64(owner + _al["component_list"]["handle"])
            unit = pm.read_u64(owner + _al["component_list"]["data"])
            if not self._sane_heap_ptr(unit) or pm.read_u64(unit + _al["unit"]["full_handle"]) != handle:
                return None
        except OSError:
            return None
        return owner, handle, unit


    def _iter_resource_properties(
        self,
        pm: ProcessMemory,
        tag_addresses: Iterable[int] | None = None,
    ) -> Iterable[ResourceProperty]:
        from war3_game_profile import current_profile
        _al = current_profile().section("layouts")
        if tag_addresses is None:
            tag = struct.pack("<Q", self.RESOURCE_PROP_TAG)
            tag_addresses = pm.scan_bytes_private(tag, max_region_size=1024 * 1024)
        for tag_address in tag_addresses:
            base = tag_address - _al["legacy_resource"]["tag"]
            try:
                value64 = pm.read_u64(base)
                kind_a = pm.read_i32(base + _al["legacy_resource"]["kind_a"])
                kind_b = pm.read_i32(base + _al["legacy_resource"]["kind_b"])
                owner_key = pm.read_u64(base + _al["legacy_resource"]["owner_key"])
            except OSError:
                continue
            if kind_a != kind_b:
                continue
            if not 0 <= kind_a <= 0x1000:
                continue
            if value64 > 0x7FFFFFFF:
                continue
            if not self._sane_heap_ptr(owner_key):
                owner_key = 0
            yield ResourceProperty(kind_a, base, int(value64), owner_key)


    def _ability_instance_from_data_for_candidate(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        data_address: int,
        rawcode: int,
    ) -> AbilityInstance | None:
        from war3_game_profile import current_profile
        _al = current_profile().section("layouts")
        if self._native_snapshot_for_candidate(candidate) is not None:
            instance, _, _ = self._native_ability_metadata(candidate, rawcode)
            return instance if instance.data_address == data_address else None
        if self._ability_data_instance_for_candidate(
            pm,
            candidate,
            data_address,
            rawcode,
        ) is None:
            return None
        component_rawcodes = {tag >> 32 for tag in self.COMPONENT_TAGS.values()}
        cache_key = (candidate.handle, data_address, rawcode)
        cached = self._ability_instance_by_data.get(cache_key)
        if cached is not None:
            refreshed = self._ability_instance_from_wrapper(
                pm,
                candidate,
                cached.wrapper_address,
                component_rawcodes,
            )
            if (
                refreshed is not None
                and refreshed.data_address == data_address
                and refreshed.rawcode == rawcode
            ):
                return replace(refreshed, slot=cached.slot)
            self._ability_instance_by_data.pop(cache_key, None)

        data_pattern = struct.pack("<Q", data_address)
        near_start = max(0, candidate.owner_address - 0x05000000)
        near_end = candidate.owner_address + 0x00800000
        near_refs = self._scan_bytes_private_between(pm, data_pattern, near_start, near_end)
        if not near_refs and self._persistent_native_initialized:
            # A persistent native unit must never widen an instance lookup
            # after the bounded owner-local search fails.
            return None
        all_refs = near_refs or pm.scan_bytes_private(data_pattern, max_region_size=8 * 1024 * 1024)
        for data_ref in all_refs:
            wrapper = data_ref - _al["component_list"]["data"]
            instance = self._ability_instance_from_wrapper(pm, candidate, wrapper, component_rawcodes)
            if instance is None:
                continue
            if instance.data_address == data_address and instance.rawcode == rawcode:
                self._ability_instance_by_data[cache_key] = instance
                return instance
        return None


    def _discover_native_hero_int_internals(self, pm: ProcessMemory) -> tuple[int, int]:
        if self._native_hero_int_set_address and self._native_hero_int_get_address:
            regions = pm.regions()
            if (
                self._is_executable_image_address(regions, self._native_hero_int_set_address)
                and self._is_executable_image_address(regions, self._native_hero_int_get_address)
            ):
                return self._native_hero_int_set_address, self._native_hero_int_get_address

        wanted = {"SetHeroInt", "GetHeroInt"}
        handlers = {
            name: self._native_handlers[name]
            for name in wanted
            if name in self._native_handlers
        }
        if set(handlers) != wanted:
            regions = pm.regions()
            table_region = self._find_native_table_region(pm, regions)
            nearby_regions = [
                region
                for region in regions
                if region.typ == MEM_PRIVATE
                and region.size <= 0x40000
                and region.base < 0x700000000000
                and abs(region.base - table_region.base) <= 0x200000
            ]
            nearby_regions.sort(key=lambda region: (abs(region.base - table_region.base), -region.base))
            for region in nearby_regions:
                missing = wanted.difference(handlers)
                if not missing:
                    break
                try:
                    blob = self._native_table_blob_for_region(pm, region)
                except OSError:
                    continue
                handlers.update(
                    self._find_native_handlers_in_table_blob(
                        pm,
                        regions,
                        blob,
                        region.base,
                        missing,
                    )
                )
            self._native_handlers.update(handlers)
        if set(handlers) != wanted:
            handlers = self._discover_native_handlers(pm, wanted)
        set_calls = self._rel32_calls_in_function(pm, handlers["SetHeroInt"].handler_address, max_bytes=0x80)
        get_jumps = self._rel32_jumps_in_function(pm, handlers["GetHeroInt"].handler_address, max_bytes=0x80)
        if len(set_calls) < 3:
            raise RuntimeError("未能从 SetHeroInt handler 定位内部智力写入函数")
        if not get_jumps:
            raise RuntimeError("未能从 GetHeroInt handler 定位内部智力读取函数")

        set_address = set_calls[-1]
        get_address = get_jumps[-1]
        regions = pm.regions()
        if not self._is_executable_image_address(regions, set_address):
            raise RuntimeError(f"内部智力写入函数地址不可执行：0x{set_address:x}")
        if not self._is_executable_image_address(regions, get_address):
            raise RuntimeError(f"内部智力读取函数地址不可执行：0x{get_address:x}")
        self._native_hero_int_set_address = set_address
        self._native_hero_int_get_address = get_address
        return set_address, get_address


    def _discover_native_ability_internals(self, pm: ProcessMemory) -> NativeAbilityInternals:
        handlers = self._discover_native_handlers(pm, ("UnitAddAbility", "UnitRemoveAbility"))
        add_handler = handlers["UnitAddAbility"].handler_address
        remove_handler = handlers["UnitRemoveAbility"].handler_address
        add_calls = self._rel32_calls_in_function(pm, add_handler)
        remove_calls = self._rel32_calls_in_function(pm, remove_handler)
        if len(add_calls) < 6:
            raise RuntimeError(
                f"UnitAddAbility 内部调用数量异常：{len(add_calls)}，不能安全创建技能"
            )
        if len(remove_calls) < 4:
            raise RuntimeError(
                f"UnitRemoveAbility 内部调用数量异常：{len(remove_calls)}，不能安全删除技能"
            )
        internals = NativeAbilityInternals(
            find_address=add_calls[1],
            begin_address=add_calls[2],
            add_address=add_calls[3],
            end_address=add_calls[4],
            refresh_address=add_calls[5],
            remove_address=remove_calls[2],
        )
        remove_find = remove_calls[1]
        if remove_find != internals.find_address:
            raise RuntimeError("UnitAddAbility/UnitRemoveAbility 使用的内部查找函数不一致")
        if remove_calls[3] != internals.refresh_address:
            raise RuntimeError("UnitAddAbility/UnitRemoveAbility 使用的刷新函数不一致")
        regions = pm.regions()
        for name, address in (
            ("find", internals.find_address),
            ("begin", internals.begin_address),
            ("add", internals.add_address),
            ("end", internals.end_address),
            ("refresh", internals.refresh_address),
            ("remove", internals.remove_address),
        ):
            if not self._is_executable_image_address(regions, address):
                raise RuntimeError(f"内部 ability 函数 {name} 地址不可执行：0x{address:x}")
        return internals


    def _inventory_native_internals(self, pm, handlers):
        item_in_slot_calls = self._rel32_calls_in_function(
            pm,
            handlers["UnitItemInSlot"].handler_address,
            max_bytes=0x80,
        )
        add_item_calls = self._rel32_calls_in_function(
            pm,
            handlers["UnitAddItemToSlotById"].handler_address,
            max_bytes=0x180,
        )
        add_by_id_calls = self._rel32_calls_in_function(
            pm,
            handlers["UnitAddItemById"].handler_address,
            max_bytes=0x120,
        )
        remove_item_calls = self._rel32_calls_in_function(
            pm,
            handlers["UnitRemoveItem"].handler_address,
            max_bytes=0x80,
        )
        if len(item_in_slot_calls) < 3 or len(add_item_calls) != 8 or len(add_by_id_calls) < 8 or len(remove_item_calls) < 4:
            raise RuntimeError("未能从物品 native handler 中定位内部物品栏函数")
        item_in_slot_internal = item_in_slot_calls[2]
        add_exact_slot_internal = add_item_calls[-1]
        create_item_internal = add_by_id_calls[2]
        if add_item_calls[2] != create_item_internal:
            raise RuntimeError("物品创建函数交叉校验失败")
        remove_item_internal = remove_item_calls[3]
        regions = pm.regions()
        for name, address in (
            ("item_in_slot", item_in_slot_internal),
            ("create_item", create_item_internal),
            ("add_exact_slot", add_exact_slot_internal),
            ("remove_item", remove_item_internal),
        ):
            if not self._is_executable_image_address(regions, address):
                raise RuntimeError(f"内部物品栏函数 {name} 地址不可执行：0x{address:x}")
        return item_in_slot_internal, create_item_internal, add_exact_slot_internal, remove_item_internal


    def _discover_jass_unit_resolver(self, pm: ProcessMemory) -> int:
        if self._jass_unit_resolver_address:
            if self._is_executable_image_address(pm.regions(), self._jass_unit_resolver_address):
                return self._jass_unit_resolver_address
            self._jass_unit_resolver_address = 0
        add_handler = self._elephant_handlers(pm, ("UnitAddAbility",))["UnitAddAbility"].handler_address
        calls = self._rel32_calls_in_function(pm, add_handler)
        if len(calls) < 2:
            raise RuntimeError("UnitAddAbility 未暴露可验证的单位句柄解析函数")
        resolver = calls[0]
        if not self._is_executable_image_address(pm.regions(), resolver):
            raise RuntimeError("单位句柄解析函数不在游戏可执行代码段")
        self._jass_unit_resolver_address = resolver
        return resolver


    def _discover_jass_unit_resolver_win10(self, pm: ProcessMemory) -> int:
        if self._jass_unit_resolver_address:
            if self._is_executable_image_address(pm.regions(), self._jass_unit_resolver_address):
                return self._jass_unit_resolver_address
            self._jass_unit_resolver_address = 0
        handler = self._discover_native_handlers(pm, ("UnitAddAbility",))["UnitAddAbility"]
        calls = self._rel32_calls_in_function(pm, handler.handler_address)
        if len(calls) < 2:
            raise RuntimeError("备用读取未能从 UnitAddAbility 定位单位句柄解析函数")
        resolver = calls[0]
        if not self._is_executable_image_address(pm.regions(), resolver):
            raise RuntimeError("备用读取的单位句柄解析函数不在游戏可执行代码段")
        self._jass_unit_resolver_address = resolver
        return resolver


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


    def _item_charge_notifier(self, pm, handlers):
        set_charges_handler = handlers["SetItemCharges"].handler_address
        jumps = self._rel32_jumps_in_function(pm, set_charges_handler)
        notify_candidates = {
            target
            for target in jumps
            if jumps.count(target) >= 2
        }
        if len(notify_candidates) != 1:
            raise RuntimeError("未能从 SetItemCharges handler 中唯一定位物品数量通知函数")
        notify_handler = next(iter(notify_candidates))
        return notify_handler
