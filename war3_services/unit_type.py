"""Classic-style runtime type-ID editing; the separate skin ID stays untouched."""
import re
from dataclasses import replace

from war3_game_session import ObjectAddress, UnitRef, session_scope
from war3_contracts import UnitMemoryField
from war3_services.operation_trace import SkillTrace


class UnitTypeTrace(SkillTrace):
    prefix = 'unit-type'
    event_name = 'unit_type_phase'
    source_inputs = ('unit_type.py', 'facade_units.py')


def parse_code(value):
    if not isinstance(value, str) or not re.fullmatch(r'[!-~]{4}', value.strip()):
        raise ValueError('单位代码请输入区分大小写的 4 位英文字符，例如 Hpal 或 H002')
    return int.from_bytes(value.strip().encode('ascii'), 'big')


def type_code_field(code):
    return UnitMemoryField(key='unit_type_code',label='单位类型代码',value_type='rawcode',
        value=code,address=0,category='基础',native_write=True,
        note='区分大小写的 4 位单位代码，并非中文名称；填写当前地图中存在的代码。只改单个选中单位；不会立即更换模型，变身结束后的效果取决于技能和地图。')


def _write_bound_code(memory, registry, session, ref, owner, adapter, target, trace):
    """Follow classic SetUnitTypeId: write the runtime ID, preserve the skin ID."""
    addresses = adapter.type_code_addresses(ref.address.value)
    if len(addresses) != 1:
        raise RuntimeError('单位类型代码写入目标应当只有一处')
    original = (ref.rawcode,)
    skin_address = adapter.skin_code_address(ref.address.value)
    skin_before = memory.read_u32(skin_address)
    written = []

    def identity():
        session.require_write()
        if ref.session != session.identity or ref.epoch != session.epoch:
            raise RuntimeError('游戏或地图已变化，请重新读取单位')
        if registry.resolve_unit(memory, ref.address.value) != (ref.handle.value, owner):
            raise RuntimeError('单位对象已变化，已停止修改单位代码')

    def values():
        return tuple(memory.read_u32(address) for address in addresses)

    identity()
    if values() != original:
        raise RuntimeError('单位类型代码已变化或正在变身，请重新读取后再修改')
    trace.record('preflight', unit=ref, owner=owner, addresses=addresses, before=original, target=target,
                 skin_address=skin_address,skin_before=skin_before,skin_write_requested=False,
                 target_definition_verified=False, morph_effect_verified=False)
    if target == ref.rawcode:
        return ref
    trace.checkpoint()
    try:
        for index, address in enumerate(addresses):
            identity()
            expected = tuple(target if i in written else value for i,value in enumerate(original))
            if values() != expected:
                raise RuntimeError('写入期间单位类型代码发生变化，已停止本次操作')
            # Record the attempted cell first: an OS error can follow a partial write.
            written.append(index)
            memory.write_u32(address, target)
            if memory.read_u32(address) != target:
                raise RuntimeError('单位类型代码写入后读回不一致')
            trace.record('cell_written', index=index, address=address, value=target)
        identity()
        if values() != (target,):
            raise RuntimeError('单位类型代码写入后读回不一致')
        rebound = session.bind_unit(memory,registry,ObjectAddress(ref.address.value))
        if rebound != replace(ref,rawcode=target):
            raise RuntimeError('修改后单位完整身份校验未通过')
        trace.record('verified', unit=rebound, values=values(), same_object=True,
                     skin_before=skin_before,skin_after=memory.read_u32(skin_address),skin_written=False)
        return rebound
    except Exception as exc:
        restored = not written
        try:
            identity()
            current = values()
            if any(current[i] not in (original[i],target) for i in range(len(addresses))):
                raise RuntimeError('单位状态由游戏改变，未覆盖当前代码')
            for index in reversed(written):
                identity()
                if memory.read_u32(addresses[index]) not in (original[index],target):
                    raise RuntimeError('恢复前单位代码再次变化，未覆盖当前状态')
                memory.write_u32(addresses[index],original[index])
            restored = values() == original
        except Exception as rollback:
            trace.record('rollback_error', error=repr(rollback), attempted_cells=written)
        trace.record('failed', error=repr(exc), original_restored=restored, attempted_cells=written)
        exc.unit_type_report = dict(original_restored=restored, attempted_cells=tuple(written),
                                    before=original, requested=target)
        if not restored:
            raise RuntimeError('本次单位代码修改未完成，原代码恢复未确认；请重新读取当前单位，勿重复点击写入') from exc
        raise


def set_type_code(host, code, unit_identity, expected_code, logger_factory):
    target = parse_code(code)
    if (not isinstance(unit_identity,tuple) or len(unit_identity)!=3
            or any(type(n) is not int or n<=0 for n in unit_identity)
            or type(expected_code) is not int or not 0<expected_code<=0xffffffff):
        raise ValueError('请先读取需要修改的单位')
    engine = host._engine_instance_24268()
    session = engine.session
    request = dict(unit_identity=unit_identity, expected_code=expected_code, requested_code=target,
                   operation='edit_unit_type_code', morph_requested=False)
    with UnitTypeTrace(host,logger_factory,request) as trace, session.lock:
        trace.bind_engine(engine)
        with host._process_memory(write=True) as memory:
            registry,_,_ = session.prepare(memory)
            with session_scope(session):
                selected = tuple(host._selected_candidates_snapshot(memory))
                if len(selected)!=1:
                    raise ValueError('修改单位代码时请只选中一个单位')
                candidate,_ = selected[0]
                if (candidate.handle,candidate.owner_address,candidate.unit_address)!=unit_identity:
                    raise RuntimeError('当前选中单位与已读取单位不同，请重新读取')
                ref = session.bind_unit(memory,registry,ObjectAddress(candidate.unit_address))
                if type(ref) is not UnitRef or ref.rawcode!=expected_code or candidate.unit_type_id!=expected_code:
                    raise RuntimeError('单位类型代码已变化，请重新读取后再修改')
                try:
                    result = _write_bound_code(memory,registry,session,ref,candidate.owner_address,
                                               session.profile.adapter.units,target,trace)
                finally:
                    # Invalidate cached fields/abilities of this object after any attempt.
                    # Keep session resources and unrelated toggles, e.g. game speed.
                    from war3_trainer_session import invalidate_trainer
                    invalidate_trainer(host,'unit type code edit')
        return trace.finish(dict(before=ref.rawcode,after=result.rawcode,changed=result.rawcode!=ref.rawcode,
                                 readback_verified=True,morph_effect_verified=False,
                                 target_definition_verified=False))
