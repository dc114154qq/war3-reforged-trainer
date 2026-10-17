"""Sequential skill bundles: report a rejected skill and continue independent ones."""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass


@dataclass(frozen=True)
class BundleFailure:
    rawcode: int
    level: int
    reason: str
    reason_en: str
    business_error: int
    log_path: str


class AbilityBundleResult(tuple):
    """Keep the published (changed, total) unpacking API; add per-request details."""
    def __new__(cls, changed, total, failures=(), log_path=''):
        result = super().__new__(cls, (changed, total))
        result.failures = tuple(failures)
        result.log_path = log_path
        return result


def _inventory_alias(report, rawcode):
    if rawcode != int.from_bytes(b'AInv', 'big'):
        return None
    journal = report.get('native_call_journal') or {}
    if journal.get('complete') is not True or journal.get('dropped_count') != 0:
        return None
    calls = journal.get('calls') or ()
    if any(call.get('native') in ('UnitAddAbility', 'SetUnitAbilityLevel', 'UnitRemoveAbility') for call in calls):
        return None
    handles = {call.get('result_raw') for call in calls
               if call.get('native') == 'BlzGetUnitAbility' and call.get('returned') is True
               and call.get('arguments', [0, 0])[1] == rawcode and call.get('result_raw')}
    aliases = {call.get('result_raw') for call in calls
               if call.get('native') == 'BlzGetAbilityId' and call.get('returned') is True
               and call.get('arguments', [0])[0] in handles
               and type(call.get('result_raw')) is int and 0 < call['result_raw'] <= 0xffffffff
               and call['result_raw'] != rawcode}
    if len(aliases) == 1:
        value = next(iter(aliases)).to_bytes(4, 'big')
        if all(32 <= char < 127 for char in value):
            return value.decode('ascii')
    return None


def _released_skill_failure(exc, rawcode, level):
    report = getattr(exc, 'report', None)
    if not isinstance(report, dict) or report.get('operation') != 'ability':
        return False
    status = report.get('ability_status') or {}
    dispatch = report.get('dispatch') or {}
    verification = report.get('verification') or {}
    # A changed selection/session is a batch boundary, rather than a skipped
    # skill. The failing skill is never replayed, including partial failures.
    return (
        report.get('request', {}).get('rawcode') == rawcode
        and report.get('request', {}).get('action') == 1
        and report.get('request', {}).get('level') == level
        and status.get('error') in (25, 26, 29, 34, 35, 36, 37)
        and dispatch.get('callback_exited') is True
        and dispatch.get('cleanup_verified') is True
        and verification.get('cleanup_complete') is True
        and verification.get('callback_exited') is True
    )


def run_indexed_bundle(host, bundle):
    from war3_error_messages import describe_error
    from war3_game_session import GameSession, SessionError
    from war3_services.operation_trace import SkillTrace, active_trace

    session = getattr(host, '_game_session', None)
    identity = (session.identity, session.epoch) if isinstance(session, GameSession) else None
    manager = nullcontext(active_trace())
    if isinstance(session, GameSession) and active_trace() is None:
        from war3_reforged_trainer import Win10ReadLogger
        manager = SkillTrace(host, Win10ReadLogger,
                            dict(operation='ability_bundle', entries=bundle,
                                 failure_policy='skip_released_skill_rejection_without_replay'))
    changed, failures = 0, []
    with manager as trace:
        for index, (rawcode, requested) in enumerate(bundle):
            if identity is not None and ((session.identity, session.epoch) != identity
                                         or session.closed or session.retained):
                raise SessionError('进程、地图或执行状态已变化，本轮技能组合已停止，请重新读取目标。')
            # 112 is the historical default-level sentinel, not a real level.
            level = 0 if requested == 112 else requested or 0
            if trace is not None:
                trace.record('bundle_entry_begin', index=index, rawcode=rawcode,
                             level=level, successful_changed=changed)
            try:
                result = host.ability_batch_24268(rawcode, 1, level)
            except Exception as exc:
                if not _released_skill_failure(exc, rawcode, level):
                    if trace is not None:
                        trace.record('bundle_stopped', index=index, rawcode=rawcode,
                                     execution_report=getattr(exc, 'report', None),
                                     successful_changed=changed, skipped=failures)
                    raise
                details = describe_error(exc, 'zh')
                english = describe_error(exc, 'en')
                report = exc.report
                alias = _inventory_alias(report, rawcode)
                if alias:
                    details = dict(details, reason=f'请求普通背包时，游戏返回地图技能 {alias}，该项已保留并跳过。')
                    english = dict(english, reason=f'The inventory query returned map skill {alias}; it was preserved and skipped.')
                path = (report.get('operation_trace') or {}).get('log_path', '') or getattr(trace, 'log_path', '') or ''
                failures.append(BundleFailure(rawcode, level, details['reason'], english['reason'],
                                              report['ability_status']['error'], path))
                if trace is not None:
                    trace.record('bundle_entry_skipped', index=index, rawcode=rawcode,
                                 reason=details, execution_report=report,
                                 repeated=False, continue_with_next_skill=True)
                continue
            changed += int(result['changed'])
            if trace is not None:
                trace.record('bundle_entry_complete', index=index, rawcode=rawcode, readback=result)
        path = getattr(trace, 'log_path', '') or ''
        if trace is not None:
            trace.finish(dict(changed=changed, total=len(bundle), completed=len(bundle)-len(failures),
                              skipped=failures, all_skills_verified=not failures,
                              automatic_replays=0))
        return AbilityBundleResult(changed, len(bundle), failures, path)


def format_bundle_outcome(label, results, language='zh'):
    results = tuple(results)
    failures = tuple(failure for result in results for failure in getattr(result, 'failures', ()))
    if not failures:
        return None
    changed = sum(result[0] for result in results)
    total = sum(result[1] for result in results)
    codes = ', '.join(dict.fromkeys(f.rawcode.to_bytes(4, 'big').decode('ascii', 'replace') for f in failures))
    paths = tuple(dict.fromkeys(result.log_path for result in results if getattr(result, 'log_path', '')))
    if language == 'en':
        name = {'全被动': 'All passives', '全光环': 'All auras'}.get(label, label)
        text = f'{name}: verified {total-len(failures)}/{total} skills; skipped {len(failures)}; confirmed changes {changed}. Skipped: {codes}.'
        return text + (f' Details: {paths[-1]}' if paths else '')
    text = f'{label}：完成 {total-len(failures)}/{total} 项，跳过 {len(failures)} 项，确认修改 {changed} 项。跳过：{codes}。'
    return text + (f' 详情：{paths[-1]}' if paths else '')
