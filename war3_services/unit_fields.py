"""Identity-bound native unit fields and the shared weapon-range route."""
from dataclasses import replace
import math
from war3_game_session import session_scope
from war3_unit_field_protocol import value_bits
from war3_unit_fields import UNIT_FIELDS

KINDS={'boolean':0,'integer':1,'real':2}
CATEGORIES={'combat':'战斗','stats':'状态','art':'外观','move':'移动','text':'文本','path':'路径','sound':'音效','tech':'科技'}
RANGE_FIELDS=((int.from_bytes(b'ua1r','big'),2,1,0),(int.from_bytes(b'ua1r','big'),2,2,0))
ATTACK_TYPE_ID=int.from_bytes(b'ua1t','big')
ATTACK_TYPE_NOTE='攻击类型：0=法术，1=普通，2=穿刺，3=攻城，4=魔法，5=混乱，6=英雄；只修改对应武器，写后按游戏接口读回'
WEAPON_FIELDS={
    'attack1_range':RANGE_FIELDS[0],'attack2_range':RANGE_FIELDS[1],
    'attack1_type':(ATTACK_TYPE_ID,1,1,0),'attack2_type':(ATTACK_TYPE_ID,1,2,0),
}

def attack_type_value(value):
    bits=value_bits(1,value)
    if not 0<=bits<=6:raise ValueError(ATTACK_TYPE_NOTE)
    return bits

def decode_weapon_fields(row,keys):
    fields=row.get('fields',())
    if len(fields)!=len(keys):raise RuntimeError('原生武器字段数量不一致')
    values={}
    for key,field in zip(keys,fields):
        if (field.get('field_id'),field.get('kind'),field.get('weapon'))!=WEAPON_FIELDS[key][:3]:
            raise RuntimeError('原生武器字段身份不一致')
        value=field['value']
        if key.endswith('_type'):attack_type_value(value)
        elif not math.isfinite(value):raise RuntimeError('原生武器射程无效')
        values[key]=value
    return values

def weapon_ranges(host,candidate):
    engine=host._engine_instance_24268()
    candidate,native=host._stat_target_24268(candidate)
    result=engine.unit_fields(RANGE_FIELDS,target_unit=native,rawcode=int(candidate.unit_type_id))
    return native,tuple(f['value'] for f in result['rows'][0]['fields'])

def replace_weapon_fields(host,candidate,fields):
    if not getattr(host,'pid',0) or not getattr(host,'hwnd',0) or getattr(host,'_game_session',None) is None:
        return fields
    keys=tuple(f.key for f in fields if f.key in WEAPON_FIELDS)
    if not keys:return fields
    try:
        getter=getattr(host,'_unit_weapon_fields_for_candidate_24268',None)
        if getter:native,replacements=getter(candidate)
        else:
            candidate,native=host._stat_target_24268(candidate)
            result=host._engine_instance_24268().unit_fields(tuple(WEAPON_FIELDS[k] for k in keys),target_unit=native,rawcode=candidate.unit_type_id)
            rows=result.get('rows',())
            if len(rows)!=1 or (rows[0]['unit'],rows[0]['rawcode'])!=(native,candidate.unit_type_id):
                raise RuntimeError('原生武器字段目标身份不一致')
            replacements=decode_weapon_fields(rows[0],keys)
        return [replace(f,value=replacements[f.key],address=0,write_address=0,write_type='',extra_writes=(),native_write=f.key!='attack2_range',
                        native_component_identity=(native,int(candidate.unit_type_id)),
                        note=(ATTACK_TYPE_NOTE if f.key.endswith('_type') else '游戏原生武器射程；写入后直接读回，不使用旧组件偏移' if f.key=='attack1_range' else '第二武器射程可读取；游戏现有原生接口无法可靠写入')) if f.key in WEAPON_FIELDS else f for f in fields]
    except Exception as exc:
        # Old offsets are not a fallback for a failed authoritative query.
        return [replace(f,address=0,write_address=0,write_type='',extra_writes=(),native_write=False,
                        note='原生武器字段读取失败，未开放写入：'+str(exc))
                if f.key in WEAPON_FIELDS else f for f in fields]

