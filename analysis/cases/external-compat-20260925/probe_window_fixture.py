"""Disposable hidden message-loop window for the local hook control test."""

import ctypes as c
import os


P = c.c_void_p
U = c.c_uint32
user32 = c.WinDLL("user32", use_last_error=True)
user32.CreateWindowExW.argtypes = (U, c.c_wchar_p, c.c_wchar_p, U,
                                  c.c_int, c.c_int, c.c_int, c.c_int,
                                  P, P, P, P)
user32.CreateWindowExW.restype = P
user32.GetMessageW.argtypes = (P, P, U, U)
user32.GetMessageW.restype = c.c_int
user32.TranslateMessage.argtypes = (P,)
user32.DispatchMessageW.argtypes = (P,)


class Message(c.Structure):
    _fields_ = [("hwnd", P), ("message", U), ("wParam", c.c_size_t),
                ("lParam", c.c_ssize_t), ("time", U), ("point_x", c.c_long),
                ("point_y", c.c_long), ("private", U)]


hwnd = user32.CreateWindowExW(0, "STATIC", "war3-hook-probe-control", 0,
                              0, 0, 1, 1, None, None, None, None)
if not hwnd:
    raise c.WinError(c.get_last_error())
print(f"pid={os.getpid()} hwnd={int(hwnd)}", flush=True)
message = Message()
while user32.GetMessageW(c.byref(message), None, 0, 0) > 0:
    user32.TranslateMessage(c.byref(message))
    user32.DispatchMessageW(c.byref(message))
