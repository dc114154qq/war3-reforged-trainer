"""Launch/focus Warcraft III and load the first QuickSave without game injection."""

from __future__ import annotations

import argparse
import csv
import ctypes
from ctypes import wintypes
import io
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
from datetime import datetime

if sys.platform != "win32":
    raise SystemExit("run_war3_quicksave.py is Windows-only")

try:
    from PIL import Image, ImageChops, ImageGrab, ImageStat
except ImportError as exc:
    raise SystemExit("Pillow is required: python -m pip install Pillow") from exc


TOOLS_DIR = Path(__file__).resolve().parent
BRIDGE = TOOLS_DIR / "war3_window_bridge.exe"
VK_F10 = 0x79
VK_RETURN = 0x0D
VK_SPACE = 0x20
VK_ESCAPE = 0x1B
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
MK_LBUTTON = 0x0001
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
BATTLE_NET_PLAY_X = 156
BATTLE_NET_PLAY_BOTTOM = 109

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.WindowFromPoint.restype = wintypes.HWND
user32.ScreenToClient.argtypes = [
    wintypes.HWND,
    ctypes.POINTER(wintypes.POINT),
]
user32.ScreenToClient.restype = wintypes.BOOL
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL


def log(message: str) -> None:
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z")
    print(f"[{stamp}] {message}", flush=True)


def make_dpi_aware() -> None:
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def process_pids(image_name: str) -> list[int]:
    result = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {image_name}", "/FO", "CSV", "/NH"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    pids: list[int] = []
    for row in csv.reader(io.StringIO(result.stdout)):
        if len(row) >= 2 and row[0].casefold() == image_name.casefold():
            try:
                pids.append(int(row[1]))
            except ValueError:
                pass
    return pids


def warcraft_pids() -> list[int]:
    return process_pids("Warcraft III.exe")


def process_executable_path(pid: int) -> Path:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(buffer))
        if not kernel32.QueryFullProcessImageNameW(
            handle,
            0,
            buffer,
            ctypes.byref(size),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return Path(buffer.value)
    finally:
        kernel32.CloseHandle(handle)


def resolve_status_file(pid: int, requested: Path | None) -> Path:
    if requested is not None:
        return requested.expanduser().resolve()
    return process_executable_path(pid).parent / "war3_selection_auto_status.bin"


def battle_net_pids() -> list[int]:
    return process_pids("Battle.net.exe")


def find_battle_net(explicit: str | None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    found = shutil.which("Battle.net Launcher.exe")
    if found:
        candidates.append(Path(found))
    for variable in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
        root = os.environ.get(variable)
        if root:
            candidates.extend(
                (
                    Path(root) / "Battle.net" / "Battle.net Launcher.exe",
                    Path(root) / "Battle.net Launcher" / "Battle.net Launcher.exe",
                )
            )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        "Battle.net Launcher.exe was not found; pass --battle-net PATH"
    )


def invoke_battle_net_play(pid: int) -> bool:
    try:
        from pywinauto import Desktop
    except ImportError:
        return False
    for window in Desktop(backend="uia").windows(process=pid):
        for button in window.descendants(control_type="Button"):
            name = button.window_text()
            if name.startswith("进入游戏"):
                button.invoke()
                log(f"Invoked Battle.net UIA button: {name}")
                return True
    return False


def launch_warcraft(battle_net: str | None) -> None:
    launcher = find_battle_net(battle_net)
    if not battle_net_pids():
        log(f"Battle.net absent; launching {launcher}")
        subprocess.Popen(
            [str(launcher)],
            close_fds=True,
            creationflags=subprocess.DETACHED_PROCESS,
        )
    deadline = time.monotonic() + 45.0
    while time.monotonic() < deadline:
        for pid in battle_net_pids():
            window = find_window(pid)
            if window:
                hwnd, _rect = window
                focus(pid)
                if invoke_battle_net_play(pid):
                    log("Warcraft launch requested through the Battle.net button")
                    return
                dpi = user32.GetDpiForWindow(hwnd) or 96
                left, _top, _right, bottom = current_rect(pid)
                x = left + round(BATTLE_NET_PLAY_X * dpi / 96)
                y = bottom - round(BATTLE_NET_PLAY_BOTTOM * dpi / 96)
                user32.SetCursorPos(x, y)
                time.sleep(0.5)
                user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                log(
                    "Clicked Battle.net Enter Game at "
                    f"screen ({x}, {y}) rect={current_rect(pid)} dpi={dpi}"
                )
                fallback_deadline = time.monotonic() + 4.0
                while (
                    time.monotonic() < fallback_deadline
                    and not warcraft_pids()
                ):
                    time.sleep(0.25)
                if not warcraft_pids():
                    point = wintypes.POINT(x, y)
                    target = user32.WindowFromPoint(point)
                    client = wintypes.POINT(x, y)
                    if not target or not user32.ScreenToClient(
                        target,
                        ctypes.byref(client),
                    ):
                        raise ctypes.WinError(ctypes.get_last_error())
                    message_position = (
                        (client.y & 0xFFFF) << 16
                    ) | (client.x & 0xFFFF)
                    user32.PostMessageW(
                        target,
                        WM_MOUSEMOVE,
                        0,
                        message_position,
                    )
                    user32.PostMessageW(
                        target,
                        WM_LBUTTONDOWN,
                        MK_LBUTTON,
                        message_position,
                    )
                    user32.PostMessageW(
                        target,
                        WM_LBUTTONUP,
                        0,
                        message_position,
                    )
                    log(
                        "Retried Battle.net Enter Game through child "
                        f"window message hwnd=0x{int(target):x} "
                        f"client=({client.x}, {client.y})"
                    )
                log("Warcraft launch requested through the Battle.net button")
                return
        time.sleep(0.5)
    raise TimeoutError("Battle.net window did not become available")


def find_window(pid: int) -> tuple[int, tuple[int, int, int, int]] | None:
    found: list[tuple[int, tuple[int, int, int, int]]] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def visitor(hwnd: int, _parameter: int) -> bool:
        owner_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner_pid))
        if owner_pid.value != pid or user32.GetWindow(hwnd, 4):
            return True
        rect = wintypes.RECT()
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            width, height = rect.right - rect.left, rect.bottom - rect.top
            if width >= 640 and height >= 360 and user32.IsWindowVisible(hwnd):
                found.append((hwnd, (rect.left, rect.top, rect.right, rect.bottom)))
        return True

    user32.EnumWindows(visitor, 0)
    return max(found, key=lambda item: area(item[1]), default=None)


