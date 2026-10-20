"""Class-bound, read-only stat mode discovery from complete reviewed methods."""
from __future__ import annotations
import struct
from war3_profile_discovery import DiscoveryEvidence

CLASSES={
    'cooldown_vtable':'CAbilityCooldownReduction',
    'amplification_vtable':'CAbilitySpellAmp',
    'spell_vamp_vtable':'CAbilitySpellVamp',
    'resolve_vtable':'CAbilityResolve',
}


def confirm_stat_module(evidence,implementation):
    """Enable the bundled service only after all of its actual inputs agree."""
    from war3_discovery_dependencies import NATIVE,missing_dependencies
    from war3_version_modules import known_implementation
    required=NATIVE|{'stat_runtime','stat_runtime.flat_flag','layouts.ability','layouts.component_list'}|{
        'stat_mode.'+key for key in CLASSES}
    path='modules.stat_details'
    if known_implementation('stat_details',implementation) and not missing_dependencies(evidence,required):
        evidence[path]=DiscoveryEvidence(path,'confirmed','native_stat_schema_and_owner_bound_mode_proofs',
            anchors=tuple(dict.fromkeys(a for key in CLASSES for a in evidence['stat_mode.'+key].anchors)))
    else:
        evidence[path]=DiscoveryEvidence(path,'unresolved','stat_service_dependencies_incomplete')


def reconcile_stat_mode(evidence):
    """A prior parent-group proof must not conceal a new child conflict."""
    paths=['stat_runtime.'+key for key in CLASSES]+['stat_mode.'+key for key in CLASSES]+['stat_runtime.flat_flag']
    if any(evidence.get(path) is not None and evidence[path].state=='ambiguous' for path in paths):
        evidence['stat_runtime']=DiscoveryEvidence('stat_runtime','unresolved','stat_mode_dependency_conflict')
        return
    group=evidence.get('stat_runtime')
    complete=all(evidence.get(path) is not None and evidence[path].state=='confirmed' for path in paths)
    flag=evidence.get('stat_runtime.flat_flag')
    if complete and all(evidence['stat_mode.'+key].candidates==flag.candidates for key in CLASSES):
        evidence['stat_runtime']=DiscoveryEvidence('stat_runtime','confirmed','all_stat_tables_and_mode_consumers')
    elif group is not None and group.method=='all_stat_tables_and_mode_consumers':
        evidence['stat_runtime']=DiscoveryEvidence('stat_runtime','unresolved','stat_mode_classes_incomplete')


