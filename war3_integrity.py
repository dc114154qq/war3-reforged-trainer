"""Windows integrity-level matching for the current-engine bridge."""

import ctypes
import os


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TOKEN_QUERY = 0x0008
TOKEN_INTEGRITY_LEVEL = 25


class SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", ctypes.c_ulong)]


class TOKEN_MANDATORY_LABEL(ctypes.Structure):
    _fields_ = [("Label", SID_AND_ATTRIBUTES)]


def _api(library, name, result, *args):
    function = getattr(library, name)
    function.restype = result
    function.argtypes = args
    return function


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

OpenProcess = _api(
    kernel32,
    "OpenProcess",
    ctypes.c_void_p,
    ctypes.c_ulong,
    ctypes.c_bool,
    ctypes.c_ulong,
)
CloseHandle = _api(kernel32, "CloseHandle", ctypes.c_bool, ctypes.c_void_p)
GetCurrentProcess = _api(kernel32, "GetCurrentProcess", ctypes.c_void_p)
OpenProcessToken = _api(
    advapi32,
    "OpenProcessToken",
    ctypes.c_bool,
    ctypes.c_void_p,
    ctypes.c_ulong,
    ctypes.POINTER(ctypes.c_void_p),
)
GetTokenInformation = _api(
    advapi32,
    "GetTokenInformation",
    ctypes.c_bool,
    ctypes.c_void_p,
    ctypes.c_ulong,
    ctypes.c_void_p,
    ctypes.c_ulong,
    ctypes.POINTER(ctypes.c_ulong),
)
GetSidSubAuthorityCount = _api(
    advapi32,
    "GetSidSubAuthorityCount",
    ctypes.POINTER(ctypes.c_ubyte),
    ctypes.c_void_p,
)
GetSidSubAuthority = _api(
    advapi32,
    "GetSidSubAuthority",
    ctypes.POINTER(ctypes.c_ulong),
    ctypes.c_void_p,
    ctypes.c_ulong,
)


def _integrity_from_token(token):
    required = ctypes.c_ulong()
    ctypes.set_last_error(0)
    GetTokenInformation(
        token,
        TOKEN_INTEGRITY_LEVEL,
        None,
        0,
        ctypes.byref(required),
    )
    if not required.value:
        return None
    buffer = ctypes.create_string_buffer(required.value)
    if not GetTokenInformation(
        token,
        TOKEN_INTEGRITY_LEVEL,
        buffer,
        required.value,
        ctypes.byref(required),
    ):
        return None
    label = ctypes.cast(buffer, ctypes.POINTER(TOKEN_MANDATORY_LABEL)).contents
    sid = label.Label.Sid
    if not sid:
        return None
    count = GetSidSubAuthorityCount(sid)
    if not count or not count.contents.value:
        return None
    rid = GetSidSubAuthority(sid, count.contents.value - 1)
    if not rid:
        return None
    value = int(rid.contents.value)
    return {
        "rid": value,
        "name": {
            0x1000: "low",
            0x2000: "medium",
            0x2100: "medium_plus",
            0x3000: "high",
            0x4000: "system",
        }.get(value, f"rid_{value}"),
    }


def process_integrity(pid=None):
    """Return integrity data without enabling debug privilege or scanning processes."""
    pid = int(os.getpid() if pid is None else pid)
    handle = GetCurrentProcess() if pid == os.getpid() else OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION,
        False,
        pid,
    )
    if not handle:
        return {"pid": pid, "error": ctypes.get_last_error()}
    token = ctypes.c_void_p()
    try:
        if not OpenProcessToken(handle, TOKEN_QUERY, ctypes.byref(token)):
            return {"pid": pid, "error": ctypes.get_last_error()}
        result = _integrity_from_token(token)
        if result is None:
            return {"pid": pid, "error": ctypes.get_last_error() or 1}
        result["pid"] = pid
        return result
    finally:
        if token:
            CloseHandle(token)
        if pid != os.getpid():
            CloseHandle(handle)


def require_matching_integrity(target_pid):
    """Return a report or raise only when both levels are known and differ."""
    trainer = process_integrity()
    target = process_integrity(target_pid)
    report = {"trainer": trainer, "target": target, "matched": None}
    if "name" not in trainer or "name" not in target:
        return report
    report["matched"] = trainer["name"] == target["name"]
    if not report["matched"]:
        raise RuntimeError(
            "修改器与游戏完整性级别不一致："
            f"trainer={trainer['name']} target={target['name']}；"
            "请以与游戏相同权限重新启动修改器"
        )
    return report
