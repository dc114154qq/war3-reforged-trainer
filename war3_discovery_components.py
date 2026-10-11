"""Infer component-list members from canonical registry and doubly linked identities.

All searches are bounded read-only probes. Neither plausible stat values nor
an empty list establish a layout. No runtime address enters cached evidence.
"""
import struct
from war3_profile_discovery import DiscoveryEvidence,DiscoveryError

COMPONENT_PATHS=frozenset('layouts.component_list.'+key for key in (
    'head','sentinel','node','previous','next','owner','tag','handle','data','snapshot_start','snapshot_size'))


def _pointer(value):
    return 0x10000<=value<0x800000000000 and value%8==0


def component_probe_units(candidate,memory,registry,selection,budget):
    """A canonical per-player group supplies units, without claiming selection semantics."""
    from war3_game_profile import GameProfile,profile_scope,_freeze
    from war3_classic_selection import read_player_selection
    if selection is None or selection.state not in ('candidate','confirmed') or len(selection.candidates)!=1:
        return ()
    data=candidate.to_dict();data['selection']['manager']=selection.candidates[0]
    for module in data['modules'].values():module['fingerprint']=list(candidate.fingerprint)
    probe=GameProfile(_freeze(data),candidate.digest);units=[]
    with profile_scope(probe):
        for player in registry.players(memory):
            budget.check()
            for unit in read_player_selection(memory,player).units:
                if unit not in units:units.append(unit)
            if len(units)>=8:break
        return tuple(units[:8])


def discover_profile_components(candidate,memory,registry,selection,budget):
    units=component_probe_units(candidate,memory,registry,selection,budget)
    return discover_component_links(memory,registry,units,budget)


def confirm_attack_member(memory,registry,units,members,native,budget):
    """A native's referenced pointer must identify the canonical Aatk component."""
    path='bridge_layout.unit_attack';method='native_cooldown_and_canonical_attack_components'
    if native is None or native.state not in ('candidate','confirmed') or len(native.candidates)!=1:
        return None
    required={'head','node','next','tag','data'}
    if not required<=set(members):return None
    offset=native.candidates[0];witnesses=0
    for unit in tuple(dict.fromkeys(units))[:8]:
        budget.check('正在核对实际攻击组件身份')
        full,owner=registry.resolve_unit(memory,unit);head=struct.unpack('<Q',budget.read(memory,owner+members['head'],8))[0]
        link=head;visited=set();attacks=[]
        while link:
            if link in visited or len(visited)>=256:raise ValueError('Cyclic attack component graph')
            visited.add(link);wrapper=link-members['node']
            tag=struct.unpack('<Q',budget.read(memory,wrapper+members['tag'],8))[0]
            if tag>>32==0x4161746b:
                identity=struct.unpack('<Q',budget.read(memory,wrapper+registry.layout['owner_handle'],8))[0]
                if registry.resolve_handle(memory,identity)!=wrapper:raise ValueError('Attack wrapper replaced')
                attacks.append(struct.unpack('<Q',budget.read(memory,wrapper+members['data'],8))[0])
            link=struct.unpack('<Q',budget.read(memory,wrapper+members['next'],8))[0]
        observed=struct.unpack('<Q',budget.read(memory,unit+offset,8))[0]
        if len(attacks)>1 or observed!=(attacks[0] if attacks else 0):
            return DiscoveryEvidence(path,'unresolved',method,anchors=native.anchors,
                                     detail='Native member differs from canonical Aatk identity')
        if (struct.unpack('<Q',budget.read(memory,owner+members['head'],8))[0]!=head or
                registry.resolve_unit(memory,unit)!=(full,owner)):
            return DiscoveryEvidence(path,'unresolved',method,detail='Unit changed during attack validation')
        witnesses+=bool(attacks)
    return DiscoveryEvidence(path,'confirmed' if witnesses>=2 else 'unresolved',method,
                             (offset,) if witnesses>=2 else (),native.anchors,
                             detail=f'{witnesses} canonical attack components')


