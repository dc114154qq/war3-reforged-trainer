# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['war3_reforged_trainer.py'],
    pathex=[],
    binaries=[
        ('tools/capstone.dll', 'capstone/lib'),
        ('tools/war3_bridge_24268.dll', 'tools'),
    ],
    datas=[('assets/app_icon.png', 'assets')],
    hiddenimports=[
        'capstone',
        'war3_runtime_check',
        'war3_clone_protocol',
        'war3_engine_24268',
        'war3_engine_transport',
        'war3_ability_protocol',
        'war3_item_protocol',
        'war3_selection_protocol',
        'war3_hero_protocol',
    ],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='War3ReforgedTrainer-v2.0.0-test',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
    upx_exclude=[], runtime_tmpdir=None, console=False,
    disable_windowed_traceback=False, uac_admin=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
    icon='assets/app_icon.ico', version='tools/war3-2.0-test-version-info.txt',
)
