"""Bundled layout/algorithm providers; imported profiles contain data only.

These providers interpret memory. They do not select transport, retain game
objects, or decide equip/restore transactions. Data packs name only bundled
algorithms; instruction-patching implementations keep separate build approval.
"""
from __future__ import annotations

from functools import cached_property
import math
from operator import itemgetter
import struct


class LayoutProvider:
    def __init__(self, profile):
        self.profile = profile


class EquipmentAdapter(LayoutProvider):
    @cached_property
    def layout(self):
        return self.profile.section("equipment_runtime")

    @cached_property
    def record_layout(self):
        return self.profile.section("layouts")["equipment_record"]

    def inventory_records(self, memory, unit_address, instances, codes, pointer):
        by_rawcode = {}
        rawcode_offset = self.profile.section("layouts")["ability"]["rawcode"]
        for instance in instances:
            data = int(instance.data_address)
            by_rawcode.setdefault(int(memory.read_u32(data + rawcode_offset)), []).append(data)
        if any(len(by_rawcode.get(code, ())) != 1 for code in codes.values()):
            raise RuntimeError("当前单位没有唯一的 AIni 扩展背包和 AEqu 装备组件")
        result = {}
        for name, count in (("AIni", 30), ("AEqu", 9)):
            data = by_rawcode[codes[name]][0]
            if (int(memory.read_u64(data + self.layout["ability_owner"])) != int(unit_address)
                    or int(memory.read_u64(data + self.layout["equipment_count"])) != count
                    or int(memory.read_u64(data + self.layout["equipment_capacity"])) < count):
                raise RuntimeError(f"{name} 组件身份或槽位数量已经变化")
            records = int(memory.read_u64(data + self.layout["equipment_records"]))
            if not pointer(records):
                raise RuntimeError(f"{name} 槽位记录地址无效")
            result[name] = records
        return result

    def records_pointer(self, memory, component):
        return int(memory.read_u64(component + self.layout["equipment_records"]))

    def record_handle(self, memory, records, index):
        return int(memory.read_u64(records + index * self.record_layout["stride"]))

    def read_records(self, memory, records, count):
        stride, state = self.record_layout["stride"], self.record_layout["state"]
        return tuple((memory.read_u64(records + index * stride),
                      memory.read_u32(records + index * stride + state))
                     for index in range(count))

    def move_record(self, memory, records, source, target, full_handle, state):
        stride, offset = self.record_layout["stride"], self.record_layout["state"]
        memory.write_u64(records + source * stride, 0xFFFFFFFFFFFFFFFF)
        memory.write_u32(records + source * stride + offset, 0)
        memory.write_u64(records + target * stride, full_handle)
        memory.write_u32(records + target * stride + offset, state)

    def restore_records(self, memory, records, values):
        stride, state = self.record_layout["stride"], self.record_layout["state"]
        for index, (value, flags) in enumerate(values):
            memory.write_u64(records + index * stride, value)
            memory.write_u32(records + index * stride + state, flags)

    def item_object(self, memory, owner, full_handle, rawcode, pointer):
        registry = self.profile.section("registry")
        address = int(memory.read_u64(owner + registry["owner_data"]))
        if (not pointer(address)
                or memory.read_u64(address + registry["object_handle"]) != full_handle
                or memory.read_u32(address + registry["object_rawcode"]) != rawcode):
            raise RuntimeError("原生来源槽物品身份与背包目标不一致")
        return address


