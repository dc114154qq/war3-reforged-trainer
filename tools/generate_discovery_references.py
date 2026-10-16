"""Compile strict data-only discovery references from an explicitly supplied capture."""
import argparse
import json
from pathlib import Path
import sys
import struct
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def generate(profile,capture,base=None):
    from capstone import Cs,CS_ARCH_X86,CS_MODE_64
    from war3_profile_discovery import DiscoveryImage,ImageSegment
    metadata=json.loads((capture/'capture.json').read_text(encoding='utf8'))
    if tuple(metadata['fingerprint'])!=profile.fingerprint:raise ValueError('Capture and source adapter identities differ')
    segments=[]
    import hashlib
    for section in metadata['sections']:
        path=(capture/section['file']).resolve()
        if path.parent!=capture.resolve():raise ValueError('Capture file outside capture directory')
        data=path.read_bytes()
        if len(data)!=section['size'] or hashlib.sha256(data).hexdigest()!=section['sha256']:
            raise ValueError('Capture content does not match its recorded digest')
        segments.append(ImageSegment(section['rva'],data,section['name']=='.text',section['name']))
    image=DiscoveryImage(base or 0,profile.fingerprint[2],segments,profile.fingerprint)
    refs={};decoder=Cs(CS_ARCH_X86,CS_MODE_64)
    for key in ('object_resolver','speed_factor','effective_interval','unit_resolver'):
        rva=profile.section('addresses')[key]
        if not rva:continue
        code=image.read(rva,160)
        if key=='effective_interval':
            end=next((i.address-rva+i.size for i in decoder.disasm(code,rva) if i.mnemonic=='ret'),len(code))
            code=code[:end]
        refs['addresses.'+key]={'rva':rva,'code':code.hex()}
    for group,rows in profile.data['checks'].items():
        for index,row in enumerate(rows):
            expected=bytes.fromhex(row['bytes'])
            # A profile witness may have been observed via another valid capture.
            # Its own exact bytes are already maintained with the official profile.
            refs[f'checks.{group}.{index}']={'rva':row['rva'],'code':expected.hex()}
    text_segment=next(s for s in segments if s.name=='.text')
    for key,ref in refs.items():
        if not key.startswith('addresses.'):continue
        data=text_segment.data;position=0;sites=[]
        while (position:=data.find(b'\xe8',position))>=0:
            if (position+5<=len(data) and position+text_segment.rva+5+
                    struct.unpack_from('<i',data,position+1)[0]==ref['rva']):
                code=data[position:position+64]
                insns=list(decoder.disasm(code,position+text_segment.rva))
                if len(insns)>=8 and insns[0].mnemonic=='call':
                    extent=insns[-1].address+insns[-1].size-position-text_segment.rva
                    sites.append({'rva':position+text_segment.rva,'code':code[:extent].hex()})
            position+=1
        if sites:ref['call_sites']=sites[:32]
    text=next(s for s in metadata['sections'] if s['name']=='.text')
    result={'source_digest':profile.digest,'references':refs,
            'text_identity':{key:text[key] for key in ('rva','size','sha256')}}
    # Reviewed semantic operands are independent of this target build's
    # answer. Never generate field names by equality with its numeric offsets.
    semantic_path=ROOT/'profiles/discovery/semantics.json'
    if semantic_path.is_file():
        semantics=json.loads(semantic_path.read_text(encoding='utf8'))
        from war3_profile_discovery import RECIPE_VERSION
        if semantics['recipe_version'] != RECIPE_VERSION:
            raise ValueError('Semantic witness recipe version differs')
        refs['semantic_fields']=semantics['consumers']
        refs['native_abi_forwarders']=semantics.get('native_abi_forwarders',[])
        # New source-class recipes must not enter an older holdout's inputs.
        if tuple(map(int,profile.data['game_version'].split('.')))>=tuple(map(int,semantics.get('stat_source_game_version','999.0.0.0').split('.'))):
            refs['stat_field_consumers']=semantics.get('stat_field_consumers',[])
        # A producer may gain an argument without changing its member's
        # meaning. Keep each reviewed code shape tied to its source version;
        # historical holdouts must never receive future source recipes.
        variants=semantics.get('stat_field_consumer_versions',{})
        applicable=[version for version in variants if tuple(map(int,version.split('.')))<=
                    tuple(map(int,profile.data['game_version'].split('.')))]
        if applicable:
            version=max(applicable,key=lambda value:tuple(map(int,value.split('.'))))
            refs['stat_field_consumers']=variants[version]
    if base is not None:
        result['static_identity']=[{'section':s.name,'rva':s.rva,'size':len(s.data),
            'sha256':image.canonical_digest(s.rva,len(s.data),pointers=s.name=='.rdata')}
            for s in segments if s.name in ('.rdata','.pdata')]
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--profile',type=Path,required=True)
    parser.add_argument('--capture',type=Path,required=True);parser.add_argument('--base',type=lambda s:int(s,0))
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    from war3_game_profile import load_profile
    from war3_profile_discovery import atomic_json,RECIPE_VERSION
    profile=load_profile(args.profile)
    book=json.loads(args.output.read_text(encoding='utf8')) if args.output.exists() else {'recipe_version':RECIPE_VERSION,'sources':{}}
    if book['recipe_version']!=RECIPE_VERSION:raise ValueError('Recipe schema differs')
    book['sources'][profile.data['game_version']]=generate(profile,args.capture,args.base)
    atomic_json(args.output,book)
    print(json.dumps({'version':profile.data['game_version'],'output':str(args.output),'source_digest':profile.digest}))


if __name__=='__main__':main()
