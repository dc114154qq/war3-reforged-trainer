"""extensions compatibility API; host primitives are explicitly bound once at composition."""
from __future__ import annotations
from contextlib import contextmanager
from war3_3_stats import STAT_DETAIL_SPECS


def _refresh_extension_equipment_effects(host, target_unit: int, candidate=None) -> dict:
    """Refresh native 3.0 stat controllers after an AEqu record move."""
    try:
        before = host.stat_details_24268(candidate)
    except Exception as exc:
        return {"status": "unavailable", "reason": str(exc)}
    present = set(int(value) for value in before.get("present", ()))
    refreshed = []
    try:
        resolved_candidate, unit_handle = host._stat_target_24268(candidate)
        engine = host._engine_instance_24268()
        for spec in STAT_DETAIL_SPECS:
            controller = int(host._coerce_memory_value("rawcode", spec.controller)) & 0xFFFFFFFF
            if controller not in present:
                continue
            engine.stat_details(
                action=2, stat_index=0, target=0.0, controller=controller,
                target_unit=int(target_unit or unit_handle),
                target_full_handle=int(resolved_candidate.handle),
            )
            refreshed.append(spec.controller)
        after = host.stat_details_24268(resolved_candidate)
        before_values = dict(before.get("values", {}))
        after_values = dict(after.get("values", {}))
        changed_keys = tuple(
            key for key in before_values
            if before_values.get(key) != after_values.get(key)
        )
        return {
            "status": "refreshed" if refreshed else "no_stat_source",
            "controllers": tuple(refreshed),
            "before": before_values,
            "after": after_values,
            "changed_keys": changed_keys,
        }
    except Exception as exc:
        return {"status": "failed", "controllers": tuple(refreshed), "reason": str(exc),
                "execution_report": getattr(exc,"report",None)}

