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
        'war3_ability_field_protocol',
        'war3_item_protocol',
        'war3_item_catalog_protocol',
        'war3_casc_catalog_24268',
        'war3_item_field_protocol',
        'war3_selection_protocol',
        'war3_hero_protocol',
        'war3_position_protocol',
        'war3_position_target_protocol',
        'war3_unit_action_protocol',
        'war3_world_protocol',
        'war3_bulk_protocol',
        'war3_effect_protocol',
        'war3_world_effect_protocol',
        'war3_spawn_protocol',
        'war3_mouse_protocol',
        'war3_screen_protocol',
        'war3_camera_protocol',
        'war3_terrain_protocol',
        'war3_map_bounds_protocol',
        'war3_equipment_protocol',
        'war3_integrity',
    ],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='War3ReforgedTrainer-v2.0.3',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
    upx_exclude=[], runtime_tmpdir=None, console=False,
    # The game normally runs at medium integrity.  Forcing the trainer to
    # high integrity makes the thread hook cross an integrity boundary and
    # can fail inside SetWindowsHookExW.  Run at the caller's integrity so
    # the bridge and the target share the same UI/security boundary.
    disable_windowed_traceback=False, uac_admin=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
    icon='assets/app_icon.ico', version='tools/war3-2.0.3-version-info.txt',
)