class ComponentAdapter(LayoutProvider):
    def frame_context_timeout_ms(self) -> int:
        return 250

    def allows_unreadable_code_check(self, name: str, error: BaseException) -> bool:
        """Preserve the released resolver's protected-page handling.

        Other checks stay strict unless a version adapter explicitly declares
        their protection behavior. Readable mismatches are never accepted.
        """
        return name == "resolver" and getattr(error, "winerror", None) == 299

    def decode_game_state(self, encoded):
        d = self.profile.section("decoder")
        mask = 0xFFFFFFFFFFFFFFFF
        value = ((encoded >> d["ror"]) | (encoded << (64 - d["ror"]))) & mask
        value = ((value << d["rol"]) | (value >> (64 - d["rol"]))) & mask
        value = ((value + d["add1"]) & mask) ^ d["xor"]
        return (value + d["add2"]) & mask

    @cached_property
    def _providers(self):
        return {}

    def subprovider(self, name):
        if name not in self._providers:
            from war3_adapter_properties import PropertyAdapter
            from war3_adapter_legacy import LegacyAdapterMethods
            factories = {"attack": AttackAdapter, "properties": PropertyAdapter,
                         "items": ItemAdapter, "abilities": AbilityAdapter,
                         "units": UnitAdapter, "selection": SelectionAdapter}
            self._providers[name] = (LegacyAdapterMethods if name == "legacy"
                                     else factories[name](self.profile))
        return self._providers[name]

    @cached_property
    def layout(self):
        return self.profile.section("layouts")["component_list"]

    @cached_property
    def snapshot_decoder(self):
        names = ("tag", "handle", "previous", "next", "owner", "data")
        ordered = sorted(names, key=self.layout.__getitem__)
        cursor = self.layout["snapshot_start"]
        parts = ["<"]
        for name in ordered:
            gap = self.layout[name] - cursor
            if gap:
                parts.append(str(gap) + "x")
            parts.append("Q")
            cursor = self.layout[name] + 8
        decoder = struct.Struct("".join(parts))
        indices = tuple(ordered.index(name) for name in names)
        reorder = None if indices == tuple(range(len(names))) else itemgetter(*indices)
        return decoder, reorder

    def nodes(self, memory, registry, owner):
        layout, object_layout = self.layout, self.profile.section("registry")
        decoder, reorder = self.snapshot_decoder

        def pointer(value):
            return 0x10000 <= value < 0x800000000000 and value % 8 == 0

        unit = memory.read_u64(owner + object_layout["owner_data"])
        handle, resolved_owner = registry.resolve_unit(memory, unit)
        if resolved_owner != owner:
            raise RuntimeError("Component owner mismatches unit registry")

        def traverse():
            head = memory.read_u64(owner + layout["head"])
            previous, node = owner + layout["sentinel"], head
            visited, identities, result = set(), [], []
            while node:
                if not pointer(node) or node in visited or len(visited) >= 4096:
                    raise RuntimeError("Invalid or cyclic unit component list")
                visited.add(node)
                wrapper = node - layout["node"]
                raw = memory.read(wrapper + layout["snapshot_start"], layout["snapshot_size"])
                values = decoder.unpack_from(raw)
                tag, full, prior, following, backlink, data = reorder(values) if reorder else values
                if prior != previous or backlink != owner:
                    raise RuntimeError("Unit component link changed or has wrong owner")
                if registry.resolve_handle(memory, full) != wrapper:
                    raise RuntimeError("Component handle mismatches registry")
                identities.append((wrapper, tag, full, prior, following, data))
                result.append((tag, wrapper, full, data))
                previous, node = node, following
            if memory.read_u64(owner + layout["head"]) != head:
                raise RuntimeError("Unit component head changed while reading")
            return head, identities, result

        last_error, first_head = None, None
        for _attempt in range(4):
            try:
                current_head, identities, result = traverse()
                if first_head is None:
                    first_head = current_head
                elif current_head != first_head:
                    raise RuntimeError("Unit component head changed while retrying")
                second_head, second_ids, second_result = traverse()
                if (identities != second_ids or result != second_result
                        or current_head != second_head
                        or registry.resolve_unit(memory, unit) != (handle, owner)):
                    raise RuntimeError("Unit component identity changed while reading")
                return result
            except RuntimeError as exc:
                last_error = exc
                if "changed" not in str(exc):
                    raise
        raise RuntimeError("Unit component list remained unstable after retries") from last_error

    def components(self, memory, registry, owner, names):
        result = {}
        owner_data = self.profile.section("registry")["owner_data"]
        unit_offset = self.profile.section("layouts")["ability"]["unit_owner"]
        for tag, wrapper, handle, data in self.nodes(memory, registry, owner):
            name = names.get(tag)
            if name is not None:
                if not data or memory.read_u64(data + unit_offset) != memory.read_u64(owner + owner_data):
                    raise RuntimeError("Invalid component unit link")
                if name in result:
                    raise RuntimeError("Duplicate built-in unit component")
                result[name] = (wrapper, data)
        return result


