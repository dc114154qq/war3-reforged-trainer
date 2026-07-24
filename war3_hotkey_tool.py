"""Standalone bilingual hotkey utility for Warcraft III: Reforged."""

from __future__ import annotations

import argparse
import ctypes
import json
import queue
import sys
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from war3_hotkey_engine import HotkeyEngine, WarcraftWindowGuard
from war3_hotkey_model import (
    APP_VERSION,
    AppConfig,
    BindingConfig,
    ConfigStore,
    KEY_NAME_TO_VK,
    KeyParseError,
    MODIFIER_ORDER,
    MODIFIER_VKS,
    ProfileConfig,
    SLOT_GROUP_SPECS,
    Translator,
    binding_conflicts,
    clone_profile,
    default_profile,
    parse_keystroke,
    validate_profile,
)


ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
ICON_PATH = ROOT / "assets" / "app_icon.ico"

SOURCE_KEY_CHOICES = (
    "Q", "W", "E", "R", "T", "Y", "A", "S", "D", "F", "G", "H", "Z", "X", "C", "V", "B", "N",
    "1", "2", "3", "4", "5", "6", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
    "Space", "Tab", "CapsLock", "Mouse4", "Mouse5", "Middle",
    "Alt+Q", "Alt+W", "Alt+E", "Alt+A", "Alt+S", "Alt+D", "Alt+Z", "Alt+X", "Alt+C",
    "Ctrl+Q", "Ctrl+W", "Ctrl+E", "Ctrl+A", "Ctrl+S", "Ctrl+D", "Ctrl+Z", "Ctrl+X", "Ctrl+C",
    "Shift+Q", "Shift+W", "Shift+E", "Shift+A", "Shift+S", "Shift+D",
)
TARGET_KEY_CHOICES = (
    "Q", "W", "E", "R", "A", "S", "D", "F", "Z", "X", "C", "V",
    "NUM7", "NUM8", "NUM4", "NUM5", "NUM1", "NUM2",
    "INSERT", "DELETE", "PAGEUP", "PAGEDOWN", "HOME", "END", "SPACE", "TAB",
)

VK_TO_KEY_NAME = {vk: name for name, vk in KEY_NAME_TO_VK.items()}


