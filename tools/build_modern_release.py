"""Build and verify the reviewed WebView frontend using pinned game dependencies."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types

from PyInstaller.archive.readers import CArchiveReader
import pefile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dist-2.1.20-modern-verified'
CASE = ROOT / 'build/release-2.1.20-20261026/exe-build'
SPEC = 'War3ReforgedTrainer-Web-2.1.20.spec'
EXE = 'War3ReforgedTrainer-v2.1.20-Web.exe'
BRIDGE_IMAGE = None


def digest(raw):
    return hashlib.sha256(raw).hexdigest().upper()


def inputs():
    loader = importlib.util.spec_from_file_location('modern_legacy_inputs', ROOT / 'tools/build_release_2120.py')
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    paths = set(module.source_paths())
    paths.update({ROOT / SPEC, Path(__file__)})
    paths.add(ROOT / 'assets/webview2-bootstrapper.exe')
    paths.add(ROOT / 'tools/generate_war3_id_descriptions.py')
    paths.update(path for path in (ROOT / 'frontend/src').rglob('*') if path.is_file())
    paths.update(path for path in (ROOT / 'frontend/public').rglob('*') if path.is_file())
    paths.update(path for path in (ROOT / 'frontend/dist').rglob('*') if path.is_file())
    paths.update(ROOT / 'frontend' / name for name in ('package.json', 'package-lock.json', 'index.html',
                 'vite.config.ts', 'tsconfig.json', 'tsconfig.app.json', 'tsconfig.node.json'))
    return {path.relative_to(ROOT).as_posix(): digest(path.read_bytes()) for path in sorted(paths)}


def inspect(exe, source_root, source_hashes, baseline):
    pe = pefile.PE(str(exe), fast_load=False)
    fixed = pe.VS_FIXEDFILEINFO[0]
    assert (fixed.FileVersionMS, fixed.FileVersionLS) == ((2 << 16) | 1, 20 << 16)
    archive = CArchiveReader(str(exe))
    pyz = archive.open_embedded_archive('PYZ-00.pyz')
    modules = {}
    for name in pyz.toc:
        if not (name.startswith('war3_') or name.startswith('war3_services')):
            continue
        path = source_root / (name.replace('.', '/') + '.py')
        if not path.is_file():
            path = source_root / name.replace('.', '/') / '__init__.py'
        assert path.is_file(), name
        code = pyz.extract(name)
        assert isinstance(code, types.CodeType)
        assert code == compile(path.read_bytes(), code.co_filename, 'exec', dont_inherit=True), name
        modules[name] = digest(path.read_bytes())
    for name, expected in baseline['bundled_sha256'].items():
        assert digest(archive.extract(name)) == expected, name
    installer = 'assets/webview2-bootstrapper.exe'
    assert digest(archive.extract(installer.replace('/', '\\'))) == source_hashes[installer]
    data = {}
    for name in source_hashes:
        if name.startswith(('profiles/', 'frontend/dist/')):
            raw = archive.extract(name.replace('/', '\\'))
            assert digest(raw) == source_hashes[name], name
            data[name] = source_hashes[name]
    assert {'war3_desktop_bridge', 'war3_webview_viewport', 'war3_web_gui', 'war3_desktop_runtime'} <= set(pyz.toc)
    assert not any(n.startswith(('PyQt', 'PySide', 'cefpython3')) for n in pyz.toc)
    return dict(modules=modules, packaged_data=data, native=baseline['bundled_sha256'])


def native_baseline(baseline, bridge_image=None, expected_native=None):
    result = dict(baseline, bundled_sha256=dict(baseline['bundled_sha256']))
    key = next(k for k in result['bundled_sha256'] if k.replace('\\', '/').endswith('/war3_bridge_24268.dll'))
    if bridge_image is not None:
        image = Path(bridge_image).resolve(strict=True)
        subprocess.run([sys.executable, str(ROOT/'tools/verify_engine_bridge.py'), str(image), 'False'], check=True, cwd=ROOT)
        archive = pefile.PE(str(image))
        names = {e.name for e in archive.DIRECTORY_ENTRY_EXPORT.symbols}
        assert not any(n and (n.startswith(b'BridgeTest') or n.endswith(b'ProbeQuery')) for n in names), 'Use a production bridge'
        result['bundled_sha256'][key] = digest(image.read_bytes())
    if expected_native is not None:
        assert set(expected_native) == set(result['bundled_sha256'])
        assert all(expected_native[k] == result['bundled_sha256'][k] for k in expected_native if k != key)
        result['bundled_sha256'][key] = expected_native[key]
    return result, key


def build():
    top = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=ROOT, text=True).strip()
    assert Path(top).resolve() == ROOT.resolve()
    source_hashes = inputs()
    base_dir = ROOT / 'dist-native-baseline'
    baseline = json.loads((base_dir / 'current.json').read_text(encoding='utf8'))
    base_exe = base_dir / baseline['artifact']
    assert digest(base_exe.read_bytes()) == baseline['exe_sha256']
    archive = CArchiveReader(str(base_exe))
    package_baseline, bridge_key = native_baseline(baseline, BRIDGE_IMAGE)
    CASE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='modern-', dir=CASE, ignore_cleanup_errors=True) as temporary:
        stage = Path(temporary)
        source = stage / 'source'
        for name in source_hashes:
            destination = source / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, destination)
        native = stage / 'native'
        runtime = native / 'runtime'
        runtime.mkdir(parents=True)
        for name, expected in baseline['bundled_sha256'].items():
            raw = archive.extract(name)
            assert digest(raw) == expected
            if BRIDGE_IMAGE is not None and name == bridge_key:
                raw = Path(BRIDGE_IMAGE).read_bytes()
                assert digest(raw) == package_baseline['bundled_sha256'][name]
            (native / Path(name.replace('\\', '/')).name).write_bytes(raw)
        subprocess.run([sys.executable, str(ROOT/'tools/verify_engine_bridge.py'), str(native/'war3_bridge_24268.dll'), 'False'], check=True, cwd=ROOT)
        shutil.copy2(native / 'war3_mpq.dll', source / 'tools/war3_mpq.dll')
        for name in archive.toc:
            if '\\' not in name and (name.lower().startswith('api-ms-win-') or name.lower() == 'ucrtbase.dll'):
                (runtime / name).write_bytes(archive.extract(name))
        environment = dict(os.environ, RELEASE_2120_RUNTIME_DIR=str(runtime),
            RELEASE_210_BRIDGE_DLL=str(native / 'war3_bridge_24268.dll'),
            RELEASE_210_ICON_DLL=str(native / 'war3_talent_icon_display.dll'),
            RELEASE_210_SPEED_DLL=str(native / 'war3_speed_clock.dll'))
        with (CASE / 'pyinstaller-final.log').open('w', encoding='utf8') as log:
            process = subprocess.run([sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm',
                '--distpath', str(stage / 'dist'), '--workpath', str(stage / 'build'), SPEC],
                cwd=source, env=environment, stdout=log, stderr=subprocess.STDOUT)
        assert process.returncode == 0, 'See pyinstaller-final.log'
        exe = stage / 'dist' / EXE
        verified = inspect(exe, source, source_hashes, package_baseline)
        assert source_hashes == inputs(), 'Source changed during build'
        sha = digest(exe.read_bytes())
        artifact = Path(sha[:12]) / EXE
        destination = OUT / artifact
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            assert digest(destination.read_bytes()) == sha
        else:
            shutil.copy2(exe, destination)
        manifest = dict(ok=True, version='2.1.20', kind='reviewed_modern_frontend',
            status='built_not_published', artifact=artifact.as_posix(), exe_sha256=sha,
            exe_bytes=exe.stat().st_size, source_sha256=source_hashes,
            head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            source_inputs=len(source_hashes), baseline_exe_sha256=baseline['exe_sha256'],
            bridge_source=str(Path(BRIDGE_IMAGE).resolve()) if BRIDGE_IMAGE is not None else 'pinned_current_native_baseline', **verified)
        OUT.mkdir(parents=True, exist_ok=True)
        pending = OUT / 'current.json.pending'
        pending.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
        os.replace(pending, OUT / 'current.json')
        print(json.dumps(dict(ok=True, artifact=str(destination), sha256=sha,
                             modules=len(verified['modules']), inputs=len(source_hashes)), ensure_ascii=False), flush=True)


def verify():
    manifest = json.loads((OUT / 'current.json').read_text(encoding='utf8'))
    assert manifest['source_sha256'] == inputs()
    exe = OUT / manifest['artifact']
    assert digest(exe.read_bytes()) == manifest['exe_sha256']
    baseline = json.loads((ROOT / 'dist-native-baseline/current.json').read_text(encoding='utf8'))
    package_baseline, bridge_key = native_baseline(baseline, expected_native=manifest['native'])
    assert inspect(exe, ROOT, manifest['source_sha256'], package_baseline)['modules'] == manifest['modules']
    print(json.dumps(dict(ok=True, artifact=str(exe), sha256=manifest['exe_sha256']), ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--bridge-image', type=Path, help='Explicit production bridge verified before packaging')
    arguments = parser.parse_args()
    BRIDGE_IMAGE = arguments.bridge_image
    verify() if arguments.verify_only else build()