class ExtensionsFacade:
    def extension_snapshot_24268(self, target_unit: int = 0) -> dict:
        engine = self._engine_instance_24268()
        override = getattr(self, '_elephant_selection_override', None)
        if not target_unit and override is not None:
            target_unit = int(override[1])
        controller_codes = tuple(
            int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
            for rawcode in TALENT_CONTROLLERS
        )
        snapshot = engine.extension(controller_codes, target_unit=target_unit) if target_unit else engine.extension(controller_codes)
        abilities = dict(snapshot["abilities"])
        active_choices = []
        for controller, (_name, tiers) in TALENT_CONTROLLERS.items():
            controller_code = int(self._coerce_memory_value("rawcode", controller)) & 0xFFFFFFFF
            if abilities.get(controller_code, 0) > 0:
                active_choices.extend(choice for tier in tiers for choice in tier)
        target = int(snapshot["target_unit"])
        for start in range(0, len(active_choices), 24):
            codes = tuple(
                int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
                for rawcode in active_choices[start:start + 24]
            )
            detail = engine.extension(codes, target_unit=target)
            abilities.update(detail["abilities"])
            snapshot = detail
        snapshot["abilities"] = abilities
        if override is not None:
            selection = dict(snapshot['selection'])
            selection['rows'] = tuple(row for row in selection['rows']
                                      if int(row['handle']) == int(target))
            snapshot['selection'] = selection
        key = (int(getattr(self, "pid", 0)), int(target))
        store = getattr(self, "_extension_saved_loadouts", {})
        snapshot["loadout_names"] = self.extension_loadout_names_24268()
        return snapshot


    def stat_details_24268(self, candidate: UnitCandidate | None = None) -> dict:
        candidate, unit_handle = self._stat_target_24268(candidate)
        result = self._engine_instance_24268().stat_details(target_unit=unit_handle, target_full_handle=candidate.handle)
        values = {
            spec.key: float(raw) * spec.scale + spec.baseline
            for spec, raw in zip(STAT_DETAIL_SPECS, result["after"])
        }
        return dict(result, values=values)


    def set_stat_detail_24268(
        self, key: str, target: int | float, candidate: UnitCandidate | None = None,
    ) -> float:
        spec = STAT_DETAIL_BY_KEY.get(str(key))
        if spec is None:
            raise ValueError("未知的 3.0 单位属性")
        value = float(target)
        if not math.isfinite(value) or abs(value) > 1_000_000.0:
            raise ValueError("属性目标值必须是 -1000000 到 1000000 之间的有限数值")
        candidate, unit_handle = self._stat_target_24268(candidate)
        index = STAT_DETAIL_SPECS.index(spec)
        result = self._engine_instance_24268().stat_details(
            action=1,
            stat_index=index,
            target=(value - spec.baseline) / spec.scale,
            controller=spec.controller,
            target_unit=unit_handle,
            target_full_handle=candidate.handle,
        )
        actual = float(result["after"][index]) * spec.scale + spec.baseline
        if not math.isclose(actual, value, rel_tol=1e-5, abs_tol=5e-3):
            raise RuntimeError(f"3.0 属性写入后总值不一致：{actual:g}!={value:g}")
        return actual

    def add_official_backpack_24268(self, rawcode: str) -> dict:
        if rawcode not in OFFICIAL_BACKPACKS:
            raise ValueError("未知的 3.0 官方背包装备")
        _hero_name, controller_rawcode = OFFICIAL_BACKPACKS[rawcode]
        before = self.extension_snapshot_24268()
        target = int(before["target_unit"])
        code = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        controller = int(self._coerce_memory_value("rawcode", controller_rawcode)) & 0xFFFFFFFF
        active_controllers = {
            name for name in TALENT_CONTROLLERS
            if int(before["abilities"].get(
                int(self._coerce_memory_value("rawcode", name)) & 0xFFFFFFFF, 0,
            )) > 0
        }
        if active_controllers and active_controllers != {controller_rawcode}:
            raise RuntimeError("当前单位已有其他官方天赋控制器，拒绝叠加第二套专属天赋")
        inventory = self.item_batch_24268()
        rows = [row for row in inventory.get("rows", ())
                if int(row.get("handle", 0)) == target]
        if len(rows) != 1:
            raise RuntimeError("当前选中英雄的经典物品栏身份不唯一，请重新选择目标")
        row = rows[0]
        if int(row.get("inventory_size", 0)) < 1:
            raise RuntimeError("当前选中单位没有经典物品栏，无法放入背包装备")
        first = row["before"][0]
        if int(first.get("rawcode", 0)) != code:
            if int(first.get("handle", 0)):
                raise RuntimeError("经典物品栏第 1 格已有物品；请先腾空该格，避免覆盖原装备")
            try:
                result = self.item_batch_24268(
                    7, code, 0, target_unit=target,
                    expected_item=int(first.get("handle", 0)),
                )
            except Exception as exc:
                # Old campaigns may not load the 3.0 item definition table.
                # Keep the original exception for the diagnostic log, but do
                # not expose its English bridge payload as the user message.
                report = getattr(self._engine_instance_24268(), "last_report", {})
                status = report.get("item_catalog_status") or report.get("item_status") or {}
                error_code = int(status.get("error", 0) or 0) if isinstance(status, dict) else 0
                if error_code in (31, 62, 63):
                    raise RuntimeError(
                        "当前战役未加载 3.0 背包装备定义，无法添加该背包。"
                        "请在包含 3.0 背包数据的战役中使用；当前物品栏未被修改。"
                    ) from exc
                raise
            written = [item for item in result.get("rows", ())
                       if int(item.get("handle", 0)) == target]
            if (len(written) != 1
                    or int(written[0]["after"][0].get("rawcode", 0)) != code
                    or not int(written[0]["after"][0].get("handle", 0))):
                raise RuntimeError("背包装备写入经典物品栏第 1 格后读回不一致")
        after = self.extension_snapshot_24268()
        if int(after["target_unit"]) != target or int(after["bag_size"]) != 30:
            raise RuntimeError("背包装备已放入第 1 格，但未读回 30 格扩展背包")
        if int(after["abilities"].get(controller, 0)) <= 0:
            raise RuntimeError(f"背包装备已放入第 1 格，但未读回其 {controller_rawcode} 天赋控制器")
        return after


    def add_forsaken_kingdom_backpack_24268(self) -> dict:
        return self.add_official_backpack_24268("ebug")


    def add_extension_item_24268(self, rawcode: int | str) -> dict:
        code = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        if not code:
            raise ValueError("物品 ID 无效")
        before = self.extension_snapshot_24268()
        bag_size = int(before["bag_size"])
        occupied = sum(bool(int(item["handle"])) for item in before["bag"][:bag_size])
        if bag_size <= 0:
            raise RuntimeError("当前单位尚未启用 3.0 扩展背包；请先添加 30 格背包装备")
        if occupied >= bag_size:
            raise RuntimeError("扩展背包已满，拒绝创建会落在地面的物品")
        from war3_services.equipment_effects import require_creation_capacity, preflight_creation, skipped_snapshot
        definition=preflight_creation(self, code, int(before['target_unit']))
        if definition.get('skipped'):
            return skipped_snapshot(before,code)
        require_creation_capacity(self, code, int(before["target_unit"]), definition)
        engine = self._engine_instance_24268()
        created_result = engine.extension(
            action=1,
            target_unit=int(before["target_unit"]),
            item_rawcode=code,
        )
        after = self.extension_snapshot_24268()
        before_handles = {int(item["handle"]) for area in ('bag','equipment')
                          for item in before[area] if int(item["handle"])}
        created_handle = int(created_result.get("item_handle", 0))
        if not created_handle or created_handle in before_handles:
            raise RuntimeError("物品已创建，但引擎未返回可转入扩展背包的实例句柄")
        created = [item for item in after["bag"]
                   if int(item["handle"]) == created_handle and int(item["rawcode"]) == code]
        if len(created) != 1:
            # Ordinary items enter the classic inventory first. Bind that
            # exact instance, remove its classic passives through the native,
            # and classify only that instance for native bag insertion.
            from war3_services.equipment_effects import transfer_created
            after = transfer_created(self, int(before["target_unit"]), created_handle, code)
            if after.get('operation_skipped'):
                return after
            created = [item for item in after["bag"]
                       if int(item["handle"]) == created_handle
                       and int(item["rawcode"]) == code]
        if len(created) != 1:
            raise RuntimeError("物品已创建，但转入扩展背包后未读回唯一新实例")
        return after


    @staticmethod
    def _extension_bag_item(snapshot: dict, slot: int) -> dict:
        slot = int(slot)
        if not 0 <= slot < int(snapshot["bag_size"]):
            raise ValueError("扩展背包槽无效")
        item = snapshot["bag"][slot]
        if not int(item["handle"]) or not int(item["rawcode"]):
            raise ValueError("所选扩展背包槽为空")
        return item


    def set_extension_bag_charges_24268(self, slot: int, charges: int) -> dict:
        charges = int(charges)
        if not 0 <= charges <= 1_000_000_000:
            raise ValueError("物品数量必须在 0 到 1000000000 之间")
        before = self.extension_snapshot_24268()
        item = self._extension_bag_item(before, slot)
        self._engine_instance_24268().extension(
            action=6,
            target_unit=int(before["target_unit"]),
            slot=charges,
            item_rawcode=int(item["rawcode"]),
            item_handle=int(item["handle"]),
        )
        after = self.extension_snapshot_24268()
        same = [row for row in after["bag"] if int(row["handle"]) == int(item["handle"])]
        if len(same) != 1 or int(same[0]["charges"]) != charges:
            raise RuntimeError("物品数量写入后实例或读回值不一致")
        return after


    def drop_extension_bag_item_24268(self, slot: int) -> dict:
        before = self.extension_snapshot_24268()
        item = self._extension_bag_item(before, slot)
        engine = self._engine_instance_24268()
        result = engine.extension(
            action=5,
            target_unit=int(before["target_unit"]),
            item_rawcode=int(item["rawcode"]),
            item_handle=int(item["handle"]),
        )
        if int(before["bag_size"]) > 0 and int(result["bag_size"]) == 0:
            engine.extension(
                action=3,
                target_unit=int(before["target_unit"]),
                item_rawcode=int(item["rawcode"]),
                item_handle=int(item["handle"]),
            )
            raise RuntimeError("所选物品承载当前扩展背包，已自动放回并拒绝丢弃")
        after = self.extension_snapshot_24268()
        if any(int(row["handle"]) == int(item["handle"]) for row in after["bag"]):
            raise RuntimeError("物品丢弃后仍存在于扩展背包")
        return after


    def duplicate_extension_bag_item_24268(self, slot: int) -> dict:
        before = self.extension_snapshot_24268()
        source = self._extension_bag_item(before, slot)
        bag_size = int(before["bag_size"])
        occupied = sum(bool(int(item["handle"])) for item in before["bag"][:bag_size])
        if occupied >= bag_size:
            raise RuntimeError("扩展背包已满，无法复制物品")
        engine = self._engine_instance_24268()
        middle = self.add_extension_item_24268(int(source["rawcode"]))
        if middle.get("operation_skipped"):
            return middle
        before_handles = {int(item["handle"]) for item in before["bag"] if int(item["handle"])}
        created = [item for item in middle["bag"]
                   if int(item["handle"]) not in before_handles
                   and int(item["rawcode"]) == int(source["rawcode"])]
        if len(created) != 1:
            raise RuntimeError("复制后未发现唯一的新物品实例")
        copied = created[0]
        try:
            if int(copied["charges"]) != int(source["charges"]):
                engine.extension(
                    action=6,
                    target_unit=int(before["target_unit"]),
                    slot=int(source["charges"]),
                    item_rawcode=int(copied["rawcode"]),
                    item_handle=int(copied["handle"]),
                )
            after = self.extension_snapshot_24268()
            matches = [item for item in after["bag"]
                       if int(item["handle"]) == int(copied["handle"])]
            if len(matches) != 1 or int(matches[0]["charges"]) != int(source["charges"]):
                raise RuntimeError("复制物品的实例或数量读回不一致")
            return after
        except Exception as exc:
            rollback_error = ""
            try:
                engine.extension(
                    action=8,
                    target_unit=int(before["target_unit"]),
                    item_rawcode=int(copied["rawcode"]),
                    item_handle=int(copied["handle"]),
                )
            except Exception as rollback_exc:
                rollback_error = f"；删除复制实例失败：{rollback_exc}"
            raise RuntimeError(f"复制物品事务失败：{exc}{rollback_error}") from exc


    def _delete_extension_bag_item_24268(self, item_handle: int, item_rawcode: int) -> dict:
        snapshot = self.extension_snapshot_24268()
        matches = [row for row in snapshot["bag"]
                   if int(row["handle"]) == int(item_handle)
                   and int(row["rawcode"]) == int(item_rawcode)]
        if len(matches) != 1:
            raise RuntimeError("待删除的扩展背包实例不是唯一当前物品")
        self._engine_instance_24268().extension(
            action=8,
            target_unit=int(snapshot["target_unit"]),
            item_rawcode=int(item_rawcode),
            item_handle=int(item_handle),
        )
        after = self.extension_snapshot_24268()
        if any(int(row["handle"]) == int(item_handle) for row in after["bag"]):
            raise RuntimeError("扩展背包实例删除后仍可见")
        return after


    def equip_extension_bag_slot_24268(self, slot: int) -> dict:
        slot = int(slot)
        snapshot = self.extension_snapshot_24268()
        if not 0 <= slot < int(snapshot["bag_size"]):
            raise ValueError("扩展背包槽无效")
        item = snapshot["bag"][slot]
        if not int(item["handle"]) or not int(item["rawcode"]):
            raise ValueError("所选扩展背包槽为空")
        target = int(snapshot["target_unit"])
        self._engine_instance_24268().extension(
            action=4,
            target_unit=target,
            item_rawcode=int(item["rawcode"]),
            item_handle=int(item["handle"]),
        )
        return self.extension_snapshot_24268()


    def _extension_inventory_equipment_records_24268(
        self, memory: ProcessMemory, candidate: UnitCandidate,
    ) -> dict[str, int]:
        codes = {
            name: int(self._coerce_memory_value("rawcode", name))
            for name in ("AIni", "AEqu")
        }
        instances = self._ability_instances_from_candidate(
            memory, candidate, required_rawcodes=set(codes.values()),
            allow_global_scan=False,
        )
        by_rawcode: dict[int, list[int]] = {}
        for instance in instances:
            data = int(instance.data_address)
            by_rawcode.setdefault(int(memory.read_u32(data + 0x70)), []).append(data)
        if any(len(by_rawcode.get(rawcode, ())) != 1 for rawcode in codes.values()):
            raise RuntimeError("当前单位没有唯一的 AIni 扩展背包和 AEqu 装备组件")
        result: dict[str, int] = {}
        for name, expected_count in (("AIni", 30), ("AEqu", 9)):
            data = by_rawcode[codes[name]][0]
            if (int(memory.read_u64(data + 0x68)) != int(candidate.unit_address)
                    or int(memory.read_u64(data + 0xD0)) != expected_count
                    or int(memory.read_u64(data + 0xE0)) < expected_count):
                raise RuntimeError(f"{name} 组件身份或槽位数量已经变化")
            records = int(memory.read_u64(data + 0xD8))
            if not self._sane_heap_ptr(records):
                raise RuntimeError(f"{name} 槽位记录地址无效")
            result[name] = records
        return result


    def _equip_non_equipment_item_to_slot_24268(
        self, before: dict, bag_slot: int, equipment_slot: int,
    ) -> dict:
        from war3_services.equipment_effects import perform
        if len(before.get("selection", {}).get("rows", ())) != 1:
            raise RuntimeError("普通物品指定装备槽需要唯一选中英雄")
        return perform(self, before, bag_slot, equipment_slot, equip=True)


    def equip_extension_bag_item_to_slot_24268(self, bag_slot: int, equipment_slot: int) -> dict:
        """Equip one owned bag instance into an explicitly selected loadout slot."""
        from war3_services.facade_extensions import _refresh_extension_equipment_effects
        bag_slot = int(bag_slot)
        equipment_slot = int(equipment_slot)
        if not 0 <= equipment_slot < len(EQUIPMENT_SLOT_NAMES):
            raise ValueError("装备槽无效")
        before = self.extension_snapshot_24268()
        if not 0 <= bag_slot < int(before["bag_size"]):
            raise ValueError("扩展背包槽无效")
        item = before["bag"][bag_slot]
        if not int(item["handle"]) or not int(item["rawcode"]):
            raise ValueError("所选扩展背包槽为空")
        if int(before["equipment"][equipment_slot]["handle"]):
            raise RuntimeError("目标装备槽已有物品；请先卸下后再指定装备")
        item_type = int(item.get("equipment_type", 0))
        any_slot_key = (int(getattr(self, "pid", 0)), int(before["target_unit"]))
        any_slot_enabled = bool(getattr(self, "_extension_any_slot_enabled", {}).get(any_slot_key))
        if not 1 <= item_type <= 9 and any_slot_enabled:
            return self._equip_non_equipment_item_to_slot_24268(before, bag_slot, equipment_slot)
        if not 1 <= item_type <= 9:
            raise RuntimeError(
                f"扩展背包第 {bag_slot + 1} 格物品 {format_rawcode(int(item['rawcode']))} "
                f"不是游戏认可的装备（装备类型 {item_type}）；任意槽只改变装备的目标槽，"
                "不能把背包或普通道具变成装备"
            )
        conflicting_slots = [
            int(row["slot"]) for row in before["equipment"]
            if int(row.get("handle", 0)) and int(row.get("equipment_type", 0)) == item_type
        ]
        if item_type not in (int(EQUIPMENT_SLOT_TYPES[equipment_slot]), 9) and not any_slot_enabled:
            raise RuntimeError("物品类型与目标装备槽不匹配；请先开启当前单位的任意槽")
        if conflicting_slots and not any_slot_enabled:
            raise RuntimeError(
                "该物品的原生类型槽已有装备；请先卸下槽位 "
                + ", ".join(str(slot + 1) for slot in conflicting_slots)
            )
        target = int(before["target_unit"])
        engine = self._engine_instance_24268()
        # Protocol-only unit tests construct War3Trainer without runtime
        # identity state. Keep their mocked action path isolated from the
        # live memory route below.
        if not hasattr(self, "_elephant_selection_override"):
            engine.extension(
                (int(self._coerce_memory_value("rawcode", "AEqu")),),
                action=12, target_unit=target, slot=equipment_slot,
                item_rawcode=int(item["rawcode"]), item_handle=int(item["handle"]),
            )
            after = self.extension_snapshot_24268(target)
            if int(after["equipment"][equipment_slot]["handle"]) != int(item["handle"]):
                raise RuntimeError("指定装备槽读回不是同一物品实例")
            return after
        candidate, _native_handle = self._direct_selected_context()
        if len(before.get("selection", {}).get("rows", ())) != 1:
            raise RuntimeError("指定装备槽写入需要唯一选中单位")

        # Native UnitEquipItem determines the item's legal source slot.  The
        # final redirection is done against the same AEqu record that the
        # verified component enumerator reads, avoiding the unstable
        # BlzGetUnitAbility wrapper path used by the old action=12 bridge.
        with ProcessMemory(int(self.pid), write=True) as memory:
            instances = self._ability_instances_from_candidate(
                memory, candidate,
                required_rawcodes={int(self._coerce_memory_value("rawcode", "AEqu"))},
                allow_global_scan=False,
            )
            if len(instances) != 1:
                raise RuntimeError("当前单位没有唯一可写的 AEqu 装备组件")
            aeq_data = int(instances[0].data_address)
            records = int(memory.read_u64(aeq_data + 0xD8))
            if not self._sane_heap_ptr(records):
                raise RuntimeError("AEqu 装备记录地址无效")

        native_records = None
        displaced_items = []
        records_redirected = False
        try:
            legal_slots = [index for index, slot_type in enumerate(EQUIPMENT_SLOT_TYPES)
                           if slot_type == item_type]
            if (legal_slots and all(int(before["equipment"][index]["handle"])
                                    for index in legal_slots)):
                if sum(bool(row["handle"]) for row in before["bag"]) >= int(before["bag_size"]):
                    raise RuntimeError("原生装备槽已占用，临时卸下旧装备需要一个空背包槽")
                engine.extension(action=2, target_unit=target, slot=legal_slots[0])
            engine.extension(
                (int(self._coerce_memory_value("rawcode", "AEqu")),),
                action=4, target_unit=target,
                item_rawcode=int(item["rawcode"]), item_handle=int(item["handle"]),
            )
            native_after = self.extension_snapshot_24268(target)
            source_slots = [
                int(row["slot"]) for row in native_after["equipment"]
                if int(row["handle"]) == int(item["handle"])
            ]
            if len(source_slots) != 1:
                raise RuntimeError("原生装备后没有读回唯一物品槽")
            source_slot = source_slots[0]
            displaced_items = [row for row in before["equipment"]
                               if int(row["handle"]) and not any(
                                   int(current["handle"]) == int(row["handle"])
                                   for current in native_after["equipment"])]
            for displaced in displaced_items:
                if sum(int(row["handle"]) == int(displaced["handle"])
                       for row in native_after["bag"]) != 1:
                    raise RuntimeError("原生装备替换后的旧物品未唯一返回背包")
            with ProcessMemory(int(self.pid), write=True) as memory:
                if int(memory.read_u64(aeq_data + 0xD8)) != records:
                    raise RuntimeError("装备记录已变化，拒绝使用旧地址")
                native_records = tuple(
                    (memory.read_u64(records + index * 12), memory.read_u32(records + index * 12 + 8))
                    for index in range(len(EQUIPMENT_SLOT_NAMES))
                )
                item_full = int(memory.read_u64(records + source_slot * 12))
                if not item_full or item_full == 0xFFFFFFFFFFFFFFFF:
                    raise RuntimeError("原生来源槽缺少物品完整实例句柄")
                from war3_object_registry import ObjectRegistry24268
                registry = ObjectRegistry24268.attach(memory)
                item_owner = registry.resolve_handle(memory, item_full)
                item_object = int(memory.read_u64(item_owner + 0x90))
                if (not self._sane_heap_ptr(item_object)
                        or memory.read_u64(item_object + 0x18) != item_full
                        or memory.read_u32(item_object + 0x70) != int(item["rawcode"])):
                    raise RuntimeError("原生来源槽物品身份与背包目标不一致")
                # Only redirect this instance. Other slots contain the game's
                # post-equip state; replaying old records can alias bag items.
                records_redirected = True
                memory.write_u64(records + source_slot * 12, 0xFFFFFFFFFFFFFFFF)
                memory.write_u32(records + source_slot * 12 + 8, 0)
                memory.write_u64(records + equipment_slot * 12, item_full)
                memory.write_u32(records + equipment_slot * 12 + 8, 0)
            for displaced in displaced_items:
                engine.extension(action=4, target_unit=target,
                                 item_rawcode=int(displaced["rawcode"]),
                                 item_handle=int(displaced["handle"]))
            after = self.extension_snapshot_24268(target)
            placed = after["equipment"][equipment_slot]
            duplicates = [row for row in after["equipment"] if int(row["handle"]) == int(item["handle"])]
            if int(placed["handle"]) != int(item["handle"]) or len(duplicates) != 1:
                raise RuntimeError("指定装备槽读回不是唯一的同一物品实例")
            if any(int(after["equipment"][index]["handle"]) != int(row["handle"])
                   for index, row in enumerate(before["equipment"]) if index != equipment_slot):
                raise RuntimeError("指定装备后其他槽位物品发生变化")
            if any(int(row["handle"]) == int(item["handle"]) for row in after["bag"]):
                raise RuntimeError("指定装备实例同时出现在背包中")
            after["equipment_effect_sync"] = _refresh_extension_equipment_effects(
                self,
                target, candidate,
            )
            return after
        except Exception as exc:
            rollback_error = ""
            try:
                # If raw record writes stopped midway, restore the native
                # post-equip layout before asking the engine to undo effects.
                # Never restore pre-equip records over an equipped instance.
                if records_redirected and native_records is not None:
                    current = self.extension_snapshot_24268(target)
                    for displaced in displaced_items:
                        slots = [int(row["slot"]) for row in current["equipment"]
                                 if int(row["handle"]) == int(displaced["handle"])]
                        for slot in slots:
                            engine.extension(action=2, target_unit=target, slot=slot)
                    with ProcessMemory(int(self.pid), write=True) as memory:
                        if int(memory.read_u64(aeq_data + 0xD8)) != records:
                            raise RuntimeError("回滚时装备记录已变化")
                        for index, (value, flags) in enumerate(native_records):
                            memory.write_u64(records + index * 12, value)
                            memory.write_u32(records + index * 12 + 8, flags)
                current = self.extension_snapshot_24268(target)
                slots = [int(row["slot"]) for row in current["equipment"]
                         if int(row["handle"]) == int(item["handle"])]
                if len(slots) > 1:
                    raise RuntimeError("回滚时目标物品占据多个槽位")
                for slot in slots:
                    engine.extension(action=2, target_unit=target, slot=slot)
                current = self.extension_snapshot_24268(target)
                for old in before["equipment"]:
                    if not int(old["handle"]) or any(int(row["handle"]) == int(old["handle"])
                                                     for row in current["equipment"]):
                        continue
                    if sum(int(row["handle"]) == int(old["handle"]) for row in current["bag"]) != 1:
                        raise RuntimeError("回滚时旧装备实例未在背包中")
                    engine.extension(action=4, target_unit=target,
                                     item_rawcode=int(old["rawcode"]), item_handle=int(old["handle"]))
                    current = self.extension_snapshot_24268(target)
                if [int(row["handle"]) for row in current["equipment"]] != [int(row["handle"]) for row in before["equipment"]]:
                    raise RuntimeError("回滚后装备槽实例与操作前不一致")
                if sorted(int(row["handle"]) for row in current["bag"] if int(row["handle"])) != sorted(int(row["handle"]) for row in before["bag"] if int(row["handle"])):
                    raise RuntimeError("回滚后背包实例与操作前不一致")
            except Exception as rollback_exc:
                rollback_error = f"；回滚未完成：{rollback_exc}"
            raise RuntimeError(
                f"指定装备事务失败：背包第 {bag_slot + 1} 格 "
                f"{format_rawcode(int(item['rawcode']))}（装备类型 {item_type}）"
                f"到{EQUIPMENT_SLOT_NAMES[equipment_slot]}槽；{exc}{rollback_error}"
            ) from exc


    def _unequip_non_equipment_slot_24268(self, before: dict, slot: int) -> dict:
        from war3_services.equipment_effects import classify_state, perform
        state = classify_state(self, before, slot, "equipment")
        if state["flags"] & 0x4000 and state["item_class"] == 7 and state["cached_type"] in range(1, 9):
            return perform(self, before, slot, slot, equip=False)
        # Older builds only moved the record. These instances have no native
        # equipment effects to remove; keep the recovery path for those items.
        if len(before.get("selection", {}).get("rows", ())) != 1:
            raise RuntimeError("普通物品卸下需要唯一选中英雄")
        empty_slots = [int(row["slot"]) for row in before["bag"]
                       if not int(row["handle"])]
        if not empty_slots:
            raise RuntimeError("扩展背包已满，无法卸下普通物品")
        destination = empty_slots[0]
        item = before["equipment"][slot]
        target = int(before["target_unit"])
        candidate, _native_handle = self._direct_selected_context()
        if int(candidate.unit_type_id) != int(before["selection"]["rows"][0]["rawcode"]):
            raise RuntimeError("选中英雄身份在卸下事务前发生变化")
        bag_before = equipment_before = None
        bag_records = equipment_records = 0
        try:
            with ProcessMemory(int(self.pid), write=True) as memory:
                records = self._extension_inventory_equipment_records_24268(memory, candidate)
                bag_records, equipment_records = records["AIni"], records["AEqu"]
                bag_before = tuple(memory.read(bag_records + index * 12, 12) for index in range(30))
                equipment_before = tuple(
                    memory.read(equipment_records + index * 12, 12) for index in range(9)
                )
                item_full = int(memory.read_u64(equipment_records + slot * 12))
                if item_full in (0, 0xFFFFFFFFFFFFFFFF):
                    raise RuntimeError("AEqu 槽位里没有待卸下物品实例")
                if int(memory.read_u64(bag_records + destination * 12)) != 0xFFFFFFFFFFFFFFFF:
                    raise RuntimeError("目标扩展背包槽已被占用")
                from war3_object_registry import ObjectRegistry24268
                registry = ObjectRegistry24268.attach(memory)
                owner = registry.resolve_handle(memory, item_full)
                item_object = int(memory.read_u64(owner + 0x90))
                if (not self._sane_heap_ptr(item_object)
                        or int(memory.read_u64(item_object + 0x18)) != item_full
                        or int(memory.read_u32(item_object + 0x70)) != int(item["rawcode"])):
                    raise RuntimeError("AEqu 普通物品实例身份不一致")
                memory.write_u64(bag_records + destination * 12, item_full)
                memory.write_u32(bag_records + destination * 12 + 8, 0)
                memory.write_u64(equipment_records + slot * 12, 0xFFFFFFFFFFFFFFFF)
                memory.write_u32(equipment_records + slot * 12 + 8, 0)
            after = self.extension_snapshot_24268(target)
            if (int(after["equipment"][slot]["handle"]) or
                    int(after["bag"][destination]["handle"]) != int(item["handle"]) or
                    sum(int(row["handle"]) == int(item["handle"])
                        for row in after["bag"]) != 1):
                raise RuntimeError("普通物品卸下后原生背包读回不一致")
            return after
        except Exception as exc:
            rollback_error = ""
            if bag_before is not None and equipment_before is not None:
                try:
                    with ProcessMemory(int(self.pid), write=True) as memory:
                        records = self._extension_inventory_equipment_records_24268(memory, candidate)
                        if records != {"AIni": bag_records, "AEqu": equipment_records}:
                            raise RuntimeError("回滚时 AIni/AEqu 记录地址已变化")
                        for index, raw in enumerate(bag_before):
                            memory.write(bag_records + index * 12, raw)
                        for index, raw in enumerate(equipment_before):
                            memory.write(equipment_records + index * 12, raw)
                    restored = self.extension_snapshot_24268(target)
                    if ([int(row["handle"]) for row in restored["bag"]] !=
                            [int(row["handle"]) for row in before["bag"]] or
                            [int(row["handle"]) for row in restored["equipment"]] !=
                            [int(row["handle"]) for row in before["equipment"]]):
                        raise RuntimeError("回滚后背包或装备槽实例不一致")
                except Exception as rollback_exc:
                    rollback_error = f"；回滚未完成：{rollback_exc}"
            raise RuntimeError(f"普通物品卸下事务失败：{exc}{rollback_error}") from exc


    def unequip_extension_slot_24268(self, slot: int) -> dict:
        slot = int(slot)
        if not 0 <= slot < len(EQUIPMENT_SLOT_NAMES):
            raise ValueError("装备槽无效")
        snapshot = self.extension_snapshot_24268()
        if int(snapshot["equipment"][slot]["handle"]) and getattr(self, '_game_session', None) is not None:
            # Runtime-classified ordinary items report the destination type
            # until their matching native removal restores the original class.
            # Looking only for type=0 misses those items after a successful equip.
            from war3_services.equipment_effects import preflight_creation, skipped_snapshot
            definition=preflight_creation(self,int(snapshot['equipment'][slot]['rawcode']),int(snapshot['target_unit']))
            if definition.get('skipped'):
                return skipped_snapshot(snapshot,int(snapshot['equipment'][slot]['rawcode']))
            if not definition['equipment_type']:
                return self._unequip_non_equipment_slot_24268(snapshot, slot)
        if (int(snapshot["equipment"][slot]["handle"]) and
                int(snapshot["equipment"][slot].get("equipment_type", 0)) == 0):
            return self._unequip_non_equipment_slot_24268(snapshot, slot)
        if sum(bool(item["handle"]) for item in snapshot["bag"]) >= int(snapshot["bag_size"]):
            raise RuntimeError("扩展背包已满，卸下装备会导致物品丢失；请先腾出一个背包槽")
        self._engine_instance_24268().extension(
            action=2, target_unit=int(snapshot["target_unit"]), slot=slot,
        )
        return self.extension_snapshot_24268()


    def save_extension_loadout_24268(self) -> dict:
        snapshot = self.extension_snapshot_24268()
        target = int(snapshot["target_unit"])
        name = str(getattr(self, "_extension_pending_loadout_name", "")).strip()
        self._extension_pending_loadout_name = ""
        if not name:
            store = getattr(self, "_extension_saved_loadouts", {})
            existing = store.get((int(getattr(self, "pid", 0)), target), {})
            name = f"套装{len(existing) + 1}"
        if len(name) > 64:
            raise ValueError("套装名称不能超过 64 个字符")
        equipment = tuple(
            (int(row["handle"]), int(row["rawcode"]), int(row.get("equipment_type", 0)))
            for row in snapshot["equipment"]
        )
        requires_any_slot = any(
            int(handle) and int(item_type) not in (
                int(EQUIPMENT_SLOT_TYPES[index]), 9,
            )
            for index, (handle, _rawcode, item_type) in enumerate(equipment)
        )
        key = (int(getattr(self, "pid", 0)), target)
        store = dict(getattr(self, "_extension_saved_loadouts", {}))
        per_target = dict(store.get(key, {}))
        per_target[name] = dict(
            name=name,
            target_unit=target,
            unit_type_id=int(next((row.get("rawcode", 0) for row in snapshot.get("selection", {}).get("rows", ()) if int(row.get("handle", 0)) == target), 0)),
            equipment=equipment,
            equipment_charges=tuple(int(row.get('charges', 0)) for row in snapshot['equipment']),
            requires_any_slot=bool(requires_any_slot),
        )
        store[key] = per_target
        self._extension_saved_loadouts = store
        # Keep the old single-record attribute readable for older callers;
        # new callers always resolve by target and custom name.
        self._extension_saved_loadout = dict(
            target_unit=target,
            equipment=tuple((handle, rawcode) for handle, rawcode, _ in equipment),
        )
        snapshot["loadout_names"] = self.extension_loadout_names_24268()
        return snapshot


    def extension_loadout_names_24268(self) -> tuple[str, ...]:
        from war3_loadout_restore import plan_choices
        return tuple(plan_choices(self))


    def save_extension_loadouts_for_selected_24268(self, name: str = "") -> dict:
        from war3_loadout_restore import run_loadout_batch
        return run_loadout_batch(self, name, 'save')


    def restore_extension_loadouts_for_selected_24268(self, name: str = "") -> dict:
        from war3_loadout_restore import run_loadout_batch
        return run_loadout_batch(self, name, 'restore')


    def _restore_extension_loadout_handles_24268(
        self, desired: tuple[tuple[int, int], ...], target_unit: int,
    ) -> dict:
        if len(desired) != len(EQUIPMENT_SLOT_NAMES):
            raise ValueError("套装记录槽位数无效")
        snapshot = self.extension_snapshot_24268()
        if int(snapshot["target_unit"]) != int(target_unit):
            raise RuntimeError("当前选中单位与套装记录不是同一个实例")

        def locations(current: dict) -> dict[int, tuple[str, int, int]]:
            found = {}
            for area in ("bag", "equipment"):
                for row in current[area]:
                    handle = int(row["handle"])
                    if handle:
                        if handle in found:
                            raise RuntimeError("同一物品实例同时出现在多个槽位")
                        found[handle] = (area, int(row["slot"]), int(row["rawcode"]))
            return found

        initial_locations = locations(snapshot)
        desired_pairs = tuple((int(row[0]), int(row[1])) for row in desired)
        for row in desired:
            handle, rawcode = int(row[0]), int(row[1])
            if not handle:
                continue
            location = initial_locations.get(handle)
            if location is None or location[2] != rawcode:
                raise RuntimeError(
                    f"套装物品实例 0x{handle:x}/{format_rawcode(rawcode)} 已不在当前背包或装备栏"
                )

        for slot, (wanted_handle, wanted_rawcode) in enumerate(desired_pairs):
            snapshot = self.extension_snapshot_24268()
            current_handle = int(snapshot["equipment"][slot]["handle"])
            if current_handle == wanted_handle:
                continue
            current_locations = locations(snapshot)
            if current_handle:
                bag_size = int(snapshot["bag_size"])
                occupied = sum(bool(int(row["handle"])) for row in snapshot["bag"][:bag_size])
                if occupied >= bag_size:
                    raise RuntimeError("扩展背包已满，无法临时卸下当前装备")
                self.unequip_extension_slot_24268(slot)
                snapshot = self.extension_snapshot_24268()
                current_locations = locations(snapshot)
            if wanted_handle:
                area, current_slot, actual_rawcode = current_locations[wanted_handle]
                if actual_rawcode != wanted_rawcode:
                    raise RuntimeError("套装物品实例身份在恢复期间发生变化")
                if area == "equipment":
                    bag_size = int(snapshot["bag_size"])
                    occupied = sum(bool(int(row["handle"])) for row in snapshot["bag"][:bag_size])
                    if occupied >= bag_size:
                        raise RuntimeError("扩展背包已满，无法交换装备槽")
                    self.unequip_extension_slot_24268(current_slot)
                    snapshot = self.extension_snapshot_24268()
                bag_slots = [
                    int(row["slot"]) for row in snapshot["bag"]
                    if int(row["handle"]) == wanted_handle
                ]
                if len(bag_slots) != 1:
                    raise RuntimeError("套装物品实例未唯一回到扩展背包")
                self.equip_extension_bag_item_to_slot_24268(bag_slots[0], slot)

        after = self.extension_snapshot_24268()
        actual = tuple((int(row["handle"]), int(row["rawcode"])) for row in after["equipment"])
        if actual != desired_pairs:
            raise RuntimeError("套装恢复后的九槽实例与保存记录不一致")
        return after


    def restore_extension_loadout_24268(self) -> dict:
        name = str(getattr(self, "_extension_pending_restore_name", "")).strip()
        self._extension_pending_restore_name = ""
        before = self.extension_snapshot_24268()
        key = (int(getattr(self, "pid", 0)), int(before["target_unit"]))
        store = getattr(self, "_extension_saved_loadouts", {})
        per_target = store.get(key, {})
        from war3_loadout_restore import plan_choices
        saved = getattr(self, '_extension_pending_restore_record', None)
        self._extension_pending_restore_record = None
        choices = plan_choices(self)
        if saved is None and not choices and not name:
            legacy = getattr(self, "_extension_saved_loadout", None)
            if legacy:
                saved = dict(legacy, name="旧套装", equipment=tuple(
                    (int(handle), int(rawcode), 0) for handle, rawcode in legacy["equipment"]))
        if saved is None and name:
            saved = choices.get(name)
            if saved is None:
                raise RuntimeError("未找到唯一的套装方案；请选择列表中带编号的具体方案")
        if saved is None and not name and len(choices) == 1:
            saved = next(iter(choices.values()))
        if saved is None:
            raise RuntimeError("没有唯一可恢复的九槽套装，请先选择或导入方案")
        from war3_loadout_restore import regenerate_loadout, run_loadout_batch
        # A manually selected plan is independent of its saved hero. The
        # one-click matcher binds one hero and supplies its matching record.
        if getattr(self, '_elephant_selection_override', None) is None and len(
            before.get('selection', {}).get('rows', ())) > 1:
            return run_loadout_batch(self, saved['name'], 'apply', saved)
        return regenerate_loadout(self, saved, before, EQUIPMENT_SLOT_TYPES)


    def audit_extension_equipment_24268(self, repair: bool = False) -> dict:
        snapshot = self.extension_snapshot_24268()
        issues = []
        bad_slots = []
        seen = {}
        for area in ("bag", "equipment"):
            for row in snapshot[area]:
                handle = int(row["handle"])
                if not handle:
                    continue
                if handle in seen:
                    issues.append(
                        f"实例 0x{handle:x} 同时位于 {seen[handle]} 与 {area}:{int(row['slot']) + 1}"
                    )
                else:
                    seen[handle] = f"{area}:{int(row['slot']) + 1}"
        for row in snapshot["equipment"]:
            slot = int(row["slot"])
            if not int(row["handle"]):
                continue
            item_type = int(row.get("equipment_type", 0))
            expected = int(EQUIPMENT_SLOT_TYPES[slot])
            if item_type not in (expected, 9):
                issues.append(
                    f"{EQUIPMENT_SLOT_NAMES[slot]}槽中的 {format_rawcode(int(row['rawcode']))} "
                    f"类型为{EQUIPMENT_TYPE_NAMES.get(item_type, str(item_type))}"
                )
                bad_slots.append(slot)
        repaired = []
        if repair and bad_slots:
            bag_size = int(snapshot["bag_size"])
            occupied = sum(bool(int(row["handle"])) for row in snapshot["bag"][:bag_size])
            if bag_size - occupied < len(bad_slots):
                raise RuntimeError("扩展背包空位不足，无法安全卸下全部错槽装备")
            for slot in bad_slots:
                self._engine_instance_24268().extension(
                    action=2, target_unit=int(snapshot["target_unit"]), slot=slot,
                )
                repaired.append(slot)
            snapshot = self.extension_snapshot_24268()
            remaining = self.audit_extension_equipment_24268(False)
            if remaining["issues"]:
                raise RuntimeError("装备结构修复后仍存在异常：" + "；".join(remaining["issues"]))
        return dict(snapshot=snapshot, issues=tuple(issues), repaired=tuple(repaired))


    def set_extension_equipment_any_slot_24268(self, enabled: bool = True) -> dict:
        """Enable the verified runtime AEqu redirection route for this unit.

        Native 3.0 equipment keeps its existing UnitEquipItem route. Ordinary
        campaign items use a separate, transactional AIni-to-AEqu instance
        move with full readback and rollback. The obsolete action=9 profile
        field setter remains unused.
        """
        snapshot = self.extension_snapshot_24268()
        target = int(snapshot["target_unit"])
        key = (int(self.pid), target)
        enabled_by_unit = dict(getattr(self, "_extension_any_slot_enabled", {}))
        if enabled:
            candidate, _native_handle = self._direct_selected_context()
            with ProcessMemory(int(self.pid)) as memory:
                self._extension_inventory_equipment_records_24268(memory, candidate)
            enabled_by_unit[key] = True
        else:
            enabled_by_unit.pop(key, None)
        self._extension_any_slot_enabled = enabled_by_unit
        return self.extension_snapshot_24268(target)


    def selected_talent_batch_24268(self, action: str, controller: str = "", tier: int = 0, choice: str = "") -> dict:
        if action not in ("grant", "reset", "choice"):
            raise ValueError("未知天赋批量操作")
        first = self.extension_snapshot_24268()
        targets = tuple(dict.fromkeys(
            int(row["handle"]) for row in first["selection"]["rows"]
            if int(row.get("handle", 0))
        ))
        if not targets:
            raise RuntimeError("当前没有可处理的选中单位")
        results = []
        last = first
        for target in targets:
            try:
                snapshot = self.extension_snapshot_24268(target)
                active = [name for name in TALENT_CONTROLLERS
                          if snapshot["abilities"].get(int.from_bytes(name.encode("ascii"), "big"), 0) > 0]
                if not active:
                    results.append(dict(target=target, status="skipped", reason="没有天赋控制器"))
                    continue
                if len(active) != 1:
                    raise RuntimeError("存在多个天赋控制器")
                if action == "choice" and active[0] != controller:
                    results.append(dict(target=target, status="skipped", reason="天赋树与所选选项不匹配"))
                    continue
                if action == "grant":
                    last = self.grant_talent_point_24268(target_unit=target)
                elif action == "reset":
                    last = self.reset_talents_24268(target_unit=target)
                else:
                    last = self.add_talent_choice_24268(controller, tier, choice, target_unit=target)
                results.append(dict(target=target, status="success"))
            except Exception as exc:
                results.append(dict(target=target, status="failed", reason=str(exc)))
        return dict(snapshot=last, results=results,
                    succeeded=sum(row["status"] == "success" for row in results),
                    skipped=sum(row["status"] == "skipped" for row in results),
                    failed=sum(row["status"] == "failed" for row in results))


    def grant_talent_point_24268(self, *, target_unit: int = 0) -> dict:
        snapshot = (self.extension_snapshot_24268(target_unit) if target_unit else self.extension_snapshot_24268())
        state = self.talent_state_24268(snapshot)
        controller = state["controller"]
        if not controller:
            raise RuntimeError("当前单位没有官方天赋控制器")
        point_cap = int(state["tier_count"]) * 3
        if int(state["total_points"]) >= point_cap:
            raise RuntimeError("当前天赋树已经达到可消费点数上限")
        # ttal is an auto-consumed PowerUp (ATap), not an inventory item.
        # Native consumption works with all six classic slots occupied;
        # verify the actual point counter instead of requiring an empty slot.
        self._engine_instance_24268().extension(
            (int(self._coerce_memory_value("rawcode", controller)) & 0xFFFFFFFF,),
            action=7,
            target_unit=int(snapshot["target_unit"]),
            item_rawcode=int(self._coerce_memory_value("rawcode", "ttal")) & 0xFFFFFFFF,
        )
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            after = (self.extension_snapshot_24268(target_unit) if target_unit else self.extension_snapshot_24268())
            if int(after["target_unit"]) != int(snapshot["target_unit"]):
                raise RuntimeError("天赋点操作后选中目标已变化；请重新读取原英雄，勿重复加点")
            after_state = self.talent_state_24268(after)
            if after_state["controller"] != controller:
                raise RuntimeError("天赋点操作后控制器已变化；请重新读取，勿重复加点")
            if int(after_state["remaining_points"]) == int(state["remaining_points"]) + 1:
                return after
            time.sleep(0.05)
        raise RuntimeError("增加天赋点后 1 秒内未读回新的可用点数")


    def talent_state_24268(self, snapshot: dict | None = None) -> dict:
        snapshot = snapshot or self.extension_snapshot_24268()
        levels = {int(code): int(level) for code, level in snapshot.get("abilities", {}).items()}
        active = []
        for controller, (name, tiers) in TALENT_CONTROLLERS.items():
            level = levels.get(int.from_bytes(controller.encode("ascii"), "big"), 0)
            if level > 0:
                active.append((controller, name, tiers, level))
        if len(active) > 1:
            return dict(controller="", name="多个控制器", tier_count=0, controller_level=0,
                        total_points=0, used_points=0, remaining_points=0, tiers=(),
                        anomalies=("检测到多个官方天赋控制器",))
        if not active:
            return dict(controller="", name="", tier_count=0, controller_level=0,
                        total_points=0, used_points=0, remaining_points=0, tiers=(),
                        anomalies=())
        controller, name, tiers, controller_level = active[0]
        tier_rows = []
        anomalies = []
        for index, choices in enumerate(tiers):
            selected = tuple(choice for choice in choices
                             if levels.get(int.from_bytes(choice.encode("ascii"), "big"), 0) > 0)
            if len(selected) > 1:
                anomalies.append(f"第 {index + 1} 层同时存在多个天赋")
            tier_rows.append(dict(index=index, choices=tuple(choices), selected=selected))
        used = sum(len(row["selected"]) for row in tier_rows)
        # The controller level is not the point counter.  3.0 stores the
        # currently consumable points in ATal+0x11c; read it from the live
        # controller when a process is available.  Snapshot-only callers keep
        # the old derived fallback for compatibility with tests and fixtures.
        live_remaining = None
        native_records = None
        native_choices = None
        point_read_error = None
        try:
            if getattr(self, "pid", 0):
                with ProcessMemory(int(self.pid)) as memory:
                    native_rows = [row for row in snapshot.get("selection", {}).get("rows", ())
                                   if int(row["handle"]) == int(snapshot["target_unit"])]
                    if len(native_rows) != 1:
                        raise RuntimeError("天赋快照缺少唯一原生目标")
                    rawcode = int(native_rows[0]["rawcode"])
                    # Extension snapshots follow native selection order, which
                    # can differ from the persistent candidate enumeration.
                    candidates = [candidate for candidate, _ in self._selected_candidates_snapshot(None)
                                  if int(candidate.unit_type_id) == rawcode]
                    if len(candidates) != 1:
                        raise RuntimeError("天赋控制器目标身份不唯一")
                    candidate = candidates[0]
                    wanted = int.from_bytes(controller.encode("ascii"), "big")
                    matches = self._ability_instances_from_candidate(
                        memory, candidate, required_rawcodes={wanted}, allow_global_scan=False,
                    )
                    # UnitRemoveAbility leaves retired owner-list nodes alive.
                    # Select the active controller, not every matching rawcode.
                    matches = [instance for instance in matches
                               if not memory.read_u32(instance.data_address + 0x38) & 0x8]
                    if len(matches) == 1:
                        # Read six native tier records and the point counter
                        # from one stable block, rather than inferring UI
                        # selection from the presence of granted abilities.
                        address = matches[0].data_address + 0xD4
                        block = memory.read(address, 76)
                        if memory.read(address, 76) != block:
                            raise RuntimeError("天赋选择记录在读取期间发生变化")
                        value = struct.unpack_from("<I", block, 72)[0]
                        if 0 <= value <= len(tiers) * 3:
                            live_remaining = int(value)
                            native_records = tuple(struct.unpack_from("<QI", block, index * 12)
                                                   for index in range(len(tiers)))
                            from war3_object_registry import ObjectRegistry24268
                            registry = getattr(self, "_classic_object_registry", None)
                            native_choices = []
                            for index, (full, _flags) in enumerate(native_records):
                                choice = ""
                                if full != 0xFFFFFFFFFFFFFFFF:
                                    registry = registry or ObjectRegistry24268.attach(memory)
                                    wrapper = registry.resolve_handle(memory, full)
                                    data = memory.read_u64(wrapper + 0x90)
                                    if memory.read_u64(data + 0x68) != candidate.unit_address:
                                        raise RuntimeError("天赋选择记录属于其他单位")
                                    choice = memory.read_u32(data + 0x70).to_bytes(4, "big").decode("ascii")
                                    if choice not in tiers[index]:
                                        raise RuntimeError("天赋选择记录与当前层不匹配")
                                native_choices.append(choice)
        except Exception as exc:
            point_read_error = exc
            live_remaining = None
        if live_remaining is None and getattr(self, "pid", 0):
            raise RuntimeError("无法读取当前天赋控制器的真实剩余点数（ATal+0x11c）："
                               + str(point_read_error or "控制器实例缺失或点数越界")) from point_read_error
        if live_remaining is None:
            total = min(max(int(controller_level) - 1, 0), len(tiers) * 3)
            remaining = max(total - used, 0)
            point_source = "controller_level_fallback"
        else:
            remaining = live_remaining
            # Extra same-tier effects added by the trainer were never debited
            # by ATal. Do not count them as earned/spent native talent points.
            spent = sum(handle != 0xFFFFFFFFFFFFFFFF for handle, _flags in native_records)
            total = spent + remaining
            point_source = "ATal+0x11c"
        if native_records is not None:
            for row, (record_handle, record_flags), native_choice in zip(tier_rows, native_records, native_choices):
                row["native_record_handle"] = record_handle
                row["native_record_flags"] = record_flags
                row["native_record_present"] = record_handle != 0xFFFFFFFFFFFFFFFF
                row["native_choice"] = native_choice
                if row["selected"] and not row["native_record_present"]:
                    anomalies.append(f"第 {row['index'] + 1} 层存在天赋技能，但原生选择记录为空")
        return dict(
            controller=controller,
            name=name,
            tier_count=len(tiers),
            controller_level=int(controller_level),
            total_points=total,
            used_points=used if native_records is None else spent,
            selected_count=used,
            remaining_points=remaining,
            point_source=point_source,
            tiers=tuple(tier_rows),
            anomalies=tuple(anomalies),
        )


    def unlock_talent_tier_24268(self, tier: int) -> dict:
        tier = int(tier)
        before = self.extension_snapshot_24268()
        state = self.talent_state_24268(before)
        if not state["controller"]:
            raise RuntimeError("当前单位没有唯一的官方天赋控制器")
        if not 0 <= tier < int(state["tier_count"]):
            raise ValueError("天赋层无效")
        if not state["tiers"][tier]["selected"]:
            raise RuntimeError("所选层尚未选择天赋，无需解除层限制")
        controller = int.from_bytes(state["controller"].encode("ascii"), "big")
        target_handle = int(before["target_unit"])
        candidates = [
            (current, int(handle))
            for current, handle in self._selected_candidates_snapshot(None)
            if int(handle) == target_handle
        ]
        if len(candidates) != 1:
            raise RuntimeError("天赋目标不在当前稳定选择快照中；请重新读取当前单位")
        candidate, target_handle = candidates[0]
        if not candidate.unit_address or not candidate.owner_address:
            raise RuntimeError("无法绑定当前单位的原生身份")
        # Use the identity-bound native helper. Extension action 10 is an
        # obsolete experimental route and intentionally rejects this write.
        with self._bound_elephant_selection(candidate, target_handle):
            results = self._run_native_helper_ops(
                int(candidate.unit_address),
                (
                    (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0,
                     int(candidate.unit_address), int(candidate.handle), int(candidate.owner_address)),
                    (self.NATIVE_HELPER_OP_UNLOCK_TALENT_TIER, controller, tier, 0, 0),
                ),
            )
        if len(results) != 2 or results[1].result != tier + 1:
            raise RuntimeError("原生天赋层解除限制未确认")
        after = self.extension_snapshot_24268()
        after_state = self.talent_state_24268(after)
        if (after_state["controller"] != state["controller"]
                or after_state["tiers"][tier]["selected"] != state["tiers"][tier]["selected"]):
            raise RuntimeError("解除层限制后已获得天赋发生变化")
        return after


    def _talent_icon_candidate_24268(self, target_unit: int) -> UnitCandidate:
        override = getattr(self, "_elephant_selection_override", None)
        snapshot = (override,) if override is not None else self._selected_candidates_snapshot(None)
        matches = [candidate for candidate, handle in snapshot if int(handle) == int(target_unit)]
        if not matches and getattr(self, "_native_selection_unavailable", False):
            # Classic snapshots carry full object identities, not JASS IDs.
            # Cross-check a fresh native selection; never match by row order.
            native = self._engine_instance_24268().ability_batch(int.from_bytes(b"AIxr", "big"))
            rows = [row for row in native["rows"] if int(row["handle"]) == int(target_unit)]
            if len(rows) == 1:
                rawcode = int(rows[0]["rawcode"])
                if sum(int(row["rawcode"]) == rawcode for row in native["rows"]) == 1:
                    matches = [candidate for candidate, _handle in snapshot
                               if int(candidate.unit_type_id) == rawcode]
        if len(matches) != 1:
            raise RuntimeError("天赋图标目标不在唯一的当前选择快照中")
        return matches[0]


    def add_talent_choice_24268(self, controller: str, tier: int, choice: str, *, target_unit: int = 0) -> dict:
        """Add one same-tier effect with the persistent command-card predicate."""
        before = (self.extension_snapshot_24268(target_unit) if target_unit else self.extension_snapshot_24268())
        state = self.talent_state_24268(before)
        if state["controller"] != controller:
            raise RuntimeError("当前天赋控制器已经变化，请重新读取")
        tier = int(tier)
        if not 0 <= tier < int(state["tier_count"]):
            raise ValueError("天赋层无效")
        row = state["tiers"][tier]
        if choice not in row["choices"]:
            raise ValueError("目标天赋不属于所选层")
        if choice in row["selected"]:
            return before
        # Additional same-tier effects are applied as ordinary passive
        # abilities and are intentionally free. The native point counter is
        # consumed only by the game's own talent-order path; requiring a
        # remaining point here made the advertised arbitrary same-tier action
        # fail exactly when the native tree was already full.
        # The 3.0 engine accepts an additional choice through its normal
        # ability path. Do not invoke the unverified tier-record callback;
        # it can crash when the tier already contains multiple choices.
        if getattr(self, "pid", 0):
            display = self.refresh_talent_icon_display_24268()
            if not display.get("installed"):
                raise RuntimeError(
                    "天赋图标判定模块未安装，本次未添加天赋："
                    + str(display.get("error", display.get("reason", "未知错误")))
                )
        try:
            self.ability_batch_24268(choice, 1, 1, target_unit=int(before["target_unit"]))
            # The 3.0 helper table does not expose BlzUnitHideAbility on every
            # campaign process. Recreate only this newly-added ability through
            # the stable extension route so the game refreshes its own card.
            self.ability_batch_24268(choice, 2, 0, target_unit=int(before["target_unit"]))
            self.ability_batch_24268(choice, 1, 1, target_unit=int(before["target_unit"]))
        except Exception:
            try:
                self.ability_batch_24268(choice, 2, 0, target_unit=int(before["target_unit"]))
            except Exception:
                pass
            raise
        after = (self.extension_snapshot_24268(target_unit) if target_unit else self.extension_snapshot_24268())
        after_state = self.talent_state_24268(after)
        selected = tuple(after_state["tiers"][tier]["selected"])
        if after_state["controller"] != controller or choice not in selected:
            try:
                self.ability_batch_24268(choice, 2, 0, target_unit=int(before["target_unit"]))
            except Exception:
                pass
            raise RuntimeError("任意天赋写入后没有读回目标选项")
        return after


    def _talent_icon_display_path_24268(self) -> Path:
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        candidates = (
            root / "tools" / "war3_talent_icon_display.dll",
            root / "analysis" / "talent-icon-display-207" / "verified" / "war3_talent_icon_display.dll",
            Path(__file__).resolve().parent / "tools" / "war3_talent_icon_display.dll",
            Path(__file__).resolve().parent / "analysis" / "talent-icon-display-207" / "verified" / "war3_talent_icon_display.dll",
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        raise RuntimeError("天赋图标显示模块未随当前版本打包")


    def refresh_talent_icon_display_24268(self) -> dict:
        """Install the UI predicate extension when the native talent panel is loaded."""
        display = getattr(self, "_talent_icon_display", None)
        if display is not None:
            try:
                state = display.snapshot()
                self._talent_icon_display_error = ""
                return state
            except Exception as exc:
                try:
                    display.close()
                except Exception as cleanup_exc:
                    reason = f"天赋图标模块状态不确定，映射已保留；原错误：{exc}；清理错误：{cleanup_exc}"
                    self._talent_icon_display_error = reason
                    return {"installed": False, "reason": "cleanup_uncertain", "retained": True, "error": reason}
                self._talent_icon_display = None
        hwnd = getattr(self, "hwnd", 0)
        if not hwnd:
            reason = "游戏窗口尚未绑定，图标刷新未执行"
            self._talent_icon_display_error = reason
            return {"installed": False, "reason": "window_unavailable", "error": reason}
        from war3_talent_icon_display import TalentIconDisplay

        try:
            display = TalentIconDisplay(
                self._engine_instance_24268(),
                self._talent_icon_display_path_24268(),
            )
            state = display.install()
        except Exception as exc:
            self._talent_icon_display_error = str(exc)
            reason = "code_unavailable" if getattr(display, "observed_code", "") == "c7" * 36 else "install_failed"
            try:
                if display is not None:
                    display.close()
            except Exception as cleanup_exc:
                self._talent_icon_display = display
                message = f"天赋图标模块安装失败且清理未确认，映射已保留；原错误：{exc}；清理错误：{cleanup_exc}"
                self._talent_icon_display_error = message
                return {"installed": False, "reason": "cleanup_uncertain", "retained": True, "error": message}
            self._talent_icon_display = None
            return {"installed": False, "reason": reason, "error": str(exc)}
        self._talent_icon_display = display
        self._talent_icon_display_error = ""
        return state


    def select_native_talent_24268(self, controller: str, tier: int, choice: str, *, target_unit: int) -> dict:
        before = self.extension_snapshot_24268(target_unit)
        state = self.talent_state_24268(before)
        if state["controller"] != controller or not 0 <= tier < state["tier_count"]:
            raise RuntimeError("原生天赋选择目标已变化")
        row = state["tiers"][tier]
        if choice not in row["choices"] or row.get("native_record_present") or state["remaining_points"] < 1:
            raise RuntimeError("原生天赋层不可选或点数不足")
        order = 0xD0311 + tier * 3 + row["choices"].index(choice)
        code = lambda text: int.from_bytes(text.encode("ascii"), "big")
        self._engine_instance_24268().talent_order(target_unit, code(controller), order, code(choice))
        deadline = time.monotonic() + 1.0
        while True:
            after = self.extension_snapshot_24268(target_unit)
            result = self.talent_state_24268(after)
            if (result["controller"] == controller and result["remaining_points"] == state["remaining_points"] - 1
                    and result["tiers"][tier].get("native_choice") == choice):
                return after
            if time.monotonic() >= deadline:
                raise RuntimeError("原生加点后记录或扣点未吻合；未重复发送命令")
            time.sleep(0.05)


    def reset_talents_24268(self, *, target_unit: int = 0) -> dict:
        before = (self.extension_snapshot_24268(target_unit) if target_unit else self.extension_snapshot_24268())
        state = self.talent_state_24268(before)
        if not state["controller"]:
            raise RuntimeError("当前单位没有唯一的官方天赋控制器")
        target_unit = int(before["target_unit"])
        controller = state["controller"]
        if state.get("point_source") != "ATal+0x11c":
            raise RuntimeError("洗点需要真实点数和原生选择记录")
        native = tuple((row["index"], row.get("native_choice", "")) for row in state["tiers"]
                       if row.get("native_record_present"))
        if any(not choice for _tier, choice in native):
            raise RuntimeError("洗点前存在无法识别的原生选择记录")
        # Snapshot-only callers may expose the live point fields without the
        # derived total. The native total is remaining points plus native
        # debit records; extra same-tier effects are free and must not inflate
        # the refund target.
        target_total = int(state.get("total_points", int(state["remaining_points"]) + len(native)))
        if not 0 <= target_total <= int(state["tier_count"]) * 3:
            raise RuntimeError("洗点返还点数越界")
        touched = False

        def clear_and_rebuild():
            current = self.extension_snapshot_24268(target_unit)
            for row in state["tiers"]:
                for choice in row["choices"]:
                    if not current["abilities"].get(int.from_bytes(choice.encode("ascii"), "big"), 0):
                        continue
                    self.ability_batch_24268(choice, 2, 0, target_unit=target_unit)
            if current["abilities"].get(int.from_bytes(controller.encode("ascii"), "big"), 0):
                self.ability_batch_24268(controller, 2, 0, target_unit=target_unit)
            self.ability_batch_24268(controller, 1, 1, target_unit=target_unit)
            fresh = self.extension_snapshot_24268(target_unit)
            fresh_state = self.talent_state_24268(fresh)
            if (fresh_state["controller"] != controller or fresh_state["remaining_points"]
                    or fresh_state["used_points"] or any(row.get("native_record_present") for row in fresh_state["tiers"])):
                raise RuntimeError("重建天赋控制器后状态未清空")
            return fresh

        def grant_until(snapshot: dict, target_remaining: int) -> dict:
            current = self.talent_state_24268(snapshot)
            if current["remaining_points"] > target_remaining:
                raise RuntimeError(
                    f"重建后的天赋点数已超过目标：{current['remaining_points']} > {target_remaining}"
                )
            for _ in range(target_remaining - int(current["remaining_points"])):
                snapshot = self.grant_talent_point_24268(target_unit=target_unit)
                current = self.talent_state_24268(snapshot)
            if current["remaining_points"] != target_remaining:
                raise RuntimeError(
                    f"补点后读回不一致：{current['remaining_points']} != {target_remaining}"
                )
            return snapshot

        try:
            touched = True
            after = clear_and_rebuild()
            after = grant_until(after, target_total)
            after_state = self.talent_state_24268(after)
            if after_state["remaining_points"] != target_total or after_state["used_points"]:
                raise RuntimeError("洗点后的点数或选择状态不一致")
            if any(before.get(key) != after.get(key) for key in ("bag_size", "bag", "equipment")):
                raise RuntimeError("洗点期间背包或装备发生变化")
            return after
        except Exception as exc:
            rollback_errors = []
            if touched:
                try:
                    restored_base = clear_and_rebuild()
                    restored_base = grant_until(
                        restored_base,
                        int(state["remaining_points"]) + len(native),
                    )
                    for tier, choice in native:
                        self.select_native_talent_24268(controller, tier, choice, target_unit=target_unit)
                    self._restore_extra_talent_choices_24268(state, target_unit)
                    restored_snapshot = self.extension_snapshot_24268(target_unit)
                    restored = self.talent_state_24268(restored_snapshot)
                    if restored["remaining_points"] != state["remaining_points"]:
                        raise RuntimeError("恢复后天赋点数不一致")
                    expected_choices = tuple((tuple(row["selected"]), row.get("native_choice", ""))
                                             for row in state["tiers"])
                    restored_choices = tuple((tuple(row["selected"]), row.get("native_choice", ""))
                                             for row in restored["tiers"])
                    if restored["controller"] != controller or restored_choices != expected_choices:
                        raise RuntimeError("恢复后的原生选择或额外同层效果不一致")
                    if any(before.get(key) != restored_snapshot.get(key) for key in ("bag_size", "bag", "equipment")):
                        raise RuntimeError("恢复后的背包或装备不一致")
                except Exception as rollback_error:
                    rollback_errors.append(str(rollback_error))
            suffix = f"；回滚异常：{'；'.join(rollback_errors)}" if rollback_errors else ""
            raise RuntimeError(f"洗点失败：{exc}{suffix}") from exc


    def _restore_extra_talent_choices_24268(self, state: dict, target_unit: int) -> None:
        for row in state["tiers"]:
            for choice in row["selected"]:
                if choice != row.get("native_choice", ""):
                    self.add_talent_choice_24268(
                        state["controller"], int(row["index"]), choice,
                        target_unit=target_unit,
                    )
