"""Desktop launcher for Warcraft III Trainer with modern Svelte 5 / WebView2 GUI."""
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

    window_title = f"魔兽争霸 III 修改器 v{APP_VERSION} ({PRODUCT_EDITION_LABEL}) by B站两杯沈梦溪"

    # Create native WebView2 window
    window = webview.create_window(
        title=window_title,
        url=target_url,
        js_api=DesktopRpcFacade(bridge_api),
        width=1280,
        height=820,
        min_size=(800, 480),
        background_color="#07090D",
    )
    bridge_api.port.window = window
    bridge_api.port.on_destroy = window.destroy
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
                ready = window.evaluate_js("Boolean(document.querySelector('.app-layout') && window.pywebview && window.pywebview.api)")
                if ready:
                    break
                time.sleep(.1)
            else:
                raise RuntimeError('Desktop frontend did not become ready')
            report['dom'] = window.evaluate_js("""(() => ({
                title: document.title,
                navigation: Array.from(document.querySelectorAll('.sidebar .nav-item')).map(x => x.textContent.trim()),
                controls: document.querySelectorAll('button,input,select,textarea').length,
                viewportWidth: innerWidth, bodyWidth: document.body.scrollWidth,
                status: document.querySelector('.status-indicator')?.textContent.trim(),
                bridgeReady: Boolean(window.pywebview.api.read_ability_fields)
            }))()""")
            hotkeys = bridge_api.get_all_hotkeys()
            assert len(hotkeys) == 68
            assert len([h for h in hotkeys if h['category'] == 'stats']) == 17
            report['hotkeys'] = len(hotkeys)
            report['parameters'] = 17
            panels = []
            count = int(window.evaluate_js("document.querySelectorAll('.sidebar .nav-item').length"))
            for index in range(count):
                window.evaluate_js(f"document.querySelectorAll('.sidebar .nav-item')[{index}].click()")
                time.sleep(.2)
                panels.append(window.evaluate_js("""(() => ({
                    label: document.querySelector('.sidebar .nav-item.active')?.textContent.trim(),
                    controls: document.querySelector('.panel-slot:not([hidden])')?.querySelectorAll('button,input,select,textarea').length || 0,
                    bodyWidth: document.body.scrollWidth, viewportWidth: innerWidth
                }))()"""))
            report['panels'] = panels
            assert len(panels) == 16 and all(p['controls'] > 0 for p in panels)
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