class AttackAdapter(LayoutProvider):
    @cached_property
    def layout(self):
        return self.profile.section("layouts")["attack"]

    def timing(self, memory, data):
        layout = self.layout
        kind = memory.read_i32(data + layout["kind"])
        cooldown = memory.read_f32(data + layout["cooldown"])
        if kind in {1, 64, 128, 256}:
            factor = 1.0
        else:
            factor = memory.read_f32(data + layout["speed_factor"])
            negative = memory.read_f32(data + layout["negative_modifier"])
            if negative < 0.0 and abs(negative) >= 0.001:
                factor += negative
            factor = min(5.0, max(0.2, factor))
        if (not math.isfinite(cooldown) or not 0.001 <= cooldown <= 1000.0
                or not math.isfinite(factor) or not 0.2 <= factor <= 5.0):
            raise RuntimeError("3.0 攻速运行时字段超出有效范围")
        interval = cooldown / factor
        return {"base_cooldown": cooldown, "speed_factor": factor,
                "after_effective_interval": interval, "after_true_aps": 1.0 / interval}


    def append_fields(self, host, pm, fields, key_prefix, label_prefix, data,
                      current_24268=False, timing_24268=None, field_type=None):
        layout = self.layout
        damage_note = "运行时攻击组件字段；用于实际选中单位，面板黄字可能有缓存"
        timing_note = "运行时攻击组件字段；已按当前选中单位链读写验证"
        candidate_note = "经典版字段候选；当前样本稳定，但语义仍以游戏内效果为准"
        readonly_candidate_note = "经典版字段候选；只读展示，未开放写入"
        host._append_unit_field(pm, fields, f"{key_prefix}_multiplier", f"{label_prefix}倍率/骰面", "i32", data + layout["multiplier"], "攻击", note=damage_note)
        host._append_unit_field(pm, fields, f"{key_prefix}_multiplier_cache", f"{label_prefix}倍率缓存", "i32", data + layout["multiplier_cache"], "攻击", note=damage_note)
        host._append_unit_field(pm, fields, f"{key_prefix}_dice", f"{label_prefix}骰子", "i32", data + layout["dice"], "攻击", note=damage_note)
        host._append_unit_field(pm, fields, f"{key_prefix}_base1", f"{label_prefix}基础1(当前)", "i32", data + layout["base1"], "攻击", note=damage_note)
        host._append_unit_field(pm, fields, f"{key_prefix}_base2", f"{label_prefix}基础2(当前)", "i32", data + layout["base2"], "攻击", note=damage_note)
        host._append_unit_field(pm, fields, f"{key_prefix}_dice_cache", f"{label_prefix}骰子缓存", "i32", data + layout["dice_cache"], "攻击", note=damage_note)
        host._append_unit_field(pm, fields, f"{key_prefix}_internal_bonus1", f"{label_prefix}内部加成槽1", "i32", data + layout["internal_bonus1"], "攻击", note=damage_note)
        host._append_unit_field(pm, fields, f"{key_prefix}_internal_bonus2", f"{label_prefix}内部加成槽2", "i32", data + layout["internal_bonus2"], "攻击", note=damage_note)
        host._append_unit_field(pm, fields, f"{key_prefix}_sound", f"{label_prefix}攻击音效码", "i32", data + layout["sound"], "攻击", note=damage_note)
        host._append_unit_field(pm, fields, f"{key_prefix}_damage_loss_factor", f"{label_prefix}丢失因子(候选只读)", "f32", data + layout["damage_loss_factor"], "攻击", writable=False, note=readonly_candidate_note)
        host._append_unit_field(pm, fields, f"{key_prefix}_type", f"{label_prefix}种类", "i32", data + layout["type"], "攻击")
        host._append_unit_field(pm, fields, f"{key_prefix}_max_targets", f"{label_prefix}最大目标数(候选)", "i32", data + layout["max_targets"], "攻击", note=candidate_note)
        if current_24268:
            host._append_unit_field(
                pm, fields, f"{key_prefix}_interval", f"{label_prefix}基础间隔/冷却",
                "f32", data + layout["cooldown"], "攻击",
                note="3.0 当前武器基础冷却；不是敏捷和攻速加成后的最终攻击间隔",
            )
            if timing_24268 is not None:
                speed_factor = float(timing_24268["speed_factor"])
                effective_interval = float(timing_24268["after_effective_interval"])
                true_aps = float(timing_24268["after_true_aps"])
                exact_note = "按 3.0 游戏内部最终攻击间隔函数的等价公式从当前运行时组件读取"
                fields.extend((
                    field_type(
                        key=f"{key_prefix}_speed_factor",
                        label=f"{label_prefix}当前攻速倍率",
                        value_type="f32", value=speed_factor,
                        address=data + layout["speed_factor"], category="攻击",
                        write_address=0, write_type="", note=exact_note,
                    ),
                    field_type(
                        key=f"{key_prefix}_effective_interval",
                        label=f"{label_prefix}当前引擎实际攻击间隔(秒)",
                        value_type="f32", value=effective_interval,
                        address=data + layout["cooldown"], category="攻击",
                        write_address=0, write_type="", note=exact_note,
                    ),
                    field_type(
                        key=f"{key_prefix}_true_speed",
                        label=f"{label_prefix}当前引擎实际攻速(次/秒)",
                        value_type="f32", value=true_aps,
                        address=data + layout["cooldown"], category="攻击",
                        write_address=0, write_type="", native_write=True,
                        note=(
                            exact_note + "；这是当前游戏实际使用的数值，可能已经受换图敏捷 bug 影响；"
                            "可写：输入目标每秒攻击次数，修改器会通过游戏接口"
                            "反算基础冷却并以最终攻击间隔读回确认"
                        ),
                    ),
                ))
        else:
            host._append_unit_field(pm, fields, f"{key_prefix}_interval", f"{label_prefix}间隔/冷却", "f32", data + layout["legacy_interval"], "攻击", note=timing_note)
            host._append_unit_field(pm, fields, f"{key_prefix}_first_delay", f"{label_prefix}首次延时", "f32", data + layout["cooldown"], "攻击", note=timing_note)
        host._append_unit_field(pm, fields, f"{key_prefix}_acquire_range", f"{label_prefix}主动攻击范围", "f32", data + layout["acquire_range"], "攻击", note=timing_note)
        host._append_unit_field(pm, fields, f"{key_prefix}_projectile_speed", f"{label_prefix}投射物速度", "f32", data + layout["projectile_speed"], "攻击", note=timing_note)
        host._append_unit_field(pm, fields, f"{key_prefix}_range", f"{label_prefix}范围", "f32", data + layout["range"], "攻击", note=timing_note)
        host._append_unit_field(pm, fields, f"{key_prefix}_range_buffer", f"{label_prefix}范围缓冲", "f32", data + layout["range_buffer"], "攻击", note=timing_note)