class HotkeyToolApp:
    def __init__(self, root: tk.Tk, *, no_hooks: bool = False):
        self.root = root
        self.store = ConfigStore()
        self.config = self.store.load()
        self.translator = Translator(self.config.language)
        self.guard = WarcraftWindowGuard()
        self.state_events: queue.SimpleQueue[tuple[str, str]] = queue.SimpleQueue()
        self.engine = HotkeyEngine(
            self.current_profile,
            guard=self.guard,
            on_state=lambda state: self.state_events.put(("state", state)),
            on_error=lambda message: self.state_events.put(("error", message)),
        )
        self.no_hooks = no_hooks
        self.localized_widgets: list[tuple[tk.Widget, str, str]] = []
        self.binding_vars: dict[str, dict[str, tk.Variable]] = {}
        self.slot_buttons: dict[str, ttk.Button] = {}
        self.smartcast_buttons: dict[str, tk.Button] = {}
        self._capturing_binding_id: str | None = None
        self.state_key = ""
        self.status_key = "ready"
        self.status_kwargs: dict[str, object] = {}
        self._build_variables()
        self._configure_window()
        self._configure_styles()
        self._build_ui()
        self._load_profile_to_ui(self.current_profile)
        self._apply_language()
        if not self.no_hooks:
            try:
                self.engine.start()
            except Exception as exc:
                self._show_error(str(exc))
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(120, self._poll)

    @property
    def current_profile(self) -> ProfileConfig:
        return self.config.profiles[self.config.active_profile]

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator(key, **kwargs)

    def _build_variables(self) -> None:
        profile = self.current_profile
        self.profile_name_var = tk.StringVar(value=self.config.active_profile)
        self.state_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.enabled_var = tk.BooleanVar(value=profile.enabled)
        self.enforce_var = tk.BooleanVar(value=profile.enforce_hotkeys)
        self.group_enabled_vars = {
            group: tk.BooleanVar(value=profile.enabled_groups.get(group, True))
            for group in SLOT_GROUP_SPECS
        }
        self.pause_chat_var = tk.BooleanVar(value=profile.pause_in_chat)
        self.smartcast_delay_var = tk.StringVar(value=str(profile.smartcast_delay_ms))
        self.repeat_delay_var = tk.StringVar(value=str(profile.repeat_delay_ms))
        self.self_modifier_var = tk.StringVar(value=profile.self_cast_modifier)
        self.autocast_modifier_var = tk.StringVar(value=profile.autocast_modifier)
        self.suspend_hotkey_var = tk.StringVar(value=profile.suspend_hotkey)
        self.mouse_lock_var = tk.BooleanVar(value=profile.mouse_lock_enabled)
        self.mouse_lock_hotkey_var = tk.StringVar(value=profile.mouse_lock_hotkey)
        self.right_repeat_var = tk.BooleanVar(value=profile.right_repeat_enabled)
        self.right_delay_var = tk.StringVar(value=str(profile.right_repeat_delay_ms))
        self.camera_enabled_var = tk.BooleanVar(value=profile.camera_enabled)
        self.distance_modifier_var = tk.StringVar(value=profile.camera_distance_modifier)
        self.rotation_modifier_var = tk.StringVar(value=profile.camera_rotation_modifier)
        self.incline_modifier_var = tk.StringVar(value=profile.camera_incline_modifier)
        self.rotate_up_var = tk.StringVar(value=profile.camera_rotate_up_key)
        self.rotate_down_var = tk.StringVar(value=profile.camera_rotate_down_key)
        self.incline_up_var = tk.StringVar(value=profile.camera_incline_up_key)
        self.incline_down_var = tk.StringVar(value=profile.camera_incline_down_key)
        self.language_var = tk.StringVar(value=self.config.language)
        self.diag_process_var = tk.StringVar(value="-")
        self.diag_foreground_var = tk.StringVar(value="-")
        self.diag_client_var = tk.StringVar(value="-")
        self.diag_hook_var = tk.StringVar(value="-")

    def _configure_window(self) -> None:
        self.root.title(f"{self.tr('app_name')} v{APP_VERSION}")
        self.root.geometry("1220x790")
        self.root.minsize(1060, 700)
        if ICON_PATH.exists():
            try:
                self.root.iconbitmap(default=str(ICON_PATH))
            except tk.TclError:
                pass

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        self.root.configure(background="#f4f5f3")
        style.configure("TFrame", background="#f4f5f3")
        style.configure("Header.TFrame", background="#202522")
        style.configure("Header.TLabel", background="#202522", foreground="#ffffff", font=("Segoe UI", 16, "bold"))
        style.configure("Version.TLabel", background="#202522", foreground="#aeb8b1", font=("Segoe UI", 9))
        style.configure("State.TLabel", background="#202522", foreground="#e8ece9", font=("Segoe UI", 10))
        style.configure("TLabel", background="#f4f5f3", foreground="#242825", font=("Segoe UI", 9))
        style.configure("TLabelframe", background="#f4f5f3", bordercolor="#c9ceca", relief="solid")
        style.configure("TLabelframe.Label", background="#f4f5f3", foreground="#242825", font=("Segoe UI", 10, "bold"))
        style.configure("TNotebook", background="#f4f5f3", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(18, 8), font=("Segoe UI", 9))
        style.map("TNotebook.Tab", background=[("selected", "#ffffff")], foreground=[("selected", "#1b6b45")])
        style.configure("Accent.TButton", background="#1b6b45", foreground="#ffffff", padding=(12, 7), font=("Segoe UI", 9, "bold"))
        style.map("Accent.TButton", background=[("active", "#155638"), ("disabled", "#8ca89a")])
        style.configure("Header.TButton", background="#343b37", foreground="#ffffff", padding=(9, 5))
        style.map("Header.TButton", background=[("active", "#465149")])
        style.configure("Status.TLabel", foreground="#4f5751", font=("Segoe UI", 9))
        style.configure("Hint.TLabel", foreground="#626a65", font=("Segoe UI", 8))
        style.configure("GridHeader.TLabel", foreground="#4f5751", font=("Segoe UI", 8, "bold"))
        style.configure("Slot.TButton", font=("Segoe UI", 12, "bold"), padding=(10, 14))
        style.configure("SlotCapture.TButton", font=("Segoe UI", 12, "bold"), padding=(10, 14), foreground="#1b6b45")

    def _localize(self, widget: tk.Widget, key: str, option: str = "text") -> tk.Widget:
        self.localized_widgets.append((widget, key, option))
        return widget

    def _build_ui(self) -> None:
        header = ttk.Frame(self.root, style="Header.TFrame", padding=(18, 12))
        header.pack(fill="x")
        title_area = ttk.Frame(header, style="Header.TFrame")
        title_area.pack(side="left", fill="x", expand=True)
        self.title_label = ttk.Label(title_area, style="Header.TLabel")
        self.title_label.pack(side="left")
        ttk.Label(title_area, text=f"v{APP_VERSION}", style="Version.TLabel").pack(side="left", padx=(8, 0), pady=(7, 0))
        self.state_dot = tk.Canvas(title_area, width=12, height=12, highlightthickness=0, background="#202522")
        self.state_dot.pack(side="left", padx=(24, 7), pady=(7, 0))
        self.state_dot_item = self.state_dot.create_oval(2, 2, 10, 10, fill="#a0a7a2", outline="")
        ttk.Label(title_area, textvariable=self.state_var, style="State.TLabel").pack(side="left", pady=(5, 0))
        self.language_button = ttk.Button(header, style="Header.TButton", width=5, command=self.toggle_language)
        self.language_button.pack(side="right", padx=(10, 0))
        self.enable_check = ttk.Checkbutton(header, variable=self.enabled_var, command=self.toggle_enabled, style="Header.TButton")
        self.enable_check.pack(side="right")

        profile_bar = ttk.Frame(self.root, padding=(18, 10, 18, 8))
        profile_bar.pack(fill="x")
        self.profile_label = self._localize(ttk.Label(profile_bar), "profile")
        self.profile_label.pack(side="left")
        self.profile_combo = ttk.Combobox(
            profile_bar,
            textvariable=self.profile_name_var,
            values=tuple(self.config.profiles),
            state="readonly",
            width=24,
        )
        self.profile_combo.pack(side="left", padx=(8, 10))
        self.profile_combo.bind("<<ComboboxSelected>>", self.select_profile)
        for key, command in (
            ("new_profile", self.new_profile),
            ("duplicate_profile", self.duplicate_profile),
            ("delete_profile", self.delete_profile),
        ):
            button = self._localize(ttk.Button(profile_bar, command=command), key)
            button.pack(side="left", padx=(0, 6))
        self.save_button = self._localize(ttk.Button(profile_bar, command=self.save_and_apply, style="Accent.TButton"), "save_apply")
        self.save_button.pack(side="right")

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=18, pady=(0, 8))
        self.bindings_tab = ttk.Frame(self.notebook, padding=10)
        self.mouse_tab = ttk.Frame(self.notebook, padding=10)
        self.settings_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.bindings_tab, text="")
        self.notebook.add(self.mouse_tab, text="")
        self.notebook.add(self.settings_tab, text="")
        self._build_bindings_tab()
        self._build_mouse_tab()
        self._build_settings_tab()

        footer = ttk.Frame(self.root, padding=(18, 6, 18, 10))
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.status_var, style="Status.TLabel").pack(side="left", fill="x", expand=True)
        self.admin_note = self._localize(ttk.Label(footer, style="Hint.TLabel"), "admin_note")
        self.admin_note.pack(side="right")

    def _build_bindings_tab(self) -> None:
        self.bindings_tab.columnconfigure(0, weight=1, uniform="binding-columns")
        self.bindings_tab.columnconfigure(1, weight=1, uniform="binding-columns")
        self.bindings_tab.rowconfigure(0, weight=1, uniform="binding-rows")
        self.bindings_tab.rowconfigure(1, weight=1, uniform="binding-rows")
        placements = {
            "ability": (0, 0),
            "item": (0, 1),
            "spellbook": (1, 0),
            "shop": (1, 1),
        }
        by_group: dict[str, list[BindingConfig]] = {name: [] for name in SLOT_GROUP_SPECS}
        for binding in self.current_profile.bindings:
            by_group[binding.group].append(binding)
        for group, (row, column) in placements.items():
            frame = self._localize(ttk.LabelFrame(self.bindings_tab, padding=10), f"{group}_group")
            padx = (0, 7) if column == 0 else (7, 0)
            pady = (0, 7) if row == 0 else (7, 0)
            frame.grid(row=row, column=column, sticky="nsew", padx=padx, pady=pady)
            columns, rows = SLOT_GROUP_SPECS[group]
            for index in range(columns):
                frame.columnconfigure(index, weight=1, uniform=f"{group}-columns")
            for index in range(rows):
                frame.rowconfigure(index, weight=1, uniform=f"{group}-rows")
            for binding in sorted(by_group[group], key=lambda value: value.slot_index or 0):
                self._build_slot(frame, binding, columns)

    def _build_slot(self, parent: ttk.LabelFrame, binding: BindingConfig, columns: int) -> None:
        variables: dict[str, tk.Variable] = {
            "enabled": tk.BooleanVar(value=binding.enabled),
            "source": tk.StringVar(value=binding.source),
            "smartcast": tk.BooleanVar(value=binding.smartcast),
            "repeat": tk.BooleanVar(value=binding.repeat),
        }
        self.binding_vars[binding.binding_id] = variables
        index = binding.slot_index or 0
        cell = ttk.Frame(parent)
        cell.grid(row=index // columns, column=index % columns, sticky="nsew", padx=5, pady=5)
        cell.columnconfigure(0, weight=1)
        cell.rowconfigure(0, weight=1)
        key_button = ttk.Button(
            cell,
            textvariable=variables["source"],
            style="Slot.TButton",
            command=lambda binding_id=binding.binding_id: self.begin_slot_capture(binding_id),
        )
        key_button.grid(row=0, column=0, sticky="nsew")
        self.slot_buttons[binding.binding_id] = key_button
        smartcast_button = tk.Button(
            cell,
            text="⚡",
            font=("Segoe UI Symbol", 12),
            relief="solid",
            borderwidth=1,
            command=lambda binding_id=binding.binding_id: self.toggle_slot_smartcast(binding_id),
        )
        smartcast_button.grid(row=1, column=0, sticky="ew", pady=(2, 0), ipady=1)
        self.smartcast_buttons[binding.binding_id] = smartcast_button
        self._refresh_smartcast_button(binding.binding_id)

    def _build_mouse_tab(self) -> None:
        self.mouse_tab.columnconfigure(0, weight=1, uniform="mouse-columns")
        self.mouse_tab.columnconfigure(1, weight=1, uniform="mouse-columns")
        general = self._localize(ttk.LabelFrame(self.mouse_tab, padding=12), "general")
        camera = self._localize(ttk.LabelFrame(self.mouse_tab, padding=12), "camera_controls")
        general.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        camera.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.mouse_tab.rowconfigure(0, weight=1)

        row = 0
        for key, variable in (
            ("pause_in_chat", self.pause_chat_var),
            ("right_repeat", self.right_repeat_var),
            ("mouse_lock", self.mouse_lock_var),
        ):
            widget = self._localize(ttk.Checkbutton(general, variable=variable), key)
            widget.grid(row=row, column=0, columnspan=2, sticky="w", pady=5)
            row += 1
        for key, variable in (
            ("smartcast_delay", self.smartcast_delay_var),
            ("repeat_delay", self.repeat_delay_var),
            ("right_repeat_delay", self.right_delay_var),
            ("self_modifier", self.self_modifier_var),
            ("autocast_modifier", self.autocast_modifier_var),
            ("suspend_hotkey", self.suspend_hotkey_var),
            ("mouse_lock_hotkey", self.mouse_lock_hotkey_var),
        ):
            label = self._localize(ttk.Label(general), key)
            label.grid(row=row, column=0, sticky="w", pady=5, padx=(0, 12))
            if "modifier" in key:
                control = ttk.Combobox(general, textvariable=variable, values=MODIFIER_ORDER, state="readonly", width=14)
            else:
                control = ttk.Entry(general, textvariable=variable, width=16)
            control.grid(row=row, column=1, sticky="ew", pady=5)
            row += 1
        general.columnconfigure(1, weight=1)

        self.camera_check = self._localize(ttk.Checkbutton(camera, variable=self.camera_enabled_var), "camera_enabled")
        self.camera_check.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))
        headers = ("", "wheel_up_key", "wheel_down_key")
        for column, key in enumerate(headers):
            if key:
                self._localize(ttk.Label(camera, style="GridHeader.TLabel"), key).grid(row=1, column=column, sticky="w", padx=(0, 8))
        rows = (
            ("distance_modifier", self.distance_modifier_var, None, None),
            ("rotation_modifier", self.rotation_modifier_var, self.rotate_up_var, self.rotate_down_var),
            ("incline_modifier", self.incline_modifier_var, self.incline_up_var, self.incline_down_var),
        )
        for index, (key, modifier_var, up_var, down_var) in enumerate(rows, 2):
            item = ttk.Frame(camera)
            item.grid(row=index, column=0, sticky="ew", pady=7, padx=(0, 8))
            self._localize(ttk.Label(item), key).pack(side="left")
            ttk.Combobox(item, textvariable=modifier_var, values=MODIFIER_ORDER, state="readonly", width=7).pack(side="right")
            if up_var is None:
                ttk.Label(camera, text="Wheel").grid(row=index, column=1, columnspan=2, sticky="w", pady=7)
            else:
                ttk.Combobox(camera, textvariable=up_var, values=TARGET_KEY_CHOICES, width=11).grid(
                    row=index, column=1, sticky="ew", padx=(0, 8), pady=7
                )
                ttk.Combobox(camera, textvariable=down_var, values=TARGET_KEY_CHOICES, width=11).grid(
                    row=index, column=2, sticky="ew", pady=7
                )
        camera.columnconfigure(0, weight=1)
        camera.columnconfigure(1, weight=1)
        camera.columnconfigure(2, weight=1)

    def _build_settings_tab(self) -> None:
        self.settings_tab.columnconfigure(0, weight=1, uniform="settings-columns")
        self.settings_tab.columnconfigure(1, weight=1, uniform="settings-columns")
        settings = self._localize(ttk.LabelFrame(self.settings_tab, padding=12), "startup")
        diagnostics = self._localize(ttk.LabelFrame(self.settings_tab, padding=12), "diagnostics")
        settings.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        diagnostics.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.settings_tab.rowconfigure(0, weight=1)

        self._localize(ttk.Label(settings), "language").grid(row=0, column=0, sticky="w", padx=(0, 12), pady=6)
        self.language_combo = ttk.Combobox(settings, textvariable=self.language_var, state="readonly", width=18)
        self.language_combo.grid(row=0, column=1, sticky="ew", pady=6)
        self.language_combo.bind("<<ComboboxSelected>>", self.select_language)
        self._localize(ttk.Checkbutton(settings, variable=self.enabled_var, command=self.toggle_enabled), "start_enabled").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=6
        )
        self._localize(ttk.Checkbutton(settings, variable=self.enforce_var), "enforce_hotkeys").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=6
        )
        self._localize(ttk.Label(settings, style="GridHeader.TLabel"), "enabled_groups").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(14, 4)
        )
        for index, group in enumerate(SLOT_GROUP_SPECS):
            self._localize(
                ttk.Checkbutton(settings, variable=self.group_enabled_vars[group]),
                f"{group}_group",
            ).grid(row=4 + index // 2, column=index % 2, sticky="w", pady=4)
        self._localize(ttk.Label(settings, style="Hint.TLabel", wraplength=430), "about_reference").grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(14, 4)
        )
        settings.columnconfigure(1, weight=1)

        fields = (
            ("process", self.diag_process_var),
            ("foreground", self.diag_foreground_var),
            ("client_size", self.diag_client_var),
            ("hook_state", self.diag_hook_var),
        )
        for row, (key, variable) in enumerate(fields):
            self._localize(ttk.Label(diagnostics), key).grid(row=row, column=0, sticky="w", padx=(0, 18), pady=5)
            ttk.Label(diagnostics, textvariable=variable).grid(row=row, column=1, sticky="w", pady=5)
        self._localize(ttk.Button(diagnostics, command=self.refresh_diagnostics), "refresh").grid(
            row=0, column=2, rowspan=2, sticky="ne", padx=(20, 0), pady=3
        )
        diagnostics.columnconfigure(1, weight=1)

    def _load_profile_to_ui(self, profile: ProfileConfig) -> None:
        self.enabled_var.set(profile.enabled)
        self.enforce_var.set(profile.enforce_hotkeys)
        for group, variable in self.group_enabled_vars.items():
            variable.set(profile.enabled_groups.get(group, True))
        self.pause_chat_var.set(profile.pause_in_chat)
        self.smartcast_delay_var.set(str(profile.smartcast_delay_ms))
        self.repeat_delay_var.set(str(profile.repeat_delay_ms))
        self.self_modifier_var.set(profile.self_cast_modifier)
        self.autocast_modifier_var.set(profile.autocast_modifier)
        self.suspend_hotkey_var.set(profile.suspend_hotkey)
        self.mouse_lock_var.set(profile.mouse_lock_enabled)
        self.mouse_lock_hotkey_var.set(profile.mouse_lock_hotkey)
        self.right_repeat_var.set(profile.right_repeat_enabled)
        self.right_delay_var.set(str(profile.right_repeat_delay_ms))
        self.camera_enabled_var.set(profile.camera_enabled)
        self.distance_modifier_var.set(profile.camera_distance_modifier)
        self.rotation_modifier_var.set(profile.camera_rotation_modifier)
        self.incline_modifier_var.set(profile.camera_incline_modifier)
        self.rotate_up_var.set(profile.camera_rotate_up_key)
        self.rotate_down_var.set(profile.camera_rotate_down_key)
        self.incline_up_var.set(profile.camera_incline_up_key)
        self.incline_down_var.set(profile.camera_incline_down_key)
        by_id = {binding.binding_id: binding for binding in profile.bindings}
        for binding_id, variables in self.binding_vars.items():
            binding = by_id.get(binding_id)
            if binding is None:
                continue
            variables["enabled"].set(binding.enabled)
            variables["source"].set(binding.source)
            variables["smartcast"].set(binding.smartcast)
            variables["repeat"].set(binding.repeat)
            self._refresh_smartcast_button(binding_id)

    def _profile_from_ui(self) -> ProfileConfig:
        original = self.current_profile
        bindings: list[BindingConfig] = []
        by_id = {binding.binding_id: binding for binding in original.bindings}
        for binding_id, variables in self.binding_vars.items():
            template = by_id[binding_id]
            try:
                source = parse_keystroke(str(variables["source"].get())).canonical()
            except KeyParseError as exc:
                raise ValueError(self.tr("invalid_key", field=self.tr("trigger"), value=variables["source"].get())) from exc
            bindings.append(
                BindingConfig(
                    binding_id=binding_id,
                    source=source,
                    target=source,
                    enabled=bool(variables["enabled"].get()),
                    smartcast=bool(variables["smartcast"].get()),
                    repeat=bool(variables["repeat"].get()),
                    slot_index=template.slot_index,
                    group=template.group,
                )
            )
        conflicts = binding_conflicts([
            binding
            for binding in bindings
            if self.group_enabled_vars[binding.group].get()
        ])
        if conflicts:
            raise ValueError(self.tr("duplicate_key", keys=", ".join(conflicts)))
        profile = ProfileConfig(
            enabled=bool(self.enabled_var.get()),
            enforce_hotkeys=bool(self.enforce_var.get()),
            enabled_groups={
                group: bool(variable.get())
                for group, variable in self.group_enabled_vars.items()
            },
            pause_in_chat=bool(self.pause_chat_var.get()),
            smartcast_delay_ms=int(self.smartcast_delay_var.get()),
            repeat_delay_ms=int(self.repeat_delay_var.get()),
            self_cast_modifier=self.self_modifier_var.get().upper(),
            autocast_modifier=self.autocast_modifier_var.get().upper(),
            suspend_hotkey=parse_keystroke(self.suspend_hotkey_var.get(), allow_mouse=False).canonical(),
            mouse_lock_enabled=bool(self.mouse_lock_var.get()),
            mouse_lock_hotkey=parse_keystroke(self.mouse_lock_hotkey_var.get(), allow_mouse=False).canonical(),
            right_repeat_enabled=bool(self.right_repeat_var.get()),
            right_repeat_delay_ms=int(self.right_delay_var.get()),
            camera_enabled=bool(self.camera_enabled_var.get()),
            camera_distance_modifier=self.distance_modifier_var.get().upper(),
            camera_rotation_modifier=self.rotation_modifier_var.get().upper(),
            camera_incline_modifier=self.incline_modifier_var.get().upper(),
            camera_rotate_up_key=parse_keystroke(self.rotate_up_var.get(), allow_mouse=False).canonical(),
            camera_rotate_down_key=parse_keystroke(self.rotate_down_var.get(), allow_mouse=False).canonical(),
            camera_incline_up_key=parse_keystroke(self.incline_up_var.get(), allow_mouse=False).canonical(),
            camera_incline_down_key=parse_keystroke(self.incline_down_var.get(), allow_mouse=False).canonical(),
            bindings=bindings,
        )
        validate_profile(profile)
        return profile

    def save_and_apply(self) -> None:
        try:
            profile = self._profile_from_ui()
            self.config.profiles[self.config.active_profile] = profile
            self.store.save(self.config)
            self.engine.apply_profile(profile)
            self.set_status("saved", name=self.config.active_profile)
        except (ValueError, KeyParseError) as exc:
            messagebox.showerror(self.tr("invalid_config"), str(exc), parent=self.root)

    def toggle_enabled(self) -> None:
        self.current_profile.enabled = bool(self.enabled_var.get())
        self.store.save(self.config)
        self.engine.apply_profile(self.current_profile)
        self._refresh_enabled_text()

    def select_profile(self, _event=None) -> None:
        name = self.profile_name_var.get()
        if name not in self.config.profiles:
            return
        self.config.active_profile = name
        self.store.save(self.config)
        self._load_profile_to_ui(self.current_profile)
        self.engine.apply_profile(self.current_profile)

    def new_profile(self) -> None:
        name = simpledialog.askstring(self.tr("new_profile"), self.tr("profile_name"), parent=self.root)
        if not name:
            return
        name = name.strip()
        if not name:
            return
        if name in self.config.profiles:
            messagebox.showerror(self.tr("error"), self.tr("profile_exists"), parent=self.root)
            return
        self.config.profiles[name] = default_profile()
        self.config.active_profile = name
        self._refresh_profile_list()
        self._load_profile_to_ui(self.current_profile)
        self.store.save(self.config)
        self.engine.apply_profile(self.current_profile)

    def duplicate_profile(self) -> None:
        name = simpledialog.askstring(self.tr("duplicate_profile"), self.tr("profile_name"), parent=self.root)
        if not name:
            return
        name = name.strip()
        if name in self.config.profiles:
            messagebox.showerror(self.tr("error"), self.tr("profile_exists"), parent=self.root)
            return
        self.config.profiles[name] = clone_profile(self.current_profile)
        self.config.active_profile = name
        self._refresh_profile_list()
        self.store.save(self.config)

    def delete_profile(self) -> None:
        if len(self.config.profiles) <= 1:
            messagebox.showerror(self.tr("error"), self.tr("profile_required"), parent=self.root)
            return
        name = self.config.active_profile
        if not messagebox.askyesno(self.tr("confirm"), self.tr("delete_confirm", name=name), parent=self.root):
            return
        del self.config.profiles[name]
        self.config.active_profile = next(iter(self.config.profiles))
        self._refresh_profile_list()
        self._load_profile_to_ui(self.current_profile)
        self.store.save(self.config)
        self.engine.apply_profile(self.current_profile)

    def _refresh_profile_list(self) -> None:
        self.profile_combo.configure(values=tuple(self.config.profiles))
        self.profile_name_var.set(self.config.active_profile)

    def toggle_language(self) -> None:
        language = "en" if self.translator.language == "zh" else "zh"
        self.language_var.set(language)
        self.config.language = language
        self.translator.set_language(language)
        self.store.save(self.config)
        self._apply_language()

    def select_language(self, _event=None) -> None:
        display_to_code = {
            self.tr("auto_language"): "auto",
            self.tr("chinese"): "zh",
            self.tr("english"): "en",
        }
        selected = self.language_var.get()
        language = display_to_code.get(selected, selected if selected in {"auto", "zh", "en"} else "auto")
        self.config.language = language
        self.translator.set_language(language)
        self.store.save(self.config)
        self._apply_language()

    def _apply_language(self) -> None:
        self.root.title(f"{self.tr('app_name')} v{APP_VERSION}")
        self.title_label.configure(text=self.tr("app_name"))
        self.language_button.configure(text="EN" if self.translator.language == "zh" else "中")
        self.notebook.tab(self.bindings_tab, text=self.tr("bindings_tab"))
        self.notebook.tab(self.mouse_tab, text=self.tr("mouse_tab"))
        self.notebook.tab(self.settings_tab, text=self.tr("settings_tab"))
        for widget, key, option in self.localized_widgets:
            values = getattr(widget, "_translation_values", {})
            try:
                widget.configure(**{option: self.tr(key, **values)})
            except tk.TclError:
                pass
        language_values = (self.tr("auto_language"), self.tr("chinese"), self.tr("english"))
        self.language_combo.configure(values=language_values)
        language_display = {
            "auto": self.tr("auto_language"),
            "zh": self.tr("chinese"),
            "en": self.tr("english"),
        }
        self.language_var.set(language_display.get(self.config.language, language_values[0]))
        self._refresh_enabled_text()
        if not self.state_key:
            game = self.guard.snapshot()
            self.state_key = "game_active" if game.foreground else "game_background" if game.found else "game_not_found"
        self.state_var.set(self.tr(self.state_key))
        self.set_status(self.status_key, **self.status_kwargs)
        self.refresh_diagnostics()

    def _refresh_enabled_text(self) -> None:
        self.enable_check.configure(text=self.tr("enabled") if self.enabled_var.get() else self.tr("disabled"))

    def begin_slot_capture(self, binding_id: str) -> None:
        if self._capturing_binding_id is not None:
            self._finish_slot_capture()
        self._capturing_binding_id = binding_id
        self.slot_buttons[binding_id].configure(style="SlotCapture.TButton")
        self.set_status("press_slot_key")
        if self.engine.running:
            self.engine.begin_key_capture(
                lambda value, captured_id=binding_id: self.state_events.put(
                    ("capture", f"{captured_id}\t{value or ''}")
                )
            )
        else:
            self.root.bind_all("<KeyPress>", self._capture_slot_key)
            self.root.bind_all("<Button-2>", lambda event: self._capture_mouse_key("MIDDLE"))

    def _capture_slot_key(self, event: tk.Event) -> str | None:
        binding_id = self._capturing_binding_id
        if binding_id is None:
            return None
        key_name = VK_TO_KEY_NAME.get(int(event.keycode))
        if key_name is None or key_name in MODIFIER_ORDER:
            return "break"
        if key_name == "ESC":
            self._finish_slot_capture()
            return "break"
        modifiers = []
        get_async_key_state = ctypes.windll.user32.GetAsyncKeyState
        for modifier in MODIFIER_ORDER:
            if get_async_key_state(MODIFIER_VKS[modifier]) & 0x8000:
                modifiers.append(modifier.title())
        value = "+".join((*modifiers, key_name))
        self.binding_vars[binding_id]["source"].set(parse_keystroke(value).canonical())
        self._finish_slot_capture()
        return "break"

    def _capture_mouse_key(self, key_name: str) -> str:
        binding_id = self._capturing_binding_id
        if binding_id is not None:
            self.binding_vars[binding_id]["source"].set(key_name)
            self._finish_slot_capture()
        return "break"

    def _finish_slot_capture(self) -> None:
        binding_id = self._capturing_binding_id
        self._capturing_binding_id = None
        self.engine.cancel_key_capture()
        if binding_id is not None and binding_id in self.slot_buttons:
            self.slot_buttons[binding_id].configure(style="Slot.TButton")
        self.root.unbind_all("<KeyPress>")
        self.root.unbind_all("<Button-2>")
        self.set_status("ready")

    def toggle_slot_smartcast(self, binding_id: str) -> None:
        variable = self.binding_vars[binding_id]["smartcast"]
        variable.set(not bool(variable.get()))
        self._refresh_smartcast_button(binding_id)

    def _refresh_smartcast_button(self, binding_id: str) -> None:
        button = self.smartcast_buttons.get(binding_id)
        variables = self.binding_vars.get(binding_id)
        if button is None or variables is None:
            return
        enabled = bool(variables["smartcast"].get())
        button.configure(
            background="#cce7fb" if enabled else "#ecefed",
            activebackground="#b6dcf7" if enabled else "#dde2df",
            foreground="#0b5f93" if enabled else "#4a504c",
        )

    def refresh_diagnostics(self) -> None:
        snapshot = self.engine.status_snapshot()
        game = snapshot["game"]
        self.diag_process_var.set(f"{Path(game.executable).name} (PID {game.pid})" if game.found else "-")
        self.diag_foreground_var.set(self.tr("yes") if game.foreground else self.tr("no"))
        if game.client_rect:
            left, top, right, bottom = game.client_rect
            self.diag_client_var.set(f"{right - left} x {bottom - top}")
        else:
            self.diag_client_var.set("-")
        self.diag_hook_var.set(self.tr("running") if snapshot["running"] else self.tr("stopped"))

    def set_status(self, key: str, **kwargs: object) -> None:
        self.status_key = key
        self.status_kwargs = kwargs
        self.status_var.set(self.tr(key, **kwargs))

    def _poll(self) -> None:
        try:
            while True:
                event_type, value = self.state_events.get_nowait()
                if event_type == "state":
                    self.state_key = value
                    self.state_var.set(self.tr(value))
                    color = {
                        "game_active": "#36b66f",
                        "game_background": "#d3a52d",
                        "chat_paused": "#d3a52d",
                        "suspended": "#d85d55",
                        "game_not_found": "#8f9691",
                    }.get(value, "#8f9691")
                    self.state_dot.itemconfigure(self.state_dot_item, fill=color)
                elif event_type == "capture":
                    binding_id, _, captured = value.partition("\t")
                    if binding_id == self._capturing_binding_id and captured:
                        self.binding_vars[binding_id]["source"].set(captured)
                    if binding_id == self._capturing_binding_id:
                        self._finish_slot_capture()
                else:
                    self.set_status("error")
                    self.status_var.set(value)
        except queue.Empty:
            pass
        if not self.state_var.get():
            game = self.guard.snapshot()
            key = "game_active" if game.foreground else "game_background" if game.found else "game_not_found"
            self.state_key = key
            self.state_var.set(self.tr(key))
        self.refresh_diagnostics()
        self.root.after(350, self._poll)

    def _show_error(self, message: str) -> None:
        messagebox.showerror(self.tr("error"), message, parent=self.root)

    def close(self) -> None:
        if self._capturing_binding_id is not None:
            self._finish_slot_capture()
        try:
            self.store.save(self.config)
        finally:
            self.engine.stop()
            self.root.destroy()


