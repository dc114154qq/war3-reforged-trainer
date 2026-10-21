"""Command-line adapter over the public game backend."""
from __future__ import annotations
import argparse,sys
from pathlib import Path
from typing import Iterable
from war3_backend import *
from war3_contracts import *
def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Warcraft III Reforged trainer")
    parser.add_argument("--extract-archive-fields", metavar="W3V_OR_W3Z", help="Read official campaign cache fields without modifying the file")
    parser.add_argument("--archive-fields-output", metavar="JSON_OR_CSV", help="Export campaign fields to a new file")
    parser.add_argument("--extract-save-codes", metavar="FILE_OR_DIRECTORY", help="Extract RPG save-code candidates without connecting to a game")
    parser.add_argument("--save-code-prefix", default="-load", help="Map load command, for example --save-code-prefix=-load")
    parser.add_argument("--save-code-output", metavar="TXT_OR_JSON", help="Export extracted codes to a new file")
    parser.add_argument("--pid", type=int, help="Warcraft III.exe PID")
    parser.add_argument("--status", action="store_true", help="Print process/resource status")
    parser.add_argument("--list-resources", action="store_true", help="Print all detected player/resource groups")
    parser.add_argument("--focus", action="store_true", help="Bring Warcraft III to foreground")
    parser.add_argument("--send-cheat", help="Send a raw Warcraft III cheat command")
    parser.add_argument("--add-gold", type=int)
    parser.add_argument("--add-lumber", type=int)
    parser.add_argument("--add-both", type=int, help="greedisgood delta")
    parser.add_argument("--set-gold", type=int)
    parser.add_argument("--set-lumber", type=int)
    parser.add_argument("--current-gold", type=int, help="Fallback current gold for cache calibration")
    parser.add_argument("--current-lumber", type=int, help="Fallback current lumber for cache calibration")
    parser.add_argument("--current-food", type=int, help="Fallback current food used for resource calibration")
    parser.add_argument("--current-food-cap", type=int, help="Fallback current food cap for resource calibration")
    parser.add_argument("--set-food-used", type=int)
    parser.add_argument("--set-food-cap", type=int)
    parser.add_argument("--current-hp", type=float)
    parser.add_argument("--current-mp", type=float)
    parser.add_argument("--current-hp-max", type=float)
    parser.add_argument("--current-mp-max", type=float)
    parser.add_argument("--set-hp", type=float)
    parser.add_argument("--set-mp", type=float)
    parser.add_argument("--set-hp-regen", type=float)
    parser.add_argument("--set-mp-regen", type=float)
    parser.add_argument("--set-x", type=float)
    parser.add_argument("--set-y", type=float)
    parser.add_argument("--read-selected", action="store_true", help="Read current selected unit through the selection handle")
    parser.add_argument("--read-selected-fields", action="store_true", help="Read all supported fields from the current selected unit")
    parser.add_argument("--engine-camera-probe", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--enable-hotkeys", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--list-selection-candidates", action="store_true", help="List plausible selected-unit candidates with full clues")
    parser.add_argument("--unit-identity", help="Manual candidate identity: HANDLE,OWNER,UNIT or handle=...,owner=...,unit=...")
    parser.add_argument("--verify-selection-locator", action="store_true", help="Verify selected-unit locator uses handle -> owner -> unit chain")
    parser.add_argument("--native-selection-probe", action="store_true", help="Locate selected unit through native-disassembled selection manager")
    parser.add_argument("--jass-selection-probe", action="store_true", help="Experiment: call JASS selection natives and print raw/mapped result")
    parser.add_argument("--jass-locate-selected", action="store_true", help="Experiment: locate current selected unit through JASS selection natives")
    parser.add_argument("--set-unit-field", action="append", default=[], metavar="KEY=VALUE", help="Write a supported selected-unit field by key")
    parser.add_argument("--set-xp", type=int)
    parser.add_argument("--set-skill-points", type=int)
    parser.add_argument("--set-base-str", type=int)
    parser.add_argument("--set-base-agi", type=int)
    parser.add_argument("--set-int", type=float)
    parser.add_argument("--set-intelligence", type=float)
    parser.add_argument("--set-add-str", type=float)
    parser.add_argument("--set-add-int", type=float)
    parser.add_argument("--set-add-agi", type=float)
    parser.add_argument("--set-move-speed", type=float)
    parser.add_argument("--set-defense", type=float)
    parser.add_argument("--set-armor", type=float)
    parser.add_argument("--set-armor-type", type=int)
    parser.add_argument("--set-attack-type", type=int)
    parser.add_argument("--set-attack-speed", type=float)
    parser.add_argument("--set-attack-damage-level", type=int)
    parser.add_argument("--set-attack-damage-item", type=int)
    parser.add_argument("--gui", action="store_true", help="Launch GUI even when CLI flags are present")
    parser.add_argument('--import-game-profile', metavar='JSON', help='手动导入经过校验的离线游戏适配包，然后退出')
    parser.add_argument('--inspect-game-profile', metavar='JSON', help='校验并显示离线适配包信息，然后退出')
    return parser