def _selector(instructions,kind):
    """Return the initialized byte or the serialized byte with fixed registers."""
    from capstone.x86 import X86_OP_MEM,X86_OP_REG,X86_OP_IMM
    if kind=='initializer':
        # A reviewed producer variant explicitly clears its fourth argument.
        # Preserve every semantic instruction and map the selected operand
        # back to the original body; branch targets still use real addresses.
        if len(instructions) in (37,56):
            extra=[i for i,ins in enumerate(instructions)
                   if (ins.mnemonic,ins.op_str)==('xor','r9d, r9d')]
            expected=[15] if len(instructions)==37 else [15,34]
            if extra!=expected or any(
                    (instructions[i+1].mnemonic,instructions[i+1].op_str)!=('lea','r8, [rsp + 0x38]')
                    for i in extra):return None
            kept=[i for i in range(len(instructions)) if i not in extra]
            selected=_selector([instructions[i] for i in kept],kind)
            return (kept[selected[0]],selected[1]) if selected is not None else None
        if len(instructions) not in (36,54):return None
        index=27 if len(instructions)==36 else 26
        ins=instructions[index]
        if (ins.mnemonic!='mov' or len(ins.operands)!=2 or
                ins.operands[0].type!=X86_OP_MEM or ins.operands[0].size!=1 or
                ins.operands[0].mem.index or ins.reg_name(ins.operands[0].mem.base)!=('rdi' if index==27 else 'rbx') or
                ins.operands[1].type!=X86_OP_REG or ins.reg_name(ins.operands[1].reg)!='al'):
            return None
        # The reviewed real DataB read produces XMM0; unordered/nonzero goes
        # to AL=1, zero to AL=0, with both paths joining this exact byte store.
        expected=[('call',None),('movss','xmm0, dword ptr [rsp + 0x30]'),('ucomiss',None),
                  ('jp',None),('jne',None),('xor','al, al'),('jmp',None),('mov','al, 1')]
        for at,(mnemonic,operands) in zip(range(18,26),expected):
            candidate=instructions[at]
            if candidate.mnemonic!=mnemonic or operands is not None and candidate.op_str!=operands:return None
        if (instructions[20].operands[0].type!=X86_OP_REG or instructions[20].reg_name(instructions[20].operands[0].reg)!='xmm0' or
                instructions[20].operands[1].type!=X86_OP_MEM or instructions[20].operands[1].size!=4 or
                instructions[20].reg_name(instructions[20].operands[1].mem.base)!='rip' or
                any(instructions[at].operands[0].type!=X86_OP_IMM or
                    instructions[at].operands[0].imm!=instructions[25].address for at in (21,22)) or
                instructions[24].operands[0].type!=X86_OP_IMM or
                instructions[24].operands[0].imm!=instructions[26].address):return None
        return index,ins.operands[0].mem.disp
    if kind=='serializer':
        if len(instructions) not in (16,19):return None
        index=10;ins=instructions[index]
        if (ins.mnemonic!='movzx' or len(ins.operands)!=2 or
                ins.operands[0].type!=X86_OP_REG or ins.reg_name(ins.operands[0].reg)!='edx' or
                ins.operands[1].type!=X86_OP_MEM or ins.operands[1].size!=1 or
                ins.operands[1].mem.index or ins.reg_name(ins.operands[1].mem.base)!='rbx'):
            return None
        if instructions[index+1].mnemonic!='mov' or instructions[index+1].op_str!='rcx, rdi':return None
        return index,ins.operands[1].mem.disp
    raise ValueError('Unreviewed stat mode consumer')


def _method(image,table,recipe,budget):
    from capstone import CS_GRP_JUMP
    from capstone.x86 import X86_OP_IMM
    from war3_discovery_locators import decoder,signature
    if (set(recipe)!={'kind','slot','code','source'} or not recipe['source'] or
            recipe['kind'] not in ('initializer','serializer') or
            recipe['slot']!=(36 if recipe['kind']=='initializer' else 15)):
        raise ValueError('Unreviewed stat class method binding')
    raw=bytes.fromhex(recipe['code'])
    if not 24<=len(raw)<=1024:raise ValueError('Stat consumer code exceeds extent bound')
    source=list(decoder().disasm(raw,0))
    if sum(ins.size for ins in source)!=len(raw) or not source or source[-1].mnemonic not in ('ret','jmp'):
        raise ValueError('Stat source consumer is incomplete')
    selected=_selector(source,recipe['kind'])
    if selected is None:raise ValueError('Stat selector does not describe its reviewed source')
    boundaries={ins.address for ins in source}
    if any(ins.group(CS_GRP_JUMP) and (ins.operands[0].type!=X86_OP_IMM or
        0<=ins.operands[0].imm<len(raw) and ins.operands[0].imm not in boundaries) for ins in source):
        raise ValueError('Stat source branch enters an operand')
    binary,mask=signature(raw)
    mask=bytearray(mask);member_ins=source[selected[0]]
    mask[member_ins.address+member_ins.disp_offset:member_ins.address+member_ins.disp_offset+member_ins.disp_size]=bytes(member_ins.disp_size)
    # Spell amplification serializes another initialized byte immediately
    # after DataB; it must remain adjacent when this class layout relocates.
    paired_indices=((45,) if len(source)==54 else (47,) if len(source)==56 else ()) if recipe['kind']=='initializer' else (13,) if len(source)==19 else ()
    for index in paired_indices:
        ins=source[index]
        op=ins.operands[0 if recipe['kind']=='initializer' else 1]
        if op.mem.disp!=selected[1]+1:raise ValueError('Amplification paired flag layout differs')
        mask[ins.address+ins.disp_offset:ins.address+ins.disp_offset+ins.disp_size]=bytes(ins.disp_size)
    budget.check('正在核对属性模式的独立类方法')
    pointer_rva=table+recipe['slot']*8
    try:
        at=struct.unpack('<Q',image.read(pointer_rva,8))[0]-image.base
        if not image.executable(at) or image.function_size(at)!=len(raw):return None
        actual=image.read(at,len(raw))
    except OSError:return None
    if any(flag and left!=right for left,right,flag in zip(binary,actual,mask)):return None
    instructions=list(decoder().disasm(actual,at))
    if sum(ins.size for ins in instructions)!=len(raw) or len(instructions)!=len(source):return None
    for old,new in zip(source,instructions):
        if new.mnemonic=='call' and new.operands[0].type==X86_OP_IMM and not image.executable(new.operands[0].imm):
            return None
        if old.group(CS_GRP_JUMP):
            if 0<=old.operands[0].imm<len(raw):
                if new.operands[0].imm-at!=old.operands[0].imm:return None
            elif at<=new.operands[0].imm<at+len(raw) or not image.executable(new.operands[0].imm):return None
    observed=_selector(instructions,recipe['kind'])
    if observed is None or not 0<observed[1]<0x1000:return None
    for index in paired_indices:
        op=instructions[index].operands[0 if recipe['kind']=='initializer' else 1]
        if op.mem.disp!=observed[1]+1:return None
    return observed[1],(at,actual.hex()),('method',table,recipe['slot'],at)


