"""Desktop launcher for Warcraft III Trainer with React / WebView2 GUI."""
from __future__ import annotations

import argparse
import logging
import os
import sys
import json
import threading
import time
from pathlib import Path

import webview

from war3_desktop_bridge import DesktopBridgeApi, DesktopRpcFacade
from war3_metadata import APP_VERSION, PRODUCT_EDITION_LABEL

logger = logging.getLogger("War3WebGui")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Warcraft III Modern Web GUI Trainer")
    parser.add_argument("--dev", action="store_true", help="Connect to Vite dev server at http://localhost:5173")
    parser.add_argument("--dev-url", default="http://localhost:5173", help="Custom Vite dev server URL")
    parser.add_argument("--pid", type=int, default=None, help="Target game process PID to connect on startup")
    parser.add_argument("--enable-hotkeys", action="store_true", help="Enable global hotkeys immediately on startup")
    parser.add_argument("--debug", action="store_true", help="Enable WebView2 developer tools (F12 inspect)")
    parser.add_argument('--offline', action='store_true', help='Open UI without game initialization')
    parser.add_argument('--ui-check', help='Write an offline desktop UI verification report')
    return parser.parse_args()


def apply_title_bar_colors(window, title: str) -> None:
    """Match the native title bar to the console: dark mode, then Windows 11 caption colours.

    Older systems ignore the attributes they do not know; nothing here is required.
    """
    if sys.platform != 'win32':
        return
    try:
        import ctypes
        from ctypes import wintypes
        hwnd = 0
        native = getattr(window, 'native', None)
        if native is not None and hasattr(native, 'Handle'):
            hwnd = int(native.Handle.ToInt64())
        if not hwnd:
            hwnd = ctypes.windll.user32.FindWindowW(None, title)
        if not hwnd:
            return
        dwm = ctypes.windll.dwmapi

        def set_attribute(attribute: int, value: int) -> int:
            data = ctypes.c_int(value)
            return dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), attribute, ctypes.byref(data), ctypes.sizeof(data))

        # Immersive dark mode is attribute 20 from Windows 10 20H1, 19 before that.
        if set_attribute(20, 1) != 0:
            set_attribute(19, 1)
        # Windows 11 only; COLORREF is 0x00BBGGRR.
        set_attribute(35, 0x001E2226)  # caption: iron #26221E
        set_attribute(36, 0x00D2E3EA)  # caption text: bone #EAE3D2
        set_attribute(34, 0x004E8AB0)  # border: bronze #B08A4E
    except Exception as exc:  # cosmetic only
        logger.debug('Title bar colours not applied: %s', exc)


def _visit_pages(window) -> list[dict]:
    """Open every page through the real navigation: each chapter, then each of its page tabs."""
    pages = []
    chapters = int(window.evaluate_js("document.querySelectorAll('[data-testid^=\"chapter-\"]').length"))
    for chapter in range(chapters):
        window.evaluate_js(f"document.querySelectorAll('[data-testid^=\"chapter-\"]')[{chapter}].click()")
        time.sleep(.25)
        tabs = int(window.evaluate_js("document.querySelectorAll('[data-testid^=\"page-\"]').length"))
        for tab in range(max(tabs, 1)):
            if tabs:
                window.evaluate_js(f"document.querySelectorAll('[data-testid^=\"page-\"]')[{tab}].click()")
                time.sleep(.25)
            # Pages load as separate chunks: wait for one to render before counting its controls.
            deadline = time.monotonic() + 5
            while True:
                page = window.evaluate_js(_PAGE_PROBE)
                if (page['ready'] and page['controls'] > 0) or time.monotonic() > deadline:
                    break
                time.sleep(.1)
            pages.append(page)
    return pages