def run_cli(args: argparse.Namespace) -> int:
    t = War3Trainer(args.pid)
    manual_identity = parse_unit_identity(args.unit_identity) if args.unit_identity else None
    print(f"Warcraft III PID={t.pid} HWND=0x{t.hwnd:x}")
    if args.focus:
        t.focus()
        print("focused Warcraft III")
    if args.status:
        try:
            cache = t.read_resource_cache(
                args.current_gold,
                args.current_lumber,
                args.current_food,
                args.current_food_cap,
            )
            food_text = ""
            if cache.source == "persistent native player state" or cache.food_used_address or cache.food_cap_address:
                food_text = (
                    f" food={cache.food_used}/{cache.food_cap}"
                    f" food_used_addr=0x{cache.food_used_address:x}"
                    f" food_cap_addr=0x{cache.food_cap_address:x}"
                )
            print(
                f"resources gold={cache.gold} lumber={cache.lumber}{food_text} "
                f"gold_addr=0x{cache.gold_address:x} lumber_addr=0x{cache.lumber_address:x} "
                f"source={cache.source}"
            )
        except Exception as exc:
            print(f"resources unavailable: {exc}")
    if args.list_resources:
        try:
            caches = t.list_resource_caches(
                args.current_gold,
                args.current_lumber,
                args.current_food,
                args.current_food_cap,
            )
            if not caches:
                print("resource_groups count=0")
            for index, cache in enumerate(caches, 1):
                food_text = ""
                if cache.source == "persistent native player state" or cache.food_used_address or cache.food_cap_address:
                    food_text = (
                        f" food={cache.food_used}/{cache.food_cap}"
                        f" food_used_addr=0x{cache.food_used_address:x}"
                        f" food_cap_addr=0x{cache.food_cap_address:x}"
                    )
                print(
                    f"resource_group index={index} gold={cache.gold} lumber={cache.lumber}{food_text} "
                    f"gold_addr=0x{cache.gold_address:x} lumber_addr=0x{cache.lumber_address:x} "
                    f"owner=0x{cache.owner_key:x} start_kind=0x{cache.block_start_kind:x} "
                    f"header={cache.header_value} player={cache.player_value} score={cache.score}"
                )
        except Exception as exc:
            print(f"resource_groups unavailable: {exc}")
    if args.send_cheat:
        t.send_cheat(args.send_cheat)
        print(f"sent cheat: {args.send_cheat}")
    if args.add_gold is not None:
        t.add_gold(args.add_gold)
        print(f"gold delta sent: {args.add_gold:+d}")
    if args.add_lumber is not None:
        t.add_lumber(args.add_lumber)
        print(f"lumber delta sent: {args.add_lumber:+d}")
    if args.add_both is not None:
        t.add_gold_and_lumber(args.add_both)
        print(f"gold/lumber delta sent: {args.add_both:+d}")
    if args.set_gold is not None:
        delta = t.set_gold(args.set_gold, args.current_gold, args.current_lumber)
        print(f"gold set delta={delta:+d}")
    if args.set_lumber is not None:
        delta = t.set_lumber(args.set_lumber, args.current_gold, args.current_lumber)
        print(f"lumber set delta={delta:+d}")
    if args.set_food_used is not None or args.set_food_cap is not None:
        cache = t.set_food(
            args.set_food_used,
            args.set_food_cap,
            args.current_gold,
            args.current_lumber,
            args.current_food,
            args.current_food_cap,
        )
        print(
            f"food written food={cache.food_used}/{cache.food_cap} "
            f"food_used_addr=0x{cache.food_used_address:x} food_cap_addr=0x{cache.food_cap_address:x} "
            f"source={cache.source}"
        )
    if args.read_selected:
        if manual_identity is not None:
            panel, cand, _fields = t.read_unit_fields_by_identity(*manual_identity)
        else:
            panel, cand = t.locate_current_selected_unit()
        pos_text = ""
        with ProcessMemory(t.pid) as pm:
            pos = t._position_from_candidate(pm, cand)
            regen_text = ""
            native = t._native_snapshot_for_candidate(cand)
            if native is not None:
                for key in ("hp_regen", "mp_regen"):
                    value = getattr(native, key)
                    if value is not None:
                        regen_text += f" {key}={value:.6g}"
            else:
                if cand.hp_regen_address:
                    regen_text += f" hp_regen={pm.read_f32(cand.hp_regen_address):.6g}"
                if cand.mp_regen_address:
                    regen_text += f" mp_regen={pm.read_f32(cand.mp_regen_address):.6g}"
        if pos is not None:
            pos_text = f" x={pos[0]:.3f} y={pos[1]:.3f}"
        print(
            f"selected memory hp={panel.hp_text} mp={panel.mp_text} "
            f"base=0x{cand.base:x} unit=0x{cand.unit_address:x} hp_cur=0x{cand.hp_current_address:x} "
            f"hp_max=0x{cand.hp_max_address:x} hp_regen_addr=0x{cand.hp_regen_address:x} "
            f"mp_cur=0x{cand.mp_current_address:x} mp_max=0x{cand.mp_max_address:x} "
            f"mp_regen_addr=0x{cand.mp_regen_address:x}{regen_text}{pos_text} "
            f"source={cand.selection_source or 'unknown'} note={cand.note}"
        )
    if args.read_selected_fields:
        if manual_identity is not None:
            panel, cand, fields = t.read_unit_fields_by_identity(*manual_identity)
        else:
            panel, cand, fields = t.read_selected_unit_fields()
        print(
            f"selected fields hp={panel.hp_text} mp={panel.mp_text} "
            f"owner=0x{cand.owner_address:x} handle=0x{cand.handle:x} "
            f"unit=0x{cand.unit_address:x} source={cand.selection_source or 'unknown'} note={cand.note}"
        )
        for field in fields:
            writable = "rw" if field.writable else "ro"
            note = f" note={field.note}" if field.note else ""
            print(
                f"{field.key} [{field.category}] {field.label}={field.value_text()} "
                f"type={field.value_type} addr=0x{field.address:x} {writable}{note}"
            )
    if args.engine_camera_probe:
        result = t.camera_snapshot_24268()
        print(
            "current_engine_camera "
            f"target={result.get('target')} eye={result.get('eye')} "
            f"screen={result.get('screen')} fields={result.get('fields')}"
        )
    if args.list_selection_candidates:
        summaries = t.list_selection_candidates(
            extra_identities=[manual_identity] if manual_identity is not None else None
        )
        print(f"selection_candidates count={len(summaries)}")
        for index, summary in enumerate(summaries, 1):
            print(t.selection_candidate_line(summary, index))
    if args.verify_selection_locator:
        with ProcessMemory(t.pid) as pm:
            cand = t.locate_selected_unit_by_handle(pm, allow_deep_scan=True)
            layout = t._game_session.profile.section("registry")
            owner_handle = pm.read_u64(cand.owner_address + layout["owner_handle"]) if cand.owner_address else 0
            unit_handle = pm.read_u64(cand.unit_address + layout["object_handle"]) if cand.unit_address else 0
            status = (
                cand.handle != 0
                and owner_handle == cand.handle
                and unit_handle == cand.handle
                and cand.owner_address != 0
                and cand.unit_address != 0
                and cand.selection_source == "memory"
                and (cand.note.startswith("selected_handle=") or cand.note.startswith("selected_unit_slot="))
            )
        print(
            f"selection_locator={'OK' if status else 'FAILED'} "
            f"mode={cand.selection_source or 'unknown'} handle=0x{cand.handle:x} "
            f"owner=0x{cand.owner_address:x} owner_handle=0x{owner_handle:x} "
            f"unit=0x{cand.unit_address:x} unit_handle=0x{unit_handle:x} "
            f"slot=0x{cand.selection_slot_address:x} "
            f"slot_note={cand.note}"
        )
        if not status:
            raise RuntimeError("选中单位定位链验证失败")
    if args.native_selection_probe:
        probe = t.probe_native_selection_manager()
        mapped = "yes" if probe.candidate is not None else "no"
        detail = ""
        if probe.candidate is not None:
            detail = (
                f" handle=0x{probe.candidate.handle:x}"
                f" owner=0x{probe.candidate.owner_address:x}"
                f" unit=0x{probe.candidate.unit_address:x}"
                f" note={probe.candidate.note}"
            )
        print(
            f"native_selection offset=0x{probe.selection_manager_offset:x}"
            f" list=0x{probe.primary_list_offset:x}/0x{probe.alternate_list_offset:x}"
            f" is_unit_selected=0x{probe.is_unit_selected_handler:x}"
            f" group_enum=0x{probe.group_enum_selected_handler:x}"
            f" mapped={mapped}{detail}"
        )
    if args.jass_selection_probe:
        probe = t.probe_jass_selected_unit()
        mapped = "yes" if probe.candidate is not None else "no"
        detail = ""
        if probe.candidate is not None:
            detail = (
                f" handle=0x{probe.candidate.handle:x} owner=0x{probe.candidate.owner_address:x}"
                f" unit=0x{probe.candidate.unit_address:x} note={probe.candidate.note}"
            )
        print(
            f"jass_selection unit=0x{probe.unit_handle:x} handle_id=0x{probe.handle_id:x} "
            f"player=0x{probe.player_handle:x} mapped={mapped}{detail}"
        )
    if args.jass_locate_selected:
        cand = t.locate_selected_unit_by_jass_native()
        with ProcessMemory(t.pid) as pm:
            panel = t._panel_from_candidate(pm, cand)
            pos = t._position_from_candidate(pm, cand)
        pos_text = f" x={pos[0]:.3f} y={pos[1]:.3f}" if pos is not None else ""
        print(
            f"jass_selected hp={panel.hp_text} mp={panel.mp_text}{pos_text} "
            f"handle=0x{cand.handle:x} owner=0x{cand.owner_address:x} unit=0x{cand.unit_address:x} "
            f"note={cand.note}"
        )
    if (
        args.set_hp is not None
        or args.set_mp is not None
        or args.set_hp_regen is not None
        or args.set_mp_regen is not None
        or args.set_x is not None
        or args.set_y is not None
    ):
        if manual_identity is not None:
            panel, _cand, _fields = t.read_unit_fields_by_identity(*manual_identity)
            cand = t.set_unit_by_identity(
                *manual_identity,
                args.current_hp if args.current_hp is not None else panel.current_hp,
                args.current_mp if args.current_mp is not None else panel.current_mp,
                args.set_hp,
                args.set_mp,
                args.current_hp_max if args.current_hp_max is not None else panel.max_hp,
                args.current_mp_max if args.current_mp_max is not None else panel.max_mp,
                args.set_x,
                args.set_y,
                args.set_hp_regen,
                args.set_mp_regen,
            )
        elif args.current_hp is None:
            panel, cand = t.locate_current_selected_unit()
            cand = t.set_selected_unit(
                panel.current_hp,
                panel.current_mp,
                args.set_hp,
                args.set_mp,
                panel.max_hp,
                panel.max_mp,
                args.set_x,
                args.set_y,
                args.set_hp_regen,
                args.set_mp_regen,
            )
        else:
            cand = t.set_selected_unit(
                args.current_hp,
                args.current_mp,
                args.set_hp,
                args.set_mp,
                args.current_hp_max,
                args.current_mp_max,
                args.set_x,
                args.set_y,
                args.set_hp_regen,
                args.set_mp_regen,
            )
        pos_text = ""
        with ProcessMemory(t.pid) as pm:
            pos = t._position_from_candidate(pm, cand)
            regen_text = ""
            native = t._native_snapshot_for_candidate(cand)
            if native is not None:
                for key in ("hp_regen", "mp_regen"):
                    value = getattr(native, key)
                    if value is not None:
                        regen_text += f" {key}={value:.6g}"
            else:
                if cand.hp_regen_address:
                    regen_text += f" hp_regen={pm.read_f32(cand.hp_regen_address):.6g}"
                if cand.mp_regen_address:
                    regen_text += f" mp_regen={pm.read_f32(cand.mp_regen_address):.6g}"
        if pos is not None:
            pos_text = f" x={pos[0]:.3f} y={pos[1]:.3f}"
        print(
            "selected unit written "
            f"base=0x{cand.base:x} unit=0x{cand.unit_address:x} hp_cur=0x{cand.hp_current_address:x} "
            f"hp_max=0x{cand.hp_max_address:x} hp_regen_addr=0x{cand.hp_regen_address:x} "
            f"mp_cur=0x{cand.mp_current_address:x} mp_max=0x{cand.mp_max_address:x} "
            f"mp_regen_addr=0x{cand.mp_regen_address:x}{regen_text}{pos_text} "
            f"source={cand.selection_source or 'unknown'} note={cand.note}"
        )
    unit_specs: list[MemoryWriteSpec] = []
    for arg_name, field_key in t.CLI_UNIT_FIELD_KEYS.items():
        value = getattr(args, f"set_{arg_name}")
        if value is not None:
            unit_specs.append(MemoryWriteSpec(field_key, 0, "", value))
    for assignment in args.set_unit_field:
        if "=" not in assignment:
            raise ValueError("--set-unit-field 格式应为 KEY=VALUE")
        key, value = assignment.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError("--set-unit-field 缺少字段名")
        unit_specs.append(MemoryWriteSpec(key, 0, "", value))
    if unit_specs:
        if manual_identity is not None:
            written = [
                t.write_unit_field_by_identity(*manual_identity, spec.label, spec.value)
                for spec in unit_specs
            ]
        else:
            written = t.write_selected_unit_fields(unit_specs)
        for field in written:
            note = f" note={field.note}" if field.note else ""
            print(
                f"unit field written {field.key} {field.label}={field.value_text()} "
                f"type={field.value_type} addr=0x{field.address:x}{note}"
            )
    return 0


