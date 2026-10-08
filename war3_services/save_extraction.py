"""Offline save-code files and session-bound, read-only game string extraction."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import tempfile
import traceback

from war3_save_codes import SaveCode, SaveExtractionError, decode_text, extract_text, validate_prefix


TEXT_EXTENSIONS = frozenset({".txt", ".pld", ".log", ".j", ".lua"})
MAX_FILE_BYTES = 8 * 1024 * 1024


def documents_directory() -> Path:
    if os.name == "nt":
        import ctypes
        buffer = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer) == 0:
            return Path(buffer.value)
    return Path.home() / "Documents"


def default_save_roots() -> tuple[Path, ...]:
    root = documents_directory() / "Warcraft III"
    candidates = [root / "CustomMapData"]
    if (root / "BattleNet").is_dir():
        candidates.extend((root / "BattleNet").glob("*/CustomMapData"))
        candidates.extend((root / "BattleNet").glob("*/*/CustomMapData"))
    return tuple(path for path in candidates if path.is_dir())


def read_code_file(path, prefix="-load"):
    path = Path(path)
    if not path.is_file():
        raise SaveExtractionError("未找到所选文件，请重新选择存档码文件。")
    if path.suffix.lower() in {".w3z", ".w3v"}:
        raise SaveExtractionError("这是整局游戏存档或战役缓存，不是 RPG 存档码文件。请选择地图生成的 TXT/PLD 文件，或先在游戏里生成存档码。")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise SaveExtractionError("文本文件超过 8 MB，请选择地图生成的存档码文件，或粘贴需要提取的文字。")
    with path.open("rb") as file:
        data = file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise SaveExtractionError("文件在读取过程中变大，未完成提取，请稍后重试。")
    if data.startswith(b"Warcraft III recorded game\x1a\0") or path.suffix.lower() in {".w3z", ".w3v"}:
        raise SaveExtractionError("这是整局游戏存档或战役缓存，不是 RPG 存档码文件。请选择地图生成的 TXT/PLD 文件，或先在游戏里生成存档码。")
    return extract_text(decode_text(data), str(path), prefix)


def scan_code_directory(path, prefix="-load", *, cancel=None, progress=None, max_files=2000, max_bytes=64 * 1024 * 1024):
    """Limits and skipped files are reported; a partial scan is never called a full scan."""
    validate_prefix(prefix)
    root = Path(path)
    if not root.is_dir():
        raise SaveExtractionError("未找到存档码目录，请选择 Warcraft III 的 CustomMapData，或地图实际保存文件的目录。")
    codes, warnings = [], []
    files = total = 0
    complete = True
    stopped = False

    def walk_error(exc):
        nonlocal complete
        complete = False
        warnings.append({"file": str(exc.filename or root), "reason": "目录无法读取", "detail": str(exc)})

    for directory, dirs, names in os.walk(root, followlinks=False, onerror=walk_error):
        dirs[:] = sorted(name for name in dirs if not (Path(directory) / name).is_symlink())
        for name in sorted(names):
            if cancel is not None and cancel.is_set():
                complete = False; stopped = True; break
            file = Path(directory) / name
            if file.is_symlink() or file.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            if files >= max_files or total >= max_bytes:
                complete = False; stopped = True; break
            files += 1
            try:
                size = file.stat().st_size
                if total + size > max_bytes:
                    complete = False; stopped = True; break
                rows = read_code_file(file, prefix)
                total += size
                codes.extend(rows)
            except (OSError, ValueError) as exc:
                warnings.append({"file": str(file), "reason": "该文件未能提取", "detail": str(exc)})
                complete = False
            if progress is not None:
                progress({"files": files, "bytes": total, "candidates": len(codes)})
        if stopped:
            break
    # Keep identical codes from different files visible: names may bind the code to a player.
    unique = {(row.command, row.code, row.source, row.kind): row for row in codes}
    return {"codes": tuple(unique.values()), "files": files, "bytes": total, "complete": complete,
            "cancelled": bool(cancel is not None and cancel.is_set()), "warnings": warnings}


def read_live_codes(host, prefix="-load", *, cancel=None, progress=None):
    """Use the existing selected game/session, never enumerate a guessed target."""
    from war3_external_backend import ExternalMemoryBackend
    from war3_game_session import session_scope

    validate_prefix(prefix)
    session = host._game_session
    if (session.pid, session.hwnd) != (host.pid, host.hwnd):
        raise SaveExtractionError("游戏进程或窗口已变化，请先重新连接后再读取存档码。")
    with session.lock:
        with host._session_memory_factory(host.pid) as memory:
            session.prepare(memory)
            with session_scope(session):
                return ExternalMemoryBackend(session).read_save_codes(memory, prefix=prefix,
                    cancel=cancel, progress=progress)


def _atomic_new_file(path: Path, data: bytes):
    """Exports only create new files; never replace a user's map-generated save."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".save-code-", suffix=".pending", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(data); file.flush(); os.fsync(file.fileno())
        # On Windows os.rename rejects an existing destination; the source is already flushed.
        if path.exists():
            raise SaveExtractionError("所选导出文件已经存在，请换一个文件名；原文件未改动。")
        if os.name == "nt":
            os.rename(temporary, path)
        else:
            os.link(temporary, path); os.unlink(temporary)
        if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(data).digest():
            raise SaveExtractionError("导出文件读回不一致，请保留日志。")
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def export_codes(path, rows):
    path = Path(path)
    rows = tuple(rows)
    if not rows:
        raise SaveExtractionError("尚未提取到存档码，请先读取文件、粘贴文本或扫描游戏。")
    if path.suffix.lower() == ".json":
        data = json.dumps({"format": "war3-save-codes", "schema_version": 1,
            "created_at": datetime.now().astimezone().isoformat(), "map_validation": "not_performed",
            "codes": [row.to_dict() for row in rows]}, ensure_ascii=False, indent=2).encode("utf-8")
    else:
        lines = ["魔兽争霸存档码提取", "存档码候选；是否有效、属于哪个角色，以原地图的载入结果为准。", ""]
        for row in rows:
            lines.extend(["来源：" + row.source, "类型：" + ("原始片段，不能直接载入" if row.kind == "fragment" else "载入指令候选"),
                          row.command or row.code, ""])
        data = "\n".join(lines).encode("utf-8-sig")
    _atomic_new_file(path, data)
    return path


def log_extraction_failure(exc):
    root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "War3Trainer" / "log"
    name = "save-extraction-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".log"
    path = root / name
    text = "operation=save_extraction\n" + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    if isinstance(getattr(exc, "report", None), dict):
        text += "\nreport=" + json.dumps(exc.report, ensure_ascii=False, indent=2, default=str)
    _atomic_new_file(path, text.encode("utf-8"))
    exc.diagnostic_log_path = str(path)
    return path
