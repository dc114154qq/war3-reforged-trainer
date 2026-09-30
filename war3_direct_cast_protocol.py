"""Identity-bound staged runtime effects; the image is disposable per phase."""
import struct
from war3_world_cast_protocol import SIGNATURES as WORLD, build_work as world_work
from war3_selection_protocol import decode_work as selection_result

SIGNATURES = WORLD + (("GetUnitAbilityLevel", "(Hunit;I)I"),)
WORK_SIZE = 824
ABI = struct.pack('<3I', 0x24268050, 216, WORK_SIZE)


def build_work(entries, tls, *, module_base, unit_resolver, action, rawcode,
               mode=3, passes=1, area=100000.0, state=None):
    state = state or {}
    entry = entries['GetUnitAbilityLevel']
    if entry.signature != '(Hunit;I)I':
        raise ValueError('Ability-level ABI differs')
    payload = world_work(entries, tls, action=action, rawcode=rawcode,
        order_id=1 if action == 1 else 0, cast_kind=1,
        area=area if action == 1 else 0,
        target=state.get('order_after', 0),
        **{k: state.get(k, 0) for k in ('source', 'ability_handle', 'prior_area', 'added')})
    payload += struct.pack('<6Q4I', module_base, unit_resolver, entry.handler,
        state.get('unit_full', 0), state.get('ability_full', 0), state.get('ability_data', 0),
        mode, passes, state.get('level_index', 0), 0)
    validate_work(payload)
    return payload


def validate_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError('Direct cast work size differs')
    from war3_world_cast_protocol import validate_work as validate_world
    validate_world(payload[:760])
    base, resolver, level_fn, unit_full, ability_full, data, mode, passes, level, cleanup = struct.unpack_from('<6Q4I', payload, 760)
    action = struct.unpack_from('<I', payload, 696)[0]
    if (any(not 0x10000 <= p < 0x800000000000 for p in (base, resolver, level_fn))
            or mode not in (2, 3, 4) or not 1 <= passes <= 255 or level > 100000 or cleanup):
        raise ValueError('Invalid direct cast request')
    if action == 1:
        if any((unit_full, ability_full, data, level)):
            raise ValueError('Direct cast start identity must be empty')
    elif not unit_full or not ability_full or not 0x10000 <= data < 0x800000000000:
        raise ValueError('Direct cast continuation identity is missing')


def decode_work(payload, _count):
    if len(payload) != WORK_SIZE:
        raise ValueError('Incomplete direct cast response')
    source, ability_handle, _target = struct.unpack_from('<3Q', payload, 672)
    values = struct.unpack_from('<16I', payload, 696)
    action, rawcode, _, _, area, prior, added, invoked, error, completed = values[:10]
    _, _, _, unit_full, ability_full, data, mode, passes, level, cleanup = struct.unpack_from('<6Q4I', payload, 760)
    if error or cleanup or completed != 1 or (action == 1 and invoked != 1):
        raise ValueError(f'Direct effect incomplete: action={action}, error={error}, cleanup={cleanup}')
    real = lambda bits: struct.unpack('<f', struct.pack('<I', bits))[0]
    selected = selection_result(payload[:480], struct.unpack_from('<I', payload, 80)[0]) if action == 1 else None
    return dict(action=action, rawcode=rawcode, source=source, ability_handle=ability_handle,
        unit_full=unit_full, ability_full=ability_full, ability_data=data, mode=mode,
        passes=passes, level_index=level, prior_area=prior, added=added, invoked=invoked,
        mana_before=real(values[10]), mana_after=real(values[11]),
        cooldown_after=real(values[12]), order_after=values[13],
        point=(real(values[14]), real(values[15])), selection=selected, cleanup_verified=action == 2)
