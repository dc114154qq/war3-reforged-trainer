"""Configuration and key parsing for the Warcraft III: Reforged hotkey tool."""

from __future__ import annotations

import copy
import ctypes
import json
import locale
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


APP_VERSION = "1.0.0"
APP_NAME_ZH = "魔兽争霸3重制版改键工具"
APP_NAME_EN = "Warcraft III: Reforged Hotkey Tool"

MODIFIER_ORDER = ("CTRL", "ALT", "SHIFT", "WIN")
MODIFIER_VKS = {
    "CTRL": 0x11,
    "ALT": 0x12,
    "SHIFT": 0x10,
    "WIN": 0x5B,
}

KEY_NAME_TO_VK: dict[str, int] = {
    "BACKSPACE": 0x08,
    "TAB": 0x09,
    "ENTER": 0x0D,
    "PAUSE": 0x13,
    "CAPSLOCK": 0x14,
    "ESC": 0x1B,
    "SPACE": 0x20,
    "PAGEUP": 0x21,
    "PAGEDOWN": 0x22,
    "END": 0x23,
    "HOME": 0x24,
    "LEFT": 0x25,
    "UP": 0x26,
    "RIGHT": 0x27,
    "DOWN": 0x28,
    "INSERT": 0x2D,
    "DELETE": 0x2E,
    "NUM0": 0x60,
    "NUM1": 0x61,
    "NUM2": 0x62,
    "NUM3": 0x63,
    "NUM4": 0x64,
    "NUM5": 0x65,
    "NUM6": 0x66,
    "NUM7": 0x67,
    "NUM8": 0x68,
    "NUM9": 0x69,
    "NUM*": 0x6A,
    "NUM+": 0x6B,
    "NUM-": 0x6D,
    "NUM.": 0x6E,
    "NUM/": 0x6F,
    "SEMICOLON": 0xBA,
    "EQUALS": 0xBB,
    "COMMA": 0xBC,
    "MINUS": 0xBD,
    "PERIOD": 0xBE,
    "SLASH": 0xBF,
    "BACKTICK": 0xC0,
    "LBRACKET": 0xDB,
    "BACKSLASH": 0xDC,
    "RBRACKET": 0xDD,
    "QUOTE": 0xDE,
}
KEY_NAME_TO_VK.update({chr(code): code for code in range(ord("A"), ord("Z") + 1)})
KEY_NAME_TO_VK.update({str(number): 0x30 + number for number in range(10)})
KEY_NAME_TO_VK.update({f"F{number}": 0x6F + number for number in range(1, 25)})

MOUSE_KEYS = {"MOUSE4", "MOUSE5", "MIDDLE"}
KEY_ALIASES = {
    "CONTROL": "CTRL",
    "CTL": "CTRL",
    "OPTION": "ALT",
    "WINDOWS": "WIN",
    "META": "WIN",
    "RETURN": "ENTER",
    "ESCAPE": "ESC",
    "PGUP": "PAGEUP",
    "PGDN": "PAGEDOWN",
    "DEL": "DELETE",
    "INS": "INSERT",
    "NUMPAD0": "NUM0",
    "NUMPAD1": "NUM1",
    "NUMPAD2": "NUM2",
    "NUMPAD3": "NUM3",
    "NUMPAD4": "NUM4",
    "NUMPAD5": "NUM5",
    "NUMPAD6": "NUM6",
    "NUMPAD7": "NUM7",
    "NUMPAD8": "NUM8",
    "NUMPAD9": "NUM9",
    "XBUTTON1": "MOUSE4",
    "XBUTTON2": "MOUSE5",
    "MOUSE 4": "MOUSE4",
    "MOUSE 5": "MOUSE5",
}


class KeyParseError(ValueError):
    pass


@dataclass(frozen=True)
class KeyStroke:
    key: str
    modifiers: frozenset[str] = frozenset()

    @property
    def is_mouse(self) -> bool:
        return self.key in MOUSE_KEYS

    @property
    def vk(self) -> int | None:
        return KEY_NAME_TO_VK.get(self.key)

    def canonical(self) -> str:
        parts = [modifier.title() for modifier in MODIFIER_ORDER if modifier in self.modifiers]
        parts.append(display_key_name(self.key))
        return "+".join(parts)


