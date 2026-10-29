"""Comprehensive, Zero-Mock Desktop Bridge connecting Web UI to TrainerApplication and DesktopServices."""
from __future__ import annotations

import os
import sys
import json
import logging
import threading
import inspect
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
from war3_id_catalog import CATALOG_COUNTS, search_id_entries
from war3_field_labels import ability_field_search_text, item_field_search_text
from war3_new_equipment_catalog import EQUIPMENT

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
        self._original_set_status=self.app.set_status
        self.app.set_status=self._set_status
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
        except Exception:
            logger.exception('Desktop failure log write failed')

    def _failure(self,exc,operation='desktop_action'):
        payload=getattr(exc,'_desktop_failure',None)
        if payload:return payload
        from war3_error_messages import format_error
        path=self._log_failure(operation,exc)
        if path and not getattr(exc,'diagnostic_log_path',None):
            try:exc.diagnostic_log_path=path
            except Exception:pass
        message=format_error(exc,self.port.value('ui_language')['code'])
        details=getattr(exc,'user_details',None) if operation in ('map_object_catalog','map_script_tools') else None
        notice=self.port.publish_error(message,title=getattr(exc,'user_title','操作未完成') if details else '操作未完成',
            log_path=getattr(exc,'diagnostic_log_path',''),details=details)
        payload=dict(success=False,error=message,logPath=notice['logPath'],notificationId=notice['id'])
        try:exc._desktop_failure=payload
        except Exception:pass
        return payload

    def _set_status(self,text):
        # These workers report failures through status instead of call_async.
        # Keep their failure visible in the same desktop notification channel.
        source=str(text)
        if source.startswith(('锁定失败：','我方锁血已停止：','持续快速建造/升级已停止：')):
            payload=self._failure(RuntimeError(source),'background_guard')
            source=payload['error'].split('\n',1)[0]
        self._original_set_status(source)

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
        self.port.value("elephant_hotkeys_enabled").set(bool(enabled))
        try:
            self.app.refresh_elephant_hotkeys()
            status_text = "全局快捷键已启用" if enabled else "全局快捷键已禁用"
            self.port.value("elephant_hotkey_status").set(status_text)
            return {"success": True, "enabled": enabled, "status": status_text}
        except Exception as err:
            return self._failure(err)

    def set_ui_language(self, lang: str) -> dict[str, Any]:
        if lang in ("zh", "en"):
            self.port.value("ui_language")["code"] = lang
            self.port.value("status").refresh()
            self.port.value("elephant_hotkey_status").refresh()
            if self.port.window and hasattr(self.port.window,'set_title'):
                title=(f'Warcraft III Reforged Trainer v{APP_VERSION} ({PRODUCT_EDITION_LABEL}) by Bilibili Two Cups of Shen Mengxi'
                       if lang=='en' else f'魔兽争霸 III 修改器 v{APP_VERSION} ({PRODUCT_EDITION_LABEL}) by B站两杯沈梦溪')
                self.port.window.set_title(title)
            from war3_ui_i18n import _EN_TRANSLATIONS
            return {"success": True, "language": lang, 'translations': _EN_TRANSLATIONS}
        return {"success": False, "error": "Unsupported language"}

    # =========================================================================
    # 2. Player Resources
    # =========================================================================

    def get_resource_snapshot(self) -> dict[str, Any]:
        tree: VirtualTree = self.port.value("resource_tree")
        groups = tree.to_list_of_dicts()
        return {
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
                return {**self._failure(RuntimeError('部分金矿未完成修改，请查看下方逐项结果；已完成的金矿保留。'),'gold_mines'),
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
            return {"success": False, "error": f"Unknown resource kind: {kind}"}
        return {"success": True, "data": self.get_resource_snapshot()}

    def add_resource(self, kind: str, delta: str | None = None) -> dict[str, Any]:
        if delta is not None:
            self.port.value("resource_delta").set(delta)
        self.app.add_resource(kind)
        return {"success": True, "data": self.get_resource_snapshot()}

    def add_resource_lock(self, kind: str) -> dict[str, Any]:
        self.app.add_resource_lock(kind)
        return {"success": True, "locks": self.get_locks()}

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
            return {"success": True, "data": self.read_ability_fields(
                self.port.value("ability_field_rawcode").get(),
                self.port.value("ability_field_level").get(),
            )}
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
            return {"success": True, "data": self.read_item_fields(str(int(self.port.value("item_field_slot").get()) - 1))}
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
            try:
                current = self.app.read_item_effect_field_snapshot(snapshot.source.area, snapshot.source.slot, snapshot.level)
                state['item_effect_snapshot'] = current
                return {'success': True, 'data': self.app.item_effect_fields_view(current)}
            except Exception as exc:
                payload = self._failure(RuntimeError('物品数值已写入并读回；刷新列表时发生错误，请重新读取。'+str(exc)), 'refresh_item_effect_fields')
                return dict(payload, write_completed=True)
        except Exception as exc:
            state['item_effect_snapshot'] = None
            return self._failure(exc, 'write_item_effect_field')

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
            'loadoutNames': list(getattr(self.port.value('extension_loadout_box'), 'values', ())),
            'talentChoices': list(getattr(self.port.value('extension_talent_choice_box'), 'values', ())),
            'loadoutWarnings': {key: value for key, value in (self.port.value('state').get('extension_snapshot') or {}).items()
                                if key in ('loadout_charge_mismatches', 'loadout_postcondition_warning')},
        }

    def extension_bag_action(self, action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        try:
            if action == "add_item":
                self.port.value("extension_item_rawcode").set(params.get("rawcode", ""))
                self.port.value("extension_item_charges").set(str(params.get("charges", "1")))
                self.app.extension_add_item()
            elif action == "set_charges":
                row_iid = params.get("row_iid", "")
                self.port.value("extension_bag_tree").selection_set(row_iid)
                self.port.value("extension_item_charges").set(str(params.get("charges", "1")))
                self.app.extension_set_bag_charges()
            elif action == "duplicate":
                self.port.value("extension_bag_tree").selection_set(params.get("row_iid", ""))
                self.app.extension_duplicate_bag_item()
            elif action == "drop":
                self.port.value("extension_bag_tree").selection_set(params.get("row_iid", ""))
                self.app.extension_drop_clicked()
            elif action == "destroy":
                self.port.value("extension_bag_tree").selection_set(params.get("row_iid", ""))
                self.app.extension_destroy_clicked("bag")
            elif action == "repair_item":
                self.port.value("extension_bag_tree").selection_set(params.get("row_iid", ""))
                self.app.extension_repair_bag_item()
            elif action == "add_official_backpack":
                choice = params.get("choice", "")
                if choice:
                    self.port.value("extension_backpack_choice").set(choice)
                self.app.extension_add_backpack_equipment()
            else:
                raise ValueError(f'Unknown backpack action: {action}')
            return {"success": True, "data": self.refresh_extension_status(False)}
        except Exception as err:
            return self._failure(err)

    def extension_equipment_action(self, action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        message = ''
        try:
            if action == "unequip":
                self.port.value("extension_equipment_tree").selection_set(params.get("row_iid", ""))
                self.app.extension_unequip_item()
            elif action == "destroy":
                self.port.value("extension_equipment_tree").selection_set(params.get("row_iid", ""))
                self.app.extension_destroy_clicked("equipment")
            elif action == "save_loadout":
                name = params.get("name", "套装1")
                self.port.value("extension_loadout_name").set(name)
                message = self.app.extension_save_loadout()
            elif action == "restore_loadout":
                name = params.get("name", "")
                if 'name' in params:
                    self.port.value("extension_loadout_choice").set(name)
                message = self.app.extension_restore_loadout()
            elif action == "save_all_loadouts":
                if 'name' in params:
                    self.port.value("extension_loadout_name").set(params['name'])
                message = self.app.extension_save_all_loadouts()
            elif action == "restore_all_loadouts":
                if 'name' in params:
                    self.port.value("extension_loadout_choice").set(params['name'])
                message = self.app.extension_restore_all_loadouts()
            elif action == "audit":
                self.app.extension_audit_equipment()
            elif action == "repair_misplaced":
                self.app.extension_repair_equipment_clicked()
            elif action == "equip_bag_to_slot":
                self.port.value('extension_bag_tree').selection_set(params.get('bag_row_iid', ''))
                self.port.value('extension_equipment_tree').selection_set(params.get('row_iid', ''))
                self.app.extension_equip_bag_to_slot()
            elif action == "enable_any_slot":
                self.app.extension_enable_any_slot()
            elif action == "repair_state":
                self.app.extension_repair_equipment_state()
            elif action == 'export_loadouts':
                self.app.extension_export_plans()
            elif action == 'import_loadouts':
                self.app.extension_import_plans()
            else:
                raise ValueError(f'Unknown equipment action: {action}')
            return {"success": True, 'message': message, "data": self.refresh_extension_status(False)}
        except Exception as err:
            return self._failure(err)

    def extension_talent_action(self, action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
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
                self.app.extension_add_talent_choice()
            elif action == "grant_point":
                self.app.extension_grant_talent_point()
            elif action == "reset_talents":
                self.app.extension_reset_talents_clicked()
            elif action == 'select_tier':
                pass
            else:
                raise ValueError(f'Unknown talent action: {action}')
            return {"success": True, "data": self.refresh_extension_status(False)}
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
            self._log_failure('prepare_backpack_definitions', err)
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
                return {"success": False, "error": f"Unknown action: {action_name}"}

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
        self.port.value('elephant_'+key).set(str(value))
        return dict(success=True,changedParameters={key:str(value)})

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
            return {"success": False, "error": f"保存失败: {err}"}

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
        if name in checks:
            checks[name].set(bool(enabled))
            if self.port.value("elephant_hotkeys_enabled").get():
                try:
                    self.app.refresh_elephant_hotkeys()
                except Exception as err:
                    logger.warning("refresh_elephant_hotkeys: %s", err)
            return {"success": True, "name": name, "enabled": enabled}
        return {"success": False, "error": f"Unknown hotkey: {name}"}

    def set_all_hotkeys_checks(self, enabled: bool) -> dict[str, Any]:
        self.app.set_all_elephant_hotkeys(enabled)
        return {"success": True, "enabled": enabled, "hotkeys": self.get_all_hotkeys()}

    def set_hotkey_parameter(self, param_key: str, value: str) -> dict[str, Any]:
        if param_key.startswith("stat_"):
            stat_k = param_key[5:]
            stat_values = self.port.value("elephant_stat_values")
            if stat_k in stat_values:
                stat_values[stat_k].set(value)
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
                self.port.value(var_name).set(value)
                return {"success": True, "paramKey": param_key, "value": value}

        return {"success": False, "error": f"Unknown param key: {param_key}"}

    def trigger_hotkey(self, name: str) -> dict[str, Any]:
        callbacks = self.port.value("hotkey_callbacks")
        if name in callbacks:
            try:
                result = callbacks[name]()
                if name != 'read_unit':
                    self._mark_units_changed()
                return {"success": True, "name": name, "message": str(result or '操作完成')}
            except Exception as err:
                return {**self._failure(err,'trigger_hotkey'), "name": name}
        return {"success": False, "error": f"Hotkey callback not found: {name}"}

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
            return {"success": False, "error": f"Invalid catalog kind: {kind}"}
        matches = search_id_entries(kind, query)
        # Limit matches to 200 for fast serialization
        rows = [
            {"rawcode": row.rawcode, "name_zh": row.name_zh, "name_en": row.name_en,
             "category": row.category_en if self.port.value('ui_language')['code']=='en' else row.category_zh,
             "description": (row.description_en or row.description_zh) if self.port.value('ui_language')['code']=='en' else (row.description_zh or row.description_en),
             "descriptionSource": 'Warcraft III 3.0.1.24371 base game data' if self.port.value('ui_language')['code']=='en' else row.description_source,
             "descriptionPartial": row.description_partial}
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
            return {"success": True, "units": units, 'fields': options}
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
            files = self.services.find_archive_files(p)
            result = [{"name": f.name, "path": str(f), "date": str(f.stat().st_mtime)} for f in files[:100]]
            return {"success": True, "directory": dir_path, "files": result}
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
            return {"success": True, "rows": rows}
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
        with self.port.dispatch_lock:
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
                    'get_elephant_parameters', 'set_elephant_parameter', 'close'}:
                    raise RuntimeError('离线界面验收：未连接游戏')
            outer = getattr(self, '_api_depth', 0) == 0
            self._api_depth = getattr(self, '_api_depth', 0) + 1
            if outer:
                self.port.dialog_error = None
                self.port.dialog_notice = None
                self.port.cancelled = False
            try:
                result = method(self, *args, **kwargs)
                if outer and self.port.dialog_error:
                    exc=RuntimeError(self.port.dialog_error)
                    notice=self.port.dialog_notice
                    if notice:exc._desktop_failure=dict(success=False,error=notice['message'],notificationId=notice['id'],logPath=notice['logPath'])
                    raise exc
                if outer and self.port.cancelled:
                    return {'success': False, 'cancelled': True, 'error': '操作已取消'}
                if outer and isinstance(result,dict) and result.get('success') is False and not result.get('cancelled') and not result.get('notificationId'):
                    failure=self._failure(RuntimeError(result.get('error') or '操作未完成'),method.__name__)
                    result={**result,**failure,'logPath':result.get('logPath') or failure['logPath']}
                return result
            except Exception as exc:
                if outer:
                    self._failure(exc,method.__name__)
                raise
            finally:
                self._api_depth -= 1
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
    def __init__(self, bridge):
        self._bridge = bridge
        for name, method in vars(DesktopBridgeApi).items():
            if not name.startswith('_') and callable(method) and name != 'close':
                bound=getattr(bridge,name)
                def export(bound):
                    @wraps(bound)
                    def invoke(*args,**kwargs):
                        try:return bound(*args,**kwargs)
                        except Exception as exc:return bridge._failure(exc,bound.__name__)
                    invoke.__signature__=inspect.signature(bound)
                    return invoke
                setattr(self, name, export(bound))
