"""3.0 player selection list reader; locating the local player is separate.

Offsets are verified against 3.0.0.24268. This module does not locate players,
enumerate memory regions, resolve JASS handles, or write game state.
"""
from dataclasses import dataclass
import struct


class SelectionReadError(RuntimeError):
    pass


@dataclass(frozen=True)
class ClassicSelection:
    player: int
    manager: int
    units: tuple[int, ...]


def _pointer(value):
    return 0x10000 <= value < 0x800000000000 and value % 8 == 0


def _read(memory, address, size):
    data = memory.read(address, size)
    if len(data) != size:
        raise SelectionReadError("Selection read was incomplete")
    return data


def read_player_selection(memory, player: int) -> ClassicSelection:
    """Read only this player's canonical list and reject inconsistent snapshots.

    Empty lists have a tagged sentinel, not a null root. Two matching traversals
    also catch list edits that preserve both root and count during the first read.
    """
    if not _pointer(player):
        raise SelectionReadError("Invalid player pointer")
    slot = _read(memory, player + 0x168, 8)
    manager = struct.unpack("<Q", slot)[0]
    if not _pointer(manager):
        raise SelectionReadError("Invalid selection manager")
    sentinel = (manager + 0x10) | 1

    def capture():
        header = _read(memory, manager + 0x10, 0x18)
        tail, root, count = struct.unpack_from("<QQI", header)
        if count > 24:
            raise SelectionReadError("Selection count exceeds 24")
        if count == 0:
            if root != sentinel or tail != manager + 0x10:
                raise SelectionReadError("Empty selection has inconsistent sentinel")
            return header, ()
        node, last = root, 0
        nodes, units = set(), []
        for _ in range(count):
            if not _pointer(node) or node in nodes:
                raise SelectionReadError("Selection list is truncated or cyclic")
            nodes.add(node)
            next_node, unit = struct.unpack("<QQ", _read(memory, node + 8, 16))
            if not _pointer(unit) or unit in units:
                raise SelectionReadError("Selection contains invalid or duplicate unit")
            units.append(unit)
            last, node = node, next_node
        if node != sentinel or tail != last:
            raise SelectionReadError("Selection length or tail disagrees with header")
        return header, tuple(units)

    first = capture()
    if capture() != first or _read(memory, player + 0x168, 8) != slot:
        raise SelectionReadError("Selection changed while reading")
    return ClassicSelection(player, manager, first[1])
