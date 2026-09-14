"""Explicit ABI for the 24268 selection-query bridge; no process access here."""
import struct

MAX_SELECTED = 24
WORK_SIZE = 480
COMMAND_SIZE = 216
ABI = struct.pack('<3I', 0x24268003, COMMAND_SIZE, WORK_SIZE)
SIGNATURES = (
    ('GetLocalPlayer', '()Hplayer;'),
    ('CreateGroup', '()Hgroup;'),
    ('GroupEnumUnitsSelected', '(Hgroup;Hplayer;Hboolexpr;)V'),
    ('FirstOfGroup', '(Hgroup;)Hunit;'),
    ('GroupRemoveUnit', '(Hgroup;Hunit;)B'),
    ('DestroyGroup', '(Hgroup;)V'),
    ('GetUnitTypeId', '(Hunit;)I'),
    ('GetHeroLevel', '(Hunit;)I'),
)


def build_work(entries):
    handlers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError('Missing or mismatched selection native: ' + name)
        handlers.append(entry.handler)
    payload = struct.pack('<8Q', *handlers) + bytes(WORK_SIZE - 64)
    validate_work(payload)
    return payload


def validate_work(payload, *, fixture=False):
    if len(payload) != WORK_SIZE:
        raise ValueError('SelectionWork must contain exactly 480 bytes')
    if fixture:
        return
    handlers = struct.unpack_from('<8Q', payload)
    if any(not 0x10000 <= address < 0x800000000000 for address in handlers):
        raise ValueError('SelectionWork contains an invalid handler')
    if len(set(handlers)) != len(handlers):
        raise ValueError('SelectionWork contains duplicate handlers')
    if any(payload[64:]):
        raise ValueError('SelectionWork output must be zero-initialized')


def decode_work(payload, expected_count):
    if len(payload) != WORK_SIZE:
        raise ValueError('Incomplete selection result')
    player, group, count, error, destroyed, reserved = struct.unpack_from('<2Q4I', payload, 64)
    if error or not player or not group or destroyed != 1 or reserved:
        raise ValueError('Selection query or temporary-group cleanup failed')
    if count > MAX_SELECTED or count != expected_count:
        raise ValueError('Selection count mismatch')
    rows = []
    for index in range(count):
        unit, rawcode, level = struct.unpack_from('<QIi', payload, 96 + index * 16)
        if not unit or not rawcode or level < 0 or any(r['handle'] == unit for r in rows):
            raise ValueError('Invalid or duplicate selection row')
        rows.append(dict(handle=unit, rawcode=rawcode, level=level))
    return dict(player=player, count=count, rows=rows, temporary_group_destroyed=True)
