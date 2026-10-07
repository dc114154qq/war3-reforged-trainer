"""fields compatibility API; host primitives are explicitly bound once at composition."""
from __future__ import annotations
from contextlib import contextmanager

class FieldsFacade:
    def _selected_components(self, pm: ProcessMemory, owner: int) -> dict[str, tuple[int, int]]:
        if not owner:
            return {}
        if uses_indexed_backend(self):
            # Read the live list every time: a valid cached subset can still
            # miss components attached after the previous read.
            return {name: (wrapper, data) for name, wrapper, data in
                    self._iter_indexed_owner_component_wrappers(pm, owner)}
        components: dict[str, tuple[int, int]] = {}
        cache_key = self._owner_component_identity(pm, owner)
        if cache_key is None:
            return {}
        cached = self._selected_components_cache.get(cache_key)
        if cached is not None:
            if cached:
                valid = self._validated_owner_components(pm, owner, cached)
                if len(valid) == len(cached):
                    return dict(valid)
            self._selected_components_cache.pop(cache_key, None)

        direct = self._components_from_unit_object(pm, owner)
        if self._persistent_native_initialized:
            # The persistent native snapshot already validated this unit. The
            # unit object pointers are independently checked by
            # _components_from_unit_object. Never turn a missing direct
            # component into a process-wide index scan on this hot path: that
            # can pair a newly selected unit with an older object.
            self._selected_components_cache[cache_key] = dict(direct)
            return direct
        wrapper_components: dict[str, tuple[int, int]] = {}
        for name, wrapper, data in self._iter_owner_component_wrappers(pm, owner):
            wrapper_components.setdefault(name, (wrapper, data))

        direct_is_fully_verified = bool(direct) and all(
            wrapper_components.get(name, (0, 0))[1] == data
            for name, (_wrapper, data) in direct.items()
        )
        if direct_is_fully_verified and set(wrapper_components) == set(direct):
            components.update(wrapper_components)
            self._selected_components_cache[cache_key] = dict(components)
            return components

        if not direct and not wrapper_components and self._unit_component_layout_matches_process(pm):
            return {}

        if self._component_index_cache is None or (
            owner not in self._component_index_cache
            and owner not in self._component_index_misses
        ):
            self._rebuild_component_index(pm)
            if owner not in self._component_index_cache:
                self._component_index_misses.add(owner)
        indexed_source = self._component_index_cache.get(owner, {})
        indexed = self._validated_owner_components(
            pm,
            owner,
            indexed_source,
        )
        if len(indexed) != len(indexed_source):
            self._rebuild_component_index(pm)
            indexed = self._validated_owner_components(
                pm,
                owner,
                self._component_index_cache.get(owner, {}),
            )
        components.update(indexed)
        if components:
            self._selected_components_cache[cache_key] = dict(components)
        else:
            self._selected_components_cache.pop(cache_key, None)
        return components


    def _validated_owner_components(
        self,
        pm: ProcessMemory,
        owner: int,
        components: dict[str, tuple[int, int]],
    ) -> dict[str, tuple[int, int]]:
        from war3_game_profile import current_profile
        return current_profile().adapter.legacy._validated_owner_components(self, pm, owner, components)


    def _scan_component_index(
        self,
        pm: ProcessMemory,
    ) -> dict[int, dict[str, tuple[int, int]]]:
        from war3_game_profile import current_profile
        return current_profile().adapter.legacy._scan_component_index(self, pm)


    def _scan_component_index_win10(
        self,
        pm: ProcessMemory,
    ) -> dict[int, dict[str, tuple[int, int]]]:
        from war3_game_profile import current_profile
        return current_profile().adapter.legacy._scan_component_index_win10(self, pm)


    def _rebuild_component_index(self, pm: ProcessMemory) -> None:
        self._component_index_cache = self._scan_component_index(pm)
        known_owners = set(self._unit_owner_index.values())
        self._component_index_misses = known_owners.difference(self._component_index_cache)


    def _component_map_for_owners(
        self,
        pm: ProcessMemory,
        owners: set[int],
    ) -> dict[int, dict[str, tuple[int, int]]]:
        components_by_owner: dict[int, dict[str, tuple[int, int]]] = {}
        if not owners:
            return components_by_owner
        if self._component_index_cache is None:
            self._rebuild_component_index(pm)
        for owner in owners:
            components = self._validated_owner_components(
                pm,
                owner,
                self._component_index_cache.get(owner, {}),
            )
            if components:
                components_by_owner[owner] = components
        return components_by_owner


    def _append_unit_field(
        self,
        pm: ProcessMemory,
        fields: list[UnitMemoryField],
        key: str,
        label: str,
        value_type: str,
        address: int,
        category: str,
        writable: bool = True,
        note: str = "",
        extra_writes: tuple[tuple[int, str], ...] = (),
    ) -> None:
        if not address:
            return
        try:
            value = self._read_memory_value(pm, address, value_type)
        except OSError:
            return
        if isinstance(value, float):
            if not math.isfinite(value):
                return
        fields.append(
            UnitMemoryField(
                key=key,
                label=label,
                value_type=value_type,
                value=value,
                address=address,
                category=category,
                write_address=address if writable else 0,
                write_type=value_type if writable else "",
                note=note,
                extra_writes=extra_writes if writable else (),
            )
        )


    def _append_attack_fields(
        self, pm: ProcessMemory, fields: list[UnitMemoryField], key_prefix: str,
        label_prefix: str, data: int, current_24268: bool = False,
        timing_24268: dict | None = None,
    ) -> None:
        from war3_game_profile import current_profile
        return current_profile().adapter.attack.append_fields(
            self, pm, fields, key_prefix, label_prefix, data,
            current_24268, timing_24268, UnitMemoryField,
        )


    @staticmethod
    def _attack_timing_24268_from_memory(pm: ProcessMemory, data: int) -> dict:
        from war3_game_profile import current_profile
        return current_profile().adapter.attack.timing(pm, data)


    @staticmethod
    def _looks_like_rawcode(value: int) -> bool:
        data = struct.pack(">I", value & 0xFFFFFFFF)
        return all(32 <= byte < 127 for byte in data) and any(65 <= byte <= 90 for byte in data)


    @staticmethod
    def _looks_like_item_rawcode(value: int) -> bool:
        data = struct.pack(">I", value & 0xFFFFFFFF)
        return all(
            48 <= byte <= 57 or 65 <= byte <= 90 or 97 <= byte <= 122
            for byte in data
        )


    def _ability_instance_from_wrapper(
        self, pm: ProcessMemory, candidate: UnitCandidate, wrapper: int,
        component_rawcodes: set[int],
    ) -> AbilityInstance | None:
        from war3_game_profile import current_profile
        return current_profile().adapter.abilities.instance(
            self, pm, candidate, wrapper, component_rawcodes, AbilityInstance,
        )


    def _validated_cached_ability_instances(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        key: tuple[int, int, int, bool],
    ) -> list[AbilityInstance] | None:
        cached = self._ability_instances_cache.get(key)
        from war3_game_profile import current_profile
        component_layout = current_profile().section("layouts")["component_list"]
        ability_layout = current_profile().section("layouts")["ability"]
        if cached is None:
            return None
        for instance in cached:
            try:
                if pm.read_u64(instance.wrapper_address + component_layout["owner"]) != candidate.owner_address:
                    return None
                if pm.read_u64(instance.wrapper_address + component_layout["data"]) != instance.data_address:
                    return None
                if pm.read_u64(instance.data_address + ability_layout["unit_owner"]) != candidate.unit_address:
                    return None
                if pm.read_u32(instance.data_address + ability_layout["rawcode"]) != instance.rawcode:
                    return None
                if pm.read_u32(instance.data_address + ability_layout["mirror_rawcode"]) != instance.rawcode:
                    return None
            except OSError:
                return None
        return list(cached)


    def _near_ability_instances_from_candidate(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        component_rawcodes: set[int],
    ) -> tuple[list[AbilityInstance], set[int]]:
        from war3_game_profile import current_profile
        return current_profile().adapter.legacy._near_ability_instances_from_candidate(self, pm, candidate, component_rawcodes)


    def _ability_instances_from_candidate(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        required_rawcodes: set[int] | None = None,
        allow_global_scan: bool = False,
    ) -> list[AbilityInstance]:
        from war3_game_profile import current_profile
        _al = current_profile().section("layouts")
        if not candidate.owner_address or not candidate.unit_address:
            return []
        if uses_indexed_backend(self):
            from war3_unit_components import read_unit_component_nodes
            from war3_object_registry import ObjectRegistry24268
            registry = self._classic_object_registry or ObjectRegistry24268.attach(pm)
            self._classic_object_registry = registry
            component_rawcodes = {tag >> 32 for tag in self.COMPONENT_NAMES}
            instances = []
            for tag, wrapper, full, data in read_unit_component_nodes(pm, registry, candidate.owner_address):
                # The owner list also contains task records (task/tskO/etc.).
                # Ability class tags in this build start with A.
                if tag >> 56 != ord("A") or tag >> 32 in component_rawcodes:
                    continue
                instance = self._ability_instance_from_wrapper(pm, candidate, wrapper, component_rawcodes)
                if instance is None or (instance.handle, instance.data_address) != (full, data):
                    # Task and placeholder ability nodes share the owner list;
                    # only a complete ability identity enters the editable list.
                    continue
                if required_rawcodes is None or instance.rawcode in required_rawcodes:
                    instances.append(replace(instance, slot=len(instances) + 1))
            return instances
        if (self._persistent_native_initialized or candidate.native_snapshot is not None
                or candidate.selection_source == "persistent_native"):
            # Persistent native selection already identifies the live unit.
            # Never widen an ability lookup to a process-wide search for this
            # unit, even when an older caller requested its legacy fallback.
            allow_global_scan = False
            native = self._native_snapshot_for_candidate(candidate)
            if native is not None:
                handlers = self._query_native_table_handlers(
                    ("BlzGetUnitAbilityByIndex", "BlzGetAbilityId", "GetUnitAbilityLevel")
                )
                results = self._run_native_helper_ops(native.handle, (
                    (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0, candidate.unit_address,
                     candidate.handle, candidate.owner_address),
                    (self.NATIVE_HELPER_OP_BOUND_ABILITY_LIST, 0,
                     handlers["BlzGetUnitAbilityByIndex"].handler_address,
                     handlers["BlzGetAbilityId"].handler_address, 0),
                ))
                if len(results) != 2 or any(result.last_error for result in results):
                    raise RuntimeError("DLL 技能枚举返回不完整")
                values = tuple(int(value) for value in results[0].extra_results)
                count = int(results[1].result)
                if count < 0 or count > 4096 or len(values) != count * 10:
                    raise RuntimeError("DLL 技能枚举结果长度异常")
                instances: list[AbilityInstance] = []
                seen_ability_identity: set[tuple[int, int, int]] = set()
                for index in range(count):
                    row = values[index * 10:(index + 1) * 10]
                    ability, data, wrapper, full, tag, wrapper_vtable, data_vtable, rawcode, level, cache = row
                    if (not all(0x10000 <= address < 0x0000800000000000
                                for address in (data, wrapper, wrapper_vtable, data_vtable))
                            or not full
                            or not self._looks_like_rawcode(rawcode)
                            or not self._looks_like_rawcode(tag >> 32)):
                        raise RuntimeError("DLL 技能枚举返回无效对象身份")
                    # Engine ability enumeration includes unit components.
                    # Their presence is valid; only actual skills belong in
                    # the editable ability list, as in the legacy mapper.
                    if tag >> 32 in {value >> 32 for value in self.COMPONENT_TAGS.values()}:
                        continue
                    instance = AbilityInstance(
                        slot=0, wrapper_address=wrapper, data_address=data,
                        wrapper_vtable=wrapper_vtable, data_vtable=data_vtable,
                        wrapper_tag_address=wrapper + _al["component_list"]["tag"], wrapper_tag=tag, handle=full,
                        class_rawcode=tag >> 32, rawcode=rawcode, rawcode_address=data + _al["ability"]["rawcode"],
                        mirror_rawcode_address=data + _al["ability"]["mirror_rawcode"], data_cache_address=data + _al["ability"]["data_cache"],
                        data_cache_pointer=cache if 0x10000 <= cache < 0x0000800000000000 else 0,
                    )
                    identity = (instance.handle, instance.data_address, instance.wrapper_address)
                    if identity in seen_ability_identity:
                        raise RuntimeError("DLL 技能枚举返回重复的能力对象")
                    seen_ability_identity.add(identity)
                    if required_rawcodes is None or rawcode in required_rawcodes:
                        instances.append(instance)
                return [replace(instance, slot=index + 1) for index, instance in enumerate(instances)]
        cache_key = (candidate.handle, candidate.owner_address, candidate.unit_address, bool(allow_global_scan))
        if required_rawcodes is None:
            cached = self._validated_cached_ability_instances(pm, candidate, cache_key)
            if cached is not None:
                return cached
        if allow_global_scan:
            raise RuntimeError("global ability scan is disabled; native object-table enumeration is required")
        component_rawcodes = {tag >> 32 for tag in self.COMPONENT_TAGS.values()}
        instances, seen_wrappers = self._near_ability_instances_from_candidate(pm, candidate, component_rawcodes)
        instances.sort(key=lambda instance: (instance.handle, instance.wrapper_address))
        instances = [
            replace(instance, slot=index + 1)
            for index, instance in enumerate(instances)
        ]
        if required_rawcodes is None:
            self._ability_instances_cache[cache_key] = list(instances)
        return instances


    def _inventory_record_address(
        self, pm: ProcessMemory, candidate: UnitCandidate, inventory_data: int,
    ) -> int:
        from war3_game_profile import current_profile
        adapter = current_profile().adapter.items
        return adapter.inventory_record(
            pm, candidate, inventory_data,
            int(self._coerce_memory_value("rawcode", "AInv")),
            indexed=uses_indexed_backend(self),
        )


    def _item_object_from_handle(self, pm: ProcessMemory, owner: int, handle: int) -> int:
        from war3_game_profile import current_profile
        adapter = current_profile().adapter.items
        return adapter.item_data_near_owner(
            pm, owner, handle, self._sane_heap_ptr, self._looks_like_rawcode, self._looks_like_vtable,
        )


    def _item_objects_from_handles(
        self,
        pm: ProcessMemory,
        handles: Iterable[int],
        owner: int = 0,
    ) -> dict[int, int]:
        from war3_game_profile import current_profile
        return current_profile().adapter.legacy._item_objects_from_handles(self, pm, handles, owner)


    def _native_snapshot_for_candidate(
        self, candidate: UnitCandidate,
    ) -> PersistentNativeUnitSnapshot | None:
        identity = (candidate.handle, candidate.owner_address, candidate.unit_address)
        bound = candidate.native_snapshot
        if bound is not None:
            if identity != (bound.full_handle, bound.owner_address, bound.unit_address):
                raise RuntimeError("当前 native 快照已经失效，请重新读取选中单位")
            return bound
        if candidate.selection_source == "persistent_native":
            # A native candidate must never pick up another read's payload,
            # even when the engine has reused its unit object address.
            raise RuntimeError("当前 native 快照已经失效，请重新读取选中单位")
        return next((item for item in getattr(self, "_last_persistent_native_snapshots", ())
                     if identity == (item.full_handle, item.owner_address, item.unit_address)), None)


    def _native_inventory_items(self, candidate: UnitCandidate) -> list[InventoryItem]:
        native = self._native_snapshot_for_candidate(candidate)
        if native is None:
            raise RuntimeError("Native inventory requires a bound unit snapshot")
        results = self._run_native_helper_ops(native.handle, (
            (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0, candidate.unit_address,
             candidate.handle, candidate.owner_address),
            (self.NATIVE_HELPER_OP_BOUND_INVENTORY, 0, 0, 0, 0),
        ))
        if len(results) != 2 or any(result.last_error for result in results) or results[1].result != 6:
            raise RuntimeError("Incomplete inventory returned by the DLL")
        return self._parse_native_inventory_items(tuple(results[0].extra_results))


    def _parse_native_inventory_items(self, values: tuple[int, ...]) -> list[InventoryItem]:
        if len(values) != 49 or not 0 <= values[0] <= 6:
            raise RuntimeError("Invalid DLL inventory payload length or capacity")
        from war3_game_profile import current_profile
        item_layout = current_profile().adapter.items.layout
        items = []
        seen_handles, seen_full, seen_objects = set(), set(), set()
        for index in range(6):
            handle, full, obj, rawcode, charges, mirror, ability, wrapper = values[1+index*8:9+index*8]
            if not handle:
                if any((full, obj, rawcode, charges, mirror, ability, wrapper)):
                    raise RuntimeError("Empty DLL inventory slot contains item metadata")
            elif (index >= values[0] or not all((full, obj, rawcode, wrapper))
                  or handle in seen_handles or full in seen_full or obj in seen_objects):
                raise RuntimeError("Invalid or duplicate DLL inventory item identity")
            if handle:
                seen_handles.add(handle); seen_full.add(full); seen_objects.add(obj)
            mirror = mirror if self._looks_like_rawcode(mirror) else 0
            ability = ability if self._looks_like_rawcode(ability) else 0
            items.append(InventoryItem(
                slot=index+1, handle=full, handle_address=0, item_address=obj, rawcode=rawcode,
                rawcode_address=obj+item_layout["rawcode"] if obj else 0,
                charges=ctypes.c_int32(charges & 0xFFFFFFFF).value,
                charges_address=obj+item_layout["charges"] if obj else 0,
                mirror_rawcode=mirror, mirror_rawcode_address=obj+item_layout["rawcode_mirror"] if mirror else 0,
                ability_rawcode=ability, ability_rawcode_address=obj+item_layout["ability_rawcode"] if ability else 0,
                native_slot=index < values[0],
            ))
        return items


    def _inventory_items_from_candidate(
        self, pm: ProcessMemory, candidate: UnitCandidate,
        components: dict[str, tuple[int, int]] | None = None,
    ) -> list[InventoryItem]:
        if pm is None and self._native_snapshot_for_candidate(candidate) is None:
            with self._process_memory() as inventory_memory:
                return self._inventory_items_from_candidate(inventory_memory, candidate, components=components)
        native = self._native_snapshot_for_candidate(candidate)
        if native is not None:
            return self._native_inventory_items(candidate)
        from war3_game_profile import current_profile
        adapter = current_profile().adapter.items
        components = components if components is not None else self._selected_components(pm, candidate.owner_address)
        inventory = components.get("inventory")
        if inventory is None:
            return []
        _wrapper, data = inventory
        record = self._inventory_record_address(pm, candidate, data)
        if not record:
            return []
        layout = adapter.inventory_layout
        try:
            slot_array = pm.read_u64(record + layout["slot_array"])
        except OSError:
            return []
        if not self._sane_heap_ptr(slot_array):
            return []
        slot_handles = []
        for index in range(layout["slot_count"]):
            handle_address = slot_array + index * layout["slot_stride"]
            try:
                handle = pm.read_u64(handle_address)
            except OSError:
                handle = 0
            slot_handles.append((index, handle_address, handle))
        item_by_handle = self._item_objects_from_handles(
            pm, (handle for _index, _address, handle in slot_handles), candidate.owner_address,
        )
        items = []
        item_layout = adapter.layout
        for index, handle_address, handle in slot_handles:
            item_address = item_by_handle.get(handle, 0)
            values = {"rawcode": 0, "rawcode_address": 0, "mirror_rawcode": 0,
                      "mirror_rawcode_address": 0, "ability_rawcode": 0,
                      "ability_rawcode_address": 0, "charges": 0, "charges_address": 0}
            if item_address:
                try:
                    values = adapter.fields(pm, item_address, self._looks_like_rawcode)
                except OSError:
                    pass
            items.append(InventoryItem(
                slot=index + 1, handle=handle, handle_address=handle_address,
                item_address=item_address, **values,
            ))
        return items


    def _native_unit_field_memory(self, candidate: UnitCandidate) -> NativeUnitFieldMemory:
        native = self._native_snapshot_for_candidate(candidate)
        if native is None:
            raise RuntimeError("读取 DLL 单位字段需要当前单位的 native 身份")
        results = self._run_native_helper_ops(native.handle, (
            (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0, candidate.unit_address,
             candidate.handle, candidate.owner_address),
            (self.NATIVE_HELPER_OP_BOUND_UNIT_FIELDS, 0, 0, 0, 0),
        ))
        if (len(results) != 2 or any(result.last_error for result in results)
                or results[1].result != 346 or len(results[0].extra_results) != 346):
            raise RuntimeError("DLL 单位字段返回不完整")
        values = tuple(results[0].extra_results)
        memory = NativeUnitFieldMemory(candidate, values[:293])
        memory.inventory_items = self._parse_native_inventory_items(values[293:342])
        for index, name in enumerate(("inventory", "hero", "move", "attack")):
            full = values[342+index]
            if bool(full) != (name in memory.components):
                raise RuntimeError("Incomplete native component generation")
            if full:
                memory.component_identities[name] = (memory.components[name][1], full)
        return memory


    def _unit_fields_from_candidate(
        self,
        pm: ProcessMemory | None,
        candidate: UnitCandidate,
    ) -> list[UnitMemoryField]:
        from war3_game_profile import current_profile
        _al = current_profile().section("layouts")
        if pm is None and self._native_snapshot_for_candidate(candidate) is None:
            with self._process_memory() as field_memory:
                return self._unit_fields_from_candidate(field_memory, candidate)
        fields: list[UnitMemoryField] = []
        from war3_game_profile import current_profile
        adapter = current_profile().adapter
        unit_layout = adapter.units.layout
        hero_layout = adapter.units.hero_layout
        ability_layout = current_profile().section("layouts")["ability"]
        native = self._native_snapshot_for_candidate(candidate)
        self._unit_field_warnings = []

        def note_optional_query_failure(key: str, label: str, exc: Exception) -> None:
            # A failed game-thread query does not invalidate fields already
            # read through the external backend. Keep the panel readable even
            # while unresolved native resources still guard later writes.
            try:
                log_path = record_operation_failure(
                    self.pid, key, exc, requested_pid=self.pid, target_hwnd=self.hwnd,
                )
                note = f"原生查询失败；诊断日志：{log_path}"
            except Exception as log_exc:
                note = f"原生查询失败：{type(exc).__name__}；日志写入失败：{log_exc}"
            self._unit_field_warnings.append(f"{label}不可用")
            fields.append(UnitMemoryField(
                key=f"{key}_unavailable", label=label, value_type="text",
                value="不可用", address=0, category="诊断", note=note,
            ))

        def append_native_real(
            key: str, label: str, value: float, address: int, category: str,
        ) -> None:
            if not math.isfinite(float(value)):
                return
            uses_native_setter = key in self.NATIVE_BASIC_FIELD_ARGUMENTS
            fields.append(UnitMemoryField(
                key=key, label=label, value_type="f32", value=float(value),
                address=address, category=category,
                write_address=0 if uses_native_setter else address,
                write_type="f32" if address and not uses_native_setter else "",
                native_write=uses_native_setter,
                note="persistent native snapshot for current unit",
            ))

        def append_native_int(
            key: str, label: str, value: int, address: int, category: str,
        ) -> None:
            fields.append(UnitMemoryField(
                key=key, label=label, value_type="i32", value=int(value),
                address=address, category=category,
                write_address=address, write_type="i32" if address else "",
                note="persistent native snapshot for current unit",
            ))

        if native is None:
            self._append_unit_field(pm, fields, "hp_max", "HP-最大值", "f32", candidate.hp_max_address, "基础")
            self._append_unit_field(pm, fields, "hp_current", "HP-当前值", "f32", candidate.hp_current_address, "基础")
        else:
            append_native_real("hp_max", "HP-最大值", native.hp_max, candidate.hp_max_address, "基础")
            append_native_real("hp_current", "HP-当前值", native.hp, candidate.hp_current_address, "基础")
        if native is None:
            self._append_unit_field(pm, fields, "hp_regen", "HP-回复率", "f32", candidate.hp_regen_address, "基础")
        elif native.hp_regen is not None:
            append_native_real("hp_regen", "HP-回复率", native.hp_regen, candidate.hp_regen_address, "基础")
        if native is None:
            self._append_unit_field(pm, fields, "mp_max", "MP-最大值", "f32", candidate.mp_max_address, "基础")
            self._append_unit_field(pm, fields, "mp_current", "MP-当前值", "f32", candidate.mp_current_address, "基础")
        else:
            append_native_real("mp_max", "MP-最大值", native.mp_max, candidate.mp_max_address, "基础")
            append_native_real("mp_current", "MP-当前值", native.mp, candidate.mp_current_address, "基础")
        if native is None:
            self._append_unit_field(pm, fields, "mp_regen", "MP-回复率", "f32", candidate.mp_regen_address, "基础")
        elif native.mp_regen is not None:
            append_native_real("mp_regen", "MP-回复率", native.mp_regen, candidate.mp_regen_address, "基础")
        if native is None:
            self._append_unit_field(pm, fields, "x", "坐标-X", "f32", candidate.x_address, "坐标")
            self._append_unit_field(pm, fields, "y", "坐标-Y", "f32", candidate.y_address, "坐标")
        else:
            append_native_real("x", "坐标-X", native.x, candidate.x_address, "坐标")
            append_native_real("y", "坐标-Y", native.y, candidate.y_address, "坐标")

        current_unit_stats = None
        bridge_install_failed = False
        if uses_indexed_backend(self):
            try:
                current_unit_stats = self._unit_stats_for_candidate_24268(candidate)
            except Exception as exc:
                note_optional_query_failure("unit_stats", "护甲/智力", exc)
                bridge_install_failed = isinstance(getattr(exc, "report", None), dict)

        process_memory = pm
        if native is None:
            components = self._selected_components(pm, candidate.owner_address)
        else:
            pm = self._native_unit_field_memory(candidate)
            components = pm.components
        move = components.get("move")
        if move is not None:
            _wrapper, data = move
            if native is None:
                self._append_unit_field(pm, fields, "move_speed", "移动速度", "f32", data + unit_layout["move_speed"], "移动")
            else:
                append_native_real("move_speed", "移动速度", native.move_speed, data + unit_layout["move_speed"], "移动")

        if current_unit_stats is not None:
            identity = (int(current_unit_stats["unit"]), int(current_unit_stats["rawcode"]))
            fields.append(UnitMemoryField(
                key="armor", label="护甲", value_type="f32",
                value=float(current_unit_stats["armor_after"]), address=0,
                category="防御", native_write=True, native_component_identity=identity,
                note="3.0 BlzGetUnitArmor / BlzSetUnitArmor 原生读写",
            ))
            fields.append(UnitMemoryField(
                key="armor_type", label="护甲类型", value_type="i32",
                value=int(current_unit_stats["defense_after"]), address=0,
                category="防御", native_write=True, native_component_identity=identity,
                note="3.0 UNIT_IF_DEFENSE_TYPE 原生读写；0小型、1中型、2大型、3城甲、4普通、5英雄、6神圣、7无甲",
            ))
        elif candidate.unit_address and not uses_indexed_backend(self):
            self._append_unit_field(pm, fields, "armor", "护甲", "f32", candidate.unit_address + unit_layout["armor"], "防御")
            self._append_unit_field(pm, fields, "armor_type", "护甲类型", "i32", candidate.unit_address + unit_layout["armor_type"], "防御")

        # The 3.0 stat-details bridge is a live-process query.  Keep legacy
        # fixture and offline field paths independent from it; real trainer
        # instances always carry both process identifiers.
        stat_details = None
        if getattr(self, "pid", 0) and getattr(self, "hwnd", 0):
            if bridge_install_failed:
                self._unit_field_warnings.append("3.0 属性不可用")
                fields.append(UnitMemoryField(
                    key="stat_details_unavailable", label="3.0 属性",
                    value_type="text", value="不可用", address=0,
                    category="诊断", note="原生桥接失败；详见护甲/智力查询的诊断日志",
                ))
            else:
                try:
                    stat_details = self.stat_details_24268(candidate)
                except Exception as exc:
                    note_optional_query_failure("stat_details", "3.0 属性", exc)
        if stat_details is not None:
            for stat_spec in STAT_DETAIL_SPECS:
                stat_note = (
                    "只统计已识别且有触发几率的暴击来源；多来源显示最高倍率，写入时同步每个来源并验证回滚"
                    if stat_spec.key in ("critical_damage", "spell_critical_damage") else
                    "3.0 Stat Details 原生能力累计值；写入时保留其他装备、天赋和光环贡献并读回总值"
                )
                fields.append(UnitMemoryField(
                    key=f"stat3_{stat_spec.key}", label=stat_spec.label, value_type="f32",
                    value=float(stat_details["values"][stat_spec.key]), address=0,
                    category="3.0 属性", native_write=True,
                    note=stat_note,
                ))

        ability_instances: list[AbilityInstance] = []

        if native is not None:
            if len(native.ability_ids) != len(native.ability_levels):
                raise RuntimeError("Native ability IDs and levels have different lengths")
            # The engine enumeration is authoritative for all unit kinds.
            # Wrapper proximity and the hero's learnable slots cannot determine
            # which abilities currently exist on a unit.
            for slot, (rawcode, level) in enumerate(zip(native.ability_ids, native.ability_levels), 1):
                fields.append(UnitMemoryField(
                    key=f"ability_{slot:02d}_rawcode", label=f"能力{slot:02d} rawcode",
                    value_type="rawcode", value=rawcode, address=0,
                    category="能力实例", note="persistent native ability enumeration",
                ))
                fields.append(UnitMemoryField(
                    key=f"ability_{slot:02d}_level", label=f"能力{slot:02d}等级",
                    value_type="i32", value=level, address=0,
                    category="能力实例", note="persistent native ability enumeration",
                ))

        hero_skill_config_rawcodes: list[int] = []
        hero = components.get("hero")
        if native is not None and native.hero_level > 0:
            data = hero[1] if hero is not None else 0
            append_native_int("hero_level", "英雄等级", native.hero_level, 0, "英雄")
            append_native_int("xp", "经验值", native.hero_xp, data + hero_layout["xp"] if data else 0, "英雄")
            append_native_int("base_strength", "力量(基础)", native.base_strength, data + hero_layout["base_strength"] if data else 0, "英雄")
            append_native_int("base_agility", "敏捷(基础)", native.base_agility, data + hero_layout["base_agility"] if data else 0, "英雄")
            append_native_int("base_intelligence", "智力(基础)", native.base_intelligence, 0, "英雄")
            append_native_int("strength_total", "力量(当前总值)", native.strength, 0, "英雄")
            append_native_int("agility_total", "敏捷(当前总值)", native.agility, 0, "英雄")
            append_native_int("intelligence_total", "智力(当前总值)", native.intelligence, data + hero_layout["intelligence_total"] if data else 0, "英雄")
        if hero is not None:
            _wrapper, data = hero
            if native is None:
                self._append_unit_field(pm, fields, "xp", "经验值", "i32", data + hero_layout["xp"], "英雄")
                self._append_unit_field(pm, fields, "base_strength", "力量(基础)", "i32", data + hero_layout["base_strength"], "英雄")
                self._append_unit_field(pm, fields, "base_agility", "敏捷(基础)", "i32", data + hero_layout["base_agility"], "英雄")
                if current_unit_stats is not None:
                    identity = (int(current_unit_stats["unit"]), int(current_unit_stats["rawcode"]))
                    fields.append(UnitMemoryField(
                        key="base_intelligence", label="智力(基础)", value_type="i32",
                        value=int(current_unit_stats["intelligence_base_after"]), address=0,
                        category="英雄", note="3.0 GetHeroInt(false) 原生读回",
                    ))
                    fields.append(UnitMemoryField(
                        key="intelligence_total", label="智力(当前总值)", value_type="i32",
                        value=int(current_unit_stats["intelligence_total_after"]), address=0,
                        category="英雄", native_write=True, native_component_identity=identity,
                        note="3.0 GetHeroInt(true)；写入时保留装备与光环加成并读回确认",
                    ))
                elif uses_indexed_backend(self):
                    # The indexed cache is not the 3.0 native intelligence value.
                    pass
                else:
                    try:
                        base_intelligence, total_intelligence = self._get_hero_intelligence_pair_via_native_internal(pm, candidate)
                        fields.append(
                            UnitMemoryField(
                                key="intelligence_total",
                                label="智力(当前总值)",
                                value_type="i32",
                                value=total_intelligence,
                                address=data + hero_layout["intelligence_total"],
                                category="英雄",
                                write_address=data + hero_layout["intelligence_total"],
                                write_type="i32",
                                note=(
                                    "内部 GetHeroInt 真实总智力；写入通过内部 SetHeroInt；"
                                    f"基础智力={base_intelligence}"
                                ),
                            )
                        )
                    except Exception as exc:
                        self._append_unit_field(
                            pm,
                            fields,
                            "intelligence_total",
                            "智力(当前总值候选)",
                            "f32",
                            data + hero_layout["intelligence_total"],
                            "英雄",
                            note=f"内部 GetHeroInt 读取失败，暂用旧缓存候选：{exc}",
                        )
            self._append_unit_field(pm, fields, "skill_points", "技能点", "i32", data + hero_layout["skill_points"], "英雄")
            growth_note = "英雄组件成长值，不是面板装备/光环加成"
            self._append_unit_field(pm, fields, "strength_growth", "力量成长/级", "f32", data + hero_layout["strength_growth"], "英雄", note=growth_note)
            self._append_unit_field(pm, fields, "intelligence_growth", "智力成长/级", "f32", data + hero_layout["intelligence_growth"], "英雄", note=growth_note)
            self._append_unit_field(pm, fields, "agility_growth", "敏捷成长/级", "f32", data + hero_layout["agility_growth"], "英雄", note=growth_note)
            current_24268 = bool(uses_indexed_backend(self))
            skill_name_offset = hero_layout["skill_name_native"] if current_24268 else hero_layout["skill_name_legacy"]
            skill_cache_offset = hero_layout["skill_cache_native"] if current_24268 else hero_layout["skill_cache_legacy"]
            skill_level_offset = hero_layout["skill_level_native"] if current_24268 else hero_layout["skill_level_legacy"]
            skill_requirement_offset = hero_layout["skill_requirement_native"] if current_24268 else hero_layout["skill_requirement_legacy"]
            skill_name_note = "英雄技能栏 rawcode；替换时由引擎从地图资源创建技能"
            skill_cache_note = "旧版候选/运行时缓存；单改这里通常不改变已学技能效果"
            for index in range(self.HERO_SKILL_SLOT_COUNT):
                name_address = data + skill_name_offset + index * 4
                try:
                    current_config_rawcode = pm.read_u32(name_address)
                except OSError:
                    current_config_rawcode = 0
                hero_skill_config_rawcodes.append(current_config_rawcode)
            if native is None:
                ability_instances = self._ability_instances_from_candidate(pm, candidate)
            for index in range(self.HERO_SKILL_SLOT_COUNT):
                number = index + 1
                name_address = data + skill_name_offset + index * 4
                cache_address = data + skill_cache_offset + index * 4
                extra_writes = [(cache_address, "rawcode")]
                self._append_unit_field(
                    pm,
                    fields,
                    f"skill{number}_name",
                    f"技能{number}名称",
                    "rawcode",
                    name_address,
                    "技能",
                    note=skill_name_note,
                    extra_writes=tuple(extra_writes),
                )
                self._append_unit_field(
                    pm,
                    fields,
                    f"skill{number}_cache_rawcode",
                    f"技能{number}缓存rawcode",
                    "rawcode",
                    cache_address,
                    "技能",
                    writable=False,
                    note=skill_cache_note,
                )
                self._append_unit_field(
                    pm,
                    fields,
                    f"skill{number}_learnable",
                    f"技能{number}可学",
                    "i32",
                    data + skill_level_offset + index * 4,
                    "技能",
                    note="英雄组件技能等级/可学数组",
                )
                self._append_unit_field(
                    pm,
                    fields,
                    f"skill{number}_requirement",
                    f"技能{number}要求",
                    "i32",
                    data + skill_requirement_offset + index * 4,
                    "技能",
                    note="英雄组件技能需求数组",
                )

        if hero_skill_config_rawcodes:
            skill_instance_by_index = self._map_hero_skill_instances(
                hero_skill_config_rawcodes,
                ability_instances,
            )
            used_instance_wrappers = {
                instance.wrapper_address
                for instance in skill_instance_by_index.values()
            }
            for index, rawcode in enumerate(hero_skill_config_rawcodes):
                if not rawcode:
                    continue
                instance = skill_instance_by_index.get(index)
                if instance is None:
                    continue
                number = index + 1
                mirror = (
                    ((instance.mirror_rawcode_address, "rawcode"),)
                    if instance.mirror_rawcode_address
                    else ()
                )
                fields.append(
                    UnitMemoryField(
                        key=f"skill{number}_instance_rawcode",
                        label=f"技能{number}实例rawcode",
                        value_type="rawcode",
                        value=instance.rawcode,
                        address=instance.rawcode_address,
                        category="技能",
                        write_address=0,
                        write_type="",
                        note=(
                            f"class={instance.class_text} wrapper=0x{instance.wrapper_address:x}; "
                            "只读：运行时能力实例 ID，单改这里不会改变技能效果"
                        ),
                        extra_writes=(),
                    )
                )
                fields.append(
                    UnitMemoryField(
                        key=f"skill{number}_effect_class",
                        label=f"技能{number}效果类",
                        value_type="rawcode",
                        value=instance.class_rawcode,
                        address=instance.wrapper_tag_address,
                        category="技能",
                        write_address=0,
                        write_type="",
                        note=(
                            f"wrapper=0x{instance.wrapper_address:x} handle=0x{instance.handle:x}; "
                            "只读：运行时能力类决定已存在技能效果，单改 rawcode 不会改这里"
                        ),
                    )
                )
                fields.append(
                    UnitMemoryField(
                        key=f"skill{number}_data_vtable",
                        label=f"技能{number}数据vtable",
                        value_type="ptr",
                        value=instance.data_vtable,
                        address=instance.data_address,
                        category="技能",
                        write_address=0,
                        write_type="",
                        note="只读：能力实例数据对象虚表；不同效果类通常不同",
                    )
                )
                fields.append(
                    UnitMemoryField(
                        key=f"skill{number}_data_cache",
                        label=f"技能{number}数据缓存",
                        value_type="ptr",
                        value=instance.data_cache_pointer,
                        address=instance.data_cache_address,
                        category="技能",
                        write_address=0,
                        write_type="",
                        note="只读：疑似 AbilDataCacheNode 指针；实际技能数据不只由 rawcode/cache 字段决定",
                    )
                )
        else:
            used_instance_wrappers = set()

        for instance in ability_instances:
            if instance.wrapper_address in used_instance_wrappers:
                continue
            mirror = (
                ((instance.mirror_rawcode_address, "rawcode"),)
                if instance.mirror_rawcode_address
                else ()
            )
            fields.append(
                UnitMemoryField(
                    key=f"ability_{instance.slot:02d}_rawcode",
                    label=f"能力{instance.slot:02d} rawcode",
                    value_type="rawcode",
                    value=instance.rawcode,
                    address=instance.rawcode_address,
                    category="能力实例",
                    write_address=0,
                    write_type="",
                    note=(
                        f"class={instance.class_text} wrapper=0x{instance.wrapper_address:x}; "
                        "只读：实际挂在单位上的能力实例 ID，单改这里不会改变效果"
                    ),
                    extra_writes=(),
                )
            )
            fields.append(
                UnitMemoryField(
                    key=f"ability_{instance.slot:02d}_effect_class",
                    label=f"能力{instance.slot:02d}效果类",
                    value_type="rawcode",
                    value=instance.class_rawcode,
                    address=instance.wrapper_tag_address,
                    category="能力实例",
                    write_address=0,
                    write_type="",
                    note=(
                        f"wrapper=0x{instance.wrapper_address:x} handle=0x{instance.handle:x}; "
                        "只读：运行时能力类决定已存在能力效果"
                    ),
                )
            )
            fields.append(
                UnitMemoryField(
                    key=f"ability_{instance.slot:02d}_data_vtable",
                    label=f"能力{instance.slot:02d}数据vtable",
                    value_type="ptr",
                    value=instance.data_vtable,
                    address=instance.data_address,
                    category="能力实例",
                    write_address=0,
                    write_type="",
                    note="只读：能力实例数据对象虚表；不同效果类通常不同",
                )
            )
            fields.append(
                UnitMemoryField(
                    key=f"ability_{instance.slot:02d}_data_cache",
                    label=f"能力{instance.slot:02d}数据缓存",
                    value_type="ptr",
                    value=instance.data_cache_pointer,
                    address=instance.data_cache_address,
                    category="能力实例",
                    write_address=0,
                    write_type="",
                    note="只读：疑似 AbilDataCacheNode 指针",
                )
            )

        attack = components.get("attack")
        if attack is not None:
            _wrapper, data = attack
            current_24268 = bool(uses_indexed_backend(self))
            timing_24268 = None
            if current_24268:
                timing_24268 = self._attack_timing_24268_from_memory(pm, data)
            self._append_attack_fields(
                pm, fields, "attack1", "攻击1", data,
                current_24268=current_24268,
                timing_24268=timing_24268,
            )
            try:
                attack2_data = data + current_profile().section("layouts")["attack"]["second_component"]
                has_attack2 = pm.attack2 if native is not None else (
                    self._looks_like_vtable(pm.read_u64(attack2_data))
                    and pm.read_i32(attack2_data + _al["attack"]["identity_kind"]) == pm.read_i32(data + _al["attack"]["identity_kind"]))
                if has_attack2:
                    self._append_attack_fields(pm, fields, "attack2", "攻击2", attack2_data)
            except OSError:
                pass

        if native is None:
            display_items = self._inventory_items_from_candidate(process_memory, candidate, components)
        else:
            if any(len(values) != 6 for values in (native.item_ids, native.item_charges,
                                                   native.item_handles, native.item_addresses, native.item_full_handles)):
                raise RuntimeError("Native inventory snapshot must contain six slots")
            # Both values and optional slot metadata come from the DLL. Bind
            # write capability only when the two responses identify the same item.
            metadata = {item.slot: item for item in pm.inventory_items}
            display_items = []
            for index in range(6):
                rawcode = native.item_ids[index]
                handle = native.item_handles[index]
                if bool(rawcode) != bool(handle):
                    raise RuntimeError("Native inventory item identity is incomplete")
                item = metadata.get(index + 1)
                if item is not None and (item.rawcode != rawcode or
                    (rawcode and (item.item_address != native.item_addresses[index]
                                  or item.handle != native.item_full_handles[index])) or
                    (not rawcode and item.item_address)):
                    item = None
                if item is None:
                    item = InventoryItem(slot=index + 1, handle=0, handle_address=0)
                display_items.append(replace(item, rawcode=rawcode, charges=native.item_charges[index]))

        for item in display_items:
            if item.rawcode:
                fields.append(
                    UnitMemoryField(
                        key=f"inventory_slot_{item.slot}",
                        label=f"物品槽{item.slot}",
                        value_type="rawcode",
                        value=item.rawcode,
                        address=item.rawcode_address,
                        category="物品栏",
                        write_address=item.rawcode_address,
                        write_type="rawcode",
                        native_write=item.native_slot,
                        note=(
                            f"handle=0x{item.handle:x} item=0x{item.item_address:x}; "
                            f"mirror=0x{item.mirror_rawcode_address:x} ability={format_rawcode(item.ability_rawcode) if item.ability_rawcode else '0'}; "
                            "写入时通过内部物品栏函数创建/替换本槽 item，不交换其他物品槽"
                        ),
                    )
                )
            else:
                note = "空" if not item.handle else f"未解析 item 对象；handle=0x{item.handle:x}"
                fields.append(
                    UnitMemoryField(
                        key=f"inventory_slot_{item.slot}",
                        label=f"物品槽{item.slot}",
                        value_type="rawcode",
                        value=0,
                        address=item.handle_address,
                        category="物品栏",
                        write_address=item.handle_address,
                        write_type="rawcode",
                        native_write=item.native_slot,
                        note=note + "；写入时通过内部物品栏函数在本槽创建物品",
                    )
                )
            fields.append(
                UnitMemoryField(
                    key=f"inventory_slot_{item.slot}_charges",
                    label=f"物品槽{item.slot}数量",
                    value_type="i32",
                    value=item.charges,
                    address=item.charges_address or item.handle_address,
                    category="物品栏",
                    write_address=0 if native is not None else item.charges_address,
                    write_type="i32" if native is None and item.charges_address else "",
                    native_write=bool(native is not None and native.item_handles[item.slot - 1]
                                      and native.item_addresses[item.slot - 1] and native.item_full_handles[item.slot - 1]),
                    note=(
                        f"item charges offset=0x{self.ITEM_CHARGES_OFFSET:x}"
                        if item.charges_address
                        else "空槽或未解析 item 对象"
                    ),
                )
            )
        if native is not None and isinstance(pm, NativeUnitFieldMemory):
            for index, field in enumerate(fields):
                if field.key == "intelligence_total" or self._skill_index_from_field_key(field.key) is not None:
                    identity = pm.component_identities.get("hero")
                    if identity is not None:
                        fields[index] = replace(field, write_address=0, write_type="", extra_writes=(), native_write=True,
                                                native_component_identity=identity)
                    continue
                spec = NATIVE_COMPONENT_FIELD_SPECS.get(field.key)
                if spec is None or not field.writable:
                    continue
                identity = pm.component_identities.get(spec[1])
                if identity is None:
                    raise RuntimeError("Incomplete native component generation")
                fields[index] = replace(field, write_address=0, write_type="", extra_writes=(),
                                        native_write=True, native_component_identity=identity)
        if native is not None:
            hero_stat_notes = {
                "base_strength": "输入目标基础力量（0～1000000 的整数）；通过游戏属性接口设置，并按本栏的读取方式确认。不是设置总力量；读回不等于目标时会报错。",
                "base_agility": "输入目标基础敏捷（0～1000000 的整数）；通过游戏属性接口设置，并按本栏的读取方式确认。不是设置总敏捷；读回不等于目标时会报错。",
                "base_intelligence": "显示游戏返回的基础智力；当前未提供基础智力直接写入，请修改“智力(当前总值)”。",
                "strength_total": "显示包含当前加成的总力量，不能直接写入；如需调整，请修改“力量(基础)”，其输入值不等于目标总力量。",
                "agility_total": "显示包含当前加成的总敏捷，不能直接写入；如需调整，请修改“敏捷(基础)”，其输入值不等于目标总敏捷。",
                "intelligence_total": "输入目标总智力；通过游戏接口调整基础智力并保留当前加成，读回确认总值。仅接受 0～1000000 的整数；低于当前加成、无法保留加成时会拒绝写入。",
            }
            for index, field in enumerate(fields):
                if field.key in hero_stat_notes:
                    access = "可写" if field.writable else "只读"
                    unavailable = "；当前未取得可写的英雄组件" if (
                        not field.writable and field.key in {"base_strength", "base_agility", "intelligence_total"}) else ""
                    fields[index] = replace(field, note=f"{access}{unavailable}；{hero_stat_notes[field.key]}")
        return fields


    def read_selected_unit_fields(self) -> tuple[VisibleUnitPanel, UnitCandidate, list[UnitMemoryField]]:
        snapshot = self._selected_candidates_snapshot(None)
        if not snapshot:
            raise RuntimeError("游戏当前没有可操作的选中单位")
        candidate = snapshot[0][0]
        if self._native_snapshot_for_candidate(candidate) is not None:
            panel = self._panel_from_candidate(None, candidate)
            summaries = self._selected_summaries_from_snapshot(None, snapshot)
            fields = self._unit_fields_from_candidate(None, candidate)
        else:
            with self._process_memory() as memory:
                panel = self._panel_from_candidate(memory, candidate)
                summaries = self._selected_summaries_from_snapshot(memory, snapshot)
                fields = self._unit_fields_from_candidate(memory, candidate)
        self._last_selected_summaries = summaries
        return panel, candidate, fields


    def _recover_win10_native_handlers(
        self,
        isolated: "War3Trainer",
        pm: ProcessMemory,
        diagnostics: Win10ReadLogger,
    ) -> tuple[int, tuple[str, ...]]:
        wanted = set(self.WIN10_COMPAT_NATIVE_NAMES)
        isolated._native_handlers.update(
            {
                name: handler
                for name, handler in self._native_handlers.items()
                if name in wanted
            }
        )
        discovery_error = ""
        try:
            isolated._discover_native_handlers_near_table_win10(pm, wanted)
        except Exception as exc:
            discovery_error = repr(exc)

        regions = pm.regions(force_refresh=True)
        validated: dict[str, NativeHandler] = {}
        for name in sorted(wanted):
            handler = isolated._native_handlers.get(name)
            if handler is None or handler.name != name:
                continue
            record_region = self._region_for_address(regions, handler.record_address)
            if record_region is None or record_region.typ not in (MEM_PRIVATE, MEM_MAPPED):
                continue
            if not self._is_executable_image_address(regions, handler.handler_address):
                continue
            try:
                size = pm.read_u64(handler.record_address + 8)
            except OSError:
                continue
            if size != len(name):
                continue
            validated[name] = handler

        shared_before = set(self._native_handlers)
        for name, handler in validated.items():
            self._native_handlers.setdefault(name, handler)

        profile_names = set(self.NATIVE_RECORD_PROFILE_EXTERNALS)
        missing_profile = tuple(sorted(profile_names.difference(validated)))
        recovered_profile = len(profile_names) - len(missing_profile)
        self._last_win10_native_recovered = recovered_profile
        self._last_win10_native_missing = missing_profile
        diagnostics.log(
            "win10_native_recovery",
            requested=len(wanted),
            validated=len(validated),
            shared_added=len(set(self._native_handlers).difference(shared_before)),
            profile_recovered=recovered_profile,
            profile_total=len(profile_names),
            profile_missing=list(missing_profile),
            all_missing=sorted(wanted.difference(validated)),
            discovery_error=discovery_error,
        )
        return recovered_profile, missing_profile


    @contextmanager
    def _win10_memory_operation(
        self,
        operation: str,
        *,
        write: bool = False,
    ) -> Iterator[tuple[Win10ReadLogger, Win10ProcessMemory]]:
        diagnostics = Win10ReadLogger(self.pid)
        self._last_win10_log_path = str(diagnostics.latest_path)
        diagnostics.log("win10_operation_begin", operation=operation, write=write)
        try:
            with Win10ProcessMemory(self.pid, diagnostics, write=write) as pm:
                yield diagnostics, pm
            diagnostics.log("win10_operation_success", operation=operation)
        except Exception as exc:
            diagnostics.log_traceback("win10_operation_failure", exc)
            raise
        finally:
            diagnostics.close()


    def _win10_session_for_identity(
        self,
        handle: int,
        owner: int,
        unit: int,
        pm: ProcessMemory,
    ) -> "War3Trainer":
        # Compatibility callers used to create an isolated backup reader here.
        # Identity-bound operations now all use the persistent native object
        # table, so creating a second reader would reintroduce a scan-capable
        # execution path. Keep the signature for old callers but return the
        # active native trainer directly.
        del handle, owner, unit, pm
        return self


    def trainer_for_read_source(
        self,
        identity: tuple[int, int, int],
        win10_compat: bool,
    ) -> "War3Trainer":
        # Display source labels do not select a different execution engine.
        return self


    def _seed_win10_isolated_state(self, isolated: "War3Trainer") -> dict[str, int]:
        owner_index = dict(self._unit_owner_index)
        owner_index.update(isolated._unit_owner_index)
        isolated._unit_owner_index = owner_index
        isolated._selection_player_candidates = list(
            dict.fromkeys(
                [
                    *isolated._selection_player_candidates,
                    *self._selection_player_candidates,
                ]
            )
        )
        # A discovered handle slot can remain readable after the selection changes.
        # Reusing it pins later reads to the first unit seen in this session.
        isolated._selected_handle_addresses = list(self.KNOWN_SELECTED_HANDLE_ADDRESSES)
        resource_candidates = {
            start: list(caches)
            for start, caches in self._resource_candidates_by_start.items()
        }
        for start, caches in isolated._resource_candidates_by_start.items():
            resource_candidates[start] = list(
                dict.fromkeys([*resource_candidates.get(start, []), *caches])
            )
        isolated._resource_candidates_by_start = resource_candidates

        component_index: dict[int, dict[str, tuple[int, int]]] = {}
        if self._component_index_cache is not None:
            component_index.update(
                {
                    owner: dict(components)
                    for owner, components in self._component_index_cache.items()
                }
            )
        if isolated._component_index_cache is not None:
            for owner, components in isolated._component_index_cache.items():
                component_index.setdefault(owner, {}).update(components)
        isolated._component_index_cache = component_index or None

        selected_components_cache = {
            key: dict(components)
            for key, components in self._selected_components_cache.items()
        }
        for key, components in isolated._selected_components_cache.items():
            selected_components_cache[key] = dict(components)
        isolated._selected_components_cache = selected_components_cache
        isolated._unit_component_layout_confirmed = bool(
            self._unit_component_layout_confirmed
            or isolated._unit_component_layout_confirmed
        )

        isolated._selection_manager_offset = self._selection_manager_offset
        isolated._selection_list_offsets = tuple(self._selection_list_offsets)
        isolated._native_handlers.update(self._native_handlers)
        return {
            "owner_cache": len(isolated._unit_owner_index),
            "selection_player_candidates": len(isolated._selection_player_candidates),
            "selected_handle_addresses": len(isolated._selected_handle_addresses),
            "resource_candidate_groups": len(isolated._resource_candidates_by_start),
            "component_index": len(isolated._component_index_cache or {}),
            "selected_component_cache": len(isolated._selected_components_cache),
            "native_handlers": len(isolated._native_handlers),
        }


    @staticmethod
    def _win10_candidate_from_identity(
        isolated: "War3Trainer",
        pm: ProcessMemory,
        handle: int,
        owner: int,
        unit: int,
    ) -> UnitCandidate:
        candidate = isolated._candidate_from_identity(
            pm,
            handle,
            owner,
            unit,
            f"win10_candidate handle=0x{handle:x} owner=0x{owner:x} unit=0x{unit:x}",
            900,
        )
        if candidate is None:
            raise RuntimeError("备用读取的单位身份已经失效，请重新点击备用读取")
        return candidate


    def read_selected_unit_fields_win10(
        self,
    ) -> tuple[VisibleUnitPanel, UnitCandidate, list[UnitMemoryField]]:
        # Keep the compatibility API, but selection, identity and fields must
        # follow the same DLL path. Native failures must not start a heap scan.
        return self.read_selected_unit_fields()


    def read_unit_fields_by_identity(
        self,
        handle: int,
        owner: int,
        unit: int,
    ) -> tuple[VisibleUnitPanel, UnitCandidate, list[UnitMemoryField]]:
        candidate = self._candidate_from_display_identity(
            None, handle, owner, unit,
            f"manual_candidate handle=0x{handle:x} owner=0x{owner:x} unit=0x{unit:x}", 850)
        if candidate is None:
            raise RuntimeError("候选单位已经失效，请重新读取候选列表")
        if self._native_snapshot_for_candidate(candidate) is not None:
            return self._panel_from_candidate(None, candidate), candidate, self._unit_fields_from_candidate(None, candidate)
        with self._process_memory() as memory:
            return self._panel_from_candidate(memory, candidate), candidate, self._unit_fields_from_candidate(memory, candidate)


    def read_unit_fields_by_identity_win10(
        self,
        handle: int,
        owner: int,
        unit: int,
    ) -> tuple[VisibleUnitPanel, UnitCandidate, list[UnitMemoryField]]:
        # Compatibility entry points share the native object-table identity path.
        return self.read_unit_fields_by_identity(handle, owner, unit)


    def _skill_index_from_field_key(self, key: str) -> int | None:
        if not key.startswith("skill") or not key.endswith("_name"):
            return None
        slot_text = key[len("skill") : -len("_name")]
        if not slot_text.isdigit():
            return None
        index = int(slot_text) - 1
        if not 0 <= index < self.HERO_SKILL_SLOT_COUNT:
            return None
        return index


    def _map_hero_skill_instances(
        self,
        configs: list[int],
        ability_instances: list[AbilityInstance],
    ) -> dict[int, AbilityInstance]:
        ordered_instances = sorted(
            ability_instances,
            key=lambda instance: (instance.handle, instance.wrapper_address),
        )
        skill_candidates = [
            instance
            for instance in ordered_instances
            if ((instance.rawcode >> 24) & 0xFF) != ord("B")
            and ((instance.class_rawcode >> 24) & 0xFF) != ord("B")
        ]
        mapped: dict[int, AbilityInstance] = {}
        used_wrappers: set[int] = set()
        for index, rawcode in enumerate(configs):
            if not rawcode:
                continue
            for instance in skill_candidates:
                if instance.wrapper_address in used_wrappers:
                    continue
                if instance.rawcode != rawcode:
                    continue
                mapped[index] = instance
                used_wrappers.add(instance.wrapper_address)
                break

        missing_indices = [
            index
            for index, rawcode in enumerate(configs)
            if rawcode and index not in mapped
        ]
        if not missing_indices:
            return mapped

        nonzero_indices = [
            index
            for index, rawcode in enumerate(configs)
            if rawcode
        ]
        nonzero_config_count = sum(1 for rawcode in configs if rawcode)
        candidate_position_by_wrapper = {
            instance.wrapper_address: position
            for position, instance in enumerate(skill_candidates)
        }
        rank_by_index = {
            index: rank
            for rank, index in enumerate(nonzero_indices)
        }
        start_positions = {
            candidate_position_by_wrapper[instance.wrapper_address] - rank_by_index[index]
            for index, instance in mapped.items()
            if instance.wrapper_address in candidate_position_by_wrapper
        }
        if len(start_positions) == 1:
            start = next(iter(start_positions))
            end = start + nonzero_config_count
            if 0 <= start and end <= len(skill_candidates):
                window = skill_candidates[start:end]
                anchors_match = all(
                    mapped[index].wrapper_address == window[rank_by_index[index]].wrapper_address
                    for index in mapped
                    if index in rank_by_index
                )
                if anchors_match:
                    for index in missing_indices:
                        instance = window[rank_by_index[index]]
                        if instance.wrapper_address not in used_wrappers:
                            mapped[index] = instance
                            used_wrappers.add(instance.wrapper_address)
                    return mapped

        remaining_instances = [
            instance
            for instance in skill_candidates
            if instance.wrapper_address not in used_wrappers
        ]
        if len(skill_candidates) != nonzero_config_count:
            return mapped
        if len(remaining_instances) != len(missing_indices):
            return mapped

        for index, instance in zip(missing_indices, remaining_instances):
            mapped[index] = instance
        return mapped


    def _hero_skill_instance_map(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        hero_data: int,
    ) -> tuple[list[int], dict[int, AbilityInstance], list[AbilityInstance]]:
        configs: list[int] = []
        from war3_game_profile import current_profile
        layout = current_profile().adapter.units.hero_layout
        config_offset = layout["skill_name_native"] if uses_indexed_backend(self) else layout["skill_name_legacy"]
        for index in range(self.HERO_SKILL_SLOT_COUNT):
            try:
                configs.append(pm.read_u32(hero_data + config_offset + index * 4))
            except OSError:
                configs.append(0)
        ability_instances = self._ability_instances_from_candidate(
            pm,
            candidate,
            allow_global_scan=True,
        )
        mapped = self._map_hero_skill_instances(configs, ability_instances)
        return configs, mapped, ability_instances


    def _hero_skill_instance_map_for_write(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        configs: list[int],
    ) -> tuple[dict[int, AbilityInstance], list[AbilityInstance]]:
        mapped: dict[int, AbilityInstance] = {}
        instances: list[AbilityInstance] = []
        seen_data: set[int] = set()
        if self._persistent_native_initialized and self._native_snapshot_for_candidate(candidate) is not None:
            native_instances = self._ability_instances_from_candidate(pm, candidate)
            for index, rawcode in enumerate(configs):
                if not rawcode:
                    continue
                matches = [
                    ability for ability in native_instances
                    if ability.rawcode == rawcode and ability.data_address not in seen_data
                ]
                if len(matches) != 1:
                    continue
                instance = replace(matches[0], slot=index + 1)
                seen_data.add(instance.data_address)
                mapped[index] = instance
                instances.append(instance)
            return mapped, instances
        for index, rawcode in enumerate(configs):
            if not rawcode:
                continue
            data_address = self._find_engine_ability_data(pm, candidate, rawcode)
            if not data_address or data_address in seen_data:
                continue
            seen_data.add(data_address)
            instance = self._ability_instance_from_data_for_candidate(
                pm,
                candidate,
                data_address,
                rawcode,
            )
            if instance is None:
                continue
            instance = replace(instance, slot=index + 1)
            mapped[index] = instance
            instances.append(instance)

        missing_indices = [
            index
            for index, rawcode in enumerate(configs)
            if rawcode and index not in mapped and configs.count(rawcode) == 1
        ]
        if missing_indices:
            fallback_rawcodes = {configs[index] for index in missing_indices}
            fallback_instances = self._ability_instances_from_candidate(
                pm,
                candidate,
                required_rawcodes=fallback_rawcodes,
                allow_global_scan=True,
            )
            for index in missing_indices:
                rawcode = configs[index]
                matches = [
                    ability
                    for ability in fallback_instances
                    if ability.rawcode == rawcode
                    and ability.data_address not in seen_data
                ]
                if len(matches) != 1:
                    continue
                instance = replace(matches[0], slot=index + 1)
                seen_data.add(instance.data_address)
                mapped[index] = instance
                instances.append(instance)
        return mapped, instances


    def _ability_runtime_template_from_instance(
        self,
        pm: ProcessMemory,
        instance: AbilityInstance,
    ) -> dict[str, object]:
        return {
            "class_rawcode": instance.class_rawcode,
            "fields": {
                offset: pm.read(instance.data_address + offset, 8)
                for offset in self.ABILITY_RUNTIME_TEMPLATE_QWORD_OFFSETS
            },
        }


    def _write_ability_runtime_template(
        self,
        pm: ProcessMemory,
        instance: AbilityInstance,
        rawcode: int,
        template: dict[str, object],
    ) -> int:
        class_rawcode = int(template.get("class_rawcode", rawcode)) & 0xFFFFFFFF
        fields = template.get("fields")
        if not isinstance(fields, dict):
            raise RuntimeError("技能运行时模板缺少字段快照")
        for offset in self.ABILITY_RUNTIME_TEMPLATE_QWORD_OFFSETS:
            data = fields.get(offset)
            if not isinstance(data, (bytes, bytearray)) or len(data) != 8:
                raise RuntimeError(f"技能运行时模板字段 0x{offset:x} 无效")
            pm.write_bytes(instance.data_address + offset, bytes(data))
        pm.write_u32(instance.rawcode_address, rawcode)
        if instance.mirror_rawcode_address:
            pm.write_u32(instance.mirror_rawcode_address, rawcode)
        old_tag = pm.read_u64(instance.wrapper_tag_address)
        pm.write_bytes(
            instance.wrapper_tag_address,
            struct.pack("<Q", ((class_rawcode & 0xFFFFFFFF) << 32) | (old_tag & 0xFFFFFFFF)),
        )
        return class_rawcode


    def _ability_template_source_is_live(
        self,
        pm: ProcessMemory,
        owner: int,
        unit: int,
    ) -> bool:
        if not self._sane_heap_ptr(owner) or not self._sane_heap_ptr(unit):
            return False
        source = self._candidate_from_owner(pm, owner, 0, "ability_template_source")
        if source is None or source.unit_address != unit:
            return False
        try:
            current_hp = pm.read_f32(source.hp_current_address)
            max_hp = pm.read_f32(source.hp_max_address)
        except OSError:
            return False
        return self._valid_current_limit(current_hp, max_hp) and current_hp > 0.0 and max_hp > 0.0


    def _ability_template_source_candidate(
        self,
        pm: ProcessMemory,
        owner: int,
        unit: int,
    ) -> UnitCandidate | None:
        if not self._sane_heap_ptr(owner) or not self._sane_heap_ptr(unit):
            return None
        source = self._candidate_from_owner(pm, owner, 0, "ability_template_source")
        if source is None or source.unit_address != unit:
            return None
        try:
            current_hp = pm.read_f32(source.hp_current_address)
            max_hp = pm.read_f32(source.hp_max_address)
        except OSError:
            return None
        if not (self._valid_current_limit(current_hp, max_hp) and current_hp > 0.0 and max_hp > 0.0):
            return None
        return source


    def _find_ability_runtime_template(
        self,
        pm: ProcessMemory,
        rawcode: int,
        *,
        excluded_wrappers: set[int] | None = None,
        excluded_data: set[int] | None = None,
    ) -> AbilityInstance | None:
        from war3_game_profile import current_profile
        return current_profile().adapter.legacy._find_ability_runtime_template(self, pm, rawcode, excluded_wrappers=excluded_wrappers, excluded_data=excluded_data)


    def _selected_ability_level_for_candidate(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        rawcode: int,
    ) -> int:
        if isinstance(pm, Win10ProcessMemory):
            unit_handle = self._current_jass_unit_handle_win10(
                pm,
                candidate,
                pm.diagnostics,
            )
            handlers = self._discover_native_handlers_near_table_win10(
                pm,
                ("GetUnitAbilityLevel",),
            )
        else:
            unit_handle = self._elephant_selected_handle(pm)
            resolved_unit = self._resolve_jass_unit_handle(unit_handle)
            if resolved_unit != candidate.unit_address:
                raise RuntimeError("当前选择已经变化，请重新读取当前选中单位")
            handlers = self._discover_native_handlers(
                pm,
                ("GetUnitAbilityLevel",),
            )
        return int(
            self._run_native_helper_ops(
                unit_handle,
                ((
                    self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE_LEVEL,
                    rawcode,
                    handlers["GetUnitAbilityLevel"].handler_address,
                    0,
                    0,
                ),),
            )[0].result
        )


    def _write_hero_skill_name_field_24268(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        field: UnitMemoryField,
        index: int,
        new_rawcode: int,
    ) -> UnitMemoryField:
        """Replace one current-build hero skill through engine callbacks."""
        from war3_game_profile import current_profile
        _al = current_profile().section("layouts")
        try:
            selected = self._selected_candidates_snapshot(pm)
        except (AttributeError, OSError, RuntimeError) as exc:
            raise RuntimeError(
                "3.0 英雄技能替换需要稳定的当前选择和引擎上下文；"
                "原技能及配置未修改"
            ) from exc
        if len(selected) != 1 or selected[0][0].unit_address != candidate.unit_address:
            raise RuntimeError("3.0 英雄技能替换需要只选中当前英雄")
        components = self._selected_components(pm, candidate.owner_address)
        hero = components.get("hero")
        if hero is None:
            raise RuntimeError("当前选中单位没有英雄组件，不能替换英雄技能")
        _hero_wrapper, hero_data = hero
        if pm.read_u64(hero_data + _al["ability"]["unit_owner"]) != candidate.unit_address:
            raise RuntimeError("3.0 英雄组件身份已经变化，请重新读取")
        name_address = hero_data + _al["hero"]["skill_name_native"] + index * 4
        cache_address = hero_data + _al["hero"]["skill_cache_native"] + index * 4
        old_rawcode = pm.read_u32(name_address)
        old_cache = pm.read_u32(cache_address)
        if not old_rawcode:
            raise RuntimeError("当前英雄技能栏为空，没有可替换的技能")
        if old_rawcode == new_rawcode:
            return replace(
                field, value=new_rawcode, write_address=0, write_type="",
                extra_writes=(), native_write=True,
                note="3.0 当前引擎技能栏已是目标资源",
            )
        configs = [pm.read_u32(hero_data + _al["hero"]["skill_name_native"] + slot * 4)
                   for slot in range(self.HERO_SKILL_SLOT_COUNT)]
        if new_rawcode in configs[:index] + configs[index + 1:]:
            raise RuntimeError(f"{format_rawcode(new_rawcode)} 已存在于当前英雄的其它技能槽")
        old_result = self.ability_batch_24268(old_rawcode, 0)
        old_rows = [row for row in old_result.get("rows", ())
                    if row.get("handle") == candidate.handle]
        if len(old_rows) != 1:
            raise RuntimeError("当前英雄技能实例已变化，请重新读取")
        old_level = int(old_rows[0].get("after", 0))
        new_result = self.ability_batch_24268(new_rawcode, 0)
        new_rows = [row for row in new_result.get("rows", ())
                    if row.get("handle") == candidate.handle]
        if len(new_rows) != 1:
            raise RuntimeError("当前英雄目标技能实例读取不完整")
        if int(new_rows[0].get("after", 0)) > 0:
            raise RuntimeError(f"{format_rawcode(new_rawcode)} 已经存在于当前英雄，拒绝生成重复技能")

        changed_runtime = False
        try:
            if old_level > 0:
                removed = self.ability_batch_24268(old_rawcode, 2)
                removed_rows = [row for row in removed.get("rows", ())
                                if row.get("handle") == candidate.handle]
                if len(removed_rows) != 1 or int(removed_rows[0].get("after", -1)) != 0:
                    raise RuntimeError("旧技能移除后读回不一致")
                added = self.ability_batch_24268(new_rawcode, 1, old_level)
                added_rows = [row for row in added.get("rows", ())
                              if row.get("handle") == candidate.handle]
                if len(added_rows) != 1 or int(added_rows[0].get("after", 0)) <= 0:
                    raise RuntimeError("新技能创建后读回不一致")
                changed_runtime = True
            pm.write_u32(name_address, new_rawcode)
            pm.write_u32(cache_address, new_rawcode)
            if pm.read_u32(name_address) != new_rawcode or pm.read_u32(cache_address) != new_rawcode:
                raise RuntimeError("英雄技能配置写入后读回不一致")
        except Exception as exc:
            rollback_errors: list[str] = []
            if changed_runtime:
                try:
                    self.ability_batch_24268(new_rawcode, 2)
                except Exception as rollback_error:
                    rollback_errors.append(f"移除新技能：{rollback_error}")
                try:
                    restored = self.ability_batch_24268(old_rawcode, 1, old_level)
                    rows = [row for row in restored.get("rows", ())
                            if row.get("handle") == candidate.handle]
                    if len(rows) != 1 or int(rows[0].get("after", 0)) <= 0:
                        rollback_errors.append("旧技能读回失败")
                except Exception as rollback_error:
                    rollback_errors.append(f"恢复旧技能：{rollback_error}")
            try:
                if pm.read_u32(name_address) == new_rawcode:
                    pm.write_u32(name_address, old_rawcode)
                if pm.read_u32(cache_address) == new_rawcode:
                    pm.write_u32(cache_address, old_cache)
            except Exception as rollback_error:
                rollback_errors.append(f"恢复技能配置：{rollback_error}")
            suffix = f"；回滚失败：{'；'.join(rollback_errors)}" if rollback_errors else ""
            raise RuntimeError(f"3.0 技能替换失败：{exc}{suffix}") from exc
        return replace(
            field, value=new_rawcode, write_address=0, write_type="",
            extra_writes=(), native_write=True,
            note=(f"3.0 当前引擎从地图资源创建技能；原等级={old_level}；"
                  "已验证配置与运行时实例"),
        )


    def _write_hero_skill_name_field(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        field: UnitMemoryField,
        value: int | float | str,
    ) -> UnitMemoryField:
        from war3_game_profile import current_profile
        _al = current_profile().section("layouts")
        index = self._skill_index_from_field_key(field.key)
        if index is None:
            raise RuntimeError(f"不是英雄技能名称字段：{field.key}")
        new_rawcode = int(self._coerce_memory_value("rawcode", value)) & 0xFFFFFFFF
        if not self._looks_like_rawcode(new_rawcode):
            raise ValueError(f"技能 rawcode 无效：{format_rawcode(new_rawcode)}")
        if uses_indexed_backend(self):
            return self._write_hero_skill_name_field_24268(
                pm, candidate, field, index, new_rawcode,
            )
        native = self._native_snapshot_for_candidate(candidate)
        if native is not None:
            identity = field.native_component_identity
            if not all(identity):
                raise RuntimeError("技能栏缺少绑定的英雄组件身份，停止写入")
            old_rawcode = int(field.value) & 0xFFFFFFFF
            if not old_rawcode:
                raise RuntimeError("当前英雄技能栏为空，没有可替换的技能")
            results = self._run_native_helper_ops(native.handle, (
                (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0, candidate.unit_address,
                 candidate.handle, candidate.owner_address),
                (self.NATIVE_HELPER_OP_REPLACE_HERO_SKILL, new_rawcode, *identity,
                 (index << 32) | old_rawcode),
            ))
            if (len(results) != 2 or any(result.last_error for result in results)
                    or results[1].result != new_rawcode):
                raise RuntimeError("DLL 英雄技能替换读回不一致")
            return replace(field, value=new_rawcode, write_address=0, write_type="", extra_writes=(),
                           native_write=True,
                           note=f"引擎从地图资源替换技能；当前等级={results[1].arg1}")
        if uses_indexed_backend(self):
            # Changing rawcode/class tags does not construct a new ability or
            # update engine-owned effect state. Never publish that as replacement.
            raise RuntimeError(
                "3.0 技能替换尚未接通引擎创建/替换接口；原技能及配置未修改"
            )
        components = self._selected_components(pm, candidate.owner_address)
        hero = components.get("hero")
        if hero is None:
            raise RuntimeError("当前选中单位没有英雄组件，不能写入英雄技能")
        _hero_wrapper, hero_data = hero
        name_address = hero_data + _al["hero"]["skill_name_legacy"] + index * 4
        cache_address = hero_data + _al["hero"]["skill_cache_legacy"] + index * 4
        configs: list[int] = []
        for slot_index in range(self.HERO_SKILL_SLOT_COUNT):
            try:
                configs.append(pm.read_u32(hero_data + _al["hero"]["skill_name_legacy"] + slot_index * 4))
            except OSError:
                configs.append(0)
        old_rawcode = configs[index] if index < len(configs) else 0
        mapped, ability_instances = self._hero_skill_instance_map_for_write(
            pm,
            candidate,
            configs,
        )
        instance = mapped.get(index)
        source_runtime_level: int | None = None
        runtime_needs_update = instance is not None and instance.rawcode != new_rawcode
        needs_runtime_replacement = old_rawcode != new_rawcode or runtime_needs_update
        if needs_runtime_replacement:
            if not old_rawcode:
                raise RuntimeError(
                    f"技能{index + 1}当前没有已学技能 rawcode，"
                    "没有可替换的运行时 ability 实例；为避免命令卡空格，本次不写入。"
                )
            source_ability_rawcode = instance.rawcode if instance is not None else old_rawcode
            source_skill_slots = [
                other_index + 1
                for other_index, rawcode in enumerate(configs)
                if rawcode == old_rawcode
            ]
            active_source_data = self._find_engine_ability_data(
                pm,
                candidate,
                source_ability_rawcode,
            )
            source_ability_slots = [
                other.slot
                for other in ability_instances
                if other.rawcode == source_ability_rawcode
                and (
                    (instance is not None and other.wrapper_address == instance.wrapper_address)
                    or (active_source_data and other.data_address == active_source_data)
                )
            ]
            ambiguous_source = len(source_skill_slots) != 1 or len(source_ability_slots) > 1
            if instance is None and not ambiguous_source:
                source_runtime_level = self._selected_ability_level_for_candidate(
                    pm,
                    candidate,
                    old_rawcode,
                )
            missing_learned_instance = instance is None and source_runtime_level != 0
            mismatched_instance = instance is not None and len(source_ability_slots) != 1
            if ambiguous_source or missing_learned_instance or mismatched_instance:
                details: list[str] = []
                if source_skill_slots:
                    details.append("技能栏" + ",".join(str(slot) for slot in source_skill_slots))
                if source_ability_slots:
                    details.append("能力实例" + ",".join(str(slot) for slot in source_ability_slots))
                if source_runtime_level is not None:
                    details.append(f"native等级{source_runtime_level}")
                raise RuntimeError(
                    f"技能{index + 1}当前 {format_rawcode(old_rawcode)} "
                    + ("同时出现在" + "；".join(details) if details else "没有匹配的运行时实例")
                    + "，无法唯一定位要替换的 ability 实例；为避免写错实例导致命令卡空格，本次不写入。"
                )
            duplicate_skill_slots = [
                other_index + 1
                for other_index, rawcode in enumerate(configs)
                if other_index != index and rawcode == new_rawcode
            ]
            duplicate_ability_slots = [
                other
                for other in ability_instances
                if (instance is None or other.wrapper_address != instance.wrapper_address)
                and other.rawcode == new_rawcode
            ]
            active_duplicate_data = self._find_engine_ability_data(pm, candidate, new_rawcode)
            duplicate_ability_slots = [
                other.slot
                for other in duplicate_ability_slots
                if active_duplicate_data and other.data_address == active_duplicate_data
            ]
            hidden_duplicate = (
                active_duplicate_data
                and not duplicate_ability_slots
                and (instance is None or active_duplicate_data != instance.data_address)
            )
            if duplicate_skill_slots or duplicate_ability_slots or hidden_duplicate:
                details: list[str] = []
                if duplicate_skill_slots:
                    details.append(
                        "技能栏" + ",".join(str(slot) for slot in duplicate_skill_slots)
                    )
                if duplicate_ability_slots:
                    details.append(
                        "能力实例" + ",".join(str(slot) for slot in duplicate_ability_slots)
                    )
                if hidden_duplicate:
                    details.append(f"隐藏运行时实例0x{active_duplicate_data:x}")
                raise RuntimeError(
                    f"{format_rawcode(new_rawcode)} 已存在于当前单位的" + "；".join(details) + "。"
                    "Warcraft III 的同 rawcode 已学技能不会生成第二个命令卡按钮，"
                    "强写会表现为目标格技能消失；请先把已有同名技能改成其它 rawcode。"
                )
        replacement_instance: AbilityInstance | None = None
        replacement_source = ""
        if instance is not None and needs_runtime_replacement:
            replacement_instance = self._replace_engine_ability_instance(
                pm,
                candidate,
                instance,
                new_rawcode,
            )
            replacement_source = (
                f"engine-replaced old_wrapper=0x{instance.wrapper_address:x} "
                f"new_wrapper=0x{replacement_instance.wrapper_address:x}"
            )

        pm.write_u32(name_address, new_rawcode)
        pm.write_u32(cache_address, new_rawcode)
        actions = [
            f"config/cache {format_rawcode(old_rawcode)}->{format_rawcode(new_rawcode)}",
        ]
        final_runtime_instance = replacement_instance or instance
        if instance is not None:
            if replacement_instance is not None:
                actions.append(
                    f"runtime {replacement_source} "
                    f"{instance.rawcode_text}->{format_rawcode(new_rawcode)} "
                    f"class={format_rawcode(replacement_instance.class_rawcode)}"
                )
            else:
                old_tag = pm.read_u64(instance.wrapper_tag_address)
                new_tag = ((new_rawcode & 0xFFFFFFFF) << 32) | (old_tag & 0xFFFFFFFF)
                pm.write_bytes(instance.wrapper_tag_address, struct.pack("<Q", new_tag))
                pm.write_u32(instance.rawcode_address, new_rawcode)
                if instance.mirror_rawcode_address:
                    pm.write_u32(instance.mirror_rawcode_address, new_rawcode)
                actions.append(
                    f"runtime wrapper=0x{instance.wrapper_address:x} "
                    f"{instance.rawcode_text}->{format_rawcode(new_rawcode)}"
                )
        else:
            if source_runtime_level == 0:
                actions.append("旧技能未学习(native等级0)，仅更新英雄技能栏配置")
            else:
                actions.append("未找到已学 ability 实例，仅更新英雄技能栏配置")

        time.sleep(0.05)
        final_config = pm.read_u32(name_address)
        final_cache = pm.read_u32(cache_address)
        if final_config != new_rawcode or final_cache != new_rawcode:
            raise RuntimeError(
                f"技能{index + 1}写入后读回 config={format_rawcode(final_config)} "
                f"cache={format_rawcode(final_cache)}，不是 {format_rawcode(new_rawcode)}"
            )
        if final_runtime_instance is not None:
            final_rawcode = pm.read_u32(final_runtime_instance.rawcode_address)
            if final_rawcode != new_rawcode:
                raise RuntimeError(
                    f"技能{index + 1}运行时实例读回 {format_rawcode(final_rawcode)}，"
                    f"不是 {format_rawcode(new_rawcode)}"
                )

        if self._refresh_selected_hero_command_card():
            actions.append("已触发英雄选择刷新")
        else:
            actions.append("写入成功；如游戏命令卡未立即刷新，请重新选择该英雄")
        return UnitMemoryField(
            key=field.key,
            label=field.label,
            value_type="rawcode",
            value=final_config,
            address=name_address,
            category=field.category,
            write_address=name_address,
            write_type="rawcode",
            note="；".join(actions),
            extra_writes=((cache_address, "rawcode"),),
        )


    def _inventory_slot_index_from_field_key(self, key: str) -> int | None:
        prefix = "inventory_slot_"
        if not key.startswith(prefix) or key.endswith("_charges"):
            return None
        slot_text = key[len(prefix) :]
        if not slot_text.isdigit():
            return None
        index = int(slot_text) - 1
        if not 0 <= index < 6:
            return None
        return index


    def _inventory_slot_charges_index_from_field_key(self, key: str) -> int | None:
        prefix = "inventory_slot_"
        suffix = "_charges"
        if not key.startswith(prefix) or not key.endswith(suffix):
            return None
        slot_text = key[len(prefix) : -len(suffix)]
        if not slot_text.isdigit():
            return None
        index = int(slot_text) - 1
        if not 0 <= index < 6:
            return None
        return index


    def _inventory_slot_snapshot(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        slot_index: int,
    ) -> InventoryItem | None:
        for item in self._inventory_items_from_candidate(pm, candidate):
            if item.slot == slot_index + 1:
                return item
        return None


    def _write_inventory_slot_field(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        field: UnitMemoryField,
        value: int | float | str,
    ) -> UnitMemoryField:
        slot_index = self._inventory_slot_index_from_field_key(field.key)
        if slot_index is None:
            raise RuntimeError(f"不是物品槽字段：{field.key}")
        new_rawcode = int(self._coerce_memory_value("rawcode", value)) & 0xFFFFFFFF
        if not self._looks_like_item_rawcode(new_rawcode):
            raise ValueError(f"物品 rawcode 无效：{format_rawcode(new_rawcode)}")
        if uses_indexed_backend(self):
            snapshot = self.item_batch_24268()
            targets = [row for row in snapshot.get("rows", ())
                       if int(row.get("rawcode", 0)) == int(candidate.unit_type_id)]
            if len(targets) != 1:
                raise RuntimeError("当前选中单位的物品槽身份不唯一，请重新选择目标单位")
            target = targets[0]
            engine = self._engine_instance_24268()
            kind = engine.equipment(rawcode=new_rawcode)["equipment_type"]
            if kind:
                equipped = engine.equipment(rawcode=new_rawcode, action=1,
                                            target_unit=int(target["handle"]))
                self._last_equipment_write = equipped
                slot_names = ("头部", "胸部", "手套", "靴子", "戒指", "戒指2", "主手", "副手", "饰品")
                return replace(field, value=new_rawcode, write_address=0, write_type="",
                               note=f"已装备到{slot_names[equipped['slot']]}装备槽；普通物品栏保持不变")
            result = self.item_batch_24268(
                7, new_rawcode, slot_index,
                target_unit_rawcode=int(candidate.unit_type_id),
                target_unit=int(target["handle"]),
                expected_item=int(target["before"][slot_index]["handle"]),
            )
            rows = [row for row in result.get("rows", ())
                    if int(row.get("handle", 0)) == int(target["handle"])]
            if len(rows) != 1 or rows[0]["after"][slot_index]["rawcode"] != new_rawcode:
                raise RuntimeError("3.0 当前引擎物品槽写入后读回不一致")
            item = rows[0]["after"][slot_index]
            return UnitMemoryField(
                key=field.key,
                label=field.label,
                value_type="rawcode",
                value=new_rawcode,
                address=field.address,
                category=field.category,
                write_address=0,
                write_type="",
                write_base=field.write_base,
                note=(f"当前引擎精确槽位替换；slot={slot_index + 1} "
                      f"item=0x{int(item['handle']):x}"),
                extra_writes=field.extra_writes,
            )

        previous = self._native_snapshot_for_candidate(candidate)
        try:
            candidate = self._refresh_native_candidate(candidate)
        except TimeoutError as exc:
            # Inventory identity was not confirmed. Never reinterpret this as
            # a basic-vitals request or retry a potentially partial operation.
            exc.add_note("Inventory identity refresh timed out; no replacement or basic-field retry was issued")
            raise
        current = self._native_snapshot_for_candidate(candidate)
        if previous is not None:
            names = ("item_handles", "item_addresses", "item_ids", "item_full_handles")
            if current is None or any(getattr(previous, name)[slot_index] != getattr(current, name)[slot_index]
                                      for name in names):
                raise RuntimeError("Native inventory item changed before writing")
        if current is not None:
            components = None
        else:
            components = self._selected_components(pm, candidate.owner_address)
            if "inventory" not in components:
                raise RuntimeError("当前选中单位没有物品栏组件")

        items = self._inventory_items_from_candidate(pm, candidate, components)
        old_snapshot = next((item for item in items if item.slot == slot_index + 1), None)
        if candidate.native_snapshot is not None and (len(items) != 6 or old_snapshot is None):
            raise RuntimeError("当前 native 快照已经失效，请重新读取选中单位")
        if candidate.native_snapshot is not None and not old_snapshot.native_slot:
            raise RuntimeError("当前选中单位没有物品栏组件")
        if current is not None and (old_snapshot.handle, old_snapshot.item_address, old_snapshot.rawcode) != (
                current.item_full_handles[slot_index], current.item_addresses[slot_index], current.item_ids[slot_index]):
            raise RuntimeError("Native inventory item changed before writing")
        before_by_slot = {item.slot: item.rawcode for item in items}
        old_rawcode = old_snapshot.rawcode if old_snapshot is not None else 0
        actions: list[str] = []
        if old_rawcode == new_rawcode:
            actions.append("物品 rawcode 未变化")
        else:
            removed_handle, added_item, native_rawcode = self._set_inventory_slot_item_via_native_handler(
                pm,
                candidate,
                slot_index,
                new_rawcode,
            )
            self._item_object_cache.clear()
            actions.append(
                f"内部物品栏替换 {format_rawcode(old_rawcode) if old_rawcode else '空'}"
                f"->{format_rawcode(native_rawcode)} removed=0x{removed_handle:x} "
                f"new_item=0x{added_item:x}"
            )
            actions.append("未交换其他物品槽")

        final_snapshot: InventoryItem | None = None
        after_items: list[InventoryItem] = []
        native_readback = candidate.native_snapshot is not None
        for attempt in range(1 if native_readback else 6):
            if native_readback:
                candidate = self._refresh_native_candidate(candidate)
            else:
                time.sleep(0.03 if attempt == 0 else 0.08)
            self._item_object_cache.clear()
            after_items = self._inventory_items_from_candidate(pm, candidate, components)
            final_snapshot = next((item for item in after_items if item.slot == slot_index + 1), None)
            if final_snapshot is not None and final_snapshot.rawcode == new_rawcode:
                break
        if native_readback and len(after_items) != 6:
            raise RuntimeError("当前 native 快照已经失效，请重新读取选中单位")
        after_by_slot = {item.slot: item.rawcode for item in after_items}
        changed_other_slots = [
            slot
            for slot, before_rawcode in before_by_slot.items()
            if slot != slot_index + 1 and after_by_slot.get(slot, before_rawcode) != before_rawcode
        ]
        if changed_other_slots:
            raise RuntimeError(
                "物品写入影响了非目标槽：" + ", ".join(str(slot) for slot in changed_other_slots)
            )
        final_rawcode = final_snapshot.rawcode if final_snapshot is not None else 0
        final_handle = final_snapshot.handle if final_snapshot is not None else 0
        if final_rawcode != new_rawcode:
            raise RuntimeError(
                f"物品槽{slot_index + 1}写入后读回 {format_rawcode(final_rawcode) if final_rawcode else '空'}，"
                f"不是 {format_rawcode(new_rawcode)}"
            )
        final_address = field.address
        if final_snapshot is not None and final_snapshot.rawcode_address:
            final_address = final_snapshot.rawcode_address
        if final_snapshot is not None:
            note = (
                f"handle=0x{final_snapshot.handle:x} item=0x{final_snapshot.item_address:x}; "
                f"mirror=0x{final_snapshot.mirror_rawcode_address:x} "
                f"ability={format_rawcode(final_snapshot.ability_rawcode) if final_snapshot.ability_rawcode else '0'}; "
                "通过内部物品栏函数创建/替换本槽 item，未交换其他物品槽"
            )
        else:
            note = field.note
            if final_handle:
                handle_note = f"handle=0x{final_handle:x}"
                note = (note + "；" if note else "") + handle_note
        if actions:
            note = (note + "；" if note else "") + "；".join(actions)
        return UnitMemoryField(
            key=field.key,
            label=field.label,
            value_type="rawcode",
            value=final_rawcode,
            address=final_address,
            category=field.category,
            write_address=final_address,
            write_type=field.write_type,
            write_base=field.write_base,
            note=note,
            extra_writes=field.extra_writes,
        )


    def _write_inventory_slot_charges_field(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        field: UnitMemoryField,
        value: int | float | str,
    ) -> UnitMemoryField:
        slot_index = self._inventory_slot_charges_index_from_field_key(field.key)
        if slot_index is None:
            raise RuntimeError(f"不是物品数量字段：{field.key}")
        new_charges = int(self._coerce_memory_value("i32", value))
        if new_charges < 0:
            new_charges = 0
        native = self._native_snapshot_for_candidate(candidate)
        if native is not None:
            # Keep the item chosen by this display bound across the targeted
            # refresh; replacing an item in the same slot must not retarget it.
            expected = (native.item_handles[slot_index], native.item_addresses[slot_index],
                        native.item_ids[slot_index], native.item_full_handles[slot_index])
            if not all(expected):
                raise RuntimeError("Native inventory slot has no resolved item")
            candidate = self._refresh_native_candidate(candidate)
            current = self._native_snapshot_for_candidate(candidate)
            if current is None or expected != (current.item_handles[slot_index],
                                               current.item_addresses[slot_index], current.item_ids[slot_index],
                                               current.item_full_handles[slot_index]):
                raise RuntimeError("Native inventory item changed before writing")
            results = self._run_native_helper_ops(current.handle, (
                (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0, candidate.unit_address,
                 candidate.handle, candidate.owner_address),
                (self.NATIVE_HELPER_OP_SET_BOUND_ITEM_CHARGES, slot_index,
                 expected[1], expected[0], new_charges),
                (self.NATIVE_HELPER_OP_BOUND_ITEM_IDENTITY, 0, expected[3], 0, 0),
            ))
            actual = int(results[1].result)
            if actual != new_charges:
                raise RuntimeError("Native item quantity readback differs from request")
            return replace(field, value=actual, write_address=0, write_type="", native_write=True,
                           note="native item quantity verified in game callback")
        if new_charges > 999:
            raise ValueError("物品数量不能超过 999")

        components = self._selected_components(pm, candidate.owner_address)
        if "inventory" not in components:
            raise RuntimeError("当前选中单位没有物品栏组件")
        snapshot = next(
            (
                item
                for item in self._inventory_items_from_candidate(pm, candidate, components)
                if item.slot == slot_index + 1
            ),
            None,
        )
        if snapshot is None or not snapshot.item_address or not snapshot.charges_address:
            raise RuntimeError(f"物品槽{slot_index + 1}为空或未解析 item 对象，不能写数量")

        old_charges = snapshot.charges
        old_flags = pm.read_u32(snapshot.item_address + self.ITEM_CHARGES_FLAG_OFFSET)
        if uses_indexed_backend(self):
            pm.write_i32(snapshot.charges_address, new_charges)
            if pm.read_i32(snapshot.charges_address) != new_charges:
                raise RuntimeError("物品数量直接写入读回不一致")
        else:
            try:
                self._set_item_charges_via_native_handler(pm, candidate, snapshot, new_charges)
            except (RuntimeError, TimeoutError) as exc:
                self._native_selection_unavailable = True
                self._native_fallback_reason = f"item charge native failure: {exc}"
                pm.write_i32(snapshot.charges_address, new_charges)
                if pm.read_i32(snapshot.charges_address) != new_charges:
                    raise RuntimeError("物品数量回退写入读回不一致") from exc
        time.sleep(0.05)

        final_snapshot = next(
            (
                item
                for item in self._inventory_items_from_candidate(pm, candidate, components)
                if item.slot == slot_index + 1
            ),
            None,
        )
        final_charges = final_snapshot.charges if final_snapshot is not None else -1
        if final_charges != new_charges:
            raise RuntimeError(
                f"物品槽{slot_index + 1}数量写入后读回 {final_charges}，不是 {new_charges}"
            )
        if final_snapshot is not None and final_snapshot.item_address:
            final_flags = pm.read_u32(final_snapshot.item_address + self.ITEM_CHARGES_FLAG_OFFSET)
        else:
            final_flags = old_flags
        refresh_note = ""
        if "hero" in components:
            if self._refresh_selected_hero_command_card():
                refresh_note = "; 已触发英雄选择刷新"
            else:
                refresh_note = "; 写入成功，如物品栏未立即刷新请重新选择该英雄"
        return UnitMemoryField(
            key=field.key,
            label=field.label,
            value_type=field.value_type,
            value=final_charges,
            address=field.address,
            category=field.category,
            write_address=field.write_address,
            write_type=field.write_type,
            write_base=field.write_base,
            note=(
                f"SetItemCharges {old_charges}->{final_charges}; "
                f"item charges offset=0x{self.ITEM_CHARGES_OFFSET:x}; "
                f"flags 0x{old_flags:x}->0x{final_flags:x}"
                f"{refresh_note}"
            ),
            extra_writes=field.extra_writes,
        )


    def _component_field_write_op(self, field: UnitMemoryField, value: int | float | str) -> tuple[int, int, int, int, int]:
        code, _component, kind = NATIVE_COMPONENT_FIELD_SPECS[field.key]
        if not all(field.native_component_identity) or field.value_type != kind:
            raise RuntimeError("Incomplete native component field identity")
        if field.key in {"base_strength", "base_agility"}:
            try:
                target = int(str(value).strip())
            except (ValueError, TypeError) as exc:
                raise ValueError("基础力量、敏捷必须是 0～1000000 的整数") from exc
            if not 0 <= target <= 1_000_000:
                raise ValueError("基础力量、敏捷必须是 0～1000000 的整数")
            return (self.NATIVE_HELPER_OP_SET_BOUND_HERO_BASE, int(field.key == "base_agility"),
                    *field.native_component_identity, target)
        coerced = self._coerce_memory_value(kind, value)
        if kind == "i32" and not -(1 << 31) <= coerced < (1 << 31):
            raise ValueError("Native component integer is outside int32 range")
        bits = self._float_bits(coerced) if kind == "f32" else int(coerced) & 0xFFFFFFFF
        return (self.NATIVE_HELPER_OP_WRITE_COMPONENT_FIELDS, code, *field.native_component_identity, bits)


    def _write_true_attack_speed_field(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        field: UnitMemoryField,
        value: int | float | str,
    ) -> UnitMemoryField:
        from war3_game_profile import current_profile
        _al = current_profile().section("layouts")
        try:
            target_aps = float(str(value).strip()) if isinstance(value, str) else float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("当前引擎实际攻速必须是 0.001 到 1000 的有限数值") from exc
        if not math.isfinite(target_aps) or not 0.001 <= target_aps <= 1000.0:
            raise ValueError("当前引擎实际攻速必须是 0.001 到 1000 的有限数值")
        components = self._selected_components(pm, candidate.owner_address)
        attack = components.get("attack")
        if attack is None or field.key != "attack1_true_speed":
            raise RuntimeError("当前单位没有经过校验的第一攻击组件")
        attack_data = attack[1]
        if field.address != attack_data + _al["attack"]["cooldown"]:
            raise RuntimeError("当前引擎实际攻速字段绑定的攻击组件已经变化，请重新读取")
        result = self.attack_speed_24268(candidate, attack_data, target_aps, 0)
        actual = float(result["after_true_aps"])
        return replace(
            field,
            value=actual,
            address=attack_data + _al["attack"]["cooldown"],
            write_address=0,
            write_type="",
            native_write=True,
            note=(
                f"游戏接口读回确认：当前引擎实际攻速 {result['true_aps']:.6g}->{actual:.6g} 次/秒；"
                f"基础冷却 {result['base_cooldown']:.6g}->{result['after_base_cooldown']:.6g} 秒"
            ),
        )


    def _write_native_component_fields(self, candidate: UnitCandidate,
                                      requests: list[tuple[int, UnitMemoryField, tuple[int, int, int, int, int]]]) -> dict[int, UnitMemoryField]:
        native = self._native_snapshot_for_candidate(candidate)
        if native is None:
            raise RuntimeError("Native component write requires a bound unit")
        written = {}
        groups = {}
        for entry in requests:
            groups.setdefault(entry[2][0], []).append(entry)
        batches = [group[start:start + self.NATIVE_HELPER_MAX_OPS - 1]
                   for group in groups.values() for start in range(0, len(group), self.NATIVE_HELPER_MAX_OPS - 1)]
        for batch in batches:
            results = self._run_native_helper_ops(native.handle, (
                (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0, candidate.unit_address,
                 candidate.handle, candidate.owner_address), *(entry[2] for entry in batch)))
            if len(results) != len(batch) + 1 or any(result.last_error for result in results):
                raise RuntimeError("Incomplete native component write result")
            for (index, field, op), result in zip(batch, results[1:]):
                if result.kind != op[0] or result.result != op[4]:
                    raise RuntimeError("Native component readback differs from request")
                value = self._float_from_bits(result.result) if field.value_type == "f32" else ctypes.c_int32(result.result).value
                written[index] = replace(field, value=value)
        return written


    def _write_unit_fields_to_candidate(
        self,
        pm: ProcessMemory | None,
        candidate: UnitCandidate,
        specs: Iterable[MemoryWriteSpec],
    ) -> list[UnitMemoryField]:
        specs = list(specs)
        if not specs:
            return []
        if pm is None and uses_indexed_backend(self):
            with self._process_memory(write=True) as memory:
                return self._write_unit_fields_to_candidate(memory, candidate, specs)
        # Resolve and validate all requested fields before any mutation. Native
        # basic fields are batched once; their writability does not depend on an
        # external property address being available.
        native_bound = self._native_snapshot_for_candidate(candidate) is not None
        needs_fields = native_bound or any(self._skill_index_from_field_key(
            self.FIELD_KEY_ALIASES.get(spec.label, spec.label)) is None for spec in specs)
        fields = self._unit_fields_from_candidate(pm, candidate) if needs_fields else []
        by_key = {field.key: field for field in fields}
        by_label = {field.label: field for field in fields}
        resolved = []
        basic_values = {"target_hp": None, "target_mp": None}
        basic_indices = []
        component_requests = []
        component_keys = set()
        seen_basic = set()
        live_engine_context = bool(getattr(self, "pid", 0) and getattr(self, "hwnd", 0))
        for index, spec in enumerate(specs):
            direct_key = self.FIELD_KEY_ALIASES.get(spec.label, spec.label)
            if not native_bound and self._skill_index_from_field_key(direct_key) is not None:
                field = UnitMemoryField(key=direct_key, label=direct_key, value_type="rawcode",
                                        value=0, address=0, category="技能", write_address=1, write_type="rawcode")
            else:
                field = by_key.get(direct_key) or by_label.get(spec.label)
            if field is None:
                raise RuntimeError(f"当前选中单位没有字段：{spec.label}")
            if not field.writable:
                raise RuntimeError(f"字段不可写：{field.label}")
            if native_bound:
                # A native snapshot must never authorize an external address
                # write. Check the entire request before submitting any setter.
                supported = field.native_write and (
                    field.key in self.NATIVE_BASIC_FIELD_ARGUMENTS
                    or (field.key in NATIVE_COMPONENT_FIELD_SPECS and all(field.native_component_identity))
                    or (live_engine_context and field.key in CURRENT_ENGINE_UNIT_STAT_FIELDS
                        and all(field.native_component_identity))
                    or ((field.key == "intelligence_total" or self._skill_index_from_field_key(field.key) is not None)
                        and all(field.native_component_identity))
                    or self._inventory_slot_charges_index_from_field_key(field.key) is not None
                    or self._inventory_slot_index_from_field_key(field.key) is not None
                    or field.key.startswith("stat3_"))
                if not supported:
                    raise RuntimeError("Native field has no bound setter: " + field.key)
            resolved.append((field, spec))
            if (field.key in NATIVE_COMPONENT_FIELD_SPECS
                    and (not live_engine_context or field.key not in CURRENT_ENGINE_UNIT_STAT_FIELDS)
                    and field.native_write and all(field.native_component_identity)):
                if field.key in component_keys:
                    raise ValueError("Duplicate native component field")
                component_keys.add(field.key)
                component_requests.append((index, field, self._component_field_write_op(field, spec.value)))
            if field.key in self.NATIVE_BASIC_FIELD_ARGUMENTS:
                if field.key in seen_basic:
                    raise ValueError("Duplicate native field in one write request")
                seen_basic.add(field.key)
                argument, _attribute = self.NATIVE_BASIC_FIELD_ARGUMENTS[field.key]
                basic_values[argument] = coerce_finite_float32(spec.value)
                basic_indices.append(index)

        written = {}
        if basic_indices:
            # Read back basic values without rebinding the request's inventory
            # identity. A trigger may replace an item during HP/position writes;
            # subsequent item operations must still validate the original item.
            basic_readback = self._write_basic_unit_values_to_candidate(pm, candidate, **basic_values)
            snapshot = self._native_snapshot_for_candidate(basic_readback)
            if snapshot is None:
                if native_bound or not uses_indexed_backend(self):
                    raise RuntimeError("No native snapshot after basic field write")
                from war3_basic_fields import FIELDS
                for index in basic_indices:
                    field, _spec = resolved[index]
                    address = getattr(basic_readback, FIELDS[field.key][2])
                    written[index] = replace(field, value=pm.read_f32(address))
            else:
                for index in basic_indices:
                    field, _spec = resolved[index]
                    _argument, attribute = self.NATIVE_BASIC_FIELD_ARGUMENTS[field.key]
                    written[index] = replace(field, value=getattr(snapshot, attribute),
                                             write_address=0, write_type="", native_write=True)
        if component_requests:
            written.update(self._write_native_component_fields(candidate, component_requests))
        for index, (field, spec) in enumerate(resolved):
            if index in written:
                continue
            if live_engine_context and field.key in CURRENT_ENGINE_UNIT_STAT_FIELDS and field.native_write:
                written[index] = self._write_unit_stat_field_24268(candidate, field, spec.value)
            elif field.key.startswith("stat3_") and field.native_write:
                detail_key = field.key[len("stat3_"):]
                actual = self.set_stat_detail_24268(detail_key, spec.value, candidate)
                written[index] = replace(field, value=actual)
            elif field.key == "attack1_true_speed":
                written[index] = self._write_true_attack_speed_field(pm, candidate, field, spec.value)
            elif field.key == "intelligence_total":
                written[index] = self._write_hero_intelligence_field(pm, candidate, field, spec.value)
            elif self._skill_index_from_field_key(field.key) is not None:
                written[index] = self._write_hero_skill_name_field(pm, candidate, field, spec.value)
            elif self._inventory_slot_charges_index_from_field_key(field.key) is not None:
                written[index] = self._write_inventory_slot_charges_field(pm, candidate, field, spec.value)
            elif self._inventory_slot_index_from_field_key(field.key) is not None:
                written[index] = self._write_inventory_slot_field(pm, candidate, field, spec.value)
            else:
                if field.native_write:
                    raise RuntimeError("No native setter for this field")
                self._write_memory_value(pm, field.write_address, field.write_type, spec.value)
                for extra_address, extra_type in field.extra_writes:
                    self._write_memory_value(pm, extra_address, extra_type, spec.value)
                new_value = self._read_memory_value(pm, field.address, field.value_type)
                written[index] = replace(field, value=new_value)
        return [written[index] for index in range(len(resolved))]


    def write_selected_unit_fields(self, specs: Iterable[MemoryWriteSpec]) -> list[UnitMemoryField]:
        specs = list(specs)
        if not specs:
            return []
        candidate = self.locate_selected_unit_by_handle()
        return self._write_unit_fields_to_candidate(None, candidate, specs)


    def write_selected_unit_field(self, key: str, value: int | float | str) -> UnitMemoryField:
        fields = self.write_selected_unit_fields([MemoryWriteSpec(key, 0, "", value)])
        return fields[0]


    def write_unit_field_by_identity(
        self,
        handle: int,
        owner: int,
        unit: int,
        key: str,
        value: int | float | str,
    ) -> UnitMemoryField:
        candidate = self._candidate_from_display_identity(
            None, handle, owner, unit,
            f"manual_candidate handle=0x{handle:x} owner=0x{owner:x} unit=0x{unit:x}", 850,
            registry_required=not str(key).startswith("inventory_slot_"))
        if candidate is None:
            raise RuntimeError("候选单位已经失效，请重新读取候选列表")
        if uses_indexed_backend(self):
            with self._process_memory(write=True) as memory:
                return self._write_unit_fields_to_candidate(
                    memory, candidate, [MemoryWriteSpec(key, 0, "", value)]
                )[0]
        return self._write_unit_fields_to_candidate(None, candidate, [MemoryWriteSpec(key, 0, "", value)])[0]


    def write_unit_field_by_identity_win10(
        self,
        handle: int,
        owner: int,
        unit: int,
        key: str,
        value: int | float | str,
    ) -> UnitMemoryField:
        # Compatibility entry points share the native object-table identity path.
        return self.write_unit_field_by_identity(handle, owner, unit, key, value)


    def locate_current_selected_unit(self) -> tuple[VisibleUnitPanel, UnitCandidate]:
        candidate = self.locate_selected_unit_by_handle()
        return self._panel_from_candidate(None, candidate), candidate


    def _write_basic_unit_values_to_candidate(
        self,
        pm: ProcessMemory | None,
        candidate: UnitCandidate,
        target_hp: float | None,
        target_mp: float | None,
        max_hp: float | None = None,
        max_mp: float | None = None,
        target_x: float | None = None,
        target_y: float | None = None,
        target_hp_regen: float | None = None,
        target_mp_regen: float | None = None,
    ) -> UnitCandidate:
        target_hp = coerce_finite_float32(target_hp) if target_hp is not None else None
        target_mp = coerce_finite_float32(target_mp) if target_mp is not None else None
        max_hp = coerce_finite_float32(max_hp) if max_hp is not None else None
        max_mp = coerce_finite_float32(max_mp) if max_mp is not None else None
        target_x = coerce_finite_float32(target_x) if target_x is not None else None
        target_y = coerce_finite_float32(target_y) if target_y is not None else None
        target_hp_regen = (
            coerce_finite_float32(target_hp_regen)
            if target_hp_regen is not None
            else None
        )
        target_mp_regen = (
            coerce_finite_float32(target_mp_regen)
            if target_mp_regen is not None
            else None
        )
        # Validate the entire request before submitting any write. The helper
        # accepts bounded real states and integer maximums, not arbitrary f32s.
        for value in (target_hp, target_mp):
            if value is not None and not -100_000_000 <= value <= 100_000_000:
                raise ValueError("Native current vital is outside the supported range")
        for value, minimum in ((max_hp, 1), (max_mp, 0)):
            if value is not None and not minimum <= value <= 1_000_000_000:
                raise ValueError("Native maximum vital is outside the supported range")
        for value in (target_x, target_y):
            if value is not None and abs(value) > 1_000_000:
                raise ValueError("Native position is outside the supported range")
        regen_mask = int(target_hp_regen is not None) | (int(target_mp_regen is not None) << 1)
        if all(value is None for value in (target_hp, target_mp, max_hp, max_mp,
                                           target_x, target_y)) and not regen_mask:
            return candidate

        native = self._native_snapshot_for_candidate(candidate)
        if uses_indexed_backend(self) and native is None:
            from war3_object_registry import ObjectRegistry24268
            from war3_basic_fields import write_basic_fields
            close_pm = pm is None
            memory = pm or self._process_memory(write=True)
            try:
                if target_x is not None or target_y is not None:
                    selected = self._classic_selection_candidates(memory)
                    matching = [
                        selected_candidate
                        for selected_candidate, _handle in selected
                        if (
                            selected_candidate.handle == candidate.handle
                            and selected_candidate.owner_address == candidate.owner_address
                            and selected_candidate.unit_address == candidate.unit_address
                        )
                    ]
                    if len(selected) != 1 or len(matching) != 1:
                        raise RuntimeError("坐标字段写入必须只选中目标单位")
                    current_x = memory.read_f32(candidate.x_address)
                    current_y = memory.read_f32(candidate.y_address)
                    requested_x = current_x if target_x is None else target_x
                    requested_y = current_y if target_y is None else target_y
                    result = self.position_batch_24268(
                        self._float_bits(requested_x), self._float_bits(requested_y),
                    )
                    rows = tuple(result.get("rows", ()))
                    if (int(result.get("count", len(rows))) != 1
                            or len(rows) != 1
                            or int(result.get("completed", -1)) != 1
                            or int(result.get("changed", -1)) != 1):
                        raise RuntimeError("坐标字段引擎写入返回不完整")
                    actual_x = self._float_from_bits(int(rows[0]["actual_x_bits"]))
                    actual_y = self._float_from_bits(int(rows[0]["actual_y_bits"]))
                    if not all(math.isfinite(value) for value in (actual_x, actual_y)):
                        raise RuntimeError("坐标字段引擎写入坐标读回无效")
                    target_x = target_y = None
                registry = self._classic_object_registry or ObjectRegistry24268.attach(memory)
                self._classic_object_registry = registry
                session = getattr(self,"_game_session",None)
                if session is not None:
                    from war3_external_backend import ExternalMemoryBackend
                    writer = ExternalMemoryBackend(session).write_basic_fields
                else:
                    writer = write_basic_fields
                writer(memory, registry, candidate, {
                    "hp_current": target_hp, "hp_max": max_hp,
                    "mp_current": target_mp, "mp_max": max_mp,
                    "x": target_x, "y": target_y,
                    "hp_regen": target_hp_regen, "mp_regen": target_mp_regen,
                })
                return candidate
            finally:
                if close_pm:
                    memory.close()
        if native is None:
            candidate = self._candidate_from_display_identity(
                pm, candidate.handle, candidate.owner_address, candidate.unit_address,
                candidate.note, candidate.score,
            )
            if candidate is None:
                raise RuntimeError("No native handle for the requested unit identity")
        candidate = self._refresh_native_candidate(candidate)
        native = self._native_snapshot_for_candidate(candidate)
        if native is None or not native.handle:
            raise RuntimeError("No native handle for the requested unit identity")
        for target, current in ((target_hp_regen, native.hp_regen), (target_mp_regen, native.mp_regen)):
            if target is not None and current is None:
                raise RuntimeError("Current unit has no writable regeneration field")

        # Build one command containing all setters in order. The command header
        # takes the JASS handle; candidate.handle is the engine object identity.
        requests = []
        for current, maximum, old_maximum, state, setter in (
            (target_hp, max_hp, native.hp_max, 0, "BlzSetUnitMaxHP"),
            (target_mp, max_mp, native.mp_max, 2, "BlzSetUnitMaxMana"),
        ):
            if current is None and maximum is None:
                continue
            limit = float(maximum) if maximum is not None else old_maximum
            if current is not None and current > limit:
                limit = math.ceil(current)
            if not math.isfinite(limit) or not 0 <= limit <= 1_000_000_000:
                raise ValueError("Native maximum vital is outside the supported range")
            if maximum is not None or limit != old_maximum:
                requests.append((setter, self.NATIVE_HELPER_OP_JASS_SET_UNIT_INT,
                                 0, int(round(limit)), 0))
            if current is not None:
                requests.append(("SetUnitState", self.NATIVE_HELPER_OP_JASS_SET_UNIT_STATE,
                                 state, self._float_bits(current), 0))
        if target_x is not None or target_y is not None:
            x = native.x if target_x is None else target_x
            y = native.y if target_y is None else target_y
            if not all(math.isfinite(v) and abs(v) <= 1_000_000 for v in (x, y)):
                raise ValueError("Native position is outside the supported range")
            requests.append(("SetUnitPosition", self.NATIVE_HELPER_OP_JASS_SET_UNIT_POSITION,
                             self._float_bits(x), self._float_bits(y), 0))
        ops = ()
        if requests:
            handlers = self._query_native_table_handlers(tuple(dict.fromkeys(row[0] for row in requests)))
            ops = tuple((kind, rawcode, handlers[name].handler_address, arg0, arg1)
                        for name, kind, rawcode, arg0, arg1 in requests)
        if regen_mask:
            ops += ((self.NATIVE_HELPER_OP_SET_UNIT_REGEN, regen_mask, 0,
                     self._float_bits(target_hp_regen or 0.0), self._float_bits(target_mp_regen or 0.0)),)
        if ops:
            guard = (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0,
                     candidate.unit_address, candidate.handle, candidate.owner_address)
            self._run_native_helper_ops(native.handle, (guard, *ops))
        return self._refresh_native_candidate(candidate)


    def set_selected_unit(
        self,
        current_hp: float,
        current_mp: float | None,
        target_hp: float | None,
        target_mp: float | None,
        max_hp: float | None = None,
        max_mp: float | None = None,
        target_x: float | None = None,
        target_y: float | None = None,
        target_hp_regen: float | None = None,
        target_mp_regen: float | None = None,
    ) -> UnitCandidate:
        candidate = self.locate_selected_unit_by_handle()
        return self._write_basic_unit_values_to_candidate(
            None, candidate, target_hp, target_mp, max_hp, max_mp,
            target_x, target_y, target_hp_regen, target_mp_regen)


    def set_unit_by_identity(
        self,
        handle: int,
        owner: int,
        unit: int,
        current_hp: float,
        current_mp: float | None,
        target_hp: float | None,
        target_mp: float | None,
        max_hp: float | None = None,
        max_mp: float | None = None,
        target_x: float | None = None,
        target_y: float | None = None,
        target_hp_regen: float | None = None,
        target_mp_regen: float | None = None,
    ) -> UnitCandidate:
        candidate = self._candidate_from_display_identity(
            None, handle, owner, unit,
            f"manual_candidate handle=0x{handle:x} owner=0x{owner:x} unit=0x{unit:x}", 850)
        if candidate is None:
            raise RuntimeError("候选单位已经失效，请重新读取候选列表")
        return self._write_basic_unit_values_to_candidate(
            None, candidate, target_hp, target_mp, max_hp, max_mp,
            target_x, target_y, target_hp_regen, target_mp_regen)


    def set_unit_by_identity_win10(
        self,
        handle: int,
        owner: int,
        unit: int,
        current_hp: float,
        current_mp: float | None,
        target_hp: float | None,
        target_mp: float | None,
        max_hp: float | None = None,
        max_mp: float | None = None,
        target_x: float | None = None,
        target_y: float | None = None,
        target_hp_regen: float | None = None,
        target_mp_regen: float | None = None,
    ) -> UnitCandidate:
        # Compatibility entry points share the native object-table identity path.
        return self.set_unit_by_identity(handle, owner, unit, current_hp, current_mp, target_hp, target_mp, max_hp, max_mp, target_x, target_y, target_hp_regen, target_mp_regen)