def display_key_name(key: str) -> str:
    return {
        "MOUSE4": "Mouse4",
        "MOUSE5": "Mouse5",
        "MIDDLE": "Middle",
        "PAGEUP": "PageUp",
        "PAGEDOWN": "PageDown",
        "BACKSPACE": "Backspace",
        "CAPSLOCK": "CapsLock",
        "SEMICOLON": ";",
        "EQUALS": "=",
        "COMMA": ",",
        "MINUS": "-",
        "PERIOD": ".",
        "SLASH": "/",
        "BACKTICK": "`",
        "LBRACKET": "[",
        "BACKSLASH": "\\",
        "RBRACKET": "]",
        "QUOTE": "'",
    }.get(key, key.title() if len(key) > 1 and not key.startswith("F") else key)


def parse_keystroke(value: str, *, allow_mouse: bool = True) -> KeyStroke:
    raw = str(value or "").strip()
    if not raw:
        raise KeyParseError("empty key")
    normalized = raw.upper().replace(" ", "")
    normalized = re.sub(r"\++", "+", normalized).strip("+")
    parts = normalized.split("+")
    modifiers: set[str] = set()
    key: str | None = None
    for part in parts:
        token = KEY_ALIASES.get(part, part)
        if token in MODIFIER_ORDER:
            modifiers.add(token)
            continue
        token = KEY_ALIASES.get(token, token)
        if key is not None:
            raise KeyParseError(f"multiple primary keys: {raw}")
        key = token
    if key is None:
        raise KeyParseError(f"missing primary key: {raw}")
    if key not in KEY_NAME_TO_VK and key not in MOUSE_KEYS:
        raise KeyParseError(f"unknown key: {key}")
    if key in MOUSE_KEYS and not allow_mouse:
        raise KeyParseError(f"mouse key is not valid here: {key}")
    return KeyStroke(key=key, modifiers=frozenset(modifiers))


@dataclass
class BindingConfig:
    binding_id: str
    source: str
    target: str
    enabled: bool = True
    smartcast: bool = False
    repeat: bool = False
    slot_index: int | None = None
    group: str = "command"


SLOT_GROUP_SPECS: dict[str, tuple[int, int]] = {
    "ability": (4, 3),
    "item": (2, 3),
    "spellbook": (4, 3),
    "shop": (4, 3),
}


def default_enabled_groups() -> dict[str, bool]:
    return {group: True for group in SLOT_GROUP_SPECS}

LEGACY_GROUP_NAMES = {
    "command": "ability",
    "inventory": "item",
}


@dataclass
class ProfileConfig:
    enabled: bool = True
    enforce_hotkeys: bool = True
    enabled_groups: dict[str, bool] = field(default_factory=default_enabled_groups)
    pause_in_chat: bool = True
    smartcast_delay_ms: int = 28
    repeat_delay_ms: int = 90
    self_cast_modifier: str = "CTRL"
    autocast_modifier: str = "SHIFT"
    suspend_hotkey: str = "Ctrl+F12"
    mouse_lock_enabled: bool = False
    mouse_lock_hotkey: str = "Ctrl+F10"
    right_repeat_enabled: bool = False
    right_repeat_delay_ms: int = 80
    camera_enabled: bool = True
    camera_distance_modifier: str = "CTRL"
    camera_rotation_modifier: str = "ALT"
    camera_incline_modifier: str = "SHIFT"
    camera_rotate_up_key: str = "DELETE"
    camera_rotate_down_key: str = "INSERT"
    camera_incline_up_key: str = "PAGEUP"
    camera_incline_down_key: str = "PAGEDOWN"
    bindings: list[BindingConfig] = field(default_factory=list)


@dataclass
class AppConfig:
    language: str = "auto"
    active_profile: str = "Default"
    profiles: dict[str, ProfileConfig] = field(default_factory=dict)