_PAGE_PROBE = """(() => {
    const stage = document.querySelector('[data-testid="stage"]');
    const content = stage.querySelector(`[data-page-view="${stage.dataset.page}"]`);
    return {
        id: stage.dataset.page,
        label: stage.querySelector('h1')?.textContent.trim(),
        ready: stage.dataset.ready === 'true' && !!content?.children.length,
        controls: content?.querySelectorAll('button,input,select,textarea').length ?? 0,
        bodyWidth: document.body.scrollWidth, viewportWidth: innerWidth
    };
})()"""


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == '--runtime-self-test':
        from war3_runtime_check import run
        return run(sys.argv[2])
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    )
    args = parse_args()
    from war3_desktop_runtime import ensure_desktop_runtime
    if not ensure_desktop_runtime():
        return 1

    # Determine frontend target
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        here = Path(sys._MEIPASS)
    else:
        here = Path(__file__).resolve().parent
    dist_index = here / "frontend" / "dist" / "index.html"

    if args.dev:
        target_url = args.dev_url
        logger.info(f"Running in DEV mode, connecting to {target_url}")
    else:
        if not dist_index.exists():
            logger.error(f"Frontend dist build not found at {dist_index}!")
            logger.error("Please run 'npm run build' inside the frontend directory first, or run with --dev")
            return 1
        target_url = str(dist_index)
        logger.info(f"Running in PRODUCTION mode, loading {target_url}")

    # Initialize Desktop Bridge
    bridge_api = DesktopBridgeApi(
        initial_pid=args.pid,
        initial_hotkeys_enabled=args.enable_hotkeys,
        initialize=not (args.offline or args.ui_check),
        offline=bool(args.offline or args.ui_check),
    )

    window_title = f"魔兽争霸 III 修改器 v{APP_VERSION} by B站两杯沈梦溪、chatgpt和claude"

    # Create native WebView2 window
    window = webview.create_window(
        title=window_title,
        url=target_url,
        js_api=DesktopRpcFacade(bridge_api),
        width=1280,
        height=820,
        min_size=(800, 480),
        # The stage colour of the new frontend, so the window does not flash before it paints.
        background_color="#121A2B",
    )
    bridge_api.port.window = window
    bridge_api.port.on_destroy = window.destroy
    window.events.shown += lambda: apply_title_bar_colors(window, window_title)
    shutdown_started = threading.Event()

    def closing():
        if bridge_api.port._closed:
            return True
        if not shutdown_started.is_set():
            shutdown_started.set()
            threading.Thread(target=bridge_api.close, name='desktop-shutdown', daemon=False).start()
        return False
    window.events.closing += closing

    def verify_ui():
        if not args.ui_check:
            return
        destination = Path(args.ui_check)
        report = {'ok': False, 'offline': True, 'frozen': bool(getattr(sys, 'frozen', False))}
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                ready = window.evaluate_js("Boolean(document.querySelector('[data-testid=\"app\"]') && window.pywebview && window.pywebview.api)")
                if ready:
                    break
                time.sleep(.1)
            else:
                raise RuntimeError('Desktop frontend did not become ready')
            report['dom'] = window.evaluate_js("""(() => ({
                title: document.title,
                chapters: Array.from(document.querySelectorAll('[data-testid^="chapter-"]')).map(x => x.textContent.trim()),
                controls: document.querySelectorAll('button,input,select,textarea').length,
                viewportWidth: innerWidth, bodyWidth: document.body.scrollWidth,
                status: document.querySelector('[data-testid="clock"]')?.getAttribute('aria-label'),
                bridgeReady: Boolean(window.pywebview.api.read_ability_fields)
            }))()""")
            hotkeys = bridge_api.get_all_hotkeys()
            assert len(hotkeys) == 68
            assert len([h for h in hotkeys if h['category'] == 'stats']) == 17
            report['hotkeys'] = len(hotkeys)
            report['parameters'] = 17
            report['panels'] = panels = _visit_pages(window)
            # Every page is rebuilt on the new frontend and must offer controls.
            report['pending_pages'] = [p['id'] for p in panels if not p['ready']]
            assert len(panels) == 17 and len({p['id'] for p in panels}) == 17, [p['id'] for p in panels]
            assert not report['pending_pages'], report['pending_pages']
            assert all(p['controls'] > 0 for p in panels), [p['id'] for p in panels if not p['controls']]
            assert all(p['bodyWidth'] <= p['viewportWidth'] for p in panels)
            report['ok'] = bool(report['dom']['bridgeReady'] and report['dom']['controls'] > 10)
        except Exception as exc:
            import traceback
            report['error'] = traceback.format_exc()
        finally:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
            bridge_api.close()

    # Launch event loop
    try:
        webview.start(verify_ui if args.ui_check else None, debug=args.debug, gui='edgechromium')
    finally:
        bridge_api.port.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