def area(rect: tuple[int, int, int, int]) -> int:
    return max(0, rect[2] - rect[0]) * max(0, rect[3] - rect[1])


def wait_for_window(timeout: float) -> tuple[int, int, tuple[int, int, int, int]]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pids = warcraft_pids()
        for pid in pids:
            window = find_window(pid)
            if window:
                hwnd, rect = window
                return pid, hwnd, rect
        if pids and BRIDGE.is_file():
            # Borderless Warcraft can initially report an off-screen 158x26
            # rectangle until its existing focus bridge restores the window.
            try:
                focus(pids[0])
            except RuntimeError:
                pass
            time.sleep(0.5)
        time.sleep(1.0)
    raise TimeoutError("Warcraft III window did not appear")


def focus(pid: int) -> None:
    if not BRIDGE.is_file():
        raise FileNotFoundError(f"window focus bridge is missing: {BRIDGE}")
    result = subprocess.run(
        [str(BRIDGE), str(pid)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "war3_window_bridge.exe failed")
    log(f"Focused window: {result.stdout.strip()}")


def current_rect(pid: int, timeout: float = 30.0) -> tuple[int, int, int, int]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        window = find_window(pid)
        if window:
            return window[1]
        if pid not in warcraft_pids():
            raise RuntimeError("Warcraft III exited")
        time.sleep(0.5)
    raise RuntimeError("Warcraft III window did not reappear")


def screenshot(pid: int) -> Image.Image:
    return ImageGrab.grab(bbox=current_rect(pid), all_screens=True).convert("RGB")


def click(pid: int, nx: float, ny: float, label: str) -> None:
    left, top, right, bottom = current_rect(pid)
    x = round(left + (right - left) * nx)
    y = round(top + (bottom - top) * ny)
    user32.SetCursorPos(x, y)
    time.sleep(0.12)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    log(f"Clicked {label} at normalized ({nx:.3f}, {ny:.3f})")


def double_click(pid: int, nx: float, ny: float, label: str) -> None:
    left, top, right, bottom = current_rect(pid)
    x = round(left + (right - left) * nx)
    y = round(top + (bottom - top) * ny)
    user32.SetCursorPos(x, y)
    time.sleep(0.12)
    for _index in range(2):
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.08)
    log(f"Double-clicked {label} at normalized ({nx:.3f}, {ny:.3f})")


def right_click(pid: int, nx: float, ny: float, label: str) -> None:
    left, top, right, bottom = current_rect(pid)
    x = round(left + (right - left) * nx)
    y = round(top + (bottom - top) * ny)
    user32.SetCursorPos(x, y)
    time.sleep(0.12)
    user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
    user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
    log(f"Right-clicked {label} at normalized ({nx:.3f}, {ny:.3f})")


