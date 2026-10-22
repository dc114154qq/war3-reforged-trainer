"""Bound nested exact-slot placement; the scope ends with this one operation."""
from contextvars import ContextVar
from contextlib import contextmanager

_placements = ContextVar('extension_slot_placements', default=())


@contextmanager
def equipment_slot_transaction(host, equipment_slot):
    key = (id(host), int(equipment_slot))
    active = _placements.get()
    if key in active:
        raise RuntimeError('这些装备的原生部位互相冲突，已保留物品；请在游戏内手动穿戴剩余装备')
    token = _placements.set(active + (key,))
    try:
        yield
    finally:
        _placements.reset(token)
