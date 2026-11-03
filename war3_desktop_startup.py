"""Observe desktop startup without relying on a working renderer or game connection."""
from __future__ import annotations

import json
import hashlib
import logging
import os
from pathlib import Path
import platform
import tempfile
import sys
import threading
import time
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

from war3_desktop_runtime import message


def application_identity():
    from war3_metadata import APP_VERSION, WIN10_COMPAT_REVISION
    result = dict(app_version=APP_VERSION, revision=WIN10_COMPAT_REVISION,
                  frozen=bool(getattr(sys, 'frozen', False)), pid=os.getpid(),
                  executable=sys.executable)
    if result['frozen']:
        try:
            digest = hashlib.sha256()
            with open(sys.executable, 'rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
            result['exe_sha256'] = digest.hexdigest()
        except OSError as exc:
            result['exe_hash_error'] = repr(exc)
    return result


def configure_startup_log():
    """The renderer's initialization exceptions otherwise disappear in a windowed EXE."""
    name = f'desktop-startup-{time.strftime("%Y%m%d-%H%M%S")}-pid{os.getpid()}.log'
    folders = [Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'War3Trainer/log',
               Path(tempfile.gettempdir()) / 'War3Trainer/log']
    for folder in folders:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / name
            handler = logging.FileHandler(path, encoding='utf8')
            handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] [%(name)s] %(message)s'))
            root = logging.getLogger()
            root.addHandler(handler)
            if root.level > logging.INFO:
                root.setLevel(logging.INFO)
            logger = logging.getLogger('War3DesktopStartup')
            logger.info('startup_environment %s', json.dumps(dict(
                windows=platform.platform(), architecture=platform.machine(),
                log_path=str(path), **application_identity()), ensure_ascii=False))
            return path
        except OSError:
            continue
    return None


def configure_rendering(safe, environ=None):
    """Opt in per launch; do not change the user's system/GPU settings."""
    environ = os.environ if environ is None else environ
    if safe:
        key = 'WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'
        flags = environ.get(key, '')
        for flag in ('--disable-gpu', '--disable-gpu-compositing'):
            if flag not in flags.split():
                flags = (flags + ' ' + flag).strip()
        environ[key] = flags


def frontend_file_url(index):
    """Use WebView2's file loader; do not depend on localhost MIME/proxy settings."""
    index = Path(index).resolve(strict=True)
    root = index.parent
    class Assets(HTMLParser):
        def __init__(self):
            super().__init__();self.paths=[]
        def handle_starttag(self, tag, attrs):
            attrs=dict(attrs)
            value=attrs.get('src') if tag=='script' else attrs.get('href') if tag=='link' and attrs.get('rel')=='stylesheet' else None
            if value:self.paths.append(value)
    parser=Assets();parser.feed(index.read_text(encoding='utf8'))
    checked=[]
    for relative in parser.paths:
        parsed=urlsplit(relative)
        if parsed.scheme or parsed.netloc:
            raise RuntimeError('内置界面入口包含外部资源：'+relative)
        path=(root/unquote(parsed.path)).resolve(strict=True)
        if not path.is_relative_to(root):
            raise RuntimeError('内置界面资源路径超出界面目录：'+relative)
        raw=path.read_bytes()
        checked.append(dict(path=relative,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    logging.getLogger('War3DesktopStartup').info('frontend_local_resources %s',json.dumps(
        dict(loader='webview2_file',entry=index.as_uri(),assets=checked),ensure_ascii=False))
    return index.as_uri()


class DesktopStartupMonitor:
    def __init__(self, log_path, *, safe=False, notify=message, timeout=45):
        self.log_path = str(log_path or '（日志目录不可写）')
        self.safe = safe
        self.notify = notify
        self.timeout = timeout
        self._lock = threading.RLock()
        self._timer = None
        self._closed = False
        self._ready = False
        self._failed = False
        self._logger = logging.getLogger('War3DesktopStartup')

    def start(self):
        self._logger.info('renderer_start safe_render=%s', self.safe)
        self._timer = threading.Timer(self.timeout, self.timed_out)
        self._timer.daemon = True
        self._timer.start()

    def report(self, stage, details=None):
        if stage not in ('ready', 'failed', 'runtime_error'):
            return dict(accepted=False)
        details = details if isinstance(details, dict) else {}
        details = {k: str(details[k])[:6000] for k in
                   ('message', 'stack', 'source', 'userAgent', 'url', 'page') if k in details}
        self._logger.info('frontend_%s %s', stage, json.dumps(details, ensure_ascii=False))
        if stage == 'ready':
            with self._lock:
                if self._closed or self._failed:
                    return dict(accepted=False)
                self._ready = True
                if self._timer:
                    self._timer.cancel()
        elif stage == 'failed':
            self.fail(details.get('message') or '界面加载失败，未收到具体错误。')
        return dict(accepted=True)

    def timed_out(self):
        with self._lock:
            if self._closed or self._ready or self._failed:
                return
            self.fail('窗口已启动，但界面在规定时间内没有完成加载。可能是显示组件初始化、界面资源或渲染出现问题。')

    def fail(self, reason, *, wait=False):
        with self._lock:
            if self._closed or self._failed:
                return
            self._failed = True
            if self._timer:
                self._timer.cancel()
        self._logger.error('desktop_display_failed %s', reason)
        tip = ('当前已使用兼容显示模式，请检查 WebView2 运行组件及显卡驱动。' if self.safe else
               '如果窗口空白或黑屏，可以关闭后使用附带的“兼容显示模式”启动文件重试。')
        # A native dialog works even when WebView2 never initialized. Do not block RPC.
        text = ('修改器界面未能正常显示。\n\n' + str(reason)[:1600] + '\n\n' + tip +
                '\n\n详细日志：\n' + self.log_path)
        if wait:
            self.notify(text)
        else:
            threading.Thread(target=self.notify, args=(text,), name='desktop-startup-error', daemon=True).start()

    def close(self):
        with self._lock:
            self._closed = True
            if self._timer:
                self._timer.cancel()
