# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path
import capstone
from war3_operations import OPERATIONS

bridge_image = os.environ.get('RELEASE_210_BRIDGE_DLL', 'tools/war3_bridge_24268.dll')
icon_image = os.environ.get('RELEASE_210_ICON_DLL', 'tools/war3_talent_icon_display.dll')
speed_candidate = Path('build/speed-clock-runtime/war3_speed_clock.dll')
speed_image = os.environ.get('RELEASE_210_SPEED_DLL', str(speed_candidate) if speed_candidate.exists() else 'tools/war3_speed_clock.dll')
capstone_image = str(Path(capstone.__file__).with_name('lib') / 'capstone.dll')

a = Analysis(
    ['war3_web_gui.py'],
    pathex=[],
    binaries=[
        (capstone_image, 'capstone/lib'),
        (bridge_image, 'tools'),
        (icon_image, 'tools'),
        (speed_image, 'tools'),
        ('tools/war3_mpq.dll', 'tools'),
    ],
    datas=[
        ('assets/app_icon.png', 'assets'),
        ('assets/extension-definitions-v1.zip', 'assets'),
        ('assets/webview2-bootstrapper.exe', 'assets'),
        ('third_party/stormlib/StormLib-LICENSE.txt', 'licenses'),
        ('profiles/*.json', 'profiles'),
        ('profiles/discovery/*.json', 'profiles/discovery'),
        ('third_party/minhook/LICENSE.txt', 'licenses'),
        ('frontend/dist', 'frontend/dist'),
    ],
    hiddenimports=[
        'war3_metadata', 'war3_contracts', 'war3_view_contract', 'war3_ui_services',
        'war3_tk_view', 'war3_gui', 'war3_application', 'war3_backend', 'war3_cli', 'war3_app',
        'war3_webview_viewport', 'war3_desktop_bridge', 'war3_web_gui',
        'webview', 'webview.platforms.winforms', 'clr', 'pythonnet',
        'capstone',
        'war3_extension_definition_ui', 'war3_mpq', 'war3_object_tables',
        'war3_services.extension_definitions', 'war3_services.ability_bundle',
        'war3_batch_edit_ui',
        'war3_artifact_plan', 'war3_artifact_plan_ui', 'war3_services.artifact_plan',
        'war3_services.batch_edit',
        'war3_runtime_check',
        'war3_clone_protocol',
        'war3_engine_24268',
        'war3_engine_transport',
        'war3_remote_exports',
        'war3_engine_continuation',
        'war3_adapter_24332',
        'war3_speed_clock_backend',
        'war3_services.speed',
        'war3_loadout_restore',
        'war3_loadout_storage',
        'war3_equipment_effect_protocol',
        'war3_item_safety_protocol',
        'war3_error_messages',
        'war3_services.equipment_effects', 'war3_services.item_effect_fields',
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
        'war3_hero_skill_catalog',
        'war3_hero_skill_ui',
        'war3_gamecache_fields',
        'war3_archive_fields_ui',
        'war3_services.archive_fields',
        'war3_save_codes',
        'war3_save_extraction_ui',
        'war3_services.save_extraction',
        'war3_profile_resolver',
        'war3_discovery_fields',
        'war3_discovery_properties',
        'war3_discovery_abi',
        'war3_discovery_call_abi',
        'war3_discovery_stats', 'war3_discovery_native_recovery', 'war3_discovery_decoder_flow',
        'war3_discovery_components',
        'war3_discovery_ability_identity',
        'war3_3_stats',
        'war3_stat_details_protocol',
        'war3_integrity',
        'war3_talent_icon_display',
        'war3_talent_icon_control_protocol',
        'pefile',
    ] + sorted({spec.protocol for spec in OPERATIONS.values() if spec.protocol}),
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['PySide6', 'PyQt6', 'PySide2', 'PyQt5', 'cefpython3', 'qtpy', 'gi'],
    noarchive=False, optimize=0,
)

runtime_root = Path(os.environ['RELEASE_2115_RUNTIME_DIR'])
runtime_entries = [row for row in a.binaries if row[0].lower().startswith('api-ms-win-') or row[0].lower() == 'ucrtbase.dll']
if runtime_entries:
    pinned = sorted(runtime_root.glob('*.dll'))
    if not pinned or not (runtime_root / 'ucrtbase.dll').is_file():
        raise RuntimeError('Verified baseline CRT set is incomplete')
    a.binaries = [row for row in a.binaries if row not in runtime_entries]
    a.binaries.extend((p.name, str(p), 'BINARY') for p in pinned)

pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='War3ReforgedTrainer-v2.1.15-Web',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
    upx_exclude=[], runtime_tmpdir=None, console=False,
    disable_windowed_traceback=False, uac_admin=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
    icon='assets/app_icon.ico', version='tools/war3-2.1.15-version-info.txt',
)
