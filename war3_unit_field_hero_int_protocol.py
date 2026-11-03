"""24342 unit-editor intelligence: bound hero getters/setter, never field guesses."""
import struct
from war3_unit_field_protocol import (HEADER,FIELDS,WORK_SIZE,validate_work as validate_scalar,
                                     decode_work as decode_scalar)
from war3_selection_protocol import build_work as selection_work

ABI=struct.pack('<3I',0x24268090,216,WORK_SIZE)
SIGNATURES=(('GetHeroInt','(Hunit;B)I'),('SetHeroInt','(Hunit;IB)V'))
FIELD_IDS=frozenset(int.from_bytes(x,'big') for x in (b'uinc',b'uinm',b'uinb'))
TOTAL_ID=int.from_bytes(b'uinb','big')
TRACE_OFFSET=FIELDS+8*16
TRACE_MAGIC=0x494e5431
MAX_VALUE=1_000_000

def enabled_for(profile):
    if profile is None:return False
    report=profile.selection_report()
    return (report.get('mode')=='exact' and report.get('actual_game_version')=='3.0.1.24342'
            and report.get('adapter_game_version')=='3.0.1.24342')

def build_work(entries,tls,fields,action=0,target_unit=0,rawcode=0):
    fields=tuple(fields)
    if type(action) is not int or action not in (0,1) or not 1<=len(fields)<=3:
        raise ValueError('智力字段请求数量或动作无效')
    if type(target_unit) is not int or not 0<target_unit<=0xffffffffffffffff or type(rawcode) is not int or not 0<rawcode<=0xffffffff:
        raise ValueError('智力字段必须绑定完整英雄身份')
    if action and len(fields)!=1:raise ValueError('每次只修改一项智力字段')
    if any(type(row) not in (tuple,list) or len(row)!=4 or any(type(v) is not int for v in row)
           or row[0] not in FIELD_IDS or row[1:3] not in ((1,0),[1,0]) or not 0<=row[3]<=MAX_VALUE for row in fields):
        raise ValueError('智力目标必须是 0～1000000 的整数')
    pointers=[0]*12
    for index,(name,sig) in enumerate(SIGNATURES):
        if index and not action:continue
        entry=entries.get(name)
        if entry is None or (entry.name,entry.signature)!=(name,sig):raise ValueError('英雄智力接口缺失或签名不符：'+name)
        pointers[1 if index==0 else 7]=entry.handler
    payload=bytearray(selection_work(entries));payload.extend(struct.pack('<13Q',*pointers,tls))
    payload.extend(struct.pack('<Q6I',target_unit,rawcode,action,len(fields),0,0,0))
    for row in fields:payload.extend(struct.pack('<4I',*row))
    payload.extend(bytes(WORK_SIZE-len(payload)));validate_work(bytes(payload));return bytes(payload)

def validate_work(payload):
    validate_scalar(payload)
    unit,code,action,count,*_=struct.unpack_from('<Q6I',payload,HEADER)
    if not unit or not code or count>3:raise ValueError('英雄智力字段目标或数量无效')
    for i in range(count):
        fid,kind,weapon,target=struct.unpack_from('<4I',payload,FIELDS+i*16)
        if fid not in FIELD_IDS or kind!=1 or weapon or target>MAX_VALUE:
            raise ValueError('英雄智力字段或目标值无效')

def details(payload):
    if len(payload)!=WORK_SIZE:raise ValueError('英雄智力读回长度不符')
    values=struct.unpack_from('<6I7i3I2i',payload,TRACE_OFFSET)
    keys=('magic','version','stage','setter_called','rollback_called','rollback_verified',
          'base_before','total_before','base_first_after','total_first_after','base_final','total_final','target_base','field_id','target',
          'correction_called','base_after_correction','total_after_correction')
    result=dict(zip(keys,values))
    if result['magic'] not in (0,TRACE_MAGIC) or result['version'] not in (0,1):raise ValueError('英雄智力诊断标识无效')
    result['field_code']=result['field_id'].to_bytes(4,'big').decode('ascii','replace')
    return result

def decode_work(payload,expected_count):
    trace=details(payload)
    error=struct.unpack_from('<I',payload,HEADER+24)[0]
    if error==920:raise ValueError('目标智力无法在保留当前加成时实现；请提高目标总值或检查加成范围')
    if error==921:raise ValueError('当前单位不是英雄，不能修改英雄智力')
    result=decode_scalar(payload,expected_count)
    if trace['magic']!=TRACE_MAGIC or trace['version']!=1:raise ValueError('英雄智力读回缺少完整诊断')
    result['hero_intelligence_trace']=trace
    return result
