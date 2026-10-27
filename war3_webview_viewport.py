"""Pure-Python WebStateViewPort implementing ViewPort contract without Tkinter."""
from __future__ import annotations

import threading
import logging
from typing import Any, Callable
from war3_view_contract import ViewPort, ViewControl
from war3_ui_i18n import detect_ui_language, translate_ui_text


class ObservableVar:
    """Observable variable compatible with Tkinter StringVar / BooleanVar."""

    def __init__(self, value: Any = "", on_change: Callable[[Any], None] | None = None):
        self._value = value
        self._on_change = on_change
        self._trace_callbacks: list[Callable[..., Any]] = []

    def get(self) -> Any:
        return self._value

    def set(self, value: Any) -> None:
        self._value = value
        if self._on_change:
            try:
                self._on_change(value)
            except Exception:
                pass
        for cb in self._trace_callbacks:
            try:
                cb(None, None, "write")
            except Exception:
                pass

    def trace_add(self, mode: str, callback: Callable[..., Any]) -> str:
        self._trace_callbacks.append(callback)
        return str(id(callback))

    def __str__(self) -> str:
        return str(self._value)

    def __repr__(self) -> str:
        return f"ObservableVar({self._value!r})"


class LocalizedObservableVar(ObservableVar):
    """Observable variable that stores raw key and returns translated text."""

    def __init__(self, value: str = "", get_language: Callable[[], str] = lambda: "zh"):
        self._source_text = str(value)
        self._get_language = get_language
        super().__init__(self._translated())

    def _translated(self) -> str:
        return translate_ui_text(self._source_text, self._get_language())

    def get(self) -> str:
        return self._translated()

    def set(self, value: Any) -> None:
        self._source_text = "" if value is None else str(value)
        super().set(self._translated())

    def refresh(self) -> None:
        super().set(self._translated())

    def source_text(self) -> str:
        return self._source_text


class VirtualTree:
    """Virtual treeview table that mimics ttk.Treeview data methods."""

    def __init__(self, columns: tuple[str, ...] = ()):
        self.columns = columns
        self.rows: dict[str, tuple[Any, ...]] = {}  # iid -> values
        self.order: list[str] = []
        self._selection: list[str] = []
        self._headings: dict[str, str] = {}
        self._column_widths: dict[str, int] = {}
        self._lock = threading.RLock()

    def get_children(self, item: str = "") -> tuple[str, ...]:
        with self._lock:
            return tuple(self.order)

    def delete(self, *items: str) -> None:
        with self._lock:
            if not items:
                return
            for item in items:
                self.rows.pop(item, None)
                if item in self.order:
                    self.order.remove(item)
                if item in self._selection:
                    self._selection.remove(item)

    def insert(self, parent: str, index: Any, iid: str | None = None, values: tuple[Any, ...] = ()) -> str:
        with self._lock:
            if iid is None:
                iid = f"row_{len(self.order) + 1}_{id(values)}"
            self.rows[iid] = tuple(values)
            if iid not in self.order:
                if index == "end":
                    self.order.append(iid)
                elif isinstance(index, int):
                    self.order.insert(index, iid)
                else:
                    self.order.append(iid)
            return iid

    def exists(self, iid: str) -> bool:
        with self._lock:
            return iid in self.rows

    def item(self, iid: str, option: str | None = None, **kwargs) -> Any:
        with self._lock:
            if "values" in kwargs:
                self.rows[iid] = tuple(kwargs["values"])
            res = {"values": self.rows.get(iid, ())}
            if option == "values":
                return res["values"]
            return res

    def selection(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._selection)

    def selection_set(self, *items: Any) -> None:
        with self._lock:
            flat = []
            for item in items:
                if isinstance(item, (list, tuple)):
                    flat.extend(item)
                else:
                    flat.append(item)
            self._selection = [i for i in flat if i in self.rows]

    def focus(self, iid: str = "") -> str:
        return iid

    def heading(self, column: str, text: str = "", **kwargs) -> str:
        with self._lock:
            if text:
                self._headings[column] = text
            return self._headings.get(column, column)

    def column(self, column: str, width: int = 0, **kwargs) -> None:
        with self._lock:
            if width:
                self._column_widths[column] = width

    def see(self, iid: str) -> None:
        pass

    def to_list_of_dicts(self) -> list[dict[str, Any]]:
        with self._lock:
            result = []
            for iid in self.order:
                val = self.rows.get(iid, ())
                row_dict = {"_iid": iid}
                for idx, col in enumerate(self.columns):
                    row_dict[col] = val[idx] if idx < len(val) else ""
                result.append(row_dict)
            return result


