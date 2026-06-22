import argparse
import ctypes
from pathlib import Path

from PIL import Image


user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)


def make_dpi_aware():
    # Per-monitor v2 when available, system DPI aware as fallback.
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def capture(path: str):
    make_dpi_aware()
    sm_xvirtualscreen = 76
    sm_yvirtualscreen = 77
    sm_cxvirtualscreen = 78
    sm_cyvirtualscreen = 79
    left = user32.GetSystemMetrics(sm_xvirtualscreen)
    top = user32.GetSystemMetrics(sm_yvirtualscreen)
    width = user32.GetSystemMetrics(sm_cxvirtualscreen)
    height = user32.GetSystemMetrics(sm_cyvirtualscreen)

    hdc_screen = user32.GetDC(None)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
    old = gdi32.SelectObject(hdc_mem, hbmp)
    srccopy = 0x00CC0020
    if not gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, left, top, srccopy):
        raise ctypes.WinError(ctypes.get_last_error())

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", ctypes.c_uint32),
            ("biWidth", ctypes.c_int32),
            ("biHeight", ctypes.c_int32),
            ("biPlanes", ctypes.c_uint16),
            ("biBitCount", ctypes.c_uint16),
            ("biCompression", ctypes.c_uint32),
            ("biSizeImage", ctypes.c_uint32),
            ("biXPelsPerMeter", ctypes.c_int32),
            ("biYPelsPerMeter", ctypes.c_int32),
            ("biClrUsed", ctypes.c_uint32),
            ("biClrImportant", ctypes.c_uint32),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", ctypes.c_uint32 * 3)]

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = width
    bmi.bmiHeader.biHeight = -height
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0
    buf = ctypes.create_string_buffer(width * height * 4)
    lines = gdi32.GetDIBits(hdc_mem, hbmp, 0, height, buf, ctypes.byref(bmi), 0)
    if lines != height:
        raise ctypes.WinError(ctypes.get_last_error())

    image = Image.frombuffer("RGBA", (width, height), buf, "raw", "BGRA", 0, 1)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    image.save(path)

    gdi32.SelectObject(hdc_mem, old)
    gdi32.DeleteObject(hbmp)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(None, hdc_screen)
    print(f"{path} {width}x{height} origin={left},{top}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "output",
        nargs="?",
        default=r"D:\War3CodexWork\reforged-trainer\physical-screen.png",
    )
    args = parser.parse_args()
    capture(args.output)
