"""Bounded read-only evidence captured after a canonical selection rejection."""
from war3_basic_fields import REAL_TAG, POSITION_TAG


def inspect_candidate_failure(memory, owner, unit, handle, profile):
    layout=profile.section('registry')
    identity_fields=((owner+layout['owner_handle'],handle),
                     (owner+layout['owner_data'],unit),
                     (unit+layout['object_handle'],handle))

    def qword(address):
        try:
            return {'address':address,'ok':True,'value':memory.read_u64(address)}
        except OSError as exc:
            return {'address':address,'ok':False,'winerror':getattr(exc,'winerror',None),
                    'exception':repr(exc)}

    def pointer(value):
        return 0x10000<=value<0x800000000000 and value%8==0

    identity=[dict(qword(address),expected=expected) for address,expected in identity_fields]
    lists=[];seen=set()
    for list_offset,size_offset in ((0xa0,0xa8),(0xb0,0xb8)):
        address,capacity=qword(owner+list_offset),qword(owner+size_offset)
        row={'pointer':address,'capacity':capacity,'entries':[]}
        lists.append(row)
        if not address['ok'] or not capacity['ok']:
            row['status']='descriptor_unreadable';continue
        array,size=address['value'],capacity['value']
        if not pointer(array):
            row['status']='null_or_invalid_pointer';continue
        walk=size if 0<size<=0x400 else 0x100
        row.update(status='observed',capacity_valid=0<size<=0x400,
                   inspected_entries=min(walk//8,16),truncated=walk//8>16)
        for index in range(min(walk//8,16)):
            entry={'index':index,'pointer':qword(array+index*8)}
            row['entries'].append(entry)
            if not entry['pointer']['ok']:
                entry['status']='entry_unreadable';continue
            prop=entry['pointer']['value']
            if not pointer(prop):
                entry['status']='null_or_invalid_pointer';continue
            if prop in seen:
                entry['status']='duplicate';continue
            seen.add(prop)
            entry['tag']=qword(prop+0x18);entry['owner']=qword(prop+0x50)
            if not entry['tag']['ok'] or not entry['owner']['ok']:
                entry['status']='property_unreadable';continue
            if entry['owner']['value']!=owner:
                entry['status']='foreign_owner';continue
            if entry['tag']['value']==REAL_TAG:
                entry['kind']=qword(prop+0x78)
                if not entry['kind']['ok']:
                    entry['status']='kind_unreadable';continue
                entry['status']='real_property'
                entry['kind_value']=(entry['kind']['value']>>32)&0xffffffff
            elif entry['tag']['value']==POSITION_TAG:
                entry['status']='position_property'
            else:
                entry['status']='unrecognized_tag'
        row['pointer_after']=qword(owner+list_offset)
        row['capacity_after']=qword(owner+size_offset)
    identity_after=[qword(address) for address,_ in identity_fields]
    return {'observation_timing':'after_candidate_rejection','read_only':True,
            'profile':profile.id,'fingerprint':profile.fingerprint,
            'identity':identity,'identity_after':identity_after,'property_lists':lists,
            'identity_stable':all(before.get('ok') and after.get('ok') and
                before.get('value')==after.get('value') for before,after in zip(identity,identity_after)),
            'warning':'Follow-up observations cannot prove the original failure state was identical.'}
