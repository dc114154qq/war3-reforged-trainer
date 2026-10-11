"""Read-only property-container graph discovery using tagged state identities."""
import struct
from war3_profile_discovery import DiscoveryEvidence, DiscoveryError

PROPERTY_PATHS=frozenset('layouts.property.'+key for key in (
    'owner_descriptor','descriptor_size','array','capacity','mirror','mirror_capacity',
    'stride','slots','count','tag','owner','handle','kind','state_identity_stride',
    'resource_snapshot_start','resource_snapshot_size'))

def _pointer(value):
    return 0x10000 <= value < 0x800000000000 and value % 8 == 0


def discover_player_property_identity(memory, registry, players, source, budget, *, owner_span=512):
    """Corroborate the vector grammar and derive movable record identity members.

    This proves metadata/backlinks only. Current resource or vital values and
    regeneration coefficients are not inferred from plausible numeric values.
    """
    from war3_player_resources import PROPERTY_TAG, REQUIRED_STATES
    relative={key:source.data['layouts']['property'][key] for key in
              ('array','capacity','mirror','mirror_capacity','stride','slots','count')}
    extent=max(relative[key]+(8 if key in ('array','capacity','mirror','mirror_capacity') else 4)
               for key in relative)
    size=(extent+7)//8*8
    if not 1<=size<=128 or len(players)<2:return {},{}
    owners=[]
    for player in players[:4]:
        handle=struct.unpack('<Q',budget.read(memory,player+registry.layout['object_handle'],8))[0]
        owner=registry.resolve_handle(memory,handle)
        owners.append(owner)
    candidates=[]
    for offset in range(0,max(0,owner_span-size)+1,8):
        budget.check('正在核对玩家属性记录结构')
        groups=[];anchors=[];valid=True
        for owner in owners:
            try:
                block=budget.read(memory,owner+offset,size)
                values={key:struct.unpack_from('<Q' if key in ('array','capacity','mirror','mirror_capacity') else '<I',
                                             block,member)[0] for key,member in relative.items()}
                array,capacity=values['array'],values['capacity']
                if (not _pointer(array) or not 0<capacity<=4096 or values['mirror']!=array or
                    values['mirror_capacity']!=capacity or values['stride']!=8 or
                    values['slots']*8!=capacity or not 6<=values['count']<=min(128,values['slots'])):
                    valid=False;break
                pointers=budget.read(memory,array,values['count']*8)
                records=[]
                for address in struct.unpack('<'+'Q'*values['count'],pointers):
                    if not _pointer(address):valid=False;break
                    raw=budget.read(memory,address,160)
                    tags=[member for member in range(0,128,8) if struct.unpack_from('<Q',raw,member)[0]==PROPERTY_TAG]
                    if tags:records.append((address,raw,tags))
                if not valid or len(records)<len(REQUIRED_STATES):valid=False;break
                if (budget.read(memory,owner+offset,size)!=block or
                    budget.read(memory,array,len(pointers))!=pointers):valid=False;break
                groups.append(records);anchors.append((owner+offset,block))
            except DiscoveryError:raise
            except (OSError,ValueError,RuntimeError):valid=False;break
        if not valid:continue
        common_tags=set.intersection(*(set(tags) for group in groups for _,_,tags in group))
        owner_members=set.intersection(*({member for member in range(0,128,8)
            if struct.unpack_from('<Q',raw,member)[0]==owner}
            for owner,group in zip(owners,groups) for _,raw,_ in group))
        if len(common_tags)!=1 or len(owner_members)!=1:continue
        for handle_member in range(0,128,8):
            for kind_member in range(0,156,4):
                if kind_member in (handle_member,handle_member+4):continue
                strides=set();states=[];identities_ok=True
                for player_id,group in enumerate(groups):
                    observed={}
                    for _,raw,_ in group:
                        packed=struct.unpack_from('<Q',raw,handle_member)[0]
                        low,high=packed&0xffffffff,packed>>32
                        kind=struct.unpack_from('<I',raw,kind_member)[0]
                        if not 1<=low<0x10000 or low!=high or not 0<=kind<=25 or kind in observed:
                            identities_ok=False;break
                        difference=low-kind-1
                        if player_id==0:
                            if difference:identities_ok=False;break
                        elif difference<=0 or difference%player_id:
                            identities_ok=False;break
                        else:strides.add(difference//player_id)
                        observed[kind]=packed
                    if not identities_ok or not set(REQUIRED_STATES)<=observed.keys():identities_ok=False;break
                    states.append(observed)
                if not identities_ok or len(strides)!=1:continue
                stride=next(iter(strides))
                if not 26<=stride<=128:continue
                proposed=dict(owner_descriptor=offset,descriptor_size=size,
                    **relative,tag=next(iter(common_tags)),owner=next(iter(owner_members)),
                    handle=handle_member,kind=kind_member,state_identity_stride=stride)
                stable=True
                for group in groups:
                    for address,raw,_ in group:
                        for key,width in (('tag',8),('owner',8),('handle',8),('kind',4)):
                            member=proposed[key]
                            if budget.read(memory,address+member,width)!=raw[member:member+width]:
                                stable=False;break
                        if not stable:break
                    if not stable:break
                if stable:candidates.append(proposed)
    unique={tuple(sorted(row.items())):row for row in candidates}
    if len(unique)!=1:
        return {},{'property_identity_graph':DiscoveryEvidence('property_identity_graph',
             'ambiguous' if unique else 'unresolved','tagged_player_property_containers')}
    values=next(iter(unique.values()))
    # Re-read the exact winning grammar through the existing property adapter
    # on the next public operation. This scan never authorizes value offsets.
    updates={'layouts.property.'+key:value for key,value in values.items()}
    evidence={path:DiscoveryEvidence(path,'confirmed','tagged_states_packed_ids_and_owner_backlinks',(value,))
              for path,value in updates.items()}
    return updates,evidence


def resource_snapshot_bounds(evidence):
    """Derive a byte window only after every consumed record member is proved."""
    widths={'tag':8,'handle':8,'owner':8,'kind':4,'value':4}
    proofs={key:evidence.get('layouts.property.'+key) for key in widths}
    if any(proof is None or proof.state!='confirmed' or len(proof.candidates)!=1 for proof in proofs.values()):
        return {},{}
    values={key:proof.candidates[0] for key,proof in proofs.items()}
    start=min(values.values());end=max(values[key]+width for key,width in widths.items())
    if not 0<=start<end<=4096:return {},{}
    updates={'layouts.property.resource_snapshot_start':start,'layouts.property.resource_snapshot_size':end-start}
    evidence={path:DiscoveryEvidence(path,'confirmed','proved_record_member_span',(value,)) for path,value in updates.items()}
    return updates,evidence
