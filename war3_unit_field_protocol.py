"""Typed unit/weapon native field ABI, independent of object memory offsets."""
import math
import struct
from war3_selection_protocol import (SIGNATURES as SELECTION_SIGNATURES,
    build_work as build_selection, validate_work as validate_selection, decode_work as decode_selection)
MAX_FIELDS=32
HEADER,FIELDS,STATUS,BEFORE,AFTER,WORK_SIZE=584,616,1128,1224,4296,7368
ABI=struct.pack('<3I',0x24268082,216,WORK_SIZE)
SIGNATURES=tuple((f'Blz{verb}Unit{weapon}{kind}Field',f'(Hunit;Hunit{weapon.lower()}{kind.lower()}field;'+('I' if weapon else '')+(value if verb=='Set' else '')+')'+('B' if verb=='Set' else value))
    for verb in ('Get','Set') for weapon in ('','Weapon') for kind,value in (('Boolean','B'),('Integer','I'),('Real','R')))

def value_bits(kind,value):
    if kind==0:
        if str(value).lower() not in ('0','1','true','false'):raise ValueError('布尔字段只能填写 0/1 或 true/false')
        return int(str(value).lower() in ('1','true'))
    if kind==1:
        result=int(str(value).strip(),0) if str(value).strip().lower().startswith(('0x','-0x')) else int(str(value).strip())
        if not -2147483648<=result<=2147483647:raise ValueError('整数超出 32 位有符号范围')
        return result&0xffffffff
    result=float(value)
    if not math.isfinite(result):raise ValueError('实数字段必须填写有限数值')
    try:raw=struct.pack('<f',result)
    except OverflowError as exc:raise ValueError('实数超出游戏单精度范围') from exc
    if not math.isfinite(struct.unpack('<f',raw)[0]):raise ValueError('实数超出游戏单精度范围')
    return struct.unpack('<I',raw)[0]

def decoded_value(kind,bits):
    if kind==0:
        if bits not in (0,1):raise ValueError('单位布尔字段读回无效')
        return bool(bits)
    return struct.unpack('<f' if kind==2 else '<i',struct.pack('<I',bits))[0]

def descriptor(row):
    if type(row) not in (tuple,list) or len(row)!=4 or any(type(x) is not int for x in row):raise ValueError('单位字段描述格式无效')
    fid,kind,weapon,target=row
    if not 0<fid<=0xffffffff or kind not in (0,1,2) or weapon not in (0,1,2) or not 0<=target<=0xffffffff:raise ValueError('单位字段描述超出范围')
    if kind==0 and target not in (0,1) or kind==2 and not math.isfinite(decoded_value(kind,target)):raise ValueError('单位字段目标值无效')
    return tuple(row)

def handler_indices(fields,action):
    gets={kind+(3 if weapon else 0) for _,kind,weapon,_ in fields}
    return gets|{i+6 for i in gets} if action else gets

def build_work(entries,tls,fields,action=0,target_unit=0,rawcode=0):
    fields=tuple(descriptor(row) for row in fields)
    if type(action) is not int or action not in (0,1) or not 1<=len(fields)<=32:raise ValueError('单位字段动作或数量无效')
    if type(target_unit) is not int or not 0<=target_unit<=0xffffffffffffffff or type(rawcode) is not int or not 0<=rawcode<=0xffffffff:raise ValueError('单位字段目标身份无效')
    if bool(target_unit)!=bool(rawcode) or action and (len(fields)!=1 or not target_unit):raise ValueError('写入需要唯一完整目标，每次只写一个字段')
    pointers=[0]*12
    for i in handler_indices(fields,action):
        name,signature=SIGNATURES[i];entry=entries.get(name)
        if entry is None or entry.name!=name or entry.signature!=signature:raise ValueError('单位字段接口缺失或签名不符：'+name)
        pointers[i]=entry.handler
    result=bytearray(build_selection(entries));result.extend(struct.pack('<13Q',*pointers,tls))
    result.extend(struct.pack('<Q6I',target_unit,rawcode,action,len(fields),0,0,0))
    for row in fields:result.extend(struct.pack('<4I',*row))
    result.extend(bytes(WORK_SIZE-len(result)));validate_work(bytes(result));return bytes(result)

def validate_work(payload):
    if len(payload)!=WORK_SIZE:raise ValueError('单位字段协议长度不符')
    validate_selection(payload[:480]);handlers=struct.unpack_from('<13Q',payload,480)
    if not 0x10000<=handlers[-1]<0x800000000000 or handlers[-1]%8:raise ValueError('单位字段线程上下文无效')
    unit,rawcode,action,count,completed,error,changed=struct.unpack_from('<Q6I',payload,HEADER)
    if action not in (0,1) or not 1<=count<=32 or bool(unit)!=bool(rawcode) or any((completed,error,changed)):raise ValueError('单位字段请求头无效')
    if action and (not unit or count!=1):raise ValueError('写入必须绑定一个目标和一个字段')
    rows=[descriptor(struct.unpack_from('<4I',payload,FIELDS+i*16)) for i in range(count)]
    if len({row[:3] for row in rows})!=count:raise ValueError('单位字段重复')
    for i in handler_indices(rows,action):
        if not 0x10000<=handlers[i]<0x800000000000:raise ValueError('单位字段函数指针无效')
    if any(payload[FIELDS+count*16:]):raise ValueError('单位字段输出必须清零')

def decode_work(payload,expected_count):
    if len(payload)!=WORK_SIZE:raise ValueError('单位字段读回长度不符')
    selection=decode_selection(payload[:480],expected_count)
    unit,rawcode,action,count,completed,error,changed=struct.unpack_from('<Q6I',payload,HEADER)
    if error:
        messages={910:'请求无效',911:'字段描述无效',912:'选中单位读取或临时组清理失败',913:'目标身份已变化，请重新读取',914:'目标已不在当前选择中，请重新读取',915:'游戏返回了无效实数，未写入',916:'游戏拒绝修改此字段，原值已确认保留',917:'游戏读回与目标不符，本次已恢复原值',918:'读回不符且恢复未确认，请查看日志',919:'运行时武器或完整单位身份无效，未继续写入'}
        raise ValueError('单位字段：'+messages.get(error,f'操作失败（{error}）'))
    if not 1<=count<=32 or completed!=expected_count:raise ValueError('单位字段未完整处理当前选择')
    descriptors=[struct.unpack_from('<4I',payload,FIELDS+i*16) for i in range(count)];rows=[]
    for i,selected in enumerate(selection['rows']):
        status=struct.unpack_from('<I',payload,STATUS+i*4)[0];matched=not unit or selected['handle']==unit
        if status!=(1 if matched else 2) or matched and rawcode and selected['rawcode']!=rawcode:raise ValueError('单位字段读回目标不一致')
        if not matched:continue
        values=[]
        for j,(fid,kind,weapon,target) in enumerate(descriptors):
            b=struct.unpack_from('<I',payload,BEFORE+(i*32+j)*4)[0];a=struct.unpack_from('<I',payload,AFTER+(i*32+j)*4)[0]
            if action and a!=target or not action and a!=b:raise ValueError('单位字段业务读回不符')
            values.append(dict(field_id=fid,kind=kind,weapon=weapon,before=decoded_value(kind,b),value=decoded_value(kind,a),bits=a))
        rows.append(dict(unit=selected['handle'],rawcode=selected['rawcode'],fields=values))
    if unit and len(rows)!=1:raise ValueError('单位字段缺少唯一目标')
    return dict(rows=rows,changed=changed,count=len(rows),temporary_group_destroyed=True)
