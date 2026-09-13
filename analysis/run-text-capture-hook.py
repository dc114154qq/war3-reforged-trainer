"""Load the research-only capture hook; unhook after its one-shot result."""
import ctypes
import hashlib
import json
from pathlib import Path
import struct
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from war3_reforged_trainer import kernel32,user32,find_war3
pid=int(sys.argv[1])
directory=ROOT/'analysis/native-bootstrap-24268'
status=directory/f'capture-{pid}.status'
raw=directory/f'capture-{pid}.raw'
assert not status.exists() and not raw.exists(), 'Preserve earlier captures'
hwnd,actual_pid=find_war3(pid)
thread=user32.GetWindowThreadProcessId(hwnd,None)
print(f'capture pid={actual_pid} hwnd={hwnd:#x} thread={thread}',flush=True)
dll=kernel32.LoadLibraryW(str(directory/'capture.dll'))
if not dll: raise ctypes.WinError(ctypes.get_last_error())
hook=None
try:
    proc=kernel32.GetProcAddress(dll,b'CaptureHook')
    if not proc: raise ctypes.WinError(ctypes.get_last_error())
    hook=user32.SetWindowsHookExW(4,proc,dll,thread)
    if not hook: raise ctypes.WinError(ctypes.get_last_error())
    reply=ctypes.c_void_p()
    if not user32.SendMessageTimeoutW(hwnd,0,0,0,2,5000,ctypes.byref(reply)):
        raise ctypes.WinError(ctypes.get_last_error())
    deadline=time.monotonic()+40
    while not status.exists():
        if time.monotonic()>deadline: raise TimeoutError('Capture hook did not return')
        user32.SendMessageTimeoutW(hwnd,0,0,0,2,150,ctypes.byref(reply))
        time.sleep(0.05)
    # The writer opens status with FILE_SHARE_READ; wait for the complete payload.
    while True:
        data=status.read_bytes()
        if len(data)>=16:
            magic,error,size,count=struct.unpack_from('<4I',data)
            if len(data)==16+4*count: break
        if time.monotonic()>deadline: raise TimeoutError('Incomplete capture status')
        time.sleep(0.05)
    assert magic==0x24268001
    gaps=list(struct.unpack_from(f'<{count}I',data,16))
    report=dict(pid=pid,error=error,bytes=size,unreadable_pages=count,complete=error==0 and count==0,
                gaps=[hex(rva) for rva in gaps],read_only_game_state=True)
    if raw.exists(): report['sha256']=hashlib.sha256(raw.read_bytes()).hexdigest()
    (directory/'capture-summary.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='gaps'},indent=2))
finally:
    if hook: user32.UnhookWindowsHookEx(hook)
    kernel32.FreeLibrary(dll)
