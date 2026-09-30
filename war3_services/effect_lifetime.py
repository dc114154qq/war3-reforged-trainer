"""A held effect belongs to one session and one typed source identity."""
import time
from war3_game_session import ObjectAddress
from war3_object_registry import ObjectRegistry24268


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
        result = self.engine.direct_cast(self.rawcode, 2, mode=self.state['mode'],
            passes=self.state['passes'], state=self.state)
        self.closed = True
        return result


def run_held_effect(engine, rawcode, mode, passes, area, duration):
    session = engine.session
    key = 'held_fullscreen_effect'
    with session.lock:
        if key in session.resources:
            raise RuntimeError('A fullscreen effect still owns its source instance')
        state = engine.direct_cast(rawcode, 1, mode=mode, passes=passes, area=area)
        resource = None
        try:
            resource = HeldEffect(engine, rawcode, state)
            session.resources[key] = resource
            time.sleep(duration)
            observed = engine.direct_cast(rawcode, 3, mode=mode, passes=passes, state=state)
            return dict(start=state, state=observed)
        finally:
            try:
                if resource is not None:
                    resource.close()
                else:
                    engine.direct_cast(rawcode, 2, mode=mode, passes=passes, state=state)
            except BaseException:
                session.uncertain = True
                raise
            else:
                session.resources.pop(key, None)
