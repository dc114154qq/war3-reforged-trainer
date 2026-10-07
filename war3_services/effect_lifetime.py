"""A held effect belongs to one session and one typed source identity."""
import time
import math
import sys
from war3_engine_continuation import run_continuation, unstarted_continuation_proven
from war3_game_session import ObjectAddress
from war3_object_registry import ObjectRegistry24268


class HeldEffectCleanupError(RuntimeError):
    def __init__(self, primary, cleanup, *, deferred=False):
        super().__init__('技能已发送，但游戏暂未接收清理请求；下次先清理原技能，不会重复施放，其他读取可继续'
            if deferred else '全屏技能清理状态不确定，未重复施放；请保留诊断日志')
        self.primary_error=primary
        self.cleanup_error=cleanup
        self.report=dict(getattr(primary,'report',None) or getattr(cleanup,'report',None) or {})
        self.report['held_effect_cleanup']={
            'primary_error':repr(primary), 'cleanup_error':repr(cleanup),
            'cleanup_report':getattr(cleanup,'report',None), 'deferred':deferred}


def full_map_area(engine):
    bounds=engine.map_bounds()
    left,right,bottom,top=(float(bounds[k]) for k in ('min_x','max_x','min_y','max_y'))
    if not all(math.isfinite(v) for v in (left,right,bottom,top)) or right<=left or top<=bottom:
        raise RuntimeError('当前地图边界读回无效，未施放全屏雷霆一击')
    radius=math.hypot(right-left,top-bottom)+32.0
    if radius>100000.0:raise RuntimeError('当前地图超出原生全屏技能支持的范围，未施放')
    return radius


class HeldEffect:
    def __init__(self, engine, rawcode, state):
        self.engine, self.rawcode, self.state = engine, rawcode, state
        self.closed = False
        with engine.memory_factory(engine.pid) as memory:
            registry = ObjectRegistry24268.attach(memory)
            owner = registry.resolve_handle(memory, state['unit_full'])
            self.ref = engine.session.bind_unit(memory, registry,
                ObjectAddress(memory.read_u64(owner+registry.layout['owner_data'])))

    def close(self):
        if self.closed:
            return dict(closed=True)
        if self.engine.session.epoch != self.ref.epoch:
            raise RuntimeError('Held effect context changed; original cleanup remains unverified')
        result = run_continuation(self.engine, 2,
            lambda: self.engine.direct_cast(self.rawcode, 2, mode=self.state['mode'],
                passes=self.state['passes'], state=self.state), epoch=self.ref.epoch)
        self.closed = True
        return result


def verify_cast_started(state, observed):
    """Order delivery/readback is not proof that damage reached an enemy."""
    for name in ('source', 'ability_handle', 'unit_full', 'ability_full',
                 'ability_data', 'level_index'):
        if observed.get(name) != state.get(name):
            raise RuntimeError('施法单位或技能实例已改变，本次施法未确认')
    before = float(state['mana_before'])
    after = float(observed['mana_after'])
    cooldown = float(observed['cooldown_after'])
    if not all(math.isfinite(v) for v in (before, after, cooldown)):
        raise RuntimeError('技能法力或冷却读回无效，本次施法未确认')
    observed_start = cooldown > 0.01 or after < before - 0.01
    if not observed_start and state.get('invoked') != 1:
        raise RuntimeError('施法结果未确认，且未读到法力或冷却变化')
    # Maps/cheats can have zero costs, zero cooldown or a completed instant
    # order. Native invocation + identity readback is delivery, not damage.
    return dict(command_delivered=True, state_readback=True,
                cast_started=True if observed_start else None,
                actual_effect_verified=False,
                mana_or_cooldown_changed=observed_start)


def run_held_effect(engine, rawcode, mode, passes, area, duration):
    # Repeated native orders in a single callback replace each other before
    # simulation advances. Each requested pass needs its own yield/readback
    # and exact-instance cleanup; never replay a failed/uncertain pass.
    if isinstance(passes, bool) or not isinstance(passes, int) or not 1 <= passes <= 255:
        raise ValueError('全屏技能次数必须为 1 到 255 的整数')
    results = []
    with engine.session.lock:
        for _ in range(passes):
            results.append(_run_one_held_effect(engine, rawcode, mode, area, duration))
    return dict(passes=results, completed=len(results))


def _run_one_held_effect(engine, rawcode, mode, area, duration):
    session = engine.session
    key = 'held_fullscreen_effect'
    with session.lock:
        if key in session.resources:
            prior = session.resources[key]
            if not getattr(prior, 'deferred_cleanup', False):
                raise RuntimeError('A fullscreen effect still owns its source instance')
            # Exact-instance cleanup only. A new cast is not sent unless the
            # previous owned ability was actually restored/removed.
            prior.close()
            session.resources.pop(key, None)
        state = engine.direct_cast(rawcode, 1, mode=mode, passes=1, area=area)
        resource = None
        try:
            resource = HeldEffect(engine, rawcode, state)
            session.resources[key] = resource
            time.sleep(duration)
            observed = run_continuation(engine, 3,
                lambda: engine.direct_cast(rawcode, 3, mode=mode, passes=1, state=state),
                epoch=resource.ref.epoch)
            verification = verify_cast_started(state, observed)
            return dict(start=state, state=observed, verification=verification)
        finally:
            primary_error=sys.exc_info()[1]
            try:
                if resource is not None:
                    resource.close()
                else:
                    engine.direct_cast(rawcode, 2, mode=mode, passes=1, state=state)
            except BaseException as cleanup_error:
                deferred = resource is not None and unstarted_continuation_proven(
                    engine, cleanup_error, resource.ref.epoch)
                if deferred:
                    resource.deferred_cleanup = True
                else:
                    session.uncertain = True
                raise HeldEffectCleanupError(primary_error,cleanup_error,
                    deferred=deferred) from cleanup_error
            else:
                session.resources.pop(key, None)
