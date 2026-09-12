"""Verify a new clone checkpoint archive and run its offline self-test."""
from pathlib import Path
import hashlib
import json
import marshal
import os
import re
import shutil
import subprocess
import sys
import pefile
from PyInstaller.archive.readers import CArchiveReader

root = Path(__file__).resolve().parents[1]
revision = sys.argv[1]
assert re.fullmatch(r'[0-9a-f]{7,40}', revision)
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
assert head.startswith(revision)
subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', 'war3_reforged_trainer.py', 'war3_ui_i18n.py', 'war3_runtime_check.py', 'tools/war3_native_helper.dll'], cwd=root, check=True)
build = root/f'dist-v1.0.19-clone-{revision}'/'魔兽争霸3重制版修改器.exe'
archive = CArchiveReader(str(build))
main = marshal.loads(archive.extract('war3_reforged_trainer'))
assert main == compile((root/'war3_reforged_trainer.py').read_bytes(), main.co_filename, 'exec', optimize=0)
pyz = archive.open_embedded_archive(next(key for key in archive.toc if key.endswith('.pyz')))
for name in ('war3_ui_i18n', 'war3_runtime_check'):
    code = pyz.extract(name)
    assert code == compile((root/(name+'.py')).read_bytes(), code.co_filename, 'exec', optimize=0)
helper = (root/'tools/war3_native_helper.dll').read_bytes()
key = next(key for key in archive.toc if key.replace('\\', '/') == 'tools/war3_native_helper.dll')
assert archive.extract(key) == helper
pe = pefile.PE(str(build))
info = pe.VS_FIXEDFILEINFO[0]
assert (info.FileVersionMS, info.FileVersionLS) == (65536, 19 << 16)
assert pe.FILE_HEADER.Machine == 0x8664 and pe.OPTIONAL_HEADER.Subsystem == 2
pe.close()
destination = root.parents[1]/'releases'/f'1.0.19-{revision}'
destination.mkdir(exist_ok=False)
exe = destination/f'War3ReforgedTrainer-v1.0.19-{revision}.exe'
shutil.copy2(build, exe)
sha = lambda data: hashlib.sha256(data).hexdigest()
assert sha(exe.read_bytes()) == sha(build.read_bytes())
environment = os.environ.copy()
environment['__COMPAT_LAYER'] = 'RunAsInvoker'
runtime_path = destination/'runtime-self-test.json'
subprocess.run([str(exe), '--runtime-self-test', str(runtime_path)], env=environment, check=True, timeout=60)
runtime = json.loads(runtime_path.read_text(encoding='utf8'))
assert runtime['ok'] and runtime['frozen']
assert runtime['helper_sha256'] == sha(helper)
assert runtime['decoder_sha256'] == sha((root/'tools/capstone.dll').read_bytes())
protocol = int(re.search(r'NATIVE_HELPER_VERSION\s*=\s*(\d+)', (root/'war3_reforged_trainer.py').read_text(encoding='utf8')).group(1))
report = dict(ok=True, source_commit=head, file_version='1.0.19.0', native_protocol=protocol,
              exe=str(exe), exe_bytes=exe.stat().st_size, exe_sha256=sha(exe.read_bytes()),
              bundled_sources_match=True, runtime=runtime)
(root/f'analysis/package-{revision}-verification.json').write_text(json.dumps(report, indent=2), encoding='utf8')
print(json.dumps(report, indent=2))