class AbilityAdapter(LayoutProvider):
    def instance(self, host, pm, candidate, wrapper, component_rawcodes, instance_type):
        component = self.profile.section("layouts")["component_list"]
        ability = self.profile.section("layouts")["ability"]
        try:
            vtable = pm.read_u64(wrapper)
            tag = pm.read_u64(wrapper + component["tag"])
            wrapper_owner = pm.read_u64(wrapper + component["owner"])
            data = pm.read_u64(wrapper + component["data"])
        except OSError:
            return None
        if wrapper_owner != candidate.owner_address:
            return None
        if not host._looks_like_vtable(vtable) or not host._sane_heap_ptr(data):
            return None
        class_rawcode = (tag >> 32) & 0xFFFFFFFF
        if class_rawcode in component_rawcodes:
            return None
        if not host._looks_like_rawcode(class_rawcode):
            return None
        try:
            data_vtable = pm.read_u64(data)
            unit = pm.read_u64(data + ability["unit_owner"])
            rawcode = pm.read_u32(data + ability["rawcode"])
            mirror_rawcode = pm.read_u32(data + ability["mirror_rawcode"])
            handle = pm.read_u64(wrapper + component["handle"])
            data_cache_pointer = pm.read_u64(data + ability["data_cache"])
        except OSError:
            return None
        if not host._looks_like_vtable(data_vtable):
            return None
        if unit != candidate.unit_address:
            return None
        if rawcode != mirror_rawcode or not host._looks_like_item_rawcode(rawcode):
            return None
        return instance_type(
            slot=0,
            wrapper_address=wrapper,
            data_address=data,
            wrapper_vtable=vtable,
            data_vtable=data_vtable,
            wrapper_tag_address=wrapper + component["tag"],
            wrapper_tag=tag,
            handle=handle,
            class_rawcode=class_rawcode,
            rawcode=rawcode,
            rawcode_address=data + ability["rawcode"],
            mirror_rawcode_address=data + ability["mirror_rawcode"],
            data_cache_address=data + ability["data_cache"],
            data_cache_pointer=data_cache_pointer if host._sane_heap_ptr(data_cache_pointer) else 0,
        )


