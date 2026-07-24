"""Windows input engine for the standalone Warcraft III: Reforged hotkey tool."""

from __future__ import annotations

import ctypes
import queue
import sys
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from war3_hotkey_model import (
    BindingConfig,
    KEY_NAME_TO_VK,
    MODIFIER_VKS,
    KeyStroke,
    ProfileConfig,
    parse_keystroke,
)
from war3_hotkey_native import (
    CommandContext,
    NativeFrameBridge,
    ORIGIN_FRAME_PORTRAIT,
    SelectionContext,
)


if sys.platform != "win32":
    raise RuntimeError("This hotkey engine requires Windows")


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
HC_ACTION = 0
WM_QUIT = 0x0012
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_MOUSEWHEEL = 0x020A
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
XBUTTON1 = 1
XBUTTON2 = 2
LLKHF_INJECTED = 0x10
LLMHF_INJECTED = 0x01
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_WHEEL = 0x0800
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
INJECTED_MARKER = 0x57465248  # WFRH
VK_TO_KEY_NAME = {vk: name for name, vk in KEY_NAME_TO_VK.items()}

ULONG_PTR = wintypes.WPARAM
LRESULT = ctypes.c_ssize_t


class POINT(ctypes.Structure):
    _fields_ = (("x", wintypes.LONG), ("y", wintypes.LONG))


