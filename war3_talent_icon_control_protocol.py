"""Control one verified, separately mapped UI display module on the game thread."""
import struct

WORK_SIZE=96
ABI=struct.pack('<3I',0x24268046,216,WORK_SIZE)

def build_work(tls,image,install,remove,add_table,delete_table,table,config,count,action,registered=0):
    payload=struct.pack('<8Q8I',tls,image,install,remove,add_table,delete_table,table,config,
                        count,action,registered,0,0,0,0,0)
    validate_work(payload)
    return payload

def validate_work(payload):
    if len(payload)!=WORK_SIZE:raise ValueError('Talent icon control ABI size differs')
    tls,base,install,remove,add,delete,table,config,count,action,registered,*outputs=struct.unpack('<8Q8I',payload)
    if any(not 0x10000<=p<0x800000000000 for p in (tls,base,install,remove,add,delete,table,config)):
        raise ValueError('Invalid talent icon control pointer')
    if base%0x10000 or any(not base<=p<base+0x1000000 for p in (install,remove,table,config)):
        raise ValueError('UI entry is outside the mapped module')
    if not 0<count<=0x10000 or action not in (0,1) or registered not in (0,1) or any(outputs):
        raise ValueError('Invalid talent icon control state')

def decode_work(payload,count):
    if len(payload)!=WORK_SIZE or count!=1:raise ValueError('Incomplete talent icon control response')
    n,action,registered,error,completed,result,installed,active=struct.unpack_from('<8I',payload,64)
    if completed!=1:raise ValueError('Talent icon control did not complete')
    return dict(action=action,registered=bool(registered),error=error,success=bool(result and not error),
                installed=bool(installed),active=active)
