"""Diagnostic-only create/level/remove contract for a fresh temporary hero."""
import struct
WORK_SIZE = 128
ABI = struct.pack('<3I',0x24268004,216,WORK_SIZE)
SIGNATURES = (('GetOwningPlayer','(Hunit;)Hplayer;'),('GetUnitTypeId','(Hunit;)I'),
 ('GetUnitX','(Hunit;)R'),('GetUnitY','(Hunit;)R'),
 ('CreateUnit','(Hplayer;IRRR)Hunit;'),('RemoveUnit','(Hunit;)V'),
 ('GetHeroLevel','(Hunit;)I'),('SetHeroLevel','(Hunit;IB)V'))

def build_work(entries, source, rawcode, target, tls):
    handlers=[]
    for name,sig in SIGNATURES:
        e=entries.get(name)
        if e is None or e.name!=name or e.signature!=sig:
            raise ValueError('Lifecycle native signature mismatch: '+name)
        handlers.append(e.handler)
    work=struct.pack('<9QIiQ',*handlers,source,rawcode,target,tls)+bytes(40)
    validate_work(work)
    return work

def validate_work(work):
    if len(work)!=WORK_SIZE: raise ValueError('LifecycleWork must be 128 bytes')
    values=struct.unpack_from('<9QIiQ',work)
    if any(not 0x10000<=v<0x800000000000 for v in values[:8]) or len(set(values[:8]))!=8:
        raise ValueError('Invalid lifecycle handler pointers')
    if not 0<values[8]<=0xffffffff or not values[9] or not 2<=values[10]<=10:
        raise ValueError('Invalid lifecycle source or bounded target level')
    if not 0x10000<=values[11]<0x800000000000 or values[11]%8:
        raise ValueError('Invalid expected TLS')
    if any(work[88:]): raise ValueError('Lifecycle output must be zero')

def decode_work(work):
    if len(work)!=WORK_SIZE: raise ValueError('Truncated lifecycle result')
    created,phase,error,removed,before,after,removed_type,created_type,reserved=struct.unpack_from('<QIIIiiIII',work,88)
    source,rawcode,target=struct.unpack_from('<QIi',work,64)
    result=dict(created=created,phase=phase,error=error,removed=bool(removed),
                before=before,after=after,removed_type=removed_type,created_type=created_type)
    result['mutation_verified']=bool(created and created!=source and phase==5 and not error and removed==1
        and before>0 and after==target and created_type==rawcode and not reserved)
    result['ok']=result['mutation_verified'] and removed_type==0
    return result

MEMBERSHIP_ABI=struct.pack('<3I',0x24268005,216,80)
MEMBERSHIP_SIGNATURES=(('CreateGroup','()Hgroup;'),('GetOwningPlayer','(Hunit;)Hplayer;'),
 ('GroupEnumUnitsOfPlayer','(Hgroup;Hplayer;Hboolexpr;)V'),('IsUnitInGroup','(Hunit;Hgroup;)B'),
 ('DestroyGroup','(Hgroup;)V'))
def build_membership(entries,unit,tls):
    handlers=[]
    for name,sig in MEMBERSHIP_SIGNATURES:
        e=entries.get(name)
        if e is None or e.name!=name or e.signature!=sig:raise ValueError('Membership signature mismatch: '+name)
        handlers.append(e.handler)
    payload=struct.pack('<7Q',*handlers,unit,tls)+bytes(24)
    validate_membership(payload)
    return payload

def validate_membership(payload):
    if len(payload)!=80:raise ValueError('Membership work must be 80 bytes')
    values=struct.unpack_from('<7Q',payload)
    if (any(not 0x10000<=p<0x800000000000 for p in values[:5]) or len(set(values[:5]))!=5
        or not 0<values[5]<=0xffffffff or not 0x10000<=values[6]<0x800000000000
        or values[6]%8 or any(payload[56:])):raise ValueError('Invalid membership work')

def decode_membership(payload):
    if len(payload)!=80:raise ValueError('Truncated membership result')
    group,player,member,destroyed=struct.unpack_from('<2Q2I',payload,56)
    if not group or not player or member not in (0,1) or destroyed!=1:
        raise ValueError('Membership query or cleanup failed')
    return dict(group=group,player=player,member=bool(member),destroyed=True)