class RECT(ctypes.Structure):
    _fields_ = (
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    )


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = (
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = (
        ("pt", POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class MOUSEINPUT(ctypes.Structure):
    _fields_ = (
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class KEYBDINPUT(ctypes.Structure):
    _fields_ = (
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = (
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    )


class INPUT_UNION(ctypes.Union):
    _fields_ = (("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT))


class INPUT(ctypes.Structure):
    _anonymous_ = ("union",)
    _fields_ = (("type", wintypes.DWORD), ("union", INPUT_UNION))


HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.SetWindowsHookExW.argtypes = (ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD)
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.CallNextHookEx.argtypes = (wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.CallNextHookEx.restype = LRESULT
user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.GetForegroundWindow.restype = wintypes.HWND
user32.IsWindow.argtypes = (wintypes.HWND,)
user32.IsWindow.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetClientRect.argtypes = (wintypes.HWND, ctypes.POINTER(RECT))
user32.GetClientRect.restype = wintypes.BOOL
user32.ClientToScreen.argtypes = (wintypes.HWND, ctypes.POINTER(POINT))
user32.ClientToScreen.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = (ctypes.POINTER(POINT),)
user32.GetCursorPos.restype = wintypes.BOOL
user32.SetCursorPos.argtypes = (ctypes.c_int, ctypes.c_int)
user32.SetCursorPos.restype = wintypes.BOOL
user32.ClipCursor.argtypes = (ctypes.POINTER(RECT),)
user32.ClipCursor.restype = wintypes.BOOL
user32.EnumWindows.argtypes = (WNDENUMPROC, wintypes.LPARAM)
user32.EnumWindows.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = (wintypes.HWND,)
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
user32.GetWindowTextW.restype = ctypes.c_int
user32.PostThreadMessageW.argtypes = (wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
user32.PostThreadMessageW.restype = wintypes.BOOL
kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = (
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
)
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL


@dataclass(frozen=True)
class GameWindowSnapshot:
    hwnd: int = 0
    pid: int = 0
    executable: str = ""
    title: str = ""
    foreground: bool = False
    client_rect: tuple[int, int, int, int] | None = None

    @property
    def found(self) -> bool:
        return bool(self.hwnd and self.pid)


class WarcraftWindowGuard:
    """Finds the real game window and gates every input action to it."""

    def __init__(self):
        self._lock = threading.RLock()
        self._snapshot = GameWindowSnapshot()
        self._last_scan = 0.0

    def snapshot(self, *, force: bool = False) -> GameWindowSnapshot:
        now = time.monotonic()
        with self._lock:
            if self._snapshot.found and self._cached_window_is_valid(self._snapshot):
                foreground = int(user32.GetForegroundWindow() or 0) == self._snapshot.hwnd
                self._snapshot = GameWindowSnapshot(
                    hwnd=self._snapshot.hwnd,
                    pid=self._snapshot.pid,
                    executable=self._snapshot.executable,
                    title=self._snapshot.title,
                    foreground=foreground,
                    client_rect=self._client_screen_rect(self._snapshot.hwnd),
                )
            elif force or now - self._last_scan >= 0.5:
                self._snapshot = self._scan()
                self._last_scan = now
            return self._snapshot

    @staticmethod
    def _cached_window_is_valid(snapshot: GameWindowSnapshot) -> bool:
        if not user32.IsWindow(ctypes.c_void_p(snapshot.hwnd)):
            return False
        pid = wintypes.DWORD()
        thread_id = user32.GetWindowThreadProcessId(
            ctypes.c_void_p(snapshot.hwnd),
            ctypes.byref(pid),
        )
        return bool(thread_id and int(pid.value) == snapshot.pid)

    def is_foreground(self) -> bool:
        # Low-level hook callbacks must not enumerate windows: doing so can
        # re-enter User32 while the hook is dispatching and freeze the UI.
        snapshot = self._snapshot
        return bool(snapshot.found and int(user32.GetForegroundWindow() or 0) == snapshot.hwnd)

    def normalized_cursor(self) -> tuple[float, float] | None:
        snapshot = self.snapshot(force=True)
        if not snapshot.foreground or snapshot.client_rect is None:
            return None
        point = POINT()
        if not user32.GetCursorPos(ctypes.byref(point)):
            return None
        left, top, right, bottom = snapshot.client_rect
        width = max(1, right - left)
        height = max(1, bottom - top)
        x = min(1.0, max(0.0, (point.x - left) / width))
        y = min(1.0, max(0.0, (point.y - top) / height))
        return x, y

    def point_from_normalized(self, point: tuple[float, float]) -> tuple[int, int] | None:
        snapshot = self.snapshot()
        if not snapshot.foreground or snapshot.client_rect is None:
            return None
        left, top, right, bottom = snapshot.client_rect
        return (
            round(left + (right - left) * float(point[0])),
            round(top + (bottom - top) * float(point[1])),
        )

    def _scan(self) -> GameWindowSnapshot:
        matches: list[tuple[int, int, str, str]] = []

        @WNDENUMPROC
        def enum_callback(hwnd: int, _lparam: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, len(buffer))
            title = buffer.value.strip()
            if title.lower() != "warcraft iii":
                return True
            pid_value = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_value))
            executable = self._process_path(pid_value.value)
            if Path(executable).name.lower() == "warcraft iii.exe":
                matches.append((int(hwnd), int(pid_value.value), executable, title))
            return True

        user32.EnumWindows(enum_callback, 0)
        if not matches:
            return GameWindowSnapshot()
        foreground_hwnd = int(user32.GetForegroundWindow() or 0)
        match = next((item for item in matches if item[0] == foreground_hwnd), matches[0])
        hwnd, pid, executable, title = match
        return GameWindowSnapshot(
            hwnd=hwnd,
            pid=pid,
            executable=executable,
            title=title,
            foreground=hwnd == foreground_hwnd,
            client_rect=self._client_screen_rect(hwnd),
        )

    @staticmethod
    def _process_path(pid: int) -> str:
        process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not process:
            return ""
        try:
            size = wintypes.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(size)):
                return buffer.value
            return ""
        finally:
            kernel32.CloseHandle(process)

    @staticmethod
    def _client_screen_rect(hwnd: int) -> tuple[int, int, int, int] | None:
        if not hwnd:
            return None
        rect = RECT()
        if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
            return None
        top_left = POINT(rect.left, rect.top)
        bottom_right = POINT(rect.right, rect.bottom)
        if not user32.ClientToScreen(hwnd, ctypes.byref(top_left)):
            return None
        if not user32.ClientToScreen(hwnd, ctypes.byref(bottom_right)):
            return None
        return top_left.x, top_left.y, bottom_right.x, bottom_right.y


class InputSender:
    def __init__(self, guard: WarcraftWindowGuard, on_error: Callable[[str], None] | None = None):
        self.guard = guard
        self.on_error = on_error or (lambda _message: None)
        self._lock = threading.RLock()

    def send_key(self, key: str, release_modifiers: frozenset[str] = frozenset()) -> bool:
        stroke = parse_keystroke(key, allow_mouse=False)
        if stroke.vk is None:
            return False
        with self._lock:
            inputs: list[INPUT] = []
            for modifier in release_modifiers:
                inputs.append(self._keyboard_input(MODIFIER_VKS[modifier], True))
            inputs.append(self._keyboard_input(stroke.vk, False))
            inputs.append(self._keyboard_input(stroke.vk, True))
            for modifier in reversed(tuple(release_modifiers)):
                inputs.append(self._keyboard_input(MODIFIER_VKS[modifier], False))
            return self._send(inputs)

    def send_click(self, button: str, *, point: tuple[int, int] | None = None) -> bool:
        with self._lock:
            original = POINT()
            moved = False
            if point is not None and user32.GetCursorPos(ctypes.byref(original)):
                moved = bool(user32.SetCursorPos(int(point[0]), int(point[1])))
            if button == "left":
                inputs = [self._mouse_input(MOUSEEVENTF_LEFTDOWN), self._mouse_input(MOUSEEVENTF_LEFTUP)]
            else:
                inputs = [self._mouse_input(MOUSEEVENTF_RIGHTDOWN), self._mouse_input(MOUSEEVENTF_RIGHTUP)]
            sent = self._send(inputs)
            if moved:
                user32.SetCursorPos(original.x, original.y)
            return sent

    def send_wheel(self, delta: int, release_modifiers: frozenset[str] = frozenset()) -> bool:
        with self._lock:
            inputs: list[INPUT] = []
            for modifier in release_modifiers:
                inputs.append(self._keyboard_input(MODIFIER_VKS[modifier], True))
            inputs.append(self._mouse_input(MOUSEEVENTF_WHEEL, delta))
            for modifier in reversed(tuple(release_modifiers)):
                inputs.append(self._keyboard_input(MODIFIER_VKS[modifier], False))
            return self._send(inputs)

    @staticmethod
    def _keyboard_input(vk: int, key_up: bool) -> INPUT:
        return INPUT(
            type=INPUT_KEYBOARD,
            ki=KEYBDINPUT(
                wVk=vk,
                wScan=0,
                dwFlags=KEYEVENTF_KEYUP if key_up else 0,
                time=0,
                dwExtraInfo=INJECTED_MARKER,
            ),
        )

    @staticmethod
    def _mouse_input(flags: int, data: int = 0) -> INPUT:
        return INPUT(
            type=INPUT_MOUSE,
            mi=MOUSEINPUT(
                dx=0,
                dy=0,
                mouseData=data & 0xFFFFFFFF,
                dwFlags=flags,
                time=0,
                dwExtraInfo=INJECTED_MARKER,
            ),
        )

    def _send(self, inputs: list[INPUT]) -> bool:
        if not inputs or not self.guard.is_foreground():
            return False
        array = (INPUT * len(inputs))(*inputs)
        sent = int(user32.SendInput(len(inputs), array, ctypes.sizeof(INPUT)))
        if sent != len(inputs):
            error = ctypes.get_last_error()
            self.on_error(f"SendInput {sent}/{len(inputs)} (WinError {error})")
            return False
        return True


@dataclass(frozen=True)
class CompiledBinding:
    config: BindingConfig
    source: KeyStroke
    target: KeyStroke


@dataclass(frozen=True)
class BindingAction:
    binding: CompiledBinding
    modifiers: frozenset[str]
    send_target: bool
    smartcast: bool
    self_cast: bool
    autocast_toggle: bool


def plan_binding_action(binding: CompiledBinding, modifiers: frozenset[str], profile: ProfileConfig) -> BindingAction:
    self_modifier = profile.self_cast_modifier.upper()
    auto_modifier = profile.autocast_modifier.upper()
    self_cast = self_modifier in modifiers and self_modifier not in binding.source.modifiers
    autocast_toggle = (
        binding.config.group == "ability"
        and auto_modifier in modifiers
        and auto_modifier not in binding.source.modifiers
    )
    passthrough_target = (
        binding.source.key == binding.target.key
        and not binding.source.modifiers
        and not binding.config.repeat
        and not self_cast
        and not autocast_toggle
    )
    return BindingAction(
        binding=binding,
        modifiers=modifiers,
        send_target=not passthrough_target and not autocast_toggle,
        smartcast=bool(binding.config.smartcast and not autocast_toggle),
        self_cast=self_cast,
        autocast_toggle=autocast_toggle,
    )


def command_context_for(command: CommandContext, selection: SelectionContext) -> str:
    if command.submenu_active:
        return "spellbook"
    if selection.neutral_selected:
        return "shop"
    return "ability"


NATIVE_MOUSE_KEYS = {"MIDDLE": 4, "MOUSE4": 5, "MOUSE5": 6}
NATIVE_META_KEYS = {"CTRL": 1, "SHIFT": 2, "ALT": 4}


def native_ability_hotkeys(profile: ProfileConfig) -> tuple[tuple[int, int, int, int], ...]:
    by_slot = {
        binding.slot_index: binding
        for binding in profile.bindings
        if binding.group == "ability" and binding.slot_index is not None
    }
    result = []
    for slot_index in range(12):
        binding = by_slot.get(slot_index)
        if binding is None:
            raise ValueError(f"Missing ability slot {slot_index}")
        stroke = parse_keystroke(binding.source)
        key = stroke.vk if stroke.vk is not None else NATIVE_MOUSE_KEYS.get(stroke.key)
        if key is None:
            raise ValueError(f"Unsupported native ability key: {binding.source}")
        meta = sum(NATIVE_META_KEYS.get(modifier, 0) for modifier in stroke.modifiers)
        result.append((slot_index // 4, slot_index % 4, int(key), meta))
    return tuple(result)


class HotkeyEngine:
    """Low-level input hooks with all game actions serialized off the hook thread."""

    def __init__(
        self,
        profile: ProfileConfig,
        *,
        guard: WarcraftWindowGuard | None = None,
        on_state: Callable[[str], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        frame_bridge: NativeFrameBridge | None = None,
    ):
        self.guard = guard or WarcraftWindowGuard()
        self.on_state = on_state or (lambda _state: None)
        self.on_error = on_error or (lambda _message: None)
        self.sender = InputSender(self.guard, self.on_error)
        self.frame_bridge = frame_bridge or NativeFrameBridge()
        self._profile_lock = threading.RLock()
        self._profile = profile
        self._keyboard_bindings: dict[int, list[CompiledBinding]] = {}
        self._mouse_bindings: dict[str, list[CompiledBinding]] = {}
        self._compile_profile(profile)
        self._actions: queue.Queue[BindingAction | tuple[str, object] | None] = queue.Queue()
        self._stop_event = threading.Event()
        self._hook_ready = threading.Event()
        self._hook_thread: threading.Thread | None = None
        self._action_thread: threading.Thread | None = None
        self._maintenance_thread: threading.Thread | None = None
        self._native_thread: threading.Thread | None = None
        self._hook_thread_id = 0
        self._keyboard_hook = wintypes.HHOOK()
        self._mouse_hook = wintypes.HHOOK()
        self._keyboard_proc_ref: HOOKPROC | None = None
        self._mouse_proc_ref: HOOKPROC | None = None
        self._physical_keys: set[int] = set()
        self._active_binding_keys: dict[tuple[str, int], CompiledBinding] = {}
        self._repeat_due: dict[str, float] = {}
        self._right_down = False
        self._right_repeat_due = 0.0
        self._chat_mode = False
        self._suspended = False
        self._toggle_down: set[str] = set()
        self._last_state = ""
        self._clip_active = False
        self._capture_lock = threading.RLock()
        self._capture_callback: Callable[[str | None], None] | None = None
        self._capture_suppressed_keys: set[int] = set()
        self._capture_suppressed_mouse: set[str] = set()
        self._command_context = "ability"
        self._profile_revision = 0

    @property
    def running(self) -> bool:
        return bool(self._hook_thread and self._hook_thread.is_alive() and self._hook_ready.is_set())

    @property
    def suspended(self) -> bool:
        return self._suspended

    @property
    def chat_mode(self) -> bool:
        return self._chat_mode

    def apply_profile(self, profile: ProfileConfig) -> None:
        with self._profile_lock:
            self._profile = profile
            self._compile_profile(profile)
            self._profile_revision += 1
            self._repeat_due.clear()
            self._active_binding_keys.clear()
            self._chat_mode = False
            self._suspended = False

    def begin_key_capture(self, callback: Callable[[str | None], None]) -> None:
        with self._capture_lock:
            self._capture_callback = callback
            self._capture_suppressed_keys.clear()
            self._capture_suppressed_mouse.clear()

    def cancel_key_capture(self) -> None:
        with self._capture_lock:
            self._capture_callback = None

    def start(self) -> None:
        if self.running:
            return
        self._stop_event.clear()
        self._hook_ready.clear()
        self._action_thread = threading.Thread(target=self._action_loop, name="war3-hotkey-actions", daemon=True)
        self._maintenance_thread = threading.Thread(target=self._maintenance_loop, name="war3-hotkey-maintenance", daemon=True)
        self._native_thread = threading.Thread(target=self._native_loop, name="war3-hotkey-native", daemon=True)
        self._hook_thread = threading.Thread(target=self._hook_loop, name="war3-hotkey-hooks", daemon=True)
        self._action_thread.start()
        self._maintenance_thread.start()
        self._native_thread.start()
        self._hook_thread.start()
        if not self._hook_ready.wait(3.0):
            raise RuntimeError("input hook startup timed out")

    def stop(self) -> None:
        self._stop_event.set()
        self._actions.put(None)
        if self._hook_thread_id:
            user32.PostThreadMessageW(self._hook_thread_id, WM_QUIT, 0, 0)
        for thread in (self._hook_thread, self._maintenance_thread, self._native_thread, self._action_thread):
            if thread and thread.is_alive() and thread is not threading.current_thread():
                thread.join(timeout=2.0)
        self._release_cursor_clip()
        self.frame_bridge.close()
        self._hook_ready.clear()

    def status_snapshot(self) -> dict[str, object]:
        game = self.guard.snapshot(force=True)
        return {
            "running": self.running,
            "suspended": self._suspended,
            "chat_mode": self._chat_mode,
            "native_ready": self.frame_bridge.ready,
            "command_context": self._command_context,
            "game": game,
        }

    def _compile_profile(self, profile: ProfileConfig) -> None:
        keyboard: dict[int, list[CompiledBinding]] = {}
        mouse: dict[str, list[CompiledBinding]] = {}
        for config in profile.bindings:
            if not config.enabled or not profile.enabled_groups.get(config.group, True):
                continue
            source = parse_keystroke(config.source)
            target = parse_keystroke(config.target, allow_mouse=False)
            compiled = CompiledBinding(config=config, source=source, target=target)
            if source.is_mouse:
                mouse.setdefault(source.key, []).append(compiled)
            elif source.vk is not None:
                keyboard.setdefault(source.vk, []).append(compiled)
        for values in keyboard.values():
            values.sort(key=lambda item: len(item.source.modifiers), reverse=True)
        for values in mouse.values():
            values.sort(key=lambda item: len(item.source.modifiers), reverse=True)
        self._keyboard_bindings = keyboard
        self._mouse_bindings = mouse

    def _hook_loop(self) -> None:
        self._hook_thread_id = threading.get_native_id()
        self._keyboard_proc_ref = HOOKPROC(self._keyboard_callback)
        self._mouse_proc_ref = HOOKPROC(self._mouse_callback)
        module = kernel32.GetModuleHandleW(None)
        self._keyboard_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._keyboard_proc_ref, module, 0)
        self._mouse_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._mouse_proc_ref, module, 0)
        if not self._keyboard_hook or not self._mouse_hook:
            error = ctypes.get_last_error()
            self.on_error(f"SetWindowsHookExW failed (WinError {error})")
            self._hook_ready.set()
            return
        self._hook_ready.set()
        message = wintypes.MSG()
        while not self._stop_event.is_set() and user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
        if self._keyboard_hook:
            user32.UnhookWindowsHookEx(self._keyboard_hook)
        if self._mouse_hook:
            user32.UnhookWindowsHookEx(self._mouse_hook)
        self._keyboard_hook = wintypes.HHOOK()
        self._mouse_hook = wintypes.HHOOK()

    def _keyboard_callback(self, code: int, wparam: int, lparam: int) -> int:
        if code != HC_ACTION:
            return user32.CallNextHookEx(self._keyboard_hook, code, wparam, lparam)
        event = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        if event.flags & LLKHF_INJECTED or int(event.dwExtraInfo) == INJECTED_MARKER:
            return user32.CallNextHookEx(self._keyboard_hook, code, wparam, lparam)
        vk = int(event.vkCode)
        is_down = int(wparam) in {WM_KEYDOWN, WM_SYSKEYDOWN}
        is_up = int(wparam) in {WM_KEYUP, WM_SYSKEYUP}
        if not is_down and not is_up:
            return user32.CallNextHookEx(self._keyboard_hook, code, wparam, lparam)
        if is_down:
            was_down = vk in self._physical_keys
            self._physical_keys.add(vk)
        else:
            was_down = vk in self._physical_keys
            self._physical_keys.discard(vk)
        modifiers = self._current_modifiers()
        if self._handle_key_capture(vk, is_down, is_up, was_down, modifiers):
            return 1
        game_foreground = self.guard.is_foreground()

        if game_foreground and self._handle_toggle_key(vk, is_down, is_up, modifiers):
            return 1

        with self._profile_lock:
            profile = self._profile
            enabled = profile.enabled and not self._suspended
            pause_in_chat = profile.pause_in_chat

        if game_foreground and pause_in_chat and vk == KEY_NAME_TO_VK["ENTER"] and is_down and not was_down:
            self._chat_mode = not self._chat_mode
            self._publish_state()
            return user32.CallNextHookEx(self._keyboard_hook, code, wparam, lparam)
        if game_foreground and pause_in_chat and vk == KEY_NAME_TO_VK["ESC"] and is_down:
            self._chat_mode = False

        identity = ("keyboard", vk)
        if is_up and identity in self._active_binding_keys:
            binding = self._active_binding_keys.pop(identity)
            self._repeat_due.pop(binding.config.binding_id, None)
            return 1

        if not game_foreground or not enabled or self._chat_mode or not is_down:
            return user32.CallNextHookEx(self._keyboard_hook, code, wparam, lparam)

        binding = self._matching_binding(self._keyboard_bindings.get(vk, ()), modifiers)
        if binding is None:
            return user32.CallNextHookEx(self._keyboard_hook, code, wparam, lparam)
        if was_down and identity in self._active_binding_keys:
            return 1
        action = plan_binding_action(binding, modifiers, profile)
        if not action.send_target and not action.autocast_toggle:
            if action.smartcast and not was_down:
                self._actions.put(action)
            return user32.CallNextHookEx(self._keyboard_hook, code, wparam, lparam)
        self._active_binding_keys[identity] = binding
        self._actions.put(action)
        if binding.config.repeat:
            self._repeat_due[binding.config.binding_id] = time.monotonic() + profile.repeat_delay_ms / 1000.0
        return 1

    def _mouse_callback(self, code: int, wparam: int, lparam: int) -> int:
        if code != HC_ACTION:
            return user32.CallNextHookEx(self._mouse_hook, code, wparam, lparam)
        event = ctypes.cast(lparam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
        if event.flags & LLMHF_INJECTED or int(event.dwExtraInfo) == INJECTED_MARKER:
            return user32.CallNextHookEx(self._mouse_hook, code, wparam, lparam)
        message = int(wparam)
        capture_mouse_key = None
        capture_down = False
        capture_up = False
        if message in {WM_XBUTTONDOWN, WM_XBUTTONUP}:
            xbutton = (int(event.mouseData) >> 16) & 0xFFFF
            capture_mouse_key = "MOUSE4" if xbutton == XBUTTON1 else "MOUSE5" if xbutton == XBUTTON2 else None
            capture_down = message == WM_XBUTTONDOWN
            capture_up = message == WM_XBUTTONUP
        elif message in {WM_MBUTTONDOWN, WM_MBUTTONUP}:
            capture_mouse_key = "MIDDLE"
            capture_down = message == WM_MBUTTONDOWN
            capture_up = message == WM_MBUTTONUP
        if capture_mouse_key and self._handle_mouse_capture(capture_mouse_key, capture_down, capture_up):
            return 1
        if not self.guard.is_foreground():
            return user32.CallNextHookEx(self._mouse_hook, code, wparam, lparam)
        with self._profile_lock:
            profile = self._profile
            enabled = profile.enabled and not self._suspended and not self._chat_mode
        if message == WM_RBUTTONDOWN:
            self._right_down = True
            if enabled and profile.right_repeat_enabled:
                self._right_repeat_due = time.monotonic() + profile.right_repeat_delay_ms / 1000.0
        elif message == WM_RBUTTONUP:
            self._right_down = False
        if not enabled:
            return user32.CallNextHookEx(self._mouse_hook, code, wparam, lparam)
        modifiers = self._current_modifiers()
        if message == WM_MOUSEWHEEL and profile.camera_enabled:
            delta = ctypes.c_short((int(event.mouseData) >> 16) & 0xFFFF).value
            if profile.camera_rotation_modifier.upper() in modifiers:
                key = profile.camera_rotate_up_key if delta > 0 else profile.camera_rotate_down_key
                self._actions.put(("key", (key, frozenset({profile.camera_rotation_modifier.upper()}))))
                return 1
            if profile.camera_incline_modifier.upper() in modifiers:
                key = profile.camera_incline_up_key if delta > 0 else profile.camera_incline_down_key
                self._actions.put(("key", (key, frozenset({profile.camera_incline_modifier.upper()}))))
                return 1
            if profile.camera_distance_modifier.upper() in modifiers:
                self._actions.put(("wheel", (delta, frozenset({profile.camera_distance_modifier.upper()}))))
                return 1
        mouse_key = None
        is_down = False
        is_up = False
        if message in {WM_XBUTTONDOWN, WM_XBUTTONUP}:
            xbutton = (int(event.mouseData) >> 16) & 0xFFFF
            mouse_key = "MOUSE4" if xbutton == XBUTTON1 else "MOUSE5" if xbutton == XBUTTON2 else None
            is_down = message == WM_XBUTTONDOWN
            is_up = message == WM_XBUTTONUP
        elif message in {WM_MBUTTONDOWN, WM_MBUTTONUP}:
            mouse_key = "MIDDLE"
            is_down = message == WM_MBUTTONDOWN
            is_up = message == WM_MBUTTONUP
        if mouse_key is None:
            return user32.CallNextHookEx(self._mouse_hook, code, wparam, lparam)
        identity = (mouse_key, 0)
        if is_up and identity in self._active_binding_keys:
            binding = self._active_binding_keys.pop(identity)
            self._repeat_due.pop(binding.config.binding_id, None)
            return 1
        if not is_down:
            return user32.CallNextHookEx(self._mouse_hook, code, wparam, lparam)
        if identity in self._active_binding_keys:
            return 1
        binding = self._matching_binding(self._mouse_bindings.get(mouse_key, ()), modifiers)
        if binding is None:
            return user32.CallNextHookEx(self._mouse_hook, code, wparam, lparam)
        action = plan_binding_action(binding, modifiers, profile)
        self._active_binding_keys[identity] = binding
        self._actions.put(action)
        if binding.config.repeat:
            self._repeat_due[binding.config.binding_id] = time.monotonic() + profile.repeat_delay_ms / 1000.0
        return 1

    def _handle_key_capture(
        self,
        vk: int,
        is_down: bool,
        is_up: bool,
        was_down: bool,
        modifiers: frozenset[str],
    ) -> bool:
        callback: Callable[[str | None], None] | None = None
        captured: str | None = None
        with self._capture_lock:
            active = self._capture_callback is not None
            suppressed = vk in self._capture_suppressed_keys
            if not active and not suppressed:
                return False
            if is_down:
                self._capture_suppressed_keys.add(vk)
            if is_up:
                self._capture_suppressed_keys.discard(vk)
            if active and is_down and not was_down and vk not in MODIFIER_VKS.values():
                callback = self._capture_callback
                self._capture_callback = None
                if vk != KEY_NAME_TO_VK["ESC"]:
                    key_name = VK_TO_KEY_NAME.get(vk)
                    if key_name:
                        parts = [name.title() for name in ("CTRL", "ALT", "SHIFT", "WIN") if name in modifiers]
                        parts.append(key_name)
                        captured = parse_keystroke("+".join(parts)).canonical()
        if callback is not None:
            try:
                callback(captured)
            except Exception as exc:
                self.on_error(f"key capture callback failed: {exc}")
        return True

    def _handle_mouse_capture(self, key_name: str, is_down: bool, is_up: bool) -> bool:
        callback: Callable[[str | None], None] | None = None
        with self._capture_lock:
            active = self._capture_callback is not None
            suppressed = key_name in self._capture_suppressed_mouse
            if not active and not suppressed:
                return False
            if is_down:
                self._capture_suppressed_mouse.add(key_name)
                if active:
                    callback = self._capture_callback
                    self._capture_callback = None
            if is_up:
                self._capture_suppressed_mouse.discard(key_name)
        if callback is not None:
            try:
                callback(key_name)
            except Exception as exc:
                self.on_error(f"mouse capture callback failed: {exc}")
        return True

    def _handle_toggle_key(self, vk: int, is_down: bool, is_up: bool, modifiers: frozenset[str]) -> bool:
        with self._profile_lock:
            toggles = {
                "suspend": parse_keystroke(self._profile.suspend_hotkey, allow_mouse=False),
                "mouse_lock": parse_keystroke(self._profile.mouse_lock_hotkey, allow_mouse=False),
            }
        handled = False
        for name, stroke in toggles.items():
            if stroke.vk != vk or not stroke.modifiers.issubset(modifiers):
                continue
            handled = True
            if is_down and name not in self._toggle_down:
                self._toggle_down.add(name)
                if name == "suspend":
                    self._suspended = not self._suspended
                    self._repeat_due.clear()
                else:
                    with self._profile_lock:
                        self._profile.mouse_lock_enabled = not self._profile.mouse_lock_enabled
                    if not self._profile.mouse_lock_enabled:
                        self._release_cursor_clip()
                self._publish_state()
            if is_up:
                self._toggle_down.discard(name)
            break
        return handled

    def _matching_binding(
        self,
        bindings: tuple[CompiledBinding, ...] | list[CompiledBinding],
        modifiers: frozenset[str],
    ) -> CompiledBinding | None:
        return next(
            (
                binding
                for binding in bindings
                if binding.source.modifiers.issubset(modifiers)
                and (
                    binding.config.group == "item"
                    or binding.config.group == self._command_context
                )
            ),
            None,
        )

    def _current_modifiers(self) -> frozenset[str]:
        modifiers: set[str] = set()
        for name, values in {
            "CTRL": {0x11, 0xA2, 0xA3},
            "ALT": {0x12, 0xA4, 0xA5},
            "SHIFT": {0x10, 0xA0, 0xA1},
            "WIN": {0x5B, 0x5C},
        }.items():
            if values.intersection(self._physical_keys):
                modifiers.add(name)
        return frozenset(modifiers)

    def _action_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                action = self._actions.get(timeout=0.2)
            except queue.Empty:
                continue
            if action is None:
                return
            try:
                if isinstance(action, BindingAction):
                    self._execute_binding(action)
                elif action[0] == "key":
                    key, modifiers = action[1]
                    self.sender.send_key(key, modifiers)
                elif action[0] == "wheel":
                    delta, modifiers = action[1]
                    self.sender.send_wheel(int(delta), modifiers)
                elif action[0] == "right_click":
                    self.sender.send_click("right")
            except Exception as exc:
                self.on_error(f"input action failed: {exc}")

    def _execute_binding(self, action: BindingAction) -> None:
        game = self.guard.snapshot(force=True)
        if not game.foreground:
            return
        with self._profile_lock:
            profile = self._profile
            delay = profile.smartcast_delay_ms / 1000.0
        if action.autocast_toggle:
            point = self._automatic_command_slot_point(action.binding.config.slot_index)
            if point is not None:
                self.sender.send_click("right", point=point)
            return
        if not action.send_target:
            if action.smartcast:
                time.sleep(delay)
                game = self.guard.snapshot(force=True)
                if game.foreground:
                    self.sender.send_click("left")
            return
        slot_index = action.binding.config.slot_index
        if slot_index is None:
            return
        self.frame_bridge.click_slot(
            game.hwnd,
            game.pid,
            action.binding.config.group,
            slot_index,
        )
        if action.self_cast or action.smartcast:
            time.sleep(delay)
            game = self.guard.snapshot(force=True)
            if not game.foreground:
                return
            if action.self_cast:
                self.frame_bridge.click_origin(game.hwnd, game.pid, ORIGIN_FRAME_PORTRAIT, 0)
            else:
                self.sender.send_click("left")

    def _automatic_command_slot_point(self, slot_index: int | None) -> tuple[int, int] | None:
        if slot_index is None or not 0 <= slot_index < 12:
            return None
        column = slot_index % 4
        row = slot_index // 4
        normalized = (
            0.821 + (0.966 - 0.821) * column / 3.0,
            0.796 + (0.943 - 0.796) * row / 2.0,
        )
        return self.guard.point_from_normalized(normalized)

    def _native_loop(self) -> None:
        last_identity = (0, 0)
        last_hotkey_identity = (0, 0)
        last_hotkey_revision = -1
        reported_error = ""
        neutral_selected = False
        next_selection_query = 0.0
        while not self._stop_event.wait(0.05):
            game = self.guard.snapshot(force=True)
            identity = (game.hwnd, game.pid)
            if not game.found:
                if last_identity != (0, 0):
                    self.frame_bridge.close()
                last_identity = (0, 0)
                last_hotkey_identity = (0, 0)
                last_hotkey_revision = -1
                self._command_context = "ability"
                neutral_selected = False
                next_selection_query = 0.0
                continue
            try:
                self.frame_bridge.connect(game.hwnd, game.pid)
                with self._profile_lock:
                    profile = self._profile
                    profile_revision = self._profile_revision
                if identity != last_hotkey_identity or profile_revision != last_hotkey_revision:
                    if profile.enforce_hotkeys and profile.enabled_groups.get("ability", True):
                        self.frame_bridge.override_command_hotkeys(
                            game.hwnd,
                            game.pid,
                            native_ability_hotkeys(profile),
                        )
                    else:
                        self.frame_bridge.set_command_hotkey_override_enabled(
                            game.hwnd,
                            game.pid,
                            False,
                        )
                    last_hotkey_identity = identity
                    last_hotkey_revision = profile_revision
                context = self.frame_bridge.query_command_context(game.hwnd, game.pid)
                now = time.monotonic()
                if identity != last_identity or now >= next_selection_query:
                    selection = self.frame_bridge.query_selection_context(game.hwnd, game.pid)
                    neutral_selected = selection.neutral_selected
                    next_selection_query = now + 0.25
                self._command_context = command_context_for(
                    context,
                    SelectionContext(True, neutral_selected, None),
                )
                last_identity = identity
                reported_error = ""
            except Exception as exc:
                message = f"native frame bridge initialization failed: {exc}"
                if message != reported_error:
                    self.on_error(message)
                    reported_error = message
                self._command_context = "ability"
                neutral_selected = False
                next_selection_query = 0.0
                if identity != last_identity:
                    self.frame_bridge.close()
                    last_identity = identity
                self._stop_event.wait(0.25)

    def _maintenance_loop(self) -> None:
        while not self._stop_event.wait(0.015):
            now = time.monotonic()
            with self._profile_lock:
                profile = self._profile
                enabled = profile.enabled and not self._suspended and not self._chat_mode
            if enabled and self.guard.is_foreground():
                active_by_id = {binding.config.binding_id: binding for binding in self._active_binding_keys.values()}
                for binding_id, due in tuple(self._repeat_due.items()):
                    if now < due:
                        continue
                    binding = active_by_id.get(binding_id)
                    if binding is None:
                        self._repeat_due.pop(binding_id, None)
                        continue
                    self._actions.put(plan_binding_action(binding, self._current_modifiers(), profile))
                    self._repeat_due[binding_id] = now + profile.repeat_delay_ms / 1000.0
                if profile.right_repeat_enabled and self._right_down and now >= self._right_repeat_due:
                    self._actions.put(("right_click", None))
                    self._right_repeat_due = now + profile.right_repeat_delay_ms / 1000.0
                self._apply_cursor_clip(profile)
            else:
                self._release_cursor_clip()
            self._publish_state()

    def _apply_cursor_clip(self, profile: ProfileConfig) -> None:
        if not profile.mouse_lock_enabled:
            self._release_cursor_clip()
            return
        snapshot = self.guard.snapshot()
        if snapshot.client_rect is None:
            return
        rect = RECT(*snapshot.client_rect)
        if user32.ClipCursor(ctypes.byref(rect)):
            self._clip_active = True

    def _release_cursor_clip(self) -> None:
        if self._clip_active:
            user32.ClipCursor(None)
            self._clip_active = False

    def _publish_state(self) -> None:
        game = self.guard.snapshot()
        if not game.found:
            state = "game_not_found"
        elif self._suspended:
            state = "suspended"
        elif self._chat_mode:
            state = "chat_paused"
        elif game.foreground and self._profile.enabled:
            state = "game_active"
        else:
            state = "game_background"
        if state != self._last_state:
            self._last_state = state
            self.on_state(state)