def press(key: int, label: str) -> None:
    user32.keybd_event(key, 0, 0, 0)
    user32.keybd_event(key, 0, KEYEVENTF_KEYUP, 0)
    log(f"Pressed {label}")


class StateDetector:
    REFERENCE_FILES = {
        "main": (
            "_selection_limit_restart_menu.png",
            "_war3_nav1.png",
        ),
        "single": ("_war3_nav2.png", "_war3_v16_single.png"),
        "game_menu": ("_war3_v16_menu.png",),
        "load_list": ("_war3_v16_loadscreen.png", "_war3_v16_after_load_click.png"),
        "loading": (
            "_war3_loaded_direct.png",
            "_war3_v11_ready.png",
        ),
        "game": ("_war3_v17_loaded.png", "_war3_v17_user_loaded.png"),
    }

    def __init__(self) -> None:
        self.references: dict[str, list[Image.Image]] = {}
        for state, names in self.REFERENCE_FILES.items():
            images = []
            for name in names:
                path = TOOLS_DIR / name
                if path.is_file():
                    with Image.open(path) as image:
                        images.append(self._fingerprint(image.convert("RGB")))
            self.references[state] = images

    @staticmethod
    def _fingerprint(image: Image.Image) -> Image.Image:
        # Preserve large UI geometry while making resolution/DPI irrelevant.
        return image.resize((128, 72), Image.Resampling.BILINEAR)

    @staticmethod
    def _distance(left: Image.Image, right: Image.Image) -> float:
        difference = ImageChops.difference(left, right)
        rms = ImageStat.Stat(difference).rms
        return sum(rms) / (len(rms) * 255.0)

    @staticmethod
    def _parchment_fraction(image: Image.Image) -> float:
        small = image.resize((96, 54), Image.Resampling.BILINEAR)
        pixels = list(small.getdata())
        parchment = sum(
            1
            for red, green, blue in pixels
            if red > green > blue and 90 < red < 225 and red - blue < 105
        )
        return parchment / len(pixels)

    def detect(self, image: Image.Image) -> tuple[str, float]:
        fingerprint = self._fingerprint(image)
        scores = {
            state: min(
                (self._distance(fingerprint, reference) for reference in references),
                default=1.0,
            )
            for state, references in self.references.items()
        }
        if self._parchment_fraction(image) > 0.58:
            return "loading", scores.get("loading", 1.0)
        state = min(scores, key=scores.get)
        if scores[state] > 0.120:
            return "unknown", scores[state]
        return state, scores[state]


def wait_state(
    pid: int,
    detector: StateDetector,
    wanted: set[str],
    timeout: float,
    description: str,
) -> str:
    deadline = time.monotonic() + timeout
    last_state = ""
    while time.monotonic() < deadline:
        state, score = detector.detect(screenshot(pid))
        if state != last_state:
            log(f"Detected state={state} similarity_error={score:.3f}")
            last_state = state
        if state in wanted:
            return state
        time.sleep(0.75)
    raise TimeoutError(f"Timed out waiting for {description}; last state={last_state}")


def load_from_menu(pid: int, detector: StateDetector, step_timeout: float) -> None:
    deadline = time.monotonic() + step_timeout * 6.0
    while time.monotonic() < deadline:
        state = wait_state(
            pid,
            detector,
            {"main", "single", "game", "game_menu", "load_list", "loading"},
            step_timeout,
            "a recognizable Warcraft state",
        )
        if state == "loading":
            log("A save is already loading; continuing from the loading screen")
            return
        if state == "game":
            press(VK_F10, "F10")
        elif state == "game_menu":
            click(pid, 0.500, 0.345, "in-game Load Game")
        elif state == "main":
            click(pid, 0.806, 0.389, "Single Player")
        elif state == "single":
            click(pid, 0.806, 0.452, "Load Save")
        elif state == "load_list":
            click(pid, 0.350, 0.276, "top QuickSave entry")
            time.sleep(0.5)
            click(pid, 0.860, 0.780, "Continue")
            return
        time.sleep(0.75)
    raise TimeoutError("Menu state machine did not reach the load-save dialog")