class ItemAdapter(LayoutProvider):
    @cached_property
    def layout(self):
        return self.profile.section("layouts")["item"]

    @cached_property
    def inventory_layout(self):
        return self.profile.section("layouts")["inventory"]

    @cached_property
    def component_layout(self):
        return self.profile.section("layouts")["component_list"]

    def inventory_record(self, memory, candidate, data, rawcode, indexed=False):
        if not data or not candidate.unit_address:
            return 0
        layout = self.inventory_layout
        if indexed:
            if memory.read_u64(data + layout["owner"]) != candidate.unit_address:
                raise RuntimeError("Inventory component changed unit")
            capacity = memory.read_u64(data + layout["capacity"])
            count = memory.read_u64(data + layout["count"])
            if capacity != layout["slot_count"] or count != layout["slot_count"]:
                raise RuntimeError("Inventory slot layout differs from verified six-slot record")
            return data
        for offset in range(0, layout["scan_limit"], layout["scan_stride"]):
            record = data + offset
            try:
                if (memory.read_u64(record + layout["owner"]) == candidate.unit_address
                        and memory.read_u32(record + layout["rawcode"]) == rawcode):
                    return record
            except OSError:
                continue
        return 0

    def valid_item(self, memory, item, handle, sane_ptr, rawcode_check, vtable_check,
                   require_heap=True):
        layout = self.layout
        return bool(
            (not require_heap or sane_ptr(item))
            and vtable_check(memory.read_u64(item))
            and memory.read_u64(item + layout["full_handle"]) == handle
            and rawcode_check(memory.read_u32(item + layout["rawcode"]))
            and memory.read_u32(item + layout["rawcode"]) == memory.read_u32(item + layout["rawcode_mirror"])
        )

    def item_data_near_owner(self, memory, owner, handle, sane_ptr, rawcode_check, vtable_check):
        layout, component = self.layout, self.component_layout
        if not handle or handle == 0xFFFFFFFFFFFFFFFF:
            return 0
        if owner:
            for offset in range(-layout["owner_scan_radius"], layout["owner_scan_radius"], layout["owner_scan_stride"]):
                wrapper = owner + offset
                try:
                    if memory.read_u64(wrapper + component["tag"]) != layout["owner_tag"]:
                        continue
                    if memory.read_u64(wrapper + component["handle"]) != handle:
                        continue
                    item = memory.read_u64(wrapper + component["data"])
                    if self.valid_item(memory, item, handle, sane_ptr, rawcode_check, vtable_check):
                        return item
                except OSError:
                    continue
        # Compatibility callers retain their original bounded private-memory fallback.
        # Managed native selection never enters this scan path.
        for address in memory.scan_bytes_private(struct.pack("<Q", handle), max_region_size=1024 * 1024):
            item = address - layout["full_handle"]
            try:
                if self.valid_item(memory, item, handle, sane_ptr, rawcode_check, vtable_check, False):
                    return item
            except OSError:
                continue
        return 0

    def fields(self, memory, item, rawcode_check):
        values = {}
        for name, offset, reader, predicate in (
            ("rawcode", self.layout["rawcode"], memory.read_u32, None),
            ("mirror_rawcode", self.layout["rawcode_mirror"], memory.read_u32, rawcode_check),
            ("ability_rawcode", self.layout["ability_rawcode"], memory.read_u32, rawcode_check),
            ("charges", self.layout["charges"], memory.read_i32, lambda n: 0 <= n <= 999),
        ):
            address = item + offset
            try:
                value = reader(address)
                if predicate is not None and not predicate(value):
                    value = address = 0
            except OSError:
                value = address = 0
            values[name], values[name + "_address"] = value, address
        return values