def set_attack_type(host,candidate,field,value):
    bits=attack_type_value(value)
    native,expected=field.native_component_identity
    candidate,actual_native=host._stat_target_24268(candidate)
    if native!=actual_native or expected!=candidate.unit_type_id:raise RuntimeError('攻击类型目标已变化，请重新读取')
    actual=write_attack_type_verified(host._engine_instance_24268(),native,expected,
        1 if field.key=='attack1_type' else 2,bits)
    return replace(field,value=actual)

def write_attack_type_verified(engine,native,rawcode,weapon,value):
    if weapon not in (1,2):raise ValueError('攻击类型武器序号无效')
    value=attack_type_value(value)
    result=engine.unit_fields(((ATTACK_TYPE_ID,1,weapon,value),),1,native,rawcode)
    rows=result.get('rows',())
    if len(rows)!=1 or (rows[0]['unit'],rows[0]['rawcode'])!=(native,rawcode):
        raise RuntimeError('攻击类型写入后的目标身份不一致')
    actual=decode_weapon_fields(rows[0],(f'attack{weapon}_type',))[f'attack{weapon}_type']
    if actual!=value:raise RuntimeError('攻击类型写入后读回与目标不一致')
    return actual

def set_weapon_range(host,candidate,field,value):
    bits=value_bits(2,value)
    if not 0<=float(value)<=1000000:raise ValueError('攻击范围必须在 0 到 1000000 之间')
    native,expected=field.native_component_identity
    candidate,actual_native=host._stat_target_24268(candidate)
    if native!=actual_native or expected!=candidate.unit_type_id:raise RuntimeError('武器范围目标已变化，请重新读取')
    weapon=1 if field.key=='attack1_range' else 2
    engine=host._engine_instance_24268()
    result=write_range_verified(engine,native,expected,weapon,bits)
    return replace(field,value=result)

def write_range_verified(engine,native,rawcode,weapon,bits):
    if weapon!=1:raise ValueError('当前原生接口不支持可靠修改第二武器射程')
    result=engine.unit_fields(((0x75613172,2,weapon,bits),),1,native,rawcode)
    return result['rows'][0]['fields'][0]['value']



def catalogue():
    rows=[]
    for code,constant,kind,weapon,label,en,category in UNIT_FIELDS:
        for slot in ((1,2) if weapon else (0,)):
            name=label
            if weapon:
                name=label.replace('攻击 1','攻击 '+str(slot)).replace('攻击1','攻击'+str(slot))
                if '攻击 '+str(slot) not in name and '攻击'+str(slot) not in name:name=f'攻击 {slot} - {name}'
            rows.append(dict(key=f'{code}:{slot}',code=code,constant=constant,kind=kind,weapon=slot,
                label=name,labelEn=en,category=(f'攻击 {slot}' if slot else CATEGORIES.get(category,'其他')),
                writable=kind in KINDS and not (code=='ua1r' and slot==2), value=None,
                note=(ATTACK_TYPE_NOTE if code=='ua1t' else '该字段是文本定义；当前未提供经过验证的游戏字符串写入接口' if kind=='string' else '第二武器射程可读取；游戏现有原生接口无法可靠写入' if code=='ua1r' and slot==2 else '原生字段；写入以游戏接受且读回一致为准')))
    return rows


