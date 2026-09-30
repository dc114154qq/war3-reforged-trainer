"""Beta metadata and package guards; does not build or publish an executable."""
import ast
from pathlib import Path
from types import SimpleNamespace
import pytest
from PyInstaller.utils.win32.versioninfo import load_version_info_from_text_file
from war3_operations import OPERATIONS
from tools import build_release_210 as release


def test_source_windows_and_builder_identify_beta():
    tree=ast.parse(Path('war3_reforged_trainer.py').read_text(encoding='utf-8'))
    constants={n.targets[0].id:n.value.value for n in tree.body
               if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)
               and isinstance(n.value,ast.Constant)}
    assert constants['APP_VERSION']=='2.1.0'
    assert constants['APP_RELEASE_CHANNEL']=='beta'
    assert '\u6d4b\u8bd5\u7248' in constants['PRODUCT_EDITION_LABEL']
    version=load_version_info_from_text_file('tools/war3-2.1.0-beta-version-info.txt')
    assert version.ffi.fileVersionMS==(2<<16)|1
    assert version.ffi.fileVersionLS==0
    assert version.ffi.fileFlags & 2
    assert release.VERSION==(2,1,0,0)
    assert release.EXE_NAME=='War3ReforgedTrainer-v2.1.0-beta.exe'
    assert release.BRANCH=='codex/war3-modular-adapters-20260926'


def test_spec_includes_all_dynamic_protocols_and_profile():
    calls={}
    def analysis(*args,**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(pure=[],scripts=[],binaries=[],datas=[])
    namespace={'Analysis':analysis,'PYZ':lambda *args:None,'EXE':lambda *args,**kwargs:None}
    exec(compile(Path('War3ReforgedTrainer-2.1.0-beta.spec').read_text(encoding='utf-8'),'<spec>','exec'),namespace)
    required={s.protocol for s in OPERATIONS.values() if s.protocol}
    assert required <= set(calls['hiddenimports'])
    assert ('profiles/*.json','profiles') in calls['datas']
    assert ('third_party/minhook/LICENSE.txt','licenses') in calls['datas']
    assert 'war3_speed_clock_backend' in calls['hiddenimports']


def test_source_manifest_covers_services_profile_and_beta_notes():
    paths={p.relative_to(release.ROOT).as_posix() for p in release.source_paths()}
    assert {'war3_game_session.py','war3_engine_transport.py','war3_services/units.py',
            'profiles/3.0.0.24268.json','RELEASE_NOTES_v2.1.0-beta.md',
            'tools/build_release_210.py','War3ReforgedTrainer-2.1.0-beta.spec'} <= paths


@pytest.mark.parametrize('missing',[None,'profile','protocol','service','prerelease','speed_clock','license'])
def test_package_verifier_rejects_incomplete_beta(monkeypatch,tmp_path,missing):
    real_pe=release.pefile.PE
    bridge=Path('build/architecture-runtime/war3_bridge_24268.dll').read_bytes()
    parsed_bridge=real_pe(data=bridge)
    clock_bytes=Path('build/speed-clock-runtime/war3_speed_clock.dll').read_bytes()
    parsed_clock=real_pe(data=clock_bytes)
    fixed=SimpleNamespace(FileVersionMS=(2<<16)|1,FileVersionLS=0,
                          FileFlags=0 if missing=='prerelease' else 2)
    def pe(*args,**kwargs):
        return (parsed_clock if kwargs['data']==clock_bytes else parsed_bridge) if 'data' in kwargs else SimpleNamespace(VS_FIXEDFILEINFO=[fixed])
    monkeypatch.setattr(release.pefile,'PE',pe)
    modules={s.protocol for s in OPERATIONS.values() if s.protocol}
    modules.update('war3_services.'+p.stem for p in Path('war3_services').glob('*.py') if p.stem!='__init__')
    modules.update({'war3_game_session','war3_game_profile','war3_capabilities','war3_external_backend','war3_speed_clock_backend'})
    if missing=='protocol':modules.remove('war3_talent_order_protocol')
    if missing=='service':modules.remove('war3_services.units')
    data={'profiles\\'+path.name:path.read_bytes() for path in (release.ROOT/'profiles').glob('*.json')}
    data['licenses\\LICENSE.txt']=(release.ROOT/'third_party/minhook/LICENSE.txt').read_bytes()
    data[release.PACKAGE_BINARIES[2]]=clock_bytes
    toc={'PYZ-00.pyz',*release.PACKAGE_BINARIES}
    toc.update(data)
    if missing=='profile':toc.remove('profiles\\3.0.0.24268.json')
    if missing=='license':toc.remove('licenses\\LICENSE.txt')
    if missing=='speed_clock':toc.remove(release.PACKAGE_BINARIES[2])
    archive=SimpleNamespace(toc=toc,extract=lambda name:data[name] if name in data else bridge,
                            open_embedded_archive=lambda _:SimpleNamespace(toc=modules))
    monkeypatch.setattr(release,'CArchiveReader',lambda _:archive)
    if missing:
        with pytest.raises(RuntimeError):release.inspect_exe(tmp_path/'fixture.exe')
    else:
        assert set(release.inspect_exe(tmp_path/'fixture.exe'))==set(release.PACKAGE_BINARIES)
