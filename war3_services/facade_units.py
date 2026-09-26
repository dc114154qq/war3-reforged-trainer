"""units compatibility API; host primitives are explicitly bound once at composition."""
from __future__ import annotations
from contextlib import contextmanager

class UnitsFacade:
    def get_selected_hero_level(self) -> int:
        if getattr(self, "_native_selection_unavailable", False):
            result = self.hero_progress_24268()
            rows = tuple(result.get("rows", ()))
            if not rows:
                raise RuntimeError("当前选中单位中没有可读取的英雄")
            return int(rows[0]["after"])
        return self._query_elephant_unit_int("GetHeroLevel") & 0xFFFFFFFF


    def set_selected_hero_level(self, level: int) -> int:
        target = int(level)
        if not 1 <= target <= 100000:
            raise ValueError("英雄等级必须在 1 到 100000 之间")
        if getattr(self, "_native_selection_unavailable", False):
            self.hero_progress_24268(target)
            return target
        self._run_bound_hero_progress(self.NATIVE_HELPER_OP_SET_BOUND_HERO_LEVEL, target)
        return target


    def _run_bound_hero_progress(self, kind: int, value: int) -> None:
        candidate, unit_handle = self._direct_selected_context()
        results = self._run_native_helper_ops(unit_handle, (
            (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0, candidate.unit_address,
             candidate.handle, candidate.owner_address), (kind, value, 0, 0, 0)))
        if (len(results) != 2 or any(result.last_error for result in results)
                or results[1].kind != kind or results[1].result != value):
            raise RuntimeError("Native hero progression readback differs from request")


    def set_selected_unit_invulnerable(self, enabled: bool) -> None:
        if getattr(self, "_native_selection_unavailable", False):
            from war3_unit_action_protocol import ACTION_SET_INVULNERABLE
            return int(self._unit_action_result_24268(ACTION_SET_INVULNERABLE, value=int(bool(enabled)))["count"])
        self._run_elephant_unit_bool("SetUnitInvulnerable", enabled)


    def set_selected_hero_attributes(self, value: int) -> int:
        target = int(value)
        if not 0 <= target <= 1_000_000_000:
            raise ValueError("英雄属性必须在 0 到 1000000000 之间")
        if getattr(self, "_native_selection_unavailable", False):
            result = self.hero_attributes_24268(target)
            if not result.get("rows"):
                raise RuntimeError("当前选中单位中没有英雄")
            return target
        candidate, unit_handle = self._direct_selected_context()
        results = self._run_native_helper_ops(unit_handle, (
            (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0, candidate.unit_address,
             candidate.handle, candidate.owner_address),
            (self.NATIVE_HELPER_OP_SET_BOUND_HERO_ATTRIBUTES, target, 0, 0, 0),
        ))
        if (len(results) != 2 or any(result.last_error for result in results)
                or results[1].kind != self.NATIVE_HELPER_OP_SET_BOUND_HERO_ATTRIBUTES
                or results[1].result != target):
            raise RuntimeError("Native hero attributes readback differs from request")
        return target


    def set_selected_group_hero_attributes(self, value: int) -> int:
        target = int(value)
        if not 0 <= target <= 1_000_000_000:
            raise ValueError("英雄属性必须在 0 到 1000000000 之间")
        if not getattr(self, "_native_selection_unavailable", False):
            return int(bool(self.set_selected_hero_attributes(target)))
        result = self.hero_attributes_24268(target)
        return len(result["rows"])


    def add_selected_hero_skill_points(self, amount: int = 1) -> int:
        delta = int(amount)
        if not 1 <= delta <= 1_000_000:
            raise ValueError("增加技能点数必须在 1 到 1000000 之间")
        if getattr(self, "_native_selection_unavailable", False):
            from war3_unit_action_protocol import ACTION_ADD_SKILL_POINTS
            result = self._unit_action_result_24268(ACTION_ADD_SKILL_POINTS, value=delta)
            return int(result["changed"])
        self._run_bound_hero_progress(self.NATIVE_HELPER_OP_ADD_BOUND_HERO_SKILL_POINTS, delta)
        return delta


    def is_selected_unit_invulnerable(self) -> bool:
        if getattr(self, "_native_selection_unavailable", False):
            from war3_unit_action_protocol import ACTION_QUERY_INVULNERABLE
            return bool(self._unit_action_result_24268(ACTION_QUERY_INVULNERABLE)["rows"][0]["after"])
        return bool(self._query_elephant_unit_int("BlzIsUnitInvulnerable"))


    def set_selected_unit_pathing(self, enabled: bool) -> None:
        if getattr(self, "_native_selection_unavailable", False):
            from war3_unit_action_protocol import ACTION_SET_PATHING
            return int(self._unit_action_result_24268(ACTION_SET_PATHING, value=int(bool(enabled)))["count"])
        self._run_elephant_unit_bool("SetUnitPathing", enabled)


    def set_selected_unit_paused(self, enabled: bool) -> None:
        if getattr(self, "_native_selection_unavailable", False):
            from war3_unit_action_protocol import ACTION_SET_PAUSED
            return int(self._unit_action_result_24268(ACTION_SET_PAUSED, value=int(bool(enabled)))["count"])
        self._run_elephant_unit_bool("PauseUnit", enabled)


    def is_selected_unit_paused(self) -> bool:
        if getattr(self, "_native_selection_unavailable", False):
            from war3_unit_action_protocol import ACTION_QUERY_PAUSED
            return bool(self._unit_action_result_24268(ACTION_QUERY_PAUSED)["rows"][0]["after"])
        return bool(self._query_elephant_unit_int("IsUnitPaused"))


    def _query_elephant_unit_int(self, native_name: str) -> int:
        return self._query_bound_unit_values((native_name,))[0]


    def _query_bound_unit_values(self, names: tuple[str, ...]) -> tuple[int, ...]:
        candidate, unit_handle = self._direct_selected_context()
        handlers = self._query_native_table_handlers(names)
        results = self._run_native_helper_ops(unit_handle, (
            (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0, candidate.unit_address,
             candidate.handle, candidate.owner_address),
            *((self.NATIVE_HELPER_OP_JASS_UNIT_INT_QUERY, 0, handlers[name].handler_address, 0, 0)
              for name in names)))
        if (len(results) != len(names) + 1 or any(result.last_error for result in results)
                or any(result.kind != self.NATIVE_HELPER_OP_JASS_UNIT_INT_QUERY for result in results[1:])):
            raise RuntimeError("Incomplete native unit query result")
        return tuple(int(result.result) for result in results[1:])


    def _run_elephant_unit_bool(self, native_name: str, enabled: bool) -> None:
        self._run_bound_simple_unit_actions(((native_name, bool(enabled)),))


    def _run_elephant_unit_void(self, native_name: str) -> None:
        self._run_bound_simple_unit_actions(((native_name, None),))


    def _run_bound_simple_unit_actions(self, actions: tuple[tuple[str, bool | None], ...]) -> None:
        candidate, unit_handle = self._direct_selected_context()
        handlers = self._query_native_table_handlers(name for name, _value in actions)
        ops = tuple((self.NATIVE_HELPER_OP_JASS_UNIT_VOID if value is None else self.NATIVE_HELPER_OP_JASS_UNIT_BOOL,
                     0 if value is None else int(value), handlers[name].handler_address, 0, 0)
                    for name, value in actions)
        results = self._run_native_helper_ops(unit_handle, (
            (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0, candidate.unit_address,
             candidate.handle, candidate.owner_address), *ops))
        if len(results) != len(ops) + 1 or any(result.last_error for result in results):
            raise RuntimeError("Incomplete native unit action result")
        for op, result in zip(ops, results[1:]):
            expected = 1 if op[0] == self.NATIVE_HELPER_OP_JASS_UNIT_VOID else op[1]
            if result.kind != op[0] or result.result != expected:
                raise RuntimeError("Native unit action result differs from request")


    def reset_selected_unit_cooldown(self) -> None:
        if getattr(self, "_native_selection_unavailable", False):
            from war3_unit_action_protocol import ACTION_RESET_COOLDOWN
            return int(self._unit_action_result_24268(ACTION_RESET_COOLDOWN)["count"])
        self._run_elephant_unit_void("UnitResetCooldown")


    def kill_selected_unit(self) -> None:
        if getattr(self, "_native_selection_unavailable", False):
            from war3_unit_action_protocol import ACTION_KILL
            return int(self._unit_action_result_24268(ACTION_KILL)["count"])
        self._run_elephant_unit_void("KillUnit")


    def remove_selected_unit(self) -> None:
        if getattr(self, "_native_selection_unavailable", False):
            from war3_unit_action_protocol import ACTION_REMOVE
            return int(self._unit_action_result_24268(ACTION_REMOVE)["count"])
        self._run_elephant_unit_void("RemoveUnit")


    def explode_selected_unit(self) -> None:
        if getattr(self, "_native_selection_unavailable", False):
            from war3_unit_action_protocol import ACTION_EXPLODE
            return int(self._unit_action_result_24268(ACTION_EXPLODE)["count"])
        self._run_bound_simple_unit_actions((("SetUnitExploded", True), ("KillUnit", None)))


    def set_selected_unit_scale(self, scale: float) -> float:
        target = float(scale)
        if not 0.01 <= target <= 100.0:
            raise ValueError("单位大小必须在 0.01 到 100 之间")
        target = coerce_finite_float32(target)
        if getattr(self, "_native_selection_unavailable", False):
            candidate, _handle = self._direct_selected_context()
            with self._process_memory(write=True) as memory:
                from war3_object_registry import ObjectRegistry24268
                registry = self._classic_object_registry or ObjectRegistry24268.attach(memory)
                self._classic_object_registry = registry
                identity = (candidate.handle, candidate.owner_address)

                def check_identity():
                    if registry.resolve_unit(memory, candidate.unit_address) != identity:
                        raise RuntimeError("3.0 scale unit identity changed")

                check_identity()
                address = candidate.unit_address + 0x290
                current = memory.read_f32(address)
                if not math.isfinite(current) or current <= 0:
                    raise RuntimeError("3.0 scale field is invalid")
                check_identity()
                memory.write_f32(address, target)
                actual = memory.read_f32(address)
                check_identity()
                if not math.isfinite(actual) or actual != target:
                    raise RuntimeError("3.0 scale readback differs from request")
            return actual
        expected = self._float_bits(target)
        result = self._run_bound_unit_value_action("SetUnitScale", self.NATIVE_HELPER_OP_JASS_UNIT_SCALE, expected)
        if result != expected:
            raise RuntimeError("Native scale acknowledgment differs from request")
        return target


    def set_selected_group_scale(self, scale: float) -> int:
        target = float(scale)
        if not 0.01 <= target <= 100.0:
            raise ValueError("单位大小必须在 0.01 到 100 之间")
        target = coerce_finite_float32(target)
        if getattr(self, "_native_selection_unavailable", False):
            from war3_unit_action_protocol import ACTION_SET_SCALE
            bits = self._float_bits(target)
            return int(self._unit_action_result_24268(
                ACTION_SET_SCALE,
                scale_x_bits=bits, scale_y_bits=bits, scale_z_bits=bits,
            )["changed"])
        return sum(bool(self.set_selected_unit_scale(target)) for _ in (0,))


    def _run_bound_unit_value_action(self, name: str, kind: int, rawcode: int, arg0: int = 0) -> int:
        candidate, unit_handle = self._direct_selected_context()
        handler = self._query_native_table_handlers((name,))[name].handler_address
        return self._run_bound_unit_action_result(candidate, unit_handle, (kind, rawcode, handler, arg0, 0))


    def _run_bound_unit_action_result(
        self, candidate: UnitCandidate, unit_handle: int, operation: tuple[int, int, int, int, int],
    ) -> int:
        results = self._run_native_helper_ops(unit_handle, (
            (self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY, 0, candidate.unit_address,
             candidate.handle, candidate.owner_address), operation))
        if (len(results) != 2 or any(result.last_error for result in results)
                or results[1].kind != operation[0]):
            raise RuntimeError("Incomplete native bound unit action result")
        return int(results[1].result)


    def query_mouse_world_position(self) -> tuple[float, float]:
        if getattr(self, "_native_selection_unavailable", False):
            snapshot = self.camera_snapshot_24268()
            client_size = self._client_size_24268()
            screen_scale = self._screen_scale_24268()
            initial = self._mouse_world_from_camera_24268(
                snapshot, *client_size, screen_scale,
            )
            # Target Z is a good first plane, but it is not always the terrain
            # under the cursor. Refine once through the game terrain native;
            # if the read-only refinement is unavailable, retain the verified
            # camera-plane result instead of blocking movement.
            try:
                point = initial
                # A single plane correction is insufficient on ramps and cliffs:
                # the new XY point can sample a different terrain height. Repeat
                # the ray/terrain intersection until the point stops moving.
                for _ in range(3):
                    terrain_z = self.terrain_height_24268(*point)
                    refined = self._mouse_world_from_camera_24268(
                        snapshot, *client_size, screen_scale, plane_z=terrain_z,
                    )
                    if math.hypot(refined[0] - point[0], refined[1] - point[1]) <= 0.05:
                        return self._clamp_mouse_world_point_24268(refined)
                    point = refined
                return self._clamp_mouse_world_point_24268(point)
            except Exception:
                return self._clamp_mouse_world_point_24268(initial)
        packed = int(self._run_native_helper_ops(
            0,
            ((
                self.NATIVE_HELPER_OP_QUERY_WORLD_POINT,
                0,
                0,
                0,
                0,
            ),),
        )[0].result)
        x = self._float_from_bits(packed)
        y = self._float_from_bits(packed >> 32)
        if not math.isfinite(x) or not math.isfinite(y):
            raise RuntimeError("游戏返回的鼠标世界坐标无效")
        if abs(x) > 1_000_000.0 or abs(y) > 1_000_000.0:
            raise RuntimeError(f"游戏返回的鼠标世界坐标超出范围：({x:g}, {y:g})")
        return x, y


    def set_selected_unit_position(self, x: float, y: float) -> tuple[float, float]:
        target_x = float(x)
        target_y = float(y)
        if not math.isfinite(target_x) or not math.isfinite(target_y):
            raise ValueError("单位坐标必须是有限数值")
        if abs(target_x) > 1_000_000.0 or abs(target_y) > 1_000_000.0:
            raise ValueError("单位坐标超出允许范围")
        result = self.position_batch_24268(
            self._float_bits(target_x), self._float_bits(target_y),
        )
        rows = tuple(result.get("rows", ()))
        if (int(result.get("count", len(rows))) != 1
                or len(rows) != 1
                or int(result.get("completed", -1)) != 1
                or int(result.get("changed", -1)) != 1):
            raise RuntimeError("单选单位引擎瞬移返回不完整")
        actual_x = self._float_from_bits(int(rows[0]["actual_x_bits"]))
        actual_y = self._float_from_bits(int(rows[0]["actual_y_bits"]))
        if not all(math.isfinite(value) for value in (actual_x, actual_y)):
            raise RuntimeError("单选单位引擎瞬移坐标读回无效")
        return actual_x, actual_y


    def move_selected_unit_to_mouse(self) -> tuple[float, float]:
        x, y = self.query_mouse_world_position()
        return self.set_selected_unit_position(x, y)


    def set_selected_group_position(self, x: float, y: float) -> int:
        """Move the current 3.0 selection through the game-thread native ABI.

        Do not write the discovered x/y fields directly.  Those fields can
        make the display move while leaving the engine's pathing/collision
        state stale; the next ordinary movement can then crash the game.
        """
        target_x, target_y = float(x), float(y)
        if not math.isfinite(target_x) or not math.isfinite(target_y):
            raise ValueError("单位坐标必须是有限数值")
        if abs(target_x) > 1_000_000.0 or abs(target_y) > 1_000_000.0:
            raise ValueError("单位坐标超出允许范围")
        result = self.position_batch_24268(
            x_bits=self._float_bits(target_x),
            y_bits=self._float_bits(target_y),
        )
        rows = tuple(result.get("rows", ()))
        count = int(result.get("count", len(rows)))
        completed = int(result.get("completed", -1))
        changed = int(result.get("changed", -1))
        if not rows or count != len(rows) or completed != count or changed != count:
            raise RuntimeError(
                f"引擎瞬移返回不完整：count={count} completed={completed} changed={changed}"
            )
        for row in rows:
            actual_x = self._float_from_bits(int(row["actual_x_bits"]))
            actual_y = self._float_from_bits(int(row["actual_y_bits"]))
            # SetUnitPosition may resolve a multi-unit target through the
            # engine's collision/formation solver. The returned coordinates,
            # rather than the requested common point, are authoritative.
            if not math.isfinite(actual_x) or not math.isfinite(actual_y):
                raise RuntimeError(
                    f"引擎瞬移坐标读回无效：({actual_x:g},{actual_y:g})"
                )
        return count


    def move_selected_group_to_mouse(self) -> tuple[int, float, float]:
        if not getattr(self, "_native_selection_unavailable", False):
            # Preserve the 1.0.19 single-callback path for the legacy trainer.
            handler = self._query_native_table_handlers(("SetUnitPosition",))["SetUnitPosition"].handler_address
            result = self._run_native_helper_ops(0, ((
                self.NATIVE_HELPER_OP_MOVE_SELECTED_GROUP_TO_MOUSE, 0, handler, 0, 0,
            ),))[0]
            return int(result.result), self._float_from_bits(result.arg0), self._float_from_bits(result.arg0 >> 32)

        # Resolve the mouse once, then use one object snapshot and one process
        # handle for the whole selection. No per-unit native callbacks occur.
        x, y = self.query_mouse_world_position()
        count = self.set_selected_group_position(x, y)
        return int(count), x, y


    def _run_direct_selected_ability(
        self,
        rawcode: int | str,
        op_kind: int,
        vtable_offset: int,
        arg1: int,
    ) -> int:
        with self._native_helper_transaction():
            return self._run_direct_selected_ability_locked(
                rawcode,
                op_kind,
                vtable_offset,
                arg1,
            )
