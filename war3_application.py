"""Application commands and presenters. UI toolkit access is through ViewPort."""
from __future__ import annotations
from typing import Callable,Iterable
from pathlib import Path
from dataclasses import replace
import sys,threading,time
from war3_view_contract import ViewPort,ViewControl
from war3_backend import (War3Trainer,Win10ReadLogger,ResourceCache,UnitMemoryField,
    UnitSelectionSummary,AbilityFieldSnapshot,AbilityFieldValue,ItemFieldSnapshot,ItemFieldValue,
    GlobalHotkeyManager,ELEPHANT_HOTKEY_SPECS,record_operation_failure,resolve_requested_war3_pid,
    call_with_read_success_sound,format_rawcode,parse_int,parse_float,parse_changed_coordinate,
    selection_confidence_text)
from war3_metadata import APP_VERSION,PRODUCT_READ_MODE,PRODUCT_EDITION_LABEL
from war3_3_extension_catalog import EQUIPMENT_SLOT_NAMES,EQUIPMENT_TYPE_NAMES,OFFICIAL_BACKPACKS
from war3_3_stats import STAT_DETAIL_SPECS
from war3_id_catalog import CATALOG_COUNTS,search_id_entries

class TrainerApplication:
    required_ports = frozenset((
        'ability_field_detail', 'ability_field_filter', 'ability_field_level',
        'ability_field_rawcode', 'ability_field_show_unsupported', 'ability_field_show_zero',
        'ability_field_summary', 'ability_field_tree', 'ability_field_value',
        'ability_field_write_button', 'artifact_plan_panel', 'artifact_plan_settings',
        'candidate_tree', 'discovery_cancel_button', 'elephant_ability_level',
        'elephant_ability_rawcode', 'elephant_auto_effect_count', 'elephant_game_speed',
        'elephant_hero_attributes', 'elephant_hero_level', 'elephant_hotkey_checks',
        'elephant_hotkey_status', 'elephant_hotkeys_enabled', 'elephant_item_charges',
        'elephant_item_rawcode', 'elephant_mass_clone_count', 'elephant_preset_item_rawcode',
        'elephant_preset_tech_rawcode', 'elephant_reinforcement_rawcode',
        'elephant_reset_ability_rawcode', 'elephant_resource_amount', 'elephant_skill_points',
        'elephant_stat_values', 'elephant_tech_level', 'elephant_tech_rawcode',
        'elephant_unit_rawcode', 'elephant_unit_scale', 'elephant_xp_rate',
        'extension_backpack_choice', 'extension_bag_tree', 'extension_equipment_tree',
        'extension_item_charges', 'extension_item_rawcode', 'extension_loadout_box',
        'extension_loadout_choice', 'extension_loadout_name', 'extension_status',
        'extension_talent_choice', 'extension_talent_choice_box', 'extension_talent_tree',
        'filedialog', 'food_cap_current', 'food_cap_target', 'food_current', 'food_used_target',
        'gold_current', 'gold_target', 'hotkey_callbacks', 'hotkey_canvas', 'hotkey_manager',
        'hotkey_specs_by_name', 'hotkey_window', 'hp_current', 'hp_max_current', 'hp_regen_current',
        'hp_regen_target', 'hp_target', 'id_catalog_queries', 'id_catalog_statuses',
        'id_catalog_trees', 'item_field_detail', 'item_field_filter', 'item_field_show_unsupported',
        'item_field_show_zero', 'item_field_slot', 'item_field_summary', 'item_field_tree',
        'item_field_value', 'item_field_write_button', 'lock_tree', 'lumber_current',
        'lumber_target', 'messagebox', 'mp_current', 'mp_max_current', 'mp_regen_current',
        'mp_regen_target', 'mp_target', 'official_backpack_by_label', 'operation_lock',
        'operation_threads', 'operation_threads_lock', 'pid_var', 'resource_delta', 'resource_tree',
        'root', 'state', 'status', 'ui_language', 'ui_text', 'unit_field_target', 'unit_field_tree',
        'unit_type_id_current', 'x_current', 'x_target', 'y_current', 'y_target'
    ))
    def __init__(self,view: ViewPort):
        self.view=view

    def start_operation_thread(self, target: Callable[[], None], name: str) -> None:

        def tracked_target() -> None:
            try:
                target()
            finally:
                with self.view.value('operation_threads_lock'):
                    self.view.value('operation_threads').discard(threading.current_thread())
        thread = threading.Thread(target=tracked_target, name=name, daemon=False)
        with self.view.value('operation_threads_lock'):
            self.view.value('operation_threads').add(thread)
        try:
            thread.start()
        except Exception:
            with self.view.value('operation_threads_lock'):
                self.view.value('operation_threads').discard(thread)
            raise

    def active_operation_threads(self) -> tuple[threading.Thread, ...]:
        with self.view.value('operation_threads_lock'):
            return tuple((thread for thread in self.view.value('operation_threads') if thread.is_alive()))

    def close_gui(self) -> None:
        if self.view.value('state').get('closing'):
            return
        self.view.value('state')['closing'] = True
        for key in ('trainer', 'elephant_batch_trainer'):
            pending_session = getattr(self.view.value('state').get(key), '_game_session', None)
            if pending_session is not None and hasattr(pending_session, 'discovery_cancel'):
                pending_session.discovery_cancel.set()
        self.view.value('hotkey_manager').stop()
        self.set_status('正在等待后台操作安全结束...')

        def finish_close() -> None:
            if self.active_operation_threads() or self.view.value('state').get('lock_busy') or self.view.value('state').get('ally_health_lock_busy') or self.view.value('state').get('rapid_build_busy'):
                self.view.value('root').after(100, finish_close)
                return
            for key in ('trainer', 'elephant_batch_trainer'):
                value = self.view.value('state').get(key)
                if isinstance(value, War3Trainer):
                    value.close()
            for value in tuple(self.view.value('state').get('selection_source_trainers', ())):
                if isinstance(value, War3Trainer):
                    value.close()
            self.view.value('root').destroy()
        finish_close()

    def set_status(self, text: str) -> None:
        self.view.value('status').set(text)

    def configure_discovery(self, obj) -> None:
        session = obj._game_session
        if hasattr(session, 'discovery_cancel'):
            return
        session.discovery_cancel = threading.Event()

        def progress(stage, fraction):

            def show():
                if self.view.value('state').get('closing'):
                    return
                self.set_status(stage + (f' {fraction:.0%}' if fraction is not None else ''))
                self.view.value('discovery_cancel_button').state(['disabled'] if fraction == 1 else ['!disabled'])
            self.view.value('root').after(0, show)
        session.discovery_progress = progress

    def cancel_discovery(self) -> None:
        for key in ('trainer', 'elephant_batch_trainer'):
            session = getattr(self.view.value('state').get(key), '_game_session', None)
            if session is not None and hasattr(session, 'discovery_cancel'):
                session.discovery_cancel.set()
        self.view.value('discovery_cancel_button').state(['disabled'])
        self.set_status('已请求取消自动定位，可重新连接后重试。')

    def call_async(self, fn: Callable[[], str | None], operation_key: str='', busy_widget: ViewControl | None=None, busy_text: str='正在执行，请稍候...') -> None:
        if self.view.value('state').get('closing'):
            return
        active_operations = self.view.value('state').get('active_operations')
        assert isinstance(active_operations, set)
        if operation_key and operation_key in active_operations:
            return
        if operation_key:
            active_operations.add(operation_key)
        if busy_widget is not None:
            busy_widget.state(['disabled'])
        self.set_status(busy_text)
        requested_pid_text = self.view.value('pid_var').get().strip()
        try:
            requested_pid = int(requested_pid_text) if requested_pid_text else None
        except ValueError:
            requested_pid = None

        def finish(result: str | None, exc: Exception | None) -> None:
            if operation_key:
                active_operations.discard(operation_key)
            if self.view.value('state').get('closing'):
                return
            self.view.value('discovery_cancel_button').state(['disabled'])
            if busy_widget is not None:
                busy_widget.state(['!disabled'])
            if exc is not None:
                from war3_error_messages import format_error, describe_error
                details = format_error(exc, self.view.value('ui_language')['code'])
                self.view.value('messagebox').showerror(self.view.value('ui_text')('错误'), details)
                self.set_status(describe_error(exc, self.view.value('ui_language')['code'])['reason'])
            elif result:
                self.set_status(result)
            else:
                self.set_status('已完成')

        def worker() -> None:
            try:
                with self.view.value('operation_lock'):
                    result = fn()
            except Exception as exc:
                try:
                    current_trainer = self.view.value('state').get('trainer')
                    path = record_operation_failure(getattr(current_trainer, 'pid', None), operation_key or getattr(fn, '__name__', 'operation'), exc, requested_pid=requested_pid, target_hwnd=getattr(current_trainer, 'hwnd', 0))
                    exc.diagnostic_log_path = path
                except Exception as log_error:
                    exc.log_write_error = repr(log_error)
                self.view.value('root').after(0, finish, None, exc)
            else:
                self.view.value('root').after(0, finish, result, None)
        thread_name = f'war3-operation-{operation_key or 'anonymous'}'
        self.start_operation_thread(worker, thread_name)

    def trainer(self) -> War3Trainer:
        obj = self.view.value('state').get('trainer')
        if obj is None:
            obj = War3Trainer(pid=int(self.view.value('pid_var').get()) if self.view.value('pid_var').get().strip() else None)
            self.view.value('state')['trainer'] = obj
        else:
            assert isinstance(obj, War3Trainer)
            obj.refresh_window(allow_pid_change=True)
        self.view.value('root').after(0, self.view.value('pid_var').set, str(obj.pid))
        self.configure_discovery(obj)
        return obj

    def connect(self) -> str:
        requested_pid = int(self.view.value('pid_var').get()) if self.view.value('pid_var').get().strip() else None
        replacement = War3Trainer(pid=resolve_requested_war3_pid(requested_pid))
        self.configure_discovery(replacement)
        previous = self.view.value('state').get('trainer')
        batch_trainer = self.view.value('state').get('elephant_batch_trainer')
        if isinstance(previous, War3Trainer):
            previous.close()
        if isinstance(batch_trainer, War3Trainer) and batch_trainer is not previous:
            batch_trainer.close()
        self.view.value('state')['elephant_batch_trainer'] = None
        self.view.value('state')['trainer'] = replacement
        self.view.value('root').after(0, self.view.value('pid_var').set, str(self.view.value('state')['trainer'].pid))
        return f'已连接 Warcraft III，PID {self.view.value('state')['trainer'].pid}'

    def resource_iid(self, cache: ResourceCache) -> str:
        if cache.source == 'persistent native player state':
            return f'native-player:{cache.player_value}'
        return f'{cache.gold_address:x}:{cache.lumber_address:x}'

    def resource_row_values(self, index: int, cache: ResourceCache) -> tuple[str, str, str, str, str, str, str]:
        native = cache.source == 'persistent native player state'
        food_text = f'{cache.food_used}/{cache.food_cap}' if native or cache.food_used_address or cache.food_cap_address else ''
        player_text = f'{index}'
        if cache.player_value or cache.header_value:
            player_text = f'{index} (h{cache.header_value}/p{cache.player_value})'
        if native:
            player_text = f'{index} (Player {cache.player_value})'
        return (player_text, str(cache.gold), str(cache.lumber), food_text, '—' if native else f'0x{cache.gold_address:x}', '—' if native else f'0x{cache.lumber_address:x}', cache.source)

    def set_resource_entries(self, cache: ResourceCache, reset_targets: bool=True) -> None:
        native = cache.source == 'persistent native player state'
        self.view.value('gold_current').set(str(cache.gold))
        self.view.value('lumber_current').set(str(cache.lumber))
        self.view.value('food_current').set(str(cache.food_used) if native or cache.food_used_address else '')
        self.view.value('food_cap_current').set(str(cache.food_cap) if native or cache.food_cap_address else '')
        if reset_targets:
            self.view.value('gold_target').set(str(cache.gold))
            self.view.value('lumber_target').set(str(cache.lumber))
            self.view.value('food_used_target').set(str(cache.food_used) if native or cache.food_used_address else '')
            self.view.value('food_cap_target').set(str(cache.food_cap) if native or cache.food_cap_address else '')

    def populate_resource_caches(self, caches: list[ResourceCache], preferred_iid: str='', local_iid: str='') -> None:
        cache_map: dict[str, ResourceCache] = {}
        label_map: dict[str, str] = {}
        self.view.value('resource_tree').delete(*self.view.value('resource_tree').get_children())
        selected_iid = ''
        for index, cache in enumerate(caches, 1):
            iid = self.resource_iid(cache)
            cache_map[iid] = cache
            label_map[iid] = str(index)
            self.view.value('resource_tree').insert('', 'end', iid=iid, values=self.resource_row_values(index, cache))
            if iid == preferred_iid:
                selected_iid = iid
        if not selected_iid and caches:
            selected_iid = self.resource_iid(caches[0])
        self.view.value('state')['resource_caches'] = cache_map
        self.view.value('state')['resource_labels'] = label_map
        self.view.value('state')['selected_resource_iid'] = selected_iid
        self.view.value('state')['local_resource_iid'] = local_iid
        if selected_iid:
            self.view.value('resource_tree').selection_set(selected_iid)
            self.view.value('resource_tree').focus(selected_iid)
            self.set_resource_entries(cache_map[selected_iid])

    def update_resource_cache_display(self, cache: ResourceCache) -> None:
        iid = self.resource_iid(cache)
        caches = self.view.value('state').get('resource_caches', {})
        labels = self.view.value('state').get('resource_labels', {})
        if not isinstance(caches, dict) or not isinstance(labels, dict):
            return
        caches[iid] = cache
        label = str(labels.get(iid, ''))
        index = int(label) if label.isdigit() else len(caches)
        if self.view.value('resource_tree').exists(iid):
            self.view.value('resource_tree').item(iid, values=self.resource_row_values(index, cache))
        self.view.value('state')['selected_resource_iid'] = iid
        self.set_resource_entries(cache)

    def on_resource_select(self, _event=None) -> None:
        selection = self.view.value('resource_tree').selection()
        if not selection:
            return
        iid = str(selection[0])
        caches = self.view.value('state').get('resource_caches', {})
        if not isinstance(caches, dict):
            return
        cache = caches.get(iid)
        if not isinstance(cache, ResourceCache):
            return
        self.view.value('state')['selected_resource_iid'] = iid
        self.set_resource_entries(cache)

    def selected_resource_cache(self) -> ResourceCache:
        caches = self.view.value('state').get('resource_caches', {})
        if not isinstance(caches, dict) or not caches:
            raise ValueError('请先点击“读取全部资源组”，并在表格里选择一个阵营/资源组')
        iid = str(self.view.value('state').get('selected_resource_iid', ''))
        cache = caches.get(iid)
        if not isinstance(cache, ResourceCache):
            raise ValueError('请先在资源组表格里选择要修改的阵营/资源组')
        return cache

    def selected_resource_label(self, cache: ResourceCache) -> str:
        labels = self.view.value('state').get('resource_labels', {})
        iid = self.resource_iid(cache)
        if isinstance(labels, dict) and iid in labels:
            return str(labels[iid])
        return f'0x{cache.gold_address:x}'

    def refresh_resources(self) -> str:
        t = self.trainer()
        caches = t.list_resource_caches()
        if not caches:
            raise RuntimeError('No native player resource groups returned')
        local_cache = t.locate_local_player_resource_cache(caches)
        local_iid = self.resource_iid(local_cache)
        if not any((self.resource_iid(cache) == local_iid for cache in caches)):
            raise RuntimeError('Local player is missing from native resource groups; refresh again')
        self.view.value('root').after(0, self.populate_resource_caches, caches, local_iid, local_iid)
        return f'已读取 {len(caches)} 个资源组；已识别并选中本地玩家资源组（native）'

    def set_resource(self, kind: str) -> str:
        t = self.trainer()
        cache = self.selected_resource_cache()
        label = self.selected_resource_label(cache)
        current = t.read_resource_cache_addresses(cache)
        if kind == 'gold':
            target = parse_int(self.view.value('gold_target').get(), '目标金币')
            refreshed = t.write_resource_cache(current, target_gold=target)
            self.view.value('root').after(0, self.update_resource_cache_display, refreshed)
            return f'资源组 {label} 金币已写入：{current.gold} -> {refreshed.gold}'
        target = parse_int(self.view.value('lumber_target').get(), '目标木材')
        refreshed = t.write_resource_cache(current, target_lumber=target)
        self.view.value('root').after(0, self.update_resource_cache_display, refreshed)
        return f'资源组 {label} 木材已写入：{current.lumber} -> {refreshed.lumber}'

    def set_food_resource(self, kind: str) -> str:
        t = self.trainer()
        cache = self.selected_resource_cache()
        label = self.selected_resource_label(cache)
        current = t.read_resource_cache_addresses(cache)
        is_local_player = self.resource_iid(cache) == str(self.view.value('state').get('local_resource_iid', ''))
        if kind == 'food_used':
            target = parse_int(self.view.value('food_used_target').get(), '目标当前人口')
            refreshed = t.write_resource_cache(current, target_food_used=target, sync_local_food_used=is_local_player)
            message = f'当前人口已写入：{current.food_used} -> {refreshed.food_used}'
        elif kind == 'food_cap':
            target = parse_int(self.view.value('food_cap_target').get(), '目标人口上限')
            refreshed = t.write_resource_cache(current, target_food_cap=target, sync_local_food_cap=is_local_player)
            message = f'人口上限已写入：{current.food_cap} -> {refreshed.food_cap}'
        else:
            raise ValueError(f'未知人口字段：{kind}')
        self.view.value('root').after(0, self.update_resource_cache_display, refreshed)
        return f'资源组 {label} {message}；{refreshed.source}'

    def add_resource(self, kind: str) -> str:
        t = self.trainer()
        cache = self.selected_resource_cache()
        label = self.selected_resource_label(cache)
        amount = parse_int(self.view.value('resource_delta').get(), '增量')
        current = t.read_resource_cache_addresses(cache)
        if kind == 'gold':
            refreshed = t.write_resource_cache(current, target_gold=current.gold + amount)
            self.view.value('root').after(0, self.update_resource_cache_display, refreshed)
            return f'资源组 {label} 金币已修改：{amount:+d} -> {refreshed.gold}'
        if kind == 'lumber':
            refreshed = t.write_resource_cache(current, target_lumber=current.lumber + amount)
            self.view.value('root').after(0, self.update_resource_cache_display, refreshed)
            return f'资源组 {label} 木材已修改：{amount:+d} -> {refreshed.lumber}'
        refreshed = t.write_resource_cache(current, target_gold=current.gold + amount, target_lumber=current.lumber + amount)
        self.view.value('root').after(0, self.update_resource_cache_display, refreshed)
        return f'资源组 {label} 金币/木材已修改：{amount:+d} -> {refreshed.gold}/{refreshed.lumber}'

    def populate_unit_fields(self, fields: list[UnitMemoryField]) -> None:
        self.view.value('state')['unit_fields'] = {field.key: field for field in fields}
        self.view.value('unit_field_tree').delete(*self.view.value('unit_field_tree').get_children())
        for field in fields:
            self.view.value('unit_field_tree').insert('', 'end', iid=field.key, values=(self.view.value('ui_text')(field.category), self.view.value('ui_text')(field.label), self.view.value('ui_text')(field.value_text()), self.view.value('ui_text')(field.value_type), f'0x{field.address:x}', self.view.value('ui_text')(field.note)))

    def unit_identity(self, candidate: UnitCandidate) -> tuple[int, int, int]:
        return (candidate.handle, candidate.owner_address, candidate.unit_address)

    def current_manual_unit_identity(self) -> tuple[int, int, int] | None:
        identity = self.view.value('state').get('manual_unit_identity')
        if isinstance(identity, tuple) and len(identity) == 3 and all((isinstance(value, int) for value in identity)):
            return identity
        return None

    def current_display_unit_identity(self) -> tuple[int, int, int] | None:
        identity = self.view.value('state').get('selected_unit_identity')
        if isinstance(identity, tuple) and len(identity) == 3 and all((isinstance(value, int) for value in identity)):
            return identity
        return None

    def current_display_uses_win10(self) -> bool:
        return PRODUCT_READ_MODE == 'backup'

    def current_display_unit_rawcode(self) -> int:
        if self.current_display_unit_identity() is None:
            raise ValueError('请先使用读取当前选中单位或备用读取，再执行复制单位')
        rawcode = self.view.value('state').get('selected_unit_type_id')
        if not isinstance(rawcode, int) or not rawcode:
            raise ValueError('当前读取结果没有有效单位 ID，请重新读取后再执行复制单位')
        return rawcode

    def elephant_trainer(self) -> War3Trainer:
        batch_trainer = self.view.value('state').get('elephant_batch_trainer')
        if isinstance(batch_trainer, War3Trainer):
            batch_trainer.refresh_window(allow_pid_change=True)
            return batch_trainer
        return self.trainer()

    def remembered_unit_identities(self) -> list[tuple[int, int, int]]:
        remembered: list[tuple[int, int, int]] = []
        for key in ('manual_unit_identity', 'selected_unit_identity', 'last_verified_unit_identity'):
            identity = self.view.value('state').get(key)
            if isinstance(identity, tuple) and len(identity) == 3 and all((isinstance(value, int) for value in identity)) and (identity not in remembered):
                remembered.append(identity)
        return remembered

    def populate_selection_candidates(self, summaries: list[UnitSelectionSummary]) -> None:
        candidate_map: dict[str, UnitSelectionSummary] = {}
        self.view.value('candidate_tree').delete(*self.view.value('candidate_tree').get_children())
        preferred_identity = self.view.value('state').get('manual_unit_identity') or self.view.value('state').get('selected_unit_identity')
        selected_iid = ''
        for index, summary in enumerate(summaries, 1):
            iid = str(index)
            candidate_map[iid] = summary
            candidate = summary.candidate
            confidence = self.view.value('ui_text')(selection_confidence_text(summary))
            pos = summary.position
            pos_text = f'{pos[0]:.0f},{pos[1]:.0f}' if pos is not None else ''
            components = ','.join(summary.components) if summary.components else '-'
            inventory = ','.join(summary.inventory) if summary.inventory else '-'
            self.view.value('candidate_tree').insert('', 'end', iid=iid, values=(index, confidence, summary.hp_text, summary.mp_text, pos_text, f'{summary.refs}/{summary.known_hits}', components, inventory, f'0x{candidate.handle:x}', f'0x{candidate.owner_address:x}', f'0x{candidate.unit_address:x}'))
            if self.unit_identity(candidate) == preferred_identity:
                selected_iid = iid
            elif not selected_iid and summary.known_hits >= 2:
                selected_iid = iid
        self.view.value('state')['selection_candidates'] = candidate_map
        if selected_iid:
            self.view.value('candidate_tree').selection_set(selected_iid)
            self.view.value('candidate_tree').focus(selected_iid)

    def selected_selection_candidate(self) -> UnitSelectionSummary:
        selection = self.view.value('candidate_tree').selection()
        if not selection:
            raise ValueError('请先在候选单位表选择一行')
        candidates = self.view.value('state').get('selection_candidates', {})
        if not isinstance(candidates, dict):
            raise ValueError('候选单位表尚未刷新')
        summary = candidates.get(str(selection[0]))
        if not isinstance(summary, UnitSelectionSummary):
            raise ValueError('候选单位表尚未刷新')
        return summary

    def refresh_unit_candidates(self) -> str:
        summaries = self.trainer().list_selection_candidates(extra_identities=self.remembered_unit_identities())
        self.view.value('root').after(0, self.populate_selection_candidates, summaries)
        return f'已列出 {len(summaries)} 个候选单位；慢速扫描结果请选择 HP/MP、坐标、组件和物品槽匹配的行'

    def populate_auto_selected_unit_readout(self, panel: VisibleUnitPanel, cand: UnitCandidate, fields: list[UnitMemoryField], force_targets: bool=False, win10_compat: bool=False) -> None:
        self.view.value('state')['manual_unit_identity'] = None
        self.populate_selected_unit_readout(panel, cand, fields, force_targets, win10_compat)

    def populate_manual_candidate_readout(self, panel: VisibleUnitPanel, cand: UnitCandidate, fields: list[UnitMemoryField], force_targets: bool=False, win10_compat: bool=False) -> None:
        self.view.value('state')['manual_unit_identity'] = self.unit_identity(cand)
        self.populate_selected_unit_readout(panel, cand, fields, force_targets, win10_compat)

    def read_selection_candidate_fields(self) -> str:
        summary = self.selected_selection_candidate()
        identity = self.unit_identity(summary.candidate)
        t = self.trainer()
        panel, cand, fields = t.read_unit_fields_by_identity(*identity)
        self.view.value('root').after(0, self.populate_manual_candidate_readout, panel, cand, fields, True)
        return f'已读取所选候选：HP {panel.hp_text}，MP {panel.mp_text}；owner=0x{cand.owner_address:x} handle=0x{cand.handle:x} unit=0x{cand.unit_address:x}'

    def clear_selected_unit_readout(self) -> None:
        for var in (self.view.value('hp_current'), self.view.value('hp_max_current'), self.view.value('hp_regen_current'), self.view.value('mp_current'), self.view.value('mp_max_current'), self.view.value('mp_regen_current'), self.view.value('hp_target'), self.view.value('mp_target'), self.view.value('hp_regen_target'), self.view.value('mp_regen_target'), self.view.value('x_current'), self.view.value('y_current'), self.view.value('unit_type_id_current'), self.view.value('x_target'), self.view.value('y_target'), self.view.value('unit_field_target')):
            var.set('')
        self.view.value('state')['selected_unit_identity'] = None
        self.view.value('state')['selected_unit_win10'] = False
        self.view.value('state')['selected_unit_type_id'] = 0
        self.view.value('state')['manual_unit_identity'] = None
        self.view.value('state')['unit_fields'] = {}
        try:
            self.view.value('unit_field_tree').delete(*self.view.value('unit_field_tree').get_children())
        except NameError:
            pass

    def populate_selected_unit_readout(self, panel: VisibleUnitPanel, cand: UnitCandidate, fields: list[UnitMemoryField], force_targets: bool=False, win10_compat: bool=False) -> None:
        field_by_key = {field.key: field for field in fields}
        identity = (cand.handle, cand.owner_address, cand.unit_address)
        reset_targets = force_targets or self.view.value('state').get('selected_unit_identity') != identity
        self.view.value('state')['selected_unit_identity'] = identity
        self.view.value('state')['selected_unit_win10'] = bool(win10_compat)
        self.view.value('state')['selected_unit_type_id'] = int(cand.unit_type_id)
        self.view.value('state')['last_verified_unit_identity'] = identity
        self.view.value('unit_type_id_current').set(format_rawcode(cand.unit_type_id) if cand.unit_type_id else '')
        self.view.value('hp_current').set(str(panel.current_hp))
        self.view.value('hp_max_current').set(str(panel.max_hp))
        self.view.value('mp_current').set(str(panel.current_mp))
        self.view.value('mp_max_current').set(str(panel.max_mp))
        hp_regen_field = field_by_key.get('hp_regen')
        mp_regen_field = field_by_key.get('mp_regen')
        self.view.value('hp_regen_current').set(hp_regen_field.value_text() if hp_regen_field is not None else '')
        self.view.value('mp_regen_current').set(mp_regen_field.value_text() if mp_regen_field is not None else '')
        x_field = field_by_key.get('x')
        y_field = field_by_key.get('y')
        if x_field is not None and y_field is not None:
            pos_x = float(x_field.value)
            pos_y = float(y_field.value)
            self.view.value('x_current').set(f'{pos_x:.3f}')
            self.view.value('y_current').set(f'{pos_y:.3f}')
            if reset_targets:
                self.view.value('x_target').set(f'{pos_x:.3f}')
                self.view.value('y_target').set(f'{pos_y:.3f}')
        else:
            self.view.value('x_current').set('')
            self.view.value('y_current').set('')
            if reset_targets:
                self.view.value('x_target').set('')
                self.view.value('y_target').set('')
        if reset_targets:
            self.view.value('hp_target').set(str(panel.current_hp))
            self.view.value('mp_target').set(str(panel.current_mp) if panel.max_mp or panel.current_mp else '')
            self.view.value('hp_regen_target').set(self.view.value('hp_regen_current').get())
            self.view.value('mp_regen_target').set(self.view.value('mp_regen_current').get())
        self.populate_unit_fields(fields)

    def read_unit_fields(self) -> str:
        try:
            t = self.trainer()
            panel, cand, fields = t.read_selected_unit_fields()
        except Exception:
            self.view.value('root').after(0, self.clear_selected_unit_readout)
            self.view.value('root').after(0, self.populate_selection_candidates, [])
            raise
        self.view.value('root').after(0, self.populate_auto_selected_unit_readout, panel, cand, fields, True)
        warnings = getattr(t, '_unit_field_warnings', ())
        warning = '；' + '、'.join(warnings) if warnings else ''
        return f'选中单位字段：HP {panel.hp_text}，MP {panel.mp_text}；source={cand.selection_source or 'unknown'} owner=0x{cand.owner_address:x} handle=0x{cand.handle:x} unit=0x{cand.unit_address:x}{warning}'

    def selected_unit_field(self) -> UnitMemoryField:
        selection = self.view.value('unit_field_tree').selection()
        if not selection:
            raise ValueError('请先在字段表选择一项')
        fields = self.view.value('state').get('unit_fields', {})
        if not isinstance(fields, dict):
            raise ValueError('字段表尚未刷新')
        field = fields.get(selection[0])
        if not isinstance(field, UnitMemoryField):
            raise ValueError('字段表尚未刷新')
        return field

    def set_advanced_unit_field(self) -> str:
        field = self.selected_unit_field()
        if not field.writable:
            raise ValueError('该字段不可写')
        value = self.view.value('unit_field_target').get().strip()
        if not value:
            raise ValueError('请填写目标值')
        t = self.trainer()
        target_identity = self.current_display_unit_identity()
        if target_identity is not None:
            if self.current_display_uses_win10():
                written = t.write_unit_field_by_identity_win10(*target_identity, field.key, value)
                panel, cand, fields = t.read_unit_fields_by_identity_win10(*target_identity)
                self.view.value('root').after(0, self.populate_manual_candidate_readout, panel, cand, fields, False, True)
            else:
                written = t.write_unit_field_by_identity(*target_identity, field.key, value)
                panel, cand, fields = t.read_unit_fields_by_identity(*target_identity)
                self.view.value('root').after(0, self.populate_manual_candidate_readout, panel, cand, fields, False)
        else:
            written = t.write_selected_unit_field(field.key, value)
            panel, cand, fields = t.read_selected_unit_fields()
            self.view.value('root').after(0, self.populate_auto_selected_unit_readout, panel, cand, fields, False)
        note = f'；{written.note}' if written.note else ''
        return f'{written.label} 已写入 {written.value_text()}{note}'

    def populate_locks(self) -> None:
        locks = self.view.value('state').get('locks', {})
        if not isinstance(locks, dict):
            return
        self.view.value('lock_tree').delete(*self.view.value('lock_tree').get_children())
        for lock_id, item in locks.items():
            if not isinstance(item, dict):
                continue
            self.view.value('lock_tree').insert('', 'end', iid=str(lock_id), values=(self.view.value('ui_text')(item.get('scope', '')), self.view.value('ui_text')(item.get('label', '')), item.get('value', '')))

    def add_unit_lock(self) -> str:
        field = self.selected_unit_field()
        if not field.writable:
            raise ValueError('该字段不可锁定')
        value = self.view.value('unit_field_target').get().strip()
        if not value:
            raise ValueError('请填写锁定目标值')
        locks = self.view.value('state').get('locks', {})
        if not isinstance(locks, dict):
            locks = {}
            self.view.value('state')['locks'] = locks
        locks[f'unit:{field.key}'] = {'scope': '选中单位', 'kind': 'unit', 'key': field.key, 'label': field.label, 'value': value, 'unit_identity': self.current_display_unit_identity(), 'win10_compat': self.current_display_uses_win10()}
        self.view.value('root').after(0, self.populate_locks)
        return f'已锁定选中单位字段：{field.label}={value}'

    def add_resource_lock(self, kind: str) -> str:
        cache = self.selected_resource_cache()
        group_label = self.selected_resource_label(cache)
        targets = {'gold': ('金币', self.view.value('gold_target').get().strip()), 'lumber': ('木材', self.view.value('lumber_target').get().strip()), 'food_used': ('当前人口', self.view.value('food_used_target').get().strip()), 'food_cap': ('最大人口', self.view.value('food_cap_target').get().strip())}
        label, value = targets[kind]
        if not value:
            raise ValueError(f'请先填写目标{label}')
        parse_int(value, f'目标{label}')
        locks = self.view.value('state').get('locks', {})
        if not isinstance(locks, dict):
            locks = {}
            self.view.value('state')['locks'] = locks
        cache_iid = self.resource_iid(cache)
        is_local_player = cache_iid == str(self.view.value('state').get('local_resource_iid', ''))
        locks[f'resource:{cache_iid}:{kind}'] = {'scope': '本地玩家资源' if is_local_player else f'资源组 {group_label}', 'kind': 'resource', 'key': kind, 'resource_cache': cache, 'resource_local_player': is_local_player, 'label': f'{label}', 'value': value}
        self.view.value('root').after(0, self.populate_locks)
        return f'已锁定资源组 {group_label}：{label}={value}'

    def remove_selected_lock(self) -> str:
        selection = self.view.value('lock_tree').selection()
        if not selection:
            raise ValueError('请先选择要解锁的项目')
        locks = self.view.value('state').get('locks', {})
        if isinstance(locks, dict):
            for lock_id in selection:
                locks.pop(lock_id, None)
        self.view.value('root').after(0, self.populate_locks)
        return '已解锁所选项目'

    def apply_locks_once(self) -> None:
        locks = self.view.value('state').get('locks', {})
        if not isinstance(locks, dict) or not locks:
            return
        t = self.trainer()
        for item in list(locks.values()):
            if not isinstance(item, dict):
                continue
            kind = item.get('kind')
            key = str(item.get('key', ''))
            value = str(item.get('value', ''))
            if kind == 'unit':
                identity = item.get('unit_identity')
                if isinstance(identity, tuple) and len(identity) == 3 and all((isinstance(part, int) for part in identity)):
                    if item.get('win10_compat'):
                        t.write_unit_field_by_identity_win10(*identity, key, value)
                    else:
                        t.write_unit_field_by_identity(*identity, key, value)
                else:
                    t.write_selected_unit_field(key, value)
                continue
            if kind != 'resource':
                continue
            target = parse_int(value, str(item.get('label', '资源')))
            cache = item.get('resource_cache')
            if not isinstance(cache, ResourceCache):
                raise ValueError('锁定项缺少资源组地址，请删除后重新锁定')
            is_local_player = bool(item.get('resource_local_player'))

            def write_locked_resource(target_cache: ResourceCache) -> ResourceCache:
                if key == 'gold':
                    return t.write_resource_cache(target_cache, target_gold=target)
                if key == 'lumber':
                    return t.write_resource_cache(target_cache, target_lumber=target)
                if key == 'food_used':
                    return t.write_resource_cache(target_cache, target_food_used=target, sync_local_food_used=is_local_player)
                if key == 'food_cap':
                    return t.write_resource_cache(target_cache, target_food_cap=target, sync_local_food_cap=is_local_player)
                raise ValueError(f'未知资源锁定字段：{key}')
            if is_local_player:
                try:
                    cache = t.validate_local_player_resource_cache(cache)
                except (OSError, RuntimeError):
                    cache = t.locate_local_player_resource_cache()
            try:
                item['resource_cache'] = write_locked_resource(cache)
            except (OSError, RuntimeError):
                if not is_local_player:
                    raise
                cache = t.locate_local_player_resource_cache()
                item['resource_cache'] = write_locked_resource(cache)

    def lock_tick(self) -> None:
        if self.view.value('state').get('closing'):
            return
        locks = self.view.value('state').get('locks', {})
        if isinstance(locks, dict) and locks and (not self.view.value('state').get('lock_busy')):
            self.view.value('state')['lock_busy'] = True

            def worker() -> None:
                acquired = self.view.value('operation_lock').acquire(blocking=False)
                if not acquired:
                    self.view.value('state')['lock_busy'] = False
                    return
                try:
                    self.apply_locks_once()
                    if not self.view.value('state').get('closing'):
                        self.view.value('root').after(0, self.set_status, f'锁定中：{len(locks)} 项')
                except Exception as exc:
                    if not self.view.value('state').get('closing'):
                        self.view.value('root').after(0, self.set_status, f'锁定失败：{exc}')
                finally:
                    self.view.value('operation_lock').release()
                    self.view.value('state')['lock_busy'] = False
            self.start_operation_thread(worker, 'war3-lock-tick')
        if not self.view.value('state').get('closing'):
            self.view.value('root').after(1500, self.lock_tick)

    def ally_health_lock_tick(self) -> None:
        if self.view.value('state').get('closing'):
            return
        if self.view.value('state').get('ally_health_lock') and (not self.view.value('state').get('ally_health_lock_busy')):
            lock_trainer = self.view.value('state').get('ally_health_lock_trainer')
            if isinstance(lock_trainer, War3Trainer):
                self.view.value('state')['ally_health_lock_busy'] = True

                def worker() -> None:
                    acquired = self.view.value('operation_lock').acquire(blocking=False)
                    if not acquired:
                        self.view.value('state')['ally_health_lock_busy'] = False
                        return
                    try:
                        lock_trainer.heal_local_player_units()
                    except Exception as exc:
                        self.view.value('state')['ally_health_lock'] = False
                        self.view.value('state')['ally_health_lock_trainer'] = None
                        if not self.view.value('state').get('closing'):
                            self.view.value('root').after(0, self.set_status, f'我方锁血已停止：{exc}')
                    finally:
                        self.view.value('operation_lock').release()
                        self.view.value('state')['ally_health_lock_busy'] = False
                try:
                    self.start_operation_thread(worker, 'war3-ally-health-lock')
                except Exception:
                    self.view.value('state')['ally_health_lock_busy'] = False
                    self.view.value('state')['ally_health_lock'] = False
                    self.view.value('state')['ally_health_lock_trainer'] = None
                    raise
        if not self.view.value('state').get('closing'):
            self.view.value('root').after(100, self.ally_health_lock_tick)

    def rapid_build_tick(self) -> None:
        if self.view.value('state').get('closing'):
            return
        if self.view.value('state').get('rapid_build') and (not self.view.value('state').get('rapid_build_busy')):
            build_trainer = self.view.value('state').get('rapid_build_trainer')
            if isinstance(build_trainer, War3Trainer):
                self.view.value('state')['rapid_build_busy'] = True

                def worker() -> None:
                    acquired = self.view.value('operation_lock').acquire(blocking=False)
                    if not acquired:
                        self.view.value('state')['rapid_build_busy'] = False
                        return
                    try:
                        build_trainer.complete_local_player_structures()
                    except Exception as exc:
                        self.view.value('state')['rapid_build'] = False
                        self.view.value('state')['rapid_build_trainer'] = None
                        if not self.view.value('state').get('closing'):
                            self.view.value('root').after(0, self.set_status, f'持续快速建造/升级已停止：{exc}')
                    finally:
                        self.view.value('operation_lock').release()
                        self.view.value('state')['rapid_build_busy'] = False
                try:
                    self.start_operation_thread(worker, 'war3-rapid-build')
                except Exception:
                    self.view.value('state')['rapid_build_busy'] = False
                    self.view.value('state')['rapid_build'] = False
                    self.view.value('state')['rapid_build_trainer'] = None
                    raise
        if not self.view.value('state').get('closing'):
            self.view.value('root').after(1000, self.rapid_build_tick)

    def set_unit(self) -> str:
        t = self.trainer()
        hp_now = parse_float(self.view.value('hp_current').get(), '当前生命') if self.view.value('hp_current').get().strip() else 0.0
        mp_now = parse_float(self.view.value('mp_current').get(), '当前魔法') if self.view.value('mp_current').get().strip() else None
        hp_max_now = parse_float(self.view.value('hp_max_current').get(), '生命上限') if self.view.value('hp_max_current').get().strip() else None
        mp_max_now = parse_float(self.view.value('mp_max_current').get(), '魔法上限') if self.view.value('mp_max_current').get().strip() else None
        hp_new = parse_float(self.view.value('hp_target').get(), '目标生命') if self.view.value('hp_target').get().strip() else None
        mp_new = parse_float(self.view.value('mp_target').get(), '目标魔法') if self.view.value('mp_target').get().strip() else None
        hp_regen_new = parse_float(self.view.value('hp_regen_target').get(), '目标 HP 回复率') if self.view.value('hp_regen_target').get().strip() else None
        mp_regen_new = parse_float(self.view.value('mp_regen_target').get(), '目标 MP 回复率') if self.view.value('mp_regen_target').get().strip() else None
        x_new = parse_changed_coordinate(self.view.value('x_target').get(), self.view.value('x_current').get(), '目标 X')
        y_new = parse_changed_coordinate(self.view.value('y_target').get(), self.view.value('y_current').get(), '目标 Y')
        if hp_new is None and mp_new is None and (hp_regen_new is None) and (mp_regen_new is None) and (x_new is None) and (y_new is None):
            raise ValueError('至少填写一个目标生命、魔法、回复率或坐标')
        target_identity = self.current_display_unit_identity()
        if target_identity is not None:
            if self.current_display_uses_win10():
                cand = t.set_unit_by_identity_win10(*target_identity, hp_now, mp_now, hp_new, mp_new, hp_max_now, mp_max_now, x_new, y_new, hp_regen_new, mp_regen_new)
                panel, cand_after, fields = t.read_unit_fields_by_identity_win10(*target_identity)
                self.view.value('root').after(0, self.populate_manual_candidate_readout, panel, cand_after, fields, True, True)
            else:
                cand = t.set_unit_by_identity(*target_identity, hp_now, mp_now, hp_new, mp_new, hp_max_now, mp_max_now, x_new, y_new, hp_regen_new, mp_regen_new)
                panel, cand_after, fields = t.read_unit_fields_by_identity(*target_identity)
                self.view.value('root').after(0, self.populate_manual_candidate_readout, panel, cand_after, fields, True)
            return f'候选单位已写入；source={cand.selection_source or 'manual'} base=0x{cand.base:x} unit=0x{cand.unit_address:x} {cand.note}'
        cand = t.set_selected_unit(hp_now, mp_now, hp_new, mp_new, hp_max_now, mp_max_now, x_new, y_new, hp_regen_new, mp_regen_new)
        panel, cand_after, fields = t.read_selected_unit_fields()
        self.view.value('root').after(0, self.populate_auto_selected_unit_readout, panel, cand_after, fields, True)
        return f'选中单位已写入；source={cand.selection_source or 'unknown'} base=0x{cand.base:x} unit=0x{cand.unit_address:x} {cand.note}'

    def read_unit(self) -> str:
        started = time.perf_counter()
        try:
            t = self.trainer()
            panel, cand, fields = t.read_selected_unit_fields()
        except Exception:
            self.view.value('root').after(0, self.clear_selected_unit_readout)
            self.view.value('root').after(0, self.populate_selection_candidates, [])
            raise
        self.view.value('root').after(0, self.populate_auto_selected_unit_readout, panel, cand, fields, True)
        selected_summaries = t.selected_unit_summaries()
        if selected_summaries:
            self.view.value('root').after(0, self.populate_selection_candidates, list(selected_summaries))
        elapsed_ms = (time.perf_counter() - started) * 1000
        return f'已读取当前选中的 {max(1, len(selected_summaries))} 个单位；主单位 HP {panel.hp_text}，MP {panel.mp_text}；source={cand.selection_source or 'unknown'} base=0x{cand.base:x} unit=0x{cand.unit_address:x}；耗时 {elapsed_ms:.0f} ms'

    def read_unit_win10(self) -> str:
        return self.read_unit()

    def read_unit_with_sound(self) -> str:
        return call_with_read_success_sound(self.read_unit)

    def read_unit_win10_with_sound(self) -> str:
        return call_with_read_success_sound(self.read_unit_win10)

    def read_unit_native_selection(self) -> str:
        started = time.perf_counter()
        try:
            t = self.trainer()
            panel, cand, fields = t.read_selected_unit_fields()
        except Exception:
            self.view.value('root').after(0, self.clear_selected_unit_readout)
            self.view.value('root').after(0, self.populate_selection_candidates, [])
            raise
        self.view.value('root').after(0, self.populate_auto_selected_unit_readout, panel, cand, fields, True)
        selected_summaries = t.selected_unit_summaries()
        if selected_summaries:
            self.view.value('root').after(0, self.populate_selection_candidates, list(selected_summaries))
        elapsed_ms = (time.perf_counter() - started) * 1000
        return f'已读取当前选中的 {max(1, len(selected_summaries))} 个单位；主单位 HP {panel.hp_text}，MP {panel.mp_text}；source={cand.selection_source or 'unknown'} base=0x{cand.base:x} unit=0x{cand.unit_address:x}；耗时 {elapsed_ms:.0f} ms'

    def prewarm_selection_cache(self) -> str:
        t = self.trainer()
        try:
            cand = t.prewarm_selected_unit_cache()
        except (RuntimeError, OSError) as exc:
            return f'选择缓存等待游戏状态稳定（{exc}）'
        return f'选择缓存已预热；unit=0x{cand.unit_address:x}'

    def elephant_prewarm(self) -> str:
        count = self.elephant_trainer().prewarm_elephant_functions()
        if getattr(self.elephant_trainer(), '_native_selection_unavailable', False):
            return f'3.0 对象链已预热：{count} 个选中单位可直接操作；当前引擎批处理已启用'
        return f'大象功能已初始化：{count} 个 native 函数可用'

    def elephant_batch(self, action: Callable[[], object], label: str, *, direct_memory: bool=False) -> tuple[object, ...]:
        batch_trainer = self.elephant_trainer()
        self.view.value('state')['elephant_batch_trainer'] = batch_trainer
        try:
            succeeded, failed, results, errors = batch_trainer.run_for_selected_units(action)
        finally:
            self.view.value('state').pop('elephant_batch_trainer', None)
        if not succeeded:
            detail = errors[0] if errors else '没有可操作的选中单位'
            raise RuntimeError(f'{label}未成功：{detail}')
        self.view.value('state')['last_elephant_batch_failed'] = failed
        return results

    def elephant_batch_suffix(self) -> str:
        failed = int(self.view.value('state').pop('last_elephant_batch_failed', 0))
        return f'，跳过/失败 {failed} 个' if failed else ''

    def elephant_current_engine_batch(self, action: Callable[[], object], label: str) -> tuple[object, ...]:
        batch_trainer = self.elephant_trainer()
        if not getattr(batch_trainer, '_native_selection_unavailable', False):
            return self.elephant_batch(action, label)
        result = action()
        if isinstance(result, dict) and isinstance(result.get('rows'), list):
            rows = tuple(result['rows'])
        elif isinstance(result, int) and (not isinstance(result, bool)):
            rows = tuple((1 for _ in range(result)))
        else:
            rows = (result,)
        self.view.value('state')['last_elephant_batch_failed'] = 0
        if not rows:
            raise RuntimeError(f'{label}未成功：没有可操作的选中单位')
        return rows

    def elephant_read_hero_level(self) -> str:
        trainer = self.elephant_trainer()
        if getattr(trainer, '_native_selection_unavailable', False):
            result = trainer.hero_progress_24268()
            rows = tuple(result.get('rows', ()))
            if not rows:
                raise RuntimeError('当前选中单位中没有可读取的英雄')
            level = int(rows[0]['after'])
            self.view.value('root').after(0, self.view.value('elephant_hero_level').set, str(level))
            return f'已读取 {len(rows)} 个英雄；首个等级：{level}，跳过 {result['skipped']} 个非英雄'
        levels = self.elephant_batch(self.elephant_trainer().get_selected_hero_level, '读取英雄等级')
        level = int(levels[0])
        self.view.value('root').after(0, self.view.value('elephant_hero_level').set, str(level))
        return f'已读取 {len(levels)} 个英雄；首个英雄等级：{level}{self.elephant_batch_suffix()}'

    def elephant_set_hero_level(self) -> str:
        target = parse_int(self.view.value('elephant_hero_level').get(), '英雄等级')
        if not 1 <= target <= 100000:
            raise ValueError('英雄等级必须在 1 到 100000 之间')
        trainer = self.elephant_trainer()
        if getattr(trainer, '_native_selection_unavailable', False):
            result = trainer.hero_progress_24268(target)
            self.view.value('root').after(0, self.view.value('elephant_hero_level').set, str(target))
            return f'已设置 {len(result['rows'])} 个英雄等级为 {target}，实际修改 {result['changed']} 个，跳过 {result['skipped']} 个非英雄'
        results = self.elephant_batch(lambda: self.elephant_trainer().set_selected_hero_level(target), '设置英雄等级')
        self.view.value('root').after(0, self.view.value('elephant_hero_level').set, str(target))
        return f'已将 {len(results)} 个英雄的等级设置为 {target}{self.elephant_batch_suffix()}'

    def elephant_set_scale(self) -> str:
        scale = parse_float(self.view.value('elephant_unit_scale').get(), '单位大小')
        trainer = self.elephant_trainer()
        if getattr(trainer, '_native_selection_unavailable', False):
            changed = trainer.set_selected_group_scale(scale)
            return f'已将 {changed} 个单位的大小设置为 {scale:g}'
        results = self.elephant_batch(lambda: trainer.set_selected_unit_scale(scale), '设置单位大小')
        return f'已将 {len(results)} 个单位的大小设置为 {scale:g}{self.elephant_batch_suffix()}'

    def elephant_create_unit(self, copy_selected: bool, preserve_owner: bool=False) -> str:
        rawcode: int | str | None
        if copy_selected:
            rawcode = None
        else:
            rawcode = self.view.value('elephant_unit_rawcode').get().strip()
        if not copy_selected and (not rawcode):
            raise ValueError('请填写单位 ID')
        if copy_selected:
            trainer = self.elephant_trainer()
            if getattr(trainer, '_native_selection_unavailable', False):
                x, y = trainer.query_mouse_world_position()
                result = trainer.clone_batch_24268(keep=True, preserve_owner=preserve_owner, copy_abilities=True, copy_items=True, spawn=True, spawn_x_bits=trainer._float_bits(float(x)), spawn_y_bits=trainer._float_bits(float(y)))
                return f'已复制 {result['count']} 个选中单位，技能 {sum((row['ability_count'] for row in result['rows']))} 个，物品 {sum((row['item_count'] for row in result['rows']))} 个'
            results = self.elephant_batch(lambda: trainer.create_local_unit(None, use_selected_lookup=True, preserve_owner=preserve_owner), '复制选中单位')
            owner_text = '并保留原阵营' if preserve_owner else '给自己'
            return f'已复制 {len(results)} 个选中单位{owner_text}{self.elephant_batch_suffix()}'
        unit_rawcode, handle = self.elephant_trainer().create_local_unit(rawcode, use_selected_lookup=True)
        return f'已创建 {format_rawcode(unit_rawcode)}；handle=0x{handle:x}'

    def elephant_add_item(self) -> str:
        rawcode = self.view.value('elephant_item_rawcode').get().strip()
        if not rawcode:
            raise ValueError('请填写物品 ID')
        trainer = self.elephant_trainer()
        if getattr(trainer, '_native_selection_unavailable', False):
            result = trainer.item_batch_24268(1, rawcode)
            return f'已创建 {result['count']} 件物品：入包 {result['stored']} 件，落地 {result['ground']} 件'
        results = self.elephant_batch(lambda: self.elephant_trainer().add_item_to_selected_unit(rawcode), f'添加物品 {rawcode}')
        return f'已向 {len(results)} 个单位添加物品 {rawcode}{self.elephant_batch_suffix()}'

    def elephant_clear_inventory(self) -> str:
        trainer = self.elephant_trainer()
        if getattr(trainer, '_native_selection_unavailable', False):
            result = trainer.item_batch_24268(4, 0, -1)
            return f'已核对 {result['count']} 个单位，清空 {result['changed']} 件物品'
        results = self.elephant_batch(trainer.clear_selected_unit_inventory, '清空背包')
        return f'已清空 {len(results)} 个单位的背包，共删除 {sum(map(int, results))} 件物品{self.elephant_batch_suffix()}'

    def elephant_add_ability(self) -> str:
        rawcode = self.view.value('elephant_ability_rawcode').get().strip()
        if not rawcode:
            raise ValueError('请填写技能 ID')
        trainer = self.elephant_trainer()
        if getattr(trainer, '_native_selection_unavailable', False):
            result = trainer.ability_batch_24268(rawcode, 1, 0)
            return f'技能操作完成：{result['count']} 个单位，实际修改 {result['changed']} 个'
        results = self.elephant_batch(lambda: self.elephant_trainer().add_ability_to_selected_unit(rawcode), f'添加技能 {rawcode}')
        return f'已向 {len(results)} 个单位添加技能 {rawcode}{self.elephant_batch_suffix()}'

    def elephant_remove_ability(self) -> str:
        rawcode = self.view.value('elephant_ability_rawcode').get().strip()
        if not rawcode:
            raise ValueError('请填写技能 ID')
        trainer = self.elephant_trainer()
        if getattr(trainer, '_native_selection_unavailable', False):
            result = trainer.ability_batch_24268(rawcode, 2, 0)
            return f'技能操作完成：{result['count']} 个单位，实际修改 {result['changed']} 个'
        results = self.elephant_batch(lambda: self.elephant_trainer().remove_ability_from_selected_unit(rawcode), f'删除技能 {rawcode}')
        return f'已从 {len(results)} 个单位删除技能 {rawcode}{self.elephant_batch_suffix()}'

    def elephant_set_ability_level(self) -> str:
        rawcode = self.view.value('elephant_ability_rawcode').get().strip()
        level = parse_int(self.view.value('elephant_ability_level').get(), '技能等级')
        trainer = self.elephant_trainer()
        if getattr(trainer, '_native_selection_unavailable', False):
            if not 1 <= level <= 100000:
                raise ValueError('技能等级必须在 1 到 100000 之间')
            result = trainer.ability_batch_24268(rawcode, 1, level)
            return f'技能操作完成：{result['count']} 个单位，实际修改 {result['changed']} 个'
        results = self.elephant_batch(lambda: self.elephant_trainer().set_selected_unit_ability_level(rawcode, level), f'设置技能 {rawcode} 等级')
        return f'已为 {len(results)} 个单位设置技能 {rawcode} 等级{self.elephant_batch_suffix()}'

    def refresh_ability_field_tree(self) -> None:
        snapshot = self.view.value('state').get('ability_field_snapshot')
        rows: dict[str, AbilityFieldValue] = {}
        self.view.value('ability_field_tree').delete(*self.view.value('ability_field_tree').get_children())
        if not isinstance(snapshot, AbilityFieldSnapshot):
            self.view.value('state')['ability_field_rows'] = rows
            return
        query = self.view.value('ability_field_filter').get().strip().lower()
        show_zero = self.view.value('ability_field_show_zero').get()
        show_unsupported = self.view.value('ability_field_show_unsupported').get()
        type_labels = {'boolean': '布尔', 'integer': '整数', 'real': '实数', 'string': '字符串'}
        scope_labels = {'field': '全局', 'level': '等级', 'level_array': '等级数组'}
        for index, field_value in enumerate(snapshot.fields):
            spec = field_value.spec
            if not show_unsupported and field_value.status == '未开放':
                continue
            if not show_zero and field_value.value is not None and (field_value.value is False or field_value.value == 0 or field_value.value == 0.0):
                continue
            searchable = ' '.join((spec.rawcode, spec.constant_name, spec.field_name, spec.category, spec.metadata_type, field_value.note)).lower()
            if query and query not in searchable:
                continue
            iid = f'ability-field-{index}'
            rows[iid] = field_value
            label = spec.constant_name
            if label.startswith('METADATA_'):
                label = spec.field_name or spec.display_name or label
            self.view.value('ability_field_tree').insert('', 'end', iid=iid, values=(spec.rawcode, self.view.value('ui_text')(type_labels.get(spec.value_kind, spec.value_kind)), self.view.value('ui_text')(scope_labels.get(spec.scope, spec.scope)), self.view.value('ui_text')(label), self.view.value('ui_text')(field_value.value_text()), self.view.value('ui_text')(field_value.status)))
        self.view.value('state')['ability_field_rows'] = rows

    def apply_ability_field_snapshot(self, snapshot: AbilityFieldSnapshot) -> None:
        self.view.value('state')['ability_field_snapshot'] = snapshot
        effect_status = '' if snapshot.effect_class_verified else '（未确认）'
        source = '备用读取' if snapshot.win10_compat else '普通读取'
        effect_note = f'；{snapshot.effect_class_note}' if not snapshot.effect_class_verified and snapshot.effect_class_note else ''
        self.view.value('ability_field_summary').set(f'技能 {format_rawcode(snapshot.ability_rawcode)}；效果类 {format_rawcode(snapshot.effect_class)}{effect_status}；当前等级 {snapshot.current_level}；字段等级 {snapshot.requested_level}；候选 {len(snapshot.fields)} 项；来源 {source}{effect_note}')
        self.view.value('ability_field_value').set('')
        self.view.value('ability_field_detail').set('')
        self.view.value('ability_field_write_button').state(['disabled'])
        self.refresh_ability_field_tree()

    def read_ability_field_snapshot(self) -> str:
        rawcode = self.view.value('ability_field_rawcode').get().strip()
        if not rawcode:
            raise ValueError('请填写技能 ID')
        level = parse_int(self.view.value('ability_field_level').get(), '字段等级')
        identity = self.current_display_unit_identity()
        if identity is None:
            raise ValueError('请先使用普通读取或备用读取读取当前单位')
        snapshot = self.trainer().read_selected_ability_fields(rawcode, level, unit_identity=identity, win10_compat=self.current_display_uses_win10() if identity is not None else False)
        self.view.value('root').after(0, self.apply_ability_field_snapshot, snapshot)
        readable = sum((field.value is not None for field in snapshot.fields))
        writable = sum((field.value is not None and field.spec.writable for field in snapshot.fields))
        return f'已读取 {format_rawcode(snapshot.ability_rawcode)}：{readable} 项有值，{writable} 项可尝试写入'

    def select_ability_field(self, _event: object | None=None) -> None:
        selected = self.view.value('ability_field_tree').selection()
        rows = self.view.value('state').get('ability_field_rows')
        field_value = rows.get(selected[0]) if selected and isinstance(rows, dict) else None
        if not isinstance(field_value, AbilityFieldValue):
            self.view.value('ability_field_value').set('')
            self.view.value('ability_field_detail').set('')
            self.view.value('ability_field_write_button').state(['disabled'])
            return
        spec = field_value.spec
        self.view.value('ability_field_value').set(field_value.value_text())
        bounds = ''
        if spec.minimum is not None or spec.maximum is not None:
            bounds = f'；元数据范围 {spec.minimum!s} .. {spec.maximum!s}'
        specific = ''
        if spec.use_specific:
            specific = '；适用 ' + ','.join(spec.use_specific)
        self.view.value('ability_field_detail').set(f'{spec.rawcode} | {spec.constant_name} | {spec.metadata_type or spec.value_kind} | {spec.field_name or '-'}{bounds}{specific}' + (f'；{field_value.note}' if field_value.note else ''))
        if field_value.value is not None and spec.writable:
            self.view.value('ability_field_write_button').state(['!disabled'])
        else:
            self.view.value('ability_field_write_button').state(['disabled'])

    def write_selected_ability_field(self, snapshot: AbilityFieldSnapshot, rawcode: str, level: int, field_value: AbilityFieldValue, target_text: str) -> str:
        try:
            actual = self.trainer().set_selected_ability_field(rawcode, level, field_value.spec, target_text, expected_snapshot=snapshot, unit_identity=snapshot.unit_identity if any(snapshot.unit_identity) else None, win10_compat=snapshot.win10_compat)
        except RuntimeError as exc:
            if '游戏拒绝写入该技能字段' in str(exc) and '恢复无法确认' not in str(exc):
                rejected = replace(field_value, status='游戏拒绝', note=str(exc))
                key = (field_value.spec.rawcode, field_value.spec.value_kind, field_value.spec.scope)
                rejected_snapshot = replace(snapshot, fields=tuple((rejected if (item.spec.rawcode, item.spec.value_kind, item.spec.scope) == key else item for item in snapshot.fields)))
                self.view.value('root').after(0, lambda: self.apply_ability_field_snapshot(rejected_snapshot) if self.view.value('state').get('ability_field_snapshot') is snapshot else None)
            raise
        key = (field_value.spec.rawcode, field_value.spec.value_kind, field_value.spec.scope)
        updated_fields = tuple((actual if (item.spec.rawcode, item.spec.value_kind, item.spec.scope) == key else item for item in snapshot.fields))
        updated_snapshot = replace(snapshot, fields=updated_fields)
        self.view.value('root').after(0, lambda: self.apply_ability_field_snapshot(updated_snapshot) if self.view.value('state').get('ability_field_snapshot') is snapshot else None)
        return f'字段 {field_value.spec.rawcode} 已写入并读回：{actual.value_text()}'

    def ability_field_write_clicked(self) -> None:
        snapshot = self.view.value('state').get('ability_field_snapshot')
        if not isinstance(snapshot, AbilityFieldSnapshot):
            self.view.value('messagebox').showerror(self.view.value('ui_text')('错误'), self.view.value('ui_text')('请先读取技能字段'))
            return
        selected = self.view.value('ability_field_tree').selection()
        rows = self.view.value('state').get('ability_field_rows')
        field_value = rows.get(selected[0]) if selected and isinstance(rows, dict) else None
        if not isinstance(field_value, AbilityFieldValue):
            self.view.value('messagebox').showerror(self.view.value('ui_text')('错误'), self.view.value('ui_text')('请先选择一个可写字段'))
            return
        rawcode = self.view.value('ability_field_rawcode').get().strip()
        try:
            level = parse_int(self.view.value('ability_field_level').get(), '字段等级')
        except ValueError as exc:
            self.view.value('messagebox').showerror(self.view.value('ui_text')('错误'), __import__('war3_error_messages').format_error(exc, self.view.value('ui_language')['code']))
            return
        target_text = self.view.value('ability_field_value').get().strip()
        self.call_async(lambda: self.write_selected_ability_field(snapshot, rawcode, level, field_value, target_text), operation_key='ability-field-write', busy_text='正在写入并校验技能字段...')

    def refresh_item_field_tree(self) -> None:
        snapshot = self.view.value('state').get('item_field_snapshot')
        rows: dict[str, ItemFieldValue] = {}
        self.view.value('item_field_tree').delete(*self.view.value('item_field_tree').get_children())
        if not isinstance(snapshot, ItemFieldSnapshot):
            self.view.value('state')['item_field_rows'] = rows
            return
        query = self.view.value('item_field_filter').get().strip().lower()
        show_zero = self.view.value('item_field_show_zero').get()
        show_unsupported = self.view.value('item_field_show_unsupported').get()
        type_labels = {'boolean': '布尔', 'integer': '整数', 'real': '实数', 'string': '字符串'}
        for index, field_value in enumerate(snapshot.fields):
            spec = field_value.spec
            if not show_unsupported and field_value.status == '未开放':
                continue
            if not show_zero and field_value.value is not None and (field_value.value in (False, 0, 0.0)):
                continue
            searchable = ' '.join((spec.rawcode, spec.value_kind, spec.name, field_value.note)).lower()
            if query and query not in searchable:
                continue
            iid = f'item-field-{index}'
            rows[iid] = field_value
            self.view.value('item_field_tree').insert('', 'end', iid=iid, values=(spec.rawcode, self.view.value('ui_text')(type_labels.get(spec.value_kind, spec.value_kind)), self.view.value('ui_text')(spec.name), self.view.value('ui_text')(field_value.value_text()), self.view.value('ui_text')(field_value.status)))
        self.view.value('state')['item_field_rows'] = rows

    def apply_item_field_snapshot(self, snapshot: ItemFieldSnapshot) -> None:
        self.view.value('state')['item_field_snapshot'] = snapshot
        source = '备用读取' if snapshot.win10_compat else '普通读取'
        self.view.value('item_field_summary').set(f'物品栏 {snapshot.slot}；物品 {format_rawcode(snapshot.item_rawcode)}；handle=0x{snapshot.item_handle:x}；候选 {len(snapshot.fields)} 项；来源 {source}')
        self.view.value('item_field_value').set('')
        self.view.value('item_field_detail').set('')
        self.view.value('item_field_write_button').state(['disabled'])
        self.refresh_item_field_tree()

    def read_item_field_snapshot(self) -> str:
        slot = parse_int(self.view.value('item_field_slot').get(), '物品槽位')
        identity = self.current_display_unit_identity()
        if identity is None:
            raise ValueError('请先读取当前单位')
        snapshot = self.trainer().read_selected_item_fields(slot, unit_identity=identity, win10_compat=self.current_display_uses_win10())
        self.view.value('root').after(0, self.apply_item_field_snapshot, snapshot)
        readable = sum((field.value is not None for field in snapshot.fields))
        writable = sum((field.value is not None and field.spec.writable for field in snapshot.fields))
        return f'已读取物品栏 {snapshot.slot} 的 {format_rawcode(snapshot.item_rawcode)}：{readable} 项有值，{writable} 项可尝试写入'

    def select_item_field(self, _event: object | None=None) -> None:
        selected = self.view.value('item_field_tree').selection()
        rows = self.view.value('state').get('item_field_rows')
        field_value = rows.get(selected[0]) if selected and isinstance(rows, dict) else None
        if not isinstance(field_value, ItemFieldValue):
            self.view.value('item_field_value').set('')
            self.view.value('item_field_detail').set('')
            self.view.value('item_field_write_button').state(['disabled'])
            return
        spec = field_value.spec
        self.view.value('item_field_value').set(field_value.value_text())
        self.view.value('item_field_detail').set(f'{spec.rawcode} | {spec.value_kind} | {spec.name}' + (f'；{field_value.note}' if field_value.note else ''))
        if field_value.value is not None and spec.writable:
            self.view.value('item_field_write_button').state(['!disabled'])
        else:
            self.view.value('item_field_write_button').state(['disabled'])

    def write_selected_item_field(self, snapshot: ItemFieldSnapshot, field_value: ItemFieldValue, target_text: str) -> str:
        actual = self.trainer().set_selected_item_field(snapshot.slot, field_value.spec, target_text, snapshot, unit_identity=snapshot.unit_identity, win10_compat=snapshot.win10_compat)
        key = (field_value.spec.rawcode, field_value.spec.value_kind)
        updated_snapshot = replace(snapshot, fields=tuple((actual if (item.spec.rawcode, item.spec.value_kind) == key else item for item in snapshot.fields)))
        self.view.value('root').after(0, lambda: self.apply_item_field_snapshot(updated_snapshot) if self.view.value('state').get('item_field_snapshot') is snapshot else None)
        return f'物品字段 {field_value.spec.rawcode} 已写入并读回：{actual.value_text()}'

    def read_item_effect_field_snapshot(self, area: str, slot: int, level: int):
        return self.trainer().read_item_effect_fields(area, slot, level)

    def write_item_effect_field_value(self, snapshot, row_index: int, text: str):
        actual = self.trainer().write_item_effect_field(snapshot, row_index, text)
        self.set_status('物品附带技能字段已写入并读回，请在游戏中核对效果')
        return actual

    def item_effect_fields_view(self, snapshot) -> dict:
        source = snapshot.source
        labels = {'classic': '普通物品栏', 'bag': '扩展背包', 'equipment': '装备栏'}
        rows = []
        for index, (ability, field, note) in enumerate(snapshot.rows):
            ability_code = format_rawcode(ability['rawcode'])
            effect = format_rawcode(ability['effect_class'])
            spec = field.spec if field is not None else None
            rows.append(dict(_iid=f'{snapshot.generation}:{index}',
                field=spec.rawcode if spec else '—', type=spec.value_kind if spec else '组件',
                scope=spec.scope if spec else '', name=({'Iatt':'攻击加成','Idef':'护甲加成','Iagi':'敏捷加成','Iint':'智力加成','Istr':'力量加成','Imvb':'移动速度加成','Ilif':'生命值加成','Iman':'魔法值加成','Isib':'视野加成','acas':'施法时间','acdn':'冷却时间','adur':'持续时间','amcs':'魔法消耗','aare':'影响范围'}.get(spec.rawcode, spec.constant_name if not spec.constant_name.startswith('METADATA_') else spec.field_name or spec.display_name)) if spec else note,
                value=field.value_text() if field else '—', status=field.status if field else '只读',
                editable=bool(field and field.value is not None and spec.writable and spec.runtime_supported),
                ability=ability_code, effectClass=effect, note=field.note if field else note))
        return dict(summary=f"{labels[source.area]}第 {source.slot+1} 格；物品 {format_rawcode(source.rawcode)}；附带技能 {len(snapshot.abilities)} 个；字段 {len(rows)} 项；字段等级 {snapshot.level}",
            detail='修改当前这件物品的技能数值；地图脚本另行计算的加成未必属于这里。实际战斗效果请在游戏中核对。', rows=rows)

    def item_field_write_clicked(self) -> None:
        snapshot = self.view.value('state').get('item_field_snapshot')
        if not isinstance(snapshot, ItemFieldSnapshot):
            self.view.value('messagebox').showerror(self.view.value('ui_text')('错误'), self.view.value('ui_text')('请先读取物品字段'))
            return
        selected = self.view.value('item_field_tree').selection()
        rows = self.view.value('state').get('item_field_rows')
        field_value = rows.get(selected[0]) if selected and isinstance(rows, dict) else None
        if not isinstance(field_value, ItemFieldValue):
            self.view.value('messagebox').showerror(self.view.value('ui_text')('错误'), self.view.value('ui_text')('请先选择一个可写字段'))
            return
        self.call_async(lambda: self.write_selected_item_field(snapshot, field_value, self.view.value('item_field_value').get().strip()), operation_key='item-field-write', busy_text='正在写入并校验物品字段...')

    def elephant_set_tech(self) -> str:
        rawcode = self.view.value('elephant_tech_rawcode').get().strip()
        if not rawcode:
            raise ValueError('请填写科技 ID')
        level = parse_int(self.view.value('elephant_tech_level').get(), '科技等级')
        actual = self.elephant_trainer().set_local_player_tech(rawcode, level)
        return f'科技 {rawcode} 已设置为 {actual} 级'

    def elephant_set_xp_rate(self) -> str:
        rate = parse_float(self.view.value('elephant_xp_rate').get(), '经验倍率')
        actual = self.elephant_trainer().set_local_player_xp_rate(rate)
        return f'本地玩家经验倍率已设置为 {actual:g}'

    def elephant_toggle_game_speed(self) -> str:
        factor = parse_float(self.view.value('elephant_game_speed').get(), '游戏加速倍率')
        result = self.elephant_trainer().toggle_game_speed(factor)
        if result.get('unchanged'):
            return f'游戏已处于所选倍率：{result['rate']:g}x'
        return ('游戏加速倍率：' if result['accelerated'] else '已恢复游戏倍率：') + f'{result['rate']:g}x'

    def elephant_set_inventory_charges(self) -> str:
        charges = parse_int(self.view.value('elephant_item_charges').get(), '物品数量')
        trainer = self.elephant_trainer()
        if getattr(trainer, '_native_selection_unavailable', False):
            result = trainer.item_batch_24268(2, 0, charges)
            return f'已核对 {result['count']} 个单位的背包，修改 {result['changed']} 件物品次数'
        results = self.elephant_batch(lambda: self.elephant_trainer().set_selected_inventory_charges(charges), '设置物品数量', direct_memory=True)
        return f'已将 {sum(map(int, results))} 件背包物品的数量设为 {charges}{self.elephant_batch_suffix()}'

    def elephant_duplicate_inventory(self) -> str:
        trainer = self.elephant_trainer()
        if getattr(trainer, '_native_selection_unavailable', False):
            result = trainer.item_batch_24268(5, 0, -1)
            return f'已核对 {result['count']} 个单位，复制 {result['changed']} 件背包物品'
        results = self.elephant_batch(trainer.duplicate_selected_inventory_items, '复制背包物品')
        return f'已为 {len(results)} 个单位复制 {sum(map(int, results))} 件背包物品{self.elephant_batch_suffix()}'

    def elephant_drop_inventory(self) -> str:
        trainer = self.elephant_trainer()
        if getattr(trainer, '_native_selection_unavailable', False):
            result = trainer.item_batch_24268(6, 0, -1)
            return f'已核对 {result['count']} 个单位，丢弃 {result['changed']} 件背包物品'
        results = self.elephant_batch(trainer.drop_selected_inventory_items, '丢弃背包物品')
        return f'已从 {len(results)} 个单位丢弃 {sum(map(int, results))} 件背包物品{self.elephant_batch_suffix()}'

    def elephant_add_resources(self) -> str:
        amount = parse_int(self.view.value('elephant_resource_amount').get(), '金币木材增量')
        self.trainer().add_gold_and_lumber(amount)
        return f'金币和木材已增加 {amount}'

    def elephant_mass_clone(self) -> str:
        count = parse_int(self.view.value('elephant_mass_clone_count').get(), '批量复制数量')
        trainer = self.elephant_trainer()
        if getattr(trainer, '_native_selection_unavailable', False):
            unit_rawcode, created = trainer.create_local_units(count, None)
            return f'已按当前选择批量复制 {format_rawcode(unit_rawcode)}，共创建 {created} 个单位'
        results = self.elephant_batch(lambda: trainer.create_local_units(count, None, use_selected_lookup=True), '大量复制选中单位')
        created = sum((int(result[1]) for result in results))
        return f'已按 {len(results)} 个选中单位创建 {created} 个复制单位{self.elephant_batch_suffix()}'

    def elephant_set_hero_attributes(self) -> str:
        value = parse_int(self.view.value('elephant_hero_attributes').get(), '英雄属性')
        trainer = self.elephant_trainer()
        if getattr(trainer, '_native_selection_unavailable', False):
            changed = trainer.set_selected_group_hero_attributes(value)
            return f'已将 {changed} 个英雄的力量、敏捷、智力设置为 {value}'
        results = self.elephant_batch(lambda: trainer.set_selected_hero_attributes(value), '设置英雄属性', direct_memory=True)
        return f'已将 {len(results)} 个英雄的力量、敏捷、智力设置为 {value}{self.elephant_batch_suffix()}'

    def elephant_add_skill_points(self) -> str:
        amount = parse_int(self.view.value('elephant_skill_points').get(), '增加技能点数')
        trainer = self.elephant_trainer()
        if getattr(trainer, '_native_selection_unavailable', False):
            changed = trainer.add_selected_hero_skill_points(amount)
            return f'已为 {changed} 个英雄增加 {amount} 点技能点'
        results = self.elephant_batch(lambda: trainer.add_selected_hero_skill_points(amount), '增加英雄技能点')
        return f'已为 {len(results)} 个英雄增加 {amount} 点技能点{self.elephant_batch_suffix()}'

    def elephant_reset_ability(self) -> str:
        rawcode = self.view.value('elephant_reset_ability_rawcode').get().strip()
        if not rawcode:
            raise ValueError('请填写重置技能 ID')
        trainer = self.elephant_trainer()
        if getattr(trainer, '_native_selection_unavailable', False):
            result = trainer.ability_batch_24268(rawcode, 5, 0)
            return f'已核对 {result['count']} 个单位，重置技能 {rawcode} {result['changed']} 个'
        results = self.elephant_batch(lambda: trainer.reset_selected_unit_ability(rawcode), f'重置技能 {rawcode}')
        return f'已为 {len(results)} 个单位重置技能 {rawcode}{self.elephant_batch_suffix()}'

    def elephant_remove_all_abilities(self) -> str:
        trainer = self.elephant_trainer()
        if getattr(trainer, '_native_selection_unavailable', False):
            changed = trainer.remove_all_selected_unit_abilities()
            return f'已删除 {changed} 个非基础技能'
        results = self.elephant_batch(trainer.remove_all_selected_unit_abilities, '删除全部技能')
        return f'已从 {len(results)} 个单位删除 {sum(map(int, results))} 个非基础技能{self.elephant_batch_suffix()}'

    def elephant_move_to_mouse(self) -> str:
        count, x, y = self.elephant_trainer().move_selected_group_to_mouse()
        return f'已将 {count} 个单位移动到鼠标位置 ({x:g}, {y:g})'

    def elephant_add_standard_auras(self) -> str:
        from war3_services.ability_bundle import format_bundle_outcome
        entries = (('AHab', 3), ('AHad', 3), ('AOr2', 4), ('AUau', 3), ('AUav', 3), ('AEar', 3), ('AEah', 3), ('Aabr', None), ('ACac', None))
        trainer = self.elephant_trainer()
        if getattr(trainer, '_native_selection_unavailable', False):
            result = trainer.add_ability_bundle_to_selected_unit(entries)
            changed, total = result
            if getattr(result, 'failures', ()):
                return format_bundle_outcome('全光环', (result,), self.view.value('ui_language')['code'])
            return f'已批量处理全光环 {total} 项，实际修改 {changed} 项'
        results = self.elephant_batch(lambda: trainer.add_ability_bundle_to_selected_unit(entries), '添加全光环')
        if any((getattr(result, 'failures', ()) for result in results)):
            return format_bundle_outcome('全光环', results, self.view.value('ui_language')['code'])
        return f'已为 {len(results)} 个单位添加全光环{self.elephant_batch_suffix()}'

    def elephant_add_standard_passives(self) -> str:
        from war3_services.ability_bundle import format_bundle_outcome
        entries = (('AInv', None), ('AHbh', 3), ('AOcr', 3), ('Acdb', 4), ('ACce', None), ('ACes', None), ('ACrn', None), ('ACpv', None))
        trainer = self.elephant_trainer()
        if getattr(trainer, '_native_selection_unavailable', False):
            result = trainer.add_ability_bundle_to_selected_unit(entries)
            changed, total = result
            if getattr(result, 'failures', ()):
                return format_bundle_outcome('全被动', (result,), self.view.value('ui_language')['code'])
            return f'已批量处理全被动 {total} 项，实际修改 {changed} 项'
        results = self.elephant_batch(lambda: trainer.add_ability_bundle_to_selected_unit(entries), '添加全被动')
        if any((getattr(result, 'failures', ()) for result in results)):
            return format_bundle_outcome('全被动', results, self.view.value('ui_language')['code'])
        return f'已为 {len(results)} 个单位添加全被动{self.elephant_batch_suffix()}'

    def elephant_add_six_artifacts(self, plan=None) -> str:
        from war3_services.artifact_plan import apply_artifact_plan
        plan = self.view.value('artifact_plan_settings').snapshot() if plan is None else plan
        trainer = self.elephant_trainer()
        if getattr(trainer, '_native_selection_unavailable', False):
            changed = apply_artifact_plan(trainer, plan)
            return f'已批量处理六神器，实际写入 {changed} 个物品槽位'

        def add_artifacts() -> int:
            return apply_artifact_plan(trainer, plan)
        results = self.elephant_batch(add_artifacts, '添加六神器')
        return f'已为 {len(results)} 个单位写入 {sum(map(int, results))} 个神器槽位{self.elephant_batch_suffix()}'

    def elephant_create_all_items(self) -> str:
        total, created, _last_item = self.elephant_trainer().create_all_loaded_items()
        return f'已读取当前版本资源目录 {total} 个物品，成功创建 {created} 个'

    def elephant_apply_all_debuffs(self) -> str:
        trainer = self.elephant_trainer()
        if getattr(trainer, '_native_selection_unavailable', False):
            attempted, succeeded = trainer.apply_standard_debuffs_to_selected_unit()
            return f'已对当前选择执行减益 {succeeded}/{attempted} 次'
        results = self.elephant_batch(trainer.apply_standard_debuffs_to_selected_unit, '施加减益')
        attempted = sum((int(result[0]) for result in results))
        succeeded = sum((int(result[1]) for result in results))
        return f'已对 {len(results)} 个单位执行减益 {succeeded}/{attempted} 次{self.elephant_batch_suffix()}'

    def elephant_apply_all_buffs(self) -> str:
        trainer = self.elephant_trainer()
        if getattr(trainer, '_native_selection_unavailable', False):
            attempted, succeeded = trainer.apply_standard_buffs_to_selected_unit()
            return f'已对当前选择执行增益 {succeeded}/{attempted} 次'
        results = self.elephant_batch(trainer.apply_standard_buffs_to_selected_unit, '施加增益')
        attempted = sum((int(result[0]) for result in results))
        succeeded = sum((int(result[1]) for result in results))
        return f'已对 {len(results)} 个单位执行增益 {succeeded}/{attempted} 次{self.elephant_batch_suffix()}'

    def elephant_fullscreen_cast(self, action: Callable[[], tuple[int, int]], label: str) -> str:
        attempted, succeeded = action()
        if not succeeded:
            raise RuntimeError(f'游戏没有接受{label}命令')
        return f'{label}已执行 {succeeded}/{attempted} 次'

    def elephant_fullscreen_auto(self) -> str:
        count = parse_int(self.view.value('elephant_auto_effect_count').get(), '自动特效次数')
        if not 1 <= count <= 255:
            raise ValueError('自动特效次数必须在 1 到 255 之间')
        return self.elephant_fullscreen_cast(lambda: self.elephant_trainer().cast_fullscreen_auto_effect(success_limit=count), '全屏自动特效攻击')

    def elephant_create_reinforcement(self) -> str:
        rawcode = self.view.value('elephant_reinforcement_rawcode').get().strip()
        if not rawcode:
            raise ValueError('请填写增援单位 ID')
        unit_rawcode, handle = self.elephant_trainer().create_local_unit(rawcode)
        return f'已呼叫 {format_rawcode(unit_rawcode)}；handle=0x{handle:x}'

    def elephant_add_preset_item(self) -> str:
        rawcode = self.view.value('elephant_preset_item_rawcode').get().strip()
        if not rawcode:
            raise ValueError('请填写快捷物品 ID')
        trainer = self.elephant_trainer()
        if getattr(trainer, '_native_selection_unavailable', False):
            result = trainer.item_batch_24268(1, rawcode)
            return f'已向当前选择创建 {result['count']} 件物品：入包 {result['stored']} 件，落地 {result['ground']} 件'
        results = self.elephant_batch(lambda: trainer.add_item_to_selected_unit(rawcode), f'添加物品 {rawcode}')
        return f'已向 {len(results)} 个单位添加物品 {rawcode}{self.elephant_batch_suffix()}'

    def elephant_set_preset_tech(self) -> str:
        rawcode = self.view.value('elephant_preset_tech_rawcode').get().strip()
        if not rawcode:
            raise ValueError('请填写快捷科技 ID')
        actual = self.elephant_trainer().set_local_player_tech(rawcode, 1)
        return f'科技 {rawcode} 已设置为 {actual} 级'

    def elephant_set_game_paused(self, paused: bool) -> str:
        self.elephant_trainer().set_game_paused(paused)
        self.view.value('state')['elephant_game_paused'] = paused
        return '游戏已暂停' if paused else '游戏已恢复'

    def elephant_toggle_game_pause(self) -> str:
        return self.elephant_set_game_paused(not bool(self.view.value('state').get('elephant_game_paused')))

    def elephant_toggle_unit_pause(self) -> str:
        t = self.elephant_trainer()
        if getattr(t, '_native_selection_unavailable', False):
            paused = not t.is_selected_unit_paused()
            changed = t.set_selected_unit_paused(paused)
            return f'已{('暂停' if paused else '恢复')} {changed} 个单位'
        first_states = self.elephant_batch(t.is_selected_unit_paused, '读取暂停状态')
        paused = not bool(first_states[0])
        results = self.elephant_batch(lambda: t.set_selected_unit_paused(paused), '暂停选中单位' if paused else '恢复选中单位')
        return f'已{('暂停' if paused else '恢复')} {len(results)} 个单位{self.elephant_batch_suffix()}'

    def elephant_toggle_ally_health_lock(self) -> str:
        if self.view.value('state').get('ally_health_lock'):
            self.view.value('state')['ally_health_lock'] = False
            self.view.value('state')['ally_health_lock_trainer'] = None
            return '我方锁血已关闭'
        lock_trainer = self.elephant_trainer()
        healed = lock_trainer.heal_local_player_units()
        self.view.value('state')['ally_health_lock_trainer'] = lock_trainer
        self.view.value('state')['ally_health_lock'] = True
        return f'我方锁血已开启；首轮恢复 {healed} 个单位，AI 仍可正常攻击'

    def elephant_toggle_rapid_build(self) -> str:
        if self.view.value('state').get('rapid_build'):
            self.view.value('state')['rapid_build'] = False
            self.view.value('state')['rapid_build_trainer'] = None
            return '持续快速建造/升级已关闭'
        build_trainer = self.elephant_trainer()
        completed = build_trainer.complete_local_player_structures()
        self.view.value('state')['rapid_build_trainer'] = build_trainer
        self.view.value('state')['rapid_build'] = True
        return f'持续快速建造/升级已开启；首轮处理 {completed} 个建筑'

    def elephant_kill_owner_units(self) -> str:
        killed = self.elephant_trainer().kill_selected_owner_units()
        return f'已击杀该单位所属玩家的 {killed} 个单位'

    def elephant_action(self, action: Callable[[], None], message: str) -> str:
        action()
        return message

    def elephant_batch_action(self, action: Callable[[], object], label: str, *, direct_memory: bool=False) -> str:
        results = self.elephant_current_engine_batch(action, label)
        return f'{label}：成功 {len(results)} 个{self.elephant_batch_suffix()}'

    def extension_rawcode_value(self, rawcode: str) -> int:
        return int.from_bytes(rawcode.encode('ascii'), 'big')

    def populate_extension_snapshot(self, snapshot: dict) -> None:
        self.view.value('state')['extension_snapshot'] = snapshot
        self.view.value('extension_bag_tree').delete(*self.view.value('extension_bag_tree').get_children())
        self.view.value('extension_equipment_tree').delete(*self.view.value('extension_equipment_tree').get_children())
        self.view.value('extension_talent_tree').delete(*self.view.value('extension_talent_tree').get_children())
        bag_size = int(snapshot.get('bag_size', 0))
        bag_rows = tuple(snapshot.get('bag', ()))
        for row in bag_rows[:bag_size]:
            rawcode = int(row.get('rawcode', 0))
            self.view.value('extension_bag_tree').insert('', 'end', iid=f'bag:{row['slot']}', values=(int(row['slot']) + 1, format_rawcode(rawcode) if rawcode else '', int(row.get('charges', 0)) if rawcode else '', f'0x{int(row.get('handle', 0)):x}' if rawcode else ''))
        equipment_rows = tuple(snapshot.get('equipment', ()))
        for row in equipment_rows:
            slot = int(row['slot'])
            rawcode = int(row.get('rawcode', 0))
            self.view.value('extension_equipment_tree').insert('', 'end', iid=f'equipment:{slot}', values=(EQUIPMENT_SLOT_NAMES[slot], format_rawcode(rawcode) if rawcode else '', EQUIPMENT_TYPE_NAMES.get(int(row.get('equipment_type', 0)), '') if rawcode else '', int(row.get('charges', 0)) if rawcode else '', f'0x{int(row.get('handle', 0)):x}' if rawcode else ''))
        ability_levels = {int(rawcode): int(level) for rawcode, level in dict(snapshot.get('abilities', {})).items()}
        talent_state = self.trainer().talent_state_24268(snapshot)
        active_controllers = []
        if talent_state['controller']:
            active_controllers.append(f'{talent_state['name']} {talent_state['controller']}/{talent_state['controller_level']}；点数 {talent_state['remaining_points']}/{talent_state['total_points']}')
            for row in talent_state['tiers']:
                self.view.value('extension_talent_tree').insert('', 'end', iid=f'talent:{talent_state['controller']}:{int(row['index'])}', values=(talent_state['name'], int(row['index']) + 1, ' / '.join((f'{('[原生已选] ' if choice == row.get('native_choice', '') else '')}{('[能力已添加] ' if choice in row.get('selected', ()) and choice != row.get('native_choice', '') else '')}{choice} {row.get('labels', {}).get(choice, '')}'.strip() for choice in row['choices'])), f'原生选择：{row.get('native_choice')}；能力：{' / '.join(row['selected']) or '无'}' if row.get('native_choice') else ' / '.join(row['selected'])))
        elif talent_state['anomalies']:
            active_controllers.append('；'.join(talent_state['anomalies']))
        occupied_bag = sum((bool(int(row.get('rawcode', 0))) for row in bag_rows[:bag_size]))
        occupied_equipment = sum((bool(int(row.get('rawcode', 0))) for row in equipment_rows))
        controller_text = '，'.join(active_controllers) if active_controllers else '未检测到官方天赋控制器'
        self.view.value('extension_status').set(f'扩展背包 {occupied_bag}/{bag_size}；装备 {occupied_equipment}/9；{controller_text}')
        names = tuple((str(value) for value in snapshot.get('loadout_names', ())))
        try:
            self.view.value('extension_loadout_box')['values'] = names
            if self.view.value('extension_loadout_choice').get() not in names:
                self.view.value('extension_loadout_choice').set(names[-1] if names else '')
        except NameError:
            pass

    def refresh_extension_snapshot(self) -> str:
        snapshot = self.trainer().extension_snapshot_24268()
        self.view.value('root').after(0, self.populate_extension_snapshot, snapshot)
        return '已读取 3.0 扩展背包、装备和天赋状态'

    def extension_add_item(self) -> str:
        rawcode = self.view.value('extension_item_rawcode').get().strip()
        if not rawcode:
            raise ValueError('请填写物品 ID')
        trainer_obj = self.trainer()
        snapshot = trainer_obj.add_extension_item_24268(rawcode)
        self.view.value('root').after(0, self.populate_extension_snapshot, snapshot)
        if snapshot.get('operation_skipped'):
            return snapshot['operation_skipped']['reason']
        return f'已添加物品 {rawcode} 并刷新 3.0 扩展状态'

    def extension_selected_bag_slot(self) -> int:
        selected = self.view.value('extension_bag_tree').selection()
        if not selected or not str(selected[0]).startswith('bag:'):
            raise ValueError('请先选择一个扩展背包物品')
        return int(str(selected[0]).split(':', 1)[1])

    def extension_set_bag_charges(self) -> str:
        slot = self.extension_selected_bag_slot()
        charges = parse_int(self.view.value('extension_item_charges').get().strip(), '物品数量')
        snapshot = self.trainer().set_extension_bag_charges_24268(slot, charges)
        self.view.value('root').after(0, self.populate_extension_snapshot, snapshot)
        return f'已将扩展背包第 {slot + 1} 格数量设置为 {charges} 并读回验证'

    def extension_duplicate_bag_item(self) -> str:
        slot = self.extension_selected_bag_slot()
        snapshot = self.trainer().duplicate_extension_bag_item_24268(slot)
        self.view.value('root').after(0, self.populate_extension_snapshot, snapshot)
        if snapshot.get('operation_skipped'):
            return snapshot['operation_skipped']['reason']
        return f'已复制扩展背包第 {slot + 1} 格物品及其数量'

    def extension_drop_bag_item(self) -> str:
        slot = self.extension_selected_bag_slot()
        snapshot = self.trainer().drop_extension_bag_item_24268(slot)
        self.view.value('root').after(0, self.populate_extension_snapshot, snapshot)
        if snapshot.get('operation_skipped'):
            return snapshot['operation_skipped']['reason']
        return f'已将扩展背包第 {slot + 1} 格物品丢到角色脚下'

    def extension_repair_bag_item(self) -> str:
        slot = self.extension_selected_bag_slot()
        snapshot = self.trainer().repair_extension_bag_item_24268(slot)
        self.view.value('root').after(0, self.populate_extension_snapshot, snapshot)
        if snapshot.get('operation_skipped'):
            return snapshot['operation_skipped']['reason']
        return self.view.value('ui_text')('物品原生状态已验证，物品仍保留在背包中')

    def extension_repair_equipment_state(self) -> str:
        snapshot = self.trainer().repair_extension_equipment_state_24268()
        self.view.value('root').after(0, self.populate_extension_snapshot, snapshot)
        result = snapshot['equipment_state_repair']
        return self.view.value('ui_text')('装备状态原位修复完成：') + str(len(result['repaired'])) + self.view.value('ui_text')(' 件已修复，') + str(len(result['skipped'])) + self.view.value('ui_text')(' 件无需修复；原装备槽和数量保持不变')

    def extension_add_backpack_equipment(self) -> str:
        label = self.view.value('extension_backpack_choice').get().strip()
        rawcode = self.view.value('official_backpack_by_label').get(label)
        if rawcode is None:
            raise ValueError('请选择一件 3.0 官方背包装备')
        hero_name, controller = OFFICIAL_BACKPACKS[rawcode]
        snapshot = self.trainer().add_official_backpack_24268(rawcode)
        self.view.value('root').after(0, self.populate_extension_snapshot, snapshot)
        diagnostic = snapshot.get('backpack_interface', {})
        if diagnostic.get('operation_trace', {}).get('log_errors'):
            return self.view.value('ui_text')('背包能力已读回，但诊断日志写入未完成；请检查日志目录。')
        return f'已将{hero_name}官方背包装备（{rawcode}/{controller}）放入经典物品栏第 1 格'

    def extension_selected_equipment_slot(self) -> int:
        selected = self.view.value('extension_equipment_tree').selection()
        if not selected or not str(selected[0]).startswith('equipment:'):
            raise ValueError('请先选择一个装备槽')
        return int(str(selected[0]).split(':', 1)[1])

    def extension_unequip_item(self) -> str:
        slot = self.extension_selected_equipment_slot()
        snapshot = self.trainer().unequip_extension_slot_24268(slot)
        self.view.value('root').after(0, self.populate_extension_snapshot, snapshot)
        if snapshot.get('operation_skipped'):
            return snapshot['operation_skipped']['reason']
        return f'已卸下{EQUIPMENT_SLOT_NAMES[slot]}装备并验证槽位'

    def extension_equip_bag_to_slot(self) -> str:
        bag_slot = self.extension_selected_bag_slot()
        equipment_slot = self.extension_selected_equipment_slot()
        snapshot = self.trainer().equip_extension_bag_item_to_slot_24268(bag_slot, equipment_slot)
        self.view.value('root').after(0, self.populate_extension_snapshot, snapshot)
        if snapshot.get('operation_skipped'):
            return snapshot['operation_skipped']['reason']
        sync = snapshot.get('equipment_effect_sync', {})
        sync_status = sync.get('status') if isinstance(sync, dict) else 'unavailable'
        if sync_status == 'native_applied' and sync.get('verified'):
            return f'已将扩展背包第 {bag_slot + 1} 格物品原生装入{EQUIPMENT_SLOT_NAMES[equipment_slot]}槽；已验证物品能力挂载，卸下时会通过原生链路撤销效果'
        if sync_status == 'failed':
            from war3_error_messages import format_error
            refresh_error = RuntimeError(str(sync.get('reason', '')))
            refresh_error.report = sync.get('execution_report') or {}
            try:
                refresh_error.diagnostic_log_path = record_operation_failure(self.trainer().pid, 'equipment_effect_refresh', refresh_error)
            except Exception as log_error:
                refresh_error.log_write_error = repr(log_error)
            return f'已放入{EQUIPMENT_SLOT_NAMES[equipment_slot]}槽，但装备效果刷新未确认；' + format_error(refresh_error, self.view.value('ui_language')['code'])
        if sync_status == 'no_stat_source':
            effect_text = '当前单位没有可读的 3.0 属性控制器，效果只能由游戏自身链路确认'
        elif sync_status == 'refreshed':
            effect_text = '已触发原生属性控制器刷新并完成属性读回'
        elif sync_status == 'no_effect_source':
            effect_text = '槽位已读回；当前物品没有可挂载的 3.0 装备能力'
        elif sync_status == 'effect_already_present':
            effect_text = '槽位已读回；该能力在单位上已有其他来源，未重复计算'
        else:
            effect_text = '装备效果刷新状态未提供'
        return f'已将扩展背包第 {bag_slot + 1} 格物品放入{EQUIPMENT_SLOT_NAMES[equipment_slot]}槽；{effect_text}'

    def extension_enable_any_slot(self) -> str:
        snapshot = self.trainer().set_extension_equipment_any_slot_24268(True)
        self.view.value('root').after(0, self.populate_extension_snapshot, snapshot)
        return '已开启当前单位任意装备槽；有脚本冲突风险的旧式物品会跳过'

    def extension_save_loadout(self) -> str:
        name = self.view.value('extension_loadout_name').get().strip()
        trainer_obj = self.trainer()
        trainer_obj._extension_pending_loadout_name = name
        snapshot = trainer_obj.save_extension_loadout_24268()
        names = tuple(snapshot.get('loadout_names', ()))
        self.view.value('extension_loadout_choice').set(name or (names[-1] if names else ''))
        self.view.value('extension_loadout_box')['values'] = names
        self.view.value('root').after(0, self.populate_extension_snapshot, snapshot)
        return f'已保存套装“{name or (names[-1] if names else '')}”，共 {len(names)} 套'

    def extension_restore_loadout(self) -> str:
        name = self.view.value('extension_loadout_choice').get().strip()
        trainer_obj = self.trainer()
        trainer_obj._extension_pending_restore_name = name
        snapshot = trainer_obj.restore_extension_loadout_24268()
        self.view.value('root').after(0, self.populate_extension_snapshot, snapshot)
        if snapshot.get('loadout_charge_mismatches') or snapshot.get('loadout_postcondition_warning'):
            return '套装装备位置已核对，物品已保留；部分数量或效果刷新需要检查，请查看恢复详情'
        batch = snapshot.get('loadout_batch')
        if batch is not None:
            summary = f'已对选中英雄恢复所选套装 {len(batch.get('restored', ()))} 个；跳过 {len(batch.get('skipped', ()))} 个，失败 {len(batch.get('failures', ()))} 个'
            summary += f'；跳过物品 {len(batch.get('item_skips', ()))} 件'
            failures = tuple(batch.get('failures', ()))
            if failures:
                from war3_error_messages import loadout_batch_error
                raise loadout_batch_error(summary, batch)
            return summary + __import__('war3_error_messages').summarize_skips(snapshot, self.view.value('ui_language')['code'])
        item_skips = snapshot.get('loadout_item_skips', ())
        if item_skips:
            return f'套装恢复已完成，跳过 {len(item_skips)} 件不兼容物品，其余已读回验证' + __import__('war3_error_messages').summarize_skips(snapshot, self.view.value('ui_language')['code'])
        return f'已重新生成并恢复套装“{name or '唯一套装'}”，并逐槽验证物品实例和数量'

    def extension_save_all_loadouts(self) -> str:
        name = self.view.value('extension_loadout_name').get().strip()
        snapshot = self.trainer().save_extension_loadouts_for_selected_24268(name)
        self.view.value('root').after(0, self.populate_extension_snapshot, snapshot)
        batch = snapshot.get('loadout_batch', {})
        summary = f'已保存选中英雄套装 {len(batch.get('saved', ()))} 个；跳过 {len(batch.get('skipped', ()))} 个，失败 {len(batch.get('failures', ()))} 个'
        summary += f'；跳过物品 {len(batch.get('item_skips', ()))} 件'
        failures = tuple(batch.get('failures', ()))
        if failures:
            from war3_error_messages import loadout_batch_error
            raise loadout_batch_error(summary, batch)
        return summary + __import__('war3_error_messages').summarize_skips(snapshot, self.view.value('ui_language')['code'])

    def extension_restore_all_loadouts(self) -> str:
        name = self.view.value('extension_loadout_choice').get().strip()
        snapshot = self.trainer().restore_extension_loadouts_for_selected_24268(name)
        self.view.value('root').after(0, self.populate_extension_snapshot, snapshot)
        batch = snapshot.get('loadout_batch', {})
        summary = f'已恢复匹配的选中英雄套装 {len(batch.get('restored', ()))} 个；跳过 {len(batch.get('skipped', ()))} 个，失败 {len(batch.get('failures', ()))} 个'
        summary += f'；跳过物品 {len(batch.get('item_skips', ()))} 件'
        failures = tuple(batch.get('failures', ()))
        if failures:
            from war3_error_messages import loadout_batch_error
            raise loadout_batch_error(summary, batch)
        return summary + __import__('war3_error_messages').summarize_skips(snapshot, self.view.value('ui_language')['code'])

    def extension_export_plans(self) -> None:
        from war3_loadout_storage import save_file
        path = self.view.value('filedialog').asksaveasfilename(parent=self.view.value('root'), title='保存装备方案文件', defaultextension='.json', filetypes=[('JSON', '*.json')])
        if path:
            self.call_async(lambda: f'已保存装备方案文件：{save_file(self.trainer(), path)}')

    def extension_import_plans(self) -> None:
        from war3_loadout_storage import load_file
        path = self.view.value('filedialog').askopenfilename(parent=self.view.value('root'), title='选择装备方案文件', filetypes=[('JSON', '*.json')])
        if not path:
            return

        def load() -> str:
            obj = self.trainer()
            count = load_file(obj, path)
            names = obj.extension_loadout_names_24268()

            def update() -> None:
                self.view.value('extension_loadout_box')['values'] = names
                self.view.value('extension_loadout_choice').set(names[0] if names else '')
            self.view.value('root').after(0, update)
            return f'已读取装备方案文件：{count}'
        self.call_async(load)

    def extension_audit_equipment(self, repair: bool=False) -> str:
        result = self.trainer().audit_extension_equipment_24268(repair)
        self.view.value('root').after(0, self.populate_extension_snapshot, result['snapshot'])
        if result['repaired']:
            return '已卸下并复核错槽装备：' + '、'.join((EQUIPMENT_SLOT_NAMES[slot] for slot in result['repaired']))
        if result['issues']:
            return '检测到装备结构异常：' + '；'.join(result['issues'])
        return '装备实例、槽位类型及背包重叠检查均正常'

    def extension_reset_talents(self) -> str:
        return self.extension_talent_batch_result(self.trainer().selected_talent_batch_24268('reset'))

    def extension_talent_batch_result(self, result: dict) -> str:
        self.view.value('root').after(0, self.populate_extension_snapshot, result['snapshot'])
        text = f'天赋操作：成功 {result['succeeded']}，跳过 {result['skipped']}，失败 {result['failed']}'
        errors = [f'0x{row['target']:x}：{row['reason']}' for row in result['results'] if row['status'] == 'failed']
        if errors:
            error=RuntimeError(text + '；' + '；'.join(errors))
            error.report={'operation':'talent_batch','batch_failures':tuple(
                row['explanation'] for row in result['results'] if row['status']=='failed' and row.get('explanation'))}
            raise error
        return text

    def extension_selected_talent_tier(self) -> int:
        selected = self.view.value('extension_talent_tree').selection()
        if not selected or not str(selected[0]).startswith('talent:'):
            raise ValueError('请先选择一个天赋层')
        return int(str(selected[0]).rsplit(':', 1)[1])

    def extension_talent_tree_selected(self, _event=None) -> None:
        selected = self.view.value('extension_talent_tree').selection()
        if not selected or not str(selected[0]).startswith('talent:'):
            self.view.value('extension_talent_choice').set('')
            self.view.value('extension_talent_choice_box')['values'] = ()
            return
        row = self.view.value('extension_talent_tree').item(selected[0], 'values')
        choices = tuple((str(value).strip() for value in str(row[2]).split('/') if str(value).strip()))
        choices = tuple((value.split(' ', 1)[0] for value in choices))
        self.view.value('extension_talent_choice_box')['values'] = choices
        if choices and self.view.value('extension_talent_choice').get() not in choices:
            self.view.value('extension_talent_choice').set(choices[0])

    def extension_add_talent_choice(self) -> str:
        selected = self.view.value('extension_talent_tree').selection()
        if not selected or not str(selected[0]).startswith('talent:'):
            raise ValueError('请先选择一个天赋层')
        parts = str(selected[0]).split(':')
        controller, tier = (parts[1], int(parts[2]))
        choice = self.view.value('extension_talent_choice').get().strip()
        if not choice:
            raise ValueError('请先选择一个天赋选项')
        return self.extension_talent_batch_result(self.trainer().selected_talent_batch_24268('choice', controller, tier, choice))

    def extension_refresh_talent_icons(self) -> str:
        result = self.trainer().refresh_talent_icon_display_24268()
        if not result.get('installed'):
            if result.get('reason') in ('window_minimized', 'window_unavailable'):
                raise RuntimeError(str(result['error']))
            if result.get('reason') == 'code_unavailable':
                raise RuntimeError('天赋界面代码尚未解码，图标刷新未执行；请保持游戏天赋页可见后重试')
            if result.get('reason') == 'cleanup_uncertain':
                raise RuntimeError(str(result['error']))
            raise RuntimeError('天赋图标模块安装失败：' + str(result.get('error', '未知原因')))
        return '天赋图标显示模块已安装并读回'

    def extension_drop_clicked(self) -> None:
        try:
            slot = self.extension_selected_bag_slot()
        except Exception as exc:
            self.view.value('messagebox').showerror(self.view.value('ui_text')('错误'), __import__('war3_error_messages').format_error(exc, self.view.value('ui_language')['code']))
            return
        if self.view.value('messagebox').askyesno('确认丢弃', f'把扩展背包第 {slot + 1} 格物品丢到角色脚下？'):
            self.call_async(self.extension_drop_bag_item)

    def extension_destroy_clicked(self, area: str) -> None:
        try:
            slot = self.extension_selected_bag_slot() if area == 'bag' else self.extension_selected_equipment_slot()
        except Exception as exc:
            self.view.value('messagebox').showerror(self.view.value('ui_text')('错误'), __import__('war3_error_messages').format_error(exc, self.view.value('ui_language')['code']))
            return

        def prepare() -> str:
            target = self.trainer()
            expected = target.prepare_extension_item_destruction_24268(area, slot)
            code = expected['item'].rawcode.to_bytes(4, 'big').decode('ascii', 'replace')

            def confirm() -> None:
                if self.view.value('state').get('closing'):
                    return
                prompt = f'永久销毁物品 {code}？物品及其效果将被移除，不能撤销。' if self.view.value('ui_language')['code'] != 'en' else f'Permanently destroy item {code}? The item and its effects will be removed. This cannot be undone.'
                if self.view.value('messagebox').askyesno(self.view.value('ui_text')('确认销毁'), prompt, parent=self.view.value('root')):

                    def execute() -> str:
                        snapshot = target.destroy_extension_item_24268(area, slot, expected=expected)
                        self.view.value('root').after(0, self.populate_extension_snapshot, snapshot)
                        return f'已销毁 {code}，物品对象及槽位引用已验证清理' if self.view.value('ui_language')['code'] != 'en' else f'Destroyed {code}; object retirement and inventory cleanup were verified'
                    self.call_async(execute, operation_key='extension_destroy')
            self.view.value('root').after(0, confirm)
            return self.view.value('ui_text')('等待确认销毁')
        self.call_async(prepare, operation_key='extension_destroy_prepare')

    def extension_reset_talents_clicked(self) -> None:
        if self.view.value('messagebox').askyesno('确认洗点', '对全部选中单位执行洗点；没有天赋控制器的单位自动跳过？'):
            self.call_async(self.extension_reset_talents)

    def extension_repair_equipment_clicked(self) -> None:
        if self.view.value('messagebox').askyesno('确认修复', '卸下所有类型与槽位不匹配的装备？'):
            self.call_async(lambda: self.extension_audit_equipment(True))

    def extension_grant_talent_point(self) -> str:
        return self.extension_talent_batch_result(self.trainer().selected_talent_batch_24268('grant'))

    def elephant_set_stat_detail(self, key: str) -> str:
        variable = self.view.value('elephant_stat_values')[key]
        value = parse_float(variable.get(), '属性目标值')
        field_key = {'hp_regen': 'hp_regen', 'mp_regen': 'mp_regen', 'attack_speed': 'attack1_true_speed'}.get(key, f'stat3_{key}')
        written = self.elephant_trainer().write_selected_unit_field(field_key, value)
        self.view.value('root').after(0, variable.set, f'{float(written.value):g}')
        return f'已设置 {written.label}={float(written.value):g}'

    def send_cheat_command(self, command_name: str, message: str) -> str:
        t = self.trainer()
        command = t.CHEATS.get(command_name)
        if not command:
            raise RuntimeError(f'未找到秘籍：{command_name}')
        t.send_cheat(command)
        return message

    def trigger_elephant_hotkey(self, name: str) -> None:
        callback = self.view.value('hotkey_callbacks').get(name)
        spec = self.view.value('hotkey_specs_by_name').get(name)
        if callback is None or spec is None:
            return
        if name == 'six_artifacts':
            self.view.value('artifact_plan_panel').apply_clicked()
            return
        self.call_async(callback, f'elephant:hotkey:{name}', busy_text=f'正在执行 {spec.label}...')

    def on_global_hotkey(self, name: str) -> None:
        try:
            self.view.value('root').after(0, self.trigger_elephant_hotkey, name)
        except RuntimeError:
            pass

    def refresh_elephant_hotkeys(self) -> None:
        if not self.view.value('elephant_hotkeys_enabled').get():
            self.view.value('hotkey_manager').stop()
            self.view.value('elephant_hotkey_status').set('快捷键未启用')
            return
        enabled_specs = tuple((spec for spec in ELEPHANT_HOTKEY_SPECS if spec.name in self.view.value('hotkey_callbacks') and self.view.value('elephant_hotkey_checks')[spec.name].get()))
        errors = self.view.value('hotkey_manager').start(enabled_specs, self.on_global_hotkey)
        registered = len(self.view.value('hotkey_manager').registered_names)
        fallback_names = self.view.value('hotkey_manager').fallback_names
        unresolved_errors = {name: error for name, error in errors.items() if name not in fallback_names}
        active_count = registered + len(fallback_names)
        if unresolved_errors:
            conflict_details = '、'.join((f'{self.view.value('hotkey_specs_by_name')[name].label.split('  ', 1)[0]}（WinError {error}）' for name, error in unresolved_errors.items()))
            self.view.value('elephant_hotkey_status').set(f'已启用 {active_count} 个，冲突 {len(unresolved_errors)} 个：{conflict_details}')
        elif fallback_names:
            fallback_labels = '、'.join((self.view.value('hotkey_specs_by_name')[name].label.split('  ', 1)[0] for name in fallback_names))
            self.view.value('elephant_hotkey_status').set(f'已启用 {active_count} 个（兼容监听：{fallback_labels}）')
        else:
            self.view.value('elephant_hotkey_status').set(f'已注册 {registered} 个全局快捷键')
        self.set_status(self.view.value('elephant_hotkey_status').source_text())

    def set_all_elephant_hotkeys(self, enabled: bool) -> None:
        for name, variable in self.view.value('elephant_hotkey_checks').items():
            variable.set(bool(enabled and name in self.view.value('hotkey_callbacks')))
        if self.view.value('elephant_hotkeys_enabled').get():
            self.refresh_elephant_hotkeys()

    def confirm_elephant_action(self, title: str, prompt: str, fn: Callable[[], str]) -> None:
        if self.view.value('messagebox').askyesno(self.view.value('ui_text')(title), self.view.value('ui_text')(prompt), parent=self.view.value('root')):
            self.call_async(fn, f'elephant:{title}')

    def refresh_id_catalog_tree(self, kind: str) -> None:
        tree = self.view.value('id_catalog_trees').get(kind)
        if tree is None:
            return
        selected = tuple(tree.selection())
        tree.delete(*tree.get_children())
        entries = search_id_entries(kind, self.view.value('id_catalog_queries')[kind].get())
        for entry in entries:
            category = entry.category_zh if self.view.value('ui_language')['code'] == 'zh' else entry.category_en
            tree.insert('', 'end', iid=entry.rawcode, values=(entry.rawcode, entry.name_zh, entry.name_en, category))
        for iid in selected:
            if tree.exists(iid):
                tree.selection_add(iid)
        self.view.value('id_catalog_statuses')[kind].set(f'记录数：{len(entries)}')

    def clear_id_catalog_search(self, kind: str) -> None:
        self.view.value('id_catalog_queries')[kind].set('')
        self.refresh_id_catalog_tree(kind)

    def copy_selected_catalog_id(self, kind: str) -> None:
        tree = self.view.value('id_catalog_trees')[kind]
        selected = tree.selection()
        if not selected:
            self.view.value('messagebox').showerror(self.view.value('ui_text')('错误'), self.view.value('ui_text')('请先在 ID 表格里选择一项'), parent=self.view.value('root'))
            return
        rawcode = str(selected[0])
        self.view.value('root').clipboard_clear()
        self.view.value('root').clipboard_append(rawcode)
        self.set_status(f'已复制 ID：{rawcode}')

    def copy_catalog_id_from_event(self, kind: str, event: object) -> None:
        tree = self.view.value('id_catalog_trees')[kind]
        row_id = tree.identify_row(getattr(event, 'y', 0))
        if not row_id:
            return
        tree.selection_set(row_id)
        tree.focus(row_id)
        self.copy_selected_catalog_id(kind)

    def resize_hotkey_body(self, event) -> None:
        self.view.value('hotkey_canvas').itemconfigure(self.view.value('hotkey_window'), width=event.width)

    def update_hotkey_scrollregion(self, _event=None) -> None:
        self.view.value('hotkey_canvas').configure(scrollregion=self.view.value('hotkey_canvas').bbox('all'))

    def finish_initial_connect(self, message: str | None, exc: Exception | None) -> None:
        self.view.value('state')['initial_connect_busy'] = False
        if self.view.value('state').get('closing'):
            return
        if exc is not None:
            self.set_status(f'等待 Warcraft III 启动：{exc}')
            self.view.value('root').after(1000, self.init)
            return
        self.set_status(message or '已连接 Warcraft III')
        self.view.value('root').after(300, lambda: self.call_async(self.prewarm_selection_cache, busy_text='正在预热，请稍候...'))

    def init(self) -> None:
        if self.view.value('state').get('closing') or self.view.value('state').get('initial_connect_busy'):
            return
        self.view.value('state')['initial_connect_busy'] = True
        self.set_status('正在连接 Warcraft III...')

        def worker() -> None:
            try:
                with self.view.value('operation_lock'):
                    message = self.connect()
                    try:
                        self.refresh_resources()
                    except Exception:
                        pass
            except Exception as exc:
                self.view.value('root').after(0, self.finish_initial_connect, None, exc)
            else:
                self.view.value('root').after(0, self.finish_initial_connect, message, None)
        try:
            self.start_operation_thread(worker, 'war3-initial-connect')
        except Exception:
            self.view.value('state')['initial_connect_busy'] = False
            raise

    def hotkey_actions(self):
        return {'read_unit': self.read_unit_with_sound, 'hero_level': self.elephant_set_hero_level, 'instant_move': self.elephant_move_to_mouse, 'explode_unit': lambda: self.elephant_batch_action(self.elephant_trainer().explode_selected_unit, '爆炸选中单位'), 'reveal_map': lambda: self.elephant_action(lambda: self.elephant_trainer().set_map_revealed(True), '全地图视野已开启'), 'hide_map': lambda: self.elephant_action(lambda: self.elephant_trainer().set_map_revealed(False), '战争迷雾已恢复'), 'invulnerable': lambda: self.elephant_batch_action(lambda: self.elephant_trainer().set_selected_unit_invulnerable(True), '设置选中单位无敌'), 'vulnerable': lambda: self.elephant_batch_action(lambda: self.elephant_trainer().set_selected_unit_invulnerable(False), '取消选中单位无敌'), 'reset_cooldown': lambda: self.elephant_batch_action(self.elephant_trainer().reset_selected_unit_cooldown, '重置选中单位冷却'), 'clone_to_self': lambda: self.elephant_create_unit(True), 'duplicate_inventory': self.elephant_duplicate_inventory, 'unit_scale': self.elephant_set_scale, 'item_charges': self.elephant_set_inventory_charges, 'drop_inventory': self.elephant_drop_inventory, 'add_ability': self.elephant_add_ability, 'clone_unit': lambda: self.elephant_create_unit(True, preserve_owner=True), 'take_control': lambda: self.elephant_batch_action(self.elephant_trainer().take_selected_unit_control, '取得选中单位控制权'), 'add_resources': self.elephant_add_resources, 'mass_clone': self.elephant_mass_clone, 'ability_level': self.elephant_set_ability_level, 'remove_ability': self.elephant_remove_ability, 'all_auras': self.elephant_add_standard_auras, 'all_passives': self.elephant_add_standard_passives, 'six_artifacts': self.elephant_add_six_artifacts, 'reinforcements': self.elephant_create_reinforcement, 'preset_item': self.elephant_add_preset_item, 'preset_tech': self.elephant_set_preset_tech, 'create_all_items': self.elephant_create_all_items, 'ignore_collision': lambda: self.elephant_batch_action(lambda: self.elephant_trainer().set_selected_unit_pathing(False), '关闭选中单位碰撞'), 'hero_attributes': self.elephant_set_hero_attributes, 'skill_points': self.elephant_add_skill_points, 'kill_owner_units': self.elephant_kill_owner_units, 'xp_rate': self.elephant_set_xp_rate, 'game_speed': self.elephant_toggle_game_speed, 'reset_ability': self.elephant_reset_ability, 'all_debuffs': self.elephant_apply_all_debuffs, 'all_buffs': self.elephant_apply_all_buffs, 'fullscreen_swarm': lambda: self.elephant_fullscreen_cast(self.elephant_trainer().cast_fullscreen_swarm, '全屏腐臭蜂群'), 'fullscreen_clap': lambda: self.elephant_fullscreen_cast(self.elephant_trainer().cast_fullscreen_clap, '全屏雷霆一击'), 'fullscreen_monsoon': lambda: self.elephant_fullscreen_cast(self.elephant_trainer().cast_fullscreen_monsoon, '全屏季风'), 'fullscreen_starfall': lambda: self.elephant_fullscreen_cast(self.elephant_trainer().cast_fullscreen_starfall, '全屏群星陨落'), 'fullscreen_forked': lambda: self.elephant_fullscreen_cast(self.elephant_trainer().cast_fullscreen_forked_lightning, '全屏叉状闪电'), 'fullscreen_auto': self.elephant_fullscreen_auto, 'toggle_unit_pause': self.elephant_toggle_unit_pause, 'toggle_game_pause': self.elephant_toggle_game_pause, 'end_game': lambda: self.elephant_action(lambda: self.elephant_trainer().end_current_game(True), '已结束当前游戏'), 'remove_all_abilities': self.elephant_remove_all_abilities, 'ally_health_lock': self.elephant_toggle_ally_health_lock, 'allied_cooldowns': lambda: f'已重置我方 {self.elephant_trainer().reset_local_player_unit_cooldowns()} 个单位的技能冷却', 'rapid_build': self.elephant_toggle_rapid_build, 'instant_victory': lambda: self.send_cheat_command('直接胜利', '直接胜利指令已发送'), **{f'stat_{key}': lambda stat_key=key: self.elephant_set_stat_detail(stat_key) for key in self.view.value('elephant_stat_values')}}

    def ui_reveal_map(self):
        return self.call_async(lambda: self.elephant_action(lambda: self.elephant_trainer().set_map_revealed(True), '全地图视野已开启'))

    def ui_hide_map(self):
        return self.call_async(lambda: self.elephant_action(lambda: self.elephant_trainer().set_map_revealed(False), '战争迷雾已恢复'))

    def ui_peace_on(self):
        return self.confirm_elephant_action('和平模式', '将全部玩家设置为互相结盟，确定继续？', lambda: f'和平模式已开启，共更新 {self.elephant_trainer().set_peace_mode(True)} 项联盟关系')

    def ui_peace_off(self):
        return self.confirm_elephant_action('关闭和平', '这会取消全部玩家之间的被动联盟，确定继续？', lambda: f'和平模式已关闭，共更新 {self.elephant_trainer().set_peace_mode(False)} 项联盟关系')

    def ui_end_game(self):
        return self.confirm_elephant_action('结束游戏', '当前对局会立即结束，确定继续？', lambda: self.elephant_action(lambda: self.elephant_trainer().end_current_game(True), '已结束当前游戏'))

    def ui_invulnerable(self):
        return self.call_async(lambda: self.elephant_batch_action(lambda: self.elephant_trainer().set_selected_unit_invulnerable(True), '设置选中单位无敌'))

    def ui_vulnerable(self):
        return self.call_async(lambda: self.elephant_batch_action(lambda: self.elephant_trainer().set_selected_unit_invulnerable(False), '取消选中单位无敌'))

    def ui_reset_cooldown(self):
        return self.call_async(lambda: self.elephant_batch_action(self.elephant_trainer().reset_selected_unit_cooldown, '重置选中单位冷却'))

    def ui_pathing_off(self):
        return self.call_async(lambda: self.elephant_batch_action(lambda: self.elephant_trainer().set_selected_unit_pathing(False), '关闭选中单位碰撞'))

    def ui_pathing_on(self):
        return self.call_async(lambda: self.elephant_batch_action(lambda: self.elephant_trainer().set_selected_unit_pathing(True), '开启选中单位碰撞'))

    def ui_pause_unit(self):
        return self.call_async(lambda: self.elephant_batch_action(lambda: self.elephant_trainer().set_selected_unit_paused(True), '暂停选中单位'))

    def ui_resume_unit(self):
        return self.call_async(lambda: self.elephant_batch_action(lambda: self.elephant_trainer().set_selected_unit_paused(False), '恢复选中单位'))

    def ui_take_control(self):
        return self.call_async(lambda: self.elephant_batch_action(self.elephant_trainer().take_selected_unit_control, '取得选中单位控制权'))

    def ui_kill_unit(self):
        return self.confirm_elephant_action('击杀单位', '确定击杀当前选中单位？', lambda: self.elephant_batch_action(self.elephant_trainer().kill_selected_unit, '击杀选中单位'))

    def ui_explode_unit(self):
        return self.confirm_elephant_action('爆炸单位', '确定让当前选中单位爆炸死亡？', lambda: self.elephant_batch_action(self.elephant_trainer().explode_selected_unit, '爆炸选中单位'))

    def ui_remove_unit(self):
        return self.confirm_elephant_action('删除单位', '单位会从地图中直接删除，确定继续？', lambda: self.elephant_batch_action(self.elephant_trainer().remove_selected_unit, '删除选中单位'))