def diagnose() -> int:
    guard = WarcraftWindowGuard()
    snapshot = guard.snapshot(force=True)
    print(json.dumps({
        "found": snapshot.found,
        "hwnd": snapshot.hwnd,
        "pid": snapshot.pid,
        "executable": snapshot.executable,
        "foreground": snapshot.foreground,
        "client_rect": snapshot.client_rect,
    }, ensure_ascii=False, indent=2))
    return 0 if snapshot.found else 1


def engine_self_test() -> int:
    profile = default_profile()
    profile.enabled = False
    engine = HotkeyEngine(profile)
    engine.start()
    snapshot = engine.status_snapshot()
    engine.stop()
    print(json.dumps({"hook_started": bool(snapshot["running"]), "game_found": snapshot["game"].found}))
    return 0 if snapshot["running"] else 1


def install_exception_log() -> None:
    log_path = ConfigStore().path.parent / "hotkey-tool.log"

    def write_exception(exc_type, exc_value, exc_traceback) -> None:
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as handle:
                traceback.print_exception(exc_type, exc_value, exc_traceback, file=handle)
        finally:
            sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = write_exception


def acquire_single_instance() -> int | None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.CreateMutexW(None, False, "Local\\Twomengxi.War3ReforgedHotkeys")
    if not handle:
        return None
    if ctypes.get_last_error() == 183:
        kernel32.CloseHandle(handle)
        return None
    return int(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnose", action="store_true")
    parser.add_argument("--self-test-engine", action="store_true")
    parser.add_argument("--no-hooks", action="store_true")
    args = parser.parse_args(argv)
    if args.diagnose:
        return diagnose()
    if args.self_test_engine:
        return engine_self_test()
    install_exception_log()
    mutex = acquire_single_instance()
    if mutex is None:
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("Warcraft III", "The hotkey tool is already running.\n改键工具已经在运行。")
        root.destroy()
        return 0
    root = tk.Tk()
    app = HotkeyToolApp(root, no_hooks=args.no_hooks)

    def report_callback_exception(exc_type, exc_value, exc_traceback):
        sys.excepthook(exc_type, exc_value, exc_traceback)
        messagebox.showerror(app.tr("error"), str(exc_value), parent=root)

    root.report_callback_exception = report_callback_exception
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