class VirtualControl:
    """Virtual button or widget control."""

    def __init__(self, name: str = ""):
        self.name = name
        self._state: set[str] = set()

    def state(self, states: list[str] | tuple[str, ...]) -> None:
        for s in states:
            if s.startswith("!"):
                self._state.discard(s[1:])
            else:
                self._state.add(s)

    def is_disabled(self) -> bool:
        return "disabled" in self._state

    def configure(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __getitem__(self, key):
        return getattr(self, key)


class WebStateViewPort:
    """Complete implementation of ViewPort without Tkinter."""

    def __init__(self, services: Any, initial_pid: int | None = None, initial_hotkeys_enabled: bool = False):
        self.services = services
        self._values: dict[str, Any] = {}
        self._closed = False
        self.dispatch_lock = threading.RLock()
        self.window = None
        self.dialog_error = None
        self._notice_lock = threading.Lock()
        self._notices = []
        self._notice_sequence = 0
        self.cancelled = False
        self._timers = set()
        self.on_destroy = None
        self._init_ports(initial_pid, initial_hotkeys_enabled)

    def _init_ports(self, initial_pid: int | None, initial_hotkeys_enabled: bool) -> None:
        ui_lang = {"code": detect_ui_language()}

        def ui_text(text: object) -> str:
            return translate_ui_text(text, ui_lang["code"])

        self._values["ui_language"] = ui_lang
        self._values["ui_text"] = ui_text

        # Core scalar variables
        self._values["status"] = LocalizedObservableVar("正在连接 Warcraft III...", lambda: ui_lang["code"])
        self._values["pid_var"] = ObservableVar(str(initial_pid) if initial_pid is not None else "")
        self._values["gold_current"] = ObservableVar("")
        self._values["lumber_current"] = ObservableVar("")
        self._values["food_current"] = ObservableVar("")
        self._values["food_cap_current"] = ObservableVar("")
        self._values["gold_target"] = ObservableVar("")
        self._values["lumber_target"] = ObservableVar("")
        self._values["food_used_target"] = ObservableVar("")
        self._values["food_cap_target"] = ObservableVar("")
        self._values["resource_delta"] = ObservableVar("1000")

        self._values["hp_current"] = ObservableVar("")
        self._values["hp_max_current"] = ObservableVar("")
        self._values["hp_regen_current"] = ObservableVar("")
        self._values["mp_current"] = ObservableVar("")
        self._values["mp_max_current"] = ObservableVar("")
        self._values["mp_regen_current"] = ObservableVar("")
        self._values["hp_target"] = ObservableVar("")
        self._values["mp_target"] = ObservableVar("")
        self._values["hp_regen_target"] = ObservableVar("")
        self._values["mp_regen_target"] = ObservableVar("")
        self._values["x_current"] = ObservableVar("")
        self._values["y_current"] = ObservableVar("")
        self._values["unit_type_id_current"] = ObservableVar("")
        self._values["x_target"] = ObservableVar("")
        self._values["y_target"] = ObservableVar("")
        self._values["unit_field_target"] = ObservableVar("")

        # Elephant parameter variables
        self._values["elephant_hero_level"] = ObservableVar("1")
        self._values["elephant_unit_scale"] = ObservableVar("1.0")
        self._values["elephant_unit_rawcode"] = ObservableVar("")
        self._values["elephant_item_rawcode"] = ObservableVar("ckng")
        self._values["elephant_ability_rawcode"] = ObservableVar("AOsh")
        self._values["elephant_ability_level"] = ObservableVar("1")
        self._values["elephant_tech_rawcode"] = ObservableVar("")
        self._values["elephant_tech_level"] = ObservableVar("1")
        self._values["elephant_xp_rate"] = ObservableVar("1.0")
        self._values["elephant_game_speed"] = ObservableVar("2")
        self._values["elephant_item_charges"] = ObservableVar("999")
        self._values["elephant_resource_amount"] = ObservableVar("100000")
        self._values["elephant_mass_clone_count"] = ObservableVar("10")
        self._values["elephant_hero_attributes"] = ObservableVar("20000")
        self._values["elephant_skill_points"] = ObservableVar("1")
        self._values["elephant_reinforcement_rawcode"] = ObservableVar("hcth")
        self._values["elephant_preset_item_rawcode"] = ObservableVar("amrc")
        self._values["elephant_preset_tech_rawcode"] = ObservableVar("Rost")
        self._values["elephant_reset_ability_rawcode"] = ObservableVar("Apxf")
        self._values["elephant_auto_effect_count"] = ObservableVar("5")

        # 17 Stat Detail Specifications
        from war3_3_stats import STAT_DETAIL_SPECS
        stat_vars = {
            "hp_regen": ObservableVar("0"),
            "mp_regen": ObservableVar("0"),
            "attack_speed": ObservableVar("1"),
            **{spec.key: ObservableVar("150" if spec.baseline else "0") for spec in STAT_DETAIL_SPECS}
        }
        self._values["elephant_stat_values"] = stat_vars

        # Hotkeys
        hotkey_specs = self.services.hotkeys
        self._values["hotkey_specs_by_name"] = {spec.name: spec for spec in hotkey_specs}
        self._values["elephant_hotkeys_enabled"] = ObservableVar(initial_hotkeys_enabled)
        self._values["elephant_hotkey_status"] = LocalizedObservableVar("快捷键未启用" if not initial_hotkeys_enabled else "快捷键已就绪", lambda: ui_lang["code"])
        hotkey_dangerous = {"explode_unit", "drop_inventory", "kill_owner_units", "end_game", "remove_all_abilities", "instant_victory"}
        self._values["elephant_hotkey_checks"] = {
            spec.name: ObservableVar(spec.name not in hotkey_dangerous) for spec in hotkey_specs
        }
        self._values["hotkey_manager"] = self.services.hotkey_manager()
        self._values["hotkey_callbacks"] = {}

        # Ability fields
        self._values["ability_field_rawcode"] = ObservableVar("AHhb")
        self._values["ability_field_level"] = ObservableVar("1")
        self._values["ability_field_filter"] = ObservableVar("")
        self._values["ability_field_value"] = ObservableVar("")
        self._values["ability_field_summary"] = LocalizedObservableVar("尚未读取技能字段", lambda: ui_lang["code"])
        self._values["ability_field_detail"] = LocalizedObservableVar("", lambda: ui_lang["code"])
        self._values["ability_field_show_zero"] = ObservableVar(True)
        self._values["ability_field_show_unsupported"] = ObservableVar(True)

        # Item fields
        self._values["item_field_slot"] = ObservableVar("1")
        self._values["item_field_filter"] = ObservableVar("")
        self._values["item_field_value"] = ObservableVar("")
        self._values["item_field_summary"] = LocalizedObservableVar("尚未读取物品字段", lambda: ui_lang["code"])
        self._values["item_field_detail"] = LocalizedObservableVar("", lambda: ui_lang["code"])
        self._values["item_field_show_zero"] = ObservableVar(True)
        self._values["item_field_show_unsupported"] = ObservableVar(True)

        # 3.0 Extensions
        from war3_3_extension_catalog import OFFICIAL_BACKPACKS
        self._values["official_backpack_by_label"] = {
            f"{hero_name} ({rawcode})": rawcode for rawcode, (hero_name, _) in OFFICIAL_BACKPACKS.items()
        }
        self._values["extension_item_rawcode"] = ObservableVar("")
        self._values["extension_item_charges"] = ObservableVar("1")
        self._values["extension_backpack_choice"] = ObservableVar("亡灵加雷克 (ebug)")
        self._values["extension_loadout_name"] = ObservableVar("套装1")
        self._values["extension_loadout_choice"] = ObservableVar("")
        self._values["extension_talent_choice"] = ObservableVar("")
        self._values["extension_status"] = LocalizedObservableVar("尚未读取 3.0 扩展状态", lambda: ui_lang["code"])

        # Catalogs
        from war3_id_catalog import CATALOG_COUNTS
        self._values["id_catalog_queries"] = {kind: ObservableVar("") for kind in ("item", "ability", "unit")}
        self._values["id_catalog_statuses"] = {
            kind: LocalizedObservableVar(f"记录数：{CATALOG_COUNTS[kind]}", lambda: ui_lang["code"])
            for kind in ("item", "ability", "unit")
        }

        # Artifact Plan
        self._values["artifact_plan_settings"] = self.services.artifact_settings()
        self._values["artifact_plan_panel"] = VirtualControl("artifact_plan_panel")

        # Virtual Tables
        self._values["resource_tree"] = VirtualTree(("group", "gold", "lumber", "food", "gold_address", "lumber_address", "source"))
        self._values["candidate_tree"] = VirtualTree(("index", "confidence", "hp", "mp", "position", "evidence", "components", "inventory", "handle", "owner", "unit"))
        self._values["unit_field_tree"] = VirtualTree(("category", "label", "value", "type", "address", "note"))
        self._values["lock_tree"] = VirtualTree(("scope", "label", "value"))
        self._values["ability_field_tree"] = VirtualTree(("field", "type", "scope", "name", "value", "status"))
        self._values["item_field_tree"] = VirtualTree(("field", "type", "name", "value", "status"))
        self._values["extension_bag_tree"] = VirtualTree(("slot", "rawcode", "charges", "handle"))
        self._values["extension_equipment_tree"] = VirtualTree(("slot", "rawcode", "type", "charges", "handle"))
        self._values["extension_talent_tree"] = VirtualTree(("hero", "tier", "choices", "selected"))
        self._values["id_catalog_trees"] = {
            kind: VirtualTree(("rawcode", "name_zh", "name_en", "category")) for kind in ("item", "ability", "unit")
        }

        # Controls & Buttons
        self._values["ability_field_write_button"] = VirtualControl("ability_field_write_button")
        self._values["item_field_write_button"] = VirtualControl("item_field_write_button")
        self._values["discovery_cancel_button"] = VirtualControl("discovery_cancel_button")
        self._values["extension_loadout_box"] = VirtualControl("extension_loadout_box")
        self._values["extension_talent_choice_box"] = VirtualControl("extension_talent_choice_box")
        self._values["hotkey_canvas"] = VirtualControl("hotkey_canvas")
        self._values["hotkey_window"] = VirtualControl("hotkey_window")

        # Concurrency & Application state
        self._values["operation_lock"] = self.dispatch_lock
        self._values["operation_threads_lock"] = threading.Lock()
        self._values["operation_threads"] = set()
        self._values["state"] = {
            "trainer": None, "resource_caches": {}, "resource_labels": {}, "selected_resource_iid": "",
            "local_resource_iid": "", "unit_fields": {}, "selected_unit_identity": None,
            "selected_unit_win10": False, "selected_unit_type_id": 0, "last_verified_unit_identity": None,
            "selection_candidates": {}, "manual_unit_identity": None, "locks": {}, "lock_busy": False,
            "ally_health_lock": False, "ally_health_lock_busy": False, "ally_health_lock_trainer": None,
            "rapid_build": False, "rapid_build_busy": False, "rapid_build_trainer": None,
            "initial_connect_busy": False, "active_operations": set(), "elephant_game_paused": False,
            "ability_field_snapshot": None, "ability_field_rows": {}, "item_field_snapshot": None,
            "item_field_rows": {}, "extension_snapshot": None, "closing": False
        }

        # Zero-delay application updates complete before the RPC result is read.
        port = self
        class VirtualRoot:
            def after(self, ms: int, func: Callable[..., Any], *args) -> None:
                if port._closed:
                    return
                if ms == 0:
                    with port.dispatch_lock:
                        return func(*args)
                def run():
                    try:
                        with port.dispatch_lock:
                            if not port._closed:
                                func(*args)
                    except Exception as exc:
                        logging.getLogger(__name__).exception('Scheduled desktop update failed')
                        reporter=getattr(port,'error_reporter',None)
                        if reporter and not port._closed:reporter(exc)
                    finally:
                        port._timers.discard(timer)
                timer = threading.Timer(ms / 1000.0, run)
                timer.daemon = True
                port._timers.add(timer)
                timer.start()
                return timer

            def destroy(self) -> None:
                port.close()
                if port.on_destroy:
                    port.on_destroy()

            def clipboard_clear(self):
                port._clipboard = ''

            def clipboard_append(self, text):
                port._clipboard = getattr(port, '_clipboard', '') + str(text)
                if port.window:
                    import json
                    port.window.evaluate_js('navigator.clipboard.writeText(' + json.dumps(port._clipboard) + ')')

        self._values["root"] = VirtualRoot()

        # Dialog ports
        class VirtualDialog:
            @staticmethod
            def showinfo(title, message, **kwargs):
                port.value('status').set(str(message))
            @staticmethod
            def showwarning(title, message, **kwargs):
                port.value('status').set(str(message))
                port.publish_error(str(message),str(title))
            @staticmethod
            def showerror(title, message, **kwargs):
                port.dialog_error = str(message)
                port.value('status').set(str(message))
                port.dialog_notice=port.publish_error(str(message),str(title))
            @staticmethod
            def askyesno(title, message, **kwargs):
                accepted = bool(port.window and port.window.create_confirmation_dialog(str(title), str(message)))
                port.cancelled = not accepted
                return accepted

            @staticmethod
            def asksaveasfilename(**kwargs):
                if not port.window:
                    return ''
                import webview
                paths = port.window.create_file_dialog(webview.FileDialog.SAVE,
                    save_filename=kwargs.get('initialfile', ''), file_types=kwargs.get('file_types',('JSON (*.json)', 'All files (*.*)')))
                return paths[0] if paths else ''

            @staticmethod
            def askopenfilename(**kwargs):
                if not port.window:
                    return ''
                import webview
                paths = port.window.create_file_dialog(webview.FileDialog.OPEN,
                    file_types=kwargs.get('file_types',('JSON (*.json)', 'All files (*.*)')))
                return paths[0] if paths else ''

            @staticmethod
            def askopenfilenames(**kwargs):
                if not port.window:
                    return ()
                import webview
                paths = port.window.create_file_dialog(webview.FileDialog.OPEN,
                    allow_multiple=True,
                    file_types=kwargs.get('file_types', ('JSON (*.json)', 'All files (*.*)')))
                return tuple(paths or ())

            @staticmethod
            def askdirectory(**kwargs):
                if not port.window:return ''
                import webview
                paths=port.window.create_file_dialog(webview.FileDialog.FOLDER)
                return paths[0] if paths else ''

        self._values["messagebox"] = VirtualDialog()
        self._values["filedialog"] = VirtualDialog()

    def value(self, name: str) -> Any:
        if name not in self._values:
            raise KeyError(f"Undeclared port requested: {name}")
        return self._values[name]

    def publish_error(self,message,title='操作未完成',log_path='',details=None):
        with self._notice_lock:
            self._notice_sequence+=1
            notice=dict(id=self._notice_sequence,title=title,message=message,logPath=str(log_path))
            if details:notice.update(details=details,context='map_catalog')
            self._notices.append(notice)
        return notice

    def take_notifications(self):
        with self._notice_lock:
            result,self._notices=self._notices,[]
        return result

    def publish_unit_read(self,unit,candidates):
        with self._notice_lock:
            self._notices.append(dict(kind='unit_read',unit=unit,candidates=candidates))

    def publish_parameters(self,parameters):
        with self._notice_lock:
            self._notices.append(dict(kind='parameters',parameters=parameters))

    def bind(self, name: str, value: Any, callback: bool = False) -> None:
        self._values[name] = value

    def validate(self, required_ports: frozenset[str]) -> None:
        missing = required_ports - set(self._values.keys())
        if missing:
            raise RuntimeError(f"Missing required view ports: {sorted(missing)}")

    def post(self, callback, *args):
        return self.value('root').after(0, callback, *args)

    def close(self):
        self._closed = True
        for timer in tuple(self._timers):
            timer.cancel()
        self._timers.clear()
