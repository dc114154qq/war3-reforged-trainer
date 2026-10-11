"""Data-only semantic witnesses for advanced object members.

Recipes name reviewed consumers and individual operands. They do not infer
semantics by comparing numerical offsets with every field in a source pack.
"""
from __future__ import annotations
from war3_profile_discovery import DiscoveryEvidence


ALLOWED_FIELDS = frozenset({
    'layouts.ability.rawcode', 'layouts.ability.unit_owner',
    'layouts.ability.data_cache', 'layouts.ability.mirror_rawcode',
    'layouts.ability.flags', 'equipment_runtime.ability_owner',
    'equipment_runtime.item_flags', 'equipment_runtime.item_equipment_type',
    'layouts.item.equipment_mask', 'layouts.unit.rawcode',
    'registry.object_rawcode', 'equipment_runtime.equipment_count',
    'equipment_runtime.equipment_records', 'layouts.inventory.capacity',
    'layouts.inventory.slot_array', 'layouts.inventory.slot_stride',
    'layouts.equipment_record.stride',
    'layouts.property.value', 'layouts.property.maximum', 'layouts.property.regen',
    'layouts.property.position_x', 'layouts.property.position_y',
})


class _AmbiguousConsumer(ValueError):
    def __init__(self,sites):
        self.sites=tuple(sites)


def _bound_error_tails(image, instructions, rows, budget):
    """Verify the small TLS error thunk reached after the reviewed null exit."""
    from war3_discovery_locators import decoder,signature
    from capstone.x86 import X86_OP_IMM
    if not isinstance(rows,(list,tuple)) or len(rows)>2:
        raise ValueError('Bound error tail count exceeds limit')
    allowed={};anchors=[]
    shape=[('mov','edx, dword ptr [rip + '),('mov','rax, qword ptr gs:[0x58]'),
           ('mov','r8d, 0x10'),('mov','rax, qword ptr [rax + rdx*8]'),
           ('mov','dword ptr [r8 + rax], ecx'),('jmp','qword ptr [rip + ')]
    for row in rows:
        if set(row)!={'instruction','code'} or type(row['instruction']) is not int:
            raise ValueError('Invalid reviewed bound error tail')
        index=row['instruction']
        if not 0<=index<len(instructions) or index in allowed:
            raise ValueError('Invalid bound error tail selector')
        branch=instructions[index]
        if branch.mnemonic!='jmp' or not branch.operands or branch.operands[0].type!=X86_OP_IMM:
            raise ValueError('Error tail selector is not a direct jump')
        raw=bytes.fromhex(row['code']);source=list(decoder().disasm(raw,0))
        if (len(source)!=6 or sum(ins.size for ins in source)!=len(raw) or
                any(ins.mnemonic!=mnemonic or (not ins.op_str.startswith(operands) if operands.endswith(' + ')
                                              else ins.op_str!=operands)
                    for ins,(mnemonic,operands) in zip(source,shape))):
            raise ValueError('Unreviewed bound error thunk')
        at=branch.operands[0].imm
        budget.check('正在核对坐标接口的空对象错误出口')
        if not image.executable(at) or image.function_size(at) not in (None,len(raw)):
            return None
        try:observed=image.read(at,len(raw))
        except OSError:return None
        binary,mask=signature(raw)
        if any(flag and left!=right for left,right,flag in zip(binary,observed,mask)):
            return None
        allowed[index]=at;anchors.append((at,observed.hex()))
    return allowed,tuple(anchors)


def _unit_state_root_mask(raw,binary,mask):
    """Reviewed four-state dispatcher; only its paired mana subobject may move."""
    from war3_discovery_locators import decoder
    from capstone.x86 import X86_OP_REG,X86_OP_IMM,X86_OP_MEM
    ins=list(decoder().disasm(raw,0))
    prefix=[(i.mnemonic,i.op_str) for i in ins[:4]]
    if prefix != [('push','rbx'),('sub','rsp, 0x20'),('mov','rbx, rdx'),('test','r8d, r8d')] or len(ins)<5 or ins[4].mnemonic!='je':
        raise ValueError('Unreviewed unit-state dispatcher root')
    additions=[i for i in ins if i.mnemonic=='add' and len(i.operands)==2 and
        i.operands[0].type==X86_OP_REG and i.reg_name(i.operands[0].reg)=='rcx' and i.operands[1].type==X86_OP_IMM]
    direct=[i for i in ins if i.mnemonic=='call' and i.operands[0].type==X86_OP_IMM]
    virtual=[i for i in ins if i.mnemonic=='call' and i.operands[0].type==X86_OP_MEM]
    if (len(additions)!=2 or additions[0].operands[1].imm!=additions[1].operands[1].imm or
        len(direct)!=2 or len(virtual)!=2 or
        any(i.reg_name(i.operands[0].mem.base)!='rax' or i.operands[0].mem.index for i in virtual)):
        raise ValueError('Unit-state root does not describe paired scalar getters')
    changed=bytearray(mask)
    for i in additions:changed[i.address+i.imm_offset:i.address+i.imm_offset+i.imm_size]=bytes(i.imm_size)
    return binary,bytes(changed)