def main(argv: Iterable[str] | None=None, *, launch_gui=None) -> int:
    arguments = list(argv) if argv is not None else sys.argv[1:]
    parser = build_arg_parser()
    args = parser.parse_args(arguments)
    if args.extract_archive_fields:
        import json
        from war3_services.archive_fields import read_archive_file, export_archive_result
        try:
            report = read_archive_file(args.extract_archive_fields)
            if args.archive_fields_output:
                export_archive_result(args.archive_fields_output, report)
            print(json.dumps(report, ensure_ascii=False, allow_nan=False))
            return 0 if report.get('complete') else 1
        except Exception as exc:
            from war3_services.save_extraction import log_extraction_failure
            from war3_error_messages import format_error
            try:
                log_extraction_failure(exc)
            except OSError as log_error:
                exc.log_write_error = repr(log_error)
            print(format_error(exc), file=sys.stderr)
            return 1
    if args.extract_save_codes:
        import json
        from war3_services.save_extraction import read_code_file, scan_code_directory, export_codes
        source = Path(args.extract_save_codes)
        try:
            if source.is_dir():
                report = scan_code_directory(source, args.save_code_prefix)
            else:
                report = {'codes': read_code_file(source, args.save_code_prefix), 'complete': True}
            if args.save_code_output:
                export_codes(args.save_code_output, report['codes'])
            print(json.dumps({**report, 'codes': [row.to_dict() for row in report['codes']]}, ensure_ascii=False))
            return 0 if report.get('complete') else 1
        except Exception as exc:
            from war3_services.save_extraction import log_extraction_failure
            from war3_error_messages import format_error
            try:
                log_extraction_failure(exc)
            except OSError as log_error:
                exc.log_write_error = repr(log_error)
            print(format_error(exc), file=sys.stderr)
            return 1
    if args.import_game_profile or args.inspect_game_profile:
        import json
        from war3_game_profile import import_profile, load_profile, installed_profile_directory
        if args.import_game_profile:
            target = import_profile(args.import_game_profile, installed_profile_directory())
            print('适配包已导入，下次连接游戏时重新识别：' + str(target))
        else:
            profile = load_profile(args.inspect_game_profile)
            print(json.dumps({'id': profile.id, 'fingerprint': profile.fingerprint, 'digest': profile.digest, 'status': profile.data['status']}, ensure_ascii=False))
        return 0
    has_cli_action = any([args.status, args.list_resources, args.focus, args.send_cheat, args.add_gold is not None, args.add_lumber is not None, args.add_both is not None, args.set_gold is not None, args.set_lumber is not None, args.set_food_used is not None, args.set_food_cap is not None, args.read_selected, args.read_selected_fields, args.engine_camera_probe, args.list_selection_candidates, bool(args.unit_identity), args.verify_selection_locator, args.native_selection_probe, args.jass_selection_probe, args.jass_locate_selected, args.set_hp is not None, args.set_mp is not None, args.set_hp_regen is not None, args.set_mp_regen is not None, args.set_x is not None, args.set_y is not None, bool(args.set_unit_field), args.set_xp is not None, args.set_skill_points is not None, args.set_base_str is not None, args.set_base_agi is not None, args.set_int is not None, args.set_intelligence is not None, args.set_add_str is not None, args.set_add_int is not None, args.set_add_agi is not None, args.set_move_speed is not None, args.set_defense is not None, args.set_armor is not None, args.set_armor_type is not None, args.set_attack_type is not None, args.set_attack_speed is not None, args.set_attack_damage_level is not None, args.set_attack_damage_item is not None])
    if args.gui or not has_cli_action:
        launch_gui(args.pid, args.enable_hotkeys)
        return 0
    return run_cli(args)