def default_bindings() -> list[BindingConfig]:
    defaults = {
        "ability": ("M", "S", "H", "A", "D", "F", "G", "T", "Q", "W", "E", "R"),
        "item": ("1", "2", "3", "4", "5", "6"),
        "spellbook": ("Q", "W", "E", "R", "A", "S", "D", "F", "Z", "X", "C", "V"),
        "shop": ("Q", "W", "E", "R", "A", "S", "D", "F", "Z", "X", "C", "V"),
    }
    result: list[BindingConfig] = []
    for group, keys in defaults.items():
        result.extend(
            BindingConfig(
                binding_id=f"{group}_{index + 1}",
                source=key,
                target=key,
                slot_index=index,
                group=group,
            )
            for index, key in enumerate(keys)
        )
    return result


def normalize_bindings(raw_bindings: list[BindingConfig]) -> list[BindingConfig]:
    """Migrate legacy bindings and guarantee every WFE-style slot exists."""
    defaults = {binding.binding_id: binding for binding in default_bindings()}
    for binding in raw_bindings:
        group = LEGACY_GROUP_NAMES.get(binding.group, binding.group)
        binding_id = binding.binding_id
        for old, new in LEGACY_GROUP_NAMES.items():
            prefix = f"{old}_"
            if binding_id.startswith(prefix):
                binding_id = f"{new}_{binding_id[len(prefix):]}"
                break
        migrated = copy.deepcopy(binding)
        migrated.group = group
        migrated.binding_id = binding_id
        if migrated.target:
            migrated.target = migrated.source
        if binding_id in defaults:
            defaults[binding_id] = migrated
    ordered: list[BindingConfig] = []
    for group in SLOT_GROUP_SPECS:
        count = SLOT_GROUP_SPECS[group][0] * SLOT_GROUP_SPECS[group][1]
        ordered.extend(defaults[f"{group}_{index + 1}"] for index in range(count))
    return ordered


def default_profile() -> ProfileConfig:
    profile = ProfileConfig()
    profile.bindings = default_bindings()
    return profile


def default_app_config() -> AppConfig:
    return AppConfig(profiles={"Default": default_profile()})


def detect_language(locale_name: str | None = None) -> str:
    if locale_name is None and sys.platform == "win32":
        try:
            buffer = ctypes.create_unicode_buffer(85)
            get_locale_name = ctypes.WinDLL("kernel32", use_last_error=True).GetUserDefaultLocaleName
            get_locale_name.argtypes = (ctypes.c_wchar_p, ctypes.c_int)
            get_locale_name.restype = ctypes.c_int
            if get_locale_name(buffer, len(buffer)):
                locale_name = buffer.value
        except (AttributeError, OSError):
            locale_name = None
    if locale_name is None:
        try:
            locale_name = locale.getlocale()[0]
        except (TypeError, ValueError):
            locale_name = None
    return "zh" if (locale_name or "").replace("_", "-").lower().startswith("zh") else "en"


def config_directory() -> Path:
    root = Path(os.environ.get("APPDATA", Path.home()))
    return root / "Twomengxi" / "War3ReforgedHotkeys"


class ConfigStore:
    def __init__(self, path: Path | None = None):
        self.path = path or config_directory() / "config.json"

    def load(self) -> AppConfig:
        if not self.path.exists():
            return default_app_config()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            config = app_config_from_dict(raw)
            validate_app_config(config)
            return config
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            backup = self.path.with_suffix(".invalid.json")
            try:
                backup.write_bytes(self.path.read_bytes())
            except OSError:
                pass
            return default_app_config()

    def save(self, config: AppConfig) -> None:
        validate_app_config(config)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(asdict(config), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, self.path)


def binding_from_dict(raw: dict[str, Any]) -> BindingConfig:
    allowed = {field_name for field_name in BindingConfig.__dataclass_fields__}
    values = {key: value for key, value in raw.items() if key in allowed}
    return BindingConfig(**values)


