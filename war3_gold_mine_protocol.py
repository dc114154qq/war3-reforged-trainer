"""Gold mine ABI: a bounded, single-callback native read or absolute assignment."""
import math
import struct
from war3_selection_protocol import SIGNATURES as SELECTION, build_work as selection_work

MAX_MINES = 4096
MAX_AMOUNT = 100_000_000
WORK_SIZE = 197240
HEADER = 632
ABI = struct.pack('<3I', 0x24268078, 216, WORK_SIZE)
SIGNATURES = (
    ('Player', '(I)Hplayer;'),
    ('GroupEnumUnitsOfPlayer', '(Hgroup;Hplayer;Hboolexpr;)V'),
    ('GetResourceAmount', '(Hunit;)I'),
    ('SetResourceAmount', '(Hunit;I)V'),
    ('GetUnitAbilityLevel', '(Hunit;I)I'),
    ('GetWidgetLife', '(Hwidget;)R'),
    ('GetUnitX', '(Hunit;)R'),
    ('GetUnitY', '(Hunit;)R'),
    ('GetOwningPlayer', '(Hunit;)Hplayer;'),
    ('GetPlayerId', '(Hplayer;)I'),
)

def build_work(entries, tls, action=0, scope=0, target=0):
    if any(type(v) is not int for v in (action, scope, target)):
        raise ValueError('金矿操作参数应为整数')
    pointers=[]
    for name,signature in SIGNATURES:
        entry=entries.get(name)
        if entry is None or entry.name!=name or entry.signature!=signature:
            raise ValueError('Gold mine native signature differs: '+name)
        pointers.append(entry.handler)
    raw=bytearray(WORK_SIZE)
    raw[:480]=selection_work(entries)
    struct.pack_into('<11Q4I',raw,480,*pointers,tls,action,scope,target,MAX_MINES)
    validate_work(raw)
    return bytes(raw)

def validate_work(raw, *, fixture=False):
    if len(raw)!=WORK_SIZE:raise ValueError('Incomplete gold mine payload')
    from war3_selection_protocol import validate_work as validate_selection
    validate_selection(raw[:480],fixture=fixture)
    pointers=struct.unpack_from('<11Q',raw,480)
    action,scope,target,limit=struct.unpack_from('<4I',raw,568)
    if (action not in (0,1) or scope not in (0,1) or target>MAX_AMOUNT or
            not action and target or limit!=MAX_MINES):raise ValueError('Invalid gold mine request')
    if not fixture and (any(not 0x10000<=p<0x800000000000 for p in pointers) or pointers[-1]%8):
        raise ValueError('Invalid gold mine handler or TLS pointer')
    if len(set(pointers[:-1]))!=10:raise ValueError('Duplicate gold mine native handlers')
    if any(raw[584:]):raise ValueError('Gold mine outputs must start empty')

def status(raw):
    if len(raw)!=WORK_SIZE:return {}
    keys=('count','visited','ignored','changed','unchanged','failed','error','completed','created','destroyed','truncated','uncertain')
    result=dict(zip(keys,struct.unpack_from('<12I',raw,584)))
    result['rows']=[]
    for i in range(min(result['count'],MAX_MINES)):
        values=struct.unpack_from('<QIiii6I',raw,HEADER+i*48)
        row=dict(zip(('handle','rawcode','owner','before','after','kind','status','error','x_bits','y_bits','reserved'),values))
        for key in ('x','y'):row[key]=struct.unpack('<f',struct.pack('<I',row.pop(key+'_bits')))[0]
        result['rows'].append(row)
    return result

def decode_work(raw, expected_count=None):
    result=status(raw)
    if not result:raise ValueError('Incomplete gold mine result')
    if (result['error'] or result['completed']!=1 or result['truncated'] or
            result['count']>MAX_MINES or result['created']!=result['destroyed'] or not result['created'] or
            expected_count not in (None,1)):
        raise ValueError('金矿枚举或临时组清理未通过，错误码：'+str(result['error']))
    action,scope,target,limit=struct.unpack_from('<4I',raw,568)
    if (action not in (0,1) or scope not in (0,1) or target>MAX_AMOUNT or limit!=MAX_MINES or
            not action and target or result['count']>result['visited'] or
            result['visited']>100000 or result['ignored']>result['visited'] or result['created']>28):
        raise ValueError('金矿操作回执或枚举范围异常')
    seen=set()
    for row in result['rows']:
        if (not row['handle'] or row['handle'] in seen or not row['rawcode'] or
            not 0<=row['owner']<28 or not 1<=row['kind']<=15 or row['reserved'] or
            row['status'] not in range(6) or not all(math.isfinite(row[k]) for k in ('x','y'))):
            raise ValueError('金矿结果身份或数值异常')
        seen.add(row['handle'])
        if action and row['status']==0:raise ValueError('金矿修改缺少逐项回执')
        if action and row['status'] in (1,2) and row['after']!=target:
            raise ValueError('金矿剩余金币读回与目标不一致')
        if not action and row['status'] not in (0,3):raise ValueError('金矿读取包含修改结果')
    if action and (sum(r['status']==1 for r in result['rows'])!=result['changed'] or
                   sum(r['status']==2 for r in result['rows'])!=result['unchanged'] or
                   sum(r['status'] in (3,4,5) for r in result['rows'])!=result['failed'] or
                   sum(r['status']==5 for r in result['rows'])!=result['uncertain']):
        raise ValueError('金矿批量修改统计不一致')
    if not action and (result['changed'] or result['unchanged'] or result['uncertain'] or
                       sum(r['status']==3 for r in result['rows'])!=result['failed']):
        raise ValueError('金矿只读回执包含写入统计')
    return dict(result,action=action,scope=scope,target=target)