def _bound_consumer(image,binding,entries,budget,*,site_hints=None,resolver=None):
    """Match reviewed native-call bodies before following a specific callee.

    A call ordinal by itself is not semantic proof. Every parent body must
    match its reviewed shape and the registered native signature exactly.
    """
    from war3_discovery_locators import decoder,signature
    from capstone.x86 import X86_OP_IMM
    consumer=set(binding)=={'consumer','chain'}
    if ((not consumer and (set(binding)-{'native','signature','chain','unit_call'} or
                           not {'native','signature','chain'}<=set(binding))) or
        consumer and binding['consumer']!='unit_state_dispatcher' or
        not isinstance(binding['chain'],(list,tuple)) or not 1<=len(binding['chain'])<=4):
        raise ValueError('Invalid semantic native binding')
    if 'unit_call' in binding and (type(binding['unit_call']) is not int or binding['unit_call']!=0):
        raise ValueError('Unreviewed typed unit argument call')
    if 'unit_call' in binding and (resolver is None or resolver.state!='confirmed' or len(resolver.candidates)!=1):
        return None,()
    chain=binding['chain']
    for row in chain:
        if (set(row)-{'code','call_index','fixed_displacements','error_tails'} or not {'code','call_index'}<=set(row) or
                type(row.get('fixed_displacements',False)) is not bool or
                type(row['call_index']) is not int or not 0<=row['call_index']<=16):
            raise ValueError('Invalid reviewed call selector')
        raw=bytes.fromhex(row['code'])
        if not 24<=len(raw)<=1024:raise ValueError('Bound native witness extent exceeds limit')
        ins=list(decoder().disasm(raw,0))
        if sum(i.size for i in ins)!=len(raw):raise ValueError('Bound native witness incomplete')
    if consumer:
        from war3_discovery_locators import matches
        raw=bytes.fromhex(chain[0]['code']);binary,mask=_unit_state_root_mask(raw,*signature(raw,variable_fields=True))
        if site_hints is None:sites=matches(image,binary,mask,budget)
        else:
            sites=[]
            for site in dict.fromkeys(site_hints):
                budget.check('正在复核字段分派消费者')
                try:observed=image.read(site,len(binary))
                except OSError:continue
                if all(not flag or a==b for a,b,flag in zip(binary,observed,mask)):
                    sites.append(site)
        sites=[at for at in sites if image.function_size(at)==len(raw)]
        if len(sites)>1:raise _AmbiguousConsumer(sites)
        if not sites:return None,()
        at=sites[0]
    else:
        entry=(entries or {}).get(binding['native'])
        if entry is None or entry.signature!=binding['signature']:return None,()
        at=entry.handler-image.base
    anchors=[]
    for index,row in enumerate(chain):
        budget.check('正在核对原生字段的实际调用链')
        raw=bytes.fromhex(row['code']);binary,mask=signature(raw,variable_fields=not row.get('fixed_displacements',False))
        if consumer and index==0:binary,mask=_unit_state_root_mask(raw,binary,mask)
        extent=image.function_size(at)
        if extent != len(binary):return None,()
        try:observed=image.read(at,len(binary))
        except OSError:return None,()
        if any(flag and left!=right for left,right,flag in zip(binary,observed,mask)):return None,()
        ins=list(decoder().disasm(observed,at))
        from capstone import CS_GRP_JUMP
        source_ins=list(decoder().disasm(raw,0))
        tail_result=_bound_error_tails(image,ins,row.get('error_tails',()),budget)
        if tail_result is None:return None,()
        tails,tail_anchors=tail_result
        for instruction_index,(old,new) in enumerate(zip(source_ins,ins)):
            if old.group(CS_GRP_JUMP) and old.operands[0].type==X86_OP_IMM:
                if not 0<=old.operands[0].imm<len(raw):
                    if instruction_index not in tails:return None,()
                elif new.operands[0].imm-at!=old.operands[0].imm:
                    return None,()
        if consumer and index==0:
            additions=[i.operands[1].imm for i in ins if i.mnemonic=='add' and i.op_str.startswith('rcx,')]
            if len(additions)!=2 or additions[0]!=additions[1] or not 0<additions[0]<0x10000 or additions[0]%8:
                return None,()
        calls=[i for i in ins if i.mnemonic=='call' and i.operands[0].type==X86_OP_IMM]
        if row['call_index']>=len(calls):return None,()
        if index==0 and 'unit_call' in binding and (not calls or calls[0].operands[0].imm!=resolver.candidates[0]):
            return None,()
        anchors.extend(tail_anchors);anchors.append((at,observed.hex()));at=calls[row['call_index']].operands[0].imm
        if not image.executable(at):return None,()
    return at,tuple(anchors)


