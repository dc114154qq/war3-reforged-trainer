"""Read-only player-index and canonical selection-list discovery."""
from dataclasses import replace
import struct
from types import MappingProxyType
from war3_profile_discovery import DiscoveryEvidence,DiscoveryError,unique_evidence


def native_selection_manager(image, entries, budget):
    grouped=_native_group_selection_manager(image,entries,budget)
    membership=native_selection_membership(image,entries,budget)
    if grouped.state=='ambiguous':return grouped
    if grouped.state=='confirmed':
        if membership.state=='confirmed' and membership.candidates!=grouped.candidates:
            return DiscoveryEvidence('selection.native_manager','ambiguous','selection_consumers_disagree',
                                     tuple(sorted(set(grouped.candidates+membership.candidates))),grouped.anchors+membership.anchors)
        return grouped
    return membership


def native_selection_membership(image,entries,budget):
    """IsUnitSelected independently identifies the player selection manager."""
    from war3_discovery_locators import decoder
    from capstone.x86 import X86_OP_MEM,X86_OP_REG,X86_OP_IMM
    dependency='selection.native_manager';entry=entries.get('IsUnitSelected')
    if entry is None or entry.signature!='(Hunit;Hplayer;)B':
        return DiscoveryEvidence(dependency,'unresolved','selection_membership_native_missing')
    at=entry.handler-image.base;size=image.function_size(at)
    if size is None or not 64<=size<=256:return DiscoveryEvidence(dependency,'unresolved','selection_membership_boundary_missing')
    budget.check('正在核对原生选中关系')
    try:raw=image.read(at,size)
    except OSError:return DiscoveryEvidence(dependency,'unresolved','selection_membership_unreadable')
    insns=list(decoder().disasm(raw,at));values=[];anchors=[]
    if sum(i.size for i in insns)!=len(raw):
        return DiscoveryEvidence(dependency,'unresolved','selection_membership_incomplete_code')
    # EDX is the player handle, retained across resolution of the unit. The
    # second resolver returns the player; its manager then receives that same
    # resolved unit as the membership predicate's second argument.
    for index,ins in enumerate(insns):
        if ins.mnemonic!='mov' or ins.op_str!='ecx, ebx':continue
        prefix=insns[:index]
        saves=[j for j,i in enumerate(prefix) if i.mnemonic=='mov' and i.op_str=='ebx, edx']
        if len(saves)!=1:continue
        if any(i.mnemonic not in ('cmp','test') and i.operands and i.operands[0].type==X86_OP_REG and
               i.reg_name(i.operands[0].reg) in ('rbx','ebx','bx','bl','bh') for i in prefix[saves[0]+1:]):continue
        calls=[i for i in prefix if i.mnemonic=='call']
        if len(calls)!=1 or calls[0].operands[0].type!=X86_OP_IMM:continue
        unit_save=[j for j,i in enumerate(prefix) if i.mnemonic=='mov' and i.op_str=='rdi, rax' and i.address>calls[0].address]
        if len(unit_save)!=1:continue
        if any(i.mnemonic not in ('cmp','test') and i.operands and i.operands[0].type==X86_OP_REG and
               i.reg_name(i.operands[0].reg) in ('rdi','edi','di','dil') for i in prefix[unit_save[0]+1:]):continue
        tail=insns[index+1:index+6]
        if len(tail)!=5 or [i.mnemonic for i in tail]!=['call','test','je','mov','test']:continue
        if tail[0].operands[0].type!=X86_OP_IMM or not image.executable(tail[0].operands[0].imm):continue
        load=tail[3]
        if (tail[1].op_str!='rax, rax' or load.operands[0].type!=X86_OP_REG or
            load.reg_name(load.operands[0].reg)!='rbx' or load.operands[1].type!=X86_OP_MEM):continue
        member=load.operands[1].mem
        if load.reg_name(member.base)!='rax' or member.index or load.operands[1].size!=8 or not 0<member.disp<0x2000 or member.disp%8:continue
        predicate=[]
        for j in range(index+6,len(insns)-3):
            if [(i.mnemonic,i.op_str) for i in insns[j:j+2]]!=[('mov','rdx, rdi'),('mov','rcx, rbx')]:continue
            call=insns[j+2];check=insns[j+3]
            if call.mnemonic=='call' and call.operands[0].type==X86_OP_IMM and check.mnemonic=='test' and check.op_str=='al, al':
                predicate.append(call.address)
        if not predicate:continue
        values.append(member.disp);anchors.append((at,raw.hex()))
    return unique_evidence(dependency,'typed_unit_selected_player_manager',values,anchors)


