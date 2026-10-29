"""Pinned, offline pjass validation with a separate classic payload gate."""
from functools import lru_cache
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
import time
import zipfile
from war3_object_tables import DefinitionError

COMPILER_SHA256 = '45911ae998b23155c8d408597c616cf080a3fa16b4cf2e1bacb239757c704d5c'
PACK_SHA256 = '79f091a087a2af4e54bd623cf08b213c562c289fef4fe670d9e965db0d93f2aa'


@lru_cache(1)
def dependencies():
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    compiler = root/'tools/map-script-pjass.exe'
    pack = root/'assets/map-script-validation-v1.zip'
    for path, expected in ((compiler, COMPILER_SHA256), (pack, PACK_SHA256)):
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise DefinitionError('地图脚本检查组件缺失或校验失败，请重新下载完整修改器。')
    with zipfile.ZipFile(pack) as archive:
        if len(archive.infolist()) != 5 or sum(x.file_size for x in archive.infolist()) > 8*1024*1024:
            raise DefinitionError('地图脚本参考资料结构异常。')
        manifest = json.loads(archive.read('manifest.json'))
        files = {name: archive.read(name) for name in manifest['files']}
    if set(files) != {'classic/common.j','classic/Blizzard.j','modern/common.j','modern/Blizzard.j'}:
        raise DefinitionError('地图脚本参考资料不完整。')
    for name, raw in files.items():
        expected = manifest['files'][name]
        if len(raw) != expected['bytes'] or hashlib.sha256(raw).hexdigest() != expected['sha256']:
            raise DefinitionError('地图脚本参考资料内容校验失败。')
    return compiler, files


def check_script(raw, folder, *, label, library='auto', cancel=None, include_blizzard=True):
    compiler, files = dependencies()
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(raw).hexdigest()
    # ASCII filenames also work with old Windows console codepages.
    source = folder/(digest[:20]+'.j')
    source.write_bytes(raw)
    logs = []
    for mode in (('classic','modern') if library == 'auto' else (library,)):
        common = folder/(mode+'-common.j')
        blizzard = folder/(mode+'-Blizzard.j')
        if not common.exists():
            common.write_bytes(files[mode+'/common.j'])
            blizzard.write_bytes(files[mode+'/Blizzard.j'])
        log = folder/(digest[:20]+'-'+mode+('' if include_blizzard else '-native-only')+'.log')
        with log.open('wb') as stream:
            arguments = [str(compiler), str(common)]
            if include_blizzard:
                arguments += ['+rb',str(blizzard),'-rb']
            arguments.append(str(source))
            process = subprocess.Popen(arguments,
                stdout=stream, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            deadline = time.monotonic()+25
            try:
                while process.poll() is None:
                    if cancel is not None and cancel.is_set():
                        raise InterruptedError('处理已停止，原文件已保留。')
                    if time.monotonic() > deadline or log.stat().st_size > 8*1024*1024:
                        raise DefinitionError('章节脚本检查超时或错误过多，原文件已保留。')
                    time.sleep(.025)
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait()
        logs.append(str(log))
        if process.returncode == 0:
            return dict(checked=True, library=mode, sha256=digest, compiler_sha256=COMPILER_SHA256,
                        log=str(log), attempts=logs, syntax_and_types=True, gameplay_tested=False,
                        blizzard_prelude=include_blizzard)
    output = log.read_bytes().decode('utf-8', errors='replace')
    lines = [line for line in output.splitlines() if '.j:' in line][:8]
    translated=[]
    for line in lines:
        match=re.search(r'\.j:(\d+):\s*(.*)',line)
        if not match:
            continue
        number,detail=match.groups()
        symbol=re.search(r'(?:Undeclared|Undefined) (function|variable) ([A-Za-z_][A-Za-z_0-9]*)',detail)
        if symbol:
            meaning=('调用了未声明函数 '+symbol[2]+'，可能依赖其他游戏接口或插件。' if symbol[1]=='function'
                     else '使用了未声明变量 '+symbol[2]+'。')
        elif 'syntax error' in detail.lower():
            meaning='语法不符合 JASS 规则。'
        elif 'already defined' in detail.lower() or 'allready defined' in detail.lower():
            meaning='名称与已有声明或保留类型重复。'
        else:
            meaning='未通过参数类型、返回值或语法检查，详细记录见日志。'
        translated.append('第 '+number+' 行：'+meaning)
    reason = '\n'.join(translated) or '脚本没有通过语法或类型检查，详细记录见日志。'
    exc = DefinitionError(f'{label}：脚本语法或接口检查未通过，原文件已保留。\n{reason}\n完整检查记录：{log}')
    exc.diagnostic_log_path = str(log)
    exc.user_details = [dict(scope=label, file='war3map.j', message='脚本语法或接口检查未通过。', impact=reason)]
    raise exc
