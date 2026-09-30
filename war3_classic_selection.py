"""3.0 player selection list reader; locating the local player is separate.

Offsets are verified against 3.0.0.24268. This module does not locate players,
enumerate memory regions, resolve JASS handles, or write game state.
"""
from dataclasses import dataclass
import struct
from war3_game_profile import current_profile


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
    layout = current_profile().section("selection")
    manager_offset = layout["manager"]
    header_offset = layout["header"]
    next_offset, unit_offset = layout["node_next"], layout["node_unit"]
    max_count = layout["max_count"]
    adjacent_fields = unit_offset == next_offset + 8
    if not _pointer(player):
        raise SelectionReadError("Invalid player pointer")
    slot = _read(memory, player + manager_offset, 8)
    manager = struct.unpack("<Q", slot)[0]
    if not _pointer(manager):
        raise SelectionReadError("Invalid selection manager")
    sentinel = (manager + header_offset) | 1

    def capture():
        header = _read(memory, manager + header_offset, 0x18)
        tail, root, count = struct.unpack_from("<QQI", header)
        if count > max_count:
            raise SelectionReadError("Selection count exceeds 24")
        if count == 0:
            if root != sentinel or tail != manager + header_offset:
                raise SelectionReadError("Empty selection has inconsistent sentinel")
            return header, ()
        node, last = root, 0
        nodes, units = set(), []
        for _ in range(count):
            if not _pointer(node) or node in nodes:
                raise SelectionReadError("Selection list is truncated or cyclic")
            nodes.add(node)
            if adjacent_fields:
                next_node, unit = struct.unpack('<2Q', _read(memory, node+next_offset, 16))
            else:
                next_node, unit = (struct.unpack('<Q', _read(memory, node+offset, 8))[0]
                                   for offset in (next_offset, unit_offset))
            if not _pointer(unit) or unit in units:
                raise SelectionReadError("Selection contains invalid or duplicate unit")
            units.append(unit)
            last, node = node, next_node
        if node != sentinel or tail != last:
            raise SelectionReadError("Selection length or tail disagrees with header")
        return header, tuple(units)

    first = capture()
    if capture() != first or _read(memory, player + manager_offset, 8) != slot:
        raise SelectionReadError("Selection changed while reading")
    return ClassicSelection(player, manager, first[1])
