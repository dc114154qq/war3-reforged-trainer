"""Bounded, typed Native witnesses for mode indices and null-read recovery.

Only reviewed local instruction envelopes are accepted. Unreadable envelopes
stay unresolved; another Native's adjacent body is never used as a witness.
"""
from __future__ import annotations
import re
from war3_profile_discovery import DiscoveryEvidence,unique_evidence


def _native_body(image,entries,name,signature,budget,*,primary=False):
    entry=entries.get(name)
    if entry is None or entry.signature!=signature:return None
    at=entry.handler-image.base
    if not image.executable(at):return None
    if primary:
        size=image.function_size(at)
        if size is None:return None
    else:
        # Protected Natives can have several unwind regions. Bound the search
        # at the next registered handler, rather than the first pdata fragment.
        following=[e.handler-image.base for e in entries.values() if e.handler>entry.handler]
        if not following:return None
        size=min(following)-at
    if not 24<=size<=0x4000:return None
    budget.check('正在核对原生恢复与玩家模式的独立依据')
    try:return at,image.read(at,size)
    except OSError:return None


def native_mode_indices(image,entries,evidence,checks,budget):
    """GetLocalPlayer branches on the independently located mode predicate."""
    from war3_discovery_locators import decoder
    from capstone.x86 import X86_OP_IMM,X86_OP_MEM
    body=_native_body(image,entries,'GetLocalPlayer','()Hplayer;',budget,primary=True)
    required=('checks.context.2','checks.game_state.2')
    if body is None or any(evidence.get(k) is None or evidence[k].state!='confirmed' for k in required):
        return {},{}
    try:
        mode=checks['context'][2]['rva'];accessor=checks['game_state'][2]['rva']
        mode_code=bytes.fromhex(checks['context'][2]['bytes'])
    except (KeyError,IndexError,TypeError):return {},{}
    if not 8<=len(mode_code)<=128:return {},{}
    try:
        if image.read(mode,len(mode_code))!=mode_code:return {},{}
    except OSError:return {},{}
    mode_ins=list(decoder().disasm(mode_code,mode))
    if sum(i.size for i in mode_ins)!=len(mode_code):return {},{}
    predicates=[(left,right) for left,right in zip(mode_ins,mode_ins[1:])
        if left.mnemonic=='cmp' and len(left.operands)==2 and left.operands[0].type==X86_OP_MEM and
        left.operands[0].size==4 and left.operands[1].type==X86_OP_IMM and left.operands[1].imm==1 and
        right.mnemonic=='sete' and right.op_str=='al']
    if len(predicates)!=1:return {},{}
    at,raw=body;observed=[];anchors=[]
    pattern=rb'\xe8....\x48\x8b\xcb\x84\xc0\x74.\x0f\xb7\x93....\xeb.\x0f\xb7\x93....\xe8....'
    for match in re.finditer(pattern,raw,re.S):
        ins=list(decoder().disasm(match[0],at+match.start()))
        if len(ins)!=8 or sum(i.size for i in ins)!=len(match[0]):continue
        if [i.mnemonic for i in ins]!=['call','mov','test','je','movzx','jmp','movzx','call']:continue
        if ins[0].operands[0].type!=X86_OP_IMM or ins[0].operands[0].imm!=mode:continue
        if ins[-1].operands[0].type!=X86_OP_IMM or ins[-1].operands[0].imm!=accessor:continue
        if ins[3].operands[0].imm!=ins[6].address or ins[5].operands[0].imm!=ins[7].address:continue
        if any(i.operands[1].type!=X86_OP_MEM or i.operands[1].size!=2 or
               i.reg_name(i.operands[1].mem.base)!='rbx' or i.operands[1].mem.index or
               i.reg_name(i.operands[0].reg)!='edx' for i in (ins[4],ins[6])):continue
        alternate,normal=(i.operands[1].mem.disp for i in (ins[4],ins[6]))
        if alternate==normal or any(not 0<v<0x10000 or v%2 for v in (alternate,normal)):continue
        observed.append((normal,alternate));anchors.append((at+match.start(),match[0].hex()))
    proofs={};updates={}
    for index,key in enumerate(('normal_index','alternate_index')):
        path='players.'+key
        proof=unique_evidence(path,'typed_local_player_mode_branches',
                              [v[index] for v in observed],anchors)
        proofs[path]=proof
        if proof.state=='confirmed':updates[path]=proof.candidates[0]
    return updates,proofs