class UnitAdapter(LayoutProvider):
    @cached_property
    def layout(self):
        return self.profile.section("layouts")["unit"]

    @cached_property
    def hero_layout(self):
        return self.profile.section("layouts")["hero"]

    def populate_field_snapshot(self, target, candidate, values):
        layout = self.profile.section("layouts")
        if (len(values) != 293 or values[:3] != (
                candidate.unit_address, candidate.handle, candidate.owner_address)
                or values[3] & ~15 or values[14] not in (0, 1)):
            raise RuntimeError("DLL 单位字段快照长度或身份异常")
        target.components: dict[str, tuple[int, int]] = {}
        target.component_identities: dict[str, tuple[int, int]] = {
            "unit": (candidate.unit_address, candidate.handle)}
        target.inventory_items: list[InventoryItem] = []
        target.attack2 = bool(values[14])
        target._blocks: dict[int, bytes] = {}

        def block(address: int, start: int, end: int) -> None:
            target._blocks[address] = struct.pack(f"<{end-start}Q", *values[start:end])

        block(candidate.unit_address + layout["unit"]["armor"], 4, 6)
        for index, name in enumerate(("inventory", "hero", "move", "attack")):
            data, wrapper = values[6 + index*2:8 + index*2]
            present = bool(values[3] & (1 << index))
            if (present and (not data or not wrapper)) or (not present and (data or wrapper)):
                raise RuntimeError("DLL 单位组件身份不完整")
            if present:
                target.components[name] = (wrapper, data)
        if "hero" in target.components:
            block(target.components["hero"][1] + layout["hero"]["xp"], 15, 51)
        if "attack" in target.components:
            data = target.components["attack"][1]
            block(data, 51, 172)
            if target.attack2:
                block(data + layout["attack"]["second_component"], 172, 293)
        elif target.attack2:
            raise RuntimeError("DLL 第二攻击快照缺少所属组件")



class SelectionAdapter(LayoutProvider):
    @cached_property
    def layout(self):
        return self.profile.section("layouts")["selection"]

    @cached_property
    def property_layout(self):
        return self.profile.section("layouts")["property"]


