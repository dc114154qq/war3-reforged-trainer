"""Current-build batch hero progression ABI, independent of historical opcodes."""
import struct
from war3_selection_protocol import build_work as selection_work,decode_work as selection_result
WORK_SIZE=608
ABI=struct.pack('<3I',0x24268010,216,WORK_SIZE)

def build_work(entries,tls,target=0):
    setter=entries.get('SetHeroLevel')
    if setter is None or setter.signature!='(Hunit;IB)V' or setter.name!='SetHeroLevel':
        raise ValueError('SetHeroLevel signature differs from current ABI')
    work=selection_work(entries)+struct.pack('<2Q4I',setter.handler,tls,target,0,0,0)+bytes(96)
    validate_work(work)
    return work

def validate_work(work):
    from war3_selection_protocol import validate_work as selection_validate
    if len(work)!=WORK_SIZE:raise ValueError('Hero batch work must contain 608 bytes')
    selection_validate(work[:480])
    setter,tls,target,changed,error,reserved=struct.unpack_from('<2Q4I',work,480)
    if (not 0x10000<=setter<0x800000000000 or not 0x10000<=tls<0x800000000000 or tls%8
        or not 0<=target<=100000 or changed or error or reserved or any(work[512:])):
        raise ValueError('Invalid hero batch arguments')

def decode_work(work,expected_count):
    if len(work)!=WORK_SIZE:raise ValueError('Incomplete hero batch result')
    selection=selection_result(work[:480],expected_count)
    setter,tls,target,changed,error,reserved=struct.unpack_from('<2Q4I',work,480)
    after=struct.unpack_from('<24i',work,512)
    rows=[dict(row,after=after[i]) for i,row in enumerate(selection['rows']) if row['level']>0]
    if (error or reserved or not rows or changed>len(rows)
        or any(r['after']!=(target or r['level']) for r in rows)
        or changed!=sum(1 for r in rows if target and r['level']!=target)):
        raise ValueError(f'Hero batch incomplete: error={error}, changed={changed}, heroes={len(rows)}')
    return dict(rows=rows,changed=changed,skipped=selection['count']-len(rows),selection_count=selection['count'])
