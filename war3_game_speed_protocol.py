"""The five native gamespeed values, with verified readback."""
import struct

WORK_SIZE = 104
ABI = struct.pack('<3I', 0x24268051, 216, WORK_SIZE)
SIGNATURES = (
    ('ConvertGameSpeed', '(I)Hgamespeed;'),
    ('GetGameSpeed', '()Hgamespeed;'),
    ('SetGameSpeed', '(Hgamespeed;)V'),
    ('ConvertMapFlag', '(I)Hmapflag;'),
    ('IsMapFlagSet', '(Hmapflag;)B'),
    ('SetMapFlag', '(Hmapflag;B)V'),
)


def build_work(entries, tls, action=0, target=4):
    pointers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError('Game-speed native signature differs: '+name)
        pointers.append(entry.handler)
    if type(action) is not int or type(target) is not int:
        raise ValueError('Game-speed action and tier must be integers')
    payload = struct.pack('<7Q12I', *pointers, tls, action, target, *([0]*10))
    validate_work(payload)
    return payload


def validate_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError('Game-speed work size differs')
    values = struct.unpack('<7Q12I', payload)
    if (any(not 0x10000 <= p < 0x800000000000 for p in values[:7])
            or values[6] % 8 or values[7] not in (0, 1) or not 0 <= values[8] <= 4
            or any(values[9:])):
        raise ValueError('Invalid game-speed request')


def decode_work(payload, _count):
    if len(payload) != WORK_SIZE:
        raise ValueError('Incomplete game-speed response')
    action, target, before, after, changed, error, completed, lock_before, lock_after, *reserved = struct.unpack_from('<12I', payload, 56)
    if (error==362 and action==1 and before==after and before in range(5)
            and lock_before==lock_after and lock_before in (0,1) and not changed and not any(reserved)):
        raise ValueError(f'游戏未接受速度档位 {target}，实际仍为 {after}；未开启加速')
    if (error or any(reserved) or completed != 1 or before > 4 or after > 4
            or lock_before not in (0, 1) or lock_after != lock_before
            or action not in (0, 1) or changed != int(before != after)
            or (action == 0 and (changed or after != before)) or (action == 1 and after != target)):
        raise ValueError(f'Game speed readback failed: error={error}, before={before}, after={after}')
    return dict(before=before, after=after, changed=changed, action=action,
                lock_before=lock_before, lock_after=lock_after)
