"""abilities compatibility API; host primitives are explicitly bound once at composition."""
from __future__ import annotations
from contextlib import contextmanager

class AbilitiesFacade:
    def _run_direct_selected_ability_locked(
        self,
        rawcode: int | str,
        op_kind: int,
        vtable_offset: int,
        arg1: int,
    ) -> int:
        ability_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        if not ability_rawcode:
            raise ValueError("技能 ID 无效")
        effect_kind = {
            self.NATIVE_HELPER_OP_DIRECT_ABILITY_TARGET: 1,
            self.NATIVE_HELPER_OP_DIRECT_ABILITY_IMMEDIATE: 2,
            self.NATIVE_HELPER_OP_DIRECT_ABILITY_POINT: 3,
            self.NATIVE_HELPER_OP_DIRECT_ABILITY_NOARG_DERIVED: 4,
            self.NATIVE_HELPER_OP_DIRECT_ABILITY_BUFF: 5,
        }.get(op_kind)
        if effect_kind is None or int(vtable_offset) != {1: 0xA70, 2: 0x998, 3: 0xA58, 4: 0xA78, 5: 0xA00}[effect_kind]:
            raise ValueError("Unsupported direct ability effect type")
        if getattr(self, "_native_selection_unavailable", False):
            if effect_kind == 5:
                raise RuntimeError("当前引擎批处理暂未开放需要 buff 构造器的直接效果")
            point_x = int(arg1) & 0xFFFFFFFF if effect_kind == 3 else 0
            point_y = (int(arg1) >> 32) & 0xFFFFFFFF if effect_kind == 3 else 0
            result = self.effect_batch_24268(
                ability_rawcode, effect_kind, point_x, point_y,
            )
            return int(result["changed"])
        candidate, unit_handle = self._direct_selected_context()
        native = self._native_snapshot_for_candidate(candidate)
        if native is None or native.handle != unit_handle:
            raise RuntimeError("Direct ability effect requires a bound native unit identity")
        point_x = int(arg1) & 0xFFFFFFFF if effect_kind == 3 else 0
        point_y = (int(arg1) >> 32) & 0xFFFFFFFF if effect_kind == 3 else 0
        response = self._run_native_helper_ops(unit_handle, (
            (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0,
             candidate.unit_address, candidate.handle, candidate.owner_address),
            (self.NATIVE_HELPER_OP_BOUND_DIRECT_ABILITY, ability_rawcode,
             effect_kind, point_x, point_y),
        ))
        if (len(response) != 2 or any(item.last_error for item in response)
                or response[0].kind != self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY
                or response[0].result != 1
                or response[1].kind != self.NATIVE_HELPER_OP_BOUND_DIRECT_ABILITY
                or response[1].result != 1):
            raise RuntimeError("Incomplete direct ability effect result")
        return int(response[1].result)


    def apply_direct_ability_to_selected_unit(self, rawcode: int | str) -> int:
        return self._run_direct_selected_ability(
            rawcode,
            self.NATIVE_HELPER_OP_DIRECT_ABILITY_TARGET,
            0xA70,
            0,
        )


    def apply_direct_immediate_ability(self, rawcode: int | str) -> int:
        return self._run_direct_selected_ability(
            rawcode,
            self.NATIVE_HELPER_OP_DIRECT_ABILITY_IMMEDIATE,
            0x998,
            0,
        )


    def apply_direct_noarg_derived_ability(self, rawcode: int | str) -> int:
        return self._run_direct_selected_ability(
            rawcode,
            self.NATIVE_HELPER_OP_DIRECT_ABILITY_NOARG_DERIVED,
            0xA78,
            0,
        )


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


    def apply_direct_roar_buff_to_selected_unit(self, rawcode: int | str) -> int:
        with self._native_helper_transaction():
            return self._apply_direct_roar_buff_to_selected_unit_locked(rawcode)


    def _apply_direct_roar_buff_to_selected_unit_locked(self, rawcode: int | str) -> int:
        return self._run_direct_selected_ability_locked(
            rawcode, self.NATIVE_HELPER_OP_DIRECT_ABILITY_BUFF, 0xA00, 0,
        )


    def _run_direct_ability_over_enemy_units(
        self,
        rawcode: int | str,
        mode: str,
        *,
        success_limit: int = 0,
    ) -> tuple[int, int]:
        with self._native_helper_transaction():
            return self._run_direct_ability_over_enemy_units_locked(
                rawcode,
                mode,
                success_limit=success_limit,
            )


    def _run_direct_ability_over_enemy_units_locked(
        self, rawcode: int | str, mode: str, *, success_limit: int = 0,
    ) -> tuple[int, int]:
        ability_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        effect_mode = {"target": 1, "immediate": 2, "point": 3}.get(mode)
        limit = int(success_limit)
        if not ability_rawcode or effect_mode is None or not 0 <= limit <= 65535:
            raise ValueError("Invalid world ability effect parameters")
        if getattr(self, "_native_selection_unavailable", False):
            result = self.world_effect_batch_24268(ability_rawcode, effect_mode, limit)
            return int(result["attempts"]), int(result["successes"])
        candidate, handle = self._direct_selected_context()
        native = self._native_snapshot_for_candidate(candidate)
        if native is None or native.handle != handle:
            raise RuntimeError("World effect requires a bound native unit identity")
        response = self._run_native_helper_ops(handle, (
            (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0,
             candidate.unit_address, candidate.handle, candidate.owner_address),
            (self.NATIVE_HELPER_OP_BOUND_WORLD_EFFECT, ability_rawcode, effect_mode, limit, 0),
        ), timeout_ms=120000)
        if (len(response) != 2 or any(item.last_error for item in response)
                or response[0].kind != self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY or response[0].result != 1
                or response[1].kind != self.NATIVE_HELPER_OP_BOUND_WORLD_EFFECT):
            raise RuntimeError("Incomplete native world effect result")
        packed = int(response[1].result)
        attempts, successes = packed >> 32, packed & 0xFFFFFFFF
        if not 0 <= successes <= attempts <= 100000 or (limit and successes > limit):
            raise RuntimeError("Invalid native world effect counts")
        return attempts, successes


    def get_selected_unit_position(self) -> tuple[float, float]:
        x, y = self._query_bound_unit_values(("GetUnitX", "GetUnitY"))
        return self._float_from_bits(x), self._float_from_bits(y)


    def apply_direct_point_ability(
        self,
        rawcode: int | str,
        x: float | None = None,
        y: float | None = None,
    ) -> int:
        if x is None or y is None:
            x, y = self.get_selected_unit_position()
        target_x = float(x)
        target_y = float(y)
        if not math.isfinite(target_x) or not math.isfinite(target_y):
            raise ValueError("技能目标坐标必须是有限数值")
        packed = self._float_bits(target_x) | (self._float_bits(target_y) << 32)
        return self._run_direct_selected_ability(
            rawcode,
            self.NATIVE_HELPER_OP_DIRECT_ABILITY_POINT,
            0xA58,
            packed,
        )


    def enable_selected_toggle_ability(
        self,
        rawcode: int | str,
        order_id: int,
    ) -> int:
        with self._native_helper_transaction():
            return self._enable_selected_toggle_ability_locked(rawcode, order_id)


    def _enable_selected_toggle_ability_locked(
        self, rawcode: int | str, order_id: int,
    ) -> int:
        ability_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        order = int(order_id)
        if not ability_rawcode or not 0 < order <= 0x7FFFFFFF:
            raise ValueError("Invalid ability or toggle order")
        if getattr(self, "_native_selection_unavailable", False):
            # The current build has the ability lifecycle callbacks but the
            # legacy order helper is unavailable. Keep the toggle ability on
            # the unit and invoke its immediate effect in the same bridge
            # path; the order is retained for diagnostics and old builds.
            added = self.ability_batch_24268(ability_rawcode, 1, 1)
            effect = self.effect_batch_24268(ability_rawcode, 2)
            changed = int(added.get("changed", 0)) + int(effect.get("changed", 0))
            if not changed:
                raise RuntimeError("当前引擎未接受切换技能")
            return changed
        candidate, handle = self._direct_selected_context()
        native = self._native_snapshot_for_candidate(candidate)
        if native is None or native.handle != handle:
            raise RuntimeError("Toggle requires a bound native unit identity")
        response = self._run_native_helper_ops(handle, (
            (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0,
             candidate.unit_address, candidate.handle, candidate.owner_address),
            (self.NATIVE_HELPER_OP_ENABLE_BOUND_TOGGLE, ability_rawcode, order, 0, 0),
        ))
        if (len(response) != 2 or any(item.last_error for item in response)
                or response[0].kind != self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY or response[0].result != 1
                or response[1].kind != self.NATIVE_HELPER_OP_ENABLE_BOUND_TOGGLE or not response[1].result):
            raise RuntimeError("Incomplete native toggle result")
        return int(response[1].result)


    def _run_selected_ability_effect(
        self,
        rawcode: int | str,
        effect_kind: str,
        *,
        passes: int = 1,
        area: float | None = None,
        hold_seconds: float = 0.0,
        point: tuple[float, float] | None = None,
    ) -> tuple[int, int]:
        with self._native_helper_transaction():
            return self._run_selected_ability_effect_locked(
                rawcode,
                effect_kind,
                passes=passes,
                area=area,
                hold_seconds=hold_seconds,
                point=point,
            )


    def _run_selected_ability_effect_locked(
        self,
        rawcode: int | str,
        effect_kind: str,
        *,
        passes: int = 1,
        area: float | None = None,
        hold_seconds: float = 0.0,
        point: tuple[float, float] | None = None,
    ) -> tuple[int, int]:
        ability_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        mode = {"immediate": 2, "point": 3, "noarg": 4}.get(effect_kind)
        count = int(passes)
        duration = float(hold_seconds)
        if not ability_rawcode or mode is None or not 1 <= count <= 255:
            raise ValueError("Invalid ability effect or pass count")
        if not math.isfinite(duration) or not 0 <= duration <= 120:
            raise ValueError("Invalid ability effect hold duration")
        flags = 2 if duration else 0
        area_bits = 0
        if area is not None:
            area = float(area)
            if not math.isfinite(area) or not 1 <= area <= 1000000:
                raise ValueError("Invalid ability effect area")
            flags |= 1
            area_bits = self._float_bits(area)
        packed_point = 0
        if mode == 3:
            if point is None:
                flags |= 4
            else:
                x, y = map(float, point)
                if not all(math.isfinite(v) and abs(v) <= 1000000 for v in (x, y)):
                    raise ValueError("Invalid ability effect point")
                packed_point = self._float_bits(x) | (self._float_bits(y) << 32)
        elif point is not None:
            raise ValueError("Only point effects accept coordinates")
        if getattr(self, "_native_selection_unavailable", False):
            # The current bridge owns temporary ability creation, area
            # restoration, and all passes inside one game-thread callback.
            # Point callbacks keep their coordinate payload, while other
            # callbacks use the bridge's bounded area/pass option payload.
            if mode == 3:
                if point is None:
                    point_x, point_y = self.query_mouse_world_position()
                    packed_point = self._float_bits(point_x) | (self._float_bits(point_y) << 32)
                result = self.effect_batch_24268(
                    ability_rawcode,
                    mode,
                    packed_point & 0xFFFFFFFF,
                    (packed_point >> 32) & 0xFFFFFFFF,
                    area=area,
                )
            else:
                result = self.effect_batch_24268(
                    ability_rawcode,
                    mode,
                    area=area,
                    passes=count,
                )
            return count, int(result["changed"])
        candidate, handle = self._direct_selected_context()
        native = self._native_snapshot_for_candidate(candidate)
        if native is None or native.handle != handle:
            raise RuntimeError("Ability effect requires a bound native unit identity")
        guard = (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0,
                 candidate.unit_address, candidate.handle, candidate.owner_address)
        response = self._run_native_helper_ops(handle, (
            guard,
            (self.NATIVE_HELPER_OP_START_ABILITY_EFFECT, ability_rawcode, mode, count, packed_point),
            (self.NATIVE_HELPER_OP_ABILITY_EFFECT_OPTIONS, flags, 0, area_bits, math.ceil(duration * 1000)),
        ))
        token = response[1].result if len(response) >= 2 and response[1].kind == self.NATIVE_HELPER_OP_START_ABILITY_EFFECT else 0
        try:
            if (len(response) != 3 or any(item.last_error for item in response)
                    or response[0].kind != self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY or response[0].result != 1
                    or response[1].kind != self.NATIVE_HELPER_OP_START_ABILITY_EFFECT
                    or response[2].kind != self.NATIVE_HELPER_OP_ABILITY_EFFECT_OPTIONS
                    or response[1].arg0 != count or bool(token) != bool(duration)):
                raise RuntimeError("Incomplete native ability effect result")
            if duration:
                time.sleep(duration)
            return count, int(response[1].arg0)
        finally:
            if token:
                active_error = sys.exc_info()[1]
                try:
                    finished = self._run_native_helper_ops(handle, (
                        guard, (self.NATIVE_HELPER_OP_FINISH_ABILITY_EFFECT, 0, token, 0, 0),
                    ))
                    if (len(finished) != 2 or any(item.last_error for item in finished)
                            or finished[1].kind != self.NATIVE_HELPER_OP_FINISH_ABILITY_EFFECT or finished[1].result != 1):
                        raise RuntimeError("Incomplete native ability effect cleanup")
                except Exception as cleanup_error:
                    raise RuntimeError(f"Ability effect cleanup failed; token={token}; original={active_error}; cleanup={cleanup_error}") from cleanup_error


    def cast_ability_with_runtime_dummy(
        self,
        rawcode: int | str,
        order_id: int,
        cast_type: str,
        *,
        global_scope: bool = False,
        enemy_owner: bool = False,
        self_cast: bool = False,
        remove_self_ability: bool = False,
        point_geometry: str = "target",
        level: int = 1,
        passes: int = 1,
        success_limit: int = 0,
        mana: float = 100000.0,
        cleanup_duration: float = 1.5,
    ) -> tuple[int, int]:
        raise OSError(ERROR_NOT_SUPPORTED, "运行时假单位施法路径已禁用")


    def apply_standard_debuffs_to_selected_unit(self) -> tuple[int, int]:
        target_abilities = ("Acrs", "Aply", "Aslo", "Acri", "Afae", "ANso", "AEer", "ANdo")
        attempted = len(target_abilities) + 1
        succeeded = sum(
            1 if self.apply_direct_ability_to_selected_unit(ability) else 0
            for ability in target_abilities
        )
        succeeded += 1 if self.apply_direct_roar_buff_to_selected_unit("ANht") else 0
        return attempted, succeeded


    def apply_standard_buffs_to_selected_unit(self) -> tuple[int, int]:
        target_abilities = ("Aams", "Ainf", "Ablo", "Auhf", "Afzy", "Alsh", "Arej", "Aivs", "ACfa")
        attempted = len(target_abilities)
        succeeded = sum(
            1 if self.apply_direct_ability_to_selected_unit(ability) else 0
            for ability in target_abilities
        )
        for ability in ("Aroa", "Absk"):
            attempted += 1
            succeeded += 1 if self.apply_direct_immediate_ability(ability) else 0
        attempted += 1
        succeeded += 1 if self.apply_direct_point_ability("Ahwd") else 0
        channel_attempted, channel_succeeded = self._run_selected_ability_effect(
            "AEtq",
            "immediate",
            hold_seconds=12.0,
        )
        attempted += channel_attempted
        succeeded += channel_succeeded
        attempted += 1
        succeeded += 1 if self.enable_selected_toggle_ability("ANms", 852589) else 0
        attempted += 1
        succeeded += 1 if self.apply_direct_noarg_derived_ability("AIsa") else 0
        return attempted, succeeded


    def cast_fullscreen_swarm(self, *, success_limit: int = 0) -> tuple[int, int]:
        entries = (("ACca", 852218), ("ACcv", 852218), ("AOsh", 852125))
        attempted = succeeded = 0
        for ability, order_id in entries:
            attempted += 1
            self.cast_native_area_24268(ability, order_id, cast_kind=2)
            succeeded += 1
        return attempted, succeeded


    def cast_fullscreen_clap(self, *, success_limit: int = 0) -> tuple[int, int]:
        entries = (("AHtc", 852096), ("AOws", 852127))
        attempted = succeeded = 0
        for ability, order_id in entries:
            attempted += 1
            self.cast_native_area_24268(ability, order_id, cast_kind=1)
            succeeded += 1
        return attempted, succeeded


    def cast_fullscreen_monsoon(self, *, success_limit: int = 0) -> tuple[int, int]:
        self.cast_native_area_24268("ANmo", 852591, cast_kind=2, hold_seconds=12.0)
        return 1, 1


    def cast_fullscreen_starfall(self, *, success_limit: int = 0) -> tuple[int, int]:
        self.cast_native_area_24268("AEsb", 852183, cast_kind=1, hold_seconds=12.0)
        return 1, 1


    def cast_fullscreen_forked_lightning(self, *, success_limit: int = 0) -> tuple[int, int]:
        self.cast_native_area_24268("ACfl", 852587, cast_kind=3)
        return 1, 1


    def cast_fullscreen_auto_effect(self, *, success_limit: int = 0) -> tuple[int, int]:
        self.cast_native_area_24268("AEfk", 852526, cast_kind=1)
        return 1, 1


    def take_selected_unit_control(self) -> int:
        if getattr(self, "_native_selection_unavailable", False):
            from war3_unit_action_protocol import ACTION_TAKE_CONTROL
            result = self._unit_action_result_24268(ACTION_TAKE_CONTROL)
            return int(result["count"])
        candidate, unit_handle = self._direct_selected_context()
        handlers = self._query_native_table_handlers(("GetLocalPlayer", "SetUnitOwner", "GetOwningPlayer"))
        result = self._run_bound_unit_action_result(candidate, unit_handle, (
            self.NATIVE_HELPER_OP_JASS_TAKE_OWNERSHIP, 0, handlers["GetLocalPlayer"].handler_address,
            handlers["SetUnitOwner"].handler_address, handlers["GetOwningPlayer"].handler_address))
        if not result:
            raise RuntimeError("Native ownership acknowledgment is empty")
        return result


    def create_local_unit(
        self,
        rawcode: int | str | None = None,
        position: tuple[float, float] | None = None,
        *,
        use_selected_lookup: bool = True,
        preserve_owner: bool = False,
    ) -> tuple[int, int]:
        x, y = self.query_mouse_world_position() if position is None else position
        if rawcode is None and getattr(self, "_native_selection_unavailable", False):
            result = self.clone_batch_24268(
                keep=True,
                preserve_owner=preserve_owner,
                copy_abilities=True,
                copy_items=True,
                spawn=True,
                spawn_x_bits=self._float_bits(float(x)),
                spawn_y_bits=self._float_bits(float(y)),
            )
            if not result["rows"]:
                raise RuntimeError("当前选择没有可复制单位")
            row = result["rows"][0]
            return int(row["rawcode"]), int(row["clone"])
        unit_handle = 0
        if rawcode is None:
            if not use_selected_lookup:
                raise ValueError("复制单位缺少已读取的单位 ID")
            candidate, unit_handle = self._direct_selected_context()
            unit_rawcode = candidate.unit_type_id
        else:
            unit_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        if not unit_rawcode:
            raise ValueError("没有可用于创建单位的有效 ID")
        if getattr(self, "_native_selection_unavailable", False) and rawcode is not None:
            result = self.spawn_unit_24268(unit_rawcode, x, y)
            return unit_rawcode, int(result["created"])
        handler_names = ["GetLocalPlayer", "CreateUnit"]
        source_is_hero = False
        source_has_inventory = False
        if rawcode is None:
            native = self._native_snapshot_for_candidate(candidate)
            if native is None or native.handle != unit_handle:
                raise RuntimeError("Cloning requires the original native unit snapshot")
            source_is_hero = bool(native.component_mask & 2)
            source_has_inventory = bool(native.component_mask & 1)
            if preserve_owner:
                handler_names[0] = "GetOwningPlayer"
            handler_names.extend((
                "GetUnitTypeId",
                "RemoveUnit",
                "GetUnitFacing",
                "GetHeroLevel",
                "SetHeroLevel",
                "GetHeroXP",
                "SetHeroXP",
                "GetHeroStr",
                "SetHeroStr",
                "GetHeroAgi",
                "SetHeroAgi",
                "GetHeroInt",
                "SetHeroInt",
                "GetHeroSkillPoints",
                "UnitModifySkillPoints",
                "BlzGetUnitMaxHP",
                "BlzSetUnitMaxHP",
                "GetWidgetLife",
                "SetWidgetLife",
                "BlzGetUnitMaxMana",
                "BlzSetUnitMaxMana",
                "GetUnitState",
                "SetUnitState",
                "BlzGetUnitAbilityByIndex",
                "BlzGetAbilityId",
                "GetUnitAbilityLevel",
                "UnitAddAbility",
                "SetUnitAbilityLevel",
            ))
            if source_has_inventory:
                handler_names.extend((
                    "UnitItemInSlot",
                    "GetItemTypeId",
                    "UnitAddItemById",
                    "GetItemCharges",
                    "SetItemCharges",
                    "BlzGetItemIntegerField",
                    "BlzSetItemIntegerField",
                    "BlzGetItemRealField",
                    "BlzSetItemRealField",
                    "BlzGetItemBooleanField",
                    "BlzSetItemBooleanField",
                ))
        handlers = self._query_native_table_handlers(tuple(handler_names))
        coordinates = struct.unpack("<Q", struct.pack("<ff", float(x), float(y)))[0]
        if rawcode is None:
            clone_flags = (
                (self.NATIVE_HELPER_CLONE_FLAG_HERO if source_is_hero else 0)
                | (
                    self.NATIVE_HELPER_CLONE_FLAG_INVENTORY
                    if source_has_inventory
                    else 0
                )
                | (
                    self.NATIVE_HELPER_CLONE_FLAG_PRESERVE_OWNER
                    if preserve_owner
                    else 0
                )
            )

            def handler_address(name: str) -> int:
                handler = handlers.get(name)
                return handler.handler_address if handler is not None else 0

            owner_handler_name = (
                "GetOwningPlayer" if preserve_owner else "GetLocalPlayer"
            )
            clone_ops = (
                (
                    self.NATIVE_HELPER_OP_JASS_CLONE_SELECTED_UNIT,
                    unit_rawcode,
                    handlers[owner_handler_name].handler_address,
                    handlers["CreateUnit"].handler_address,
                    coordinates,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_MULTI_ARG,
                    clone_flags,
                    handlers["GetUnitFacing"].handler_address,
                    handlers["GetHeroLevel"].handler_address,
                    handlers["SetHeroLevel"].handler_address,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_MULTI_ARG,
                    0,
                    handlers["GetHeroXP"].handler_address,
                    handlers["SetHeroXP"].handler_address,
                    handlers["GetHeroStr"].handler_address,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_MULTI_ARG,
                    0,
                    handlers["SetHeroStr"].handler_address,
                    handlers["GetHeroAgi"].handler_address,
                    handlers["SetHeroAgi"].handler_address,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_MULTI_ARG,
                    0,
                    handlers["GetHeroInt"].handler_address,
                    handlers["SetHeroInt"].handler_address,
                    handlers["GetHeroSkillPoints"].handler_address,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_MULTI_ARG,
                    0,
                    handlers["UnitModifySkillPoints"].handler_address,
                    handlers["BlzGetUnitMaxHP"].handler_address,
                    handlers["BlzSetUnitMaxHP"].handler_address,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_MULTI_ARG,
                    0,
                    handlers["GetWidgetLife"].handler_address,
                    handlers["SetWidgetLife"].handler_address,
                    handlers["BlzGetUnitMaxMana"].handler_address,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_MULTI_ARG,
                    0,
                    handlers["BlzSetUnitMaxMana"].handler_address,
                    handlers["GetUnitState"].handler_address,
                    handlers["SetUnitState"].handler_address,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_MULTI_ARG,
                    0,
                    handler_address("UnitItemInSlot"),
                    handler_address("GetItemTypeId"),
                    handler_address("UnitAddItemById"),
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_MULTI_ARG,
                    0,
                    handler_address("GetItemCharges"),
                    handler_address("SetItemCharges"),
                    handler_address("BlzGetItemIntegerField"),
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_MULTI_ARG,
                    0,
                    handler_address("BlzSetItemIntegerField"),
                    handler_address("BlzGetItemRealField"),
                    handler_address("BlzSetItemRealField"),
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_MULTI_ARG,
                    0,
                    handler_address("BlzGetItemBooleanField"),
                    handler_address("BlzSetItemBooleanField"),
                    handlers["BlzGetUnitAbilityByIndex"].handler_address,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_MULTI_ARG,
                    0,
                    handlers["BlzGetAbilityId"].handler_address,
                    handlers["GetUnitAbilityLevel"].handler_address,
                    handlers["UnitAddAbility"].handler_address,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_MULTI_ARG,
                    0,
                    handlers["SetUnitAbilityLevel"].handler_address,
                    handlers["GetUnitTypeId"].handler_address,
                    handlers["RemoveUnit"].handler_address,
                ),
            )
            response = self._run_native_helper_ops(
                unit_handle,
                ((self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0, candidate.unit_address,
                  candidate.handle, candidate.owner_address), *clone_ops),
                timeout_ms=10000,
            )
            if (len(response) != 15 or any(item.last_error for item in response)
                    or response[1].kind != self.NATIVE_HELPER_OP_JASS_CLONE_SELECTED_UNIT):
                raise RuntimeError("Incomplete bound native clone result")
            result = response[1].result
            if not result:
                raise RuntimeError(f"游戏未能复制单位 {format_rawcode(unit_rawcode)}")
            return unit_rawcode, result
        result = self._run_native_helper_ops(
            0,
            ((
                self.NATIVE_HELPER_OP_JASS_CREATE_LOCAL_UNIT,
                unit_rawcode,
                handlers["GetLocalPlayer"].handler_address,
                handlers["CreateUnit"].handler_address,
                coordinates,
            ),),
        )[0].result
        if not result:
            raise RuntimeError(f"游戏未能创建单位 {format_rawcode(unit_rawcode)}")
        return unit_rawcode, result


    def heal_local_player_units(self) -> int:
        if getattr(self, "_native_selection_unavailable", False):
            from war3_bulk_protocol import BULK_HEAL_LOCAL
            return int(self.bulk_batch_24268(BULK_HEAL_LOCAL)["changed"])
        handlers = self._elephant_handlers(
                None,
                (
                    "GetLocalPlayer",
                    "CreateGroup",
                    "GroupEnumUnitsOfPlayer",
                    "FirstOfGroup",
                    "GroupRemoveUnit",
                    "GetWidgetLife",
                    "BlzGetUnitMaxHP",
                    "SetWidgetLife",
                    "DestroyGroup",
                ),
            )
        return int(self._run_native_helper_ops(
            0,
            (
                (
                    self.NATIVE_HELPER_OP_JASS_HEAL_LOCAL_UNITS,
                    0,
                    handlers["GetLocalPlayer"].handler_address,
                    handlers["CreateGroup"].handler_address,
                    handlers["GroupEnumUnitsOfPlayer"].handler_address,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_MULTI_ARG,
                    0,
                    handlers["FirstOfGroup"].handler_address,
                    handlers["GroupRemoveUnit"].handler_address,
                    handlers["GetWidgetLife"].handler_address,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_MULTI_ARG,
                    0,
                    handlers["BlzGetUnitMaxHP"].handler_address,
                    handlers["SetWidgetLife"].handler_address,
                    handlers["DestroyGroup"].handler_address,
                ),
            ),
            timeout_ms=3000,
        )[0].result)


    def reset_local_player_unit_cooldowns(self) -> int:
        if getattr(self, "_native_selection_unavailable", False):
            from war3_bulk_protocol import BULK_RESET_LOCAL_COOLDOWNS
            return int(self.bulk_batch_24268(BULK_RESET_LOCAL_COOLDOWNS)["changed"])
        handlers = self._elephant_handlers(
                None,
                (
                    "GetLocalPlayer",
                    "CreateGroup",
                    "GroupEnumUnitsOfPlayer",
                    "FirstOfGroup",
                    "GroupRemoveUnit",
                    "UnitResetCooldown",
                    "DestroyGroup",
                ),
            )
        return int(self._run_native_helper_ops(
            0,
            (
                (
                    self.NATIVE_HELPER_OP_JASS_RESET_LOCAL_COOLDOWNS,
                    0,
                    handlers["GetLocalPlayer"].handler_address,
                    handlers["CreateGroup"].handler_address,
                    handlers["GroupEnumUnitsOfPlayer"].handler_address,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_MULTI_ARG,
                    0,
                    handlers["FirstOfGroup"].handler_address,
                    handlers["GroupRemoveUnit"].handler_address,
                    handlers["UnitResetCooldown"].handler_address,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_MULTI_ARG,
                    0,
                    handlers["DestroyGroup"].handler_address,
                    0,
                    0,
                ),
            ),
            timeout_ms=3000,
        )[0].result)


    def complete_local_player_structures(self) -> int:
        if not getattr(self, "_native_selection_unavailable", False):
            raise RuntimeError("持续快速建造当前仅适用于 Warcraft III 3.0")
        from war3_bulk_protocol import BULK_COMPLETE_LOCAL_STRUCTURES
        return int(self.bulk_batch_24268(BULK_COMPLETE_LOCAL_STRUCTURES)["changed"])


    def create_local_units(
        self,
        count: int,
        rawcode: int | str | None = None,
        *,
        use_selected_lookup: bool = True,
    ) -> tuple[int, int]:
        total = int(count)
        if not 1 <= total <= 100:
            raise ValueError("批量复制数量必须在 1 到 100 之间")
        if getattr(self, "_native_selection_unavailable", False) and rawcode is None:
            unit_rawcode = 0
            created = 0
            position = self.query_mouse_world_position()
            spawn_x_bits = self._float_bits(float(position[0]))
            spawn_y_bits = self._float_bits(float(position[1]))
            for _ in range(total):
                result = self.clone_batch_24268(
                    keep=True,
                    copy_abilities=True,
                    copy_items=True,
                    spawn=True,
                    spawn_x_bits=spawn_x_bits,
                    spawn_y_bits=spawn_y_bits,
                )
                rows = tuple(result.get("rows", ()))
                if not rows or int(result.get("changed", 0)) != len(rows):
                    raise RuntimeError("3.0 当前引擎批量复制返回不完整")
                unit_rawcode = int(rows[0]["rawcode"])
                created += len(rows)
            return unit_rawcode, created
        position = self.query_mouse_world_position()
        created = 0
        unit_rawcode = 0
        for _ in range(total):
            unit_rawcode, _handle = self.create_local_unit(
                rawcode,
                position,
                use_selected_lookup=use_selected_lookup,
            )
            created += 1
        return unit_rawcode, created


    def _run_bound_ability_actions(
        self, entries: Iterable[tuple[int, int, int, int]], candidate: UnitCandidate | None = None,
    ) -> list[NativeHelperOpResult]:
        entries = tuple(entries)
        if any(action not in (1, 2, 3, 4) or not 0 < rawcode <= 0xFFFFFFFF
               or not 0 <= level <= 100000 or (action == 3 and not level)
               or (action in (2, 4) and level) or not 0 <= full < (1 << 64)
               for action, rawcode, level, full in entries):
            raise ValueError("Invalid native ability action")
        if not entries:
            return []
        if candidate is None:
            candidate, unit_handle = self._direct_selected_context()
        else:
            native = self._native_snapshot_for_candidate(candidate)
            unit_handle = native.handle if native is not None else 0
        native = self._native_snapshot_for_candidate(candidate)
        if native is None or native.handle != unit_handle:
            raise RuntimeError("Ability actions require a bound native unit identity")
        results = []
        size = self.NATIVE_HELPER_MAX_OPS - 1
        for start in range(0, len(entries), size):
            batch = entries[start:start + size]
            response = self._run_native_helper_ops(unit_handle, (
                (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0, candidate.unit_address,
                 candidate.handle, candidate.owner_address),
                *((self.NATIVE_HELPER_OP_MANAGE_BOUND_ABILITY, rawcode, action, level, full)
                  for action, rawcode, level, full in batch),
            ))
            if (len(response) != len(batch) + 1 or any(item.last_error for item in response)
                    or any(item.kind != self.NATIVE_HELPER_OP_MANAGE_BOUND_ABILITY for item in response[1:])):
                raise RuntimeError("Incomplete native ability action result")
            results.extend(response[1:])
        return results


    def _run_selected_ability_rawcode(self, native_name: str, rawcode: int | str) -> int:
        ability_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        if not ability_rawcode:
            raise ValueError("技能 ID 无效")
        action = {"UnitAddAbility": 1, "UnitRemoveAbility": 2}[native_name]
        if getattr(self, "_native_selection_unavailable", False):
            return int(self.ability_batch_24268(ability_rawcode, action)["changed"])
        return int(self._run_bound_ability_actions(((action, ability_rawcode, 0, 0),))[0].result)


    def add_ability_to_selected_unit(self, rawcode: int | str) -> None:
        if not self._run_selected_ability_rawcode("UnitAddAbility", rawcode):
            raise RuntimeError("游戏拒绝添加该技能；目标可能已拥有此技能或地图中没有该对象")


    def remove_ability_from_selected_unit(self, rawcode: int | str) -> None:
        if not self._run_selected_ability_rawcode("UnitRemoveAbility", rawcode):
            raise RuntimeError("游戏拒绝删除该技能；目标可能没有此技能")


    def add_abilities_to_selected_unit(self, rawcodes: Iterable[int | str]) -> int:
        ability_ids = tuple(int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF for rawcode in rawcodes)
        if not ability_ids or any(not rawcode for rawcode in ability_ids):
            raise ValueError("技能 ID 列表无效")
        if getattr(self, "_native_selection_unavailable", False):
            return sum(
                int(self.ability_batch_24268(rawcode, 1, 0)["changed"])
                for rawcode in ability_ids
            )
        return sum(bool(item.result) for item in self._run_bound_ability_actions(
            (1, rawcode, 0, 0) for rawcode in ability_ids))


    def add_ability_bundle_to_selected_unit(
        self,
        entries: Iterable[tuple[int | str, int | None]],
    ) -> tuple[int, int]:
        bundle = tuple((int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF,
                        None if level is None else int(level)) for rawcode, level in entries)
        if not bundle or any(not rawcode for rawcode, _ in bundle):
            raise ValueError("技能组合无效")
        if any(level is not None and not 1 <= level <= 100000 for _, level in bundle):
            raise ValueError("技能组合等级必须在 1 到 100000 之间")
        if getattr(self, "_native_selection_unavailable", False):
            # The classic route used 112 as an internal "add at default level"
            # sentinel for aura/passive bundles. Warcraft III 3.0 treats 112 as
            # an actual SetUnitAbilityLevel request and rejects it.
            changed = sum(
                int(self.ability_batch_24268(
                    rawcode, 1, 0 if level == 112 else level or 0,
                )["changed"])
                for rawcode, level in bundle
            )
            return changed, len(bundle)
        results = self._run_bound_ability_actions((1, rawcode, level or 0, 0) for rawcode, level in bundle)
        return sum(bool(item.result) for item in results), len(bundle)


    def reset_selected_unit_ability(self, rawcode: int | str) -> None:
        ability_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        if not ability_rawcode:
            raise ValueError("技能 ID 无效")
        if getattr(self, "_native_selection_unavailable", False):
            result = self.ability_batch_24268(ability_rawcode, 5, 0)
            if result["changed"] != result["count"]:
                raise RuntimeError("游戏拒绝重置该技能")
            return
        if not self._run_bound_ability_actions(((4, ability_rawcode, 0, 0),))[0].result:
            raise RuntimeError("游戏拒绝重置该技能；地图中可能没有该对象")


    def remove_all_selected_unit_abilities(self) -> int:
        if getattr(self, "_native_selection_unavailable", False):
            selected = self._selected_candidates_snapshot(None)
            if not selected:
                return 0
            rawcodes: set[int] = set()
            with self._process_memory() as memory:
                for candidate, _unit_handle in selected:
                    rawcodes.update(
                        int(instance.rawcode) & 0xFFFFFFFF
                        for instance in self._ability_instances_from_candidate(memory, candidate)
                        if int(instance.rawcode) & 0xFFFFFFFF
                    )
            return sum(
                int(self.ability_batch_24268(rawcode, 2, 0)["changed"])
                for rawcode in sorted(rawcodes)
            )
        candidate, unit_handle = self._direct_selected_context()
        native = self._native_snapshot_for_candidate(candidate)
        if native is None or native.handle != unit_handle:
            raise RuntimeError("Ability removal requires a bound native unit identity")
        abilities = self._ability_instances_from_candidate(None, candidate)
        results = self._run_bound_ability_actions(
            ((2, item.rawcode, 0, item.handle) for item in abilities), candidate)
        return sum(bool(item.result) for item in results)


    def set_selected_unit_ability_level(self, rawcode: int | str, level: int) -> int:
        ability_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        target_level = int(level)
        if not ability_rawcode or not 1 <= target_level <= 100000:
            raise ValueError("请提供有效技能 ID，等级必须在 1 到 100000 之间")
        if getattr(self, "_native_selection_unavailable", False):
            # Action 1 sets the level for existing instances and creates the
            # skill for selected units that do not already have it. This keeps
            # mixed hero/non-hero selections in one batch.
            result = self.ability_batch_24268(ability_rawcode, 1, target_level)
            if result["changed"] > result["count"]:
                raise RuntimeError("技能等级批处理返回数量异常")
            return target_level
        actual = int(self._run_bound_ability_actions(((3, ability_rawcode, target_level, 0),))[0].arg1)
        if actual != target_level:
            raise RuntimeError(f"技能等级写入后读回 {actual}，目标为 {target_level}")
        return actual


    @staticmethod
    def _ability_field_rawcode_text(rawcode: int) -> str:
        try:
            return int(rawcode).to_bytes(4, "big").decode("ascii")
        except (OverflowError, UnicodeDecodeError):
            return format_rawcode(int(rawcode))


    def _native_ability_metadata(
        self, candidate: UnitCandidate, rawcode: int,
        handlers: dict[str, NativeHandler] | None = None,
    ) -> tuple[AbilityInstance, int, int]:
        native = self._native_snapshot_for_candidate(candidate)
        if native is None:
            raise RuntimeError("技能查询缺少绑定单位快照")
        if handlers is None:
            handlers = self._query_native_table_handlers(("BlzGetUnitAbility", "BlzGetAbilityId"))
        results = self._run_native_helper_ops(native.handle, (
            (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0, candidate.unit_address,
             candidate.handle, candidate.owner_address),
            (self.NATIVE_HELPER_OP_BOUND_ABILITY_METADATA, rawcode,
             handlers["BlzGetUnitAbility"].handler_address,
             handlers["BlzGetAbilityId"].handler_address, 0),
        ))
        if len(results) != 2 or any(result.last_error for result in results):
            raise RuntimeError("DLL 技能元数据返回不完整")
        values = results[0].extra_results
        if len(values) != 10:
            raise RuntimeError("DLL 技能元数据返回不完整")
        ability, data, wrapper, full, tag, wrapper_vtable, data_vtable, actual_id, level, cache = values
        if (not ability or ability != results[1].result or not full or actual_id != rawcode
                or not all(0x10000 <= address < 0x0000800000000000
                           for address in (data, wrapper, wrapper_vtable, data_vtable))
                or not self._looks_like_rawcode(tag >> 32)
                or tag >> 32 in {value >> 32 for value in self.COMPONENT_TAGS.values()}):
            raise RuntimeError("DLL 技能元数据身份校验失败")
        instance = AbilityInstance(
            slot=0, wrapper_address=wrapper, data_address=data,
            wrapper_vtable=wrapper_vtable, data_vtable=data_vtable,
            wrapper_tag_address=wrapper + 0x18, wrapper_tag=tag, handle=full,
            class_rawcode=tag >> 32, rawcode=rawcode, rawcode_address=data + 0x70,
            mirror_rawcode_address=data + 0x78, data_cache_address=data + 0xa0,
            data_cache_pointer=cache if 0x10000 <= cache < 0x0000800000000000 else 0,
        )
        return instance, ability, int(level)


    def _ability_effect_class_for_candidate(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        ability_rawcode: int,
    ) -> tuple[int, bool, str]:
        try:
            if self._native_snapshot_for_candidate(candidate) is not None:
                instance, _, _ = self._native_ability_metadata(candidate, ability_rawcode)
                return instance.class_rawcode, True, ""
            ability_data = self._find_engine_ability_data(
                pm,
                candidate,
                ability_rawcode,
            )
            if not ability_data:
                return ability_rawcode, False, "找不到运行时技能数据对象"
            instance = self._ability_instance_from_data_for_candidate(
                pm,
                candidate,
                ability_data,
                ability_rawcode,
            )
            if instance is None:
                return ability_rawcode, False, "找不到运行时技能包装器"
            if not instance.class_rawcode:
                return ability_rawcode, False, "运行时技能没有可验证的效果类"
            return instance.class_rawcode, True, ""
        except (OSError, RuntimeError) as exc:
            return ability_rawcode, False, str(exc)


    def _current_engine_ability_instance_24268(
        self, candidate: UnitCandidate, ability_rawcode: int,
    ) -> AbilityInstance:
        with self._process_memory() as memory:
            instances = self._ability_instances_from_candidate(
                memory,
                candidate,
                required_rawcodes={ability_rawcode},
            )
        if len(instances) != 1:
            raise RuntimeError(
                f"当前单位上的 {format_rawcode(ability_rawcode)} 运行时技能实例不唯一"
            )
        instance = instances[0]
        if (instance.rawcode != ability_rawcode or not instance.class_rawcode
                or not instance.data_address or not instance.handle):
            raise RuntimeError("当前技能运行时对象身份不完整")
        return instance


    @staticmethod
    def _current_engine_ability_row_24268(result: dict, unit_handle: int) -> dict:
        rows = [row for row in result.get("rows", ()) if row.get("handle") == unit_handle]
        if len(rows) != 1 or rows[0].get("status") != 1:
            raise RuntimeError("当前选中单位没有可绑定的运行时技能实例")
        row = rows[0]
        if not row.get("ability_handle"):
            raise RuntimeError("当前技能返回了无效的运行时句柄")
        return row


    @staticmethod
    def _bind_current_engine_ability_row_24268(
        result: dict,
        candidate: UnitCandidate,
    ) -> dict:
        rawcode = int(candidate.unit_type_id)
        if not rawcode:
            raise RuntimeError("当前单位没有可用于字段绑定的类型 ID")
        rows = [
            row for row in result.get("rows", ())
            if row.get("status") == 1 and int(row.get("rawcode", 0)) == rawcode
        ]
        if len(rows) != 1:
            raise RuntimeError("当前选中单位的技能字段身份不唯一，请减少选中单位后重试")
        return War3Trainer._current_engine_ability_row_24268(result, int(rows[0]["handle"]))


    @staticmethod
    def _current_engine_ability_field_bits(
        spec: AbilityFieldSpec,
        value: bool | int | float,
    ) -> int:
        if spec.value_kind == "real":
            return War3Trainer._float_bits(float(value))
        return int(bool(value)) if spec.value_kind == "boolean" else int(value) & 0xFFFFFFFF


    def _current_engine_ability_field_descriptor_24268(
        self,
        spec: AbilityFieldSpec,
        target: bool | int | float = 0,
    ) -> tuple[int, int, int, int]:
        from war3_ability_field_protocol import descriptor
        return descriptor(
            spec.field_id,
            spec.value_kind,
            spec.scope,
            self._current_engine_ability_field_bits(spec, target),
        )


    def _read_selected_ability_fields_24268(
        self,
        rawcode: int | str,
        level: int,
        *,
        unit_identity: tuple[int, int, int] | None = None,
    ) -> AbilityFieldSnapshot:
        ability_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        level_number = int(level)
        if not ability_rawcode or not 1 <= level_number <= 1000:
            raise ValueError("请提供有效技能 ID，字段等级必须在 1 到 1000 之间")
        if unit_identity is None:
            candidate, _unit_handle = self._direct_selected_context()
        else:
            handle, owner, unit = (int(value) for value in unit_identity)
            candidate = self._candidate_from_display_identity(
                None, handle, owner, unit, "ability_field_candidate", 900,
            )
            if candidate is None:
                raise RuntimeError("当前选中单位已变化，请重新读取字段")
        instance = self._current_engine_ability_instance_24268(candidate, ability_rawcode)
        effect_text = self._ability_field_rawcode_text(instance.class_rawcode)
        specs = ability_fields_for_effect_class(effect_text)
        supported = [spec for spec in specs if spec.runtime_supported]
        values_by_key: dict[tuple[str, str, str], AbilityFieldValue] = {}
        ability_handle = 0
        ability_jass_handle = 0
        current_level: int | None = None
        for start in range(0, len(supported), 32):
            batch = tuple(supported[start:start + 32])
            result = self.ability_field_batch_24268(
                ability_rawcode,
                level_number,
                0,
                tuple(self._current_engine_ability_field_descriptor_24268(spec) for spec in batch),
                target_unit=ability_jass_handle,
            )
            row = (
                self._bind_current_engine_ability_row_24268(result, candidate)
                if not ability_jass_handle
                else self._current_engine_ability_row_24268(result, ability_jass_handle)
            )
            ability_jass_handle = int(row["handle"])
            if ability_handle and row["ability_handle"] != ability_handle:
                raise RuntimeError("技能实例在字段批处理期间发生变化")
            ability_handle = int(row["ability_handle"])
            row_level = int(row["ability_level"])
            if current_level is not None and row_level != current_level:
                raise RuntimeError("技能等级在字段批处理期间发生变化")
            current_level = row_level
            for spec, field in zip(batch, row["values"]):
                value = self._decode_ability_field_value(spec, field["before"])
                if spec.value_kind == "real" and not math.isfinite(float(value)):
                    values_by_key[(spec.rawcode, spec.value_kind, spec.scope)] = AbilityFieldValue(
                        spec, None, "读取异常", "游戏返回了非有限浮点值",
                    )
                else:
                    values_by_key[(spec.rawcode, spec.value_kind, spec.scope)] = AbilityFieldValue(
                        spec, value, "可尝试" if spec.writable else "只读",
                    )
        fields: list[AbilityFieldValue] = []
        for spec in specs:
            key = (spec.rawcode, spec.value_kind, spec.scope)
            field_value = values_by_key.get(key)
            if field_value is None:
                reason = (
                    "字符串字段的当前引擎 ABI 尚未开放字符串传输"
                    if spec.value_kind == "string"
                    else "等级数组字段需要单独的数组索引"
                )
                field_value = AbilityFieldValue(spec, None, "未开放", reason)
            fields.append(field_value)
        if current_level is None or not ability_handle:
            raise RuntimeError("当前技能字段批处理没有返回有效身份")
        return AbilityFieldSnapshot(
            ability_rawcode=ability_rawcode,
            effect_class=instance.class_rawcode,
            current_level=current_level,
            requested_level=level_number,
            fields=tuple(fields),
            unit_identity=(candidate.handle, candidate.owner_address, candidate.unit_address),
            effect_class_verified=True,
            ability_identity=(ability_handle, instance.data_address, instance.handle),
        )


    def _set_selected_ability_field_24268(
        self,
        rawcode: int | str,
        level: int,
        spec: AbilityFieldSpec,
        value: bool | int | float | str,
        expected_snapshot: AbilityFieldSnapshot | None = None,
        *,
        unit_identity: tuple[int, int, int] | None = None,
    ) -> AbilityFieldValue:
        if self._ability_field_write_disabled:
            raise RuntimeError("上一次技能字段回滚无法确认，请重新连接游戏后再写入")
        if not spec.runtime_supported or not spec.writable:
            raise ValueError("该字段当前未开放运行时写入")
        ability_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        level_number = int(level)
        if expected_snapshot is not None:
            if ability_rawcode != expected_snapshot.ability_rawcode:
                raise RuntimeError("技能 ID 已变化，请重新读取字段")
            if level_number != expected_snapshot.requested_level:
                raise RuntimeError("字段等级已变化，请重新读取字段")
            if expected_snapshot.win10_compat:
                raise RuntimeError("当前引擎字段读取来源已变化，请重新读取字段")
        target = self._coerce_ability_field_value(spec, value)
        if unit_identity is None:
            candidate, _unit_handle = self._direct_selected_context()
        else:
            handle, owner, unit = (int(item) for item in unit_identity)
            candidate = self._candidate_from_display_identity(
                None, handle, owner, unit, "ability_field_candidate", 900,
            )
            if candidate is None:
                raise RuntimeError("当前选中单位已变化，请重新读取字段")
        instance = self._current_engine_ability_instance_24268(candidate, ability_rawcode)
        effect_text = self._ability_field_rawcode_text(instance.class_rawcode)
        applicable = {
            (field.rawcode, field.value_kind, field.scope)
            for field in ability_fields_for_effect_class(effect_text)
        }
        key = (spec.rawcode, spec.value_kind, spec.scope)
        if key not in applicable or ABILITY_FIELD_BY_KEY.get(key) != spec:
            raise RuntimeError("当前技能效果类已经变化，请重新读取字段")
        if spec.use_specific and not instance.class_rawcode:
            raise RuntimeError("运行时效果类未确认，不能写入效果类专用字段")
        descriptor = self._current_engine_ability_field_descriptor_24268(spec)
        read_result = self.ability_field_batch_24268(
            ability_rawcode, level_number, 0, (descriptor,), target_unit=0,
        )
        row = self._bind_current_engine_ability_row_24268(read_result, candidate)
        ability_jass_handle = int(row["handle"])
        identity = (int(row["ability_handle"]), instance.data_address, instance.handle)
        current_level = int(row["ability_level"])
        if expected_snapshot is not None:
            if not all(expected_snapshot.ability_identity) or identity != expected_snapshot.ability_identity:
                raise RuntimeError("技能实例已经变化，请重新读取字段")
            if any(expected_snapshot.unit_identity) and (
                candidate.handle, candidate.owner_address, candidate.unit_address
            ) != expected_snapshot.unit_identity:
                raise RuntimeError("当前选中单位已变化，请重新读取字段")
            if current_level != expected_snapshot.current_level:
                raise RuntimeError("技能当前等级已变化，请重新读取字段")
            if expected_snapshot.effect_class != instance.class_rawcode:
                raise RuntimeError("当前技能效果类已经变化，请重新读取字段")
        original_bits = int(row["values"][0]["before"]) & 0xFFFFFFFF
        original = self._decode_ability_field_value(spec, original_bits)
        target_bits = self._current_engine_ability_field_bits(spec, target)
        try:
            self.ability_field_batch_24268(
                ability_rawcode,
                level_number,
                1,
                (self._current_engine_ability_field_descriptor_24268(spec, target),),
                target_unit=ability_jass_handle,
            )
            verify_result = self.ability_field_batch_24268(
                ability_rawcode, level_number, 0, (descriptor,), target_unit=ability_jass_handle,
            )
            verify_row = self._current_engine_ability_row_24268(verify_result, ability_jass_handle)
            actual = self._decode_ability_field_value(spec, verify_row["values"][0]["before"])
            if not self._ability_field_values_equal(spec, actual, target):
                raise RuntimeError(f"字段写入后读回不一致：{actual!s}!={target!s}")
        except Exception as exc:
            rollback_ok = False
            try:
                self.ability_field_batch_24268(
                    ability_rawcode,
                    level_number,
                    1,
                    (self._current_engine_ability_field_descriptor_24268(spec, original),),
                    target_unit=ability_jass_handle,
                )
                rollback_result = self.ability_field_batch_24268(
                    ability_rawcode, level_number, 0, (descriptor,), target_unit=ability_jass_handle,
                )
                rollback_row = self._current_engine_ability_row_24268(rollback_result, ability_jass_handle)
                restored = self._decode_ability_field_value(spec, rollback_row["values"][0]["before"])
                rollback_ok = self._ability_field_values_equal(spec, restored, original)
            except Exception:
                rollback_ok = False
            if not rollback_ok:
                self._ability_field_write_disabled = True
                raise RuntimeError(f"{exc}；原始字段恢复无法确认") from exc
            raise
        return AbilityFieldValue(spec, actual, "已验证")


    def _ability_field_context_from_candidate_locked(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        unit_handle: int,
        rawcode: int | str,
        level: int,
        handlers: dict[str, NativeHandler] | None = None,
    ) -> SelectedAbilityFieldContext:
        ability_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        level_number = int(level)
        if not ability_rawcode or not 1 <= level_number <= 1000:
            raise ValueError("请提供有效技能 ID，字段等级必须在 1 到 1000 之间")
        if handlers is None:
            handlers = self._discover_native_handlers_near_table(
                pm,
                self.ABILITY_FIELD_NATIVE_NAMES,
            )
        native = self._native_snapshot_for_candidate(candidate)
        if native is not None:
            if native.handle != unit_handle:
                raise RuntimeError("当前选中单位已变化，请重新读取字段")
            instance, ability_handle, current_level = self._native_ability_metadata(candidate, ability_rawcode, handlers)
            return SelectedAbilityFieldContext(
                candidate=candidate, unit_handle=unit_handle, ability_handle=ability_handle,
                ability_rawcode=ability_rawcode, effect_class=instance.class_rawcode,
                effect_class_verified=True, effect_class_note="", current_level=current_level, handlers=handlers,
                ability_identity=(ability_handle, instance.data_address, instance.handle),
            )
        ability_handle = int(self._run_native_helper_ops(
            unit_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE,
                ability_rawcode,
                handlers["BlzGetUnitAbility"].handler_address,
                0,
                0,
            ),),
        )[0].result)
        if not ability_handle:
            raise RuntimeError(
                f"当前选中单位没有 {format_rawcode(ability_rawcode)} 的运行时技能实例"
            )
        actual_rawcode = int(self._run_native_helper_ops(
            ability_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_UNIT_INT_QUERY,
                0,
                handlers["BlzGetAbilityId"].handler_address,
                0,
                0,
            ),),
        )[0].result) & 0xFFFFFFFF
        if actual_rawcode != ability_rawcode:
            raise RuntimeError(
                "技能实例在解析期间发生变化："
                f"{format_rawcode(actual_rawcode)}!={format_rawcode(ability_rawcode)}"
            )
        current_level = int(self._run_native_helper_ops(
            unit_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE_LEVEL,
                ability_rawcode,
                handlers["GetUnitAbilityLevel"].handler_address,
                0,
                0,
            ),),
        )[0].result)
        effect_class, effect_class_verified, effect_class_note = (
            self._ability_effect_class_for_candidate(
                pm,
                candidate,
                ability_rawcode,
            )
        )
        return SelectedAbilityFieldContext(
            candidate=candidate,
            unit_handle=unit_handle,
            ability_handle=ability_handle,
            ability_rawcode=ability_rawcode,
            effect_class=effect_class,
            effect_class_verified=effect_class_verified,
            effect_class_note=effect_class_note,
            current_level=current_level,
            handlers=handlers,
        )


    def _selected_ability_field_context_locked(
        self,
        rawcode: int | str,
        level: int,
    ) -> SelectedAbilityFieldContext:
        candidate, unit_handle = War3Trainer._direct_selected_context(self)
        return self._ability_field_context_from_candidate_locked(None, candidate, unit_handle, rawcode, level)


    def _ability_field_context_by_identity_locked(
        self,
        rawcode: int | str,
        level: int,
        unit_identity: tuple[int, int, int],
        win10_compat: bool,
    ) -> SelectedAbilityFieldContext:
        handle, owner, unit = (int(value) for value in unit_identity)
        # Both UI editions bind the same native identity; no compatibility recovery.
        candidate = self._candidate_from_display_identity(
            None, handle, owner, unit, "ability_field_candidate", 900)
        if candidate is None:
            raise RuntimeError("当前选中单位已变化，请重新读取字段")
        native = self._native_snapshot_for_candidate(candidate)
        if native is None:
            raise RuntimeError("技能查询缺少绑定单位快照")
        return self._ability_field_context_from_candidate_locked(
            None, candidate, native.handle, rawcode, level)


    def _ability_field_get_op(
        self,
        spec: AbilityFieldSpec,
        handlers: dict[str, NativeHandler],
        level_index: int,
    ) -> tuple[int, int, int, int, int]:
        handler_name = self.ABILITY_FIELD_GETTER_NAMES[(spec.value_kind, spec.scope)]
        op_kind = (
            self.NATIVE_HELPER_OP_JASS_ABILITY_LEVEL_FIELD_GET
            if spec.scope == "level"
            else self.NATIVE_HELPER_OP_JASS_ABILITY_FIELD_GET
        )
        return (
            op_kind,
            spec.field_id,
            handlers[handler_name].handler_address,
            level_index if spec.scope == "level" else 0,
            0,
        )


    def _decode_ability_field_value(
        self,
        spec: AbilityFieldSpec,
        raw_value: int,
    ) -> bool | int | float:
        if spec.value_kind == "boolean":
            return bool(int(raw_value) & 1)
        if spec.value_kind == "integer":
            return ctypes.c_int32(int(raw_value) & 0xFFFFFFFF).value
        return self._float_from_bits(raw_value)


    def _run_bound_ability_field_ops(
        self, context: SelectedAbilityFieldContext, ops: Iterable[tuple[int, int, int, int, int]],
    ) -> list[NativeHelperOpResult]:
        candidate = context.candidate
        native = self._native_snapshot_for_candidate(candidate)
        if native is None or native.handle != context.unit_handle or not all(context.ability_identity):
            raise RuntimeError("技能查询缺少绑定单位快照")
        handle, data, full = context.ability_identity
        if handle != context.ability_handle:
            raise RuntimeError("DLL 技能元数据身份校验失败")
        batch = tuple(ops)
        if not batch or len(batch) > self.NATIVE_HELPER_MAX_OPS - 3:
            raise ValueError("Invalid bound ability field batch size")
        guards = (
            (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0, candidate.unit_address,
             candidate.handle, candidate.owner_address),
            (self.NATIVE_HELPER_OP_BOUND_ABILITY_IDENTITY, context.ability_rawcode, handle, data, full),
            (self.NATIVE_HELPER_OP_BOUND_ABILITY_CONTEXT, context.effect_class,
             context.handlers["BlzGetUnitAbility"].handler_address,
             context.handlers["BlzGetAbilityId"].handler_address, context.current_level),
        )
        results = self._run_native_helper_ops(native.handle, guards + batch)
        if len(results) != len(guards) + len(batch) or any(result.last_error for result in results):
            raise RuntimeError("DLL 技能元数据返回不完整")
        return list(results[3:])


    def _read_single_ability_field_locked(
        self,
        context: SelectedAbilityFieldContext,
        spec: AbilityFieldSpec,
        level_index: int,
    ) -> bool | int | float:
        result = self._run_bound_ability_field_ops(
            context,
            (self._ability_field_get_op(spec, context.handlers, level_index),),
        )[0]
        return self._decode_ability_field_value(spec, result.result)


    def read_selected_ability_fields(
        self,
        rawcode: int | str,
        level: int,
        *,
        unit_identity: tuple[int, int, int] | None = None,
        win10_compat: bool = False,
    ) -> AbilityFieldSnapshot:
        if getattr(self, "_native_selection_unavailable", False):
            return self._read_selected_ability_fields_24268(
                rawcode,
                level,
                unit_identity=unit_identity,
            )
        level_number = int(level)
        level_index = level_number - 1
        with self._native_helper_transaction():
            context = (
                self._ability_field_context_by_identity_locked(
                    rawcode,
                    level_number,
                    unit_identity,
                    win10_compat,
                )
                if unit_identity is not None
                else self._selected_ability_field_context_locked(rawcode, level_number)
            )
            effect_text = self._ability_field_rawcode_text(context.effect_class)
            specs = ability_fields_for_effect_class(effect_text)
            values_by_key: dict[tuple[str, str, str], AbilityFieldValue] = {}
            supported = [
                spec
                for spec in specs
                if spec.runtime_supported
                and (context.effect_class_verified or not spec.use_specific)
            ]
            batch_size = self.NATIVE_HELPER_MAX_OPS - 3
            for start in range(0, len(supported), batch_size):
                batch = supported[start : start + batch_size]
                results = self._run_bound_ability_field_ops(
                    context, tuple(self._ability_field_get_op(spec, context.handlers, level_index) for spec in batch),
                )
                for spec, result in zip(batch, results):
                    value = self._decode_ability_field_value(spec, result.result)
                    if spec.value_kind == "real" and not math.isfinite(float(value)):
                        field_value = AbilityFieldValue(
                            spec,
                            None,
                            "读取异常",
                            "游戏返回了非有限浮点值",
                        )
                    else:
                        field_value = AbilityFieldValue(
                            spec,
                            value,
                            "可尝试" if spec.writable else "只读",
                        )
                    values_by_key[(spec.rawcode, spec.value_kind, spec.scope)] = field_value
            fields: list[AbilityFieldValue] = []
            for spec in specs:
                key = (spec.rawcode, spec.value_kind, spec.scope)
                field_value = values_by_key.get(key)
                if field_value is None:
                    if not context.effect_class_verified and spec.use_specific:
                        field_value = AbilityFieldValue(
                            spec,
                            None,
                            "未确认",
                            context.effect_class_note or "运行时效果类未解析",
                        )
                    else:
                        reason = (
                            "字符串字段的 JASS 句柄 ABI 尚未开放"
                            if spec.value_kind == "string"
                            else "等级数组字段需要单独的数组索引"
                        )
                        field_value = AbilityFieldValue(spec, None, "未开放", reason)
                fields.append(field_value)
        return AbilityFieldSnapshot(
            ability_rawcode=context.ability_rawcode,
            effect_class=context.effect_class,
            current_level=context.current_level,
            requested_level=level_number,
            fields=tuple(fields),
            unit_identity=context.unit_identity,
            effect_class_verified=context.effect_class_verified,
            effect_class_note=context.effect_class_note,
            win10_compat=bool(win10_compat and unit_identity is not None),
            ability_identity=context.ability_identity,
        )


    @staticmethod
    def _coerce_ability_field_value(
        spec: AbilityFieldSpec,
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
            try:
                parsed = parse_integer_number(value)
            except ValueError as exc:
                raise ValueError("整数字段必须是整数") from exc
            if not -(1 << 31) <= parsed <= 0xFFFFFFFF:
                raise ValueError("整数字段必须在 -2147483648 到 4294967295 之间")
            return ctypes.c_int32(parsed & 0xFFFFFFFF).value
        parsed = float(value)
        if not math.isfinite(parsed) or not -100_000_000.0 <= parsed <= 100_000_000.0:
            raise ValueError("实数字段必须是 -100000000 到 100000000 之间的有限数值")
        return parsed


    def _ability_field_set_op(
        self,
        spec: AbilityFieldSpec,
        handlers: dict[str, NativeHandler],
        level_index: int,
        value: bool | int | float,
    ) -> tuple[int, int, int, int, int]:
        handler_name = self.ABILITY_FIELD_SETTER_NAMES[(spec.value_kind, spec.scope)]
        handler = handlers[handler_name].handler_address
        if spec.value_kind == "real":
            bits = self._float_bits(float(value))
            if spec.scope == "level":
                return (
                    self.NATIVE_HELPER_OP_JASS_ABILITY_REAL_LEVEL_FIELD_SET,
                    spec.field_id,
                    handler,
                    level_index,
                    bits,
                )
            return (
                self.NATIVE_HELPER_OP_JASS_ABILITY_REAL_FIELD_SET,
                spec.field_id,
                handler,
                bits,
                0,
            )
        bits = int(bool(value)) if spec.value_kind == "boolean" else int(value) & 0xFFFFFFFF
        if spec.scope == "level":
            return (
                self.NATIVE_HELPER_OP_JASS_ABILITY_SCALAR_LEVEL_FIELD_SET,
                spec.field_id,
                handler,
                level_index,
                bits,
            )
        return (
            self.NATIVE_HELPER_OP_JASS_ABILITY_SCALAR_FIELD_SET,
            spec.field_id,
            handler,
            bits,
            0,
        )


    def _ability_field_values_equal(
        self,
        spec: AbilityFieldSpec,
        actual: bool | int | float,
        target: bool | int | float,
    ) -> bool:
        if spec.value_kind == "real":
            return self._float_bits(float(actual)) == self._float_bits(float(target))
        return actual == target


    def set_selected_ability_field(
        self,
        rawcode: int | str,
        level: int,
        spec: AbilityFieldSpec,
        value: bool | int | float | str,
        expected_snapshot: AbilityFieldSnapshot | None = None,
        *,
        unit_identity: tuple[int, int, int] | None = None,
        win10_compat: bool = False,
    ) -> AbilityFieldValue:
        if getattr(self, "_native_selection_unavailable", False):
            return self._set_selected_ability_field_24268(
                rawcode,
                level,
                spec,
                value,
                expected_snapshot,
                unit_identity=unit_identity,
            )
        if self._ability_field_write_disabled:
            raise RuntimeError("上一次技能字段回滚无法确认，请重新连接游戏后再写入")
        if not spec.runtime_supported or not spec.writable:
            raise ValueError("该字段当前未开放运行时写入")
        level_number = int(level)
        ability_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        if expected_snapshot is not None:
            if ability_rawcode != expected_snapshot.ability_rawcode:
                raise RuntimeError("技能 ID 已变化，请重新读取字段")
            if level_number != expected_snapshot.requested_level:
                raise RuntimeError("字段等级已变化，请重新读取字段")
            if bool(win10_compat) != bool(expected_snapshot.win10_compat):
                raise RuntimeError("技能字段读取来源已变化，请重新读取字段")
        target = self._coerce_ability_field_value(spec, value)
        level_index = level_number - 1
        with self._native_helper_transaction():
            context = (
                self._ability_field_context_by_identity_locked(
                    ability_rawcode,
                    level_number,
                    unit_identity,
                    win10_compat,
                )
                if unit_identity is not None
                else self._selected_ability_field_context_locked(
                    ability_rawcode,
                    level_number,
                )
            )
            if expected_snapshot is not None:
                if (not all(expected_snapshot.ability_identity)
                        or context.ability_identity != expected_snapshot.ability_identity):
                    raise RuntimeError("技能实例已经变化，请重新读取字段")
                if (
                    any(expected_snapshot.unit_identity)
                    and context.unit_identity != expected_snapshot.unit_identity
                ):
                    raise RuntimeError("当前选中单位已变化，请重新读取字段")
                if context.current_level != expected_snapshot.current_level:
                    raise RuntimeError("技能当前等级已变化，请重新读取字段")
                if (
                    context.effect_class != expected_snapshot.effect_class
                    or context.effect_class_verified
                    != expected_snapshot.effect_class_verified
                ):
                    raise RuntimeError("当前技能效果类已经变化，请重新读取字段")
            if spec.use_specific and not context.effect_class_verified:
                raise RuntimeError(
                    "运行时效果类未确认，不能写入效果类专用字段："
                    f"{context.effect_class_note or '请重新读取'}"
                )
            applicable = {
                (field.rawcode, field.value_kind, field.scope)
                for field in ability_fields_for_effect_class(
                    self._ability_field_rawcode_text(context.effect_class)
                )
            }
            key = (spec.rawcode, spec.value_kind, spec.scope)
            if key not in applicable or ABILITY_FIELD_BY_KEY.get(key) != spec:
                raise RuntimeError("当前技能效果类已经变化，请重新读取字段")
            original = self._read_single_ability_field_locked(
                context,
                spec,
                level_index,
            )

            def write_field(field_value: bool | int | float) -> bool:
                result = self._run_bound_ability_field_ops(
                    context,
                    (self._ability_field_set_op(
                        spec,
                        context.handlers,
                        level_index,
                        field_value,
                    ),),
                )[0]
                return bool(result.result)

            try:
                if not write_field(target):
                    raise RuntimeError("游戏拒绝写入该技能字段")
                actual = self._read_single_ability_field_locked(
                    context,
                    spec,
                    level_index,
                )
                if not self._ability_field_values_equal(spec, actual, target):
                    raise RuntimeError(
                        f"字段写入后读回不一致：{actual!s}!={target!s}"
                    )
            except Exception as exc:
                rollback_ok = False
                try:
                    write_field(original)
                    restored = self._read_single_ability_field_locked(
                        context,
                        spec,
                        level_index,
                    )
                    rollback_ok = self._ability_field_values_equal(
                        spec,
                        restored,
                        original,
                    )
                except Exception:
                    rollback_ok = False
                if not rollback_ok:
                    self._ability_field_write_disabled = True
                    raise RuntimeError(f"{exc}；原始字段恢复无法确认") from exc
                raise
        return AbilityFieldValue(spec, actual, "已验证")


    def set_local_player_tech(self, rawcode: int | str, level: int) -> int:
        tech_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        target_level = int(level)
        if not tech_rawcode or not 0 <= target_level <= 100000:
            raise ValueError("请提供有效科技 ID，等级必须在 0 到 100000 之间")
        if getattr(self, "_native_selection_unavailable", False):
            result = self.world_batch_24268(1, tech_rawcode, target_level)
            return int(result["after0"])
        handlers = self._elephant_handlers(
                None,
                ("GetLocalPlayer", "SetPlayerTechMaxAllowed", "SetPlayerTechResearched"),
            )
        self._run_native_helper_ops(
            0,
            (
                (
                    self.NATIVE_HELPER_OP_JASS_SET_LOCAL_TECH,
                    tech_rawcode,
                    handlers["GetLocalPlayer"].handler_address,
                    handlers["SetPlayerTechMaxAllowed"].handler_address,
                    target_level,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_SET_LOCAL_TECH,
                    tech_rawcode,
                    handlers["GetLocalPlayer"].handler_address,
                    handlers["SetPlayerTechResearched"].handler_address,
                    target_level,
                ),
            ),
        )
        return target_level


    def set_local_player_xp_rate(self, rate: float) -> float:
        target = float(rate)
        if not 0.0 <= target <= 10000.0:
            raise ValueError("经验倍率必须在 0 到 10000 之间")
        if getattr(self, "_native_selection_unavailable", False):
            result = self.world_batch_24268(2, 0, self._float_bits(target))
            return self._float_from_bits(result["after0"])
        handlers = self._elephant_handlers(None, ("GetLocalPlayer", "SetPlayerHandicapXP"))
        self._run_native_helper_ops(
            0,
            ((
                self.NATIVE_HELPER_OP_JASS_SET_LOCAL_XP_RATE,
                self._float_bits(target),
                handlers["GetLocalPlayer"].handler_address,
                handlers["SetPlayerHandicapXP"].handler_address,
                0,
            ),),
        )
        return target


    def get_map_fog_state(self) -> tuple[bool, bool]:
        if getattr(self, "_native_selection_unavailable", False):
            result = self.world_batch_24268(3, 0, 0)
            return bool(result["after0"]), bool(result["after1"])
        handlers = self._elephant_handlers(None, ("IsFogEnabled", "IsFogMaskEnabled"))
        results = self._run_native_helper_ops(
            0,
            (
                (
                    self.NATIVE_HELPER_OP_JASS_WORLD_INT_QUERY,
                    0,
                    handlers["IsFogEnabled"].handler_address,
                    0,
                    0,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_WORLD_INT_QUERY,
                    0,
                    handlers["IsFogMaskEnabled"].handler_address,
                    0,
                    0,
                ),
            ),
        )
        return bool(results[0].result), bool(results[1].result)


    def set_map_revealed(self, revealed: bool) -> None:
        if getattr(self, "_native_selection_unavailable", False):
            self.world_batch_24268(4, 0, int(bool(revealed)))
            return
        handlers = self._elephant_handlers(None, ("FogEnable", "FogMaskEnable"))
        fog_enabled = 0 if revealed else 1
        self._run_native_helper_ops(
            0,
            (
                (
                    self.NATIVE_HELPER_OP_JASS_FOG_BOOL,
                    fog_enabled,
                    handlers["FogEnable"].handler_address,
                    0,
                    0,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_FOG_BOOL,
                    fog_enabled,
                    handlers["FogMaskEnable"].handler_address,
                    0,
                    0,
                ),
            ),
        )


    def set_game_paused(self, paused: bool) -> None:
        if getattr(self, "_native_selection_unavailable", False):
            self.world_batch_24268(5, 0, int(bool(paused)))
            return
        handlers = self._elephant_handlers(None, ("PauseGame",))
        self._run_native_helper_ops(
            0,
            ((
                self.NATIVE_HELPER_OP_JASS_WORLD_BOOL,
                1 if paused else 0,
                handlers["PauseGame"].handler_address,
                0,
                0,
            ),),
        )


    def end_current_game(self, show_score_screen: bool = True) -> None:
        if getattr(self, "_native_selection_unavailable", False):
            self.world_batch_24268(6, 0, int(bool(show_score_screen)))
            return
        handlers = self._elephant_handlers(None, ("EndGame",))
        self._run_native_helper_ops(
            0,
            ((
                self.NATIVE_HELPER_OP_JASS_WORLD_BOOL,
                1 if show_score_screen else 0,
                handlers["EndGame"].handler_address,
                0,
                0,
            ),),
        )


    def set_peace_mode(self, enabled: bool) -> int:
        if getattr(self, "_native_selection_unavailable", False):
            from war3_bulk_protocol import BULK_PEACE_MODE
            return int(self.bulk_batch_24268(BULK_PEACE_MODE, int(bool(enabled)))["changed"])
        handlers = self._elephant_handlers(None, ("Player", "SetPlayerAlliance"))
        return int(self._run_native_helper_ops(
            0,
            ((
                self.NATIVE_HELPER_OP_JASS_PEACE_MODE,
                1 if enabled else 0,
                handlers["Player"].handler_address,
                handlers["SetPlayerAlliance"].handler_address,
                0,
            ),),
        )[0].result)


    def kill_selected_owner_units(self) -> int:
        if getattr(self, "_native_selection_unavailable", False):
            from war3_bulk_protocol import BULK_KILL_SELECTED_OWNER
            return int(self.bulk_batch_24268(BULK_KILL_SELECTED_OWNER)["changed"])
        candidate, unit_handle = self._direct_selected_context()
        handler = self._query_native_table_handlers(("KillUnit",))["KillUnit"].handler_address
        results = self._run_native_helper_ops(unit_handle, (
            (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0, candidate.unit_address,
             candidate.handle, candidate.owner_address),
            (self.NATIVE_HELPER_OP_BOUND_OWNER_KILL, 0, handler, 0, 0)), timeout_ms=120000)
        if (len(results) != 2 or any(result.last_error for result in results)
                or results[1].kind != self.NATIVE_HELPER_OP_BOUND_OWNER_KILL
                or not 0 <= results[1].result <= 100000):
            raise RuntimeError("Incomplete native owner group result")
        return int(results[1].result)


    @staticmethod
    def _scan_bytes_private_between(
        pm: ProcessMemory,
        pattern: bytes,
        start_address: int,
        end_address: int,
    ) -> list[int]:
        if not pattern or end_address <= start_address:
            return []
        hits: list[int] = []
        tail_len = max(0, len(pattern) - 1)
        for region in pm.regions():
            if region.typ != MEM_PRIVATE:
                continue
            start = max(region.base, start_address)
            end = min(region.base + region.size, end_address)
            if end <= start:
                continue
            offset = start - region.base
            limit = end - region.base
            tail = b""
            while offset < limit:
                size = min(4 * 1024 * 1024, limit - offset)
                try:
                    data = tail + pm.read(region.base + offset, size)
                except OSError:
                    offset += size
                    tail = b""
                    continue
                base = region.base + offset - len(tail)
                search = 0
                while True:
                    index = data.find(pattern, search)
                    if index < 0:
                        break
                    address = base + index
                    if start_address <= address < end_address:
                        hits.append(address)
                    search = index + 1
                tail = data[-tail_len:] if tail_len else b""
                offset += size
        return hits


    def _ability_instance_from_data_for_candidate(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        data_address: int,
        rawcode: int,
    ) -> AbilityInstance | None:
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
            wrapper = data_ref - 0x90
            instance = self._ability_instance_from_wrapper(pm, candidate, wrapper, component_rawcodes)
            if instance is None:
                continue
            if instance.data_address == data_address and instance.rawcode == rawcode:
                self._ability_instance_by_data[cache_key] = instance
                return instance
        return None


    def _ability_data_instance_for_candidate(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        data_address: int,
        rawcode: int,
    ) -> AbilityInstance | None:
        if not self._sane_heap_ptr(data_address):
            return None
        try:
            data_vtable = pm.read_u64(data_address)
            unit_address = pm.read_u64(data_address + 0x68)
            data_rawcode = pm.read_u32(data_address + 0x70)
            mirror_rawcode = pm.read_u32(data_address + 0x78)
            data_cache_pointer = pm.read_u64(data_address + 0xA0)
        except OSError:
            return None
        if not self._looks_like_vtable(data_vtable):
            return None
        if unit_address != candidate.unit_address:
            return None
        if data_rawcode != rawcode or mirror_rawcode != rawcode:
            return None
        return AbilityInstance(
            slot=0,
            wrapper_address=0,
            data_address=data_address,
            wrapper_vtable=0,
            data_vtable=data_vtable,
            wrapper_tag_address=0,
            wrapper_tag=0,
            handle=0,
            class_rawcode=rawcode,
            rawcode=rawcode,
            rawcode_address=data_address + 0x70,
            mirror_rawcode_address=data_address + 0x78,
            data_cache_address=data_address + 0xA0,
            data_cache_pointer=(
                data_cache_pointer if self._sane_heap_ptr(data_cache_pointer) else 0
            ),
        )


    def _run_internal_ability_ops(
        self, candidate: UnitCandidate, ops: Iterable[tuple[int, int, int, int, int]],
    ) -> list[NativeHelperOpResult]:
        native = self._native_snapshot_for_candidate(candidate)
        if native is None:
            return self._run_native_helper_ops(candidate.unit_address, ops)
        # The command uses the JASS handle for validation. C passes the
        # validated object pointer to internal functions, never the JASS ID.
        results = self._run_native_helper_ops(native.handle, (
            (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0, candidate.unit_address,
             candidate.handle, candidate.owner_address), *tuple(ops),
        ))
        return results[1:]


    def _create_engine_ability_instance(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        rawcode: int,
        *,
        refresh_after_add: bool = True,
        require_wrapper: bool = True,
    ) -> tuple[AbilityInstance, bool]:
        if not candidate.unit_address:
            raise RuntimeError("当前单位缺少运行时 unit 指针，不能从资源创建技能模板")
        internals = self._discover_native_ability_internals(pm)
        native_path = self._native_snapshot_for_candidate(candidate) is not None
        existing_data = 0
        if native_path:
            existing_instances = self._ability_instances_from_candidate(
                pm, candidate, required_rawcodes={rawcode}
            )
            if len(existing_instances) > 1:
                raise RuntimeError(
                    f"当前单位上的 {format_rawcode(rawcode)} 运行时实例不唯一"
                )
            if existing_instances:
                return existing_instances[0], False
        else:
            existing_data = self._find_engine_ability_data(pm, candidate, rawcode)
        if existing_data:
            instance = (
                self._ability_instance_from_data_for_candidate(
                    pm,
                    candidate,
                    existing_data,
                    rawcode,
                )
                if require_wrapper
                else self._ability_data_instance_for_candidate(
                    pm,
                    candidate,
                    existing_data,
                    rawcode,
                )
            )
            if instance is not None:
                return instance, False
            raise RuntimeError(
                f"当前单位已存在 {format_rawcode(rawcode)}，但无法安全映射到运行时实例"
            )
        results = self._run_internal_ability_ops(
            candidate,
            (
                (self.NATIVE_HELPER_OP_INTERNAL_ABILITY_BEGIN, 0, internals.begin_address, 0, 0),
                (self.NATIVE_HELPER_OP_INTERNAL_ABILITY_ADD, rawcode, internals.add_address, 0, 0),
                (self.NATIVE_HELPER_OP_INTERNAL_ABILITY_END, 0, internals.end_address, 0, 0),
            ),
        )
        data_address = results[1].result if len(results) >= 2 else 0
        if not data_address:
            raise RuntimeError(f"引擎未能从资源创建 {format_rawcode(rawcode)} 运行时技能实例")
        try:
            if refresh_after_add:
                self._run_internal_ability_ops(
                    candidate,
                    (
                        (
                            self.NATIVE_HELPER_OP_INTERNAL_ABILITY_REFRESH,
                            0,
                            internals.refresh_address,
                            0,
                            0,
                        ),
                    ),
                )
            instance: AbilityInstance | None = None
            if native_path:
                instance, _, _ = self._native_ability_metadata(candidate, rawcode)
                if instance.data_address != data_address:
                    raise RuntimeError("创建后的技能数据对象与引擎返回对象不一致")
            else:
                for lookup_delay in (0.05, 0.10):
                    time.sleep(lookup_delay)
                    if require_wrapper:
                        pm.regions(force_refresh=True)
                        instance = self._ability_instance_from_data_for_candidate(
                            pm, candidate, data_address, rawcode,
                        )
                    elif self._find_engine_ability_data(pm, candidate, rawcode) == data_address:
                        instance = self._ability_data_instance_for_candidate(
                            pm, candidate, data_address, rawcode,
                        )
                    if instance is not None:
                        break
            if instance is None and not native_path:
                current_instances = self._ability_instances_from_candidate(
                    pm,
                    candidate,
                    required_rawcodes={rawcode},
                    allow_global_scan=True,
                )
                matching_instances = [
                    item for item in current_instances
                    if item.data_address == data_address and item.rawcode == rawcode
                ]
                if len(matching_instances) == 1:
                    instance = matching_instances[0]
            if instance is None:
                create_error = (
                    f"引擎创建了 {format_rawcode(rawcode)}，"
                    "但未能反查到当前单位上的运行时实例"
                )
                raise RuntimeError(create_error)
        except Exception as create_exc:
            try:
                if native_path:
                    candidate = self._refresh_native_candidate(candidate)
                self._remove_engine_ability_instance(pm, candidate, data_address)
            except Exception as cleanup_exc:
                raise RuntimeError(
                    f"{create_exc}；回滚创建实例失败：{cleanup_exc}"
                ) from create_exc
            raise
        return instance, True


    def _temporary_engine_ability_template(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        rawcode: int,
    ) -> tuple[dict[str, object], str]:
        instance, created = self._create_engine_ability_instance(
            pm,
            candidate,
            rawcode,
            refresh_after_add=False,
        )
        try:
            template = self._ability_runtime_template_from_instance(pm, instance)
            source = (
                f"engine-created wrapper=0x{instance.wrapper_address:x} "
                f"class={instance.class_text}"
            )
        finally:
            if created:
                self._remove_engine_ability_instance(pm, candidate, instance.data_address)
        return template, source


    def _replace_engine_ability_instance(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        old_instance: AbilityInstance,
        new_rawcode: int,
    ) -> AbilityInstance:
        new_instance, created = self._create_engine_ability_instance(
            pm,
            candidate,
            new_rawcode,
            refresh_after_add=False,
        )
        if not created:
            raise RuntimeError(
                f"当前单位已存在 {format_rawcode(new_rawcode)}，不能作为新的替换实例"
            )
        if new_instance.data_address == old_instance.data_address:
            raise RuntimeError(
                f"引擎返回的新技能实例与旧实例相同：0x{new_instance.data_address:x}"
            )
        try:
            self._remove_engine_ability_instance(pm, candidate, old_instance.data_address)
        except Exception:
            try:
                self._remove_engine_ability_instance(pm, candidate, new_instance.data_address)
            except Exception:
                pass
            raise

        time.sleep(0.05)
        active_data = self._find_engine_ability_data(pm, candidate, new_rawcode)
        if not active_data:
            raise RuntimeError(f"引擎替换后找不到 {format_rawcode(new_rawcode)} 运行时实例")
        final_instance = self._ability_instance_from_data_for_candidate(
            pm,
            candidate,
            active_data,
            new_rawcode,
        )
        if final_instance is None:
            current_instances = self._ability_instances_from_candidate(
                pm,
                candidate,
                required_rawcodes={new_rawcode},
                allow_global_scan=True,
            )
            if len(current_instances) == 1:
                final_instance = current_instances[0]
        if final_instance is None:
            raise RuntimeError(
                f"引擎替换了 {format_rawcode(new_rawcode)}，但未能反查到当前单位上的运行时实例"
            )
        return replace(final_instance, slot=old_instance.slot)


    def _find_engine_ability_data(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        rawcode: int,
    ) -> int:
        internals = self._discover_native_ability_internals(pm)
        results = self._run_internal_ability_ops(
            candidate,
            (
                (self.NATIVE_HELPER_OP_INTERNAL_ABILITY_FIND, rawcode, internals.find_address, 0, 0),
            ),
        )
        return results[0].result if results else 0


    def _remove_engine_ability_instance(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        data_address: int,
    ) -> None:
        if not data_address:
            return
        try:
            rawcode = pm.read_u32(data_address + 0x70)
        except OSError as exc:
            raise RuntimeError(
                f"临时 ability 实例已不可读，停止内部删除：0x{data_address:x}"
            ) from exc
        if not rawcode:
            raise RuntimeError(f"临时 ability 实例 rawcode 无效：0x{data_address:x}")
        internals = self._discover_native_ability_internals(pm)
        self._run_internal_ability_ops(
            candidate,
            (
                (
                    self.NATIVE_HELPER_OP_INTERNAL_ABILITY_REMOVE,
                    rawcode,
                    internals.remove_address,
                    data_address,
                    internals.find_address,
                ),
                (
                    self.NATIVE_HELPER_OP_INTERNAL_ABILITY_REFRESH,
                    0,
                    internals.refresh_address,
                    0,
                    0,
                ),
            ),
        )
        time.sleep(0.05)
        found = self._find_engine_ability_data(pm, candidate, rawcode)
        if found == data_address:
            raise RuntimeError(f"临时 ability 实例仍挂在当前单位上：0x{data_address:x}")


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


    @staticmethod
    def _native_result_i32(result: int) -> int:
        value = result & 0xFFFFFFFF
        if value & 0x80000000:
            value -= 0x100000000
        return value


    def _get_hero_intelligence_via_native_internal(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        include_bonus: bool,
    ) -> int:
        _set_address, get_address = self._discover_native_hero_int_internals(pm)
        results = self._run_native_helper_ops(
            candidate.unit_address,
            (
                (
                    self.NATIVE_HELPER_OP_GET_HERO_INT,
                    0,
                    get_address,
                    1 if include_bonus else 0,
                    0,
                ),
            ),
        )
        return self._native_result_i32(results[0].result)


    def _get_hero_intelligence_pair_via_native_internal(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
    ) -> tuple[int, int]:
        _set_address, get_address = self._discover_native_hero_int_internals(pm)
        results = self._run_native_helper_ops(
            candidate.unit_address,
            (
                (self.NATIVE_HELPER_OP_GET_HERO_INT, 0, get_address, 0, 0),
                (self.NATIVE_HELPER_OP_GET_HERO_INT, 0, get_address, 1, 0),
            ),
        )
        return self._native_result_i32(results[0].result), self._native_result_i32(results[1].result)


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


    def _resolve_jass_unit_handle_win10(
        self,
        pm: ProcessMemory,
        unit_handle: int,
        *,
        allow_missing: bool = False,
    ) -> int:
        if not unit_handle:
            return 0
        resolver = self._discover_jass_unit_resolver_win10(pm)
        try:
            return int(
                self._run_native_helper_ops(
                    unit_handle,
                    ((self.NATIVE_HELPER_OP_JASS_UNIT_RESOLVE, 0, resolver, 0, 0),),
                )[0].result
            )
        except RuntimeError as exc:
            if allow_missing and (
                f"error={ERROR_NOT_FOUND}" in str(exc)
                or f"last_error={ERROR_NOT_FOUND}" in str(exc)
            ):
                return 0
            raise


    def _get_hero_intelligence_pair_via_jass_win10(
        self,
        pm: ProcessMemory,
        unit_handle: int,
    ) -> tuple[int, int]:
        handlers = self._discover_native_handlers(pm, ("GetHeroInt",))
        get_handler = handlers["GetHeroInt"].handler_address
        results = self._run_native_helper_ops(
            unit_handle,
            (
                (self.NATIVE_HELPER_OP_GET_HERO_INT, 0, get_handler, 0, 0),
                (self.NATIVE_HELPER_OP_GET_HERO_INT, 0, get_handler, 1, 0),
            ),
        )
        return self._native_result_i32(results[0].result), self._native_result_i32(results[1].result)


    def _current_jass_unit_handle_win10(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        diagnostics: Win10ReadLogger,
    ) -> int:
        unit_handle, handle_id, player_handle = self._read_jass_selected_unit_raw_win10(pm)
        resolved_unit = self._resolve_jass_unit_handle_win10(
            pm,
            unit_handle,
            allow_missing=True,
        )
        diagnostics.log(
            "backup_current_selection_check",
            jass_handle=f"0x{unit_handle:x}",
            handle_id=f"0x{handle_id:x}",
            player=f"0x{player_handle:x}",
            resolved_unit=f"0x{resolved_unit:x}",
            expected_unit=f"0x{candidate.unit_address:x}",
        )
        if not resolved_unit or resolved_unit != candidate.unit_address:
            raise RuntimeError("当前选择已经变化，请重新点击备用读取后再写入")
        return unit_handle


    def _replace_win10_intelligence_field(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        fields: list[UnitMemoryField],
        diagnostics: Win10ReadLogger,
    ) -> list[UnitMemoryField]:
        if self._native_snapshot_for_candidate(candidate) is not None:
            return fields
        index = next(
            (index for index, field in enumerate(fields) if field.key == "intelligence_total"),
            None,
        )
        if index is None:
            return fields
        field = fields[index]
        try:
            unit_handle = self._current_jass_unit_handle_win10(pm, candidate, diagnostics)
            base_value, total_value = self._get_hero_intelligence_pair_via_jass_win10(
                pm,
                unit_handle,
            )
        except Exception as exc:
            diagnostics.log("backup_intelligence_read_fallback", exception=repr(exc))
            return fields
        updated = list(fields)
        updated[index] = replace(
            field,
            value_type="i32",
            value=total_value,
            note=(
                "备用读取通过 JASS GetHeroInt 获取真实总智力；"
                f"基础智力={base_value}"
            ),
        )
        diagnostics.log(
            "backup_intelligence_read",
            base=base_value,
            total=total_value,
            unit=f"0x{candidate.unit_address:x}",
        )
        return updated


    def _write_hero_intelligence_field_win10(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        field: UnitMemoryField,
        value: int | float | str,
        diagnostics: Win10ReadLogger,
    ) -> UnitMemoryField:
        if self._native_snapshot_for_candidate(candidate) is not None:
            return self._write_hero_intelligence_field(pm, candidate, field, value)
        target_total = self._coerce_hero_intelligence_target(value)
        unit_handle = self._current_jass_unit_handle_win10(pm, candidate, diagnostics)
        handlers = self._discover_native_handlers(pm, ("SetHeroInt", "GetHeroInt"))
        set_handler = handlers["SetHeroInt"].handler_address
        current_base, current_total = self._get_hero_intelligence_pair_via_jass_win10(
            pm,
            unit_handle,
        )
        current_bonus = current_total - current_base
        target_base = target_total - current_bonus
        if target_base < 0:
            raise ValueError(f"目标智力低于当前加成 {current_bonus}，无法保持加成并写成该总值")

        def set_base(base_value: int) -> None:
            self._run_native_helper_ops(
                unit_handle,
                (
                    (
                        self.NATIVE_HELPER_OP_JASS_UNIT_INT_BOOL,
                        base_value & 0xFFFFFFFF,
                        set_handler,
                        1,
                        0,
                    ),
                ),
            )

        set_base(target_base)
        time.sleep(0.05)
        final_base, final_total = self._get_hero_intelligence_pair_via_jass_win10(
            pm,
            unit_handle,
        )
        if final_total != target_total:
            corrected_base = final_base + (target_total - final_total)
            if corrected_base < 0:
                raise RuntimeError(
                    f"备用 SetHeroInt 写入后总智力={final_total}，无法修正到目标 {target_total}"
                )
            set_base(corrected_base)
            time.sleep(0.05)
            final_base, final_total = self._get_hero_intelligence_pair_via_jass_win10(
                pm,
                unit_handle,
            )
        if final_total != target_total:
            raise RuntimeError(f"备用 SetHeroInt 写入后总智力={final_total}，目标={target_total}")
        diagnostics.log(
            "backup_intelligence_write",
            current_base=current_base,
            current_total=current_total,
            target_total=target_total,
            final_base=final_base,
            final_total=final_total,
            bonus=current_bonus,
        )
        return replace(
            field,
            value_type="i32",
            value=final_total,
            note=(
                f"备用 JASS SetHeroInt 已写入；总智力 {current_total}->{final_total}，"
                f"基础智力 {current_base}->{final_base}，当前加成 {current_bonus}"
            ),
        )


    @staticmethod
    def _coerce_hero_intelligence_target(value: int | float | str) -> int:
        try:
            numeric = float(str(value).strip()) if isinstance(value, str) else float(value)
        except ValueError as exc:
            raise ValueError("目标智力必须是整数") from exc
        if not math.isfinite(numeric) or numeric != int(numeric):
            raise ValueError("目标智力必须是整数")
        target = int(numeric)
        if not 0 <= target <= 1000000:
            raise ValueError("目标智力必须在 0 到 1000000 之间")
        return target


    def _write_hero_intelligence_field(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        field: UnitMemoryField,
        value: int | float | str,
    ) -> UnitMemoryField:
        native = self._native_snapshot_for_candidate(candidate)
        if native is not None:
            target_total = self._coerce_hero_intelligence_target(value)
            identity = field.native_component_identity
            if not all(identity):
                raise RuntimeError("Native intelligence write requires a bound hero component")
            results = self._run_native_helper_ops(native.handle, (
                (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0, candidate.unit_address,
                 candidate.handle, candidate.owner_address),
                (self.NATIVE_HELPER_OP_SET_BOUND_HERO_INT, target_total, *identity, 0),
            ))
            if (len(results) != 2 or any(result.last_error for result in results)
                    or results[1].result != target_total):
                raise RuntimeError("Native intelligence readback differs from request")
            return replace(field, value_type="i32", value=target_total, native_write=True,
                           write_address=0, write_type="",
                           note=field.note + "；本次总智力写入已由游戏接口读回确认")
        if getattr(self, "_native_selection_unavailable", False):
            components = self._selected_components(pm, candidate.owner_address)
            hero = components.get("hero")
            if hero is None:
                raise RuntimeError("当前选中单位没有英雄组件，不能写入智力")
            target_total = self._coerce_hero_intelligence_target(value)
            address = hero[1] + 0x118
            pm.write_f32(address, float(target_total))
            actual = int(round(pm.read_f32(address)))
            if actual != target_total:
                raise RuntimeError(f"3.0 智力写入读回 {actual}，不是 {target_total}")
            return replace(field, value=float(actual), write_address=address,
                           write_type="f32", note="3.0 hero component intelligence field readback verified")
        if not candidate.unit_address:
            raise RuntimeError("当前单位缺少运行时 unit 指针，不能调用内部 SetHeroInt")
        target_total = self._coerce_hero_intelligence_target(value)
        set_address, _get_address = self._discover_native_hero_int_internals(pm)
        current_base, current_total = self._get_hero_intelligence_pair_via_native_internal(pm, candidate)
        current_bonus = current_total - current_base
        target_base = target_total - current_bonus
        if target_base < 0:
            raise ValueError(f"目标智力低于当前加成 {current_bonus}，无法保持加成并写成该总值")

        def set_base(base_value: int) -> None:
            self._run_native_helper_ops(
                candidate.unit_address,
                (
                    (
                        self.NATIVE_HELPER_OP_SET_HERO_INT,
                        base_value & 0xFFFFFFFF,
                        set_address,
                        1,
                        0,
                    ),
                ),
            )

        set_base(target_base)
        time.sleep(0.05)
        final_base, final_total = self._get_hero_intelligence_pair_via_native_internal(pm, candidate)
        if final_total != target_total:
            corrected_base = final_base + (target_total - final_total)
            if corrected_base < 0:
                raise RuntimeError(
                    f"内部 SetHeroInt 写入后总智力={final_total}，无法修正到目标 {target_total}"
                )
            set_base(corrected_base)
            time.sleep(0.05)
            final_base, final_total = self._get_hero_intelligence_pair_via_native_internal(pm, candidate)
        if final_total != target_total:
            raise RuntimeError(f"内部 SetHeroInt 写入后总智力={final_total}，目标={target_total}")

        return UnitMemoryField(
            key=field.key,
            label=field.label,
            value_type=field.value_type,
            value=float(final_total) if field.value_type == "f32" else final_total,
            address=field.address,
            category=field.category,
            write_address=field.write_address,
            write_type=field.write_type,
            write_base=field.write_base,
            note=(
                f"内部 SetHeroInt 已写入；总智力 {current_total}->{final_total}，"
                f"基础智力 {current_base}->{final_base}，当前加成 {current_bonus}"
            ),
            extra_writes=field.extra_writes,
        )