class EffectAdapter(LayoutProvider):
    @cached_property
    def callback_layout(self):
        return self.profile.section("layouts")["effect"]

    def vtable_for(self, effect_kind):
        return self.callback_layout[
            {1: "target_vtable", 2: "immediate_vtable", 3: "point_vtable",
             4: "noarg_vtable", 5: "buff_vtable"}[int(effect_kind)]
        ]


class TalentAdapter(LayoutProvider):
    @cached_property
    def layout(self):
        return self.profile.section("layouts")["talent"]

    def selection_order(self, tier, choice_index):
        return self.layout["order_base"] + tier * self.layout["choices_per_tier"] + choice_index

    def records(self, memory, candidate, instances, tiers, registry=None):
        ability = self.profile.section("layouts")["ability"]
        instances = [instance for instance in instances
                     if not memory.read_u32(instance.data_address + ability["flags"]) & ability["retired_mask"]]
        if len(instances) != 1:
            return None
        address = instances[0].data_address + self.layout["snapshot_start"]
        block = memory.read(address, self.layout["snapshot_size"])
        if memory.read(address, self.layout["snapshot_size"]) != block:
            raise RuntimeError("天赋选择记录在读取期间发生变化")
        remaining = struct.unpack_from("<I", block, self.layout["point_counter"] - self.layout["snapshot_start"])[0]
        if not 0 <= remaining <= len(tiers) * 3:
            return None
        records = tuple((struct.unpack_from("<Q", block, index * self.layout["record_stride"])[0],
                         struct.unpack_from("<I", block, index * self.layout["record_stride"] + self.layout["record_flags"])[0])
                        for index in range(len(tiers)))
        component = self.profile.section("layouts")["component_list"]
        from war3_object_registry import ObjectRegistry24268
        choices = []
        for index, (full, _flags) in enumerate(records):
            choice = ""
            if full != 0xFFFFFFFFFFFFFFFF:
                registry = registry or ObjectRegistry24268.attach(memory)
                wrapper = registry.resolve_handle(memory, full)
                data = memory.read_u64(wrapper + component["data"])
                if memory.read_u64(data + ability["unit_owner"]) != candidate.unit_address:
                    raise RuntimeError("天赋选择记录属于其他单位")
                choice = memory.read_u32(data + ability["rawcode"]).to_bytes(4, "big").decode("ascii")
                if choice not in tiers[index]:
                    raise RuntimeError("天赋选择记录与当前层不匹配")
            choices.append(choice)
        return int(remaining), records, choices


class StatAdapter(LayoutProvider):
    @cached_property
    def runtime_layout(self):
        return self.profile.section("stat_runtime")

    @cached_property
    def ability_layout(self):
        return self.profile.section("layouts")["ability"]

    def instance_is_effective(self, memory, data):
        return memory.read_u32(data + self.ability_layout["flags"]) & self.ability_layout["excluded_flags"] == 0


class IconAdapter(LayoutProvider):
    @cached_property
    def addresses(self):
        return self.profile.section("module_addresses")

    def site(self, module_base):
        return module_base + self.addresses["talent_icon_site"]

    def resolver(self, module_base):
        return module_base + self.addresses["talent_icon_resolver"]


PROVIDERS = {"legacy_layout": ComponentAdapter, "equipment": EquipmentAdapter,
             "talents": TalentAdapter, "stat_details": StatAdapter,
             "direct_effect": EffectAdapter, "talent_icons": IconAdapter}

# Each compiled implementation is a real factory entry. A semantic change can
# replace one entry (and its subproviders) without changing feature workflows.
IMPLEMENTATION_PROVIDERS = {
    name + suffix: factory
    for suffix in ("_24268_v1", "_24323_v1")
    for name, factory in PROVIDERS.items()
}

def _component_24332(profile):
    from war3_adapter_24332 import ComponentAdapter24332
    return ComponentAdapter24332(profile)

IMPLEMENTATION_PROVIDERS["legacy_layout_24332_v1"] = _component_24332
