"""Comprehensive, Zero-Mock Desktop Bridge connecting Web UI to TrainerApplication and DesktopServices."""
from __future__ import annotations

import os
import sys
import json
import logging
import threading
import inspect
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from war3_metadata import APP_VERSION, PRODUCT_EDITION_LABEL
from war3_app import desktop_services
from war3_application import TrainerApplication
from war3_webview_viewport import WebStateViewPort, VirtualTree, VirtualControl
from war3_artifact_plan import (
    ArtifactPlanStore,
    DEFAULT_ARTIFACT_CODES,
    ArtifactPlanError,
)
from war3_id_catalog import CATALOG_COUNTS, search_id_entries, upgrade_max_level
from war3_field_labels import ability_field_search_text, item_field_search_text
from war3_new_equipment_catalog import EQUIPMENT


_failure_cache = ContextVar('desktop_failure_cache', default=None)

_ACTION_TITLES = {
    'execute_elephant_action': {
        'reveal_map':'开启全图视野','hide_map':'恢复迷雾','pause_game':'暂停游戏','resume_game':'继续游戏',
        'peace_on':'开启和平','peace_off':'关闭和平','end_game':'结束游戏',
        'hero_level_read':'读取英雄等级','hero_level_set':'修改英雄等级','invulnerable':'设为无敌',
        'vulnerable':'取消无敌','reset_cooldown':'重置冷却','collision_off':'关闭碰撞','collision_on':'恢复碰撞',
        'pause_unit':'暂停单位','resume_unit':'恢复单位行动','set_scale':'修改单位缩放',
        'take_control':'接管单位','kill_unit':'杀死单位','explode_unit':'爆炸单位','remove_unit':'移除单位',
        'kill_owner_units':'消灭同属主单位','create_unit':'创建或复制单位','add_item':'添加物品',
        'clear_inventory':'清空物品栏','add_ability':'添加技能','remove_ability':'删除技能',
        'set_ability_level':'修改技能等级','set_tech':'修改科技等级','set_xp_rate':'修改经验倍率',
    },
    'extension_bag_action': {
        'add_item':'创建背包物品','set_charges':'修改背包物品数量','duplicate':'复制背包物品',
        'drop':'丢弃背包物品','destroy':'销毁背包物品','repair_item':'修复背包物品',
        'add_official_backpack':'添加官方背包',
    },
    'extension_equipment_action': {
        'unequip':'卸下所选装备','destroy':'销毁所选装备','save_loadout':'保存套装',
        'save_loadout_with_backpack':'保存套装和背包','restore_loadout':'恢复套装',
        'restore_loadout_with_backpack':'恢复套装和背包','save_all_loadouts':'一键保存套装',
        'save_all_loadouts_with_backpack':'一键保存套装和背包','restore_all_loadouts':'一键恢复套装',
        'restore_all_loadouts_with_backpack':'一键恢复套装和背包','audit':'检查装备槽',
        'repair_misplaced':'修复错槽装备','equip_bag_to_slot':'将背包物品装到指定部位',
        'enable_any_slot':'开启任意槽','repair_state':'修复装备状态','export_loadouts':'导出套装方案',
        'import_loadouts':'导入套装方案',
    },
    'extension_talent_action': {
        'select_tier':'选择天赋层','add_choice':'添加所选天赋','grant_point':'增加天赋点','reset_talents':'重置天赋',
    },
}


@contextmanager
def _failure_scope():
    if _failure_cache.get() is not None:
        yield
        return
    token = _failure_cache.set({})
    try:
        yield
    finally:
        _failure_cache.reset(token)

def search_equipment(query: str, entries=EQUIPMENT):
    terms = query.casefold().split()
    return tuple(row for row in entries if all(term in (
        row['code'] + ' ' + row['name'] + ' ' + row['description']).casefold() for term in terms))

from war3_hero_skill_catalog import HEROES, SKILLS

ALL_HEROES = '全部角色'

def search_skills(query: str, hero: str = '', entries=SKILLS):
    terms = query.casefold().split()
    return tuple(row for row in entries if (not hero or hero == ALL_HEROES or row['hero'] == hero) and
                 all(term in (row['hero'] + ' ' + row['unit_code'] + ' ' +
                              row['name'] + ' ' + row['code'] + ' ' +
                              row['description']).casefold() for term in terms))


logger = logging.getLogger("War3DesktopBridge")


