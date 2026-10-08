"""Read save/load codes as text. No map scripts or preload files are executed."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
import time


MAX_CODE_LENGTH = 4096
_COLOR = re.compile(r"\|c[0-9a-fA-F]{8}|\|r")
_LITERAL = r'"((?:\\.|[^"\\])*)"'
_PRELOAD = re.compile(r"\bPreload\s*\(\s*" + _LITERAL, re.IGNORECASE)
_TOOLTIP = re.compile(
    r"\b(?:BlzSetAbilityTooltip|BlzSetAbilityExtendedTooltip|SetPlayerName)\s*\(\s*[^,\r\n]+,\s*"
    + _LITERAL, re.IGNORECASE,
)


class SaveExtractionError(ValueError):
    """A localized file/scanner failure, unrelated to game write state."""


@dataclass(frozen=True)
class SaveCode:
    code: str
    command: str
    source: str
    kind: str = "command"
    line: int = 0

    def to_dict(self):
        return asdict(self)


def validate_prefix(prefix: str) -> str:
    prefix = str(prefix).strip()
    if not re.fullmatch(r"[-!][A-Za-z][A-Za-z0-9_-]{0,31}", prefix):
        raise SaveExtractionError("载入指令格式不正确，请填写 -load 或地图实际使用的指令。")
    return prefix


def _unescape_literal(text: str) -> str:
    # Parse a limited string literal; never eval/exec a preload/JASS/Lua file.
    escapes = {"n": "\n", "r": "\r", "t": "\t", '"': '"', "\\": "\\"}
    return re.sub(r"\\([nrt\"\\])", lambda m: escapes[m[1]], text)


def _valid_code(code: str) -> bool:
    return (
        4 <= len(code) <= MAX_CODE_LENGTH
        and all(33 <= ord(ch) <= 126 for ch in code)
        and any(ch.isalnum() for ch in code)
        and code.casefold() not in {"xxxx", "xxxxx", "xxxxxx", "yourcode", "code", "null", "none"}
        and not any(ch in code for ch in ('"', "\\", "|", "<", ">"))
    )


def extract_text(text: str, source: str = "", prefix: str = "-load") -> tuple[SaveCode, ...]:
    """Preserve payload case and punctuation; results remain map-unverified candidates."""
    prefix = validate_prefix(prefix)
    pattern = re.compile(
        r"(?<![A-Za-z0-9_./\\-])" + re.escape(prefix)
        + r"[ \t]+([^\s\"\\|<>]{4,})", re.IGNORECASE,
    )
    labels = re.compile(r"(?:存档码|存檔碼|记录码|記錄碼|载入码|載入碼|save[ \t]+code|load[ \t]+code)"
                        r"[ \t]*[:：=][ \t]*([^\s\"\\|<>]{4,})", re.IGNORECASE)
    found = {}

    def parse(value, line):
        clean = _COLOR.sub("", value)
        for m in pattern.finditer(clean):
            code = m[1]
            if _valid_code(code):
                key = (code, "command")
                found.setdefault(key, SaveCode(code, prefix + " " + code, source, line=line))
        for m in labels.finditer(clean):
            code = m[1]
            if _valid_code(code):
                key = (code, "command")
                found.setdefault(key, SaveCode(code, prefix + " " + code, source, line=line))

    # Extract native string arguments first: raw script quoting/escapes are not codes.
    for match in _PRELOAD.finditer(text):
        parse(_unescape_literal(match[1]), text.count("\n", 0, match.start()) + 1)
    for line, value in enumerate(text.splitlines(), 1):
        parse(value, line)
    for match in _TOOLTIP.finditer(text):
        value = _COLOR.sub("", _unescape_literal(match[1])).strip()
        parse(value, text.count("\n", 0, match.start()) + 1)
        # Some maps split encoded data across tooltip natives; do not guess concatenation.
        if _valid_code(value) and len(value) >= 12 and not any(row.code == value for row in found.values()):
            found.setdefault((value, "fragment"), SaveCode(value, "", source, "fragment",
                text.count("\n", 0, match.start()) + 1))
    return tuple(found.values())


def decode_text(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig")
    if b"\0" in data:
        if len(data) % 2 == 0 and data[1::2].count(0) >= max(1, len(data) // 8):
            return data.decode("utf-16-le")
        raise SaveExtractionError("文件含有二进制数据，不是可提取存档码的文本文件。")
    for encoding in ("utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise SaveExtractionError("文件文字编码未能识别，请粘贴游戏显示的存档码后再提取。")


def extract_buffer(data: bytes, source: str = "", prefix: str = "-load") -> tuple[SaveCode, ...]:
    """Scan complete terminated UTF-8/ASCII or UTF-16 strings, not truncated chunk tails."""
    found = {}
    for match in re.finditer(rb"[\x20-\x7e\x80-\xff\t\r\n]{6,}(?=[\x00-\x08\x0b\x0c\x0e-\x1f])", data):
        value = match[0].decode("utf-8", errors="replace")
        for row in extract_text(value, source, prefix):
            if row.kind == "command":
                found.setdefault(row.command, row)
    wide_command = re.compile(re.escape(validate_prefix(prefix).encode("utf-16-le"))
        + rb"(?:[ \t]\x00)+(?:[\x21-\x7e]\x00){4,}(?=\x00\x00)", re.IGNORECASE)
    for match in wide_command.finditer(data):
        for row in extract_text(match[0].decode("utf-16-le"), source, prefix):
            if row.kind == "command":
                found.setdefault(row.command, row)
    return tuple(found.values())


def scan_memory_codes(memory, *, prefix="-load", cancel=None, progress=None,
                      max_bytes=2 * 1024 * 1024 * 1024, max_seconds=20.0, clock=time.monotonic):
    """Candidates from readable private heaps; retain boundaries, expose all scan gaps."""
    validate_prefix(prefix)
    if max_bytes <= 0 or max_seconds <= 0:
        raise SaveExtractionError("扫描范围和扫描时间必须大于零。")
    regions = sorted((r for r in memory.regions() if r.typ == 0x20000), key=lambda r: r.base)
    planned = sum(r.size for r in regions)
    started = clock()
    read = attempted = skipped = 0
    last_progress = started
    found = {}
    reason = "complete"
    overlap = 2 * MAX_CODE_LENGTH + 512
    carry = b""
    previous_end = None
    for region in regions:
        if previous_end != region.base:
            carry = b""
        offset = 0
        while offset < region.size:
            if cancel is not None and cancel.is_set():
                reason = "cancelled"; break
            now = clock()
            if now - started >= max_seconds:
                reason = "time_limit"; break
            if attempted >= max_bytes:
                reason = "size_limit"; break
            address = region.base + offset
            size = min(64 * 1024, region.size - offset, max_bytes - attempted)
            attempted += size
            offset += size
            try:
                chunk = memory.read(address, size)
                if len(chunk) != size:
                    raise OSError("partial memory read")
            except OSError:
                skipped += size
                carry = b""
                previous_end = None
                continue
            read += len(chunk)
            data = carry + chunk
            for row in extract_buffer(data, "游戏内存", prefix):
                found.setdefault(row.command, row)
            carry = data[-overlap:]
            previous_end = address + size
            if progress is not None and now - last_progress >= 0.25:
                progress({"bytes": read, "planned_bytes": planned, "candidates": len(found)})
                last_progress = now
        if reason != "complete":
            break
    return {"codes": tuple(found.values()), "bytes": read, "attempted_bytes": attempted,
            "planned_bytes": planned, "skipped_bytes": skipped,
            "complete": reason == "complete" and skipped == 0, "stop_reason": reason,
            "cancelled": reason == "cancelled", "map_validation": "not_performed"}
