"""Regression coverage for deferred casts and identity-bound cleanup."""
from types import SimpleNamespace
from threading import RLock
from unittest.mock import Mock

import pytest
from war3_services import effect_lifetime as effects


def make_engine(monkeypatch, failure=None):
    state = dict(mode=3, passes=1, source=10, ability_full=20)
    events = []
    session = SimpleNamespace(lock=RLock(), resources={}, uncertain=False, epoch=4)
    def cast(rawcode, action, **kwargs):
        events.append(action)
        if action == failure:
            raise RuntimeError('phase failed')
        if action != 1:
            assert kwargs['state'] is state
        return state
    engine = SimpleNamespace(session=session, direct_cast=cast)
    class BoundEffect:
        def __init__(self, engine, rawcode, captured):
            assert captured is state
        def close(self):
            engine.direct_cast(123, 2, state=state)
    monkeypatch.setattr(effects, 'HeldEffect', BoundEffect)
    monkeypatch.setattr(effects.time, 'sleep', lambda seconds: events.append(('wait', seconds)))
    return engine, events


def test_channel_is_kept_until_hold_and_readback_finish(monkeypatch):
    engine, events = make_engine(monkeypatch)
    effects.run_held_effect(engine, 123, 3, 1, 100000, 12)
    assert events == [1, ('wait', 12), 3, 2]
    assert not engine.session.resources and not engine.session.uncertain


def test_readback_failure_still_cleans_the_captured_instance(monkeypatch):
    engine, events = make_engine(monkeypatch, failure=3)
    with pytest.raises(RuntimeError, match='phase failed'):
        effects.run_held_effect(engine, 123, 3, 1, 100000, 12)
    assert events == [1, ('wait', 12), 3, 2]
    assert not engine.session.resources and not engine.session.uncertain


def test_cleanup_failure_retains_ownership_and_prevents_replay(monkeypatch):
    engine, events = make_engine(monkeypatch, failure=2)
    with pytest.raises(RuntimeError):
        effects.run_held_effect(engine, 123, 3, 1, 100000, 12)
    assert engine.session.uncertain and 'held_fullscreen_effect' in engine.session.resources
    with pytest.raises(RuntimeError, match='still owns'):
        effects.run_held_effect(engine, 123, 3, 1, 100000, 12)
    assert events.count(1) == 1


def test_changed_map_never_cleans_a_reused_object_address():
    engine = SimpleNamespace(session=SimpleNamespace(epoch=5), direct_cast=Mock())
    resource = object.__new__(effects.HeldEffect)
    resource.engine, resource.ref, resource.closed = engine, SimpleNamespace(epoch=4), False
    with pytest.raises(RuntimeError, match='context changed'):
        resource.close()
    engine.direct_cast.assert_not_called()
