"""Operation-local inventory reads and definition checks for loadout restoration."""
from contextvars import ContextVar
from contextlib import contextmanager
from time import perf_counter

_RESTORE = ContextVar('war3_loadout_restore', default=None)


def current_restore(host):
    value = _RESTORE.get()
    return value if value is not None and value.host is host else None


class RestoreRuntime:
    def __init__(self, host, target, name):
        self.host, self.target, self.name = host, int(target), name
        self.definitions = {}
        self.effect_refresh_needed = False
        self.started = perf_counter()
        self.logger = None
        self.snapshot_count = 0
        self.refresh_result = None

    def record(self, phase, **values):
        if self.logger is not None:
            try:
                self.logger.log('loadout_phase', phase=phase, target_unit=self.target,
                    elapsed_ms=round((perf_counter()-self.started)*1000, 3), **values)
            except OSError:
                pass

    def inventory(self, target=0):
        if target and int(target) != self.target:
            raise RuntimeError('套装恢复目标发生变化，已停止后续操作')
        # Every read is fresh. No inventory result survives a callback or a frame.
        snapshot = self.host._engine_instance_24268().extension(target_unit=self.target)
        if int(snapshot['target_unit']) != self.target:
            raise RuntimeError('套装恢复读回了其他目标，已停止后续操作')
        self.snapshot_count += 1
        override = getattr(self.host, '_elephant_selection_override', None)
        if override is not None:
            selection = dict(snapshot['selection'])
            selection['rows'] = tuple(r for r in selection['rows'] if int(r['handle']) == self.target)
            snapshot['selection'] = selection
        snapshot['loadout_names'] = self.host.extension_loadout_names_24268()
        return snapshot

    def mutation_snapshot(self, result):
        if int(result.get('target_unit', 0)) != self.target:
            raise RuntimeError('套装物品操作后目标变化，已停止后续操作')
        if not all(k in result for k in ('bag', 'equipment', 'selection', 'bag_size')):
            return self.inventory()
        result['loadout_names'] = self.host.extension_loadout_names_24268()
        return result


@contextmanager
def restore_scope(host, target, name):
    parent = current_restore(host)
    if parent is not None:
        if parent.target != int(target):
            raise RuntimeError('套装恢复期间目标变化')
        yield parent
        return
    runtime = RestoreRuntime(host, target, name)
    token = _RESTORE.set(runtime)
    from war3_game_session import GameSession
    if isinstance(getattr(host, '_game_session', None), GameSession):
        from war3_backend import Win10ReadLogger
        try:
            runtime.logger = Win10ReadLogger(host.pid, prefix='loadout', target_hwnd=host.hwnd)
        except OSError:
            pass
    runtime.record('start', name=name, strategy='fresh_inventory_only', automatic_any_slot=True)
    try:
        yield runtime
    except Exception as exc:
        runtime.record('failed', reason=str(exc), placement_report=getattr(exc, 'report', None))
        raise
    finally:
        _RESTORE.reset(token)
        try:
            if runtime.effect_refresh_needed:
                from war3_services.facade_extensions import _refresh_extension_equipment_effects
                runtime.refresh_result = _refresh_extension_equipment_effects(host, runtime.target)
                runtime.record('equipment_effect_refresh', result=runtime.refresh_result)
            runtime.record('end', inventory_reads=runtime.snapshot_count)
        finally:
            if runtime.logger is not None:
                runtime.logger.close()