def _native_group_selection_manager(image, entries, budget):
    """Trace the selected-group native's player pointer to its ring manager."""
    from war3_discovery_locators import decoder
    from capstone.x86 import X86_OP_MEM, X86_OP_REG

    dependency = 'selection.native_manager'
    entry = entries.get('GroupEnumUnitsSelected')
    if entry is None or entry.signature != '(Hgroup;Hplayer;Hboolexpr;)V':
        return DiscoveryEvidence(dependency, 'unresolved', 'selection_native_signature_missing')
    rva = entry.handler - image.base
    extent = image.function_size(rva)
    if extent is None or extent < 96 or not image.executable(rva):
        return DiscoveryEvidence(dependency, 'unresolved', 'selection_native_boundary_missing')
    budget.check('正在核对原生选中单位链路')
    try:
        instructions = list(decoder().disasm(image.read(rva, min(extent, 144)), rva))
    except OSError:
        return DiscoveryEvidence(dependency, 'unresolved', 'selection_native_unreadable')
    values, anchors = [], []
    for index, ins in enumerate(instructions):
        if ins.mnemonic != 'mov' or ins.op_str != 'ebx, edx':
            continue
        copies = [j for j in range(index+1, min(index+12, len(instructions)))
                  if instructions[j].mnemonic == 'mov' and instructions[j].op_str == 'ecx, ebx']
        if len(copies) != 1:
            continue
        next_calls = [j for j in range(copies[0]+1, min(copies[0]+4, len(instructions)))
                      if instructions[j].mnemonic == 'call']
        if len(next_calls) != 1:
            continue
        call = next_calls[0]
        if call+1 >= len(instructions) or instructions[call+1].op_str != 'rbx, rax':
            continue
        for j in range(call+2, min(call+32, len(instructions))):
            current = instructions[j]
            if (current.operands and current.operands[0].type == X86_OP_REG and
                    current.reg_name(current.operands[0].reg) in ('rbx', 'ebx', 'bx', 'bl')):
                break
            if (current.mnemonic != 'mov' or len(current.operands) != 2 or
                    current.operands[0].type != X86_OP_REG or
                    current.reg_name(current.operands[0].reg) != 'rcx' or
                    current.operands[1].type != X86_OP_MEM):
                continue
            member = current.operands[1].mem
            if (current.reg_name(member.base) != 'rbx' or member.index or
                    current.operands[1].size != 8 or not 0 < member.disp < 0x2000 or
                    member.disp % 8 or j+1 >= len(instructions) or
                    instructions[j+1].mnemonic != 'test' or
                    instructions[j+1].op_str != 'rcx, rcx' or
                    not any(i.mnemonic == 'call' for i in instructions[j+2:j+12])):
                continue
            values.append(member.disp)
            anchors.append((rva, current.address))
    return unique_evidence(dependency, 'selected_group_native_player_dataflow', values, anchors)


def locate_player_index(image,player_accessor,budget):
    from war3_discovery_locators import signature,matches,decoder
    from capstone.x86 import X86_OP_MEM,X86_OP_IMM
    # Load the normal player index, reject the sentinel, call the already located
    # player-array accessor. Both the member displacement and branch/call relocate.
    template=bytes.fromhex('0fb7960000000033f683fa1c740b498bcee800000000')
    code,mask=signature(template,variable_fields=True)
    values=[];witnesses=[]
    for site in matches(image,code,mask,budget):
        insns=list(decoder().disasm(image.read(site,len(code)),site))
        calls=[i.operands[0].imm for i in insns if i.mnemonic=='call' and i.operands[0].type==X86_OP_IMM]
        if calls!=[player_accessor]:continue
        first=insns[0]
        if first.mnemonic!='movzx' or first.operands[1].type!=X86_OP_MEM:continue
        disp=first.operands[1].mem.disp
        if 0<disp<0x10000 and disp%2==0:values.append(disp);witnesses.append(site)
    return unique_evidence('players.normal_index','normal_index_to_player_accessor',values,witnesses)


def locate_selection_graph(candidate,memory,registry,budget,*,radius=128):
    """Require a single shared manager member plus canonical rings and unit identity.

    Read-only and bounded. Empty rings alone never identify selection; at least
    one nonempty ring must contain fully resolved unit objects. No local player
    is guessed from which player happens to have units selected.
    """
    from war3_classic_selection import read_player_selection
    from war3_game_profile import GameProfile,profile_scope,_freeze
    players=registry.players(memory);old=candidate.section('selection')['manager']
    offsets=range(max(0,old-radius)//8*8,min(0x2000,old+radius+8),8)
    accepted=[]
    for offset in offsets:
        budget.check('正在定位选中单位列表')
        data=candidate.to_dict();data['selection']['manager']=offset
        for module in data['modules'].values():module['fingerprint']=list(candidate.fingerprint)
        view=GameProfile(_freeze(data),candidate.digest)
        witnessed=False;valid=True
        with profile_scope(view):
            for player in players:
                try:
                    snapshot=read_player_selection(memory,player)
                    for unit in snapshot.units:registry.resolve_unit(memory,unit)
                    # Identity resolution is part of the probe snapshot. Discard
                    # a list changed while its entries were being resolved.
                    if read_player_selection(memory,player)!=snapshot:
                        raise RuntimeError('Canonical list changed during identity validation')
                    witnessed |= bool(snapshot.units)
                except DiscoveryError:raise
                except (OSError,ValueError,RuntimeError):valid=False;break
        if valid and witnessed:accepted.append(offset)
    proof=unique_evidence('selection.manager','canonical_rings_all_players_and_unit_identity',accepted)
    # A unique ring can still be another per-player unit group. Keep it as
    # candidate evidence until native selection access corroborates its role.
    return replace(proof,state='candidate' if proof.state=='confirmed' else proof.state,
                   detail='Requires native selection-access corroboration; not a usable layout proof')


def validate_local_player(candidate,memory,registry,mode,budget):
    """Validate the code-derived index for the active mode; no other mode is implied."""
    from war3_game_profile import profile_scope
    field='alternate_index' if mode==1 else 'normal_index'
    proof=candidate.evidence.get('players.'+field)
    if proof is None or proof.state!='confirmed':return None
    budget.check('正在核对本地玩家身份')
    with profile_scope(candidate):
        pointer=registry.local_player_for_mode(memory,mode)
    return pointer