def _fog_sites(raw):
    """R14 is explicitly cleared before the faulting getter-side gate."""
    gate_pattern=bytes.fromhex('4533f6c0c8020406c0c80284c07504410fb606')
    getter_pattern=bytes.fromhex('84c0750533c00fb600')
    tail_pattern=bytes.fromhex('80f970751b410fb6064c8b7424604883c4705f5b5dc3')
    result={}
    for role,pattern,position in (('gate',gate_pattern,15),('getter',getter_pattern,6),('tail',tail_pattern,5)):
        matches=[];offset=0
        while (offset:=raw.find(pattern,offset))>=0:
            matches.append((offset+position,offset,pattern));offset+=len(pattern)
        result[role]=matches
    return result


def locate_native_recovery(image,entries,budget):
    """Data-only offsets for the currently reviewed R14 / R12 compiler shape."""
    updates={};proofs={}
    for name,signature,roles in (
        ('FogEnable','(B)V',(('gate','enable_gate'),('tail','enable_tail'))),
        ('FogMaskEnable','(B)V',(('gate','mask_gate'),('tail','mask_tail'))),
        ('IsFogEnabled','()B',(('getter','enabled_gate'),)),
        ('IsFogMaskEnabled','()B',(('getter','masked_gate'),))):
        body=_native_body(image,entries,name,signature,budget)
        for role,key in roles:
            path='fog_recovery.'+key;hits=[];anchors=[]
            if body:
                at,raw=body
                for offset,start,pattern in _fog_sites(raw)[role]:
                    if 0<offset<0x10000:
                        hits.append(offset);anchors.append((at+start,pattern.hex()))
            proof=unique_evidence(path,'typed_native_fog_'+role,hits,anchors)
            proofs[path]=proof
            if proof.state=='confirmed':updates[path]=proof.candidates[0]
    if all(p.state=='confirmed' for p in proofs.values()):
        proofs['fog_recovery']=DiscoveryEvidence('fog_recovery','confirmed','all_typed_fog_recovery_sites',
            anchors=tuple(a for p in proofs.values() for a in p.anchors))
    body=_native_body(image,entries,'SetUnitAbilityLevel','(Hunit;II)I',budget)
    path='bridge_layout.ability_level_tail';hits=[];anchors=[]
    if body:
        at,raw=body
        # Guarded null read, followed only by level-result calculation and
        # the reviewed epilogue. Native readback remains mandatory in C.
        pattern=rb'\x80\xf9\x70\x75\x05\x41\x0f\xb6\x04\x24\x8b\x83....\xff\xc0\xeb\x02\x33\xc0\x48\x8b\x9c\x24....\x48\x83\xc4\x60\x41\x5e\x41\x5c\x5f\x5e\x5d\xc3'
        for match in re.finditer(pattern,raw,re.S):
            hits.append(match.start()+5);anchors.append((at+match.start(),match[0].hex()))
    proof=unique_evidence(path,'typed_native_ability_level_tail',hits,anchors);proofs[path]=proof
    if proof.state=='confirmed':updates[path]=proof.candidates[0]
    return updates,proofs


def reconcile_native_recovery(evidence):
    paths=('enable_gate','mask_gate','enabled_gate','masked_gate','enable_tail','mask_tail')
    leaves=[evidence.get('fog_recovery.'+key) for key in paths]
    if all(p is not None and p.state=='confirmed' for p in leaves):
        evidence['fog_recovery']=DiscoveryEvidence('fog_recovery','confirmed','all_typed_fog_recovery_sites',
            anchors=tuple(dict.fromkeys(a for p in leaves for a in p.anchors)))
    elif any(p is not None and p.state=='ambiguous' for p in leaves):
        evidence['fog_recovery']=DiscoveryEvidence('fog_recovery','unresolved','fog_recovery_dependency_conflict')
    elif evidence.get('fog_recovery') is None or evidence['fog_recovery'].method!='complete_code_and_static_identity':
        evidence['fog_recovery']=DiscoveryEvidence('fog_recovery','unresolved','fog_recovery_sites_incomplete')