class UnitFieldsService:
    def __init__(self,host,logger_factory=None):
        self.host,self.logger_factory=host,logger_factory

    def read(self):
        engine=self.host._engine_instance_24268();session=engine.session
        with session.lock,session_scope(session):
            candidate,_=self.host._direct_selected_context()
            refs=self.host._capture_unit_refs_24268((candidate,))
            native,ref=engine.bind_unit_refs(refs,strict_selection=False)[0]
            rows=catalogue()
            from war3_unit_field_hero_int_protocol import enabled_for,FIELD_IDS
            int_compat=enabled_for(session.profile)
            intelligence=[r for r in rows if int_compat and int.from_bytes(r['code'].encode(),'big') in FIELD_IDS]
            supported=[r for r in rows if r['kind'] in KINDS and r not in intelligence]
            for start in range(0,len(supported),32):
                batch=supported[start:start+32]
                result=engine.unit_fields(tuple((int.from_bytes(r['code'].encode(),'big'),KINDS[r['kind']],r['weapon'],0) for r in batch),target_unit=native.value,rawcode=ref.rawcode)
                for row,value in zip(batch,result['rows'][0]['fields']):
                    actual=value['value']
                    if isinstance(actual,float) and not math.isfinite(actual):
                        row.update(value=None,writable=False,note='游戏返回非有限实数，未开放写入')
                    else:row['value']=actual
            if intelligence:
                result=engine.unit_field_hero_int(tuple((int.from_bytes(r['code'].encode(),'big'),1,0,0) for r in intelligence),
                                                  target_unit=native.value,rawcode=ref.rawcode)
                actual_rows=result.get('rows',())
                if len(actual_rows)!=1 or (actual_rows[0]['unit'],actual_rows[0]['rawcode'])!=(native.value,ref.rawcode):
                    raise RuntimeError('智力字段读取目标不一致，请重新读取')
                if len(actual_rows[0]['fields'])!=len(intelligence):raise RuntimeError('智力字段读回数量不一致')
                for row,value in zip(intelligence,actual_rows[0]['fields']):
                    if (value['field_id'],value['kind'],value['weapon'])!=(int.from_bytes(row['code'].encode(),'big'),1,0):
                        raise RuntimeError('智力字段读回类型不一致')
                    row.update(value=value['value'],note=('3.0.1.24342 兼容：输入目标总智力；保留装备与光环加成，自动换算基础智力并读回确认'
                        if row['code']=='uinb' else '3.0.1.24342 兼容：永久设置当前基础智力；保留装备与光环加成，并按英雄属性读回确认'))
                    if result['hero_intelligence_trace']['base_before']<0:
                        row.update(writable=False,note='当前单位不是英雄，没有英雄智力属性')
            with self.host._process_memory() as memory:
                registry,_,_=session.prepare(memory);session.resolve(memory,registry,ref)
            self.snapshot=(session,ref,native.value)
            return dict(success=True,rawcode=ref.rawcode,unitCode=ref.rawcode.to_bytes(4,'big').decode('ascii','replace'),
                        identity=f'{ref.handle.value}:{ref.address.value}',rows=rows)

    def write(self,key,value):
        if not hasattr(self,'snapshot'):raise ValueError('请先读取单位字段')
        row=next((r for r in catalogue() if r['key']==key),None)
        if not row or not row['writable']:raise ValueError('此字段没有经过验证的写入接口')
        bits=attack_type_value(value) if row['code']=='ua1t' else value_bits(KINDS[row['kind']],value)
        session,ref,native=self.snapshot;engine=self.host._engine_instance_24268()
        with session.lock,session_scope(session):
            if engine.session is not session:raise RuntimeError('游戏会话已变化，请重新读取')
            with self.host._process_memory() as memory:
                registry,_,_=session.prepare(memory);session.resolve(memory,registry,ref)
            bindings=engine.bind_unit_refs((ref,),strict_selection=False)
            if bindings[0][0].value!=native or bindings[0][1]!=ref:raise RuntimeError('单位身份已变化，请重新读取')
            from war3_unit_field_hero_int_protocol import enabled_for,FIELD_IDS
            if enabled_for(session.profile) and int.from_bytes(row['code'].encode(),'big') in FIELD_IDS:
                result=engine.unit_field_hero_int(((int.from_bytes(row['code'].encode(),'big'),1,0,bits),),1,native,ref.rawcode)
                actual_rows=result.get('rows',())
                if len(actual_rows)!=1 or (actual_rows[0]['unit'],actual_rows[0]['rawcode'])!=(native,ref.rawcode):
                    raise RuntimeError('智力字段写入后的目标身份不一致')
                values=actual_rows[0]['fields']
                if len(values)!=1 or (values[0]['field_id'],values[0]['kind'],values[0]['weapon'])!=(int.from_bytes(row['code'].encode(),'big'),1,0) or values[0]['value']!=bits:
                    raise RuntimeError('智力字段写入后读回与目标不符')
                actual=values[0]['value']
            elif row['code']=='ua1r':actual=write_range_verified(engine,native,ref.rawcode,row['weapon'],bits)
            elif row['code']=='ua1t':actual=write_attack_type_verified(engine,native,ref.rawcode,row['weapon'],bits)
            else:
                result=engine.unit_fields(((int.from_bytes(row['code'].encode(),'big'),KINDS[row['kind']],row['weapon'],bits),),1,native,ref.rawcode)
                actual=result['rows'][0]['fields'][0]['value']
            with self.host._process_memory() as memory:
                registry,_,_=session.prepare(memory);session.resolve(memory,registry,ref)
            return dict(success=True,key=key,value=actual)
