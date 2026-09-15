"""Current-engine 24268 batch for global game/player actions."""
import math
import struct

WORK_SIZE = 128
ABI = struct.pack('<3I', 0x24268017, 216, WORK_SIZE)
SIGNATURES = (
    ('GetLocalPlayer', '()Hplayer;'),
    ('SetPlayerTechMaxAllowed', '(Hplayer;II)V'),
    ('SetPlayerTechResearched', '(Hplayer;II)V'),
    ('SetPlayerHandicapXP', '(Hplayer;R)V'),
    ('FogEnable', '(B)V'),
    ('FogMaskEnable', '(B)V'),
    ('IsFogEnabled', '()B'),
    ('IsFogMaskEnabled', '()B'),
    ('PauseGame', '(B)V'),
    ('EndGame', '(B)V'),
)

ACTION_SET_TECH = 1
ACTION_SET_XP_RATE = 2
ACTION_QUERY_FOG = 3
ACTION_SET_FOG = 4
ACTION_SET_GAME_PAUSED = 5
ACTION_END_GAME = 6


def _pointers(entries):
    pointers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError('World native signature differs: ' + name)
        pointers.append(entry.handler)
    return pointers


def build_work(entries, tls, action, rawcode=0, value=0):
    payload = struct.pack(
        '<11Q10I', *_pointers(entries), tls, action, rawcode, value,
        0, 0, 0, 0, 0, 0, 0,
    )
    validate_work(payload)
    return payload


def validate_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError('World work must contain 128 bytes')
    values = struct.unpack_from('<11Q10I', payload, 0)
    pointers, tls = values[:10], values[10]
    action, rawcode, value, *outputs = values[11:]
    if (any(not 0x10000 <= pointer < 0x800000000000 for pointer in pointers)
            or len(set(pointers)) != len(pointers)
            or not 0x10000 <= tls < 0x800000000000 or tls % 8
            or action not in range(1, 7)):
        raise ValueError('Invalid world native pointers or action')
    if action == ACTION_SET_TECH:
        if not rawcode or value > 100000:
            raise ValueError('Invalid technology operation')
    elif action == ACTION_SET_XP_RATE:
        rate = struct.unpack('<f', struct.pack('<I', value))[0]
        if rawcode or not math.isfinite(rate) or not 0.0 <= rate <= 10000.0:
            raise ValueError('Invalid experience rate')
    elif action == ACTION_QUERY_FOG:
        if rawcode or value:
            raise ValueError('Invalid fog query')
    else:
        if rawcode or value > 1:
            raise ValueError('Invalid world boolean operation')
    if any(outputs):
        raise ValueError('World outputs must be zero')


def decode_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError('Incomplete world batch')
    action, rawcode, value, changed, error, completed, after0, after1, reserved0, reserved1 = struct.unpack_from(
        '<10I', payload, 88,
    )
    valid = not error and completed == 1 and not reserved0 and not reserved1
    if action == ACTION_SET_TECH:
        valid &= rawcode != 0 and after0 == value and changed == 1
    elif action == ACTION_SET_XP_RATE:
        valid &= rawcode == 0 and after0 == value and changed == 1
    elif action == ACTION_QUERY_FOG:
        valid &= rawcode == 0 and value == 0 and after0 <= 1 and after1 <= 1 and changed == 0
    elif action == ACTION_SET_FOG:
        valid &= rawcode == 0 and after0 == (0 if value else 1) and after1 == (0 if value else 1) and changed == 1
    elif action in (ACTION_SET_GAME_PAUSED, ACTION_END_GAME):
        valid &= rawcode == 0 and after0 == value and changed == 1
    else:
        valid = False
    if not valid:
        raise ValueError(f'World batch incomplete: error={error}, completed={completed}, changed={changed}')
    return dict(action=action, rawcode=rawcode, value=value, changed=changed,
                count=1, after0=after0, after1=after1)