def discover_component_links(memory,registry,units,budget,*,owner_span=320,node_span=192):
    if not 160<=owner_span<=512 or not 152<=node_span<=256:
        raise ValueError('Component discovery extent exceeds bounds')
    units=tuple(dict.fromkeys(units))[:8]
    if len(units)<2:return {},{}
    layout=registry.layout;owners=[];snapshots={};blocks={}
    for unit in units:
        full,owner=registry.resolve_unit(memory,unit)
        owners.append((unit,owner,full))
        snapshots[owner]=budget.read(memory,owner,owner_span)
    def raw(address):
        if address not in blocks:blocks[address]=budget.read(memory,address,node_span)
        return blocks[address]
    def q(block,offset):return struct.unpack_from('<Q',block,offset)[0]
    def wrapper(node,node_offset):
        at=node-node_offset
        if not _pointer(at):raise ValueError('Invalid component wrapper')
        block=raw(at);full=q(block,layout['owner_handle'])
        # Zero is a valid registry index for other agent types, never a live
        # component handle witness. Empty sentinels must not resolve object 0.
        if full in (0,0xffffffffffffffff) or registry.resolve_handle(memory,full)!=at:
            raise ValueError('Component identity differs from registry')
        if q(block,layout['owner_tag'])&0xffffffff!=layout['unit_tag']&0xffffffff:
            raise ValueError('Component is not an agent wrapper')
        if not _pointer(q(block,layout['owner_data'])):raise ValueError('Missing component data')
        return at,block,full
    candidates=[];first_unit,first_owner,_=owners[0]
    for head in range(0,owner_span,8):
        first=q(snapshots[first_owner],head)
        if not _pointer(first):continue
        for node_offset in range(0,min(node_span,128),8):
            budget.check('正在定位单位组件链表')
            try:at,block,full=wrapper(first,node_offset)
            except DiscoveryError:raise
            except (OSError,ValueError,RuntimeError):continue
            sentinels=[(member,q(block,member)-first_owner) for member in range(0,node_span,8)
                       if first_owner<=q(block,member)<first_owner+owner_span and q(block,member)!=first_owner]
            backlinks=[member for member in range(0,node_span,8) if q(block,member)==first_owner]
            for previous,sentinel in sentinels:
                for backlink in backlinks:
                    for following in range(0,node_span,8):
                        if following in (previous,backlink,layout['owner_handle'],layout['owner_data'],layout['owner_tag']):continue
                        second=q(block,following)
                        if not _pointer(second) or second==first:continue
                        try:second_at,second_raw,_=wrapper(second,node_offset)
                        except DiscoveryError:raise
                        except (OSError,ValueError,RuntimeError):continue
                        if q(second_raw,previous)!=first or q(second_raw,backlink)!=first_owner:continue
                        valid=True;total=0;tags=set();witnessed=0
                        for unit,owner,unit_full in owners:
                            link=q(snapshots[owner],head);prior=owner+sentinel;visited=set();ids=[]
                            try:
                                while link:
                                    budget.check()
                                    if not _pointer(link) or link in visited or len(visited)>=256:raise ValueError('Cyclic component list')
                                    visited.add(link);address,b,identity=wrapper(link,node_offset)
                                    if q(b,previous)!=prior or q(b,backlink)!=owner:raise ValueError('Component backlink mismatch')
                                    ids.append((address,b,identity));tags.add(q(b,layout['owner_tag']))
                                    prior,link=link,q(b,following)
                                if len(ids)<2:raise ValueError('Empty list is not layout evidence')
                                if (q(budget.read(memory,owner+head,8),0)!=q(snapshots[owner],head) or
                                    registry.resolve_unit(memory,unit)!=(unit_full,owner)):
                                    raise ValueError('Unit changed during discovery')
                                identity_members={layout['owner_tag'],layout['owner_handle'],layout['owner_data'],previous,following,backlink}
                                for address,b,identity in ids:
                                    current=budget.read(memory,address,node_span)
                                    if (any(q(current,member)!=q(b,member) for member in identity_members) or
                                        registry.resolve_handle(memory,identity)!=address):
                                        raise ValueError('Component changed during discovery')
                                total+=len(ids);witnessed+=1
                            except DiscoveryError:raise
                            except (OSError,ValueError,RuntimeError):valid=False;break
                        if valid and witnessed>=2 and len(tags)>=3:
                            candidates.append((head,sentinel,node_offset,previous,following,backlink,total,witnessed))
    candidates=list(dict.fromkeys(candidates))
    path='layouts.component_list'
    if len(candidates)!=1:
        return {},{path:DiscoveryEvidence(path,'ambiguous' if candidates else 'unresolved',
                       'canonical_component_links_and_registry_owners',detail=f'{len(candidates)} distinct layouts')}
    head,sentinel,node,previous,following,owner,total,witnessed=candidates[0]
    members={'head':head,'sentinel':sentinel,'node':node,'previous':previous,'next':following,
             'owner':owner,'tag':layout['owner_tag'],'handle':layout['owner_handle'],'data':layout['owner_data']}
    start=min(members[k] for k in ('tag','handle','previous','next','owner','data'))
    end=max(members[k]+8 for k in ('tag','handle','previous','next','owner','data'))
    members.update(snapshot_start=start,snapshot_size=end-start)
    method='canonical_component_links_and_registry_owners';updates={path+'.'+k:v for k,v in members.items()}
    proofs={k:DiscoveryEvidence(k,'confirmed',method,(v,),detail=f'{witnessed} unit owners; {total} component identities') for k,v in updates.items()}
    proofs[path]=DiscoveryEvidence(path,'confirmed',method,detail=f'{witnessed} unit owners; {total} component identities')
    return updates,proofs
