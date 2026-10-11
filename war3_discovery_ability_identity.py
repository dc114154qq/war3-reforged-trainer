"""Canonical ability data identities corroborated by MSVC base-class RTTI."""
import struct
from war3_profile_discovery import DiscoveryEvidence,DiscoveryError

ABILITY_IDENTITY_PATHS=frozenset(('layouts.ability.full_handle','layouts.ability.vtable'))


def ability_vtable(image,rva,type_descriptors):
    """Read fixed MSVC x64 RTTI ABI, not a game-version object layout."""
    try:
        locator=struct.unpack('<Q',image.read(rva-8,8))[0]-image.base
        signature,offset,cd,typ,hierarchy,self_rva=struct.unpack('<6I',image.read(locator,24))
        if (signature,offset,cd,self_rva)!=(1,0,0,locator):return False
        _,_,count,array=struct.unpack('<4I',image.read(hierarchy,16))
        if not 1<=count<=64:return False
        bases=struct.unpack('<'+'I'*count,image.read(array,count*4))
        types={struct.unpack('<I',image.read(base,4))[0] for base in bases}
        methods=struct.unpack('<3Q',image.read(rva,24))
        return bool(types&set(type_descriptors)) and all(image.executable(method-image.base) for method in methods)
    except (OSError,struct.error):return False


def discover_ability_identity(memory,registry,units,members,image,budget,*,data_span=192):
    if not 160<=data_span<=256:raise ValueError('Ability identity span exceeds bound')
    descriptors=getattr(image,'type_descriptors',{}).get('CAbility',())
    if not descriptors:return {},{}
    full_members=None;vtable_members=None;classes=set();owners=set();identities=[];tables={}
    for unit in tuple(dict.fromkeys(units))[:8]:
        unit_full,owner=registry.resolve_unit(memory,unit)
        head=struct.unpack('<Q',budget.read(memory,owner+members['head'],8))[0]
        node=head;visited=set();count=0
        while node:
            budget.check('正在核对技能数据完整身份')
            if node in visited or len(visited)>=256:raise ValueError('Cyclic ability identity graph')
            visited.add(node);wrapper=node-members['node']
            tag=struct.unpack('<Q',budget.read(memory,wrapper+members['tag'],8))[0]
            full=struct.unpack('<Q',budget.read(memory,wrapper+members['handle'],8))[0]
            data=struct.unpack('<Q',budget.read(memory,wrapper+members['data'],8))[0]
            following=struct.unpack('<Q',budget.read(memory,wrapper+members['next'],8))[0]
            if (tag>>56) not in (ord('A'),ord('B')):
                node=following;continue
            if registry.resolve_handle(memory,full)!=wrapper:raise ValueError('Ability wrapper replaced')
            raw=budget.read(memory,data,data_span)
            full_hits={offset for offset in range(0,data_span-7,8) if struct.unpack_from('<Q',raw,offset)[0]==full}
            table_hits=set()
            for offset in range(0,min(48,data_span-7),8):
                pointer=struct.unpack_from('<Q',raw,offset)[0];rva=pointer-image.base
                if not 0<rva<image.size:continue
                if rva not in tables:tables[rva]=ability_vtable(image,rva,descriptors)
                if tables[rva]:table_hits.add(offset)
            # Only concrete CAbility subclasses contribute. Task wrappers or
            # other agents in the same linked list are not ability evidence.
            if not table_hits:node=following;continue
            full_members=full_hits if full_members is None else full_members&full_hits
            vtable_members=table_hits if vtable_members is None else vtable_members&table_hits
            classes.add(tag>>32);owners.add(owner);identities.append((wrapper,full,data,raw))
            count+=1;node=following
        if (struct.unpack('<Q',budget.read(memory,owner+members['head'],8))[0]!=head or
            registry.resolve_unit(memory,unit)!=(unit_full,owner)):
            raise ValueError('Unit changed during ability discovery')
    if len(owners)<2 or len(classes)<3 or len(identities)<6:return {},{}
    updates={};proofs={};method='canonical_ability_handles_and_base_class_rtti'
    for path,hits in [('layouts.ability.full_handle',full_members),('layouts.ability.vtable',vtable_members)]:
        hits=tuple(sorted(hits or ()))
        proofs[path]=DiscoveryEvidence(path,'confirmed' if len(hits)==1 else 'ambiguous' if hits else 'unresolved',
                                      method,hits,tuple(descriptors),
                                      detail=f'{len(identities)} identities; {len(classes)} CAbility subclasses')
        if len(hits)==1:updates[path]=hits[0]
    # Revalidate only identity words; unrelated running-game counters can change.
    for wrapper,full,data,raw in identities:
        if (registry.resolve_handle(memory,full)!=wrapper or
            struct.unpack('<Q',budget.read(memory,wrapper+members['data'],8))[0]!=data):
            raise ValueError('Ability instance replaced during discovery')
        for member in updates.values():
            if budget.read(memory,data+member,8)!=raw[member:member+8]:
                raise ValueError('Ability identity changed during discovery')
    return updates,proofs
