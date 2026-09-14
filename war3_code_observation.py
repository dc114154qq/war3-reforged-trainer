"""Validate bounded probe transport separately from code authenticity."""
import struct

def inspect_code_observation(payload, result):
    if len(payload)!=408 or len(result)!=408:raise ValueError('Code observation size differs')
    address,tls,count,copied=struct.unpack_from('<2Q2I',result)
    source,expected_tls,requested,_=struct.unpack_from('<2Q2I',payload)
    if address!=source or tls!=expected_tls or count!=requested or copied!=requested or not 1<=count<=384:
        raise ValueError('Code observation identity or copy count differs')
    data=result[24:24+count]
    if len(set(data))<=1:
        raise ValueError('Uniform probe bytes are not usable code evidence')
    return dict(bytes_hex=data.hex(),code_authenticity='unverified',
                warning='Readable bytes and successful callback do not prove decrypted original instructions')
