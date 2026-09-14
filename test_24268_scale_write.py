"""Exercise the current product's indexed scale writer, not a legacy C fixture."""
import struct
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from war3_reforged_trainer import War3Trainer


def subject(current=1.0, actual=2.0, identities=None):
    t = object.__new__(War3Trainer)
    t._native_selection_unavailable = True
    c = SimpleNamespace(unit_address=0x100000, handle=0x123, owner_address=0x200000)
    t._direct_selected_context = Mock(return_value=(c, 0))
    memory = MagicMock()
    memory.__enter__.return_value = memory
    memory.read_f32.side_effect = [current, actual]
    t._process_memory = Mock(return_value=memory)
    registry = Mock()
    registry.resolve_unit.side_effect = identities or [(c.handle, c.owner_address)] * 3
    t._classic_object_registry = registry
    return t, memory, registry


@pytest.mark.parametrize('target', [float('nan'), float('inf'), -float('inf'), 0, -1, 100.01])
def test_invalid_target_never_opens_memory(target):
    t, memory, _ = subject()
    with pytest.raises(ValueError):
        t.set_selected_unit_scale(target)
    t._process_memory.assert_not_called()
    memory.write_f32.assert_not_called()


@pytest.mark.parametrize('current', [float('nan'), float('inf'), -float('inf'), 0, -1])
def test_invalid_original_never_writes(current):
    t, memory, _ = subject(current=current)
    with pytest.raises(RuntimeError, match='field is invalid'):
        t.set_selected_unit_scale(2)
    memory.write_f32.assert_not_called()


@pytest.mark.parametrize('actual', [float('nan'), float('inf'), 2.0001, 1.9999])
def test_bad_readback_is_not_success(actual):
    t, memory, _ = subject(actual=actual)
    with pytest.raises(RuntimeError, match='readback'):
        t.set_selected_unit_scale(2)
    memory.write_f32.assert_called_once()


@pytest.mark.parametrize('changed_at', [0, 1, 2])
def test_recycled_unit_is_detected(changed_at):
    ids = [(0x123, 0x200000)] * 3
    ids[changed_at] = (0x456, 0x200000)
    t, memory, _ = subject(identities=ids)
    with pytest.raises(RuntimeError, match='identity changed'):
        t.set_selected_unit_scale(2)
    assert memory.write_f32.call_count == (1 if changed_at == 2 else 0)


@pytest.mark.parametrize('target', [0.01, 0.1, 1.0, 2.0, 100.0])
def test_float32_target_and_identity_readback(target):
    expected = struct.unpack('<f', struct.pack('<f', target))[0]
    t, memory, registry = subject(actual=expected)
    assert t.set_selected_unit_scale(target) == expected
    memory.write_f32.assert_called_once_with(0x100290, expected)
    assert registry.resolve_unit.call_count == 3


def test_native_route_keeps_encoded_float32_contract():
    t, memory, _ = subject()
    t._native_selection_unavailable = False
    bits = struct.unpack('<I', struct.pack('<f', 0.1))[0]
    t._run_bound_unit_value_action = Mock(return_value=bits)
    assert t.set_selected_unit_scale(0.1) == struct.unpack('<f', struct.pack('<I', bits))[0]
    t._process_memory.assert_not_called()