def finish_loading(
    pid: int, detector: StateDetector, load_timeout: float
) -> None:
    started = time.monotonic()
    deadline = started + load_timeout
    next_space = started + 3.0
    last_state = ""
    enter_sent = False
    saw_loading = False
    while time.monotonic() < deadline:
        state, score = detector.detect(screenshot(pid))
        if state != last_state:
            log(f"Post-load state={state} similarity_error={score:.3f}")
            last_state = state
        if state == "loading":
            saw_loading = True
        if state == "game":
            press(VK_SPACE, "Space")
            log("QuickSave loaded and final Space key delivered")
            return
        now = time.monotonic()
        if not enter_sent and now >= started + 2.5:
            # Accept a possible overwrite/load confirmation; harmless otherwise.
            press(VK_RETURN, "Enter (load confirmation)")
            enter_sent = True
        if saw_loading and now >= next_space:
            press(VK_SPACE, "Space (continue loading screen)")
            next_space = now + 2.0
        time.sleep(0.75)
    raise TimeoutError(f"Save did not reach the game; last state={last_state}")


def load_fixed_from_main(pid: int, startup_delay: float) -> None:
    if startup_delay > 0:
        log(f"Waiting {startup_delay:.1f}s for the fixed main-menu layout")
        time.sleep(startup_delay)
    focus(pid)
    time.sleep(0.5)
    click(pid, 0.806, 0.389, "Single Player")
    time.sleep(1.5)
    click(pid, 0.806, 0.452, "Load Save")
    time.sleep(4.0)
    load_fixed_from_list(pid)


def load_fixed_from_list(pid: int) -> None:
    click(pid, 0.350, 0.276, "top QuickSave entry")
    time.sleep(0.6)
    click(pid, 0.860, 0.780, "Continue")


def finish_fixed_loading(pid: int, wait_seconds: float) -> None:
    started = time.monotonic()
    deadline = started + wait_seconds
    while time.monotonic() < deadline:
        if pid not in warcraft_pids():
            raise RuntimeError("Warcraft III exited during fixed load sequence")
        time.sleep(0.5)
    press(VK_RETURN, "Enter (continue)")
    time.sleep(2.0)
    press(VK_SPACE, "Space (final center)")
    log("Fixed QuickSave load sequence completed")