def _instruction_value(instructions, selector):
    from capstone.x86 import X86_OP_MEM, X86_OP_IMM, X86_OP_REG
    allowed = {'instruction','operand','mnemonic','base','size','transform'}
    if set(selector) - allowed: raise ValueError('Unknown semantic operand selector')
    index, operand = selector['instruction'], selector['operand']
    if type(index) is not int or type(operand) is not int or index < 0 or operand < 0:
        raise ValueError('Invalid semantic operand index')
    if index >= len(instructions): return None
    ins = instructions[index]
    if ins.mnemonic != selector['mnemonic'] or operand >= len(ins.operands): return None
    op = ins.operands[operand]
    transform = selector.get('transform', 'displacement')
    if transform == 'displacement':
        if (op.type != X86_OP_MEM or op.mem.index or
                ins.reg_name(op.mem.base) != selector['base'] or op.size != selector['size']): return None
        return op.mem.disp
    if transform == 'bit_mask':
        # The equipment classifier loads flags, shifts that same register,
        # and tests its low bit. A shift constant without these register
        # and operand roles is not a classifier witness.
        low_register = {'eax':'al', 'ecx':'cl', 'edx':'dl', 'ebx':'bl'}
        if (ins.mnemonic!='shr' or operand!=1 or op.type!=X86_OP_IMM or not 0<=op.imm<32 or
                len(ins.operands)!=2 or ins.operands[0].type!=X86_OP_REG or
                ins.reg_name(ins.operands[0].reg)!=selector['base'] or
                ins.operands[0].size!=selector['size'] or selector['size']!=4 or
                not 0<index<len(instructions)-1):return None
        previous,next_ins=instructions[index-1],instructions[index+1]
        if (previous.mnemonic!='mov' or len(previous.operands)!=2 or
                previous.operands[0].type!=X86_OP_REG or
                previous.operands[0].reg!=ins.operands[0].reg or
                previous.operands[1].type!=X86_OP_MEM or previous.operands[1].size!=4 or
                previous.operands[1].mem.index or
                next_ins.mnemonic!='test' or len(next_ins.operands)!=2 or
                next_ins.operands[0].type!=X86_OP_REG or
                next_ins.reg_name(next_ins.operands[0].reg)!=low_register.get(selector['base']) or
                next_ins.operands[1].type!=X86_OP_IMM or next_ins.operands[1].imm!=1):return None
        return 1 << op.imm
    if transform == 'immediate':
        if op.type != X86_OP_IMM: return None
        return op.imm
    if transform == 'indexed_stride':
        # Reviewed slot-address calculation: index + index*2, followed by
        # array + scaled_index*4. Both register roles and zero displacements
        # are mandatory; an arbitrary LEA is not an element-stride witness.
        from capstone.x86 import X86_OP_REG
        if (op.type!=X86_OP_MEM or op.mem.disp or op.size!=8 or
            ins.reg_name(op.mem.base)!=selector['base'] or
            ins.reg_name(op.mem.index)!=selector['base'] or op.mem.scale!=2 or
            index+1>=len(instructions)):return None
        next_ins=instructions[index+1]
        if (ins.operands[0].type!=X86_OP_REG or next_ins.mnemonic!='lea' or
            len(next_ins.operands)!=2 or next_ins.operands[0].type!=X86_OP_REG or
            next_ins.operands[0].reg!=ins.operands[0].reg or
            next_ins.operands[1].type!=X86_OP_MEM):return None
        next_op=next_ins.operands[1]
        if (next_op.mem.disp or next_op.mem.index!=ins.operands[0].reg or
            ins.reg_name(next_op.mem.base)!='rax' or next_op.mem.scale!=4):return None
        return (1+op.mem.scale)*next_op.mem.scale
    raise ValueError('Unknown semantic operand transform')


