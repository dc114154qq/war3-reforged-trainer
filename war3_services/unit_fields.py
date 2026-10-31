"""Identity-bound native unit fields and the shared weapon-range route."""
from dataclasses import replace
import math
from war3_game_session import session_scope
from war3_unit_field_protocol import value_bits
from war3_unit_fields import UNIT_FIELDS

KINDS={'boolean':0,'integer':1,'real':2}
CATEGORIES={'combat':'战斗','stats':'状态','art':'外观','move':'移动','text':'文本','path':'路径','sound':'音效','tech':'科技'}
RANGE_FIELDS=((int.from_bytes(b'ua1r','big'),2,1,0),(int.from_bytes(b'ua1r','big'),2,2,0))

def weapon_ranges(host,candidate):
    engine=host._engine_instance_24268()
    candidate,native=host._stat_target_24268(candidate)
    result=engine.unit_fields(RANGE_FIELDS,target_unit=native,rawcode=int(candidate.unit_type_id))
    return native,tuple(f['value'] for f in result['rows'][0]['fields'])

def replace_range_fields(host,candidate,fields):
    if not getattr(host,'pid',0) or not getattr(host,'hwnd',0) or getattr(host,'_game_session',None) is None:
        return fields
    if not any(f.key in ('attack1_range','attack2_range') for f in fields):return fields
    try:
        getter=getattr(host,'_unit_ranges_for_candidate_24268',None)
        native,values=getter(candidate) if getter else weapon_ranges(host,candidate)
        replacements={f'attack{i+1}_range':v for i,v in enumerate(values)}
        return [replace(f,value=replacements[f.key],write_address=0,write_type='',native_write=f.key=='attack1_range',
                        native_component_identity=(native,int(candidate.unit_type_id)),
                        note=('游戏原生武器射程；写入后直接读回，不使用旧组件偏移' if f.key=='attack1_range' else '第二武器射程可读取；游戏现有原生接口无法可靠写入')) if f.key in replacements else f for f in fields]
    except Exception as exc:
        # Old offsets are not a fallback for a failed authoritative query.
        return [replace(f,write_address=0,write_type='',native_write=False,
                        note='原生射程读取失败，未开放写入：'+str(exc))
                if f.key in ('attack1_range','attack2_range') else f for f in fields]

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
                note=('该字段是文本定义；当前未提供经过验证的游戏字符串写入接口' if kind=='string' else '第二武器射程可读取；游戏现有原生接口无法可靠写入' if code=='ua1r' and slot==2 else '原生字段；写入以游戏接受且读回一致为准')))
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
            supported=[r for r in rows if r['kind'] in KINDS]
            for start in range(0,len(supported),32):
                batch=supported[start:start+32]
                result=engine.unit_fields(tuple((int.from_bytes(r['code'].encode(),'big'),KINDS[r['kind']],r['weapon'],0) for r in batch),target_unit=native.value,rawcode=ref.rawcode)
                for row,value in zip(batch,result['rows'][0]['fields']):
                    actual=value['value']
                    if isinstance(actual,float) and not math.isfinite(actual):
                        row.update(value=None,writable=False,note='游戏返回非有限实数，未开放写入')
                    else:row['value']=actual
            with self.host._process_memory() as memory:
                registry,_,_=session.prepare(memory);session.resolve(memory,registry,ref)
            self.snapshot=(session,ref,native.value)
            return dict(success=True,rawcode=ref.rawcode,unitCode=ref.rawcode.to_bytes(4,'big').decode('ascii','replace'),
                        identity=f'{ref.handle.value}:{ref.address.value}',rows=rows)

    def write(self,key,value):
        if not hasattr(self,'snapshot'):raise ValueError('请先读取单位字段')
        row=next((r for r in catalogue() if r['key']==key),None)
        if not row or not row['writable']:raise ValueError('此字段没有经过验证的写入接口')
        bits=value_bits(KINDS[row['kind']],value)
        session,ref,native=self.snapshot;engine=self.host._engine_instance_24268()
        with session.lock,session_scope(session):
            if engine.session is not session:raise RuntimeError('游戏会话已变化，请重新读取')
            with self.host._process_memory() as memory:
                registry,_,_=session.prepare(memory);session.resolve(memory,registry,ref)
            bindings=engine.bind_unit_refs((ref,),strict_selection=False)
            if bindings[0][0].value!=native or bindings[0][1]!=ref:raise RuntimeError('单位身份已变化，请重新读取')
            if row['code']=='ua1r':actual=write_range_verified(engine,native,ref.rawcode,row['weapon'],bits)
            else:
                result=engine.unit_fields(((int.from_bytes(row['code'].encode(),'big'),KINDS[row['kind']],row['weapon'],bits),),1,native,ref.rawcode)
                actual=result['rows'][0]['fields'][0]['value']
            with self.host._process_memory() as memory:
                registry,_,_=session.prepare(memory);session.resolve(memory,registry,ref)
            return dict(success=True,key=key,value=actual)
