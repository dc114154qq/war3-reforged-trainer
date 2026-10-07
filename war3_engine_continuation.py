"""Bounded continuation of an owned effect, never replay of its cast order.

Transport owns the non-execution proof. Services supply the captured instance
and session epoch; this backend neither chooses a route nor changes profiles.
"""
from copy import deepcopy
import time


def unstarted_continuation_proven(engine, error, epoch):
    from war3_engine_transport import never_started_cleanup_complete
    session = engine.session
    report = getattr(error, 'report', None)
    if (not isinstance(report, dict) or report is not getattr(engine, 'last_report', None)
            or report.get('pid') != getattr(engine, 'pid', None) or session.epoch != epoch
            or session.closed or session.uncertain or session.retained
            or engine.quarantined):
        return False
    dispatch = report.get('dispatch') or {}
    if not (dispatch.get('unstarted_cleanup_verified') is True
            and dispatch.get('callback_received') is False
            and dispatch.get('query_completed') is False
            and dispatch.get('cleanup_verified') is True
            and dispatch.get('safe_to_release') is True
            and not dispatch.get('allocations_retained')
            and dispatch.get('work_freed') is True
            and dispatch.get('block_freed') is True
            and dispatch.get('image_unmap_status') == '0x0'):
        return False
    return never_started_cleanup_complete(
        (dispatch.get('install_thread') or {}).get('completed') is True,
        dispatch.get('after_cleanup') or {}, dispatch.get('callback_lifecycle'))


def run_continuation(engine, action, call, *, epoch):
    """Only action 3 observation/action 2 exact-instance teardown may wait.

    The original action 1 is outside this API. A timeout after callback entry,
    partial mutation, retained mapping or changed context is never retried.
    At most two extra attempts are allowed, and normal calls incur no delay.
    """
    if action not in (2, 3):
        raise ValueError('Only observation or exact-instance cleanup may continue')
    failures = []
    for attempt in range(3):
        if engine.session.epoch != epoch:
            raise RuntimeError('Held effect context changed; original cleanup remains unverified')
        try:
            result = call()
        except Exception as error:
            if attempt == 2 or not unstarted_continuation_proven(engine, error, epoch):
                report = getattr(error, 'report', None)
                if failures and isinstance(report, dict):
                    report['continuation'] = dict(action=action, attempts=attempt+1,
                        failures=failures, completed=False)
                raise
            failures.append(dict(error=deepcopy(error.report)))
            time.sleep((1.0, 5.0)[attempt])
        else:
            if failures:
                engine.last_report['continuation'] = dict(action=action,
                    attempts=attempt+1, failures=failures, completed=True)
            return result