def _helper_witnesses(image, instructions, helpers, budget):
    """Verify the called arithmetic bodies, including every internal branch."""
    from capstone import CS_GRP_JUMP
    from capstone.x86 import X86_OP_IMM
    from war3_discovery_locators import decoder, signature
    if not isinstance(helpers, (list, tuple)) or len(helpers) > 8:
        raise ValueError('Semantic helper list exceeds bound')
    anchors=[]
    for helper in helpers:
        if set(helper) != {'instruction', 'code'}:
            raise ValueError('Invalid reviewed semantic helper')
        index=helper['instruction']
        if type(index) is not int or not 0<=index<len(instructions):
            raise ValueError('Invalid semantic helper instruction')
        caller=instructions[index]
        if caller.mnemonic!='call' or len(caller.operands)!=1 or caller.operands[0].type!=X86_OP_IMM:
            raise ValueError('Semantic helper selector is not a direct call')
        raw=bytes.fromhex(helper['code'])
        if not 24<=len(raw)<=1024:
            raise ValueError('Semantic helper code extent exceeds bound')
        source=list(decoder().disasm(raw,0))
        if sum(ins.size for ins in source)!=len(raw) or not source or source[-1].mnemonic!='ret':
            raise ValueError('Semantic helper body is incomplete')
        boundaries={ins.address for ins in source}
        for ins in source:
            if ins.group(CS_GRP_JUMP) and (not ins.operands or ins.operands[0].type!=X86_OP_IMM or
                                         ins.operands[0].imm not in boundaries):
                raise ValueError('Semantic helper branch leaves its reviewed body')
        at=caller.operands[0].imm
        budget.check('正在核对字段计算的实际算术函数')
        if not image.executable(at) or image.function_size(at)!=len(raw):
            return None
        try:observed=image.read(at,len(raw))
        except OSError:return None
        binary,mask=signature(raw)
        if any(flag and a!=b for a,b,flag in zip(binary,observed,mask)):
            return None
        actual=list(decoder().disasm(observed,at))
        if sum(ins.size for ins in actual)!=len(raw) or len(actual)!=len(source):
            return None
        for old,new in zip(source,actual):
            if old.group(CS_GRP_JUMP) and (new.operands[0].imm-at!=old.operands[0].imm):
                return None
        anchors.append((at,observed.hex()))
    return tuple(dict.fromkeys(anchors))


def _coordinate_contract(instructions, contract, selectors):
    """Reviewed position-vector consumers; stack and proxy offsets stay fixed.

    The two axes are a packed pair. The getter adds their independent rates;
    the setter recomputes that pair and writes both floats together. Only this
    record's four contiguous members may relocate, with every use agreeing.
    """
    from capstone.x86 import X86_OP_MEM
    if set(selectors)!={'layouts.property.position_x','layouts.property.position_y'}:
        raise ValueError('Position contract must describe both axes')
    if contract=='position_record_getter_v1':
        base='rsi'; indices=(31,21,18,9); expected_count=45
        writes=()
    elif contract=='position_record_setter_v1':
        base='r14'; indices=(30,20,16,10); expected_count=68
        writes=(52,54,58)
    else:
        raise ValueError('Unreviewed semantic contract')
    if len(instructions)!=expected_count:return None
    members=[];masked=[]
    for index in indices:
        ins=instructions[index]
        if (ins.mnemonic!='lea' or len(ins.operands)!=2 or ins.operands[1].type!=X86_OP_MEM or
                ins.reg_name(ins.operands[1].mem.base)!=base or ins.operands[1].mem.index):
            return None
        members.append(ins.operands[1].mem.disp);masked.append(ins)
    start=members[0]
    if (not 0<start<0xfff0 or start%4 or members!=[start,start+4,start+8,start+12] or
            selectors['layouts.property.position_x']!={'instruction':indices[0],'operand':1,
                'mnemonic':'lea','base':base,'size':8,'transform':'displacement'} or
            selectors['layouts.property.position_y']!={'instruction':indices[1],'operand':1,
                'mnemonic':'lea','base':base,'size':8,'transform':'displacement'}):
        return None
    for index in writes:
        ins=instructions[index];operand=0 if index==52 else 1
        if (len(ins.operands)!=2 or ins.operands[operand].type!=X86_OP_MEM or
                ins.reg_name(ins.operands[operand].mem.base)!=base or ins.operands[operand].mem.index or
                ins.operands[operand].mem.disp!=start or ins.operands[operand].size!=8 or
                ins.mnemonic!=('mov' if index==52 else 'lea')):
            return None
        masked.append(ins)
    return tuple(masked)


