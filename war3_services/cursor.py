"""Read a physical viewport without restoring or focusing the game window."""
import ctypes

class Rect(ctypes.Structure):
    _fields_=[('left',ctypes.c_long),('top',ctypes.c_long),('right',ctypes.c_long),('bottom',ctypes.c_long)]
class Point(ctypes.Structure):
    _fields_=[('x',ctypes.c_long),('y',ctypes.c_long)]
class Placement(ctypes.Structure):
    _fields_=[('length',ctypes.c_uint),('flags',ctypes.c_uint),('show',ctypes.c_uint),('minimum',Point),('maximum',Point),('normal',Rect)]
class MonitorInfo(ctypes.Structure):
    _fields_=[('size',ctypes.c_uint),('monitor',Rect),('work',Rect),('flags',ctypes.c_uint)]

def projectable_cursor(snapshot,*,cursor,origin,size):
    width,height=size;x,y=cursor[0]-origin[0],cursor[1]-origin[1]
    if width<=0 or height<=0:raise RuntimeError('游戏视口尺寸无效，未移动单位')
    if not 0<=x<width or not 0<=y<height:
        raise RuntimeError('光标不在游戏窗口的正常显示区域内，未移动单位')
    result=dict(snapshot,screen=(x,y),screen_space='client_pixels')
    return result,(width,height),1.0

def projection_viewport(hwnd,snapshot):
    """Win32 coordinates are read in one DPI context; minimized sentinel
    coordinates never enter the game's world-position calculation.
    """
    api=ctypes.WinDLL('user32',use_last_error=True);window=ctypes.c_void_p(hwnd)
    set_dpi=api.SetThreadDpiAwarenessContext
    set_dpi.argtypes=[ctypes.c_void_p];set_dpi.restype=ctypes.c_void_p
    previous=set_dpi(ctypes.c_void_p(-4))
    if not previous:raise ctypes.WinError(ctypes.get_last_error())
    try:
        signatures={
            'GetCursorPos':([ctypes.POINTER(Point)],ctypes.c_int),
            'GetClientRect':([ctypes.c_void_p,ctypes.POINTER(Rect)],ctypes.c_int),
            'ClientToScreen':([ctypes.c_void_p,ctypes.POINTER(Point)],ctypes.c_int),
            'IsIconic':([ctypes.c_void_p],ctypes.c_int),
            'GetWindowPlacement':([ctypes.c_void_p,ctypes.POINTER(Placement)],ctypes.c_int),
            'GetWindowLongPtrW':([ctypes.c_void_p,ctypes.c_int],ctypes.c_ssize_t),
            'GetDpiForWindow':([ctypes.c_void_p],ctypes.c_uint),
            'AdjustWindowRectExForDpi':([ctypes.POINTER(Rect),ctypes.c_uint,ctypes.c_int,ctypes.c_uint,ctypes.c_uint],ctypes.c_int),
            'MonitorFromWindow':([ctypes.c_void_p,ctypes.c_uint],ctypes.c_void_p),
            'GetMonitorInfoW':([ctypes.c_void_p,ctypes.POINTER(MonitorInfo)],ctypes.c_int),
        }
        for name,(args,restype) in signatures.items():
            fn=getattr(api,name);fn.argtypes=args;fn.restype=restype
        cursor=Point()
        if not api.GetCursorPos(ctypes.byref(cursor)):raise ctypes.WinError(ctypes.get_last_error())
        if not api.IsIconic(window):
            client=Rect();origin=Point()
            if not api.GetClientRect(window,ctypes.byref(client)) or not api.ClientToScreen(window,ctypes.byref(origin)):
                raise ctypes.WinError(ctypes.get_last_error())
            size=(client.right-client.left,client.bottom-client.top)
        else:
            placement=Placement();placement.length=ctypes.sizeof(placement)
            if not api.GetWindowPlacement(window,ctypes.byref(placement)):raise ctypes.WinError(ctypes.get_last_error())
            style=api.GetWindowLongPtrW(window,-16)&0xffffffff
            extended=api.GetWindowLongPtrW(window,-20)&0xffffffff
            borders=Rect();dpi=api.GetDpiForWindow(window)
            if not dpi or not api.AdjustWindowRectExForDpi(ctypes.byref(borders),style,0,extended,dpi):
                raise ctypes.WinError(ctypes.get_last_error())
            normal=placement.normal;offset_x=offset_y=0
            if not extended&0x80:
                monitor=api.MonitorFromWindow(window,2);info=MonitorInfo();info.size=ctypes.sizeof(info)
                if not monitor or not api.GetMonitorInfoW(monitor,ctypes.byref(info)):raise ctypes.WinError(ctypes.get_last_error())
                offset_x=info.work.left-info.monitor.left;offset_y=info.work.top-info.monitor.top
            origin=Point(normal.left+offset_x-borders.left,normal.top+offset_y-borders.top)
            size=(normal.right-normal.left-(borders.right-borders.left),normal.bottom-normal.top-(borders.bottom-borders.top))
        return projectable_cursor(snapshot,cursor=(cursor.x,cursor.y),origin=(origin.x,origin.y),size=size)
    finally:set_dpi(ctypes.c_void_p(previous))
