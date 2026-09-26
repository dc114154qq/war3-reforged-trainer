"""native compatibility API; host primitives are explicitly bound once at composition."""
from __future__ import annotations
from contextlib import contextmanager

class NativeFacade:
    def _engine_instance_24268(self):
        from war3_engine_24268 import Engine24268
        engine = getattr(self, "_engine24268", None)
        if engine is None or (engine.pid, engine.hwnd) != (self.pid, self.hwnd):
            if engine is not None:
                try:
                    engine.close()
                except Exception:
                    pass
            engine = Engine24268(self.pid, self.hwnd, ProcessMemory,
                                 report_sink=lambda report: record_engine_recovery(self.pid, report),
                                 session=getattr(self,"_game_session",None))
            self._engine24268 = engine
        return engine


    def hero_progress_24268(self, target: int = 0) -> dict:
        return self._engine_instance_24268().hero_progress(target)


    def hero_attributes_24268(self, target: int) -> dict:
        return self._engine_instance_24268().hero_attributes(target)


    def _unit_stats_for_candidate_24268(self, candidate: UnitCandidate) -> dict:
        result = self._engine_instance_24268().unit_stats()
        rows = [row for row in result.get("rows", ()) if int(row.get("status", 0)) == 1]
        typed = [row for row in rows if int(row.get("rawcode", 0)) == int(candidate.unit_type_id)]
        matches = typed if len(typed) == 1 else rows if len(rows) == 1 else ()
        if len(matches) != 1:
            raise RuntimeError("当前单位原生属性身份不唯一，请只选择一个单位后重试")
        return matches[0]


    def _write_unit_stat_field_24268(
        self, candidate: UnitCandidate, field: UnitMemoryField, value: int | float | str,
    ) -> UnitMemoryField:
        from war3_unit_stats_protocol import (
            ACTION_SET_ARMOR, ACTION_SET_DEFENSE_TYPE, ACTION_SET_INTELLIGENCE,
        )
        action = {
            "armor": ACTION_SET_ARMOR,
            "armor_type": ACTION_SET_DEFENSE_TYPE,
            "intelligence_total": ACTION_SET_INTELLIGENCE,
        }[field.key]
        if field.key == "armor":
            target = coerce_finite_float32(value)
        else:
            target = int(self._coerce_memory_value("i32", value))
        unit, expected_rawcode = field.native_component_identity
        result = self._engine_instance_24268().unit_stats(action, target, int(unit))
        rows = [row for row in result.get("rows", ())
                if int(row.get("status", 0)) == 1 and int(row.get("unit", 0)) == int(unit)]
        if len(rows) != 1 or int(rows[0].get("rawcode", 0)) != int(expected_rawcode):
            raise RuntimeError("单位原生属性写入后的身份读回不一致")
        row = rows[0]
        actual = {
            "armor": row["armor_after"],
            "armor_type": row["defense_after"],
            "intelligence_total": row["intelligence_total_after"],
        }[field.key]
        return replace(field, value=actual, address=0, write_address=0,
                       write_type="", native_write=True)


    def attack_speed_24268(
        self,
        candidate: UnitCandidate,
        attack: int,
        target_aps: float = 0.0,
        weapon: int = 0,
    ) -> dict:
        if not candidate.handle or not candidate.unit_address or not candidate.unit_type_id or not attack:
            raise RuntimeError("3.0 攻速事务缺少完整单位身份")
        return self._engine_instance_24268().attack_speed(
            candidate.unit_address,
            int(attack),
            candidate.handle,
            candidate.unit_type_id,
            float(target_aps),
            int(weapon),
        )


    def ability_batch_24268(self, rawcode: int | str, action: int = 0, level: int = 0, *, target_unit: int = 0) -> dict:
        ability = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        if not ability:
            raise ValueError("技能 ID 无效")
        if target_unit:
            return self._engine_instance_24268().ability_batch(ability, action, level, target_unit=target_unit)
        return self._engine_instance_24268().ability_batch(ability, action, level)


    def ability_field_batch_24268(
        self,
        rawcode: int | str,
        level: int,
        action: int,
        fields: Iterable[tuple[int, int, int, int]],
        target_unit: int = 0,
    ) -> dict:
        ability = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        if not ability:
            raise ValueError("技能 ID 无效")
        return self._engine_instance_24268().ability_field_batch(
            ability, int(level), int(action), tuple(fields), int(target_unit),
        )


    def item_batch_24268(self, action: int = 0, rawcode: int | str = 0, charges: int = -1,
                         target_unit_rawcode: int = 0, target_unit: int = 0,
                         expected_item: int = 0) -> dict:
        code = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF if rawcode else 0
        return self._engine_instance_24268().item_batch(
            action, code, charges, int(target_unit_rawcode) & 0xFFFFFFFF,
            int(target_unit), int(expected_item),
        )


    def _stat_target_24268(self, candidate: UnitCandidate | None = None) -> tuple:
        if candidate is None:
            candidate, unit_handle = self._direct_selected_context()
        else:
            identity = (candidate.handle, candidate.owner_address, candidate.unit_address, candidate.unit_type_id)
            matches = [
                (current, handle) for current, handle in self._selected_candidates_snapshot(None)
                if (current.handle, current.owner_address, current.unit_address, current.unit_type_id) == identity
            ]
            if len(matches) != 1:
                raise RuntimeError("属性目标单位已变化或身份不唯一，请重新读取")
            candidate, unit_handle = matches[0]
        if not candidate.handle or not candidate.unit_type_id:
            raise RuntimeError("3.0 属性读取缺少完整单位身份")
        # Selection candidates use persistent identities, not the native
        # JASS handle namespace. Bind through a read-only native selection.
        native = self._engine_instance_24268().ability_batch(int.from_bytes(b"AIxr", "big"))
        rows = [row for row in native["rows"] if int(row["rawcode"]) == int(candidate.unit_type_id)]
        if len(rows) != 1:
            raise RuntimeError("属性目标的原生身份不唯一，请单选该单位后重试")
        return candidate, int(rows[0]["handle"])


    def item_field_batch_24268(self, slot: int, action: int, fields,
                             target_unit: int = 0) -> dict:
        return self._engine_instance_24268().item_field_batch(
            int(slot), int(action), tuple(fields), int(target_unit),
        )


    def world_batch_24268(self, action: int, rawcode: int | str = 0, value: int = 0) -> dict:
        code = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF if rawcode else 0
        return self._engine_instance_24268().world_batch(action, code, int(value))


    def bulk_batch_24268(self, action: int, value: int = 0) -> dict:
        return self._engine_instance_24268().bulk_batch(int(action), int(value))


    def effect_batch_24268(
        self, rawcode: int | str, action: int, x_bits: int = 0, y_bits: int = 0,
        *, area: float | None = None, passes: int = 1,
    ) -> dict:
        code = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        if not code:
            raise ValueError("技能 ID 无效")
        if isinstance(passes, bool) or not 1 <= int(passes) <= 255:
            raise ValueError("技能效果执行次数必须在 1 到 255 之间")
        area_bits = 0
        if area is not None:
            area_value = float(area)
            if not math.isfinite(area_value) or not 0 <= area_value <= 1_000_000:
                raise ValueError("技能效果范围必须是 0 到 1000000 之间的有限数值")
            area_bits = self._float_bits(area_value)
        return self._engine_instance_24268().effect_batch(
            code, int(action), int(x_bits), int(y_bits),
            area_bits=area_bits, passes=int(passes),
        )


    def world_effect_batch_24268(
        self, rawcode: int | str, action: int, success_limit: int = 0,
    ) -> dict:
        code = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        limit = int(success_limit)
        if not code:
            raise ValueError("技能 ID 无效")
        if not 0 <= limit <= 65535:
            raise ValueError("全屏效果上限必须在 0 到 65535 之间")
        return self._engine_instance_24268().world_effect_batch(code, int(action), limit)


    def cast_native_area_24268(self, rawcode: int | str, order_id: int,
                               *, cast_kind: int = 1, area: float = 100000.0,
                               source: int = 0, hold_seconds: float = 2.0) -> dict:
        code = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        if not code or not 1 <= float(area) <= 100000 or not math.isfinite(float(area)):
            raise ValueError("Invalid native area cast")
        hwnd = int(getattr(self, "hwnd", 0) or 0)
        if hwnd and ctypes.windll.user32.IsIconic(hwnd):
            raise RuntimeError("游戏窗口已最小化；请恢复窗口并解除暂停后再施放全屏技能")
        engine = self._engine_instance_24268()
        started = None
        primary_error = None
        try:
            started = engine.world_cast(code, 1, order_id=int(order_id),
                                        cast_kind=int(cast_kind), area=float(area),
                                        source=int(source))
            time.sleep(float(hold_seconds))
            identity = dict(source=started["source"],
                            ability_handle=started["ability_handle"],
                            target=started["target"], cast_kind=started["cast_kind"],
                            prior_area=started["prior_area"], added=started["added"])
            state = engine.world_cast(code, 3, **identity)
            if (state["source"] != started["source"] or
                    (state["cooldown_after"] <= 0.01 and
                     state["mana_after"] >= started["mana_before"] - 0.01)):
                raise RuntimeError("施法命令已接收，但法力和冷却未变化；请确认游戏未暂停或停在结算界面")
            return dict(start=started, state=state)
        except Exception as exc:
            primary_error = exc
            raise
        finally:
            if started is not None:
                try:
                    engine.world_cast(code, 2, source=started["source"],
                                      ability_handle=started["ability_handle"],
                                      target=started["target"],
                                      cast_kind=started["cast_kind"],
                                      prior_area=started["prior_area"],
                                      added=started["added"])
                except Exception as cleanup_error:
                    raise RuntimeError(
                        f"Native area cast cleanup failed; original={primary_error}; "
                        f"cleanup={cleanup_error}"
                    ) from cleanup_error


    def spawn_unit_24268(
        self, rawcode: int | str, x: float, y: float, facing: float = 0.0,
    ) -> dict:
        code = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        if not code:
            raise ValueError("单位 ID 无效")
        return self._engine_instance_24268().spawn_batch(
            code,
            self._float_bits(float(x)),
            self._float_bits(float(y)),
            self._float_bits(float(facing)),
        )


    def mouse_world_point_24268(self) -> tuple[float, float]:
        result = self._engine_instance_24268().mouse_world_point()
        return float(result["x"]), float(result["y"])


    def mouse_screen_point_24268(self) -> tuple[int, int]:
        result = self._engine_instance_24268().mouse_screen_point()
        return int(result["x"]), int(result["y"])


    def camera_snapshot_24268(self) -> dict:
        return self._engine_instance_24268().camera_snapshot()


    def terrain_height_24268(self, x: float, y: float) -> float:
        result = self._engine_instance_24268().terrain_height(
            self._float_bits(float(x)), self._float_bits(float(y)),
        )
        height = float(result["z"])
        if not math.isfinite(height) or abs(height) > 1_000_000.0:
            raise RuntimeError("3.0 地形高度返回无效")
        return height


    def map_bounds_24268(self) -> dict[str, float]:
        return self._engine_instance_24268().map_bounds()


    def _clamp_mouse_world_point_24268(self, point: tuple[float, float]) -> tuple[float, float]:
        bounds = self.map_bounds_24268()
        margin = 32.0
        min_x = float(bounds["min_x"]) + margin
        max_x = float(bounds["max_x"]) - margin
        min_y = float(bounds["min_y"]) + margin
        max_y = float(bounds["max_y"]) - margin
        if not min_x < max_x or not min_y < max_y:
            raise RuntimeError("当前地图可用范围无效")
        x, y = (float(point[0]), float(point[1]))
        if not all(math.isfinite(value) for value in (x, y)):
            raise RuntimeError("鼠标目标点不是有限坐标")
        return min(max(x, min_x), max_x), min(max(y, min_y), max_y)


    @staticmethod
    def _mouse_world_from_camera_24268(
        snapshot: dict, client_width: int, client_height: int, screen_scale: float = 1.0,
        plane_z: float | None = None,
    ) -> tuple[float, float]:
        if client_width <= 0 or client_height <= 0:
            raise RuntimeError("3.0 游戏客户区尺寸无效")
        target = tuple(float(value) for value in snapshot["target"])
        eye = tuple(float(value) for value in snapshot["eye"])
        screen_x, screen_y = (int(value) for value in snapshot["screen"])
        fields = tuple(float(value) for value in snapshot.get("fields", ()))
        # Warcraft III's CAMERA_FIELD_FIELD_OF_VIEW is index 2. Index 3 is
        # near-Z on the JASS camera-field enum; retain it only for old
        # synthetic snapshots that used the wrong field slot.
        if len(fields) > 2 and 0.1 < fields[2] < math.pi - 0.1:
            fov = fields[2]
        elif len(fields) > 3 and 0.1 < fields[3] < math.pi - 0.1:
            fov = fields[3]
        else:
            fov = math.radians(70.0)
        forward = tuple(target[index] - eye[index] for index in range(3))
        forward_length = math.sqrt(sum(value * value for value in forward))
        if not math.isfinite(forward_length) or forward_length <= 1e-5:
            raise RuntimeError("3.0 相机眼点和目标点重合")
        forward = tuple(value / forward_length for value in forward)
        world_up = (0.0, 0.0, 1.0)
        up_projection = sum(forward[index] * world_up[index] for index in range(3))
        up = tuple(world_up[index] - forward[index] * up_projection for index in range(3))
        up_length = math.sqrt(sum(value * value for value in up))
        if up_length <= 1e-5:
            raise RuntimeError("3.0 相机上方向无效")
        up = tuple(value / up_length for value in up)
        right = (
            forward[1] * up[2] - forward[2] * up[1],
            forward[2] * up[0] - forward[0] * up[2],
            forward[0] * up[1] - forward[1] * up[0],
        )
        aspect = float(client_width) / float(client_height)
        if screen_x > client_width * 2 or screen_y > client_height * 2:
            screen_width = screen_height = 65535.0
        else:
            if not math.isfinite(screen_scale) or not 0.5 <= screen_scale <= 4.0:
                raise RuntimeError("3.0 鼠标 DPI 缩放无效")
            screen_width = client_width * screen_scale
            screen_height = client_height * screen_scale
        ndc_x = (screen_x / screen_width) * 2.0 - 1.0
        ndc_y = 1.0 - (screen_y / screen_height) * 2.0
        spread = math.tan(fov * 0.5)
        direction = tuple(
            forward[index]
            + right[index] * ndc_x * spread * aspect
            + up[index] * ndc_y * spread
            for index in range(3)
        )
        direction_length = math.sqrt(sum(value * value for value in direction))
        direction = tuple(value / direction_length for value in direction)
        if abs(direction[2]) <= 1e-6:
            raise RuntimeError("3.0 鼠标射线没有命中地图平面")
        ground_z = target[2] if plane_z is None else float(plane_z)
        if not math.isfinite(ground_z) or abs(ground_z) > 1_000_000.0:
            raise RuntimeError("3.0 鼠标投影平面高度无效")
        distance = (ground_z - eye[2]) / direction[2]
        if not math.isfinite(distance) or distance <= 0.0:
            raise RuntimeError("3.0 鼠标射线命中点无效")
        x = eye[0] + direction[0] * distance
        y = eye[1] + direction[1] * distance
        if not math.isfinite(x) or not math.isfinite(y) or abs(x) > 1_000_000.0 or abs(y) > 1_000_000.0:
            raise RuntimeError("3.0 鼠标世界坐标超出范围")
        return x, y


    def _client_size_24268(self) -> tuple[int, int]:
        class Rect(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
        get_client_rect = user32.GetClientRect
        get_client_rect.argtypes = (ctypes.c_void_p, ctypes.POINTER(Rect))
        get_client_rect.restype = ctypes.c_bool
        rect = Rect()
        if not get_client_rect(ctypes.c_void_p(self.hwnd), ctypes.byref(rect)):
            raise ctypes.WinError(ctypes.get_last_error())
        width, height = int(rect.right - rect.left), int(rect.bottom - rect.top)
        if width > 0 and height > 0:
            return width, height

        # Some 3.0 render states expose a visible OsWindow with a zero-sized
        # client area while the camera natives still report normalized 16-bit
        # screen coordinates. Do not use its title-bar dimensions as the
        # projection aspect ratio; use a real window size or desktop metrics.
        get_window_rect = user32.GetWindowRect
        get_window_rect.argtypes = (ctypes.c_void_p, ctypes.POINTER(Rect))
        get_window_rect.restype = ctypes.c_bool
        window_rect = Rect()
        if get_window_rect(ctypes.c_void_p(self.hwnd), ctypes.byref(window_rect)):
            width = int(window_rect.right - window_rect.left)
            height = int(window_rect.bottom - window_rect.top)
            if width >= 320 and height >= 200:
                return width, height

        get_system_metrics = user32.GetSystemMetrics
        get_system_metrics.argtypes = (ctypes.c_int,)
        get_system_metrics.restype = ctypes.c_int
        width = int(get_system_metrics(0))
        height = int(get_system_metrics(1))
        if width > 0 and height > 0:
            return width, height
        raise RuntimeError("3.0 游戏客户区尺寸无效")


    def _screen_scale_24268(self) -> float:
        get_dpi_for_window = user32.GetDpiForWindow
        get_dpi_for_window.argtypes = (ctypes.c_void_p,)
        get_dpi_for_window.restype = ctypes.c_uint
        dpi = int(get_dpi_for_window(ctypes.c_void_p(self.hwnd)))
        return (dpi or 96) / 96.0


    def clone_batch_24268(self, *, keep: bool = True,
                          preserve_owner: bool = False,
                          copy_abilities: bool = True,
                          copy_items: bool = True,
                          spawn: bool = False,
                          spawn_x_bits: int = 0,
                          spawn_y_bits: int = 0) -> dict:
        return self._engine_instance_24268().clone_batch(
            keep=keep,
            preserve_owner=preserve_owner,
            copy_abilities=copy_abilities,
            copy_items=copy_items,
            spawn=spawn,
            spawn_x_bits=spawn_x_bits,
            spawn_y_bits=spawn_y_bits,
        )


    def unit_action_batch_24268(self, action: int, *, value: int = 0,
                                x_bits: int = 0, y_bits: int = 0,
                                scale_x_bits: int = 0, scale_y_bits: int = 0,
                                scale_z_bits: int = 0) -> dict:
        return self._engine_instance_24268().unit_action_batch(
            action, value=value, x_bits=x_bits, y_bits=y_bits,
            scale_x_bits=scale_x_bits, scale_y_bits=scale_y_bits,
            scale_z_bits=scale_z_bits,
        )


    def position_batch_24268(self, x_bits: int, y_bits: int) -> dict:
        return self._engine_instance_24268().position_batch(x_bits, y_bits)


    def _unit_action_result_24268(self, action: int, *, value: int = 0,
                                   x_bits: int = 0, y_bits: int = 0,
                                   scale_x_bits: int = 0, scale_y_bits: int = 0,
                                   scale_z_bits: int = 0) -> dict:
        result = self.unit_action_batch_24268(
            action, value=value, x_bits=x_bits, y_bits=y_bits,
            scale_x_bits=scale_x_bits, scale_y_bits=scale_y_bits,
            scale_z_bits=scale_z_bits,
        )
        if not result.get("rows"):
            raise RuntimeError("当前选择没有可操作单位")
        return result