def locate_semantic_fields(image, recipes, budget, *, entries=None, site_hints=None,resolver=None):
    from war3_discovery_locators import decoder, signature, matches
    from capstone import CS_GRP_JUMP
    from capstone.x86 import X86_OP_IMM
    if not isinstance(recipes, (list, tuple)) or len(recipes) > 64:
        raise ValueError('Semantic recipe list exceeds bound')
    observations = {}; failures = {}; seen_ids = set()
    for recipe in recipes:
        if set(recipe)-{'id','source','code','fields','links','binding','consumer_binding','peer_binding','helpers','contract'} or not {'id','source','code','fields','links'}<=set(recipe):
            raise ValueError('Invalid semantic recipe data')
        identity = recipe['id']
        if not isinstance(identity,str) or not identity or identity in seen_ids:
            raise ValueError('Duplicate semantic consumer identity')
        seen_ids.add(identity)
        raw = bytes.fromhex(recipe['code'])
        if not 24 <= len(raw) <= 1024 or not recipe['source']:
            raise ValueError('Semantic witness exceeds bounded code extent')
        selectors = recipe['fields']
        if not isinstance(selectors,dict) or set(selectors) - ALLOWED_FIELDS:
            raise ValueError('Unreviewed semantic member')
        budget.check('正在定位技能与装备字段')
        binary, mask = signature(raw, variable_fields='contract' not in recipe)
        # Only explicit immediate operands may vary. Other constants, masks,
        # register roles and instruction kinds stay part of the witness.
        source_ins = list(decoder().disasm(raw, 0))
        if sum(i.size for i in source_ins) != len(raw):
            raise ValueError('Semantic witness contains an undecoded suffix')
        boundaries={i.address for i in source_ins}
        if any(i.group(CS_GRP_JUMP) and (not i.operands or i.operands[0].type!=X86_OP_IMM or
               0<=i.operands[0].imm<len(raw) and i.operands[0].imm not in boundaries)
               for i in source_ins):
            raise ValueError('Semantic witness branch enters an instruction operand')
        changed = bytearray(mask)
        if 'contract' in recipe:
            getter=recipe['contract']=='position_record_getter_v1'
            helper_indices=(15,20,28,33) if getter else (14,19,27,32,40,45)
            native_prefix='Get' if getter else 'Set'
            expected_signature='(Hunit;)R' if getter else '(Hunit;R)V'
            if (not {'binding','peer_binding','helpers'}<=set(recipe) or
                    recipe['binding'].get('unit_call')!=0 or recipe['peer_binding'].get('unit_call')!=0 or
                    recipe['binding'].get('native')!=native_prefix+'UnitX' or
                    recipe['peer_binding'].get('native')!=native_prefix+'UnitY' or
                    recipe['binding'].get('signature')!=expected_signature or
                    recipe['peer_binding'].get('signature')!=expected_signature or
                    tuple(helper.get('instruction') for helper in recipe['helpers'])!=helper_indices or
                    any(not row.get('fixed_displacements') for key in ('binding','peer_binding')
                        for row in recipe[key]['chain'])):
                raise ValueError('Position contract lacks its paired typed natives or arithmetic closure')
            members=_coordinate_contract(source_ins,recipe['contract'],selectors)
            if members is None:raise ValueError('Position contract does not describe its reviewed body')
            for ins in members:
                changed[ins.address+ins.disp_offset:ins.address+ins.disp_offset+ins.disp_size]=bytes(ins.disp_size)
        for selector in selectors.values():
            if _instruction_value(source_ins, selector) is None:
                raise ValueError('Semantic selector does not describe its source instruction')
            if selector.get('transform') in ('immediate', 'bit_mask'):
                i = source_ins[selector['instruction']]
                changed[i.address+i.imm_offset:i.address+i.imm_offset+i.imm_size] = bytes(i.imm_size)
        parent_anchors=()
        if 'binding' in recipe or 'consumer_binding' in recipe:
            targets={};ambiguous=[]
            for key in ('binding','consumer_binding'):
                if key not in recipe:continue
                try:site,anchors=_bound_consumer(image,recipe[key],entries,budget,site_hints=site_hints,resolver=resolver)
                except _AmbiguousConsumer as exc:ambiguous.extend(exc.sites);continue
                if site is not None:targets.setdefault(site,[]).extend(anchors)
            if ambiguous or len(targets)>1:
                for path in selectors:failures.setdefault(path,[]).append((identity,'ambiguous',ambiguous+list(targets)))
                continue
            site=next(iter(targets),None);parent_anchors=tuple(dict.fromkeys(targets.get(site,())))
            if site is None:sites=[]
            else:
                try:observed=image.read(site,len(binary))
                except OSError:observed=b''
                sites=[site] if len(observed)==len(binary) and all(not flag or left==right for left,right,flag in zip(binary,observed,changed)) else []
        elif site_hints is None:sites = matches(image, binary, bytes(changed), budget)
        else:
            hints=tuple(dict.fromkeys(site_hints))
            if len(hints)>256 or any(type(at) is not int for at in hints):raise ValueError('Semantic cache hint set exceeds bound')
            sites=[]
            for at in hints:
                budget.check('正在复核已记录的字段消费者')
                try:observed=image.read(at,len(binary))
                except OSError:continue
                if all(not flag or left==right for left,right,flag in zip(binary,observed,changed)):sites.append(at)
        if len(sites) != 1:
            for path in selectors:
                failures.setdefault(path,[]).append((identity, 'ambiguous' if sites else 'unresolved', sites))
            continue
        site = sites[0]
        if 'peer_binding' in recipe:
            if 'contract' not in recipe or 'binding' not in recipe:
                raise ValueError('Peer native binding requires a reviewed position contract')
            peer,anchors=_bound_consumer(image,recipe['peer_binding'],entries,budget,resolver=resolver)
            if peer!=site:
                for path in selectors:failures.setdefault(path,[]).append((identity,'unresolved',[]))
                continue
            parent_anchors=tuple(dict.fromkeys(parent_anchors+anchors))
        # Pdata boundaries prove that the witness is code rather than an
        # instruction-shaped byte sequence embedded in a different function.
        extent=image.function_size(site)
        if extent != len(binary):
            for path in selectors: failures.setdefault(path,[]).append((identity,'unresolved',[]))
            continue
        insns = list(decoder().disasm(image.read(site,len(binary)),site))
        # Relative jump operands are masked during candidate searches, then
        # verified against the reviewed control flow. External reviewed tails
        # may relocate; they must remain outside the complete function.
        if (sum(i.size for i in insns)!=len(binary) or len(insns)!=len(source_ins) or
                any(old.group(CS_GRP_JUMP) and
                    ((0<=old.operands[0].imm<len(raw) and
                      new.operands[0].imm-site!=old.operands[0].imm) or
                     (not 0<=old.operands[0].imm<len(raw) and
                      site<=new.operands[0].imm<site+len(raw)))
                    for old,new in zip(source_ins,insns))):
            for path in selectors:failures.setdefault(path,[]).append((identity,'unresolved',[]))
            continue
        values = {path:_instruction_value(insns,selector) for path,selector in selectors.items()}
        if 'contract' in recipe and _coordinate_contract(insns,recipe['contract'],selectors) is None:
            for path in selectors:failures.setdefault(path,[]).append((identity,'unresolved',[]))
            continue
        if any(value is None or type(value) is not int or not 0 <= value < 0x10000 for value in values.values()):
            for path in selectors: failures.setdefault(path,[]).append((identity,'unresolved',[]))
            continue
        helper_anchors=_helper_witnesses(image,insns,recipe.get('helpers',()),budget)
        if helper_anchors is None:
            for path in selectors:failures.setdefault(path,[]).append((identity,'unresolved',[]))
            continue
        parent_anchors=tuple(dict.fromkeys(parent_anchors+helper_anchors))
        links = recipe['links']
        if not isinstance(links,(list,tuple)) or any(not isinstance(link,str) for link in links):
            raise ValueError('Invalid linked consumer identities')
        witness=(site,image.read(site,len(binary)).hex())
        for path,value in values.items():
            observations.setdefault(path,[]).append((identity,value,site,links,witness,parent_anchors))
    # All successful consumers must agree. A missing corroborator keeps a
    # field unresolved; another occurrence of the same recipe is not proof.
    updates,evidence = {},{}
    for path in set(observations) | set(failures):
        rows=observations.get(path,[]); values={row[1] for row in rows}
        required={link for row in rows for link in row[3]}
        consumers={row[0] for row in rows}
        if len(values)>1 or any(state=='ambiguous' for _,state,_ in failures.get(path,())):
            evidence[path]=DiscoveryEvidence(path,'ambiguous','semantic_consumer_disagreement',
                                              tuple(sorted(values)),tuple(dict.fromkeys(anchor for row in rows for anchor in (row[4],)+row[5])))
        elif len(values)==1 and len(consumers)>=2 and len({row[2] for row in rows})>=2 and required <= consumers:
            value=next(iter(values));updates[path]=value
            evidence[path]=DiscoveryEvidence(path,'confirmed','independent_semantic_consumers',
                                              (value,),tuple(dict.fromkeys(anchor for row in rows for anchor in (row[4],)+row[5])))
        else:
            evidence[path]=DiscoveryEvidence(path,'unresolved','semantic_corroborator_missing',
                                              tuple(sorted(values)),tuple(dict.fromkeys(anchor for row in rows for anchor in (row[4],)+row[5])))
    return updates,evidence


