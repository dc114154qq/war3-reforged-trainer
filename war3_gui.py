"""Tk presentation and command wiring; no game-process backend imports."""
from __future__ import annotations
from pathlib import Path
from typing import Callable
from dataclasses import replace
import sys,threading,time
from war3_metadata import APP_VERSION,PRODUCT_EDITION_LABEL,PRODUCT_READ_MODE
from war3_contracts import ResourceCache,UnitMemoryField,UnitSelectionSummary,AbilityFieldSnapshot,ItemFieldSnapshot
from war3_3_extension_catalog import EQUIPMENT_SLOT_NAMES,EQUIPMENT_TYPE_NAMES,OFFICIAL_BACKPACKS
from war3_3_stats import STAT_DETAIL_SPECS
from war3_id_catalog import CATALOG_COUNTS,search_id_entries
from war3_ui_i18n import detect_ui_language,translate_ui_text
from war3_tk_view import TkViewPort

def apply_ui_theme(root: object, style: object, dark: bool) -> dict[str, str]:
    palette = (
        {
            "background": "#0f1115", "surface": "#191c22", "field": "#101318",
            "foreground": "#f4f5f7", "muted": "#aeb4bf", "border": "#3a404a",
            "accent": "#2f73c9", "selection": "#245a9b",
        }
        if dark else
        {
            "background": "#f0f0f0", "surface": "#ffffff", "field": "#ffffff",
            "foreground": "#111111", "muted": "#666666", "border": "#b8b8b8",
            "accent": "#e7e7e7", "selection": "#0a64ad",
        }
    )
    if "clam" in style.theme_names():
        style.theme_use("clam")
    root.configure(background=palette["background"])
    for pattern, value in (
        ("*background", palette["background"]),
        ("*foreground", palette["foreground"]),
        ("*insertBackground", palette["foreground"]),
        ("*selectBackground", palette["selection"]),
        ("*selectForeground", "#ffffff"),
    ):
        root.option_add(pattern, value)

    common = {"background": palette["background"], "foreground": palette["foreground"]}
    for name in (".", "TFrame", "TLabel", "TCheckbutton", "TRadiobutton"):
        style.configure(name, **common)
    style.configure("TLabelframe", background=palette["background"],
                    foreground=palette["foreground"], bordercolor=palette["border"])
    style.configure("TLabelframe.Label", **common)
    style.configure("TButton", background=palette["surface"], foreground=palette["foreground"],
                    bordercolor=palette["border"], focusthickness=1, focuscolor=palette["accent"])
    style.map("TButton", background=[("active", palette["accent"]),
                                     ("pressed", palette["selection"])],
              foreground=[("disabled", palette["muted"])])
    for name in ("TEntry", "TSpinbox", "TCombobox"):
        style.configure(name, fieldbackground=palette["field"], background=palette["field"],
                        foreground=palette["foreground"], insertcolor=palette["foreground"],
                        bordercolor=palette["border"], arrowcolor=palette["foreground"])
    style.map("TCombobox", fieldbackground=[("readonly", palette["field"])],
              foreground=[("readonly", palette["foreground"])],
              selectbackground=[("readonly", palette["selection"])],
              selectforeground=[("readonly", "#ffffff")])
    style.configure("TNotebook", background=palette["background"], bordercolor=palette["border"])
    style.configure("TNotebook.Tab", background=palette["surface"],
                    foreground=palette["foreground"], padding=(9, 5))
    style.map("TNotebook.Tab", background=[("selected", palette["accent"]),
                                           ("active", palette["selection"])],
              foreground=[("selected", "#ffffff"), ("active", "#ffffff")])
    style.configure("Treeview", background=palette["field"], fieldbackground=palette["field"],
                    foreground=palette["foreground"], bordercolor=palette["border"])
    style.map("Treeview", background=[("selected", palette["selection"])],
              foreground=[("selected", "#ffffff")])
    style.configure("Treeview.Heading", background=palette["surface"],
                    foreground=palette["foreground"], bordercolor=palette["border"])
    style.map("Treeview.Heading", background=[("active", palette["accent"])])
    style.configure("TScrollbar", background=palette["surface"],
                    troughcolor=palette["background"], arrowcolor=palette["foreground"],
                    bordercolor=palette["border"])

    def repaint_classic(widget: object) -> None:
        try:
            widget_class = widget.winfo_class()
            if widget_class == "Canvas":
                widget.configure(background=palette["background"])
            elif widget_class in {"Text", "Listbox"}:
                widget.configure(background=palette["field"], foreground=palette["foreground"],
                                 insertbackground=palette["foreground"],
                                 selectbackground=palette["selection"], selectforeground="#ffffff")
            children = widget.winfo_children()
        except Exception:
            return
        for child in children:
            repaint_classic(child)

    repaint_classic(root)
    return palette