def read_auto_status(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    if len(data) < 196 or data[:4] != b"W3SA":
        raise RuntimeError(f"Invalid selection status file: {path}")

    def u32(offset: int) -> int:
        return struct.unpack_from("<I", data, offset)[0]

    def u64(offset: int) -> int:
        return struct.unpack_from("<Q", data, offset)[0]

    return {
        "version": u32(4),
        "state": u32(8),
        "error": u32(16),
        "pid": u32(44),
        "stage": u32(48),
        "sync": u32(52),
        "mirror": u32(56),
        "local": u32(60),
        "observer": u32(64),
        "flags": u32(68),
        "single": u32(72),
        "invalid": u32(76),
        "poisoned": u32(80),
        "diagnostic": tuple(u64(124 + index * 8) for index in range(9)),
    }


def run_live_move_test(
    pid: int,
    status_file: Path,
    monitor_seconds: float,
) -> None:
    focus(pid)
    time.sleep(0.5)
    double_click(pid, 688 / 1707, 523 / 960, "screen-visible same-type units")

    deadline = time.monotonic() + 8.0
    selected: dict[str, object] | None = None
    while time.monotonic() < deadline:
        if pid not in warcraft_pids():
            raise RuntimeError("Warcraft III exited during same-type selection")
        status = read_auto_status(status_file)
        if status["pid"] == pid and int(status["local"]) > 12:
            selected = status
            break
        time.sleep(0.25)
    if selected is None:
        raise RuntimeError("Same-type selection did not reach more than 12 units")
    log(
        "Extended selection ready: "
        f"sync={selected['sync']} mirror={selected['mirror']} "
        f"local={selected['local']}"
    )

    right_click(pid, 350 / 1707, 175 / 960, "upper-left move destination")
    deadline = time.monotonic() + monitor_seconds
    last_signature: tuple[object, ...] | None = None
    final: dict[str, object] | None = None
    while time.monotonic() < deadline:
        if pid not in warcraft_pids():
            raise RuntimeError("Warcraft III exited after the 13+ unit move order")
        final = read_auto_status(status_file)
        signature = (
            final["sync"],
            final["mirror"],
            final["local"],
            final["invalid"],
            final["poisoned"],
            final["diagnostic"],
        )
        if signature != last_signature:
            log(
                "Move telemetry: "
                f"sync={final['sync']} mirror={final['mirror']} "
                f"local={final['local']} invalid={final['invalid']} "
                f"poisoned={final['poisoned']} diag={final['diagnostic']}"
            )
            last_signature = signature
        time.sleep(0.25)

    if final is None:
        raise RuntimeError("Move telemetry was not observed")
    diagnostic = final["diagnostic"]
    if (
        final["pid"] != pid
        or final["sync"] != 12
        or final["mirror"] != final["local"]
        or int(final["local"]) <= 12
        or final["invalid"] != 0
        or final["poisoned"] != 0
        or diagnostic[1] != 0
        or diagnostic[4] != 8
    ):
        raise RuntimeError(f"13+ move acceptance failed: {final}")
    log("13+ move acceptance passed")


def save_timeout_screenshot(pid: int | None, requested: Path | None) -> Path | None:
    if pid is None:
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = requested or TOOLS_DIR / f"war3_quicksave_timeout_{stamp}.png"
    try:
        destination = destination.expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        screenshot(pid).save(destination)
        log(f"Saved timeout/failure screenshot: {destination}")
        return destination
    except Exception as exc:
        log(f"Could not save failure screenshot: {exc}")
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch/focus Warcraft III and load the first QuickSave."
    )
    parser.add_argument(
        "--battle-net",
        metavar="PATH",
        help="path to Battle.net Launcher.exe (auto-detected by default)",
    )
    parser.add_argument(
        "--no-launch",
        action="store_true",
        help="fail instead of launching Battle.net when Warcraft is absent",
    )
    parser.add_argument(
        "--window-timeout",
        type=float,
        default=120.0,
        help="seconds to wait for a Warcraft window (default: 120)",
    )
    parser.add_argument(
        "--step-timeout",
        type=float,
        default=20.0,
        help="seconds allowed for each menu transition (default: 20)",
    )
    parser.add_argument(
        "--load-timeout",
        type=float,
        default=180.0,
        help="seconds allowed for loading the save (default: 180)",
    )
    parser.add_argument(
        "--vision",
        action="store_true",
        help="use screenshot state detection instead of the fixed click sequence",
    )
    parser.add_argument(
        "--from-load-list",
        action="store_true",
        help="start fixed mode on the already-open load-save list",
    )
    parser.add_argument(
        "--skip-load",
        action="store_true",
        help="leave the current map untouched and run only requested live tests",
    )
    parser.add_argument(
        "--launch-only",
        action="store_true",
        help="stop after launching and focusing Warcraft III",
    )
    parser.add_argument(
        "--startup-delay",
        type=float,
        default=20.0,
        help="fixed-mode delay after launching Warcraft (default: 20)",
    )
    parser.add_argument(
        "--fixed-wait",
        type=float,
        default=45.0,
        help="fixed-mode seconds to deliver Continue/Space keys (default: 45)",
    )
    parser.add_argument(
        "--timeout-screenshot",
        type=Path,
        help="failure screenshot path (default: timestamped PNG beside this script)",
    )
    parser.add_argument(
        "--live-move-test",
        action="store_true",
        help="after loading, select 13+ units and run the fixed move acceptance test",
    )
    parser.add_argument(
        "--status-file",
        type=Path,
        help=(
            "persistent plugin telemetry file "
            "(default: beside the running Warcraft III.exe)"
        ),
    )
    parser.add_argument(
        "--monitor-seconds",
        type=float,
        default=30.0,
        help="seconds to monitor the live move test (default: 30)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    make_dpi_aware()
    pid: int | None = None
    try:
        existing = warcraft_pids()
        launched = not existing
        if not existing:
            if args.no_launch:
                raise RuntimeError("Warcraft III.exe is not running (--no-launch)")
            launch_warcraft(args.battle_net)
        pid, _hwnd, rect = wait_for_window(args.window_timeout)
        log(f"Found Warcraft III.exe pid={pid} rect={rect}")
        focus(pid)
        if args.launch_only:
            log("Warcraft launch-only flow completed")
            return 0
        if not args.skip_load:
            if args.vision:
                detector = StateDetector()
                load_from_menu(pid, detector, args.step_timeout)
                finish_loading(pid, detector, args.load_timeout)
            else:
                if args.from_load_list:
                    load_fixed_from_list(pid)
                else:
                    load_fixed_from_main(
                        pid,
                        args.startup_delay if launched else 0.5,
                    )
                finish_fixed_loading(pid, args.fixed_wait)
        else:
            log("Skipping menu/load automation; using the current map")
        if args.live_move_test:
            run_live_move_test(
                pid,
                resolve_status_file(pid, args.status_file),
                args.monitor_seconds,
            )
        return 0
    except KeyboardInterrupt:
        log("Cancelled")
        return 130
    except Exception as exc:
        log(f"ERROR: {exc}")
        if args.vision or args.timeout_screenshot:
            save_timeout_screenshot(pid, args.timeout_screenshot)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
