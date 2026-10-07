"""Explicit diagnostic-only contract for a classifier/native-equip experiment."""
import struct
from war3_extension_protocol import ABI, WORK_SIZE, decode_work
from war3_extension_protocol import validate_work as validate_extension


def validate_work(payload):
    if len(payload)!=WORK_SIZE:
        raise ValueError('Legacy equipment probe size differs')
    template=struct.unpack_from('<Q',payload,648)[0]
    item=struct.unpack_from('<Q',payload,672)[0]
    action,slot,rawcode,count=struct.unpack_from('<4I',payload,680)
    if action not in (13,14,15) or slot>=9 or not rawcode or not item or count:
        raise ValueError('Invalid legacy equipment probe')
    if not 0x10000<=template<0x800000000000 or template%8:
        raise ValueError('Invalid item-template pointer')
    common=bytearray(payload)
    struct.pack_into('<Q',common,672,0)
    struct.pack_into('<4I',common,680,0,0,0,0)
    common[720:736]=bytes(16)
    validate_extension(bytes(common))
