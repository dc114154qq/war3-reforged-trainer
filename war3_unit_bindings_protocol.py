"""Read-only, exact selected NativeHandle -> UnitRef conversion."""
import struct
from war3_game_session import UnitRef,NativeHandle,FullHandle,ObjectAddress
from war3_selection_protocol import SIGNATURES,build_work as selection_build,validate_work as selection_validate,decode_work as selection_result

WORK_SIZE=1280
ABI=struct.pack('<3I',0x24268065,216,WORK_SIZE)

def validate_refs(refs):
    refs=tuple(refs)
    if not 1<=len(refs)<=24 or any(type(ref) is not UnitRef for ref in refs):
        raise ValueError('Unit bindings require 1..24 typed UnitRef values')
    first=refs[0]
    if (len({ref.handle.value for ref in refs})!=len(refs) or len({ref.address.value for ref in refs})!=len(refs)
            or any(ref.session!=first.session or ref.epoch!=first.epoch or type(ref.handle) is not FullHandle
                   or type(ref.address) is not ObjectAddress or not 0<ref.rawcode<=0xffffffff for ref in refs)):
        raise ValueError('Unit bindings mix sessions, generations or duplicate objects')
    return refs

def build_work(entries,tls,*,base,unit_resolver,refs,strict_selection=True):
    refs=validate_refs(refs)
    if type(strict_selection) is not bool or type(tls) is not int or tls<0x10000:
        raise ValueError('Invalid unit binding query context')
    rows=b''.join(struct.pack('<2Q2I',ref.handle.value,ref.address.value,ref.rawcode,0) for ref in refs)
    payload=selection_build(entries)+struct.pack('<2Q4I',base,unit_resolver,len(refs),int(strict_selection),0,0)
    payload+=rows+bytes(24*(24-len(refs)))+bytes(192)
    validate_work(payload);return payload

def validate_work(payload):
    if len(payload)!=WORK_SIZE:raise ValueError('Unit binding work size differs')
    selection_validate(payload[:480])
    base,resolver,count,strict,error,completed=struct.unpack_from('<2Q4I',payload,480)
    if (not 0x10000<=base<0x800000000000 or not 0x10000<=resolver<0x800000000000
            or not 1<=count<=24 or strict not in (0,1) or error or completed
            or any(payload[512+count*24:])):
        raise ValueError('Invalid unit binding request')
    seen_full=set();seen_object=set()
    for i in range(count):
        full,obj,raw,reserved=struct.unpack_from('<2Q2I',payload,512+i*24)
        if not full or not 0x10000<=obj<0x800000000000 or obj%8 or not raw or reserved or full in seen_full or obj in seen_object:
            raise ValueError('Invalid unit binding object identity')
        seen_full.add(full);seen_object.add(obj)

def decode_work(payload,expected_count,*,expected_sources):
    refs=validate_refs(expected_sources)
    if len(payload)!=WORK_SIZE:raise ValueError('Incomplete unit binding response')
    selection=selection_result(payload[:480],expected_count)
    count,strict,error,completed=struct.unpack_from('<4I',payload,496)
    if error or count!=len(refs) or completed!=len(refs) or strict not in (0,1) or (strict and selection['count']!=count):
        raise ValueError(f'Unit binding query rejected: error={error}, completed={completed}')
    handles=struct.unpack_from('<24Q',payload,1088)
    expected_wire=b''.join(struct.pack('<2Q2I',ref.handle.value,ref.address.value,ref.rawcode,0) for ref in refs)
    if payload[512:512+count*24]!=expected_wire or any(payload[512+count*24:1088]) or any(handles[count:]) or len(set(handles[:count]))!=count:
        raise ValueError('Unit binding response changed immutable source identities')
    selected={row['handle']:row['rawcode'] for row in selection['rows']}
    if any(selected.get(handle)!=ref.rawcode for handle,ref in zip(handles,refs)):
        raise ValueError('Unit binding native handle is not the same selected object')
    return tuple((NativeHandle(handle),ref) for handle,ref in zip(handles,refs))

def failure_status(payload):
    if len(payload)!=WORK_SIZE:return None
    count,strict,error,completed=struct.unpack_from('<4I',payload,496)
    if not error:return None
    group_error,destroyed=struct.unpack_from('<2I',payload,84)
    clean=error in (1,3,4) and group_error==0 and destroyed==1
    return dict(error=error,completed=completed,changed=0,cleanup=int(not clean),
                session_continuable=clean,read_only_rejection=True)
