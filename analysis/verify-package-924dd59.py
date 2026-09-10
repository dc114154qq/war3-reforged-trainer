from pathlib import Path
import hashlib,json,marshal,os,shutil,subprocess
import pefile
from PyInstaller.archive.readers import CArchiveReader
root=Path.cwd()
build=root/'dist-v1.0.19-inventory-transform-924dd59'/'魔兽争霸3重制版修改器.exe'
a=CArchiveReader(str(build))
main=marshal.loads(a.extract('war3_reforged_trainer'))
assert main==compile((root/'war3_reforged_trainer.py').read_bytes(),main.co_filename,'exec',optimize=0)
pyz=a.open_embedded_archive(next(k for k in a.toc if k.endswith('.pyz')))
for name in ('war3_ui_i18n','war3_runtime_check'):
    code=pyz.extract(name)
    assert code==compile((root/(name+'.py')).read_bytes(),code.co_filename,'exec',optimize=0)
helper=(root/'tools/war3_native_helper.dll').read_bytes()
key=next(k for k in a.toc if k.replace('\\','/')=='tools/war3_native_helper.dll')
assert a.extract(key)==helper
pe=pefile.PE(str(build));info=pe.VS_FIXEDFILEINFO[0]
assert (info.FileVersionMS,info.FileVersionLS)==(65536,19<<16)
assert pe.FILE_HEADER.Machine==0x8664 and pe.OPTIONAL_HEADER.Subsystem==2
pe.close()
dest=Path(r'C:\Users\14186\Desktop\xiugai\releases\1.0.19-924dd59')
dest.mkdir(exist_ok=False)
exe=dest/'War3ReforgedTrainer-v1.0.19-924dd59.exe'
shutil.copy2(build,exe)
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(exe.read_bytes())==sha(build.read_bytes())
env=os.environ.copy();env['__COMPAT_LAYER']='RunAsInvoker'
runtime_path=dest/'runtime-self-test.json'
subprocess.run([str(exe),'--runtime-self-test',str(runtime_path)],env=env,check=True,timeout=60)
runtime=json.loads(runtime_path.read_text())
assert runtime['ok'] and runtime['frozen']
assert runtime['helper_sha256']==sha(helper)
assert runtime['decoder_sha256']==sha((root/'tools/capstone.dll').read_bytes())
report=dict(ok=True,source_commit='924dd59',file_version='1.0.19.0',native_protocol=65,exe=str(exe),exe_bytes=exe.stat().st_size,exe_sha256=sha(exe.read_bytes()),bundled_sources_match=True,runtime=runtime)
(root/'analysis/package-924dd59-verification.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report,indent=2))