def locate_stat_mode(image,recipes,evidence,budget):
    """Four unique RTTI identities and two independent consumers per class."""
    if not isinstance(recipes,(list,tuple)) or len(recipes)>4:
        raise ValueError('Stat class rule count exceeds bound')
    proofs={};values=[];anchors=[];seen=set()
    for recipe in recipes:
        if set(recipe)!={'class_key','type_name','methods'}:
            raise ValueError('Invalid stat class rule')
        key=recipe['class_key']
        if key not in CLASSES or key in seen or recipe['type_name']!=CLASSES[key]:
            raise ValueError('Unreviewed or repeated stat class')
        seen.add(key);methods=recipe['methods']
        if not isinstance(methods,(list,tuple)) or len(methods)!=2 or {row.get('kind') for row in methods}!={'initializer','serializer'}:
            raise ValueError('Stat mode requires both reviewed methods')
        path='stat_mode.'+key;table=evidence.get('stat_runtime.'+key)
        if (table is None or table.state!='confirmed' or len(table.candidates)!=1 or
                table.method!='msvc_rtti:'+CLASSES[key]):
            proofs[path]=DiscoveryEvidence(path,'unresolved','stat_class_identity_missing');continue
        observed=[_method(image,table.candidates[0],row,budget) for row in methods]
        hits=[row for row in observed if row is not None]
        candidates=tuple(sorted({row[0] for row in hits}))
        current=tuple(anchor for row in hits for anchor in row[1:])
        if len(candidates)>1:state='ambiguous';method='stat_mode_consumer_disagreement'
        elif len(hits)==2 and len({row[1][0] for row in hits})==2:state='confirmed';method='class_bound_stat_mode_consumers'
        else:state='unresolved';method='stat_mode_independent_consumer_missing'
        proofs[path]=DiscoveryEvidence(path,state,method,candidates,current)
        if state=='confirmed':values.extend(candidates);anchors.extend(current)
    required={'stat_mode.'+key for key in CLASSES}
    updates={}
    if required<=proofs.keys() and all(proofs[path].state=='confirmed' for path in required) and len(set(values))==1:
        value=values[0];updates['stat_runtime.flat_flag']=value
        proofs['stat_runtime.flat_flag']=DiscoveryEvidence('stat_runtime.flat_flag','confirmed',
            'all_class_bound_stat_mode_consumers',(value,),tuple(dict.fromkeys(anchors)))
        if all(evidence.get('stat_runtime.'+key) is not None and evidence['stat_runtime.'+key].state=='confirmed' for key in CLASSES):
            proofs['stat_runtime']=DiscoveryEvidence('stat_runtime','confirmed','all_stat_tables_and_mode_consumers')
    else:
        proofs['stat_runtime.flat_flag']=DiscoveryEvidence('stat_runtime.flat_flag',
            'ambiguous' if len(set(values))>1 else 'unresolved','stat_mode_classes_incomplete',tuple(sorted(set(values))),
            tuple(dict.fromkeys(anchors)))
    return updates,proofs
