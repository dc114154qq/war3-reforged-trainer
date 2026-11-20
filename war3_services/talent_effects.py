"""Compose live Engineering Upgrade variants on this hero's private data only.

Definitions are obtained from the current map through a read-only engine query.
Shared templates are never modified. Non-scalar or class-changing combinations
are rejected before addition, rather than claiming an ability ID proves effects.
"""
import math
import struct

from war3_services.talent_definitions import bound_target

STRIDE = 0x420


def code(value):
    return int(value).to_bytes(4, 'big').decode('ascii')


def fourcc(value):
    return int.from_bytes(value.encode('ascii'), 'big')


def _pointer(value):
    if not 0x10000 <= value < 0x800000000000 or value % 8:
        raise RuntimeError('天赋技能数据指针无效')
    return value


class Definitions:
    def __init__(self, memory):
        self.memory = memory
        self.reads = {}

    def read(self, address, size):
        _pointer(address & ~7)
        raw = self.memory.read(address, size)
        if len(raw) != size:
            raise RuntimeError('天赋技能定义读取不完整')
        self.reads[(address, size)] = raw
        return raw

    def stable(self):
        if any(self.memory.read(a, n) != raw for (a, n), raw in self.reads.items()):
            raise RuntimeError('天赋技能定义正在变化，请重新添加')

    def string(self, address, raw):
        pointer, size, capacity = struct.unpack_from('<3Q', raw)
        embedded = capacity >> 63
        capacity &= (1 << 63)-1
        if not size <= capacity <= 65536 or embedded and capacity != 15:
            raise RuntimeError('天赋技能字符串结构无效')
        if not size:
            return ''
        value = raw[24:24+size] if embedded else self.read(_pointer(pointer), size)
        return value.decode('utf8')

    def level(self, address):
        raw = self.read(address, STRIDE)
        fields = {}
        for offset in range(0, 32, 4):
            kind = 'integer' if offset in (0, 16) else 'real'
            bits = struct.unpack_from('<I', raw, offset)[0]
            value = bits if kind == 'integer' else struct.unpack('<f', struct.pack('<I', bits))[0]
            fields[offset] = (kind, value)
        for index in range(20):
            offset = 32+48*index
            leaf = raw[offset:offset+48]
            tag = struct.unpack_from('<I', leaf, 40)[0]
            if tag in (1, 2, 3):
                kind = {1:'boolean', 2:'integer', 3:'real'}[tag]
                value = struct.unpack_from('<f' if tag == 3 else '<i', leaf)[0]
                if tag == 1:
                    value = bool(leaf[0])
            elif tag == 4:
                kind, value = 'string', self.string(address+offset, leaf)
            elif tag == 0:
                kind, value = 'none', None
            else:
                # Unknown structured values are compared as opaque data only.
                kind, value = 'opaque', leaf.hex()
            if kind == 'real' and not math.isfinite(value):
                raise RuntimeError('天赋技能包含无效数值')
            fields[offset] = (kind, value)
        arrays = []
        for offset in (0x3e8, 0x404):
            vector = raw[offset:offset+28]
            inline = struct.unpack_from('<i', vector, 24)[0]
            if inline == -1:
                count, pointer, capacity = struct.unpack_from('<I4xQI', vector)
                if not count <= capacity <= 256:
                    raise RuntimeError('天赋技能的增益数组无效')
                values = self.read(_pointer(pointer), count*4) if count else b''
            else:
                if not 0 <= inline <= 3:
                    raise RuntimeError('天赋技能的内联增益数组无效')
                values = vector[:inline*4]
            arrays.append(values.hex())
            fields[offset] = ('fourcc_array',tuple(struct.unpack('<'+'I'*(len(values)//4),values)))
        fields[0x3e0] = ('unit_id',struct.unpack_from('<I',raw,0x3e0)[0])
        return dict(address=address, fields=fields, raw=raw, arrays=tuple(arrays))

    def definition(self, address, alias=None):
        address = _pointer(address)
        header = self.read(address, 0x78)
        base, actual, levels = struct.unpack_from('<2I4xI', header, 0x5c)
        if header[0x58] != 1 or alias is not None and actual != fourcc(alias):
            raise RuntimeError('天赋技能定义代码与缓存不一致')
        sentinel = struct.unpack('<i', self.read(address+0x10f8, 4))[0]
        if sentinel == -1:
            count, pointer, capacity = struct.unpack('<I4xQI4x', self.read(address+0x78, 24))
            if not count <= capacity <= 1000:
                raise RuntimeError('天赋技能等级数组无效')
            pointer = _pointer(pointer)
        else:
            count, pointer = sentinel, address+0x78
        if not 1 <= count <= 100 or count != levels or sentinel != -1 and count > 4:
            raise RuntimeError('天赋技能等级数无效')
        return dict(address=address, alias=code(actual), base=code(base), header=header,
                    levels=tuple(self.level(pointer+i*STRIDE) for i in range(count)))

    def find(self, start, wanted):
        found = {}
        for direction in (0x20, 0x18):
            address = start
            visited = set()
            for _ in range(8192):
                if address in visited:
                    break
                visited.add(address)
                header = self.read(_pointer(address), 0x78)
                if header[0x58] == 1:
                    alias = struct.unpack_from('<I', header, 0x60)[0]
                    if alias in wanted:
                        key = code(alias)
                        if key in found and found[key]['address'] != address:
                            raise RuntimeError('天赋技能共享定义重复')
                        found[key] = self.definition(address, key)
                if len(found) == len(wanted):
                    return found
                link = struct.unpack_from('<Q', header, direction)[0]
                if not link or link & 1:
                    break
                following = link if direction == 0x20 else link-0x18
                back = struct.unpack('<Q', self.read(_pointer(following)+(0x18 if direction == 0x20 else 0x20), 8))[0]
                if back != (address+0x18 if direction == 0x20 else address):
                    break  # The list anchor is not a data node.
                address = following
        missing = [code(k) for k in wanted if code(k) not in found]
        raise RuntimeError('当前地图缺少可读的天赋技能定义：'+', '.join(missing))


def _pairs(definition, level):
    if definition['base'] != 'ANeg':
        return ()
    row = definition['levels'][min(level, len(definition['levels']))-1]
    pairs = []
    for index in range(2, 6):
        kind, text = row['fields'][32+48*index]
        if kind != 'string':
            raise RuntimeError('天赋技能替换规则不是字符串')
        if text in ('', '-', '_', '0'):
            continue
        values = text.split(',')
        if len(values) != 2 or any(len(v) != 4 or not v.isascii() for v in values):
            raise RuntimeError('当前地图的天赋技能替换规则无效')
        pairs.append(tuple(values))
    return tuple(pairs)


def merge_values(base, variants, *, boolean=False):
    changes = list(dict.fromkeys(v for v in variants if v != base))
    if not changes:
        return base
    if len(changes) == 1:
        return changes[0]
    if boolean:
        return int(any(changes))
    if all(v >= base for v in changes):
        return max(changes)
    if all(v <= base for v in changes):
        return min(changes)
    raise RuntimeError('同一数值的强化方向相反，无法同时合并，已保留已有天赋')


def _field_spec(effect_class, offset):
    if offset == 0:
        return ('atar',0,'target_mask','targetList',(),())
    from war3_services.talent_field_metadata import FIELDS
    matches = [r for r in FIELDS if r[1] == offset and (not r[4] or effect_class in r[4]) and effect_class not in r[5]]
    specific = [r for r in matches if r[4]]
    if specific:
        matches = specific
    if len(matches) != 1:
        raise RuntimeError(f'{effect_class} 的字段 +0x{offset:x} 缺少唯一的原生写入接口')
    return matches[0]


def compose(base, variants):
    if any(v['base'] != base['base'] or len(v['levels']) != len(base['levels']) for v in variants):
        raise RuntimeError('这些天赋会把技能转换成不同类型，当前无法合并，已保留已有天赋')
    plan = []
    for level, original in enumerate(base['levels']):
        for offset, (kind, value) in original['fields'].items():
            values = [v['levels'][level]['fields'][offset] for v in variants]
            if all(x == (kind, value) for x in values):
                continue
            if kind == 'fourcc_array' and all(x[0] == kind for x in values):
                target=[]
                length=max(len(value),*(len(x[1]) for x in values))
                if length > 3:
                    raise RuntimeError('这些天赋的增益列表超过内联容量，已保留已有天赋')
                for index in range(length):
                    original_code=value[index] if index<len(value) else 0
                    changes={x[1][index] if index<len(x[1]) else 0 for x in values}-{original_code}
                    if len(changes)>1:
                        raise RuntimeError('这些天赋要求同一位置使用不同增益，无法同时合并，已保留已有天赋')
                    target.append(next(iter(changes)) if changes else original_code)
                plan.append(dict(level=level+1,offset=offset,spec=(
                    'BuffID' if offset==0x3e8 else 'EfctID',offset,kind,'abilityList',(),()),
                    value=tuple(target),base=value))
                continue
            if kind not in ('real', 'integer', 'boolean') or any(x[0] not in (kind, 'boolean') for x in values):
                raise RuntimeError(f"{base['alias']} 第 {level+1} 级包含不能安全合并的非数值效果，已保留已有天赋")
            spec = _field_spec(base['base'], offset)
            if spec[2] == 'target_mask':
                target=0
                for _,mask in values:target |= mask
            else:
                target = merge_values(value, [x[1] for x in values], boolean=spec[2] == 'boolean')
            plan.append(dict(level=level+1, offset=offset, spec=spec, value=target, base=value))
    return plan


def prepare(host, snapshot, state, tier, choice):
    """No gameplay writes. Return an exact plan for actual map definitions."""
    row = state['tiers'][tier]
    selected = tuple(dict.fromkeys((*row['selected'], choice)))
    if len(selected) < 2:
        return None
    engine = host._engine_instance_24268()
    # Loading definitions changes only the engine's data cache, not the hero.
    engine.ability_definitions(tuple(fourcc(c) for c in selected))
    with bound_target(host, snapshot) as (memory, registry, candidate, profile):
        profile.require_module('talents')
        instances = host._ability_instances_from_candidate(memory, candidate, allow_global_scan=False)
        layout = profile.section('layouts')['ability']
        start = memory.read_u64(instances[0].data_address+layout['data_cache'])
        reader = Definitions(memory)
        choices = reader.find(start, {fourcc(c) for c in selected})
        pairs = {c:_pairs(choices[c], max(1, int(snapshot['abilities'].get(fourcc(c), 1)))) for c in selected}
        reader.stable()
    groups = {}
    for c, entries in pairs.items():
        for source, target in entries:
            groups.setdefault(source, {})[c] = target
    groups = {k:v for k, v in groups.items() if len(set(v.values())) > 1}
    if not groups:
        return None
    ids = {s for s in groups} | {v for entries in groups.values() for v in entries.values()}
    engine.ability_definitions(tuple(fourcc(c) for c in sorted(ids)))
    plans = []
    with bound_target(host, snapshot) as (memory, registry, candidate, profile):
        instances = host._ability_instances_from_candidate(memory, candidate, allow_global_scan=False)
        reader = Definitions(memory)
        start = memory.read_u64(instances[0].data_address+layout['data_cache'])
        definitions = reader.find(start, {fourcc(c) for c in ids})
        for source, variants in groups.items():
            targets = set(variants.values())
            attached = [i for i in instances if code(i.rawcode) in targets | {source}]
            if len(attached) != 1:
                raise RuntimeError(f'请先让当前英雄学会 {source}，再追加同层强化天赋')
            try:
                steps = compose(definitions[source], [definitions[c] for c in sorted(targets)])
            except Exception as exc:
                original=definitions[source]
                exc.report=dict(operation='talent_effect_preflight',source=source,variants=variants,
                    live_map_definition_verified=True,game_version=profile.data['game_version'],
                    gameplay_setter_executed=False,independent_operations_allowed=True,
                    definitions={c:dict(alias=definitions[c]['alias'],base=definitions[c]['base'],
                        levels=[dict((str(o),v) for o,v in row['fields'].items()
                            if index>=len(original['levels']) or v!=original['levels'][index]['fields'].get(o))
                            for index,row in enumerate(definitions[c]['levels'])]) for c in sorted(targets)})
                raise
            plans.append(dict(source=source,variants=variants,steps=steps,current=code(attached[0].rawcode),
                shared_cache_addresses=tuple(definitions[c]['address'] for c in [source,*sorted(targets)])))
        reader.stable()
    return dict(controller=state['controller'], tier=tier, choice=choice, groups=plans,
                live_map_definition_verified=True)


def _active(host, snapshot, group):
    """Resolve afresh, including the attached ability's complete identity."""
    with bound_target(host, snapshot) as (memory, registry, candidate, profile):
        instances = host._ability_instances_from_candidate(memory,candidate,allow_global_scan=False)
        choices = {group['source'], *group['variants'].values()}
        matches = [i for i in instances if code(i.rawcode) in choices]
        if len(matches) != 1:
            raise RuntimeError('天赋强化的目标技能已变化')
        instance = matches[0]
        layout = profile.section('layouts')['ability']
        primary, private = struct.unpack('<QQ',memory.read(instance.data_address+layout['data_cache'],16))
        reader = Definitions(memory)
        definition = reader.definition(private or primary)
        if definition['alias'] not in choices or definition['base'] != code(instance.class_rawcode):
            raise RuntimeError('天赋技能实例与实际定义类型不一致')
        reader.stable()
        return instance, primary, private, definition


def _current_values(host, snapshot, group, steps):
    instance, primary, private, definition = _active(host,snapshot,group)
    if any(step['level'] > len(definition['levels']) for step in steps):
        raise RuntimeError('天赋技能的等级数据已经变化')
    values = []
    for step in steps:
        kind, value = definition['levels'][step['level']-1]['fields'][step['offset']]
        if step['spec'][2] == 'boolean':
            if kind not in ('boolean','integer') or value not in (0,1):
                raise RuntimeError('天赋开关字段类型无效')
        elif kind != step['spec'][2] and not (kind=='integer' and step['spec'][2]=='target_mask'):
            raise RuntimeError('天赋数值字段类型无效')
        values.append(value)
    return instance, private, values


def _bits(value, kind):
    if kind == 'fourcc_array':
        return tuple(value)
    if kind == 'target_mask':
        return int(value)&0xffffffff
    if kind == 'real':
        return struct.unpack('<I',struct.pack('<f',value))[0]
    if not -(1<<31) <= int(value) < (1<<31):
        raise RuntimeError('天赋字段数值超出范围')
    return int(value)&0xffffffff


def _write(host, snapshot, group, steps, guard, trace):
    target = int(snapshot['target_unit'])
    guard.check(host.extension_snapshot_24268(target))
    original_instance, _, originals = _current_values(host,snapshot,group,steps)
    pending = [(s,v) for s,v in zip(steps, originals) if v != s['value']]
    trace.record('field_before',source=group['source'],ability=original_instance,
                 values=[dict(**s,before=v) for s,v in zip(steps,originals)])
    if not pending:
        return 0
    active_code = code(original_instance.rawcode)
    # The game owns allocation, copy and release of the private cache. Even
    # an all-boolean plan first takes this tested native scalar-copy path.
    if not any(s['spec'][2] in ('integer','real') for s,_ in pending):
        _, _, _, definition = _active(host,snapshot,group)
        cost = definition['levels'][0]['fields'][16][1]
        host.ability_field_batch_24268(active_code,1,1,((fourcc('amcs'),1,1,_bits(cost,'integer')),),target_unit=target)
    for level in sorted({s['level'] for s,_ in pending if s['spec'][2] in ('integer','real')}):
        guard.check(host.extension_snapshot_24268(target))
        descriptors = tuple((fourcc(s['spec'][0]),{'integer':1,'real':2}[s['spec'][2]],1,
                             _bits(s['value'],s['spec'][2])) for s,_ in pending
                            if s['level'] == level and s['spec'][2] in ('integer','real'))
        result = host.ability_field_batch_24268(active_code,level,1,descriptors,target_unit=target)
        trace.record('native_scalar_write',source=group['source'],level=level,result=result)
    private_steps = [s for s,_ in pending if s['spec'][2] in ('boolean','fourcc_array','target_mask')]
    if private_steps:
        # The game's BooleanLevelField getter faults after a private copy on
        # 24371. Only the validated scalar leaf of the engine-owned private
        # cache is changed. No strings, shared nodes or allocations are edited.
        engine = host._engine_instance_24268()
        from war3_game_session import session_scope
        with bound_target(host,snapshot) as (read_memory,registry,candidate,profile):
            instance,primary,private,definition = _active(host,snapshot,group)
            if not private or private == primary or instance.handle != original_instance.handle:
                raise RuntimeError('天赋技能没有独立的私有数据，未写入开关')
            layout = profile.section('layouts')['ability']
            # The native setter above owns COW/allocation. Private copies do
            # not initialize unused hash/database members, so those bytes
            # cannot establish ownership. Match the full attached instance,
            # the engine's override pointer and actual global definitions.
            shared=group.get('shared_cache_addresses',())
            if not shared or private in shared:
                raise RuntimeError('天赋技能的私有数据指向共享定义，未写入')
            trace.record('private_cache_bound',ability=instance,primary=primary,private=private,
                shared_cache_addresses=shared,private_header=definition['header'].hex())
            with engine.memory_factory(engine.pid,write=True) as memory,session_scope(engine.session):
                for step in private_steps:
                    guard.check(host.extension_snapshot_24268(target))
                    engine.session.resolve(memory,registry,guard.ref)
                    if (memory.read_u64(instance.data_address+layout['full_handle']) != instance.handle
                            or memory.read_u64(instance.data_address+layout['unit_owner']) != candidate.unit_address
                            or memory.read(instance.data_address+layout['data_cache'],16) != struct.pack('<QQ',primary,private)):
                        raise RuntimeError('天赋开关写入前技能身份已变化')
                    leaf = definition['levels'][step['level']-1]['address']+step['offset']
                    if step['spec'][2] == 'fourcc_array':
                        vector=memory.read(leaf,28);inline=struct.unpack_from('<i',vector,24)[0]
                        if inline == -1:
                            count,pointer,capacity=struct.unpack_from('<I4xQI',vector)
                            if not count<=capacity<=256 or len(step['value'])>capacity:
                                raise RuntimeError('天赋增益列表的私有容量无效')
                            _pointer(pointer);count_address=leaf
                        else:
                            if not 0<=inline<=3 or len(step['value'])>3:
                                raise RuntimeError('天赋增益列表的内联容量无效')
                            pointer=leaf;count_address=leaf+24
                        data=struct.pack('<'+'I'*len(step['value']),*step['value'])
                        for index,value in enumerate(step['value']):
                            memory.write_u32(pointer+index*4,value)
                        memory.write_u32(count_address,len(step['value']))
                        if memory.read(pointer,len(data)) != data or memory.read_u32(count_address)!=len(step['value']):
                            raise RuntimeError('天赋增益列表写入后读回不一致')
                        trace.record('private_array_write',field=step['spec'][0],level=step['level'],
                            private_cache=private,values=step['value'],allocation_required=False,shared_template_written=False)
                        continue
                    if step['spec'][2] == 'target_mask':
                        memory.write_u32(leaf,step['value'])
                        if memory.read_u32(leaf)!=step['value']:
                            raise RuntimeError('天赋允许目标写入后读回不一致')
                        trace.record('private_target_mask_write',level=step['level'],private_cache=private,value=step['value'])
                        continue
                    tag = memory.read_u32(leaf+40)
                    if tag not in (1,2) or memory.read_u32(leaf) not in (0,1):
                        raise RuntimeError('天赋开关的私有数据类型已变化')
                    before = memory.read_u32(leaf)
                    memory.write_u32(leaf,int(bool(step['value'])))
                    if memory.read_u32(leaf) != int(bool(step['value'])) or memory.read_u32(leaf+40) != tag:
                        raise RuntimeError('天赋开关写入后读回不一致')
                    trace.record('private_boolean_write',field=step['spec'][0],level=step['level'],
                        private_cache=private,leaf=leaf,before=before,after=int(bool(step['value'])),shared_template_written=False)
    guard.check(host.extension_snapshot_24268(target))
    _, _, after = _current_values(host,snapshot,group,steps)
    if any(_bits(v,s['spec'][2]) != _bits(s['value'],s['spec'][2]) for s,v in zip(steps,after)):
        raise RuntimeError('天赋合并后的实际技能数值未全部匹配')
    trace.record('field_after',source=group['source'],values=after,all_levels_verified=True)
    return len(pending)


def apply(host, snapshot, plan, guard, trace):
    originals = []
    changed = 0
    try:
        for group in plan['groups']:
            _, _, values = _current_values(host,snapshot,group,group['steps'])
            originals.append((group,[dict(s,value=v) for s,v in zip(group['steps'],values)]))
            changed += _write(host,snapshot,group,group['steps'],guard,trace)
    except Exception as exc:
        errors = []
        for group, steps in reversed(originals):
            try:
                _write(host,host.extension_snapshot_24268(guard.target),group,steps,guard,trace)
            except Exception as rollback_error:
                errors.append(str(rollback_error))
        exc.report = dict(operation='talent_effect_composition',error=str(exc),rollback_errors=errors,
                          independent_operations_allowed=True,plan=plan)
        trace.record('failed',execution_report=exc.report)
        raise
    return dict(status='verified',changed_fields=changed,groups=plan['groups'],
                live_map_definition_verified=True,all_level_values_verified=True)


def add_choice(host, controller, tier, choice, target_unit, primitive):
    from war3_services.loadout_talents import _Guard
    from war3_services.operation_trace import BackpackTrace
    from war3_backend import Win10ReadLogger
    class EffectTrace(BackpackTrace):
        prefix='talent-effect';event_name='talent_effect_phase'
        source_inputs=('talent_effects.py','talent_field_metadata.py','facade_extensions.py')
    engine = host._engine_instance_24268()
    with engine.session.lock,EffectTrace(host,Win10ReadLogger,dict(controller=controller,tier=tier,choice=choice)) as trace:
        trace.bind_engine(engine)
        snapshot = host.extension_snapshot_24268(target_unit) if target_unit else host.extension_snapshot_24268()
        state = host.talent_state_24268(snapshot)
        tier = int(tier)
        if state['controller'] != controller or not 0 <= tier < len(state['tiers']) or choice not in state['tiers'][tier]['choices']:
            raise RuntimeError('天赋选项或英雄已变化，请重新读取')
        guard = _Guard(host,snapshot)
        try:
            plan = prepare(host,snapshot,state,tier,choice)
        except Exception as exc:
            trace.record('preflight_failed',state=state,reason=str(exc),execution_report=getattr(exc,'report',None))
            raise
        trace.record('prepared',state=state,plan=plan)
        guard.check(host.extension_snapshot_24268(guard.target))
        after = primitive(controller,tier,choice,target_unit=guard.target)
        if plan:
            try:
                result = apply(host,after,plan,guard,trace)
            except Exception as exc:
                if choice not in state['tiers'][tier]['selected']:
                    try:
                        guard.check(host.extension_snapshot_24268(guard.target))
                        host.ability_batch_24268(choice,2,0,target_unit=guard.target)
                    except Exception as cleanup_error:
                        report = getattr(exc,'report',{})
                        report['new_choice_cleanup_error'] = str(cleanup_error)
                        exc.report = report
                raise
            after = host.extension_snapshot_24268(guard.target)
            guard.check(after)
            after['talent_effect_composition'] = result
        trace.record('complete',result=after.get('talent_effect_composition',dict(status='ordinary_native_effect')))
        return after


def before_reset(host,snapshot,state):
    """Reconstruct from live definitions, also after restarting the trainer."""
    if not getattr(host,'pid',0):
        return ()
    plans = []
    from war3_services.loadout_talents import _trace
    with _trace(host,'prepare_reset_effects',int(snapshot['target_unit']),'') as trace:
        for index,row in enumerate(state['tiers']):
            if len(row['selected']) < 2:
                continue
            try:
                plan = prepare(host,snapshot,state,index,row['selected'][-1])
            except RuntimeError as exc:
                # Unsupported combinations were never merged by this module;
                # their ordinary removal must still remain available.
                trace.record('ordinary_reset_only',tier=index,reason=str(exc),execution_report=getattr(exc,'report',None))
                continue
            if plan:
                for group in plan['groups']:
                    plans.append(dict(group,steps=[dict(s,value=s['base']) for s in group['steps']]))
        trace.record('reset_prepared',plans=plans)
    return tuple(plans)


def after_reset(host,snapshot,groups):
    if not groups:
        return snapshot
    from war3_services.loadout_talents import _Guard,_trace
    guard = _Guard(host,snapshot)
    with _trace(host,'reset_composed_effects',guard.target,'') as trace:
        for group in groups:
            _write(host,snapshot,group,group['steps'],guard,trace)
        trace.record('reset_fields_verified',sources=[g['source'] for g in groups])
    return host.extension_snapshot_24268(guard.target)
