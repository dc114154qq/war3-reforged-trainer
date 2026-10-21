"""First-run checks for the desktop renderer; ordinary starts need no download."""
from pathlib import Path
import ctypes,hashlib,json,os,subprocess,sys,time,winreg

BOOTSTRAPPER_SHA256='f414de01c4680f0bb0694d1ea7803c6968f3a81bf6bad01b89bfc65dce14c2a2'
TITLE='魔兽争霸 III 修改器 · 运行环境'

def log(stage,**values):
    try:
        folder=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'War3Trainer/log'
        folder.mkdir(parents=True,exist_ok=True)
        with (folder/'desktop-runtime.jsonl').open('a',encoding='utf8') as f:
            f.write(json.dumps(dict(time=time.strftime('%Y-%m-%d %H:%M:%S'),stage=stage,**values),ensure_ascii=False)+'\n')
    except OSError:pass

def framework_release():
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full',0,
                            winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as key:
            return int(winreg.QueryValueEx(key,'Release')[0])
    except (OSError,ValueError,TypeError):return 0

def webview_version():
    if getattr(sys,'frozen',False):root=Path(sys._MEIPASS)/'webview'
    else:
        from importlib.util import find_spec
        spec=find_spec('webview')
        if spec is None or not spec.origin:return ''
        root=Path(spec.origin).parent
    loader=root/'lib/runtimes/win-x64/native/WebView2Loader.dll'
    dll=ctypes.WinDLL(str(loader));function=dll.GetAvailableCoreWebView2BrowserVersionString
    function.argtypes=(ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_void_p));function.restype=ctypes.c_long
    ptr=ctypes.c_void_p()
    free=ctypes.WinDLL('ole32').CoTaskMemFree;free.argtypes=(ctypes.c_void_p,);free.restype=None
    try:
        status=function(None,ctypes.byref(ptr))
        return ctypes.wstring_at(ptr) if status==0 and ptr.value else ''
    finally:
        if ptr.value:free(ptr)

def message(text,question=False):
    api=ctypes.WinDLL('user32').MessageBoxW
    api.argtypes=(ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_uint);api.restype=ctypes.c_int
    return api(None,text,TITLE,(0x24|0x10000) if question else (0x10|0x10000))==6

def install_webview():
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
    installer=root/'assets/webview2-bootstrapper.exe'
    if not installer.is_file() or hashlib.sha256(installer.read_bytes()).hexdigest()!=BOOTSTRAPPER_SHA256:
        raise RuntimeError('内置微软组件安装程序校验失败，请重新下载完整修改器。')
    # Microsoft's own installer presents progress. It is only started after Yes.
    return subprocess.run([str(installer),'/install'],timeout=900,check=False).returncode

def ensure_desktop_runtime(*,detect=webview_version,framework=framework_release,
                           ask=message,install=install_webview,record=log):
    try:
        release=framework()
        if release<394802:
            record('framework_missing',release=release)
            ask('本机缺少新版界面需要的微软 .NET Framework 组件。\n\n'
                '请安装 .NET Framework 4.8 后重新打开修改器。\n'
                '微软下载页：https://dotnet.microsoft.com/download/dotnet-framework/net48')
            return False
        version=detect()
        if version:
            record('ready',webview2=version,framework_release=release)
            return True
        record('webview2_missing',framework_release=release)
        approved=ask('本机缺少新版界面需要的微软 WebView2 运行组件。\n\n'
            '是否现在安装？首次安装需要联网，安装窗口将显示进度。\n'
            '安装完成后修改器会继续打开，无需安装 Python 或 Node.js。',question=True)
        if not approved:
            record('installation_cancelled');return False
        record('installation_started');exit_code=install();version=detect()
        record('installation_finished',exit_code=exit_code,webview2=version)
        if version:return True
        ask('微软 WebView2 组件尚未安装完成。请检查网络，安装完成后重新打开修改器。\n\n'
            f'安装结果：{exit_code}\n微软下载页：https://developer.microsoft.com/microsoft-edge/webview2/')
        return False
    except Exception as exc:
        record('startup_failed',exception=repr(exc))
        ask('新版界面的运行环境检查未完成。\n\n'+str(exc)+'\n\n请检查安装组件或重新下载完整修改器。')
        return False