def native_scalar_members(image, entries, evidence, budget):
    """Typed direct scalar getters; opaque or accessor-based bodies stay unresolved."""
    from capstone.x86 import X86_OP_REG,X86_OP_MEM,X86_OP_IMM
    from war3_discovery_locators import decoder
    specification=(('BlzGetUnitArmor','(Hunit;)R','native_members.unit_armor'),)
    resolver=evidence.get('addresses.unit_resolver')
    updates,proofs={},{}
    for name,signature,path in specification:
        entry=entries.get(name)
        if resolver is None or resolver.state!='confirmed' or entry is None or entry.signature!=signature:continue
        at=entry.handler-image.base;size=image.function_size(at)
        if size is None or not 20<=size<=128:continue
        budget.check('正在核对原生属性读取字段')
        try:raw=image.read(at,size)
        except OSError:continue
        insns=list(decoder().disasm(raw,at))
        if sum(i.size for i in insns)!=size:continue
        calls=[i for i in insns if i.mnemonic=='call']
        if (len(calls)!=1 or len(calls[0].operands)!=1 or calls[0].operands[0].type!=X86_OP_IMM or
                calls[0].operands[0].imm!=resolver.candidates[0]):continue
        before=[i for i in insns if i.address<calls[0].address]
        if any(i.mnemonic not in ('push','sub','mov','nop') or
               (i.operands and i.operands[0].type==X86_OP_REG and
                i.reg_name(i.operands[0].reg) in ('rcx','ecx','cx','cl')) for i in before):continue
        # This approved compiler shape guards the null unit, then loads and
        # returns exactly one four-byte member of the resolved unit object.
        tail=[i for i in insns if i.address>calls[0].address]
        if len(tail)!=7:continue
        guard,branch,cleanup,empty_ret,load,final_cleanup,final_ret=tail
        if (guard.mnemonic!='test' or guard.op_str!='rax, rax' or branch.mnemonic not in ('jne','jnz') or
            branch.operands[0].type!=X86_OP_IMM or branch.operands[0].imm!=load.address or
            cleanup.mnemonic!='add' or cleanup.op_str!='rsp, 0x28' or empty_ret.mnemonic!='ret' or
            final_cleanup.mnemonic!='add' or final_cleanup.op_str!='rsp, 0x28' or final_ret.mnemonic!='ret' or
            load.mnemonic!='mov' or len(load.operands)!=2 or load.operands[0].type!=X86_OP_REG or
            load.reg_name(load.operands[0].reg)!='eax' or load.operands[1].type!=X86_OP_MEM or
            load.operands[1].size!=4 or load.reg_name(load.operands[1].mem.base)!='rax' or
            load.operands[1].mem.index):continue
        member=load.operands[1].mem.disp
        if not 0<member<0x10000 or member%4:continue
        proofs[path]=DiscoveryEvidence(path,'confirmed','typed_native_scalar_member_return',(member,),((at,raw.hex()),))
        # A typed getter proves its own return member. It does not establish
        # that an existing external field called "armor" has the same meaning
        # (base versus final/cached armor). Keep this observation separate;
        # never overwrite that profile member merely because the names match.
    return updates,proofs


