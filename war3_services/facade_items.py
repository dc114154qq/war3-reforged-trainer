"""items compatibility API; host primitives are explicitly bound once at composition."""
from __future__ import annotations
from contextlib import contextmanager

class ItemsFacade:
    def create_all_loaded_items(
        self,
        limit: int = 0,
        *,
        dry_run: bool = False,
    ) -> tuple[int, int, tuple[int, ...]]:
        item_limit = int(limit)
        if not 0 <= item_limit <= 100000:
            raise ValueError("创建物品测试上限必须在 0 到 100000 之间")
        if getattr(self, "_native_selection_unavailable", False):
            from war3_casc_catalog_24268 import ITEM_RAWCODES
            from war3_item_catalog_protocol import ACTION_CREATE_LIST
            rawcodes = tuple(int.from_bytes(rawcode.encode("ascii"), "big") for rawcode in ITEM_RAWCODES)
            if item_limit:
                rawcodes = rawcodes[:item_limit]
            if not rawcodes:
                raise RuntimeError("当前 3.0 资源目录为空")
            if dry_run:
                return len(rawcodes), 0, ()
            x, y = self.query_mouse_world_position()
            x_bits, y_bits = self._float_bits(x), self._float_bits(y)
            result = self._engine_instance_24268().item_catalog(
                ACTION_CREATE_LIST,
                0,
                x_bits,
                y_bits,
                rawcodes=rawcodes,
                dry_run=dry_run,
            )
            total = int(result["total"])
            created = int(result["created"])
            handles = tuple(int(handle) for handle in result.get("handles", ()))
            if total != len(rawcodes):
                raise RuntimeError(
                    f"资源目录返回 {total} 个，期望 {len(rawcodes)} 个"
                )
            if not dry_run and len(handles) != created:
                raise RuntimeError(
                    f"物品创建返回 {created} 个，但句柄列表有 {len(handles)} 个"
                )
            return total, created, handles
        handlers = self._elephant_handlers(None, ("ChooseRandomItem", "CreateItem"))
        encoded_limit = item_limit | (0x80000000 if dry_run else 0)
        result = self._run_native_helper_ops(
            0,
            ((
                self.NATIVE_HELPER_OP_CREATE_ALL_ITEMS,
                encoded_limit,
                handlers["ChooseRandomItem"].handler_address,
                handlers["CreateItem"].handler_address,
                0,
            ),),
            timeout_ms=120000,
        )[0]
        packed = int(result.result)
        created = packed & 0xFFFFFFFF
        total = (packed >> 32) & 0xFFFFFFFF
        if not total:
            raise RuntimeError("运行时物品数据库为空")
        handles = tuple(int(handle) for handle in result.extra_results if handle)
        if not dry_run and len(handles) != created:
            raise RuntimeError(
                f"物品创建返回 {created} 个，但句柄列表有 {len(handles)} 个"
            )
        return total, created, handles


    def remove_item_handle(self, item_handle: int) -> None:
        self.remove_item_handles((item_handle,))


    def remove_item_handles(self, item_handles: Iterable[int]) -> int:
        handles = tuple(int(handle) for handle in item_handles if int(handle))
        if not handles:
            return 0
        if getattr(self, "_native_selection_unavailable", False):
            from war3_item_catalog_protocol import ACTION_REMOVE
            removed = 0
            for start in range(0, len(handles), 100000):
                result = self._engine_instance_24268().item_catalog(
                    ACTION_REMOVE,
                    handles=handles[start : start + 100000],
                )
                removed += int(result["removed"])
            return removed
        handler = self._elephant_handlers(None, ("RemoveItem",))["RemoveItem"].handler_address
        removed = 0
        for start in range(0, len(handles), 47):
            batch = handles[start : start + 47]
            first = batch[0]
            second = batch[1] if len(batch) > 1 else 0
            ops: list[tuple[int, int, int, int, int]] = [(
                self.NATIVE_HELPER_OP_REMOVE_ITEM_HANDLES,
                len(batch),
                handler,
                first,
                second,
            )]
            remaining = batch[2:]
            for offset in range(0, len(remaining), 3):
                triple = remaining[offset : offset + 3]
                ops.append((
                    self.NATIVE_HELPER_OP_REMOVE_ITEM_HANDLES_ARG,
                    0,
                    triple[0],
                    triple[1] if len(triple) > 1 else 0,
                    triple[2] if len(triple) > 2 else 0,
                ))
            removed += int(self._run_native_helper_ops(0, tuple(ops))[0].result)
        return removed


    def add_item_to_selected_unit(self, rawcode: int | str) -> int:
        item_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        if not item_rawcode:
            raise ValueError("物品 ID 无效")
        if getattr(self, "_native_selection_unavailable", False):
            result = self.item_batch_24268(1, item_rawcode)
            rows = tuple(result.get("rows", ()))
            if not rows:
                raise RuntimeError("当前选中单位没有可添加物品的单位")
            created = int(rows[0].get("created", 0))
            if not created:
                raise RuntimeError("物品创建返回了无效句柄")
            return created
        return int(self._run_bound_item_create(item_rawcode).arg0)


    def _run_bound_item_create(self, rawcode: int) -> NativeHelperOpResult:
        candidate, unit_handle = self._direct_selected_context()
        results = self._run_native_helper_ops(unit_handle, (
            (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0, candidate.unit_address,
             candidate.handle, candidate.owner_address),
            (self.NATIVE_HELPER_OP_BOUND_ITEM_CREATE, rawcode, 0, 0, 0)))
        if (len(results) != 2 or any(result.last_error for result in results)
                or results[1].kind != self.NATIVE_HELPER_OP_BOUND_ITEM_CREATE
                or not 0 <= results[1].result <= 6
                or (rawcode and results[1].result != 1)
                or bool(results[1].result) != bool(results[1].arg0)):
            raise RuntimeError("Incomplete native item creation result")
        return results[1]


    def _run_bound_inventory_batch(self, mode: int, quantity: int = 0) -> int:
        candidate, unit_handle = self._direct_selected_context()
        results = self._run_native_helper_ops(unit_handle, (
            (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0, candidate.unit_address,
             candidate.handle, candidate.owner_address),
            (self.NATIVE_HELPER_OP_BOUND_INVENTORY_BATCH, mode, 0, quantity, 0)))
        if (len(results) != 2 or any(result.last_error for result in results)
                or results[1].kind != self.NATIVE_HELPER_OP_BOUND_INVENTORY_BATCH
                or not 0 <= results[1].result <= 6):
            raise RuntimeError("Incomplete native inventory batch result")
        return int(results[1].result)


    def clear_selected_unit_inventory(self) -> int:
        if getattr(self, "_native_selection_unavailable", False):
            return int(self.item_batch_24268(4, 0, -1)["changed"])
        return self._run_bound_inventory_batch(0)


    def set_selected_inventory_charges(self, charges: int) -> int:
        target = int(charges)
        if not 1 <= target <= 1_000_000_000:
            raise ValueError("物品数量必须在 1 到 1000000000 之间")
        if getattr(self, "_native_selection_unavailable", False):
            result = self.item_batch_24268(2, 0, target)
            return sum(bool(item['handle']) for row in result['rows'] for item in row['after'])
        return self._run_bound_inventory_batch(1, target)


    def duplicate_selected_inventory_items(self) -> int:
        if getattr(self, "_native_selection_unavailable", False):
            return int(self.item_batch_24268(5, 0, -1)["changed"])
        return int(self._run_bound_item_create(0).result)


    def drop_selected_inventory_items(self) -> int:
        if getattr(self, "_native_selection_unavailable", False):
            return int(self.item_batch_24268(6, 0, -1)["changed"])
        return self._run_bound_inventory_batch(2)


    def replace_selected_inventory_items(
        self,
        slot_items: Iterable[tuple[int, int | str]],
    ) -> int:
        replacements = tuple(
            (
                int(slot),
                int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF,
            )
            for slot, rawcode in slot_items
        )
        if not replacements:
            raise ValueError("物品组合为空")
        if any(not 0 <= slot < 6 or not rawcode for slot, rawcode in replacements):
            raise ValueError("物品槽位或物品 ID 无效")
        if len({slot for slot, _rawcode in replacements}) != len(replacements):
            raise ValueError("物品组合包含重复槽位")
        if getattr(self, "_native_selection_unavailable", False):
            for slot, rawcode in replacements:
                result = self.item_batch_24268(7, rawcode, slot)
                if not result.get("rows") or int(result.get("completed", result.get("count", 0))) != int(result.get("count", 0)):
                    raise RuntimeError("3.0 当前引擎物品槽替换批处理不完整")
            return len(replacements)
        candidate, _unit_handle = self._direct_selected_context()
        for slot, rawcode in replacements:
            self._set_inventory_slot_item_via_native_handler(None, candidate, slot, rawcode)
        return len(replacements)


    def _current_engine_item_24268(
        self, candidate: UnitCandidate, slot: int,
    ) -> InventoryItem:
        slot_number = int(slot)
        if not 1 <= slot_number <= 6:
            raise ValueError("物品槽位必须在 1 到 6 之间")
        with self._process_memory() as memory:
            items = self._inventory_items_from_candidate(memory, candidate)
        item = next((item for item in items if item.slot == slot_number and item.rawcode), None)
        if item is None or not item.handle or not item.item_address:
            raise RuntimeError(f"当前选中单位的物品栏 {slot_number} 为空")
        return item


    @staticmethod
    def _current_engine_item_field_row_24268(result: dict, unit_handle: int) -> dict:
        rows = [row for row in result.get("rows", ()) if row.get("handle") == unit_handle]
        if len(rows) != 1 or rows[0].get("status") != 1 or not rows[0].get("item_handle"):
            raise RuntimeError("当前选中单位没有可绑定的运行时物品")
        return rows[0]


    @staticmethod
    def _bind_current_engine_item_field_row_24268(
        result: dict,
        candidate: UnitCandidate,
        item: InventoryItem,
    ) -> dict:
        rawcode = int(candidate.unit_type_id)
        if not rawcode:
            raise RuntimeError("当前单位没有可用于物品字段绑定的类型 ID")
        rows = [
            row for row in result.get("rows", ())
            if row.get("status") == 1
            and int(row.get("rawcode", 0)) == rawcode
            and int(row.get("item_rawcode", 0)) == int(item.rawcode)
        ]
        if len(rows) != 1:
            raise RuntimeError("当前选中单位的物品字段身份不唯一，请减少选中单位后重试")
        return War3Trainer._current_engine_item_field_row_24268(
            result, int(rows[0]["handle"]),
        )


    @staticmethod
    def _current_engine_item_field_bits(
        spec: ItemFieldSpec,
        value: bool | int | float,
    ) -> int:
        if spec.value_kind == "real":
            return War3Trainer._float_bits(float(value))
        return int(bool(value)) if spec.value_kind == "boolean" else int(value) & 0xFFFFFFFF


    def _current_engine_item_field_descriptor_24268(
        self, spec: ItemFieldSpec, target: bool | int | float = 0,
    ) -> tuple[int, int, int, int]:
        from war3_item_field_protocol import descriptor
        return descriptor(
            spec.field_id,
            spec.value_kind,
            self._current_engine_item_field_bits(spec, target),
        )


    def _read_selected_item_fields_24268(
        self,
        slot: int,
        *,
        unit_identity: tuple[int, int, int],
    ) -> ItemFieldSnapshot:
        handle, owner, unit = (int(value) for value in unit_identity)
        candidate = self._candidate_from_display_identity(
            None, handle, owner, unit, "item_field_candidate", 900,
            registry_required=False,
        )
        if candidate is None:
            raise RuntimeError("当前选中单位已变化，请重新读取字段")
        item = self._current_engine_item_24268(candidate, slot)
        supported = tuple(spec for spec in ITEM_FIELD_CATALOG if spec.runtime_supported)
        values: dict[str, ItemFieldValue] = {}
        result = self.item_field_batch_24268(
            item.slot - 1,
            0,
            tuple(self._current_engine_item_field_descriptor_24268(spec) for spec in supported),
            target_unit=0,
        )
        row = self._bind_current_engine_item_field_row_24268(result, candidate, item)
        if row["item_rawcode"] != item.rawcode:
            raise RuntimeError("物品实例在字段批处理期间发生变化")
        for spec, field in zip(supported, row["values"]):
            value = self._decode_item_field_value(spec, field["before"])
            values[spec.rawcode] = ItemFieldValue(spec, value, "可写" if spec.writable else "只读")
        fields = [
            values[spec.rawcode]
            if spec.runtime_supported
            else ItemFieldValue(spec, None, "未开放", "当前引擎 ABI 尚未开放字符串传输")
            for spec in ITEM_FIELD_CATALOG
        ]
        item_handle = int(row["item_handle"])
        return ItemFieldSnapshot(
            slot=item.slot,
            item_handle=item_handle,
            item_rawcode=item.rawcode,
            fields=tuple(fields),
            unit_identity=(candidate.handle, candidate.owner_address, candidate.unit_address),
            item_identity=(item_handle, item.item_address, item.handle),
        )


    def _set_selected_item_field_24268(
        self,
        slot: int,
        spec: ItemFieldSpec,
        value: bool | int | float | str,
        expected_snapshot: ItemFieldSnapshot,
        *,
        unit_identity: tuple[int, int, int],
    ) -> ItemFieldValue:
        if self._item_field_write_disabled:
            raise RuntimeError("上一次物品字段回滚无法确认，请重新连接游戏后再写入")
        if not spec.runtime_supported or not spec.writable:
            raise ValueError("该字段当前未开放运行时写入")
        if int(slot) != expected_snapshot.slot:
            raise RuntimeError("物品槽位已变化，请重新读取字段")
        if expected_snapshot.win10_compat:
            raise RuntimeError("当前引擎物品字段读取来源已变化，请重新读取字段")
        if ITEM_FIELD_BY_KEY.get((spec.rawcode, spec.value_kind)) != spec:
            raise RuntimeError("物品字段目录已变化，请重新读取字段")
        handle, owner, unit = (int(item) for item in unit_identity)
        candidate = self._candidate_from_display_identity(
            None, handle, owner, unit, "item_field_candidate", 900,
            registry_required=False,
        )
        if candidate is None:
            raise RuntimeError("当前选中单位已变化，请重新读取字段")
        item = self._current_engine_item_24268(candidate, slot)
        target = self._coerce_item_field_value(spec, value)
        descriptor = self._current_engine_item_field_descriptor_24268(spec)
        read_result = self.item_field_batch_24268(
            item.slot - 1, 0, (descriptor,), target_unit=0,
        )
        row = self._bind_current_engine_item_field_row_24268(read_result, candidate, item)
        item_jass_handle = int(row["handle"])
        identity = (int(row["item_handle"]), item.item_address, item.handle)
        if (
            identity != expected_snapshot.item_identity
            or row["item_rawcode"] != expected_snapshot.item_rawcode
            or (candidate.handle, candidate.owner_address, candidate.unit_address) != expected_snapshot.unit_identity
        ):
            raise RuntimeError("当前物品已经变化，请重新读取字段")
        original_bits = int(row["values"][0]["before"]) & 0xFFFFFFFF
        original = self._decode_item_field_value(spec, original_bits)
        try:
            self.item_field_batch_24268(
                item.slot - 1,
                1,
                (self._current_engine_item_field_descriptor_24268(spec, target),),
                target_unit=item_jass_handle,
            )
            verify = self.item_field_batch_24268(
                item.slot - 1, 0, (descriptor,), target_unit=item_jass_handle,
            )
            verify_row = self._current_engine_item_field_row_24268(verify, item_jass_handle)
            actual = self._decode_item_field_value(spec, verify_row["values"][0]["before"])
            if not self._ability_field_values_equal(spec, actual, target):
                raise RuntimeError(f"物品字段写入后读回不一致：{actual!s}!={target!s}")
        except Exception as exc:
            rollback_ok = False
            try:
                self.item_field_batch_24268(
                    item.slot - 1,
                    1,
                    (self._current_engine_item_field_descriptor_24268(spec, original),),
                    target_unit=item_jass_handle,
                )
                rollback = self.item_field_batch_24268(
                    item.slot - 1, 0, (descriptor,), target_unit=item_jass_handle,
                )
                rollback_row = self._current_engine_item_field_row_24268(rollback, item_jass_handle)
                restored = self._decode_item_field_value(spec, rollback_row["values"][0]["before"])
                rollback_ok = self._ability_field_values_equal(spec, restored, original)
            except Exception:
                rollback_ok = False
            if not rollback_ok:
                self._item_field_write_disabled = True
                raise RuntimeError(f"{exc}；原始字段恢复无法确认") from exc
            raise
        return ItemFieldValue(spec, actual, "已验证")


    def _item_field_context_from_candidate_locked(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        unit_handle: int,
        slot: int,
        handlers: dict[str, NativeHandler] | None = None,
    ) -> ItemFieldContext:
        slot_number = int(slot)
        if not 1 <= slot_number <= 6:
            raise ValueError("物品槽位必须在 1 到 6 之间")
        if handlers is None:
            handlers = self._discover_native_handlers_near_table(
                pm,
                self.ITEM_FIELD_NATIVE_NAMES,
            )
        native = self._native_snapshot_for_candidate(candidate)
        if native is None or native.handle != unit_handle:
            raise RuntimeError("物品查询缺少绑定单位快照")
        index = slot_number - 1
        item_handle = native.item_handles[index]
        item_rawcode = native.item_ids[index]
        identity = (item_handle, native.item_addresses[index], native.item_full_handles[index])
        if not all(identity) or not item_rawcode:
            raise RuntimeError(f"当前选中单位的物品栏 {slot_number} 为空")
        return ItemFieldContext(candidate, slot_number, item_handle, item_rawcode, handlers, identity)


    def _item_field_context_by_identity_locked(
        self,
        slot: int,
        unit_identity: tuple[int, int, int],
        win10_compat: bool,
    ) -> ItemFieldContext:
        handle, owner, unit = (int(value) for value in unit_identity)
        candidate = self._candidate_from_display_identity(None, handle, owner, unit, "item_field_candidate", 900)
        if candidate is None:
            raise RuntimeError("当前选中单位已变化，请重新读取字段")
        native = self._native_snapshot_for_candidate(candidate)
        if native is None:
            raise RuntimeError("物品查询缺少绑定单位快照")
        return self._item_field_context_from_candidate_locked(None, candidate, native.handle, slot)


    def _item_field_get_op(
        self,
        spec: ItemFieldSpec,
        handlers: dict[str, NativeHandler],
    ) -> tuple[int, int, int, int, int]:
        return (
            self.NATIVE_HELPER_OP_JASS_ITEM_FIELD_GET,
            spec.field_id,
            handlers[self.ITEM_FIELD_GETTER_NAMES[spec.value_kind]].handler_address,
            0,
            0,
        )


    def _decode_item_field_value(
        self,
        spec: ItemFieldSpec,
        raw_value: int,
    ) -> bool | int | float:
        if spec.value_kind == "boolean":
            return bool(int(raw_value) & 1)
        if spec.value_kind == "integer":
            return ctypes.c_int32(int(raw_value) & 0xFFFFFFFF).value
        return self._float_from_bits(raw_value)


    def _run_bound_item_field_ops(
        self, context: ItemFieldContext, ops: Iterable[tuple[int, int, int, int, int]],
    ) -> list[NativeHelperOpResult]:
        candidate = context.candidate
        native = self._native_snapshot_for_candidate(candidate)
        if native is None or not all(context.item_identity) or context.item_identity[0] != context.item_handle:
            raise RuntimeError("物品查询缺少绑定单位快照")
        batch = tuple(ops)
        if not batch or len(batch) > self.NATIVE_HELPER_MAX_OPS - 3:
            raise ValueError("Invalid bound item field batch size")
        handle, data, full = context.item_identity
        guards = (
            (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0, candidate.unit_address, candidate.handle, candidate.owner_address),
            (self.NATIVE_HELPER_OP_BOUND_INVENTORY_ITEM, context.slot - 1, handle, data, full),
            (self.NATIVE_HELPER_OP_BOUND_ITEM_TYPE, context.item_rawcode, 0, 0, 0),
        )
        results = self._run_native_helper_ops(native.handle, guards + batch)
        if len(results) != len(guards) + len(batch) or any(result.last_error for result in results):
            raise RuntimeError("DLL 物品字段返回不完整")
        return list(results[3:])


    def _read_single_item_field_locked(self, context: ItemFieldContext, spec: ItemFieldSpec) -> bool | int | float:
        result = self._run_bound_item_field_ops(context, (self._item_field_get_op(spec, context.handlers),))[0]
        return self._decode_item_field_value(spec, result.result)


    def read_selected_item_fields(
        self,
        slot: int,
        *,
        unit_identity: tuple[int, int, int],
        win10_compat: bool = False,
    ) -> ItemFieldSnapshot:
        if getattr(self, "_native_selection_unavailable", False):
            return self._read_selected_item_fields_24268(
                slot,
                unit_identity=unit_identity,
            )
        with self._native_helper_transaction():
            context = self._item_field_context_by_identity_locked(
                slot,
                unit_identity,
                win10_compat,
            )
            values = {}
            supported = [spec for spec in ITEM_FIELD_CATALOG if spec.runtime_supported]
            batch_size = self.NATIVE_HELPER_MAX_OPS - 3
            for start in range(0, len(supported), batch_size):
                batch = supported[start:start + batch_size]
                results = self._run_bound_item_field_ops(context, tuple(self._item_field_get_op(spec, context.handlers) for spec in batch))
                for spec, result in zip(batch, results):
                    values[spec.rawcode] = ItemFieldValue(spec, self._decode_item_field_value(spec, result.result),
                                                         "可写" if spec.writable else "只读")
            fields = [values[spec.rawcode] if spec.runtime_supported else
                      ItemFieldValue(spec, None, "未开放", "native helper 当前未开放字符串传输")
                      for spec in ITEM_FIELD_CATALOG]
        return ItemFieldSnapshot(
            slot=context.slot,
            item_handle=context.item_handle,
            item_rawcode=context.item_rawcode,
            fields=tuple(fields),
            unit_identity=context.unit_identity,
            win10_compat=bool(win10_compat),
            item_identity=context.item_identity,
        )


    def _coerce_item_field_value(
        self,
        spec: ItemFieldSpec,
        value: bool | int | float | str,
    ) -> bool | int | float:
        if spec.value_kind == "boolean":
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"1", "true", "yes", "on", "是"}:
                    return True
                if normalized in {"0", "false", "no", "off", "否"}:
                    return False
                raise ValueError("布尔字段请输入 true/false 或 1/0")
            return bool(value)
        if spec.value_kind == "integer":
            return int(self._coerce_memory_value("i32", value))
        target = float(value)
        if not math.isfinite(target):
            raise ValueError("实数字段必须是有限数值")
        return self._float_from_bits(self._float_bits(target))


    def _item_field_set_op(
        self,
        spec: ItemFieldSpec,
        handlers: dict[str, NativeHandler],
        value: bool | int | float,
    ) -> tuple[int, int, int, int, int]:
        bits = (
            self._float_bits(float(value))
            if spec.value_kind == "real"
            else int(value) & 0xFFFFFFFF
        )
        return (
            self.NATIVE_HELPER_OP_JASS_ITEM_FIELD_SET,
            spec.field_id,
            handlers[self.ITEM_FIELD_SETTER_NAMES[spec.value_kind]].handler_address,
            bits,
            2 if spec.value_kind == "real" else 0,
        )


    def set_selected_item_field(
        self,
        slot: int,
        spec: ItemFieldSpec,
        value: bool | int | float | str,
        expected_snapshot: ItemFieldSnapshot,
        *,
        unit_identity: tuple[int, int, int],
        win10_compat: bool = False,
    ) -> ItemFieldValue:
        if getattr(self, "_native_selection_unavailable", False):
            return self._set_selected_item_field_24268(
                slot,
                spec,
                value,
                expected_snapshot,
                unit_identity=unit_identity,
            )
        if self._item_field_write_disabled:
            raise RuntimeError("上一次物品字段回滚无法确认，请重新连接游戏后再写入")
        if not spec.runtime_supported or not spec.writable:
            raise ValueError("该字段当前未开放运行时写入")
        if int(slot) != expected_snapshot.slot:
            raise RuntimeError("物品槽位已变化，请重新读取字段")
        if bool(win10_compat) != bool(expected_snapshot.win10_compat):
            raise RuntimeError("物品字段读取来源已变化，请重新读取字段")
        if ITEM_FIELD_BY_KEY.get((spec.rawcode, spec.value_kind)) != spec:
            raise RuntimeError("物品字段目录已变化，请重新读取字段")
        target = self._coerce_item_field_value(spec, value)
        with self._native_helper_transaction():
            context = self._item_field_context_by_identity_locked(
                slot,
                unit_identity,
                win10_compat,
            )
            if (
                context.unit_identity != expected_snapshot.unit_identity
                or context.item_handle != expected_snapshot.item_handle
                or context.item_rawcode != expected_snapshot.item_rawcode
                or not all(expected_snapshot.item_identity)
                or context.item_identity != expected_snapshot.item_identity
            ):
                raise RuntimeError("当前物品已经变化，请重新读取字段")
            original = self._read_single_item_field_locked(
                context,
                spec,
            )

            def write_field(field_value: bool | int | float) -> bool:
                result = self._run_bound_item_field_ops(
                    context,
                    (self._item_field_set_op(spec, context.handlers, field_value),),
                )[0]
                return bool(result.result)

            try:
                if not write_field(target):
                    raise RuntimeError("游戏拒绝写入该物品字段")
                actual = self._read_single_item_field_locked(
                    context,
                    spec,
                )
                if not self._ability_field_values_equal(spec, actual, target):
                    raise RuntimeError(f"字段写入后读回不一致：{actual!s}!={target!s}")
            except Exception as exc:
                rollback_ok = False
                try:
                    write_field(original)
                    restored = self._read_single_item_field_locked(
                        context,
                        spec,
                    )
                    rollback_ok = self._ability_field_values_equal(spec, restored, original)
                except Exception:
                    rollback_ok = False
                if not rollback_ok:
                    self._item_field_write_disabled = True
                    raise RuntimeError(f"{exc}；原始字段恢复无法确认") from exc
                raise
        return ItemFieldValue(spec, actual, "已验证")


    def _set_item_charges_via_native_handler(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        item: InventoryItem,
        charges: int,
    ) -> None:
        if not candidate.unit_address:
            raise RuntimeError("当前单位缺少运行时 unit 指针，不能调用物品数量 native handler")
        if not item.item_address:
            raise RuntimeError(f"物品槽{item.slot}缺少 item 对象地址，不能调用物品数量 native handler")
        handlers = self._discover_native_handlers(pm, ("SetItemCharges",))
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
        self._run_native_helper_ops(
            candidate.unit_address,
            (
                (
                    self.NATIVE_HELPER_OP_SET_ITEM_CHARGES,
                    0,
                    notify_handler,
                    item.item_address,
                    charges & 0xFFFFFFFF,
                ),
            ),
        )


    def _set_inventory_slot_item_via_native_handler(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        slot_index: int,
        rawcode: int,
    ) -> tuple[int, int, int]:
        native = self._native_snapshot_for_candidate(candidate)
        if native is not None:
            if not 0 <= slot_index < 6:
                raise ValueError("Invalid inventory slot")
            results = self._run_native_helper_ops(native.handle, (
                (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0, candidate.unit_address,
                 candidate.handle, candidate.owner_address),
                (self.NATIVE_HELPER_OP_REPLACE_INVENTORY_ITEM, rawcode, 0,
                 native.item_handles[slot_index], native.item_full_handles[slot_index]),
                (self.NATIVE_HELPER_OP_REPLACE_INVENTORY_CONTEXT, slot_index,
                 native.item_addresses[slot_index], native.item_ids[slot_index], 0),
            ))
            if (len(results) != 3 or any(result.last_error for result in results)
                    or not results[1].result or results[2].result != rawcode):
                raise RuntimeError("Native item replacement returned an incomplete result")
            return native.item_addresses[slot_index], results[1].result, results[2].result
        if not candidate.unit_address:
            raise RuntimeError("当前单位缺少运行时 unit 指针，不能调用物品 native handler")
        handlers = self._discover_native_handlers(
            pm,
            (
                "UnitAddItemToSlotById",
                "UnitAddItemById",
                "UnitItemInSlot",
                "UnitRemoveItem",
            ),
        )
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
        item_ops = (
                (
                    self.NATIVE_HELPER_OP_REMOVE_ITEM_SLOT,
                    slot_index,
                    item_in_slot_internal,
                    remove_item_internal,
                    0,
                ),
                (
                    self.NATIVE_HELPER_OP_ADD_ITEM_TO_SLOT_BY_ID,
                    rawcode,
                    create_item_internal,
                    add_exact_slot_internal,
                    slot_index,
                ),
                (
                    self.NATIVE_HELPER_OP_GET_ITEM_TYPE_IN_SLOT,
                    slot_index,
                    item_in_slot_internal,
                    0,
                    0,
                ),
            )
        native = self._native_snapshot_for_candidate(candidate)
        if native is not None:
            results = self._run_native_helper_ops(native.handle, (
                (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0, candidate.unit_address,
                 candidate.handle, candidate.owner_address), *item_ops))
            results = results[1:]
        else:
            results = self._run_native_helper_ops(candidate.unit_address, item_ops,
            timeout_ms=1500,
        )
        removed_handle = results[0].result
        added_item = results[1].result
        final_rawcode = results[2].result & 0xFFFFFFFF
        if final_rawcode != rawcode:
            raise RuntimeError(
                f"内部 UnitAddItemToSlot 写入后 native 读回 "
                f"{format_rawcode(final_rawcode) if final_rawcode else '空'}，"
                f"不是 {format_rawcode(rawcode)}；新 item=0x{added_item:x}"
            )
        return removed_handle, added_item, final_rawcode
