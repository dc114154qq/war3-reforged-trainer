# -*- mode: python ; coding: utf-8 -*-

import os

bridge_image = os.environ.get('RELEASE_207_BRIDGE_DLL', 'tools/war3_bridge_24268.dll')
icon_image = os.environ.get('RELEASE_207_ICON_DLL', 'tools/war3_talent_icon_display.dll')

a = Analysis(
    ['war3_reforged_trainer.py'],
    pathex=[],
    binaries=[
        ('tools/capstone.dll', 'capstone/lib'),
        (bridge_image, 'tools'),
        (icon_image, 'tools'),
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
        'war3_hero_attributes_protocol',
        'war3_attack_speed_protocol',
        'war3_position_protocol',
        'war3_position_target_protocol',
        'war3_unit_action_protocol',
        'war3_unit_stats_protocol',
        'war3_world_protocol',
        'war3_bulk_protocol',
        'war3_effect_protocol',
        'war3_world_effect_protocol',
        'war3_world_cast_protocol',
        'war3_spawn_protocol',
        'war3_mouse_protocol',
        'war3_screen_protocol',
        'war3_camera_protocol',
        'war3_terrain_protocol',
        'war3_map_bounds_protocol',
        'war3_equipment_protocol',
        'war3_extension_protocol',
        'war3_3_extension_catalog',
        'war3_new_equipment_catalog',
        'war3_new_equipment_ui',
        'war3_3_stats',
        'war3_stat_details_protocol',
        'war3_integrity',
        'war3_talent_icon_display',
        'war3_talent_icon_control_protocol',
        'pefile',
    ],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='War3ReforgedTrainer-v2.0.7',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
    upx_exclude=[], runtime_tmpdir=None, console=False,
    disable_windowed_traceback=False, uac_admin=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
    icon='assets/app_icon.ico', version='tools/war3-2.0.7-version-info.txt',
)