def native_direct_coordinates(image,entries,resolver,budget):
    """Require independent getter/setter dataflow, with no field-name aliasing."""
    from capstone import CS_GRP_JUMP
    from capstone.x86 import X86_OP_REG,X86_OP_MEM,X86_OP_IMM
    from war3_discovery_abi import _body,_register_family,_return_epilogue,_unit_input_to_call,VOLATILE
    updates,proofs={},{}
    for axis in ('X','Y'):
        path='layouts.unit.position_'+axis.lower();samples={}
        if resolver is not None and resolver.state=='confirmed' and len(resolver.candidates)==1:
            for kind,name,signature in (
                ('getter','GetUnit'+axis,'(Hunit;)R'),
                ('setter','SetUnit'+axis,'(Hunit;R)V')):
                entry=entries.get(name)
                if entry is None or entry.signature!=signature:continue
                parsed=_body(image,entry,budget)
                if parsed is None:continue
                at,raw,insns=parsed
                calls=[i for i in insns if i.mnemonic=='call']
                if (not calls or calls[0].operands[0].type!=X86_OP_IMM or
                    calls[0].operands[0].imm!=resolver.candidates[0] or
                    kind=='setter' and len(calls)!=1):continue
                first=calls[0]
                if not _unit_input_to_call(insns,first):continue
                units=set();real={'rdx'} if kind=='setter' else set();values=set();members=[];invalid=False
                for index,ins in enumerate(insns):
                    ops=ins.operands
                    if ins.mnemonic=='call':
                        units.difference_update(VOLATILE);real.difference_update(VOLATILE)
                        values.difference_update(VOLATILE|{'xmm'+str(i) for i in range(6)})
                        if ins.address==first.address:units.add('rax')
                        continue
                    if kind=='setter' and ins.group(CS_GRP_JUMP):
                        # This supported direct setter has at most a null-unit
                        # exit. Followed helper calls or other branches require
                        # a separate reviewed recipe.
                        previous=insns[index-1] if index else None
                        target=ops[0].imm if ops and ops[0].type==X86_OP_IMM else -1
                        suffix=[i for i in insns if i.address>=target]
                        if (ins.mnemonic not in ('je','jz') or previous is None or previous.mnemonic!='test' or
                            len(previous.operands)!=2 or any(op.type!=X86_OP_REG for op in previous.operands) or
                            previous.operands[0].reg!=previous.operands[1].reg or
                            previous.reg_name(previous.operands[0].reg) not in units or
                            target<=ins.address or not suffix or suffix[-1].mnemonic!='ret' or
                            any(i.mnemonic not in ('mov','add','pop','nop','ret') or
                                i.operands and i.operands[0].type==X86_OP_MEM and
                                i.reg_name(i.operands[0].mem.base)!='rsp' for i in suffix)):
                            invalid=True;break
                    copied_unit=copied_real=copied_value=None;loaded_value=None
                    if len(ops)==2:
                        if kind=='getter' and (ins.mnemonic=='mov' and ops[0].type==X86_OP_REG and
                            ins.reg_name(ops[0].reg)=='eax' and ops[1].type==X86_OP_MEM and
                            ops[1].size==4 and not ops[1].mem.index and
                            ins.reg_name(ops[1].mem.base) in units and _return_epilogue(insns,index)):
                            members.append(ops[1].mem.disp)
                        if kind=='setter' and ins.mnemonic in ('mov','movss') and ops[0].type==X86_OP_MEM:
                            mem=ops[0].mem
                            if (ops[0].size==4 and not mem.index and ins.reg_name(mem.base) in units and
                                ops[1].type==X86_OP_REG and _register_family(ins.reg_name(ops[1].reg)) in values):
                                members.append(mem.disp)
                        if ins.mnemonic=='mov' and ops[0].type==ops[1].type==X86_OP_REG and ops[0].size==ops[1].size==8:
                            destination=ins.reg_name(ops[0].reg);source=ins.reg_name(ops[1].reg)
                            if source in units:copied_unit=destination
                            if source in real:copied_real=destination
                        if kind=='setter' and ins.mnemonic in ('mov','movss') and ops[0].type==X86_OP_REG:
                            destination=_register_family(ins.reg_name(ops[0].reg))
                            if (ops[1].type==X86_OP_MEM and ops[1].size==4 and not ops[1].mem.index and
                                ops[1].mem.disp==0 and ins.reg_name(ops[1].mem.base) in real):
                                loaded_value=destination
                            elif (ops[1].type==X86_OP_REG and ops[1].size==ops[0].size and
                                  _register_family(ins.reg_name(ops[1].reg)) in values):
                                copied_value=destination
                    _,written=ins.regs_access()
                    changed={_register_family(ins.reg_name(reg)) for reg in written}
                    units.difference_update(changed);real.difference_update(changed);values.difference_update(changed)
                    if copied_unit is not None:units.add(copied_unit)
                    if copied_real is not None:real.add(copied_real)
                    if loaded_value is not None:values.add(loaded_value)
                    if copied_value is not None:values.add(copied_value)
                members=set(members)
                if not invalid and len(members)==1 and all(0<v<0x10000 and v%4==0 for v in members):
                    samples[kind]=(next(iter(members)),(at,raw.hex()))
        candidates=tuple(sorted({v for v,anchor in samples.values()}));anchors=tuple(a for v,a in samples.values())
        if (len(samples)==2 and len(candidates)==1 and len({a[0] for a in anchors})==2):
            updates[path]=candidates[0]
            proofs[path]=DiscoveryEvidence(path,'confirmed','typed_coordinate_getter_and_setter',candidates,anchors)
        elif len(candidates)>1:
            proofs[path]=DiscoveryEvidence(path,'ambiguous','coordinate_consumer_disagreement',candidates,anchors)
        else:
            proofs[path]=DiscoveryEvidence(path,'unresolved','coordinate_independent_consumer_missing',candidates,anchors)
    return updates,proofs
