# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['war3_reforged_trainer.py'],
    pathex=[],
    binaries=[
        ('tools/capstone.dll', 'capstone/lib'),
        ('tools/war3_bridge_24268.dll', 'tools'),
    ],
    datas=[('assets/app_icon.png', 'assets')],
    hiddenimports=['capstone', 'war3_runtime_check'],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='War3ReforgedTrainer-3.0.0.24268',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
    upx_exclude=[], runtime_tmpdir=None, console=False,
    disable_windowed_traceback=False, uac_admin=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
    icon='assets/app_icon.ico', version='tools/war3-3.0-version-info.txt',
)