def run_gui(initial_pid: int | None=None, initial_hotkeys_enabled: bool=False, *, application_factory, services) -> None:
    ELEPHANT_HOTKEY_SPECS = services.hotkeys
    Win10ReadLogger = services.logger_factory
    GlobalHotkeyManager = services.hotkey_manager
    import tkinter as tk
    from tkinter import messagebox, ttk, filedialog
    ui_language = {'code': detect_ui_language()}

    def ui_text(text: object) -> str:
        return translate_ui_text(text, ui_language['code'])
    root = tk.Tk()
    root.application_services = services
    view = TkViewPort(root)
    application = application_factory(view)
    root.application_controller = application
    ability_field_write_clicked = application.ability_field_write_clicked
    add_resource = application.add_resource
    add_resource_lock = application.add_resource_lock
    add_unit_lock = application.add_unit_lock
    ally_health_lock_tick = application.ally_health_lock_tick
    apply_locks_once = application.apply_locks_once
    call_async = application.call_async
    cancel_discovery = application.cancel_discovery
    clear_id_catalog_search = application.clear_id_catalog_search
    close_gui = application.close_gui
    confirm_elephant_action = application.confirm_elephant_action
    connect = application.connect
    copy_catalog_id_from_event = application.copy_catalog_id_from_event
    copy_selected_catalog_id = application.copy_selected_catalog_id
    elephant_add_ability = application.elephant_add_ability
    elephant_add_item = application.elephant_add_item
    elephant_add_six_artifacts = application.elephant_add_six_artifacts
    elephant_clear_inventory = application.elephant_clear_inventory
    elephant_create_unit = application.elephant_create_unit
    elephant_kill_owner_units = application.elephant_kill_owner_units
    elephant_prewarm = application.elephant_prewarm
    elephant_read_hero_level = application.elephant_read_hero_level
    elephant_remove_ability = application.elephant_remove_ability
    elephant_set_ability_level = application.elephant_set_ability_level
    elephant_set_game_paused = application.elephant_set_game_paused
    elephant_set_hero_level = application.elephant_set_hero_level
    elephant_set_scale = application.elephant_set_scale
    elephant_set_tech = application.elephant_set_tech
    elephant_set_xp_rate = application.elephant_set_xp_rate
    extension_add_backpack_equipment = application.extension_add_backpack_equipment
    extension_add_item = application.extension_add_item
    extension_add_talent_choice = application.extension_add_talent_choice
    extension_audit_equipment = application.extension_audit_equipment
    extension_destroy_clicked = application.extension_destroy_clicked
    extension_drop_clicked = application.extension_drop_clicked
    extension_duplicate_bag_item = application.extension_duplicate_bag_item
    extension_enable_any_slot = application.extension_enable_any_slot
    extension_equip_bag_to_slot = application.extension_equip_bag_to_slot
    extension_export_plans = application.extension_export_plans
    extension_grant_talent_point = application.extension_grant_talent_point
    extension_import_plans = application.extension_import_plans
    extension_refresh_talent_icons = application.extension_refresh_talent_icons
    extension_repair_bag_item = application.extension_repair_bag_item
    extension_repair_equipment_clicked = application.extension_repair_equipment_clicked
    extension_repair_equipment_state = application.extension_repair_equipment_state
    extension_reset_talents_clicked = application.extension_reset_talents_clicked
    extension_restore_all_loadouts = application.extension_restore_all_loadouts
    extension_restore_loadout = application.extension_restore_loadout
    extension_save_all_loadouts = application.extension_save_all_loadouts
    extension_save_loadout = application.extension_save_loadout
    extension_set_bag_charges = application.extension_set_bag_charges
    extension_talent_tree_selected = application.extension_talent_tree_selected
    extension_unequip_item = application.extension_unequip_item
    init = application.init
    item_field_write_clicked = application.item_field_write_clicked
    lock_tick = application.lock_tick
    on_resource_select = application.on_resource_select
    populate_locks = application.populate_locks
    populate_selection_candidates = application.populate_selection_candidates
    populate_unit_fields = application.populate_unit_fields
    rapid_build_tick = application.rapid_build_tick
    read_ability_field_snapshot = application.read_ability_field_snapshot
    read_item_field_snapshot = application.read_item_field_snapshot
    read_selection_candidate_fields = application.read_selection_candidate_fields
    read_unit_fields = application.read_unit_fields
    read_unit_native_selection = application.read_unit_native_selection
    read_unit_with_sound = application.read_unit_with_sound
    refresh_ability_field_tree = application.refresh_ability_field_tree
    refresh_elephant_hotkeys = application.refresh_elephant_hotkeys
    refresh_extension_snapshot = application.refresh_extension_snapshot
    refresh_id_catalog_tree = application.refresh_id_catalog_tree
    refresh_item_field_tree = application.refresh_item_field_tree
    refresh_resources = application.refresh_resources
    refresh_unit_candidates = application.refresh_unit_candidates
    remove_selected_lock = application.remove_selected_lock
    resize_hotkey_body = application.resize_hotkey_body
    select_ability_field = application.select_ability_field
    select_item_field = application.select_item_field
    selected_unit_field = application.selected_unit_field
    set_advanced_unit_field = application.set_advanced_unit_field
    set_all_elephant_hotkeys = application.set_all_elephant_hotkeys
    set_food_resource = application.set_food_resource
    set_resource = application.set_resource
    set_unit = application.set_unit
    start_operation_thread = application.start_operation_thread
    trainer = application.trainer
    update_hotkey_scrollregion = application.update_hotkey_scrollregion
    view.bind('messagebox', messagebox)
    view.bind('filedialog', filedialog)
    view.bind('ui_language', ui_language)
    view.bind('ui_text', ui_text, callback=True)
    view.bind('root', root)
    root.title(ui_text(f'魔兽争霸3重制版修改器 v{APP_VERSION} {PRODUCT_EDITION_LABEL} by B站 两杯沈梦溪'))
    root.geometry('1180x780')
    root.minsize(1040, 700)
    ui_style = ttk.Style(root)
    apply_ui_theme(root, ui_style, True)
    dark_mode = tk.BooleanVar(master=root, value=True)
    icon_path = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / 'assets' / 'app_icon.png'
    try:
        app_icon = tk.PhotoImage(file=str(icon_path))
        root.iconphoto(True, app_icon)
    except tk.TclError:
        app_icon = None

    class LocalizedStringVar(tk.StringVar):

        def __init__(self, value: str='') -> None:
            super().__init__(master=root)
            self._source_text = ''
            self.set(value)

        def set(self, value: object) -> None:
            self._source_text = '' if value is None else str(value)
            super().set(ui_text(self._source_text))

        def refresh(self) -> None:
            super().set(ui_text(self._source_text))

        def source_text(self) -> str:
            return self._source_text
    language_choice = tk.StringVar(value='中文' if ui_language['code'] == 'zh' else 'English')
    status = LocalizedStringVar(value='正在连接 Warcraft III...')
    view.bind('status', status)
    pid_var = tk.StringVar(value=str(initial_pid) if initial_pid is not None else '')
    view.bind('pid_var', pid_var)
    gold_current = tk.StringVar(value='')
    view.bind('gold_current', gold_current)
    lumber_current = tk.StringVar(value='')
    view.bind('lumber_current', lumber_current)
    food_current = tk.StringVar(value='')
    view.bind('food_current', food_current)
    food_cap_current = tk.StringVar(value='')
    view.bind('food_cap_current', food_cap_current)
    gold_target = tk.StringVar(value='')
    view.bind('gold_target', gold_target)
    lumber_target = tk.StringVar(value='')
    view.bind('lumber_target', lumber_target)
    food_used_target = tk.StringVar(value='')
    view.bind('food_used_target', food_used_target)
    food_cap_target = tk.StringVar(value='')
    view.bind('food_cap_target', food_cap_target)
    resource_delta = tk.StringVar(value='1000')
    view.bind('resource_delta', resource_delta)
    hp_current = tk.StringVar(value='')
    view.bind('hp_current', hp_current)
    hp_max_current = tk.StringVar(value='')
    view.bind('hp_max_current', hp_max_current)
    hp_regen_current = tk.StringVar(value='')
    view.bind('hp_regen_current', hp_regen_current)
    mp_current = tk.StringVar(value='')
    view.bind('mp_current', mp_current)
    mp_max_current = tk.StringVar(value='')
    view.bind('mp_max_current', mp_max_current)
    mp_regen_current = tk.StringVar(value='')
    view.bind('mp_regen_current', mp_regen_current)
    hp_target = tk.StringVar(value='')
    view.bind('hp_target', hp_target)
    mp_target = tk.StringVar(value='')
    view.bind('mp_target', mp_target)
    hp_regen_target = tk.StringVar(value='')
    view.bind('hp_regen_target', hp_regen_target)
    mp_regen_target = tk.StringVar(value='')
    view.bind('mp_regen_target', mp_regen_target)
    x_current = tk.StringVar(value='')
    view.bind('x_current', x_current)
    y_current = tk.StringVar(value='')
    view.bind('y_current', y_current)
    unit_type_id_current = tk.StringVar(value='')
    view.bind('unit_type_id_current', unit_type_id_current)
    x_target = tk.StringVar(value='')
    view.bind('x_target', x_target)
    y_target = tk.StringVar(value='')
    view.bind('y_target', y_target)
    unit_field_target = tk.StringVar(value='')
    view.bind('unit_field_target', unit_field_target)
    elephant_hero_level = tk.StringVar(value='1')
    view.bind('elephant_hero_level', elephant_hero_level)
    elephant_unit_scale = tk.StringVar(value='1.0')
    view.bind('elephant_unit_scale', elephant_unit_scale)
    elephant_unit_rawcode = tk.StringVar(value='')
    view.bind('elephant_unit_rawcode', elephant_unit_rawcode)
    elephant_item_rawcode = tk.StringVar(value='ckng')
    view.bind('elephant_item_rawcode', elephant_item_rawcode)
    artifact_plan_settings = services.artifact_settings()
    view.bind('artifact_plan_settings', artifact_plan_settings)
    elephant_ability_rawcode = tk.StringVar(value='AOsh')
    view.bind('elephant_ability_rawcode', elephant_ability_rawcode)
    elephant_ability_level = tk.StringVar(value='1')
    view.bind('elephant_ability_level', elephant_ability_level)
    ability_field_rawcode = tk.StringVar(value='AHhb')
    view.bind('ability_field_rawcode', ability_field_rawcode)
    ability_field_level = tk.StringVar(value='1')
    view.bind('ability_field_level', ability_field_level)
    ability_field_filter = tk.StringVar(value='')
    view.bind('ability_field_filter', ability_field_filter)
    ability_field_value = tk.StringVar(value='')
    view.bind('ability_field_value', ability_field_value)
    ability_field_summary = LocalizedStringVar(value='尚未读取技能字段')
    view.bind('ability_field_summary', ability_field_summary)
    ability_field_detail = LocalizedStringVar(value='')
    view.bind('ability_field_detail', ability_field_detail)
    ability_field_show_zero = tk.BooleanVar(value=True)
    view.bind('ability_field_show_zero', ability_field_show_zero)
    ability_field_show_unsupported = tk.BooleanVar(value=True)
    view.bind('ability_field_show_unsupported', ability_field_show_unsupported)
    item_field_slot = tk.StringVar(value='1')
    view.bind('item_field_slot', item_field_slot)
    item_field_filter = tk.StringVar(value='')
    view.bind('item_field_filter', item_field_filter)
    item_field_value = tk.StringVar(value='')
    view.bind('item_field_value', item_field_value)
    item_field_summary = LocalizedStringVar(value='尚未读取物品字段')
    view.bind('item_field_summary', item_field_summary)
    item_field_detail = LocalizedStringVar(value='')
    view.bind('item_field_detail', item_field_detail)
    item_field_show_zero = tk.BooleanVar(value=True)
    view.bind('item_field_show_zero', item_field_show_zero)
    item_field_show_unsupported = tk.BooleanVar(value=True)
    view.bind('item_field_show_unsupported', item_field_show_unsupported)
    extension_item_rawcode = tk.StringVar(value='')
    view.bind('extension_item_rawcode', extension_item_rawcode)
    extension_item_charges = tk.StringVar(value='1')
    view.bind('extension_item_charges', extension_item_charges)
    official_backpack_labels = tuple((f'{hero_name} ({rawcode})' for rawcode, (hero_name, _controller) in OFFICIAL_BACKPACKS.items()))
    official_backpack_by_label = {label: rawcode for label, rawcode in zip(official_backpack_labels, OFFICIAL_BACKPACKS)}
    view.bind('official_backpack_by_label', official_backpack_by_label)
    extension_backpack_choice = tk.StringVar(value='亡灵加雷克 (ebug)')
    view.bind('extension_backpack_choice', extension_backpack_choice)
    extension_loadout_name = tk.StringVar(value='套装1')
    view.bind('extension_loadout_name', extension_loadout_name)
    extension_loadout_choice = tk.StringVar(value='')
    view.bind('extension_loadout_choice', extension_loadout_choice)
    extension_talent_choice = tk.StringVar(value='')
    view.bind('extension_talent_choice', extension_talent_choice)
    extension_status = LocalizedStringVar(value='尚未读取 3.0 扩展状态')
    view.bind('extension_status', extension_status)
    id_catalog_queries = {kind: tk.StringVar(value='') for kind in ('item', 'ability', 'unit')}
    view.bind('id_catalog_queries', id_catalog_queries)
    id_catalog_statuses = {kind: LocalizedStringVar(value=f'记录数：{CATALOG_COUNTS[kind]}') for kind in ('item', 'ability', 'unit')}
    view.bind('id_catalog_statuses', id_catalog_statuses)
    id_catalog_trees: dict[str, ttk.Treeview] = {}
    view.bind('id_catalog_trees', id_catalog_trees)
    elephant_tech_rawcode = tk.StringVar(value='')
    view.bind('elephant_tech_rawcode', elephant_tech_rawcode)
    elephant_tech_level = tk.StringVar(value='1')
    view.bind('elephant_tech_level', elephant_tech_level)
    elephant_xp_rate = tk.StringVar(value='1.0')
    view.bind('elephant_xp_rate', elephant_xp_rate)
    elephant_game_speed = tk.StringVar(value='2')
    view.bind('elephant_game_speed', elephant_game_speed)
    elephant_item_charges = tk.StringVar(value='999')
    view.bind('elephant_item_charges', elephant_item_charges)
    elephant_resource_amount = tk.StringVar(value='100000')
    view.bind('elephant_resource_amount', elephant_resource_amount)
    elephant_mass_clone_count = tk.StringVar(value='10')
    view.bind('elephant_mass_clone_count', elephant_mass_clone_count)
    elephant_hero_attributes = tk.StringVar(value='20000')
    view.bind('elephant_hero_attributes', elephant_hero_attributes)
    elephant_skill_points = tk.StringVar(value='1')
    view.bind('elephant_skill_points', elephant_skill_points)
    elephant_reinforcement_rawcode = tk.StringVar(value='hcth')
    view.bind('elephant_reinforcement_rawcode', elephant_reinforcement_rawcode)
    elephant_preset_item_rawcode = tk.StringVar(value='amrc')
    view.bind('elephant_preset_item_rawcode', elephant_preset_item_rawcode)
    elephant_preset_tech_rawcode = tk.StringVar(value='Rost')
    view.bind('elephant_preset_tech_rawcode', elephant_preset_tech_rawcode)
    elephant_reset_ability_rawcode = tk.StringVar(value='Apxf')
    view.bind('elephant_reset_ability_rawcode', elephant_reset_ability_rawcode)
    elephant_auto_effect_count = tk.StringVar(value='5')
    view.bind('elephant_auto_effect_count', elephant_auto_effect_count)
    elephant_stat_values = {'hp_regen': tk.StringVar(value='0'), 'mp_regen': tk.StringVar(value='0'), 'attack_speed': tk.StringVar(value='1'), **{spec.key: tk.StringVar(value='150' if spec.baseline else '0') for spec in STAT_DETAIL_SPECS}}
    view.bind('elephant_stat_values', elephant_stat_values)
    elephant_hotkeys_enabled = tk.BooleanVar(value=initial_hotkeys_enabled)
    view.bind('elephant_hotkeys_enabled', elephant_hotkeys_enabled)
    elephant_hotkey_status = LocalizedStringVar(value='快捷键未启用')
    view.bind('elephant_hotkey_status', elephant_hotkey_status)
    elephant_hotkey_checks = {spec.name: tk.BooleanVar(value=True) for spec in ELEPHANT_HOTKEY_SPECS}
    view.bind('elephant_hotkey_checks', elephant_hotkey_checks)
    hotkey_manager = GlobalHotkeyManager()
    view.bind('hotkey_manager', hotkey_manager)
    operation_lock = threading.RLock()
    view.bind('operation_lock', operation_lock)
    operation_threads_lock = threading.Lock()
    view.bind('operation_threads_lock', operation_threads_lock)
    operation_threads: set[threading.Thread] = set()
    view.bind('operation_threads', operation_threads)
    state: dict[str, object] = {'trainer': None, 'resource_caches': {}, 'resource_labels': {}, 'selected_resource_iid': '', 'local_resource_iid': '', 'unit_fields': {}, 'selected_unit_identity': None, 'selected_unit_win10': False, 'selected_unit_type_id': 0, 'last_verified_unit_identity': None, 'selection_candidates': {}, 'manual_unit_identity': None, 'locks': {}, 'lock_busy': False, 'ally_health_lock': False, 'ally_health_lock_busy': False, 'ally_health_lock_trainer': None, 'rapid_build': False, 'rapid_build_busy': False, 'rapid_build_trainer': None, 'initial_connect_busy': False, 'active_operations': set(), 'elephant_game_paused': False, 'ability_field_snapshot': None, 'ability_field_rows': {}, 'item_field_snapshot': None, 'item_field_rows': {}, 'extension_snapshot': None, 'closing': False}
    view.bind('state', state)
    root.protocol('WM_DELETE_WINDOW', close_gui)
    hotkey_callbacks = application.hotkey_actions()
    view.bind('hotkey_callbacks', hotkey_callbacks)
    hotkey_specs_by_name = {spec.name: spec for spec in ELEPHANT_HOTKEY_SPECS}
    view.bind('hotkey_specs_by_name', hotkey_specs_by_name)
    hotkey_dangerous = {'explode_unit', 'drop_inventory', 'kill_owner_units', 'end_game', 'remove_all_abilities', 'instant_victory'}
    for name, variable in elephant_hotkey_checks.items():
        variable.set(name in hotkey_callbacks and name not in hotkey_dangerous)

    def build_id_catalog_tab(kind: str, title: str) -> None:
        tab = ttk.Frame(notebook, padding=10)
        notebook.add(tab, text=title)
        toolbar = ttk.Frame(tab)
        toolbar.grid(row=0, column=0, sticky='ew', pady=(0, 8))
        ttk.Label(toolbar, text='搜索 ID、中文名或英文名').grid(row=0, column=0, sticky='w')
        search_entry = ttk.Entry(toolbar, textvariable=id_catalog_queries[kind], width=36)
        search_entry.grid(row=0, column=1, sticky='ew', padx=(8, 6))
        search_entry.bind('<KeyRelease>', lambda _event, catalog_kind=kind: refresh_id_catalog_tree(catalog_kind))
        ttk.Button(toolbar, text='清空', command=lambda catalog_kind=kind: clear_id_catalog_search(catalog_kind)).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(toolbar, text='复制 ID', command=lambda catalog_kind=kind: copy_selected_catalog_id(catalog_kind)).grid(row=0, column=3)
        ttk.Label(toolbar, textvariable=id_catalog_statuses[kind]).grid(row=0, column=4, sticky='e', padx=(14, 0))
        toolbar.columnconfigure(1, weight=1)
        table_frame = ttk.Frame(tab)
        table_frame.grid(row=1, column=0, sticky='nsew')
        tree = ttk.Treeview(table_frame, columns=('rawcode', 'name_zh', 'name_en', 'category'), show='headings', height=20, selectmode='browse')
        for column, heading, width, stretch in (('rawcode', 'ID / Rawcode', 130, False), ('name_zh', '中文名称', 300, True), ('name_en', 'English Name', 360, True), ('category', '类别', 160, False)):
            tree.heading(column, text=heading)
            tree.column(column, width=width, minwidth=width, anchor='w', stretch=stretch)
        scroll = ttk.Scrollbar(table_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.grid(row=0, column=0, sticky='nsew')
        scroll.grid(row=0, column=1, sticky='ns')
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        tree.bind('<Double-1>', lambda event, catalog_kind=kind: copy_catalog_id_from_event(catalog_kind, event))
        id_catalog_trees[kind] = tree
        ttk.Label(tab, text='双击表格行可复制 ID。数据来源：W3x2LNI zhCN-1.32.8 与 war3-objectdata 英文社区快照；自定义地图对象不在通用目录内。', anchor='w', justify='left', wraplength=1080).grid(row=2, column=0, sticky='ew', pady=(8, 0))
        tab.rowconfigure(1, weight=1)
        tab.columnconfigure(0, weight=1)
        refresh_id_catalog_tree(kind)
    widget_text_sources: dict[object, str] = {}
    notebook_tab_sources: dict[tuple[object, str], str] = {}
    tree_heading_sources: dict[tuple[object, str], str] = {}

    def capture_translatable_widgets(widget: object) -> None:
        try:
            if 'text' in widget.keys():
                source = str(widget.cget('text'))
                if source:
                    widget_text_sources.setdefault(widget, source)
        except (AttributeError, tk.TclError):
            pass
        if isinstance(widget, ttk.Notebook):
            for tab_id in widget.tabs():
                key = (widget, str(tab_id))
                notebook_tab_sources.setdefault(key, str(widget.tab(tab_id, 'text')))
        if isinstance(widget, ttk.Treeview):
            for column in widget.cget('columns'):
                key = (widget, str(column))
                tree_heading_sources.setdefault(key, str(widget.heading(column, 'text')))
        try:
            children = widget.winfo_children()
        except (AttributeError, tk.TclError):
            return
        for child in children:
            capture_translatable_widgets(child)

    def refresh_language_dependent_rows() -> None:
        selections = {unit_field_tree: tuple(unit_field_tree.selection()), lock_tree: tuple(lock_tree.selection()), candidate_tree: tuple(candidate_tree.selection()), ability_field_tree: tuple(ability_field_tree.selection()), item_field_tree: tuple(item_field_tree.selection())}
        selections.update({tree: tuple(tree.selection()) for tree in id_catalog_trees.values()})
        fields = state.get('unit_fields')
        if isinstance(fields, dict) and fields:
            populate_unit_fields(list(fields.values()))
        locks = state.get('locks')
        if isinstance(locks, dict) and locks:
            populate_locks()
        candidates = state.get('selection_candidates')
        if isinstance(candidates, dict) and candidates:
            populate_selection_candidates(list(candidates.values()))
        if isinstance(state.get('ability_field_snapshot'), AbilityFieldSnapshot):
            refresh_ability_field_tree()
        if isinstance(state.get('item_field_snapshot'), ItemFieldSnapshot):
            refresh_item_field_tree()
        for kind in id_catalog_trees:
            refresh_id_catalog_tree(kind)
        for tree_widget, selected_items in selections.items():
            existing_items = tuple((item for item in selected_items if tree_widget.exists(item)))
            if existing_items:
                tree_widget.selection_set(existing_items)
                tree_widget.focus(existing_items[0])

    def refresh_gui_language() -> None:
        root.title(ui_text(f'魔兽争霸3重制版修改器 v{APP_VERSION} {PRODUCT_EDITION_LABEL} by B站 两杯沈梦溪'))
        capture_translatable_widgets(root)
        for widget, source in tuple(widget_text_sources.items()):
            try:
                widget.configure(text=ui_text(source))
            except tk.TclError:
                pass
        for (notebook_widget, tab_id), source in tuple(notebook_tab_sources.items()):
            try:
                notebook_widget.tab(tab_id, text=ui_text(source))
            except tk.TclError:
                pass
        for (tree_widget, column), source in tuple(tree_heading_sources.items()):
            try:
                tree_widget.heading(column, text=ui_text(source))
            except tk.TclError:
                pass
        for variable in (status, ability_field_summary, ability_field_detail, item_field_summary, item_field_detail, elephant_hotkey_status, *id_catalog_statuses.values()):
            variable.refresh()
        refresh_language_dependent_rows()
        save_extraction_tab.refresh_language()
        batch_edit_tab.refresh_language()
        extension_definition_panel.refresh_language()
        artifact_plan_panel.refresh_language()

    def on_language_changed(_event: object | None=None) -> None:
        ui_language['code'] = 'zh' if language_choice.get() == '中文' else 'en'
        refresh_gui_language()
    outer = ttk.Frame(root, padding=12)
    outer.pack(fill='both', expand=True)
    top = ttk.Frame(outer)
    top.pack(fill='x')
    ttk.Button(top, text='连接/刷新进程', command=lambda: call_async(connect)).pack(side='left')
    discovery_cancel_button = ttk.Button(top, text='取消自动定位', command=cancel_discovery, state='disabled')
    view.bind('discovery_cancel_button', discovery_cancel_button)
    discovery_cancel_button.pack(side='left', padx=(4, 0))
    read_unit_button = ttk.Button(top, text='读取所有选中单位 (Ctrl+F11)')
    read_unit_button.configure(command=lambda: batch_edit_tab.read_clicked() if notebook.select() == str(batch_edit_tab.frame) else call_async(read_unit_with_sound, 'read_unit', read_unit_button))
    read_unit_button.pack(side='left', padx=(12, 0))
    ttk.Checkbutton(top, text='启用全局快捷键', variable=elephant_hotkeys_enabled, command=refresh_elephant_hotkeys).pack(side='left', padx=(12, 0))
    ttk.Checkbutton(top, text='深色模式', variable=dark_mode, command=lambda: apply_ui_theme(root, ui_style, bool(dark_mode.get()))).pack(side='left', padx=(12, 0))
    ttk.Label(top, text='PID').pack(side='left', padx=(16, 4))
    ttk.Entry(top, textvariable=pid_var, width=10).pack(side='left')
    language_frame = ttk.Frame(top)
    language_frame.pack(side='right')
    ttk.Label(language_frame, text='语言').pack(side='left', padx=(8, 4))
    language_selector = ttk.Combobox(language_frame, textvariable=language_choice, values=('中文', 'English'), width=9, state='readonly')
    language_selector.pack(side='left')
    language_selector.bind('<<ComboboxSelected>>', on_language_changed)
    ttk.Label(top, textvariable=status).pack(side='right', padx=(8, 0))
    ttk.Label(top, text='大象功能灵感来源于经典版大象修改器，本软件完全免费，谨防倒卖').pack(side='left', padx=(12, 0))
    notebook = ttk.Notebook(outer)
    notebook.pack(fill='both', expand=True, pady=(12, 8))
    res = ttk.Frame(notebook, padding=10)
    notebook.add(res, text='玩家资源')
    ttk.Button(res, text='读取全部资源组', command=lambda: call_async(refresh_resources)).grid(row=0, column=0, pady=(0, 8), sticky='w')
    resource_frame = ttk.Frame(res)
    resource_frame.grid(row=1, column=0, columnspan=7, sticky='nsew', pady=(0, 10))
    res.rowconfigure(1, weight=1)
    res.columnconfigure(6, weight=1)
    resource_columns = ('group', 'gold', 'lumber', 'food', 'gold_address', 'lumber_address', 'source')
    resource_tree = ttk.Treeview(resource_frame, columns=resource_columns, show='headings', height=10)
    view.bind('resource_tree', resource_tree)
    resource_headings = {'group': ('资源组', 130), 'gold': ('金币', 80), 'lumber': ('木材', 80), 'food': ('人口', 80), 'gold_address': ('金币地址', 150), 'lumber_address': ('木材地址', 150), 'source': ('来源', 340)}
    for column, (heading, width) in resource_headings.items():
        resource_tree.heading(column, text=heading)
        resource_tree.column(column, width=width, anchor='w', stretch=column == 'source')
    resource_scroll = ttk.Scrollbar(resource_frame, orient='vertical', command=resource_tree.yview)
    resource_tree.configure(yscrollcommand=resource_scroll.set)
    resource_tree.grid(row=0, column=0, sticky='nsew')
    resource_scroll.grid(row=0, column=1, sticky='ns')
    resource_frame.rowconfigure(0, weight=1)
    resource_frame.columnconfigure(0, weight=1)
    resource_tree.bind('<<TreeviewSelect>>', on_resource_select)
    ttk.Label(res, text='当前金币').grid(row=2, column=0, sticky='w')
    ttk.Entry(res, textvariable=gold_current, width=12, state='readonly').grid(row=2, column=1, sticky='w')
    ttk.Label(res, text='目标金币').grid(row=2, column=2, sticky='w', padx=(16, 0))
    ttk.Entry(res, textvariable=gold_target, width=12).grid(row=2, column=3, sticky='w')
    ttk.Button(res, text='设置金币', command=lambda: call_async(lambda: set_resource('gold'))).grid(row=2, column=4, padx=8)
    ttk.Button(res, text='锁定金币', command=lambda: call_async(lambda: add_resource_lock('gold'))).grid(row=2, column=5, padx=4)
    ttk.Label(res, text='当前木材').grid(row=3, column=0, sticky='w', pady=8)
    ttk.Entry(res, textvariable=lumber_current, width=12, state='readonly').grid(row=3, column=1, sticky='w')
    ttk.Label(res, text='目标木材').grid(row=3, column=2, sticky='w', padx=(16, 0))
    ttk.Entry(res, textvariable=lumber_target, width=12).grid(row=3, column=3, sticky='w')
    ttk.Button(res, text='设置木材', command=lambda: call_async(lambda: set_resource('lumber'))).grid(row=3, column=4, padx=8)
    ttk.Button(res, text='锁定木材', command=lambda: call_async(lambda: add_resource_lock('lumber'))).grid(row=3, column=5, padx=4)
    ttk.Label(res, text='当前人口').grid(row=4, column=0, sticky='w', pady=8)
    ttk.Entry(res, textvariable=food_current, width=12, state='readonly').grid(row=4, column=1, sticky='w')
    ttk.Label(res, text='人口上限').grid(row=4, column=2, sticky='w', padx=(16, 0))
    ttk.Entry(res, textvariable=food_cap_current, width=12, state='readonly').grid(row=4, column=3, sticky='w')
    ttk.Label(res, text='目标当前人口').grid(row=5, column=0, sticky='w', pady=8)
    ttk.Entry(res, textvariable=food_used_target, width=12).grid(row=5, column=1, sticky='w')
    ttk.Button(res, text='设置当前人口', command=lambda: call_async(lambda: set_food_resource('food_used'))).grid(row=5, column=2, padx=8)
    ttk.Button(res, text='锁定当前人口', command=lambda: call_async(lambda: add_resource_lock('food_used'))).grid(row=5, column=3, padx=4)
    ttk.Label(res, text='目标人口上限').grid(row=6, column=0, sticky='w', pady=8)
    ttk.Entry(res, textvariable=food_cap_target, width=12).grid(row=6, column=1, sticky='w')
    ttk.Button(res, text='设置人口上限', command=lambda: call_async(lambda: set_food_resource('food_cap'))).grid(row=6, column=2, padx=8)
    ttk.Button(res, text='锁定人口上限', command=lambda: call_async(lambda: add_resource_lock('food_cap'))).grid(row=6, column=3, padx=4)
    ttk.Label(res, text='增量').grid(row=7, column=0, sticky='w', pady=(12, 0))
    ttk.Entry(res, textvariable=resource_delta, width=12).grid(row=7, column=1, sticky='w', pady=(12, 0))
    ttk.Button(res, text='金币 +/-', command=lambda: call_async(lambda: add_resource('gold'))).grid(row=7, column=2, pady=(12, 0))
    ttk.Button(res, text='木材 +/-', command=lambda: call_async(lambda: add_resource('lumber'))).grid(row=7, column=3, pady=(12, 0))
    ttk.Button(res, text='金木一起 +/-', command=lambda: call_async(lambda: add_resource('both'))).grid(row=7, column=4, pady=(12, 0), padx=8)
    unit = ttk.Frame(notebook, padding=10)
    notebook.add(unit, text='选中单位')
    ttk.Label(unit, text='当前生命').grid(row=0, column=0, sticky='w')
    ttk.Entry(unit, textvariable=hp_current, width=12).grid(row=0, column=1, sticky='w')
    ttk.Label(unit, text='生命上限').grid(row=0, column=2, sticky='w', padx=(16, 0))
    ttk.Entry(unit, textvariable=hp_max_current, width=12).grid(row=0, column=3, sticky='w')
    ttk.Label(unit, text='目标生命').grid(row=0, column=4, sticky='w', padx=(16, 0))
    ttk.Entry(unit, textvariable=hp_target, width=12).grid(row=0, column=5, sticky='w')
    ttk.Label(unit, text='当前魔法').grid(row=1, column=0, sticky='w', pady=8)
    ttk.Entry(unit, textvariable=mp_current, width=12).grid(row=1, column=1, sticky='w')
    ttk.Label(unit, text='魔法上限').grid(row=1, column=2, sticky='w', padx=(16, 0))
    ttk.Entry(unit, textvariable=mp_max_current, width=12).grid(row=1, column=3, sticky='w')
    ttk.Label(unit, text='目标魔法').grid(row=1, column=4, sticky='w', padx=(16, 0))
    ttk.Entry(unit, textvariable=mp_target, width=12).grid(row=1, column=5, sticky='w')
    ttk.Label(unit, text='HP 回复率').grid(row=2, column=0, sticky='w', pady=8)
    ttk.Entry(unit, textvariable=hp_regen_current, width=12).grid(row=2, column=1, sticky='w')
    ttk.Label(unit, text='目标 HP 回复率').grid(row=2, column=2, sticky='w', padx=(16, 0))
    ttk.Entry(unit, textvariable=hp_regen_target, width=12).grid(row=2, column=3, sticky='w')
    ttk.Label(unit, text='MP 回复率').grid(row=3, column=0, sticky='w', pady=8)
    ttk.Entry(unit, textvariable=mp_regen_current, width=12).grid(row=3, column=1, sticky='w')
    ttk.Label(unit, text='目标 MP 回复率').grid(row=3, column=2, sticky='w', padx=(16, 0))
    ttk.Entry(unit, textvariable=mp_regen_target, width=12).grid(row=3, column=3, sticky='w')
    ttk.Label(unit, text='当前 X').grid(row=4, column=0, sticky='w', pady=8)
    ttk.Entry(unit, textvariable=x_current, width=12).grid(row=4, column=1, sticky='w')
    ttk.Label(unit, text='当前 Y').grid(row=4, column=2, sticky='w', padx=(16, 0))
    ttk.Entry(unit, textvariable=y_current, width=12).grid(row=4, column=3, sticky='w')
    ttk.Label(unit, text='单位 ID').grid(row=4, column=4, sticky='w', padx=(16, 0))
    ttk.Entry(unit, textvariable=unit_type_id_current, width=12, state='readonly').grid(row=4, column=5, sticky='w')
    ttk.Label(unit, text='目标 X').grid(row=5, column=0, sticky='w', pady=8)
    ttk.Entry(unit, textvariable=x_target, width=12).grid(row=5, column=1, sticky='w')
    ttk.Label(unit, text='目标 Y').grid(row=5, column=2, sticky='w', padx=(16, 0))
    ttk.Entry(unit, textvariable=y_target, width=12).grid(row=5, column=3, sticky='w')
    ttk.Button(unit, text='写入选中单位', command=lambda: call_async(set_unit)).grid(row=6, column=0, pady=12, sticky='w')
    ttk.Button(unit, text='刷新字段表', command=lambda: call_async(read_unit_fields)).grid(row=6, column=1, pady=12, sticky='w')
    ttk.Button(unit, text='列出候选单位', command=lambda: call_async(refresh_unit_candidates)).grid(row=6, column=2, pady=12, sticky='w')
    ttk.Button(unit, text='读取所选候选', command=lambda: call_async(read_selection_candidate_fields)).grid(row=6, column=3, pady=12, sticky='w')
    ttk.Button(unit, text='Native定位', command=lambda: call_async(read_unit_native_selection)).grid(row=6, column=4, pady=12, sticky='w')
    candidate_frame = ttk.Frame(unit)
    candidate_frame.grid(row=7, column=0, columnspan=7, sticky='nsew', pady=(0, 8))
    candidate_columns = ('index', 'confidence', 'hp', 'mp', 'position', 'evidence', 'components', 'inventory', 'handle', 'owner', 'unit')
    candidate_tree = ttk.Treeview(candidate_frame, columns=candidate_columns, show='headings', height=5)
    view.bind('candidate_tree', candidate_tree)
    for column, heading, width in (('index', '#', 36), ('confidence', '可信度', 56), ('hp', '生命', 86), ('mp', '魔法', 86), ('position', '坐标', 90), ('evidence', 'refs/known', 82), ('components', '组件', 170), ('inventory', '物品槽', 220), ('handle', 'handle', 132), ('owner', 'owner', 132), ('unit', 'unit', 132)):
        candidate_tree.heading(column, text=heading)
        candidate_tree.column(column, width=width, anchor='w', stretch=column in {'components', 'inventory'})
    candidate_scroll = ttk.Scrollbar(candidate_frame, orient='vertical', command=candidate_tree.yview)
    candidate_tree.configure(yscrollcommand=candidate_scroll.set)
    candidate_tree.pack(side='left', fill='both', expand=True)
    candidate_scroll.pack(side='right', fill='y')
    candidate_tree.bind('<Double-1>', lambda _event: call_async(read_selection_candidate_fields))
    unit_field_frame = ttk.Frame(unit)
    unit_field_frame.grid(row=8, column=0, columnspan=7, sticky='nsew', pady=(4, 0))
    unit_field_columns = ('category', 'label', 'value', 'type', 'address', 'note')
    unit_field_tree = ttk.Treeview(unit_field_frame, columns=unit_field_columns, show='headings', height=11)
    view.bind('unit_field_tree', unit_field_tree)
    for column, heading, width in (('category', '分类', 80), ('label', '字段', 190), ('value', '当前值', 110), ('type', '类型', 60), ('address', '地址', 150), ('note', '备注', 260)):
        unit_field_tree.heading(column, text=heading)
        unit_field_tree.column(column, width=width, anchor='w')
    unit_field_scroll = ttk.Scrollbar(unit_field_frame, orient='vertical', command=unit_field_tree.yview)
    unit_field_tree.configure(yscrollcommand=unit_field_scroll.set)
    unit_field_tree.pack(side='left', fill='both', expand=True)
    unit_field_scroll.pack(side='right', fill='y')

    def on_unit_field_select(_event) -> None:
        try:
            field = selected_unit_field()
        except Exception:
            return
        if field.writable:
            unit_field_target.set(field.value_text())
    unit_field_tree.bind('<<TreeviewSelect>>', on_unit_field_select)
    ttk.Label(unit, text='字段目标值').grid(row=9, column=0, sticky='w', pady=(8, 0))
    ttk.Entry(unit, textvariable=unit_field_target, width=16).grid(row=9, column=1, sticky='w', pady=(8, 0))
    ttk.Button(unit, text='写入字段', command=lambda: call_async(set_advanced_unit_field)).grid(row=9, column=2, sticky='w', pady=(8, 0))
    ttk.Button(unit, text='锁定字段', command=lambda: call_async(add_unit_lock)).grid(row=9, column=3, sticky='w', pady=(8, 0))
    for col in range(7):
        unit.columnconfigure(col, weight=1 if col == 6 else 0)
    unit.rowconfigure(8, weight=1)
    from war3_batch_edit_ui import BatchEditTab
    batch_edit_tab = BatchEditTab(notebook, get_trainer=trainer, call_async=call_async, ui_text=ui_text, logger_factory=Win10ReadLogger)
    notebook.add(batch_edit_tab.frame, text='批量修改')
    locks_tab = ttk.Frame(notebook, padding=10)
    notebook.add(locks_tab, text='锁定列表')
    lock_tree = ttk.Treeview(locks_tab, columns=('scope', 'label', 'value'), show='headings', height=15)
    view.bind('lock_tree', lock_tree)
    for column, heading, width in (('scope', '类型', 110), ('label', '项目', 240), ('value', '锁定值', 140)):
        lock_tree.heading(column, text=heading)
        lock_tree.column(column, width=width, anchor='w')
    lock_scroll = ttk.Scrollbar(locks_tab, orient='vertical', command=lock_tree.yview)
    lock_tree.configure(yscrollcommand=lock_scroll.set)
    lock_tree.grid(row=0, column=0, columnspan=3, sticky='nsew')
    lock_scroll.grid(row=0, column=3, sticky='ns')
    ttk.Button(locks_tab, text='立即执行一次', command=lambda: call_async(lambda: (apply_locks_once(), '锁定项已执行一次')[1])).grid(row=1, column=0, sticky='w', pady=(10, 0))
    ttk.Button(locks_tab, text='解锁所选', command=lambda: call_async(remove_selected_lock)).grid(row=1, column=1, sticky='w', pady=(10, 0))
    locks_tab.columnconfigure(0, weight=1)
    locks_tab.rowconfigure(0, weight=1)
    ability_fields_tab = ttk.Frame(notebook, padding=10)
    notebook.add(ability_fields_tab, text='技能字段')
    ability_field_toolbar = ttk.Frame(ability_fields_tab)
    ability_field_toolbar.grid(row=0, column=0, sticky='ew', pady=(0, 8))
    ttk.Label(ability_field_toolbar, text='技能 ID').grid(row=0, column=0, sticky='w')
    ttk.Entry(ability_field_toolbar, textvariable=ability_field_rawcode, width=10).grid(row=0, column=1, sticky='w', padx=(6, 16))
    ttk.Label(ability_field_toolbar, text='字段等级').grid(row=0, column=2, sticky='w')
    ttk.Entry(ability_field_toolbar, textvariable=ability_field_level, width=7).grid(row=0, column=3, sticky='w', padx=(6, 16))
    ability_field_read_button = ttk.Button(ability_field_toolbar, text='读取可修改字段', command=lambda: call_async(read_ability_field_snapshot, operation_key='ability-field-read', busy_widget=ability_field_read_button, busy_text='正在解析技能实例并读取字段...'))
    ability_field_read_button.grid(row=0, column=4, sticky='w')
    ttk.Label(ability_field_toolbar, text='筛选').grid(row=0, column=5, sticky='e', padx=(24, 6))
    ability_field_filter_entry = ttk.Entry(ability_field_toolbar, textvariable=ability_field_filter, width=24)
    ability_field_filter_entry.grid(row=0, column=6, sticky='ew')
    ability_field_filter_entry.bind('<KeyRelease>', lambda _event: refresh_ability_field_tree())
    ttk.Checkbutton(ability_field_toolbar, text='显示零值', variable=ability_field_show_zero, command=refresh_ability_field_tree).grid(row=0, column=7, padx=(14, 0))
    ttk.Checkbutton(ability_field_toolbar, text='显示未开放', variable=ability_field_show_unsupported, command=refresh_ability_field_tree).grid(row=0, column=8, padx=(10, 0))
    ability_field_toolbar.columnconfigure(6, weight=1)
    ability_field_table_frame = ttk.Frame(ability_fields_tab)
    ability_field_table_frame.grid(row=1, column=0, sticky='nsew')
    ability_field_columns = ('field', 'type', 'scope', 'name', 'value', 'status')
    ability_field_tree = ttk.Treeview(ability_field_table_frame, columns=ability_field_columns, show='headings', height=18, selectmode='browse')
    view.bind('ability_field_tree', ability_field_tree)
    for column, heading, width, stretch in (('field', '字段', 72, False), ('type', '类型', 68, False), ('scope', '范围', 78, False), ('name', '字段名称', 480, True), ('value', '当前值', 130, False), ('status', '状态', 90, False)):
        ability_field_tree.heading(column, text=heading)
        ability_field_tree.column(column, width=width, minwidth=width, anchor='w', stretch=stretch)
    ability_field_scroll = ttk.Scrollbar(ability_field_table_frame, orient='vertical', command=ability_field_tree.yview)
    ability_field_tree.configure(yscrollcommand=ability_field_scroll.set)
    ability_field_tree.grid(row=0, column=0, sticky='nsew')
    ability_field_scroll.grid(row=0, column=1, sticky='ns')
    ability_field_table_frame.rowconfigure(0, weight=1)
    ability_field_table_frame.columnconfigure(0, weight=1)
    ability_field_tree.bind('<<TreeviewSelect>>', select_ability_field)
    ability_field_editor = ttk.Frame(ability_fields_tab)
    ability_field_editor.grid(row=2, column=0, sticky='ew', pady=(10, 0))
    ttk.Label(ability_field_editor, text='新值').grid(row=0, column=0, sticky='w')
    ttk.Entry(ability_field_editor, textvariable=ability_field_value, width=28).grid(row=0, column=1, sticky='w', padx=(6, 10))
    ability_field_write_button = ttk.Button(ability_field_editor, text='写入选中字段', command=ability_field_write_clicked)
    view.bind('ability_field_write_button', ability_field_write_button)
    ability_field_write_button.grid(row=0, column=2, sticky='w')
    ability_field_write_button.state(['disabled'])
    ttk.Label(ability_field_editor, textvariable=ability_field_detail, anchor='w').grid(row=1, column=0, columnspan=3, sticky='ew', pady=(6, 0))
    ability_field_editor.columnconfigure(2, weight=1)
    ttk.Label(ability_fields_tab, textvariable=ability_field_summary, anchor='w').grid(row=3, column=0, sticky='ew', pady=(8, 0))
    ability_fields_tab.rowconfigure(1, weight=1)
    ability_fields_tab.columnconfigure(0, weight=1)
    item_fields_tab = ttk.Frame(notebook, padding=10)
    notebook.add(item_fields_tab, text='物品字段')
    item_field_toolbar = ttk.Frame(item_fields_tab)
    item_field_toolbar.grid(row=0, column=0, sticky='ew', pady=(0, 8))
    ttk.Label(item_field_toolbar, text='物品槽位').grid(row=0, column=0, sticky='w')
    ttk.Spinbox(item_field_toolbar, textvariable=item_field_slot, from_=1, to=6, width=5).grid(row=0, column=1, sticky='w', padx=(6, 16))
    item_field_read_button = ttk.Button(item_field_toolbar, text='读取可修改字段', command=lambda: call_async(read_item_field_snapshot, operation_key='item-field-read', busy_widget=item_field_read_button, busy_text='正在解析物品实例并读取字段...'))
    item_field_read_button.grid(row=0, column=2, sticky='w')
    ttk.Label(item_field_toolbar, text='筛选').grid(row=0, column=3, sticky='e', padx=(24, 6))
    item_field_filter_entry = ttk.Entry(item_field_toolbar, textvariable=item_field_filter, width=24)
    item_field_filter_entry.grid(row=0, column=4, sticky='ew')
    item_field_filter_entry.bind('<KeyRelease>', lambda _event: refresh_item_field_tree())
    ttk.Checkbutton(item_field_toolbar, text='显示零值', variable=item_field_show_zero, command=refresh_item_field_tree).grid(row=0, column=5, padx=(14, 0))
    ttk.Checkbutton(item_field_toolbar, text='显示未开放', variable=item_field_show_unsupported, command=refresh_item_field_tree).grid(row=0, column=6, padx=(10, 0))
    item_field_toolbar.columnconfigure(4, weight=1)
    item_field_table_frame = ttk.Frame(item_fields_tab)
    item_field_table_frame.grid(row=1, column=0, sticky='nsew')
    item_field_columns = ('field', 'type', 'name', 'value', 'status')
    item_field_tree = ttk.Treeview(item_field_table_frame, columns=item_field_columns, show='headings', height=18, selectmode='browse')
    view.bind('item_field_tree', item_field_tree)
    for column, heading, width, stretch in (('field', '字段', 82, False), ('type', '类型', 78, False), ('name', '字段名称', 520, True), ('value', '当前值', 150, False), ('status', '状态', 100, False)):
        item_field_tree.heading(column, text=heading)
        item_field_tree.column(column, width=width, minwidth=width, anchor='w', stretch=stretch)
    item_field_scroll = ttk.Scrollbar(item_field_table_frame, orient='vertical', command=item_field_tree.yview)
    item_field_tree.configure(yscrollcommand=item_field_scroll.set)
    item_field_tree.grid(row=0, column=0, sticky='nsew')
    item_field_scroll.grid(row=0, column=1, sticky='ns')
    item_field_table_frame.rowconfigure(0, weight=1)
    item_field_table_frame.columnconfigure(0, weight=1)
    item_field_tree.bind('<<TreeviewSelect>>', select_item_field)
    item_field_editor = ttk.Frame(item_fields_tab)
    item_field_editor.grid(row=2, column=0, sticky='ew', pady=(10, 0))
    ttk.Label(item_field_editor, text='新值').grid(row=0, column=0, sticky='w')
    ttk.Entry(item_field_editor, textvariable=item_field_value, width=28).grid(row=0, column=1, sticky='w', padx=(6, 10))
    item_field_write_button = ttk.Button(item_field_editor, text='写入选中字段', command=item_field_write_clicked)
    view.bind('item_field_write_button', item_field_write_button)
    item_field_write_button.grid(row=0, column=2, sticky='w')
    item_field_write_button.state(['disabled'])
    ttk.Label(item_field_editor, textvariable=item_field_detail, anchor='w').grid(row=1, column=0, columnspan=3, sticky='ew', pady=(6, 0))
    item_field_editor.columnconfigure(2, weight=1)
    ttk.Label(item_fields_tab, textvariable=item_field_summary, anchor='w').grid(row=3, column=0, sticky='ew', pady=(8, 0))
    item_fields_tab.rowconfigure(1, weight=1)
    item_fields_tab.columnconfigure(0, weight=1)
    extension_tab = ttk.Frame(notebook, padding=10)
    notebook.add(extension_tab, text='3.0 扩展')
    extension_toolbar = ttk.Frame(extension_tab)
    extension_toolbar.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 8))
    extension_status_row = ttk.Frame(extension_toolbar)
    extension_status_row.pack(side='top', fill='x')
    extension_refresh_button = ttk.Button(extension_status_row, text='读取扩展状态', command=lambda: call_async(refresh_extension_snapshot, operation_key='extension-read', busy_widget=extension_refresh_button, busy_text='正在读取 3.0 扩展状态...'))
    extension_refresh_button.pack(side='left')
    ttk.Label(extension_status_row, textvariable=extension_status).pack(side='left', padx=(12, 0))
    from war3_extension_definition_ui import ExtensionDefinitionPanel
    extension_definition_panel = ExtensionDefinitionPanel(extension_toolbar, get_language=lambda: ui_language['code'], start_thread=start_operation_thread, is_closing=lambda: bool(state.get('closing')))
    extension_definition_panel.pack(side='top', fill='x', pady=(8, 0))
    extension_bag_frame = ttk.LabelFrame(extension_tab, text='30 格扩展背包', padding=8)
    extension_bag_frame.grid(row=1, column=0, sticky='nsew', padx=(0, 5), pady=(0, 8))
    extension_bag_tree = ttk.Treeview(extension_bag_frame, columns=('slot', 'rawcode', 'charges', 'handle'), show='headings', height=13, selectmode='browse')
    view.bind('extension_bag_tree', extension_bag_tree)
    for column, heading, width in (('slot', '槽位', 54), ('rawcode', '物品 ID', 86), ('charges', '数量', 70), ('handle', 'handle', 142)):
        extension_bag_tree.heading(column, text=heading)
        extension_bag_tree.column(column, width=width, anchor='w')
    extension_bag_scroll = ttk.Scrollbar(extension_bag_frame, orient='vertical', command=extension_bag_tree.yview)
    extension_bag_tree.configure(yscrollcommand=extension_bag_scroll.set)
    extension_bag_tree.grid(row=0, column=0, columnspan=5, sticky='nsew')
    extension_bag_scroll.grid(row=0, column=5, sticky='ns')
    ttk.Entry(extension_bag_frame, textvariable=extension_item_rawcode, width=10).grid(row=1, column=0, sticky='w', pady=(8, 0))
    ttk.Button(extension_bag_frame, text='添加物品', command=lambda: call_async(extension_add_item)).grid(row=1, column=1, sticky='w', padx=(6, 0), pady=(8, 0))
    ttk.Button(extension_bag_frame, text='修复物品状态', command=lambda: call_async(extension_repair_bag_item)).grid(row=1, column=2, columnspan=2, sticky='w', padx=(6, 0), pady=(8, 0))
    ttk.Entry(extension_bag_frame, textvariable=extension_item_charges, width=10).grid(row=2, column=0, sticky='w', pady=(6, 0))
    ttk.Button(extension_bag_frame, text='设置数量', command=lambda: call_async(extension_set_bag_charges)).grid(row=2, column=1, sticky='w', padx=(6, 0), pady=(6, 0))
    ttk.Button(extension_bag_frame, text='复制所选', command=lambda: call_async(extension_duplicate_bag_item)).grid(row=2, column=2, sticky='w', padx=(6, 0), pady=(6, 0))
    ttk.Button(extension_bag_frame, text='丢弃所选', command=extension_drop_clicked).grid(row=2, column=3, sticky='w', padx=(6, 0), pady=(6, 0))
    ttk.Button(extension_bag_frame, text='销毁所选', command=lambda: extension_destroy_clicked('bag')).grid(row=2, column=4, sticky='w', padx=(6, 0), pady=(6, 0))
    ttk.Combobox(extension_bag_frame, textvariable=extension_backpack_choice, values=official_backpack_labels, state='readonly', width=24).grid(row=3, column=0, columnspan=2, sticky='w', pady=(6, 0))
    ttk.Button(extension_bag_frame, text='添加官方背包装备', command=lambda: call_async(extension_add_backpack_equipment)).grid(row=3, column=2, columnspan=2, sticky='w', padx=(6, 0), pady=(6, 0))
    extension_bag_frame.rowconfigure(0, weight=1)
    extension_bag_frame.columnconfigure(0, weight=1)
    extension_equipment_frame = ttk.LabelFrame(extension_tab, text='9 槽装备', padding=8)
    extension_equipment_frame.grid(row=1, column=1, sticky='nsew', padx=(5, 0), pady=(0, 8))
    extension_equipment_tree = ttk.Treeview(extension_equipment_frame, columns=('slot', 'rawcode', 'type', 'charges', 'handle'), show='headings', height=13, selectmode='browse')
    view.bind('extension_equipment_tree', extension_equipment_tree)
    for column, heading, width in (('slot', '装备槽', 72), ('rawcode', '物品 ID', 86), ('type', '类型', 70), ('charges', '数量', 60), ('handle', 'handle', 130)):
        extension_equipment_tree.heading(column, text=heading)
        extension_equipment_tree.column(column, width=width, anchor='w')
    extension_equipment_tree.grid(row=0, column=0, columnspan=5, sticky='nsew')
    ttk.Button(extension_equipment_frame, text='卸下所选', command=lambda: call_async(extension_unequip_item)).grid(row=1, column=0, sticky='w', pady=(8, 0))
    ttk.Label(extension_equipment_frame, text='保存名称').grid(row=1, column=1, sticky='e', padx=(6, 0), pady=(8, 0))
    ttk.Entry(extension_equipment_frame, textvariable=extension_loadout_name, width=14).grid(row=1, column=2, sticky='w', padx=(6, 0), pady=(8, 0))
    ttk.Button(extension_equipment_frame, text='保存套装', command=lambda: call_async(extension_save_loadout)).grid(row=1, column=3, sticky='w', padx=(6, 0), pady=(8, 0))
    extension_loadout_box = ttk.Combobox(extension_equipment_frame, textvariable=extension_loadout_choice, state='readonly', width=14)
    view.bind('extension_loadout_box', extension_loadout_box)
    extension_loadout_box.grid(row=2, column=0, columnspan=2, sticky='w', pady=(6, 0))
    ttk.Button(extension_equipment_frame, text='销毁所选', command=lambda: extension_destroy_clicked('equipment')).grid(row=1, column=4, sticky='w', padx=(6, 0), pady=(8, 0))
    ttk.Button(extension_equipment_frame, text='恢复选中套装', command=lambda: call_async(extension_restore_loadout)).grid(row=2, column=2, sticky='w', padx=(6, 0), pady=(6, 0))
    ttk.Button(extension_equipment_frame, text='一键保存选中英雄', command=lambda: call_async(extension_save_all_loadouts)).grid(row=2, column=3, sticky='w', padx=(6, 0), pady=(6, 0))
    ttk.Button(extension_equipment_frame, text='审计装备', command=lambda: call_async(extension_audit_equipment)).grid(row=3, column=0, sticky='w', pady=(6, 0))
    ttk.Button(extension_equipment_frame, text='修复错槽', command=extension_repair_equipment_clicked).grid(row=3, column=1, sticky='w', padx=(6, 0), pady=(6, 0))
    ttk.Button(extension_equipment_frame, text='背包装入目标槽', command=lambda: call_async(extension_equip_bag_to_slot)).grid(row=3, column=2, sticky='w', padx=(6, 0), pady=(6, 0))
    ttk.Button(extension_equipment_frame, text='开启任意槽', command=lambda: call_async(extension_enable_any_slot)).grid(row=3, column=3, sticky='w', padx=(6, 0), pady=(6, 0))
    ttk.Button(extension_equipment_frame, text='一键恢复选中英雄', command=lambda: call_async(extension_restore_all_loadouts)).grid(row=4, column=0, columnspan=2, sticky='w', pady=(6, 0))
    ttk.Button(extension_equipment_frame, text='保存方案文件', command=extension_export_plans).grid(row=4, column=2, sticky='w', padx=(6, 0), pady=(6, 0))
    ttk.Button(extension_equipment_frame, text='从文件选择方案', command=extension_import_plans).grid(row=4, column=3, sticky='w', padx=(6, 0), pady=(6, 0))
    ttk.Button(extension_equipment_frame, text='一键修复装备状态', command=lambda: call_async(extension_repair_equipment_state)).grid(row=5, column=0, columnspan=2, sticky='w', pady=(6, 0))
    extension_equipment_frame.rowconfigure(0, weight=1)
    extension_equipment_frame.columnconfigure(0, weight=1)
    extension_talent_frame = ttk.LabelFrame(extension_tab, text='天赋', padding=8)
    extension_talent_frame.grid(row=2, column=0, columnspan=2, sticky='nsew')
    extension_talent_tree = ttk.Treeview(extension_talent_frame, columns=('hero', 'tier', 'choices', 'selected'), show='headings', height=8, selectmode='browse')
    view.bind('extension_talent_tree', extension_talent_tree)
    for column, heading, width, stretch in (('hero', '天赋树', 130, False), ('tier', '层', 42, False), ('choices', '候选', 250, True), ('selected', '已选择', 130, False)):
        extension_talent_tree.heading(column, text=heading)
        extension_talent_tree.column(column, width=width, anchor='w', stretch=stretch)
    extension_talent_tree.grid(row=0, column=0, columnspan=5, sticky='nsew')
    extension_talent_choice_box = ttk.Combobox(extension_talent_frame, textvariable=extension_talent_choice, state='readonly', width=10)
    view.bind('extension_talent_choice_box', extension_talent_choice_box)
    extension_talent_choice_box.grid(row=1, column=0, sticky='w', pady=(8, 0))
    extension_talent_tree.bind('<<TreeviewSelect>>', extension_talent_tree_selected)
    ttk.Button(extension_talent_frame, text='任意添加所选天赋', command=lambda: call_async(extension_add_talent_choice)).grid(row=1, column=1, sticky='w', padx=(6, 0), pady=(8, 0))
    ttk.Button(extension_talent_frame, text='增加 1 天赋点', command=lambda: call_async(extension_grant_talent_point)).grid(row=1, column=2, sticky='w', padx=(6, 0), pady=(8, 0))
    ttk.Button(extension_talent_frame, text='洗点', command=extension_reset_talents_clicked).grid(row=1, column=3, sticky='w', padx=(6, 0), pady=(8, 0))
    ttk.Button(extension_talent_frame, text='刷新天赋图标', command=lambda: call_async(extension_refresh_talent_icons)).grid(row=1, column=4, sticky='w', padx=(6, 0), pady=(8, 0))
    extension_talent_frame.rowconfigure(0, weight=1)
    extension_talent_frame.columnconfigure(0, weight=1)
    extension_tab.rowconfigure(1, weight=3)
    extension_tab.rowconfigure(2, weight=2)
    extension_tab.columnconfigure(0, weight=1, uniform='extension')
    extension_tab.columnconfigure(1, weight=1, uniform='extension')
    elephant_tab = ttk.Frame(notebook, padding=8)
    notebook.add(elephant_tab, text='大象功能')
    elephant_notebook = ttk.Notebook(elephant_tab)
    elephant_notebook.pack(fill='both', expand=True)
    elephant_controls_tab = ttk.Frame(elephant_notebook, padding=10)
    elephant_hotkeys_tab = ttk.Frame(elephant_notebook, padding=10)
    elephant_notebook.add(elephant_controls_tab, text='功能面板')
    from war3_artifact_plan_ui import ArtifactPlanPanel
    artifact_plan_panel = ArtifactPlanPanel(elephant_notebook, settings=artifact_plan_settings, get_language=lambda: ui_language['code'], on_apply=lambda plan: call_async(lambda: elephant_add_six_artifacts(plan), 'elephant:hotkey:six_artifacts', artifact_plan_panel.apply_button))
    view.bind('artifact_plan_panel', artifact_plan_panel)
    elephant_notebook.add(artifact_plan_panel, text='一键神器装备方案')
    elephant_notebook.add(elephant_hotkeys_tab, text='快捷键功能')
    ttk.Button(elephant_controls_tab, text='初始化/验证大象功能', command=lambda: call_async(elephant_prewarm, 'elephant:prewarm')).grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 10))
    world_frame = ttk.LabelFrame(elephant_controls_tab, text='地图与游戏', padding=10)
    world_frame.grid(row=1, column=0, sticky='nsew', padx=(0, 6), pady=(0, 8))
    ttk.Button(world_frame, text='开图', command=application.ui_reveal_map).grid(row=0, column=0, sticky='ew', padx=(0, 6), pady=3)
    ttk.Button(world_frame, text='关图', command=application.ui_hide_map).grid(row=0, column=1, sticky='ew', pady=3)
    ttk.Button(world_frame, text='暂停游戏', command=lambda: call_async(lambda: elephant_set_game_paused(True))).grid(row=1, column=0, sticky='ew', padx=(0, 6), pady=3)
    ttk.Button(world_frame, text='恢复游戏', command=lambda: call_async(lambda: elephant_set_game_paused(False))).grid(row=1, column=1, sticky='ew', pady=3)
    ttk.Button(world_frame, text='开启和平模式', command=application.ui_peace_on).grid(row=2, column=0, sticky='ew', padx=(0, 6), pady=3)
    ttk.Button(world_frame, text='关闭和平模式', command=application.ui_peace_off).grid(row=2, column=1, sticky='ew', pady=3)
    ttk.Button(world_frame, text='结束当前游戏', command=application.ui_end_game).grid(row=3, column=0, columnspan=2, sticky='ew', pady=(8, 3))
    world_frame.columnconfigure(0, weight=1)
    world_frame.columnconfigure(1, weight=1)
    hero_frame = ttk.LabelFrame(elephant_controls_tab, text='英雄与单位状态', padding=10)
    hero_frame.grid(row=1, column=1, sticky='nsew', padx=6, pady=(0, 8))
    ttk.Label(hero_frame, text='英雄等级').grid(row=0, column=0, sticky='w', pady=3)
    ttk.Entry(hero_frame, textvariable=elephant_hero_level, width=9).grid(row=0, column=1, sticky='w', pady=3)
    ttk.Button(hero_frame, text='读取', command=lambda: call_async(elephant_read_hero_level)).grid(row=0, column=2, padx=4, pady=3)
    ttk.Button(hero_frame, text='设置', command=lambda: call_async(elephant_set_hero_level)).grid(row=0, column=3, pady=3)
    ttk.Button(hero_frame, text='无敌', command=application.ui_invulnerable).grid(row=1, column=0, sticky='ew', pady=3)
    ttk.Button(hero_frame, text='取消无敌', command=application.ui_vulnerable).grid(row=1, column=1, columnspan=2, sticky='ew', padx=(6, 0), pady=3)
    ttk.Button(hero_frame, text='重置冷却', command=application.ui_reset_cooldown).grid(row=2, column=0, columnspan=3, sticky='ew', pady=3)
    ttk.Button(hero_frame, text='关闭碰撞', command=application.ui_pathing_off).grid(row=3, column=0, sticky='ew', pady=3)
    ttk.Button(hero_frame, text='开启碰撞', command=application.ui_pathing_on).grid(row=3, column=1, columnspan=2, sticky='ew', padx=(6, 0), pady=3)
    ttk.Button(hero_frame, text='暂停单位', command=application.ui_pause_unit).grid(row=4, column=0, sticky='ew', pady=3)
    ttk.Button(hero_frame, text='恢复单位', command=application.ui_resume_unit).grid(row=4, column=1, columnspan=2, sticky='ew', padx=(6, 0), pady=3)
    ttk.Label(hero_frame, text='单位大小').grid(row=5, column=0, sticky='w', pady=(8, 3))
    ttk.Entry(hero_frame, textvariable=elephant_unit_scale, width=9).grid(row=5, column=1, sticky='w', pady=(8, 3))
    ttk.Button(hero_frame, text='设置大小', command=lambda: call_async(elephant_set_scale)).grid(row=5, column=2, columnspan=2, sticky='ew', pady=(8, 3))
    target_frame = ttk.LabelFrame(elephant_controls_tab, text='目标单位', padding=10)
    target_frame.grid(row=1, column=2, sticky='nsew', padx=(6, 0), pady=(0, 8))
    ttk.Button(target_frame, text='获取控制权', command=application.ui_take_control).grid(row=0, column=0, columnspan=2, sticky='ew', pady=3)
    ttk.Button(target_frame, text='击杀单位', command=application.ui_kill_unit).grid(row=1, column=0, sticky='ew', padx=(0, 6), pady=3)
    ttk.Button(target_frame, text='爆炸单位', command=application.ui_explode_unit).grid(row=1, column=1, sticky='ew', pady=3)
    ttk.Button(target_frame, text='删除单位', command=application.ui_remove_unit).grid(row=2, column=0, columnspan=2, sticky='ew', pady=3)
    ttk.Button(target_frame, text='秒杀所属玩家全部单位', command=lambda: confirm_elephant_action('秒杀阵营', '该单位所属玩家的全部单位都会死亡，确定继续？', elephant_kill_owner_units)).grid(row=3, column=0, columnspan=2, sticky='ew', pady=(10, 3))
    target_frame.columnconfigure(0, weight=1)
    target_frame.columnconfigure(1, weight=1)
    create_frame = ttk.LabelFrame(elephant_controls_tab, text='创建与物品', padding=10)
    create_frame.grid(row=2, column=0, sticky='nsew', padx=(0, 6), pady=(0, 8))
    ttk.Label(create_frame, text='单位 ID').grid(row=0, column=0, sticky='w', pady=3)
    ttk.Entry(create_frame, textvariable=elephant_unit_rawcode, width=10).grid(row=0, column=1, sticky='w', pady=3)
    ttk.Button(create_frame, text='创建单位', command=lambda: call_async(lambda: elephant_create_unit(False))).grid(row=0, column=2, padx=(6, 0), pady=3)
    ttk.Button(create_frame, text='复制选中单位给自己', command=lambda: call_async(lambda: elephant_create_unit(True))).grid(row=1, column=0, columnspan=3, sticky='ew', pady=3)
    ttk.Label(create_frame, text='物品 ID').grid(row=2, column=0, sticky='w', pady=(10, 3))
    ttk.Entry(create_frame, textvariable=elephant_item_rawcode, width=10).grid(row=2, column=1, sticky='w', pady=(10, 3))
    ttk.Button(create_frame, text='添加物品', command=lambda: call_async(elephant_add_item)).grid(row=2, column=2, padx=(6, 0), pady=(10, 3))
    ttk.Button(create_frame, text='清空背包', command=lambda: confirm_elephant_action('清空背包', '当前选中单位背包内的物品会被删除，确定继续？', elephant_clear_inventory)).grid(row=3, column=0, columnspan=3, sticky='ew', pady=3)
    ability_frame = ttk.LabelFrame(elephant_controls_tab, text='技能', padding=10)
    ability_frame.grid(row=2, column=1, sticky='nsew', padx=6, pady=(0, 8))
    ttk.Label(ability_frame, text='技能 ID').grid(row=0, column=0, sticky='w', pady=3)
    ttk.Entry(ability_frame, textvariable=elephant_ability_rawcode, width=10).grid(row=0, column=1, sticky='w', pady=3)
    ttk.Label(ability_frame, text='等级').grid(row=0, column=2, sticky='w', padx=(8, 0), pady=3)
    ttk.Entry(ability_frame, textvariable=elephant_ability_level, width=7).grid(row=0, column=3, sticky='w', pady=3)
    ttk.Button(ability_frame, text='添加技能', command=lambda: call_async(elephant_add_ability)).grid(row=1, column=0, columnspan=2, sticky='ew', pady=3)
    ttk.Button(ability_frame, text='删除技能', command=lambda: call_async(elephant_remove_ability)).grid(row=1, column=2, columnspan=2, sticky='ew', padx=(6, 0), pady=3)
    ttk.Button(ability_frame, text='设置技能等级', command=lambda: call_async(elephant_set_ability_level)).grid(row=2, column=0, columnspan=4, sticky='ew', pady=3)
    player_frame = ttk.LabelFrame(elephant_controls_tab, text='玩家科技与经验', padding=10)
    player_frame.grid(row=2, column=2, sticky='nsew', padx=(6, 0), pady=(0, 8))
    ttk.Label(player_frame, text='科技 ID').grid(row=0, column=0, sticky='w', pady=3)
    ttk.Entry(player_frame, textvariable=elephant_tech_rawcode, width=10).grid(row=0, column=1, sticky='w', pady=3)
    ttk.Label(player_frame, text='等级').grid(row=0, column=2, sticky='w', padx=(8, 0), pady=3)
    ttk.Entry(player_frame, textvariable=elephant_tech_level, width=7).grid(row=0, column=3, sticky='w', pady=3)
    ttk.Button(player_frame, text='设置科技', command=lambda: call_async(elephant_set_tech)).grid(row=1, column=0, columnspan=4, sticky='ew', pady=3)
    ttk.Label(player_frame, text='经验倍率').grid(row=2, column=0, sticky='w', pady=(10, 3))
    ttk.Entry(player_frame, textvariable=elephant_xp_rate, width=10).grid(row=2, column=1, sticky='w', pady=(10, 3))
    ttk.Button(player_frame, text='设置倍率', command=lambda: call_async(elephant_set_xp_rate)).grid(row=2, column=2, columnspan=2, sticky='ew', padx=(6, 0), pady=(10, 3))
    for column in range(3):
        elephant_controls_tab.columnconfigure(column, weight=1, uniform='elephant')
    elephant_controls_tab.rowconfigure(1, weight=1)
    elephant_controls_tab.rowconfigure(2, weight=1)
    hotkey_toolbar = ttk.Frame(elephant_hotkeys_tab)
    hotkey_toolbar.pack(fill='x', pady=(0, 8))
    ttk.Button(hotkey_toolbar, text='全选可用', command=lambda: set_all_elephant_hotkeys(True)).pack(side='left', padx=(12, 4))
    ttk.Button(hotkey_toolbar, text='清空', command=lambda: set_all_elephant_hotkeys(False)).pack(side='left')
    ttk.Label(hotkey_toolbar, textvariable=elephant_hotkey_status).pack(side='right')
    hotkey_canvas = tk.Canvas(elephant_hotkeys_tab, borderwidth=0, highlightthickness=0, background=ttk.Style().lookup('TFrame', 'background') or root.cget('background'))
    view.bind('hotkey_canvas', hotkey_canvas)
    hotkey_scroll = ttk.Scrollbar(elephant_hotkeys_tab, orient='vertical', command=hotkey_canvas.yview)
    hotkey_canvas.configure(yscrollcommand=hotkey_scroll.set)
    hotkey_canvas.pack(side='left', fill='both', expand=True)
    hotkey_scroll.pack(side='right', fill='y')
    hotkey_body = ttk.Frame(hotkey_canvas)
    hotkey_window = hotkey_canvas.create_window((0, 0), window=hotkey_body, anchor='nw')
    view.bind('hotkey_window', hotkey_window)
    hotkey_canvas.bind('<Configure>', resize_hotkey_body)
    hotkey_body.bind('<Configure>', update_hotkey_scrollregion)
    hotkey_parameter_vars = {'hero_level': elephant_hero_level, 'unit_scale': elephant_unit_scale, 'item_charges': elephant_item_charges, 'add_ability': elephant_ability_rawcode, 'add_resources': elephant_resource_amount, 'mass_clone': elephant_mass_clone_count, 'ability_level': elephant_ability_level, 'remove_ability': elephant_ability_rawcode, 'reinforcements': elephant_reinforcement_rawcode, 'preset_item': elephant_preset_item_rawcode, 'preset_tech': elephant_preset_tech_rawcode, 'hero_attributes': elephant_hero_attributes, 'skill_points': elephant_skill_points, 'xp_rate': elephant_xp_rate, 'reset_ability': elephant_reset_ability_rawcode, 'fullscreen_auto': elephant_auto_effect_count, **{f'stat_{key}': variable for key, variable in elephant_stat_values.items()}}
    hotkeys_per_column = (len(ELEPHANT_HOTKEY_SPECS) + 2) // 3
    for index, spec in enumerate(ELEPHANT_HOTKEY_SPECS):
        column = index // hotkeys_per_column
        row = index % hotkeys_per_column
        item = ttk.Frame(hotkey_body)
        item.grid(row=row, column=column, sticky='ew', padx=(0 if column == 0 else 12, 0), pady=2)
        check = ttk.Checkbutton(item, text=spec.label, variable=elephant_hotkey_checks[spec.name], command=refresh_elephant_hotkeys)
        check.grid(row=0, column=0, sticky='w')
        parameter = hotkey_parameter_vars.get(spec.name)
        if spec.name == 'game_speed':
            ttk.Entry(item, textvariable=elephant_game_speed, width=6).grid(row=0, column=1, sticky='e', padx=(6, 0))
            ttk.Label(item, text='x').grid(row=0, column=2, padx=(2, 0))
        elif parameter is not None:
            ttk.Entry(item, textvariable=parameter, width=8).grid(row=0, column=1, sticky='e', padx=(6, 0))
        item.columnconfigure(0, weight=1)
    for column in range(3):
        hotkey_body.columnconfigure(column, weight=1, uniform='elephant-hotkeys')
    build_id_catalog_tab('item', '物品 ID')
    build_id_catalog_tab('ability', '技能 ID')
    build_id_catalog_tab('unit', '单位 ID')
    from war3_new_equipment_ui import NewEquipmentTab
    NewEquipmentTab(notebook)
    from war3_hero_skill_ui import HeroSkillTab
    HeroSkillTab(notebook)
    from war3_archive_fields_ui import ArchiveFieldsTab
    save_extraction_tab = ArchiveFieldsTab(notebook, get_trainer=trainer, start_thread=start_operation_thread, operation_lock=operation_lock, get_language=lambda: ui_language['code'], is_closing=lambda: bool(state.get('closing')))
    ttk.Label(outer, textvariable=status, anchor='w', wraplength=1000).pack(fill='x', pady=(0, 2))
    apply_ui_theme(root, ui_style, bool(dark_mode.get()))
    refresh_gui_language()
    root.after(100, init)
    root.after(1500, lock_tick)
    root.after(100, ally_health_lock_tick)
    root.after(1000, rapid_build_tick)
    view.validate(application.required_ports)
    root.mainloop()