class DesktopBridgeApi:
    """Methods exposed directly to the Svelte 5 frontend in WebView2."""

    def __init__(self, initial_pid: int | None = None, initial_hotkeys_enabled: bool = False, *, initialize: bool = True, offline: bool = False):
        self.offline = offline
        self.services = desktop_services()
        self.port = WebStateViewPort(self.services, initial_pid, initial_hotkeys_enabled)
        self.port.validate(TrainerApplication.required_ports)
        self.app = TrainerApplication(self.port)
        self.app.call_async = self._run_action
        self.artifact_store = ArtifactPlanStore()
        self._batch_model = None
        from war3_definition_jobs import DefinitionJobs
        self._definition_jobs=DefinitionJobs(self.services.prepare_extension_definitions,self.app.start_operation_thread,
            lambda exc:self._failure(exc,'prepare_backpack_definitions'))
        from war3_map_catalog_jobs import MapCatalogJobs
        self._map_catalog_jobs=MapCatalogJobs(self.app.start_operation_thread,
            lambda exc:self._failure(exc,'map_object_catalog'))
        from war3_script_features import ScriptOptionStore
        from war3_map_script_jobs import MapScriptJobs
        self._script_option_store = ScriptOptionStore()
        self._map_script_jobs = MapScriptJobs(self.app.start_operation_thread,
            lambda exc:self._failure(exc,'map_script_tools'))
        self.port.operation_error_reporter=self._failure
        self.port.failure_scope=_failure_scope
        self._original_finish_connect=self.app.finish_initial_connect
        self._initial_failure_reason=None
        self.app.finish_initial_connect=self._finish_initial_connect
        self.port.error_reporter=lambda exc:self._failure(exc,'scheduled_desktop_update')

        # Bind hotkey callbacks
        self.port.bind("hotkey_callbacks", self.app.hotkey_actions())
        from types import SimpleNamespace
        self.port.bind('artifact_plan_panel', SimpleNamespace(apply_clicked=lambda:
            self._run_action(lambda: self.app.elephant_add_six_artifacts(
                self.port.value('artifact_plan_settings').snapshot()), 'six_artifacts')))

        preferences = self.app.preferences.load()
        language = self.port.value('ui_language')
        if 'language' in preferences:
            language['code'] = preferences['language']
            self.port.value('status').refresh()
        self.app.restore_hotkey_preferences(preferences, force_enabled=initial_hotkeys_enabled)
        if initialize and not offline and self.port.value('elephant_hotkeys_enabled').get():
            try:
                self.app.refresh_elephant_hotkeys()
            except Exception as exc:
                self.port.value('elephant_hotkeys_enabled').set(False)
                self._failure(exc, 'initialize_hotkeys')

        # Initialize trainer connection in background
        self._init_thread = None
        if initialize:
            self._init_thread = threading.Thread(target=self._safe_init, daemon=True)
            self._init_thread.start()
            for name, delay in (('lock_tick', 1500), ('ally_health_lock_tick', 100), ('rapid_build_tick', 1000)):
                self.port.value('root').after(delay, getattr(self.app, name))

    def _run_action(self, fn, operation_key='', busy_widget=None, busy_text='正在执行，请稍候...'):
        with self.port.dispatch_lock:
            if self.port.value('state').get('closing'):
                raise RuntimeError('程序正在退出')
            self.app.set_status(busy_text)
            if busy_widget:
                busy_widget.state(['disabled'])
            try:
                result = fn()
                if operation_key.endswith(':read_unit'):
                    self.port.publish_unit_read(self._unit_snapshot(),self.port.value('candidate_tree').to_list_of_dicts())
                elif operation_key.startswith('elephant:hotkey:'):
                    self.port.publish_parameters(self.get_elephant_parameters())
                if result:
                    self.app.set_status(str(result))
                return result
            except Exception as exc:
                payload=self._failure(exc,operation_key or 'desktop_action')
                self.app.set_status(payload['error'].split('\n',1)[0])
                raise
            finally:
                if (operation_key.startswith('elephant:hotkey:') and not operation_key.endswith(':read_unit')) or operation_key == 'six_artifacts':
                    self._mark_units_changed()
                if busy_widget:
                    busy_widget.state(['!disabled'])

    def close(self):
        self._definition_jobs.cancel()
        self._map_catalog_jobs.cancel()
        self._map_script_jobs.cancel()
        with self.port.dispatch_lock:
            self.app.close_gui()

    def _log_failure(self, operation, exc):
        if self.offline:
            return
        try:
            from war3_backend import record_operation_failure
            pid = self.port.value('pid_var').get()
            return record_operation_failure(int(pid) if pid else None, operation, exc)
        except Exception as log_error:
            exc.log_write_error = repr(log_error)
            logger.exception('Desktop failure log write failed')

    def _failure(self,exc,operation='desktop_action'):
        cache = _failure_cache.get()
        payload = cache[id(exc)][1] if cache is not None and id(exc) in cache else None
        if payload:return payload
        from war3_error_messages import _chain, describe_error, format_error, operation_name
        operation = getattr(self, '_active_api_operation', operation) if operation=='desktop_action' else operation
        language=self.port.value('ui_language')['code']
        path=next((entry.diagnostic_log_path for entry in _chain(exc)
                   if getattr(entry,'diagnostic_log_path',None)),None)
        if not path:path=self._log_failure(operation,exc)
        if path and not getattr(exc,'diagnostic_log_path',None):
            try:exc.diagnostic_log_path=path
            except Exception:pass
        diagnosis=describe_error(exc,language,operation=operation)
        title_operation = diagnosis['operation'] if (
            operation in ('desktop_action','scheduled_desktop_update') or operation.startswith('elephant:')
        ) else operation
        name=operation_name(title_operation,language)
        action_title = getattr(self,'_active_action_title','')
        active_entry = getattr(self,'_active_api_operation','')
        if action_title and language=='zh' and (operation==active_entry or (
            active_entry=='extension_equipment_action' and operation.startswith(('save_','restore_'))
        )):
            name = action_title
        title=getattr(exc,'user_title',None) or (f'Could not {name[0].lower()+name[1:]}' if language=='en' else f'{name}未完成')
        if operation.startswith('elephant:hotkey:'):
            spec = self.port.value('hotkey_specs_by_name').get(operation.rsplit(':',1)[-1])
            if spec and not getattr(exc,'user_title',None):
                title = ('Hotkey action did not complete' if language=='en' else '快捷键操作未完成') + f' · {spec.label}'
        message=format_error(exc,language,diagnosis=diagnosis)
        notice=self.port.publish_error(message,title=title,log_path=path or '',details=getattr(exc,'user_details',None),
            diagnosis={**diagnosis,'logSaveFailed':bool(getattr(exc,'log_write_error',None) and not path)},
            context='map_catalog' if operation=='map_object_catalog' else '')
        payload=dict(success=False,error=message,logPath=notice['logPath'],notificationId=notice['id'],notice=notice)
        if cache is not None:
            cache[id(exc)]=(exc,payload)
        return payload

    def get_ui_notifications(self):
        return self.port.take_notifications()

    def _finish_initial_connect(self,message,exc):
        if exc is None:
            self._initial_failure_reason=None
        elif not self.port.value('state').get('closing') and str(exc) not in (
            '没有找到 Warcraft III 正式服或测试服的可见窗口',
            '没有找到同一 Warcraft III 安装目录的可见窗口'):
            from war3_error_messages import describe_error
            reason=describe_error(exc,self.port.value('ui_language')['code'])['reason']
            if reason!=self._initial_failure_reason:
                self._failure(exc,'initial_connect')
                self._initial_failure_reason=reason
            exc=RuntimeError(reason)
        return self._original_finish_connect(message,exc)

    def _safe_init(self) -> None:
        try:
            self.app.init()
        except Exception as err:
            logger.warning("Bridge init exception: %s", err)
            self._failure(err,'desktop_initialize')

    # =========================================================================
    # 1. System & Global
    # =========================================================================

    def get_system_status(self) -> dict[str, Any]:
        trainer = self.port.value("state").get("trainer")
        connected = trainer is not None and not self.port.value('state').get('closing', False)
        if connected and getattr(trainer, 'hwnd', 0):
            from war3_backend import is_war3_window
            connected = is_war3_window(trainer.hwnd, trainer.pid)
            if not connected and not self.offline:
                # Chapter loads can replace a window. Poll without waiting for
                # loading or discarding user plans; all game writes still bind
                # and validate the actual process/map/unit before execution.
                session=getattr(trainer,'_game_session',None)
                lock=getattr(session,'lock',None)
                acquired=lock is None or lock.acquire(blocking=False)
                if acquired:
                    try:
                        trainer.refresh_window(allow_pid_change=True,attempts=1)
                        connected=is_war3_window(trainer.hwnd,trainer.pid)
                        if connected:self.port.value('pid_var').set(str(trainer.pid))
                    except (RuntimeError,OSError):pass
                    finally:
                        if lock is not None:lock.release()
        pid = self.port.value("pid_var").get()
        pid_val = int(pid) if pid and pid.isdigit() else None
        game_version = "未知版本"
        adapter_profile = "未适配"
        bridge_profile = 3

        if trainer and hasattr(trainer, "_game_session"):
            session = trainer._game_session
            prof = getattr(session, 'profile', None)
            if prof is not None:
                game_version = prof.data['game_version']
                adapter_profile = prof.id
                bridge_profile = prof.data.get('bridge_profile_version', 3)

        return {
            "appVersion": APP_VERSION,
            "edition": PRODUCT_EDITION_LABEL,
            "connected": connected,
            "connectionId": f'{id(trainer):x}:{getattr(trainer,"pid",0)}:{getattr(trainer,"hwnd",0)}' if trainer else '',
            "pid": pid_val,
            "gameVersion": game_version if connected else None,
            "adapterProfile": adapter_profile if connected else None,
            "bridgeProfile": bridge_profile,
            "hotkeysEnabled": bool(self.port.value("elephant_hotkeys_enabled").get()),
            "statusMessage": self._status_text(),
            "language": self.port.value("ui_language")["code"],
            'offline': self.offline,
        }

    def _status_text(self):
        text=str(self.port.value('status').get())
        # Technical reports belong in the diagnostic file, never the ticker.
        import re
        if re.search(r'\{\s*["\']|engine24268=|Traceback',text):
            text=re.split(r'\{\s*["\']|engine24268=|Traceback',text,maxsplit=1)[0].strip(' ;；:：,，\n')
            return text[:180] or ('Operation finished; details are in the log.' if self.port.value('ui_language')['code']=='en' else '操作已结束，详细记录见日志。')
        return text

    def connect_process(self, pid: int | None = None) -> dict[str, Any]:
        if pid is not None:
            self.port.value("pid_var").set(str(pid))
        try:
            self.app.connect()
            self._batch_model = None
            self.app.clear_selected_unit_readout()
            self._mark_units_changed()
            return {"success": True, "status": self.get_system_status()}
        except Exception as err:
            return {**self._failure(err,'connect_process'), "status": self.get_system_status()}

    def cancel_discovery(self) -> dict[str, Any]:
        try:
            self.app.cancel_discovery()
            return {"success": True}
        except Exception as err:
            return self._failure(err)

    def set_hotkeys_enabled(self, enabled: bool) -> dict[str, Any]:
        enabled = bool(enabled)
        switch = self.port.value('elephant_hotkeys_enabled')
        before = switch.get()
        switch.set(enabled)
        try:
            if not self.offline:
                self.app.refresh_elephant_hotkeys()
            else:
                self.port.value('elephant_hotkey_status').set('全局快捷键已启用' if enabled else '快捷键未启用')
        except Exception as err:
            switch.set(before)
            try:
                self.app.refresh_elephant_hotkeys()
            except Exception:
                logger.exception('Could not restore the previous hotkey registration')
                switch.set(False)
            return self._failure(err)
        self.app.save_ui_preferences(hotkeys_enabled=enabled)
        return {"success": True, "enabled": enabled, "status": self.port.value('elephant_hotkey_status').get()}

    def set_ui_language(self, lang: str, remember: bool = True) -> dict[str, Any]:
        if lang in ("zh", "en"):
            if remember:
                self.app.save_ui_preferences(language=lang)
            self.port.value("ui_language")["code"] = lang
            self.port.value("status").refresh()
            self.port.value("elephant_hotkey_status").refresh()
            if self.port.window and hasattr(self.port.window,'set_title'):
                from war3_metadata import trainer_window_title
                self.port.window.set_title(trainer_window_title(lang))
            from war3_ui_i18n import _EN_TRANSLATIONS
            return {"success": True, "language": lang, 'translations': _EN_TRANSLATIONS}
        raise ValueError('所选语言不受支持，请选择简体中文或英语。')

    # =========================================================================
    # 2. Player Resources
    # =========================================================================

    def get_resource_snapshot(self) -> dict[str, Any]:
        tree: VirtualTree = self.port.value("resource_tree")
        groups = tree.to_list_of_dicts()
        return {
            "selectedGroup": self.port.value("state").get("selected_resource_iid", ""),
            "current": {
                "gold": self.port.value("gold_current").get(),
                "lumber": self.port.value("lumber_current").get(),
                "food": self.port.value("food_current").get(),
                "foodCap": self.port.value("food_cap_current").get(),
            },
            "targets": {
                "gold": self.port.value("gold_target").get(),
                "lumber": self.port.value("lumber_target").get(),
                "foodUsed": self.port.value("food_used_target").get(),
                "foodCap": self.port.value("food_cap_target").get(),
            },
            "delta": self.port.value("resource_delta").get(),
            "groups": groups,
        }

    def gold_mines(self, scope: str='selected', amount: str | None=None) -> dict[str, Any]:
        result = None
        def execute():
            nonlocal result
            result = self.app.gold_mines(scope,amount)
            return f"金矿：{result['count']}；已修改 {result['changed']}；已符合 {result['unchanged']}；跳过或失败 {result['failed']}"
        try:
            self._run_action(execute,'gold_mines',busy_text='正在读取或修改金矿，请稍候...')
            rows=[]
            kinds={1:'普通金矿',2:'闹鬼金矿',4:'缠绕金矿'}
            states={0:'已读取',1:'已修改',2:'已符合目标',3:'修改失败',4:'状态变化，已跳过',5:'结果待确认'}
            for r in result['rows']:
                rows.append(dict(handle=hex(r['handle']),rawcode=r['rawcode'].to_bytes(4,'big').decode('ascii','replace'),
                    kind=kinds.get(r['kind'],'自定义金矿'),owner=r['owner'],before=r['before'],after=r['after'],
                    status=states[r['status']],error=r['error'],x=r['x'],y=r['y']))
            data={k:result[k] for k in ('count','visited','ignored','changed','unchanged','failed','uncertain')}
            data.update(rows=rows,scope=scope,action=0 if amount is None else 1)
            if result['failed']:
                from war3_error_messages import describe_error
                language=self.port.value('ui_language')['code']
                failure=RuntimeError('部分金矿未完成'+('读取。' if amount is None else '修改，已完成的金矿保留。'))
                failure.user_details=[]
                for row in rows:
                    if not row['error']:continue
                    error=RuntimeError()
                    error.report={'operation':'gold_mine','gold_mine_status':{'error':row['error']}}
                    detail=describe_error(error,language)['reason']
                    row['reason']=detail
                    failure.user_details.append(dict(scope=row['kind'],file=f"{row['rawcode']} ({row['x']:.0f}, {row['y']:.0f})",message=detail))
                return {**self._failure(failure,'gold_mines'),
                        'data':data,'reports':rows}
            if amount is not None and not rows:
                return {**self._failure(RuntimeError('当前范围未找到可修改的金矿，请检查游戏选择或改用全图读取。'),'gold_mines'),
                        'data':data,'reports':rows}
            return dict(success=True,data=data)
        except Exception as err:
            return self._failure(err,'gold_mines')

    def refresh_resources(self) -> dict[str, Any]:
        try:
            self.app.refresh_resources()
            return {"success": True, "data": self.get_resource_snapshot()}
        except Exception as err:
            return {**self._failure(err,'refresh_resources'), "data": self.get_resource_snapshot()}

    def set_resource(self, kind: str, value: str) -> dict[str, Any]:
        if kind == "gold":
            self.port.value("gold_target").set(value)
            self.app.set_resource("gold")
        elif kind == "lumber":
            self.port.value("lumber_target").set(value)
            self.app.set_resource("lumber")
        elif kind == "food_used":
            self.port.value("food_used_target").set(value)
            self.app.set_food_resource("food_used")
        elif kind == "food_cap":
            self.port.value("food_cap_target").set(value)
            self.app.set_food_resource("food_cap")
        else:
            raise ValueError('此资源类型不能修改，请重新选择金币、木材或人口。')
        return {"success": True, "data": self.get_resource_snapshot()}

    def add_resource(self, kind: str, delta: str | None = None) -> dict[str, Any]:
        if delta is not None:
            self.port.value("resource_delta").set(delta)
        self.app.add_resource(kind)
        return {"success": True, "data": self.get_resource_snapshot()}

    def add_resource_lock(self, kind: str, expected_group: str | None = None) -> dict[str, Any]:
        self.app.add_resource_lock(kind, capture_current=True, expected_group=expected_group)
        return {"success": True, "locks": self.get_locks(), "data": self.get_resource_snapshot()}

    # =========================================================================
    # 3. Selected Unit & Candidates
    # =========================================================================

    def read_selected_unit(self) -> dict[str, Any]:
        self.app.read_unit_fields()
        return self._unit_snapshot()

    def read_all_selected_units(self):
        self.app.read_unit_with_sound()
        return dict(unit=self._unit_snapshot(),candidates=self.port.value('candidate_tree').to_list_of_dicts())

    def _unit_snapshot(self) -> dict[str, Any]:
        field_tree: VirtualTree = self.port.value("unit_field_tree")
        fields = field_tree.to_list_of_dicts()

        state = self.port.value("state")
        identity = state.get("selected_unit_identity")

        return {
            "hasSelection": bool(identity),
            "unitTypeId": self.port.value("unit_type_id_current").get(),
            "identity": str(identity) if identity else None,
            "hp": {
                "current": self.port.value("hp_current").get(),
                "max": self.port.value("hp_max_current").get(),
                "regen": self.port.value("hp_regen_current").get(),
                "target": self.port.value("hp_target").get(),
                "regenTarget": self.port.value("hp_regen_target").get(),
            },
            "mp": {
                "current": self.port.value("mp_current").get(),
                "max": self.port.value("mp_max_current").get(),
                "regen": self.port.value("mp_regen_current").get(),
                "target": self.port.value("mp_target").get(),
                "regenTarget": self.port.value("mp_regen_target").get(),
            },
            "position": {
                "xCurrent": self.port.value("x_current").get(),
                "yCurrent": self.port.value("y_current").get(),
                "xTarget": self.port.value("x_target").get(),
                "yTarget": self.port.value("y_target").get(),
            },
            "fields": fields,
        }

    def get_selected_unit_snapshot(self):
        return self._unit_snapshot()

    def get_unit_candidates_snapshot(self):
        return self.port.value('candidate_tree').to_list_of_dicts()

    def select_resource_group(self, row_iid: str):
        tree = self.port.value('resource_tree')
        if not tree.exists(row_iid):
            raise ValueError('资源组已变化，请重新读取')
        tree.selection_set(row_iid)
        self.app.on_resource_select()
        return self.get_resource_snapshot()

    def write_selected_unit(self, targets: dict[str, str]) -> dict[str, Any]:
        for k, v in targets.items():
            if k == "hpTarget":
                self.port.value("hp_target").set(v)
            elif k == "mpTarget":
                self.port.value("mp_target").set(v)
            elif k == "hpRegenTarget":
                self.port.value("hp_regen_target").set(v)
            elif k == "mpRegenTarget":
                self.port.value("mp_regen_target").set(v)
            elif k == "xTarget":
                self.port.value("x_target").set(v)
            elif k == "yTarget":
                self.port.value("y_target").set(v)
        try:
            self.app.set_unit()
            return {"success": True, "data": self._unit_snapshot()}
        except Exception as err:
            return self._failure(err)

    def write_unit_field(self, field_row_iid: str, target_value: str) -> dict[str, Any]:
        tree: VirtualTree = self.port.value("unit_field_tree")
        tree.selection_set(field_row_iid)
        self.port.value("unit_field_target").set(target_value)
        try:
            self.app.set_advanced_unit_field()
            return {"success": True, "data": self._unit_snapshot()}
        except Exception as err:
            return self._failure(err)

    def add_unit_field_lock(self, field_row_iid: str, target_value: str) -> dict[str, Any]:
        tree: VirtualTree = self.port.value("unit_field_tree")
        tree.selection_set(field_row_iid)
        self.port.value("unit_field_target").set(target_value)
        try:
            self.app.add_unit_lock()
            return {"success": True, "locks": self.get_locks()}
        except Exception as err:
            return self._failure(err)

    def refresh_unit_candidates(self) -> list[dict[str, Any]]:
        self.app.refresh_unit_candidates()
        tree: VirtualTree = self.port.value("candidate_tree")
        return tree.to_list_of_dicts()

    def read_selection_candidate(self, candidate_iid: str) -> dict[str, Any]:
        tree: VirtualTree = self.port.value("candidate_tree")
        tree.selection_set(candidate_iid)
        try:
            self.app.read_selection_candidate_fields()
            return {"success": True, "unit": self._unit_snapshot()}
        except Exception as err:
            return self._failure(err)

    def read_native_selection(self) -> dict[str, Any]:
        try:
            self.app.read_unit_native_selection()
            return {"success": True, "unit": self._unit_snapshot()}
        except Exception as err:
            return self._failure(err)

    # =========================================================================
    # 4. Locks List
    # =========================================================================

    def get_locks(self) -> list[dict[str, Any]]:
        self.app.populate_locks()
        tree: VirtualTree = self.port.value("lock_tree")
        return tree.to_list_of_dicts()

    def apply_locks_once(self) -> dict[str, Any]:
        try:
            self.app.apply_locks_once()
            return {"success": True, "message": "锁定项已执行一次"}
        except Exception as err:
            return self._failure(err)

    def remove_lock(self, lock_iid: str) -> dict[str, Any]:
        tree: VirtualTree = self.port.value("lock_tree")
        tree.selection_set(lock_iid)
        try:
            self.app.remove_selected_lock()
            return {"success": True, "locks": self.get_locks()}
        except Exception as err:
            return self._failure(err)

    # =========================================================================
    # 5. Ability Fields
    # =========================================================================

    def read_ability_fields(self, rawcode: str, level: str, filter_text: str = "", show_zero: bool = True, show_unsupported: bool = True) -> dict[str, Any]:
        self.port.value("ability_field_rawcode").set(rawcode)
        self.port.value("ability_field_level").set(level)
        self.port.value("ability_field_filter").set(filter_text)
        self.port.value("ability_field_show_zero").set(show_zero)
        self.port.value("ability_field_show_unsupported").set(show_unsupported)
        try:
            if self.port.value('state').pop('fields_need_refresh', False):
                self.app.read_unit_fields()
            self.app.read_ability_field_snapshot()
            self.app.refresh_ability_field_tree()
        except Exception as err:
            self.port.value('state')['ability_field_snapshot'] = None
            self.app.refresh_ability_field_tree()
            self.port.value('ability_field_summary').set(str(err))
            raise

        tree: VirtualTree = self.port.value("ability_field_tree")
        return {
            "summary": self.port.value("ability_field_summary").get(),
            "detail": self.port.value("ability_field_detail").get(),
            "rows": [dict(row, searchText=ability_field_search_text(field.spec) if
                          (field := self.port.value('state')['ability_field_rows'].get(row['_iid'])) else '')
                     for row in tree.to_list_of_dicts()],
        }

    def write_ability_field(self, row_iid: str, new_value: str) -> dict[str, Any]:
        tree: VirtualTree = self.port.value("ability_field_tree")
        tree.selection_set(row_iid)
        self.port.value("ability_field_value").set(new_value)
        try:
            snapshot = self.port.value('state').get('ability_field_snapshot')
            field = self.port.value('state')['ability_field_rows'].get(row_iid)
            if snapshot is None or field is None or field.value is None or not field.spec.writable:
                raise ValueError('请重新读取并选择可写技能字段')
            self.app.write_selected_ability_field(snapshot,
                self.port.value('ability_field_rawcode').get(),
                int(self.port.value('ability_field_level').get()), field, new_value)
            return self._after_field_write('refresh_ability_fields', lambda: self.read_ability_fields(
                self.port.value("ability_field_rawcode").get(),
                self.port.value("ability_field_level").get(),
            ))
        except Exception as err:
            return self._failure(err)

    # =========================================================================
    # 6. Item Fields
    # =========================================================================

    def read_item_fields(self, slot: str, filter_text: str = "", show_zero: bool = True, show_unsupported: bool = True) -> dict[str, Any]:
        self.port.value("item_field_slot").set(str(int(slot) + 1))
        self.port.value("item_field_filter").set(filter_text)
        self.port.value("item_field_show_zero").set(show_zero)
        self.port.value("item_field_show_unsupported").set(show_unsupported)
        try:
            if self.port.value('state').pop('fields_need_refresh', False):
                self.app.read_unit_fields()
            self.app.read_item_field_snapshot()
            self.app.refresh_item_field_tree()
        except Exception as err:
            self.port.value('state')['item_field_snapshot'] = None
            self.app.refresh_item_field_tree()
            raise

        tree: VirtualTree = self.port.value("item_field_tree")
        return {
            "summary": self.port.value("item_field_summary").get(),
            "detail": self.port.value("item_field_detail").get(),
            "rows": [dict(row, editable=bool((field := self.port.value("state")["item_field_rows"].get(row["_iid"])) and field.value is not None and field.spec.writable), searchText=item_field_search_text(field.spec) if field else '') for row in tree.to_list_of_dicts()],
        }

    def write_item_field(self, row_iid: str, new_value: str) -> dict[str, Any]:
        tree: VirtualTree = self.port.value("item_field_tree")
        tree.selection_set(row_iid)
        self.port.value("item_field_value").set(new_value)
        try:
            snapshot = self.port.value('state').get('item_field_snapshot')
            field = self.port.value('state')['item_field_rows'].get(row_iid)
            if snapshot is None or field is None or field.value is None or not field.spec.writable:
                raise ValueError('请重新读取并选择可写物品字段')
            self.app.write_selected_item_field(snapshot, field, new_value)
            return self._after_field_write('refresh_item_fields', lambda: self.read_item_fields(str(int(self.port.value("item_field_slot").get()) - 1)))
        except Exception as err:
            return self._failure(err)

    def read_item_effect_fields(self, area: str, slot: str, level: str = '1') -> dict[str, Any]:
        state = self.port.value('state')
        state['item_effect_snapshot'] = None
        snapshot = self.app.read_item_effect_field_snapshot(str(area), int(slot), int(level))
        state['item_effect_snapshot'] = snapshot
        return self.app.item_effect_fields_view(snapshot)

    def write_item_effect_field(self, row_iid: str, new_value: str) -> dict[str, Any]:
        state = self.port.value('state')
        snapshot = state.get('item_effect_snapshot')
        try:
            if snapshot is None or not isinstance(row_iid, str):
                raise ValueError('请重新读取物品附带技能字段')
            generation, index = row_iid.rsplit(':', 1)
            if generation != snapshot.generation:
                raise ValueError('这条物品字段已失效，请重新读取')
            self.app.write_item_effect_field_value(snapshot, int(index), str(new_value))
            state['item_effect_snapshot'] = None
            def refresh():
                current = self.app.read_item_effect_field_snapshot(snapshot.source.area, snapshot.source.slot, snapshot.level)
                state['item_effect_snapshot'] = current
                return self.app.item_effect_fields_view(current)
            return self._after_field_write('refresh_item_effect_fields', refresh)
        except Exception as exc:
            state['item_effect_snapshot'] = None
            return self._failure(exc, 'write_item_effect_field')

    def _after_field_write(self, operation, refresh):
        from war3_error_messages import CompletedWithWarning
        try:
            return {'success':True, 'data':refresh()}
        except Exception as exc:
            warning = self._failure(CompletedWithWarning(exc),operation)
            return {'success':True,'write_completed':True,'notice':warning['notice']}

    # =========================================================================
    # 7. 3.0 Extensions (Backpack, Equipment, Talents, Definition Repair)
    # =========================================================================

    def refresh_extension_status(self, refresh: bool = True) -> dict[str, Any]:
        if refresh:
            self.app.refresh_extension_snapshot()

        bag_tree: VirtualTree = self.port.value("extension_bag_tree")
        equip_tree: VirtualTree = self.port.value("extension_equipment_tree")
        talent_tree: VirtualTree = self.port.value("extension_talent_tree")

        from war3_3_extension_catalog import OFFICIAL_BACKPACKS
        backpack_options = [f"{hero_name} ({rawcode})" for rawcode, (hero_name, _) in OFFICIAL_BACKPACKS.items()]
        from war3_loadout_restore import plan_choices
        trainer=self.port.value('state').get('trainer')
        plans = plan_choices(trainer) if trainer is not None else {}
        saved_names = list(plans)
        self.port.value('extension_loadout_box')['values']=tuple(saved_names)
        choice=self.port.value('extension_loadout_choice').get()
        if choice not in saved_names:
            typed=self.port.value('extension_loadout_name').get()
            choice=typed if typed in saved_names else (saved_names[-1] if saved_names else '')
            self.port.value('extension_loadout_choice').set(choice)

        return {
            "status": self.port.value("extension_status").get(),
            "bag": bag_tree.to_list_of_dicts(),
            "equipment": equip_tree.to_list_of_dicts(),
            "talents": [dict(row, choiceCodes=list(self.port.value('state').get(
                'extension_talent_choices', {}).get(row['_iid'], ())))
                for row in talent_tree.to_list_of_dicts()],
            "selectedTalentIid": next(iter(talent_tree.selection()), ''),
            "currentTalentChoice": self.port.value('extension_talent_choice').get(),
            "officialBackpacks": backpack_options,
            "currentBackpackChoice": self.port.value("extension_backpack_choice").get(),
            "loadoutName": self.port.value("extension_loadout_name").get(),
            'loadoutNames': saved_names,
            'loadoutBackpackCounts': {name: sum(bool(code) for code, _ in record['backpack'])
                                      for name, record in plans.items() if 'backpack' in record},
            'currentLoadoutChoice': choice,
            'talentChoices': list(getattr(self.port.value('extension_talent_choice_box'), 'values', ())),
            'loadoutWarnings': {key: value for key, value in (self.port.value('state').get('extension_snapshot') or {}).items()
                                if key in ('loadout_charge_mismatches', 'loadout_postcondition_warning', 'loadout_talents', 'loadout_talent_summary', 'talent_display_warning')},
        }

    def extension_bag_action(self, action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        try:
            if action == "add_item":
                self.port.value("extension_item_rawcode").set(params.get("rawcode", ""))
                self.port.value("extension_item_charges").set(str(params.get("charges", "1")))
                message = self.app.extension_add_item()
            elif action == "set_charges":
                row_iid = params.get("row_iid", "")
                self.port.value("extension_bag_tree").selection_set(row_iid)
                self.port.value("extension_item_charges").set(str(params.get("charges", "1")))
                message = self.app.extension_set_bag_charges()
            elif action == "duplicate":
                self.port.value("extension_bag_tree").selection_set(params.get("row_iid", ""))
                message = self.app.extension_duplicate_bag_item()
            elif action == "drop":
                self.port.value("extension_bag_tree").selection_set(params.get("row_iid", ""))
                message = self.app.extension_drop_clicked()
            elif action == "destroy":
                self.port.value("extension_bag_tree").selection_set(params.get("row_iid", ""))
                message = self.app.extension_destroy_clicked("bag")
            elif action == "repair_item":
                self.port.value("extension_bag_tree").selection_set(params.get("row_iid", ""))
                message = self.app.extension_repair_bag_item()
            elif action == "add_official_backpack":
                choice = params.get("choice", "")
                if choice:
                    self.port.value("extension_backpack_choice").set(choice)
                message = self.app.extension_add_backpack_equipment()
            else:
                raise ValueError('这项背包操作在当前版本不可用，请重新打开修改器后选择背包按钮。')
            return {"success": True, "message":message or '', "data": self.refresh_extension_status(False)}
        except Exception as err:
            return self._failure(err, action if action=='add_official_backpack' else 'extension_bag_action')

    def extension_equipment_action(self, action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        message = ''
        try:
            if action == "unequip":
                self.port.value("extension_equipment_tree").selection_set(params.get("row_iid", ""))
                message = self.app.extension_unequip_item()
            elif action == "destroy":
                self.port.value("extension_equipment_tree").selection_set(params.get("row_iid", ""))
                message = self.app.extension_destroy_clicked("equipment")
            elif action in ("save_loadout", "save_loadout_with_backpack"):
                name = params.get("name", "套装1")
                self.port.value("extension_loadout_name").set(name)
                message = (self.app.extension_save_loadout(with_backpack=True) if action == 'save_loadout_with_backpack'
                           else self.app.extension_save_loadout())
            elif action in ("restore_loadout", "restore_loadout_with_backpack"):
                name = params.get("name", "")
                if 'name' in params:
                    self.port.value("extension_loadout_choice").set(name)
                message = (self.app.extension_restore_loadout(with_backpack=True) if action == 'restore_loadout_with_backpack'
                           else self.app.extension_restore_loadout())
            elif action in ('save_all_loadouts', 'save_all_loadouts_with_backpack'):
                if 'name' in params:
                    self.port.value("extension_loadout_name").set(params['name'])
                message = (self.app.extension_save_all_loadouts(with_backpack=True) if action.endswith('_with_backpack')
                           else self.app.extension_save_all_loadouts())
            elif action in ('restore_all_loadouts', 'restore_all_loadouts_with_backpack'):
                if 'name' in params:
                    self.port.value("extension_loadout_choice").set(params['name'])
                message = (self.app.extension_restore_all_loadouts(with_backpack=True) if action.endswith('_with_backpack')
                           else self.app.extension_restore_all_loadouts())
            elif action == "audit":
                message = self.app.extension_audit_equipment()
            elif action == "repair_misplaced":
                message = self.app.extension_repair_equipment_clicked()
            elif action == "equip_bag_to_slot":
                self.port.value('extension_bag_tree').selection_set(params.get('bag_row_iid', ''))
                self.port.value('extension_equipment_tree').selection_set(params.get('row_iid', ''))
                message = self.app.extension_equip_bag_to_slot()
            elif action == "enable_any_slot":
                message = self.app.extension_enable_any_slot()
            elif action == "repair_state":
                message = self.app.extension_repair_equipment_state()
            elif action == 'export_loadouts':
                message = self.app.extension_export_plans()
                if not message:return dict(success=False,cancelled=True)
            elif action == 'import_loadouts':
                message = self.app.extension_import_plans()
                if not message:return dict(success=False,cancelled=True)
            else:
                raise ValueError('这项装备操作在当前版本不可用，请重新打开修改器后选择装备按钮。')
            return {"success": True, 'message': message, "data": self.refresh_extension_status(False)}
        except Exception as err:
            return self._failure(err, action if action in (
                'save_loadout','save_loadout_with_backpack','save_all_loadouts','save_all_loadouts_with_backpack',
                'restore_loadout','restore_loadout_with_backpack','restore_all_loadouts','restore_all_loadouts_with_backpack',
            ) else 'extension_equipment_action')

    def extension_talent_action(self, action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        message = ''
        try:
            if action in ('select_tier', 'add_choice'):
                iid = params.get('row_iid', '')
                tree = self.port.value('extension_talent_tree')
                if not isinstance(iid, str) or not tree.exists(iid):
                    raise ValueError('天赋层已变化，请重新读取并选择')
                tree.selection_set(iid)
                self.app.extension_talent_tree_selected()
            if action == "add_choice":
                choice = params.get("choice", "")
                if not isinstance(choice, str) or not choice:
                    raise ValueError('请先选择一个天赋选项')
                self.port.value("extension_talent_choice").set(choice)
                message = self.app.extension_add_talent_choice()
            elif action == "grant_point":
                message = self.app.extension_grant_talent_point()
            elif action == "reset_talents":
                message = self.app.extension_reset_talents_clicked()
            elif action == 'select_tier':
                pass
            else:
                raise ValueError('这项天赋操作在当前版本不可用，请刷新天赋或重新打开修改器。')
            return {"success": True, "message":message or '', "data": self.refresh_extension_status(False)}
        except Exception as err:
            return self._failure(err)

    def prepare_backpack_definitions(self, map_path: str, output_folder: str = '') -> dict[str, Any]:
        try:
            from dataclasses import asdict
            p = Path(map_path.strip().strip('"')).expanduser()
            if not p.is_file():
                return {"success": False, "error": f"文件不存在: {map_path}"}
            folder = Path(output_folder.strip().strip('"')).expanduser() if output_folder.strip() else p.resolve().parent
            result = self.services.prepare_extension_definitions(p, folder)
            return {"success": True, "destination": result.output, "report": asdict(result),
                    "message": f'文件校验完成：共 {result.chapter_count} 个章节，补齐 {result.changed_chapters} 个章节。请使用下方新副本重新进入地图。'}
        except Exception as err:
            return self._failure(err,'prepare_backpack_definitions')

    def start_backpack_definitions(self,map_path: str,output_folder: str=''):
        return self._definition_jobs.start(map_path,output_folder)

    def start_backpack_definitions_batch(self,map_paths: list[str],output_folder: str=''):
        return self._definition_jobs.start_batch(map_paths,output_folder)

    def get_backpack_definition_progress(self,job_id: str=''):
        return self._definition_jobs.snapshot(job_id)

    def cancel_backpack_definitions(self,job_id: str=''):
        return self._definition_jobs.cancel(job_id)

    def choose_definition_file(self):
        if not self.port.window:raise ValueError('请在修改器桌面窗口内选择文件。')
        path=self.port.value('filedialog').askopenfilename(file_types=(
            'Warcraft campaigns and maps (*.w3n;*.w3x;*.w3m)',
            'Warcraft campaigns (*.w3n)','Warcraft maps (*.w3x;*.w3m)'))
        return dict(success=True,path=path,cancelled=not bool(path))

    def choose_definition_folder(self):
        if not self.port.window:raise ValueError('请在修改器桌面窗口内选择文件夹。')
        path=self.port.value('filedialog').askdirectory()
        return dict(success=True,path=path,cancelled=not bool(path))

    def choose_definition_files(self):
        if not self.port.window:raise ValueError('请在修改器桌面窗口内选择文件。')
        paths=self.port.value('filedialog').askopenfilenames(file_types=(
            'Warcraft campaigns and maps (*.w3n;*.w3x;*.w3m)',
            'Warcraft campaigns (*.w3n)','Warcraft maps (*.w3x;*.w3m)'))
        return dict(success=True,paths=list(paths),cancelled=not bool(paths))

    # =========================================================================
    # 8. Elephant Features & Direct Actions
    # =========================================================================

    def prewarm_elephant(self) -> dict[str, Any]:
        try:
            self.app.elephant_prewarm()
            self._mark_units_changed()
            return {"success": True, "message": "大象功能初始化就绪"}
        except Exception as err:
            return self._failure(err)

    def execute_elephant_action(self, action_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        try:
            # Map & Game
            if action_name == "reveal_map":
                self.app.ui_reveal_map()
            elif action_name == "hide_map":
                self.app.ui_hide_map()
            elif action_name == "pause_game":
                self.app.elephant_set_game_paused(True)
            elif action_name == "resume_game":
                self.app.elephant_set_game_paused(False)
            elif action_name == "peace_on":
                self.app.ui_peace_on()
            elif action_name == "peace_off":
                self.app.ui_peace_off()
            elif action_name == "end_game":
                self.app.ui_end_game()

            # Hero status
            elif action_name == "hero_level_read":
                self.app.elephant_read_hero_level()
            elif action_name == "hero_level_set":
                self.port.value("elephant_hero_level").set(str(params.get("level", "1")))
                self.app.elephant_set_hero_level()
            elif action_name == "invulnerable":
                self.app.ui_invulnerable()
            elif action_name == "vulnerable":
                self.app.ui_vulnerable()
            elif action_name == "reset_cooldown":
                self.app.ui_reset_cooldown()
            elif action_name == "collision_off":
                self.app.ui_pathing_off()
            elif action_name == "collision_on":
                self.app.ui_pathing_on()
            elif action_name == "pause_unit":
                self.app.ui_pause_unit()
            elif action_name == "resume_unit":
                self.app.ui_resume_unit()
            elif action_name == "set_scale":
                self.port.value("elephant_unit_scale").set(str(params.get("scale", "1.0")))
                self.app.elephant_set_scale()

            # Target
            elif action_name == "take_control":
                self.app.ui_take_control()
            elif action_name == "kill_unit":
                self.app.ui_kill_unit()
            elif action_name == "explode_unit":
                self.app.ui_explode_unit()
            elif action_name == "remove_unit":
                self.app.ui_remove_unit()
            elif action_name == "kill_owner_units":
                self.app.elephant_kill_owner_units()

            # Create & Items
            elif action_name == "create_unit":
                rawcode = params.get("rawcode", "")
                if rawcode:
                    self.port.value("elephant_unit_rawcode").set(rawcode)
                to_self = bool(params.get("to_self", False))
                self.app.elephant_create_unit(to_self)
            elif action_name == "add_item":
                rawcode = params.get("rawcode", "")
                if rawcode:
                    self.port.value("elephant_item_rawcode").set(rawcode)
                self.app.elephant_add_item()
            elif action_name == "clear_inventory":
                self.app.elephant_clear_inventory()

            # Abilities
            elif action_name == "add_ability":
                rawcode = params.get("rawcode", "")
                if rawcode:
                    self.port.value("elephant_ability_rawcode").set(rawcode)
                level = params.get("level", "1")
                self.port.value("elephant_ability_level").set(str(level))
                self.app.elephant_add_ability()
            elif action_name == "remove_ability":
                rawcode = params.get("rawcode", "")
                if rawcode:
                    self.port.value("elephant_ability_rawcode").set(rawcode)
                self.app.elephant_remove_ability()
            elif action_name == "set_ability_level":
                rawcode = params.get("rawcode", "")
                if rawcode:
                    self.port.value("elephant_ability_rawcode").set(rawcode)
                level = params.get("level", "1")
                self.port.value("elephant_ability_level").set(str(level))
                self.app.elephant_set_ability_level()

            # Tech & XP
            elif action_name == "set_tech":
                rawcode = params.get("rawcode", "")
                if rawcode:
                    self.port.value("elephant_tech_rawcode").set(rawcode)
                level = params.get("level", "1")
                self.port.value("elephant_tech_level").set(str(level))
                self.app.elephant_set_tech()
            elif action_name == "set_xp_rate":
                rate = params.get("rate", "1.0")
                self.port.value("elephant_xp_rate").set(str(rate))
                self.app.elephant_set_xp_rate()
            else:
                raise ValueError('当前版本没有这条大象功能指令。请重新打开修改器，从界面中的按钮执行。')

            self._mark_units_changed()
            return {"success": True, "action": action_name,'parameters':self.get_elephant_parameters()}
        except Exception as err:
            return {**self._failure(err), "action": action_name}

    # =========================================================================
    # 9. 6-Slot Artifact Custom Plan
    # =========================================================================

    def get_elephant_parameters(self):
        return {key:self.port.value('elephant_'+key).get() for key in (
            'hero_level','unit_scale','unit_rawcode','item_rawcode','ability_rawcode','ability_level',
            'tech_rawcode','tech_level','xp_rate')}

    def set_elephant_parameter(self,key: str,value: str):
        if key not in self.get_elephant_parameters():raise ValueError('参数已变化，请重新打开此页面。')
        self._set_saved_parameter(key, self.port.value('elephant_'+key), value)
        return dict(success=True,changedParameters={key:str(value)})

    def _set_saved_parameter(self, key, variable, value):
        value = str(value)
        if len(value) > 128:
            raise ValueError('参数不能超过 128 个字符')
        self.app.save_ui_preferences(parameters={key: value})
        variable.set(value)

    def get_artifact_plan(self) -> dict[str, Any]:
        settings = self.port.value("artifact_plan_settings")
        displayed = settings.displayed_plan
        return {
            "codes": list(displayed.codes),
            "isDefault": list(displayed.codes) == list(DEFAULT_ARTIFACT_CODES),
            "defaultCodes": list(DEFAULT_ARTIFACT_CODES),
        }

    def save_artifact_plan(self, codes: list[str]) -> dict[str, Any]:
        if len(codes) != 6:
            return {"success": False, "error": "方案必须为精确的 6 个物品代码"}
        try:
            settings = self.port.value("artifact_plan_settings")
            settings.update(tuple(codes))
            return {"success": True, "plan": self.get_artifact_plan()}
        except ArtifactPlanError as err:
            return self._failure(err)
        except Exception as err:
            return self._failure(err)

    def restore_default_artifact_plan(self) -> dict[str, Any]:
        try:
            settings = self.port.value("artifact_plan_settings")
            settings.update(DEFAULT_ARTIFACT_CODES)
            return {"success": True, "plan": self.get_artifact_plan()}
        except Exception as err:
            return self._failure(err)

    def apply_artifact_plan(self, codes: list[str] | None = None) -> dict[str, Any]:
        if codes is not None:
            res = self.save_artifact_plan(codes)
            if not res["success"]:
                return res
        try:
            settings = self.port.value("artifact_plan_settings")
            message = self.app.elephant_add_six_artifacts(settings.snapshot())
            self._mark_units_changed()
            return {"success": True, "message": message}
        except Exception as err:
            return self._failure(err)

    # =========================================================================
    # 10. All 68 Elephant Hotkeys
    # =========================================================================

    def get_all_hotkeys(self) -> list[dict[str, Any]]:
        specs = self.services.hotkeys
        checks = self.port.value("elephant_hotkey_checks")
        stat_values = self.port.value("elephant_stat_values")

        param_map = {
            "hero_level": ("elephant_hero_level", "等级"),
            "unit_scale": ("elephant_unit_scale", "缩放"),
            "item_charges": ("elephant_item_charges", "数量"),
            "add_ability": ("elephant_ability_rawcode", "技能ID"),
            "add_resources": ("elephant_resource_amount", "增量"),
            "mass_clone": ("elephant_mass_clone_count", "数量"),
            "ability_level": ("elephant_ability_level", "等级"),
            "remove_ability": ("elephant_ability_rawcode", "技能ID"),
            "reinforcements": ("elephant_reinforcement_rawcode", "单位ID"),
            "preset_item": ("elephant_preset_item_rawcode", "物品ID"),
            "preset_tech": ("elephant_preset_tech_rawcode", "科技ID"),
            "hero_attributes": ("elephant_hero_attributes", "属性值"),
            "skill_points": ("elephant_skill_points", "点数"),
            "xp_rate": ("elephant_xp_rate", "倍率"),
            "reset_ability": ("elephant_reset_ability_rawcode", "技能ID"),
            "fullscreen_auto": ("elephant_auto_effect_count", "特效数"),
            "game_speed": ("elephant_game_speed", "倍速"),
        }

        dangerous_set = {"explode_unit", "drop_inventory", "kill_owner_units", "end_game", "remove_all_abilities", "instant_victory"}

        result = []
        for spec in specs:
            name = spec.name
            enabled = bool(checks[name].get()) if name in checks else False
            param_key = None
            param_label = None
            param_value = None

            if name.startswith("stat_"):
                stat_k = name[5:]
                if stat_k in stat_values:
                    param_key = f"stat_{stat_k}"
                    param_label = "参数值"
                    param_value = stat_values[stat_k].get()
            elif name in param_map:
                p_var_name, param_label = param_map[name]
                param_key = name
                param_value = self.port.value(p_var_name).get()

            # Categorize
            category = "general"
            if name.startswith("stat_"):
                category = "stats"
            elif name.startswith("fullscreen_"):
                category = "fullscreen"
            elif name in ("instant_move", "explode_unit", "clone_unit", "clone_to_self", "take_control", "mass_clone", "kill_owner_units"):
                category = "combat"
            elif name in ("reveal_map", "hide_map", "toggle_game_pause", "end_game", "rapid_build", "instant_victory", "game_speed", "add_resources"):
                category = "world"

            result.append({
                "name": name,
                "label": spec.label.split(None,1)[1] if len(spec.label.split(None,1))==2 else spec.label,
                "key": spec.label.split(None,1)[0],
                "enabled": enabled,
                "paramKey": param_key,
                "paramLabel": param_label,
                "paramValue": param_value,
                "isDangerous": name in dangerous_set,
                "category": category,
            })
        return result

    def set_hotkey_check(self, name: str, enabled: bool) -> dict[str, Any]:
        checks = self.port.value("elephant_hotkey_checks")
        if name in checks and name in self.port.value('hotkey_callbacks'):
            enabled = bool(enabled)
            self.app.save_ui_preferences(hotkey_checks={name: enabled})
            checks[name].set(enabled)
            return {**self._refresh_saved_hotkey_checks(), "name":name, "enabled":enabled}
        raise ValueError('找不到要设置的快捷键，请刷新全局快捷键列表。')

    def set_all_hotkeys_checks(self, enabled: bool) -> dict[str, Any]:
        callbacks = self.port.value('hotkey_callbacks')
        checks = self.port.value('elephant_hotkey_checks')
        choices = {name: bool(enabled and name in callbacks) for name in checks}
        self.app.save_ui_preferences(hotkey_checks=choices)
        for name, value in choices.items():
            checks[name].set(value)
        return {**self._refresh_saved_hotkey_checks(), "enabled":enabled, "hotkeys":self.get_all_hotkeys()}

    def _refresh_saved_hotkey_checks(self):
        result = {'success':True}
        if not self.offline and self.port.value('elephant_hotkeys_enabled').get():
            try:
                self.app.refresh_elephant_hotkeys()
            except Exception as err:
                err.user_title = '快捷键选项已保存，注册未完成'
                result['notice'] = self._failure(err,'set_hotkeys_enabled')['notice']
        return result

    def set_hotkey_parameter(self, param_key: str, value: str) -> dict[str, Any]:
        if param_key.startswith("stat_"):
            stat_k = param_key[5:]
            stat_values = self.port.value("elephant_stat_values")
            if stat_k in stat_values:
                self._set_saved_parameter(param_key, stat_values[stat_k], value)
                return {"success": True, "paramKey": param_key, "value": value}
        else:
            param_var_map = {
                "hero_level": "elephant_hero_level",
                "unit_scale": "elephant_unit_scale",
                "item_charges": "elephant_item_charges",
                "add_ability": "elephant_ability_rawcode",
                "add_resources": "elephant_resource_amount",
                "mass_clone": "elephant_mass_clone_count",
                "ability_level": "elephant_ability_level",
                "remove_ability": "elephant_ability_rawcode",
                "reinforcements": "elephant_reinforcement_rawcode",
                "preset_item": "elephant_preset_item_rawcode",
                "preset_tech": "elephant_preset_tech_rawcode",
                "hero_attributes": "elephant_hero_attributes",
                "skill_points": "elephant_skill_points",
                "xp_rate": "elephant_xp_rate",
                "reset_ability": "elephant_reset_ability_rawcode",
                "fullscreen_auto": "elephant_auto_effect_count",
                "game_speed": "elephant_game_speed",
            }
            if param_key in param_var_map:
                var_name = param_var_map[param_key]
                self._set_saved_parameter(var_name.removeprefix('elephant_'), self.port.value(var_name), value)
                return {"success": True, "paramKey": param_key, "value": value}

        raise ValueError('此快捷键的参数设置已失效，请刷新全局快捷键列表。')

    def trigger_hotkey(self, name: str) -> dict[str, Any]:
        callbacks = self.port.value("hotkey_callbacks")
        if name in callbacks:
            try:
                result = callbacks[name]()
                if name != 'read_unit':
                    self._mark_units_changed()
                return {"success": True, "name": name, "message": str(result or '操作完成')}
            except Exception as err:
                return {**self._failure(err,'elephant:hotkey:'+name), "name": name}
        raise ValueError('找不到要执行的快捷键功能，请刷新全局快捷键列表。')

    def _mark_units_changed(self):
        state = self.port.value('state')
        state['fields_need_refresh'] = True
        state['ability_field_snapshot'] = None
        state['item_field_snapshot'] = None
        state['item_effect_snapshot'] = None
        self.app.refresh_ability_field_tree()
        self.app.refresh_item_field_tree()

    # =========================================================================
    # 11-14. Search Catalogs
    # =========================================================================

    def start_map_catalog(self, path: str):
        return self._map_catalog_jobs.start(path)

    def get_map_script_options(self):
        from war3_script_features import FEATURES
        return dict(success=True, options=self._script_option_store.load().data(), features=FEATURES)

    def save_map_script_options(self, options: dict):
        from war3_script_features import ScriptOptions
        saved = self._script_option_store.save(ScriptOptions.parse(options))
        return dict(success=True, options=saved.data())

    def start_map_scripts(self, paths: list[str], output_folder: str='', options: dict | None=None, combined: bool=False):
        from war3_script_features import ScriptOptions
        config = self._script_option_store.load() if options is None else ScriptOptions.parse(options)
        self._script_option_store.save(config)
        return self._map_script_jobs.start(paths, output_folder, config.data(), combined)

    def get_map_script_progress(self, job_id: str=''):
        return self._map_script_jobs.snapshot(job_id)

    def cancel_map_scripts(self, job_id: str=''):
        return self._map_script_jobs.cancel(job_id)

    def get_map_catalog_progress(self, job_id: str = ''):
        return self._map_catalog_jobs.snapshot(job_id)

    def cancel_map_catalog(self, job_id: str = ''):
        return self._map_catalog_jobs.cancel(job_id)

    def search_map_catalog(self, job_id: str, kind: str = '', query: str = '', scope: str = '', change_type: str = '', offset: int = 0):
        return self._map_catalog_jobs.search(job_id,kind,query,scope,change_type,offset)

    def get_map_catalog_entry(self, job_id: str, row_id: str):
        return self._map_catalog_jobs.detail(job_id,row_id)

    def export_map_catalog(self, job_id: str, format: str = 'csv', kind: str = '', query: str = '', scope: str = '', change_type: str = ''):
        if format not in ('csv','json'):raise ValueError('请选择 CSV 或 JSON 导出格式。')
        self._map_catalog_jobs.snapshot(job_id)
        path=self.port.value('filedialog').asksaveasfilename(initialfile='地图自定义数据目录.'+format,
            file_types=('CSV (*.csv)',) if format=='csv' else ('JSON (*.json)',))
        if not path:return dict(success=False,cancelled=True)
        if not Path(path).suffix:path+='.'+format
        return self._map_catalog_jobs.export(job_id,path,kind,query,scope,change_type)

    def search_id_catalog(self, kind: str, query: str = "") -> dict[str, Any]:
        if kind not in ("item", "ability", "unit", "upgrade"):
            raise ValueError('此资料分类不可用，请从单位、物品、技能或科技中重新选择。')
        matches = search_id_entries(kind, query)
        # Limit matches to 200 for fast serialization
        rows = [
            {"rawcode": row.rawcode, "name_zh": row.name_zh, "name_en": row.name_en,
             "category": row.category_en if self.port.value('ui_language')['code']=='en' else row.category_zh,
             "description": (row.description_en or row.description_zh) if self.port.value('ui_language')['code']=='en' else (row.description_zh or row.description_en),
             "descriptionSource": 'Warcraft III 3.0.1.24371 base game data' if self.port.value('ui_language')['code']=='en' else row.description_source,
             "descriptionPartial": row.description_partial,
             **({"maxLevel": upgrade_max_level(row)} if kind == "upgrade" else {})}
            for row in matches[:200]
        ]
        return {
            "kind": kind,
            "totalCount": CATALOG_COUNTS.get(kind, 0),
            "matchCount": len(matches),
            "rows": rows,
        }


    def search_3_equipment(self, query: str = "") -> dict[str, Any]:
        matches = search_equipment(query)
        rows = [
            {"name": row["name"], "code": row["code"], "description": row["description"]}
            for row in matches[:200]
        ]
        return {
            "totalCount": len(EQUIPMENT),
            "matchCount": len(matches),
            "rows": rows,
        }

    def search_3_hero_skills(self, hero: str = "", query: str = "") -> dict[str, Any]:
        matches = search_skills(query, hero)
        rows = [
            {"hero": row["hero"], "name": row["name"], "code": row["code"], "levels": row["levels"], "description": row["description"]}
            for row in matches[:200]
        ]
        hero_names = ["全部角色"] + [name for _, name in HEROES]
        return {
            "heroes": hero_names,
            "totalCount": len(SKILLS),
            "matchCount": len(matches),
            "rows": rows,
        }

    # =========================================================================
    # 15. Batch Edit & Archive Extraction
    # =========================================================================

    def read_unit_fields(self) -> dict[str, Any]:
        trainer=self.port.value('state').get('trainer')
        if not trainer:raise ValueError('尚未连接游戏，请先连接后选择单位')
        service=self.services.UnitFieldsService(trainer,self.services.logger_factory)
        result=service.read()
        self._unit_field_service=service
        return result

    def write_unit_field_value(self,key: str,value: str) -> dict[str, Any]:
        service=getattr(self,'_unit_field_service',None)
        trainer=self.port.value('state').get('trainer')
        if service is None or service.host is not trainer:raise ValueError('请先读取当前单位字段')
        return service.write(key,value)

    def batch_read_units(self) -> dict[str, Any]:
        trainer = self.port.value("state").get("trainer")
        if not trainer:
            return {"success": False, "error": "尚未连接魔兽争霸 III 进程"}
        try:
            service = self.services.BatchEditService(trainer, self.services.logger_factory)
            model = self.services.BatchEditModel(service.read())
            self._batch_model = model
            units = [
                {"checked": True, "rawcode": self._format_code(u.ref.rawcode),
                 "instance": ':'.join(str(value) for value in u.identity),
                 "hp": next((f.value_text() for f in u.fields if f.key == 'hp_current'), ''),
                 "mp": next((f.value_text() for f in u.fields if f.key == 'mp_current'), ''), 'error': u.error}
                for u in model.snapshot.units
            ]
            options = [dict(key=f.key, label=f.label, category=f.category,
                            type=f.value_type, supported=f.supported) for f in model.field_options()]
            response = {"success": True, "units": units, 'fields': options}
            unreadable = [(index,row) for index,row in enumerate(units,1) if row['error']]
            if unreadable:
                from war3_error_messages import describe_error
                error = RuntimeError(f'已取得 {len(units)} 个目标，其中 {len(unreadable)} 个单位的部分字段没能读到。')
                error.user_title = '批量读取有单位未读完整'
                error.user_details = [dict(scope=f'第 {index} 个选中单位',file=row['rawcode'],
                    message=describe_error(RuntimeError(row['error']),operation='batch_read_units')['reason'])
                    for index,row in unreadable]
                response['notice'] = self._failure(error,'batch_read_units')['notice']
            return response
        except Exception as err:
            return self._failure(err)

    def batch_write_units(self, unit_instances: list[str], target_fields: dict[str, str]) -> dict[str, Any]:
        trainer = self.port.value("state").get("trainer")
        if not trainer:
            return {"success": False, "error": "尚未连接游戏进程"}
        try:
            model = self._batch_model
            if model is None:
                raise ValueError('请先读取批量单位')
            known = {':'.join(str(value) for value in u.identity): u for u in model.snapshot.units}
            if any(key not in known for key in unit_instances):
                raise ValueError('目标不属于本次读取，请重新读取')
            result = self.services.BatchEditService(trainer, self.services.logger_factory).apply(
                model.snapshot, tuple(known[key] for key in dict.fromkeys(unit_instances)), target_fields)
            reports = [dict(unit=':'.join(str(v) for v in row.unit.identity), field=row.key,
                            target=row.target, status=row.status, reason=row.reason, actual=row.actual)
                       for row in result.fields]
            failures = [row for row in result.fields if row.status == 'failed']
            if failures or result.stopped:
                reasons = {}
                for row in failures:
                    field=next((field.label for field in row.unit.fields if field.key==row.key),row.key)
                    key=(field,row.reason)
                    reasons[key]=reasons.get(key,0)+1
                error=RuntimeError(f'批量修改中有 {len(failures)} 项字段失败，已完成的修改保留。')
                error.user_details=[dict(scope='批量修改',file=f'{field}（{count} 项）',message=reason)
                    for (field,reason),count in reasons.items()]
                if result.stopped:
                    error.user_details.append(dict(scope='批量修改',file='后续字段未执行',message=result.stopped))
                error.diagnostic_log_path=result.log_path
                self._failure(error,'batch_write_units')
            return {'success': True, 'message': f'批量处理完成，共 {len(reports)} 项字段结果',
                    'reports': reports, 'stopped': result.stopped, 'logPath': result.log_path}
        except Exception as err:
            return self._failure(err,'batch_write_units')

    @staticmethod
    def _format_code(rawcode):
        from war3_contracts import format_rawcode
        return format_rawcode(rawcode)

    def scan_archive_directory(self, dir_path: str = "") -> dict[str, Any]:
        if not dir_path:
            dir_path = str(self.services.documents_directory() / "Warcraft III")
        p = Path(dir_path)
        if not p.is_dir():
            return {"success": False, "error": f"目录不存在: {dir_path}"}
        try:
            scan = self.services.find_archive_files(p)
            result = [{"name": row['name'], "path": row['path'], "date": str(row['modified_ns']/1_000_000_000)}
                      for row in scan['files'][:100]]
            response = {"success": True, "directory": dir_path, "files": result}
            if not scan['complete']:
                error = RuntimeError('只读取了部分存档。可选择具体的存档子目录再扫一次。')
                error.user_title='存档列表只读取了部分内容'
                error.user_details=[dict(scope='读取存档目录',file=row['source'],message=row['reason'])
                                    for row in scan['warnings']]
                response['notice']=self._failure(error,'scan_archive_directory')['notice']
            return response
        except Exception as err:
            return self._failure(err)

    def read_archive_file(self, file_path: str) -> dict[str, Any]:
        p = Path(file_path)
        if not p.is_file():
            return {"success": False, "error": f"文件不存在: {file_path}"}
        try:
            res = self.services.read_archive_file(p)
            rows = [{"scope": r[0], "key": r[1], "type": r[2], "value": r[3]} for r in self.services.display_rows(res)]
            return {"success": True, "filePath": file_path, "rows": rows}
        except Exception as err:
            return self._failure(err)

    def read_live_heroes(self) -> dict[str, Any]:
        trainer = self.port.value("state").get("trainer")
        if not trainer:
            return {"success": False, "error": "尚未连接游戏进程"}
        try:
            res = self.services.read_current_heroes(trainer)
            rows = [{"scope": r[0], "key": r[1], "type": r[2], "value": r[3]} for r in self.services.display_rows(res)]
            response = {"success": True, "rows": rows}
            if res.get('warnings'):
                from war3_error_messages import describe_error
                error=RuntimeError('已读取英雄资料，其中部分字段或物品没有读完整。')
                error.user_title='当前英雄资料只读取了部分内容'
                error.user_details=[dict(scope=row['section'],file=row['unit'],
                    message=describe_error(RuntimeError(row['reason']),operation='read_live_heroes')['reason'])
                    for row in res['warnings']]
                response['notice']=self._failure(error,'read_live_heroes')['notice']
            return response
        except Exception as err:
            return self._failure(err)

    def scan_rpg_codes_memory(self, prefix: str = "-load") -> dict[str, Any]:
        trainer = self.port.value("state").get("trainer")
        if not trainer:
            return {"success": False, "error": "尚未连接游戏进程"}
        try:
            codes = self.services.read_live_codes(trainer, prefix)
            rows = [{"kind": "游戏内存扫描", "code": c.code, "source": f"内存匹配 ({c.evidence})"} for c in codes]
            return {"success": True, "rows": rows}
        except Exception as err:
            return self._failure(err)

    def parse_rpg_codes_text(self, text: str, prefix: str = "-load") -> dict[str, Any]:
        try:
            codes = self.services.extract_text(text, prefix)
            rows = [{"kind": "剪贴板/文本提取", "code": c.code, "source": "文本分析"} for c in codes]
            return {"success": True, "rows": rows}
        except Exception as err:
            return self._failure(err)


def _serialized_api(method):
    @wraps(method)
    def invoke(self, *args, **kwargs):
        with self.port.dispatch_lock, _failure_scope():
            if getattr(self, 'offline', False):
                if method.__name__ == 'read_selected_unit':
                    return self._unit_snapshot()
                if method.__name__ == 'refresh_extension_status':
                    return method(self, False)
                if method.__name__ not in {'get_system_status', 'get_all_hotkeys', 'get_artifact_plan',
                    'get_resource_snapshot', 'get_selected_unit_snapshot', 'get_unit_candidates_snapshot', 'get_locks', 'set_ui_language',
                    'search_id_catalog', 'search_3_equipment', 'search_3_hero_skills',
                    'prepare_backpack_definitions', 'start_backpack_definitions', 'choose_definition_file',
                    'start_backpack_definitions_batch', 'choose_definition_files',
                    'start_map_catalog','export_map_catalog',
                    'get_map_script_options','save_map_script_options','start_map_scripts',
                    'choose_definition_folder', 'save_artifact_plan', 'restore_default_artifact_plan',
                    'get_elephant_parameters', 'set_elephant_parameter', 'set_hotkeys_enabled',
                    'set_hotkey_check', 'set_all_hotkeys_checks', 'set_hotkey_parameter', 'close'}:
                    raise RuntimeError('离线界面验收：未连接游戏')
            outer = getattr(self, '_api_depth', 0) == 0
            self._api_depth = getattr(self, '_api_depth', 0) + 1
            if outer:
                self._active_api_operation = method.__name__
                selector = args[0] if args else kwargs.get('action',kwargs.get('action_name'))
                self._active_action_title = _ACTION_TITLES.get(method.__name__,{}).get(selector,'') if isinstance(selector,str) else ''
                self.port.dialog_error = None
                self.port.dialog_notice = None
                self.port.cancelled = False
            try:
                result = method(self, *args, **kwargs)
                if outer and self.port.dialog_error:
                    exc=RuntimeError(self.port.dialog_error)
                    notice=self.port.dialog_notice
                    if notice:
                        _failure_cache.get()[id(exc)]=(exc,dict(success=False,error=notice['message'],
                            notificationId=notice['id'],logPath=notice['logPath'],notice=notice))
                    raise exc
                if outer and self.port.cancelled:
                    return {'success': False, 'cancelled': True, 'error': '操作已取消'}
                if outer and isinstance(result,dict) and result.get('success') is False and not result.get('cancelled') and not result.get('notificationId'):
                    exc=RuntimeError(result.get('error') or '操作未完成')
                    if result.get('logPath'):exc.diagnostic_log_path=result['logPath']
                    failure=self._failure(exc,method.__name__)
                    result={**result,**failure,'logPath':result.get('logPath') or failure['logPath']}
                return result
            except Exception as exc:
                if outer:
                    self._failure(exc,method.__name__)
                raise
            finally:
                self._api_depth -= 1
                if outer:
                    del self._active_api_operation
                    del self._active_action_title
    invoke.__signature__ = inspect.signature(method)
    return invoke


for _name, _method in tuple(vars(DesktopBridgeApi).items()):
    if not _name.startswith('_') and callable(_method) and _name not in {
        'cancel_discovery','get_ui_notifications','get_backpack_definition_progress','cancel_backpack_definitions',
        'get_map_catalog_progress','cancel_map_catalog','search_map_catalog','get_map_catalog_entry',
        'get_map_script_progress','cancel_map_scripts'} and not isinstance(_method, staticmethod):
        setattr(DesktopBridgeApi, _name, _serialized_api(_method))


class DesktopRpcFacade:
    """Expose explicit RPC methods without walking application/service objects."""
    def __init__(self, bridge, startup=None):
        self._bridge = bridge
        self._startup = startup
        for name, method in vars(DesktopBridgeApi).items():
            if not name.startswith('_') and callable(method) and name != 'close':
                bound=getattr(bridge,name)
                def export(bound):
                    @wraps(bound)
                    def invoke(*args,**kwargs):
                        with _failure_scope():
                            try:return bound(*args,**kwargs)
                            except Exception as exc:return bridge._failure(exc,bound.__name__)
                    invoke.__signature__=inspect.signature(bound)
                    return invoke
                setattr(self, name, export(bound))

    def report_frontend_state(self, stage, details=None):
        # Startup health must not wait for the gameplay operation lock.
        if self._startup is None:
            return {'accepted': False}
        result = self._startup.report(stage, details)
        if stage == 'runtime_error' and result.get('accepted'):
            if self._bridge.port.has_pending_error('界面处理报错'):
                return result
            self._bridge.port.publish_error(
                '界面代码在处理当前页面时中断。请先核对页面或游戏的当前结果，再重新打开修改器。',
                title='界面处理报错', log_path=self._startup.log_path,
            )
        return result