def profile_from_dict(raw: dict[str, Any]) -> ProfileConfig:
    allowed = {field_name for field_name in ProfileConfig.__dataclass_fields__}
    values = {
        key: value
        for key, value in raw.items()
        if key in allowed and key not in {"bindings", "enabled_groups"}
    }
    profile = ProfileConfig(**values)
    raw_groups = raw.get("enabled_groups")
    profile.enabled_groups = {
        group: bool(raw_groups.get(group, True)) if isinstance(raw_groups, dict) else True
        for group in SLOT_GROUP_SPECS
    }
    bindings = raw.get("bindings")
    parsed = [binding_from_dict(item) for item in bindings] if isinstance(bindings, list) else []
    profile.bindings = normalize_bindings(parsed)
    return profile


def app_config_from_dict(raw: dict[str, Any]) -> AppConfig:
    profiles_raw = raw.get("profiles") if isinstance(raw, dict) else None
    profiles = {
        str(name): profile_from_dict(value)
        for name, value in (profiles_raw or {}).items()
        if isinstance(value, dict)
    }
    if not profiles:
        profiles = {"Default": default_profile()}
    active = str(raw.get("active_profile", "Default"))
    if active not in profiles:
        active = next(iter(profiles))
    language = str(raw.get("language", "auto"))
    return AppConfig(language=language, active_profile=active, profiles=profiles)


def validate_app_config(config: AppConfig) -> None:
    if config.language not in {"auto", "zh", "en"}:
        raise ValueError("invalid language")
    if not config.profiles:
        raise ValueError("at least one profile is required")
    if config.active_profile not in config.profiles:
        raise ValueError("active profile does not exist")
    for profile in config.profiles.values():
        validate_profile(profile)


def validate_profile(profile: ProfileConfig) -> None:
    if set(profile.enabled_groups) != set(SLOT_GROUP_SPECS):
        raise ValueError("invalid enabled groups")
    if not 10 <= int(profile.smartcast_delay_ms) <= 500:
        raise ValueError("smartcast delay must be between 10 and 500 ms")
    if not 25 <= int(profile.repeat_delay_ms) <= 2000:
        raise ValueError("repeat delay must be between 25 and 2000 ms")
    if not 25 <= int(profile.right_repeat_delay_ms) <= 2000:
        raise ValueError("right-click repeat delay must be between 25 and 2000 ms")
    parse_keystroke(profile.suspend_hotkey, allow_mouse=False)
    parse_keystroke(profile.mouse_lock_hotkey, allow_mouse=False)
    for modifier in (
        profile.self_cast_modifier,
        profile.autocast_modifier,
        profile.camera_distance_modifier,
        profile.camera_rotation_modifier,
        profile.camera_incline_modifier,
    ):
        if modifier.upper() not in MODIFIER_ORDER:
            raise ValueError(f"invalid modifier: {modifier}")
    for key in (
        profile.camera_rotate_up_key,
        profile.camera_rotate_down_key,
        profile.camera_incline_up_key,
        profile.camera_incline_down_key,
    ):
        parse_keystroke(key, allow_mouse=False)
    seen: dict[tuple[str, KeyStroke], str] = {}
    for binding in profile.bindings:
        source = parse_keystroke(binding.source)
        if binding.target:
            parse_keystroke(binding.target, allow_mouse=False)
        context_key = (binding.group, source)
        group_enabled = profile.enabled_groups.get(binding.group, True)
        if context_key in seen and binding.enabled and group_enabled:
            raise ValueError(f"duplicate hotkey: {source.canonical()}")
        if binding.enabled and group_enabled:
            seen[context_key] = binding.binding_id
        if binding.group not in SLOT_GROUP_SPECS:
            raise ValueError(f"invalid binding group: {binding.group}")
        columns, rows = SLOT_GROUP_SPECS[binding.group]
        if binding.slot_index is None or not 0 <= binding.slot_index < columns * rows:
            raise ValueError("invalid slot index")


def clone_profile(profile: ProfileConfig) -> ProfileConfig:
    return copy.deepcopy(profile)


def binding_conflicts(bindings: list[BindingConfig]) -> dict[str, list[str]]:
    by_source: dict[tuple[str, KeyStroke], list[str]] = {}
    for binding in bindings:
        if not binding.enabled:
            continue
        try:
            source = parse_keystroke(binding.source)
        except KeyParseError:
            continue
        by_source.setdefault((binding.group, source), []).append(binding.binding_id)
    return {
        f"{group}: {source.canonical()}": ids
        for (group, source), ids in by_source.items()
        if len(ids) > 1
    }


TRANSLATIONS = {
    "zh": {
        "app_name": APP_NAME_ZH,
        "profile": "配置方案",
        "new_profile": "新建",
        "duplicate_profile": "复制",
        "delete_profile": "删除",
        "save_apply": "保存并应用",
        "enabled": "已启用",
        "disabled": "未启用",
        "game_not_found": "未检测到 Warcraft III",
        "game_background": "已检测到游戏，等待游戏窗口置前",
        "game_active": "Warcraft III 前台生效中",
        "suspended": "改键已临时暂停",
        "chat_paused": "聊天输入中，改键暂时停用",
        "bindings_tab": "按键",
        "mouse_tab": "鼠标与相机",
        "settings_tab": "设置",
        "ability_group": "普通技能",
        "item_group": "物品",
        "spellbook_group": "技能书 / 学习技能",
        "shop_group": "中立单位 / 商店",
        "slot": "格位",
        "trigger": "触发键",
        "game_key": "游戏键",
        "smartcast": "智能施法",
        "repeat": "按住连发",
        "command_slot": "命令 {row}-{column}",
        "inventory_slot": "物品 {number}",
        "general": "通用",
        "enforce_hotkeys": "修改游戏技能快捷键",
        "enabled_groups": "启用栏目",
        "pause_in_chat": "聊天输入时自动暂停",
        "smartcast_delay": "智能施法延迟 (ms)",
        "repeat_delay": "连发间隔 (ms)",
        "self_modifier": "自身施法修饰键",
        "autocast_modifier": "自动施法切换修饰键",
        "suspend_hotkey": "暂停/恢复热键",
        "right_repeat": "按住右键连续点击",
        "right_repeat_delay": "右键连点间隔 (ms)",
        "mouse_lock": "游戏前台时锁定鼠标",
        "mouse_lock_hotkey": "鼠标锁定开关热键",
        "camera_controls": "滚轮相机控制",
        "camera_enabled": "启用滚轮组合控制",
        "distance_modifier": "距离：修饰键 + 滚轮",
        "rotation_modifier": "旋转：修饰键 + 滚轮",
        "incline_modifier": "倾角：修饰键 + 滚轮",
        "wheel_up_key": "向上对应键",
        "wheel_down_key": "向下对应键",
        "language": "界面语言",
        "auto_language": "跟随系统",
        "chinese": "中文",
        "english": "English",
        "startup": "启动行为",
        "start_enabled": "启动后立即启用当前方案",
        "diagnostics": "运行状态",
        "refresh": "刷新",
        "process": "游戏进程",
        "foreground": "前台状态",
        "client_size": "客户区",
        "hook_state": "钩子状态",
        "running": "运行中",
        "stopped": "未运行",
        "yes": "是",
        "no": "否",
        "ready": "配置已载入",
        "saved": "已保存并应用配置方案“{name}”",
        "invalid_config": "配置无效",
        "invalid_key": "{field} 的按键无效：{value}",
        "duplicate_key": "存在重复触发键：{keys}",
        "profile_name": "配置方案名称",
        "profile_exists": "该配置方案已存在",
        "profile_required": "至少保留一个配置方案",
        "delete_confirm": "删除配置方案“{name}”？",
        "about_reference": "参考 WFE 的格位按键模型；每个命令格位独立设置按键和 SmartCast。",
        "press_slot_key": "请按下要绑定到该格位的按键，按 Esc 取消",
        "admin_note": "游戏若以管理员身份运行，本工具也需要管理员权限。",
        "profile_default": "默认",
        "error": "错误",
        "confirm": "确认",
        "mouse4": "鼠标侧键 1",
        "mouse5": "鼠标侧键 2",
    },
    "en": {
        "app_name": APP_NAME_EN,
        "profile": "Profile",
        "new_profile": "New",
        "duplicate_profile": "Duplicate",
        "delete_profile": "Delete",
        "save_apply": "Save & Apply",
        "enabled": "Enabled",
        "disabled": "Not enabled",
        "game_not_found": "Warcraft III was not detected",
        "game_background": "Game detected; waiting for its window to be foreground",
        "game_active": "Active in foreground Warcraft III",
        "suspended": "Hotkeys are temporarily suspended",
        "chat_paused": "Chat input is active; hotkeys are paused",
        "bindings_tab": "Keys",
        "mouse_tab": "Mouse & Camera",
        "settings_tab": "Settings",
        "ability_group": "Abilities",
        "item_group": "Items",
        "spellbook_group": "Spellbook / Ability Learn",
        "shop_group": "Neutral Units / Shops",
        "slot": "Slot",
        "trigger": "Trigger",
        "game_key": "Game key",
        "smartcast": "SmartCast",
        "repeat": "Hold repeat",
        "command_slot": "Command {row}-{column}",
        "inventory_slot": "Item {number}",
        "general": "General",
        "enforce_hotkeys": "Override game ability hotkeys",
        "enabled_groups": "Enabled sections",
        "pause_in_chat": "Pause automatically while typing chat",
        "smartcast_delay": "SmartCast delay (ms)",
        "repeat_delay": "Repeat interval (ms)",
        "self_modifier": "Self-cast modifier",
        "autocast_modifier": "Autocast-toggle modifier",
        "suspend_hotkey": "Suspend/resume hotkey",
        "right_repeat": "Repeat while right mouse is held",
        "right_repeat_delay": "Right-click interval (ms)",
        "mouse_lock": "Lock mouse while game is foreground",
        "mouse_lock_hotkey": "Mouse-lock toggle hotkey",
        "camera_controls": "Mouse-wheel Camera Controls",
        "camera_enabled": "Enable wheel combinations",
        "distance_modifier": "Distance: modifier + wheel",
        "rotation_modifier": "Rotation: modifier + wheel",
        "incline_modifier": "Incline: modifier + wheel",
        "wheel_up_key": "Wheel-up key",
        "wheel_down_key": "Wheel-down key",
        "language": "Interface language",
        "auto_language": "System default",
        "chinese": "中文",
        "english": "English",
        "startup": "Startup",
        "start_enabled": "Enable the current profile at startup",
        "diagnostics": "Runtime Status",
        "refresh": "Refresh",
        "process": "Game process",
        "foreground": "Foreground",
        "client_size": "Client area",
        "hook_state": "Hook state",
        "running": "Running",
        "stopped": "Stopped",
        "yes": "Yes",
        "no": "No",
        "ready": "Configuration loaded",
        "saved": "Saved and applied profile \"{name}\"",
        "invalid_config": "Invalid configuration",
        "invalid_key": "Invalid key in {field}: {value}",
        "duplicate_key": "Duplicate trigger keys: {keys}",
        "profile_name": "Profile name",
        "profile_exists": "That profile already exists",
        "profile_required": "At least one profile must remain",
        "delete_confirm": "Delete profile \"{name}\"?",
        "about_reference": "Uses WFE's slot binding model; every command slot has its own key and SmartCast switch.",
        "press_slot_key": "Press the key to bind to this slot, or Esc to cancel",
        "admin_note": "If the game runs as administrator, this tool must also run as administrator.",
        "profile_default": "Default",
        "error": "Error",
        "confirm": "Confirm",
        "mouse4": "Mouse side button 1",
        "mouse5": "Mouse side button 2",
    },
}


class Translator:
    def __init__(self, language: str):
        self.language_setting = language
        self.language = detect_language() if language == "auto" else language

    def set_language(self, language: str) -> None:
        self.language_setting = language
        self.language = detect_language() if language == "auto" else language

    def __call__(self, key: str, **values: Any) -> str:
        text = TRANSLATIONS.get(self.language, TRANSLATIONS["en"]).get(key, key)
        return text.format(**values) if values else text
