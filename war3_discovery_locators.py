"""Instruction-aware, read-only locators; no first-match or address-delta fallback."""
from __future__ import annotations
import re
import struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_GRP_CALL, CS_GRP_JUMP
from capstone.x86 import X86_OP_MEM, X86_OP_IMM, X86_REG_RIP
from war3_profile_discovery import DiscoveryEvidence, unique_evidence


def decoder():
    result = Cs(CS_ARCH_X86, CS_MODE_64)
    result.detail = True
    return result


def signature(code, rva=0, *, variable_immediates=False, variable_fields=False):
    """Mask relocation operands, not registers/opcodes/control-flow instruction kinds."""
    mask = bytearray(b"\xff" * len(code))
    extent = 0
    for ins in decoder().disasm(code, rva):
        off = ins.address-rva
        extent = off+ins.size
        relative = any(op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP for op in ins.operands)
        if relative or variable_fields:
            mask[off+ins.disp_offset:off+ins.disp_offset+ins.disp_size] = bytes(ins.disp_size)
        if ins.group(CS_GRP_CALL) or ins.group(CS_GRP_JUMP) or variable_immediates:
            mask[off+ins.imm_offset:off+ins.imm_offset+ins.imm_size] = bytes(ins.imm_size)
    return code[:extent], bytes(mask[:extent])


def matches(image, code, mask, budget, *, limit=4096):
    if not code or len(code) != len(mask) or sum(bool(m) for m in mask) < 6:
        return []
    spans=[];start=None
    for index,value in enumerate(mask+b'\0'):
        if value and start is None:start=index
        if not value and start is not None:
            spans.append((start,index));start=None
    a,b=max(spans,key=lambda pair:pair[1]-pair[0])
    if b-a>=6:
        # The literal anchor is searched in C; only its bounded candidates need
        # masked comparison. Avoid one whole-image regex pass per caller recipe.
        found=[]
        for hit in image.find(code[a:b],budget,executable=True,limit=limit):
            site=hit-a
            try:observed=image.read(site,len(code))
            except OSError:continue
            if all(not flag or left==right for left,right,flag in zip(code,observed,mask)):
                found.append(site)
        return found
    # Regex executes the masked batch in C and includes instruction-boundary bytes.
    pattern = re.compile(b"(?=(" + b"".join(re.escape(bytes([b])) if m else b"."
                                           for b, m in zip(code, mask)) + b"))", re.DOTALL)
    found = []
    for segment in image.segments:
        budget.check("正在匹配函数与结构特征")
        if not segment.executable: continue
        for match in pattern.finditer(segment.data):
            budget.check()
            found.append(segment.rva+match.start())
            if len(found) > limit:
                return []  # Too broad, never choose the first candidate.
    return found


def rip_targets(image, rva, size):
    result = []
    for ins in decoder().disasm(image.read(rva, size), rva):
        for op in ins.operands:
            if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                value = ins.address+ins.size+op.mem.disp
                if 0 <= value < image.size: result.append(value)
    return result


def locate_reference(image, reference, budget):
    code = bytes.fromhex(reference["code"])
    binary, mask = signature(code, reference.get("rva", 0),
                             variable_immediates=reference.get("variable_immediates", False),
                             variable_fields=reference.get("variable_fields", False))
    found = matches(image, binary, mask, budget)
    return found, len(binary)


def rtti_tables(image, type_name, budget):
    """MSVC x64 complete-object locator, self RVA, primary subobject and method pointers."""
    descriptors = set(image.find((".?AV"+type_name+"@@").encode()+b"\0", budget, executable=False))
    descriptors.update(rva+16 for rva in getattr(image, 'type_descriptors', {}).get(type_name, ()))
    tables = []
    for name_rva in descriptors:
        type_rva = name_rva-16
        if type_rva < 0: continue
        for hit in image.find(struct.pack("<I", type_rva), budget, executable=False):
            col = hit-12
            if col < 0 or col % 4: continue
            try:
                sig, offset, cd, typ, hierarchy, self_rva = struct.unpack("<6I", image.read(col, 24))
                if (sig, offset, cd, typ, self_rva) != (1, 0, 0, type_rva, col): continue
                if not 0 < hierarchy < image.size: continue
                for at in image.find(struct.pack("<Q", image.base+col), budget, executable=False):
                    if at % 8: continue
                    methods = struct.unpack("<3Q", image.read(at+8, 24))
                    if all(image.executable(ptr-image.base) for ptr in methods):
                        tables.append(at+8)
            except OSError:
                continue
    return tuple(sorted(set(tables)))


def rtti_table_witness(image,table,budget):
    """Store only relative identity data; absolute method pointers are discarded."""
    budget.check('正在记录属性组件类型依据')
    col=struct.unpack('<Q',image.read(table-8,8))[0]-image.base
    raw=image.read(col,24)
    signature,offset,cd,typ,hierarchy,self_rva=struct.unpack('<6I',raw)
    if (signature,offset,cd,self_rva)!=(1,0,0,col):raise ValueError('Invalid primary RTTI identity')
    methods=tuple(value-image.base for value in struct.unpack('<3Q',image.read(table,24)))
    if not all(image.executable(value) for value in methods):raise ValueError('RTTI methods leave the executable image')
    return table,col,raw.hex(),methods


def decode_state_fragment(code, rva):
    """Recognize the two bundled algorithms and recover constants; reject other orderings."""
    insns = list(decoder().disasm(code, rva))
    constants, operations = {}, []
    target = None
    for ins in insns:
        ops = ins.operands
        if ins.mnemonic in ("mov", "movabs") and len(ops) == 2 and ops[1].type == X86_OP_IMM:
            constants[ins.reg_name(ops[0].reg)] = ops[1].imm & ((1<<64)-1)
        elif ins.mnemonic in ("rol", "ror", "add", "xor") and len(ops) == 2:
            reg = ins.reg_name(ops[0].reg)
            if target is None: target = reg
            if reg != target: return None
            value = ops[1].imm if ops[1].type == X86_OP_IMM else constants.get(ins.reg_name(ops[1].reg))
            if value is None: return None
            operations.append((ins.mnemonic, value))
        elif ins.mnemonic != "nop":
            return None
    names = tuple(op[0] for op in operations)
    if names == ("ror", "rol", "add", "xor", "add"):
        return "legacy", dict(zip(("ror", "rol", "add1", "xor", "add2"), (op[1] for op in operations)))
    if names == ("rol", "xor", "ror"):
        return "modern_tail", dict(zip(("rol", "xor", "ror"), (op[1] for op in operations)))
    return None


STAT_TYPES = {
    "cooldown_vtable": "CAbilityCooldownReduction",
    "amplification_vtable": "CAbilitySpellAmp",
    "spell_vamp_vtable": "CAbilitySpellVamp",
    "resolve_vtable": "CAbilityResolve",
}


def locate(image, source, references, budget):
    updates, evidence, checks = {}, {}, {}
    def accept(path, values, method, anchors=()):
        proof = unique_evidence(path, method, values, anchors)
        evidence[path] = proof
        if proof.state == "confirmed": updates[path] = proof.candidates[0]
        return proof
    # The registry resolver contains both primary and alternate references to the same root.
    for key in ("object_resolver", "speed_factor", "effective_interval", "unit_resolver"):
        ref = references.get("addresses."+key)
        if not ref: continue
        if key == 'object_resolver':
            ref = dict(ref, variable_fields=True)
        found, size = locate_reference(image, ref, budget)
        proof = accept("addresses."+key, found, "instruction_shape", tuple(found))
        if key == "object_resolver" and proof.state == "confirmed":
            targets = rip_targets(image, found[0], size)
            root = accept("addresses.registry_root", targets, "resolver_primary_alternate_rip", tuple(found))
            if len(targets) < 2:
                evidence["addresses.registry_root"] = DiscoveryEvidence("addresses.registry_root", "unresolved", "resolver_missing_second_reference")
                updates.pop("addresses.registry_root", None)
    for group, rows in source.data["checks"].items():
        checks[group] = []
        for index, row in enumerate(rows):
            name = f"checks.{group}.{index}"
            ref = references.get(name, dict(code=row["bytes"], rva=row["rva"]))
            if group == 'resolver': ref = dict(ref, variable_fields=True)
            found, size = locate_reference(image, ref, budget)
            proof = accept(name, found, "instruction_shape", tuple(found))
            if proof.state == "confirmed":
                checks[group].append(dict(rva=found[0], bytes=image.read(found[0], size).hex()))
            else:
                checks[group].append(None)
            if group == "context" and index == 0:
                accept("addresses.tls_index", [v for at in found for v in rip_targets(image, at, size)],
                       "context_tls_rip", tuple(found))
            if group == "game_state" and index == 0:
                accept("addresses.game_state", [v for at in found for v in rip_targets(image, at, size)],
                       "state_global_rip", tuple(found))
    for field, name in STAT_TYPES.items():
        tables=rtti_tables(image,name,budget)
        accept("stat_runtime."+field,tables,"msvc_rtti:"+name,
               tuple(rtti_table_witness(image,table,budget) for table in tables))
    if references.get('stat_field_consumers'):
        from war3_discovery_stats import locate_stat_mode,reconcile_stat_mode
        from war3_profile_resolver import _merge_observations
        stat_updates,stat_evidence=locate_stat_mode(image,references['stat_field_consumers'],evidence,budget)
        _merge_observations(updates,evidence,stat_updates,stat_evidence)
        reconcile_stat_mode(evidence)
    layout_updates, layout_evidence, layout_checks = locate_public_layout(image, source, budget)
    updates.update(layout_updates)
    evidence.update(layout_evidence)
    if 'context' in layout_checks:
        checks['context'] = layout_checks['context']
    if 'game_state_player' in layout_checks:
        checks['game_state'][2] = layout_checks['game_state_player']
    player_check=layout_checks.get('game_state_player')
    state_updates,state_evidence,state_checks=locate_state_decoder(
        image,budget,player_accessor=player_check['rva'] if player_check else None)
    updates.update(state_updates);evidence.update(state_evidence)
    if state_checks is not None:
        checks['game_state'][:2]=state_checks
    call_updates,call_evidence=locate_call_targets(image,
        {key:ref for key,ref in references.items() if key.startswith('addresses.') and
         (key not in evidence or evidence[key].state!='confirmed')},budget)
    for name,proof in call_evidence.items():
        if proof.state=='confirmed' and evidence.get(name,proof).state!='confirmed':
            updates[name]=call_updates[name];evidence[name]=proof
    resolver = evidence.get('addresses.object_resolver')
    if resolver is not None and resolver.state == 'confirmed':
        registry_updates, registry_evidence = resolver_registry_layout(image, resolver.candidates[0], budget)
        updates.update(registry_updates); evidence.update(registry_evidence)
    if references.get('semantic_fields'):
        from war3_discovery_fields import locate_semantic_fields
        from war3_profile_resolver import _merge_observations
        field_updates, field_evidence = locate_semantic_fields(image, references['semantic_fields'], budget)
        _merge_observations(updates, evidence, field_updates, field_evidence)
    return updates, evidence, checks


def resolver_registry_layout(image, rva, budget):
    """Parse both indexed handle branches; equal offsets elsewhere are irrelevant."""
    from capstone.x86 import X86_OP_REG
    budget.check('正在定位对象表布局')
    try: instructions = list(decoder().disasm(image.read(rva, 114), rva))
    except OSError: return {}, {}
    branches=[]; current=None
    for ins in instructions:
        ops=ins.operands
        if (ins.mnemonic=='mov' and len(ops)==2 and ops[0].type==X86_OP_REG and
                ops[1].type==X86_OP_MEM and ops[1].mem.base==X86_REG_RIP and ops[1].size==8):
            current={'root':ins.reg_name(ops[0].reg), 'counts':[], 'tables':[], 'owners':[], 'generation':[]}
            branches.append(current); continue
        if current is None: continue
        for operand in ops:
            if operand.type != X86_OP_MEM: continue
            mem=operand.mem; reg=ins.reg_name(mem.base)
            if reg==current['root'] and not mem.index:
                if ins.mnemonic=='cmp' and operand.size==4:current['counts'].append(mem.disp)
                if (ins.mnemonic=='mov' and len(ops)==2 and operand is ops[1] and operand.size==8):
                    current['tables'].append(mem.disp)
            if ins.mnemonic=='mov' and len(ops)==2 and operand is ops[1] and operand.size==8 and mem.index and mem.scale==8:
                current['owners'].append(mem.disp)
            if ins.mnemonic=='cmp' and reg=='rcx' and not mem.index and operand.size==4:
                current['generation'].append(mem.disp)
    if len(branches)!=2 or any(any(len(branch[k])!=1 for k in ('counts','tables','owners','generation')) for branch in branches):
        return {}, {'registry.indexed':DiscoveryEvidence('registry.indexed','unresolved','resolver_branch_shape')}
    first,second=branches
    count_offsets=[b['counts'][0]-b['tables'][0] for b in branches]
    owners=[b['owners'][0] for b in branches];generations=[b['generation'][0] for b in branches]
    doubled=sum(ins.mnemonic=='add' and ins.op_str in ('rcx, rcx','rax, rax') for ins in instructions)
    if (len(set(count_offsets))!=1 or len(set(owners))!=1 or len(set(generations))!=1 or doubled!=3 or
            not 0 < count_offsets[0] < 256 or not 0 < owners[0] < 64 or generations[0]<4):
        return {}, {'registry.indexed':DiscoveryEvidence('registry.indexed','unresolved','resolver_branch_disagreement')}
    values={'primary':first['tables'][0], 'alternate':second['tables'][0],
            'count':count_offsets[0], 'stride':16, 'slot_owner':owners[0]}
    if not all(0<value<0x400 and value%8==0 for value in values.values()): return {}, {}
    updates={'registry.'+key:value for key,value in values.items()}
    evidence={path:DiscoveryEvidence(path,'confirmed','both_resolver_handle_branches',(value,),(rva,))
              for path,value in updates.items()}
    # Comparing the generation dword does not prove the low dword's position.
    # Retain the complete-handle member as a candidate until a live owner agrees.
    evidence['registry.owner_handle']=DiscoveryEvidence('registry.owner_handle','candidate',
        'resolver_generation_member',(generations[0]-4,),(rva,))
    return updates,evidence


def native_call_and_field_evidence(image, entries, budget):
    """Use live registered getters to disambiguate calls and data-field access.

    Every operand is parsed on an instruction boundary. Truncated/protected
    functions remain unresolved rather than treating arbitrary bytes as evidence.
    """
    from capstone.x86 import X86_OP_REG
    from war3_discovery_abi import _body,_unit_input_to_call
    updates,evidence={},{}
    unit_calls=[]; corroborated_calls=set();caller_sites=set();anchors=[]
    for name in ("GetUnitTypeId", "GetUnitPointValue", "GetUnitX", "GetUnitY"):
        entry=entries.get(name)
        if entry is None:continue
        expected='(Hunit;)R' if name in ('GetUnitX','GetUnitY') else '(Hunit;)I'
        if getattr(entry,'signature',None)!=expected:continue
        budget.check('正在核对原生接口调用关系')
        parsed=_body(image,entry,budget)
        if parsed is None:continue
        rva,code,instructions=parsed
        calls=[i.operands[0].imm for i in instructions if i.mnemonic=='call' and len(i.operands)==1 and i.operands[0].type==X86_OP_IMM]
        if not calls or not image.executable(calls[0]):continue
        first_call=next(i for i in instructions if i.mnemonic=='call')
        # The unit handle must reach the first direct call unchanged in RCX.
        if not _unit_input_to_call(instructions,first_call):continue
        unit_calls.append(calls[0])
        caller_sites.add(rva);anchors.append((rva,code.hex()))
        if name=='GetUnitTypeId':
            try:
                prefix_code=image.read(calls[0],21)
                callee=list(decoder().disasm(prefix_code,calls[0]))
                expected=(('push','rbx'),('push','rbp'),('push','rsi'),('push','rdi'),
                          ('push','r14'),('sub','rsp, 0x20'),('mov','ebx, ecx'),
                          ('xor','esi, esi'),('mov','dword ptr [rsp + 0x50], esi'),('test','ecx, ecx'))
                if tuple((i.mnemonic,i.op_str) for i in callee)==expected and any(
                    i.mnemonic=='mov' and len(i.operands)==2 and i.operands[0].type==X86_OP_REG and
                    i.reg_name(i.operands[0].reg)=='eax' and i.operands[1].type==X86_OP_MEM and
                    i.reg_name(i.operands[1].mem.base)=='rax' and i.operands[1].size==4
                    for i in instructions):
                    corroborated_calls.add(calls[0])
                    anchors.append((calls[0],prefix_code.hex()))
            except OSError:pass
    proof=unique_evidence('addresses.unit_resolver','typed_native_unit_resolver_callers',unit_calls,
                         tuple(dict.fromkeys(anchors)))
    if len(caller_sites)<2 and not (len(set(unit_calls))==1 and set(unit_calls)==corroborated_calls):
        proof=DiscoveryEvidence('addresses.unit_resolver','unresolved','native_caller_and_callee_unconfirmed')
    evidence[proof.dependency]=proof
    if proof.state=='confirmed':updates[proof.dependency]=proof.candidates[0]
    # A getter's incidental load is not a complete coordinate proof. A
    # separately registered setter must consume the real pointer and write
    # the same field of the same resolved unit.
    from war3_discovery_fields import native_direct_coordinates
    for axis in ('x','y'):updates.pop('layouts.unit.position_'+axis,None)
    coordinate_updates,coordinate_proofs=native_direct_coordinates(image,entries,proof,budget)
    updates.update(coordinate_updates);evidence.update(coordinate_proofs)
    return updates,evidence


def locate_public_layout(image, source, budget):
    """Recover TLS accessor and player array fields from bounded producer functions."""
    from capstone.x86 import X86_OP_REG
    updates,evidence,checks={},{},{}
    def accept(path,values,method,anchors=()):
        proof=unique_evidence(path,method,values,anchors);evidence[path]=proof
        if proof.state=='confirmed':updates[path]=proof.candidates[0]
        return proof
    row=source.data['checks']['context'][2]
    code,mask=signature(bytes.fromhex(row['bytes']),row['rva'],variable_fields=True)
    sites=matches(image,code,mask,budget)
    if len(sites)==1:
        site=sites[0];body=list(decoder().disasm(image.read(site,len(code)),site))
        calls=[i.operands[0].imm for i in body if i.mnemonic=='call' and i.operands[0].type==X86_OP_IMM]
        if len(calls)==1:
            accessor=calls[0]
            try:body_bytes=image.read(accessor,256)
            except OSError:body_bytes=b''
            # Search a bounded, already linked accessor, then disassemble complete patterns.
            tls_sites=[]
            for off in range(max(0,len(body_bytes)-10)):
                raw=body_bytes[off:off+11]
                if raw[:2]==b'\x8b\x0d' and raw[6:7]==b'\xe8':tls_sites.append(accessor+off)
            tls=accept('addresses.tls_index',[target for at in tls_sites for target in rip_targets(image,at,11)],'linked_tls_accessor',tls_sites)
            list_row=source.data['checks']['context'][1]
            code1,mask1=signature(bytes.fromhex(list_row['bytes']),list_row['rva'],variable_fields=True)
            list_sites=[at for at in matches(image,code1,mask1,budget) if accessor<=at<accessor+256]
            headers=[]
            for at in list_sites:
                for ins in decoder().disasm(image.read(at,len(code1)),at):
                    for operand in ins.operands:
                        if operand.type==X86_OP_MEM and operand.mem.scale==8 and operand.mem.index and 0<=operand.mem.disp<=0x100:
                            headers.append(operand.mem.disp)
            header=unique_evidence('tls_header','indexed_tls_accessor',headers)
            if tls.state=='confirmed' and header.state=='confirmed' and len(list_sites)==1:
                # Mode slot index comes from the caller, not a profile/build constant.
                index=[ins.operands[1].imm for ins in body if ins.mnemonic=='mov' and len(ins.operands)==2 and
                       ins.operands[0].type==X86_OP_REG and ins.reg_name(ins.operands[0].reg)=='ecx' and ins.operands[1].type==X86_OP_IMM]
                if len(index)==1:
                    accept('context.mode_context',[header.candidates[0]+index[0]*8],'mode_slot_accessor',(site,list_sites[0]))
                offsets=[]
                for ins in body:
                    if len(ins.operands)==2 and ins.operands[1].type==X86_OP_MEM:
                        mem=ins.operands[1].mem
                        if not mem.index and mem.base!=X86_REG_RIP:offsets.append(mem.disp)
                    if ins.mnemonic=='cmp' and ins.operands[0].type==X86_OP_MEM:offsets.append(ins.operands[0].mem.disp)
                if len(offsets)==3:
                    for field,value in zip(('mode_bridge','mode_object','mode_value'),offsets):
                        accept('context.'+field,[value],'mode_native_dataflow',(site,))
                checks['context']=[{'rva':min(tls_sites),'bytes':image.read(min(tls_sites),11).hex()},
                                   {'rva':list_sites[0],'bytes':image.read(list_sites[0],len(code1)).hex()},
                                   {'rva':site,'bytes':image.read(site,len(code)).hex()}]
                for i,entry in enumerate(checks['context']):
                    evidence[f'checks.context.{i}']=unique_evidence(f'checks.context.{i}','linked_tls_accessor',[entry['rva']])
    row=source.data['checks']['game_state'][2]
    code,mask=signature(bytes.fromhex(row['bytes']),row['rva'],variable_fields=True)
    sites=matches(image,code,mask,budget)
    if len(sites)==1:
        at=sites[0];fields=[]
        for ins in decoder().disasm(image.read(at,len(code)),at):
            for op in ins.operands:
                if op.type==X86_OP_MEM and ins.reg_name(op.mem.base)=='rcx':fields.append((ins.mnemonic,op.mem.disp,op.mem.scale,bool(op.mem.index)))
        counts=[d for m,d,scale,indexed in fields if m=='cmp' and not indexed]
        arrays=[d for m,d,scale,indexed in fields if m=='mov' and indexed and scale==8]
        accept('players.count',counts,'player_index_bounds',(at,))
        accept('players.array',arrays,'player_index_array',(at,))
        checks['game_state_player']={'rva':at,'bytes':image.read(at,len(code)).hex()}
        evidence['checks.game_state.2']=unique_evidence('checks.game_state.2','player_accessor',[at])
        from war3_discovery_selection import locate_player_index
        local=locate_player_index(image,at,budget)
        evidence[local.dependency]=local
        if local.state=='confirmed':updates[local.dependency]=local.candidates[0]
        limits=[i.operands[1].imm+1 for i in decoder().disasm(image.read(at,len(code)),at)
                if i.mnemonic=='cmp' and len(i.operands)==2 and i.operands[0].type==X86_OP_REG and
                i.reg_name(i.operands[0].reg)=='edx' and i.operands[1].type==X86_OP_IMM and 0<i.operands[1].imm<64]
        accept('players.max_count',limits,'player_accessor_index_bound',(at,))
    return updates,evidence,checks


STATE_FRAGMENTS = (
    # Only the two bundled operation orders. Immediates below are placeholders,
    # not copied target answers; signature() masks them before matching.
    ("legacy", bytes.fromhex('48d1cb48b8000000000000000048c1c3014803d848b800000000000000004833d848b800000000000000004803d8')),
    ("modern_tail", bytes.fromhex('48c1c30148b800000000000000004833d848c1cb01')),
)


def _decoder_player_consumers(image, records, player_accessor, budget):
    """Distinguish a decoded state from a decoder with a folded member address.

    Require the decoded pointer as RCX of the independently located player
    accessor in two distinct functions. Frequency and the source constants are
    not evidence. A second qualifying decoder remains a conflict.
    """
    from bisect import bisect_right
    from capstone.x86 import X86_OP_REG
    from war3_discovery_abi import _register_family, VOLATILE
    image.function_size(player_accessor)
    functions=getattr(image,'_runtime_functions',{})
    starts=sorted(functions)
    witnesses={}
    for record in records:
        mode,values,root,producer,head,tail,raw=record
        if mode!='legacy':continue
        index=bisect_right(starts,tail)-1
        if index<0:continue
        start=starts[index];end=functions[start]
        if not start<=producer<tail<tail+len(raw)<end:continue
        extent=min(end-tail-len(raw),160)
        budget.check('正在核对游戏状态解码的实际消费者')
        try:suffix=image.read(tail+len(raw),extent)
        except OSError:continue
        aliases={'rbx'}
        for ins in decoder().disasm(suffix,tail+len(raw)):
            if ins.mnemonic in ('ret','int3','jmp'):break
            if ins.mnemonic=='call':
                if (ins.operands[0].type==X86_OP_IMM and
                        ins.operands[0].imm==player_accessor and 'rcx' in aliases):
                    identity=(mode,tuple(sorted(values.items())),root)
                    code=image.read(tail,ins.address+ins.size-tail)
                    witnesses.setdefault(identity,{})[start]=(tail,code.hex())
                    break
                aliases.difference_update(VOLATILE)
                continue
            ops=ins.operands
            copied=None
            if (ins.mnemonic=='mov' and len(ops)==2 and
                    ops[0].type==ops[1].type==X86_OP_REG and
                    ops[0].size==ops[1].size==8 and ins.reg_name(ops[1].reg) in aliases):
                copied=ins.reg_name(ops[0].reg)
            _,written=ins.regs_access()
            aliases.difference_update(_register_family(ins.reg_name(reg)) for reg in written)
            if copied:aliases.add(copied)
            if not aliases:break
    return {identity:tuple(rows.values()) for identity,rows in witnesses.items() if len(rows)>=2}


def locate_state_decoder(image, budget, *, player_accessor=None):
    records=[]
    for strategy,template in STATE_FRAGMENTS:
        code,mask=signature(template,variable_immediates=True)
        sites=matches(image,code,mask,budget)
        for at in sites:
            raw=image.read(at,len(code));decoded=decode_state_fragment(raw,at)
            if decoded is None:continue
            mode,values=decoded
            # The nearby producer must load the same RBX value before this tail.
            # Never traverse across an unreadable hole or invent a missing constant.
            try:prefix=image.read(max(4096,at-512),min(512,at-4096))
            except OSError:continue
            start=max(4096,at-512)
            offset=prefix.rfind(b'\x48\x8b\x1d')
            if offset<0:continue
            producer=start+offset
            length=23 if mode=='modern_tail' else 7
            try:head=image.read(producer,length)
            except OSError:continue
            root=rip_targets(image,producer,7)
            if len(root)!=1:continue
            if mode=='modern_tail':
                instructions=list(decoder().disasm(head,producer))
                if len(instructions)<3 or instructions[1].mnemonic!='movabs' or instructions[2].mnemonic!='add':continue
                if instructions[1].op_str.split(',')[0]!='rcx' or instructions[2].op_str!='rbx, rcx':continue
                values=dict(values,add1=instructions[1].operands[1].imm&((1<<64)-1),add2=0)
            records.append((mode,values,root[0],producer,head,at,raw))
    identities={(mode,tuple(sorted(values.items())),root) for mode,values,root,*_ in records}
    consumer_anchors=()
    if len(identities)>1 and player_accessor is not None:
        consumers=_decoder_player_consumers(image,records,player_accessor,budget)
        if len(consumers)==1:
            identity,consumer_anchors=next(iter(consumers.items()))
            records=[r for r in records if (r[0],tuple(sorted(r[1].items())),r[2])==identity]
            identities={identity}
    if len(identities)!=1:
        return {},{'decoder':DiscoveryEvidence('decoder','ambiguous' if records else 'unresolved','known_decoder_dataflow')},None
    # Multiple equivalent instruction sites prove one semantic value; retain the
    # lowest site only as an exact-byte witness, not as an address-selection guess.
    mode,values,root,producer,head,tail,raw=min(records,key=lambda r:(r[3],r[5]))
    updates={'addresses.game_state':root, **{'decoder.'+k:v for k,v in values.items()}}
    strategy='legacy_layout_24332_v1' if mode=='modern_tail' else 'legacy_layout_24323_v1'
    updates['modules.legacy_layout.implementation']=strategy
    evidence={name:DiscoveryEvidence(name,'confirmed','known_decoder_dataflow',(value,),tuple(r[3] for r in records))
              for name,value in updates.items()}
    evidence['decoder']=DiscoveryEvidence('decoder','confirmed','known_decoder_dataflow',anchors=tuple(r[5] for r in records))
    if consumer_anchors:
        evidence['decoder.player_consumers']=DiscoveryEvidence('decoder.player_consumers','confirmed',
            'typed_player_accessor_decoder_consumers',anchors=consumer_anchors)
    checks=[{'rva':producer,'bytes':head.hex()},{'rva':tail,'bytes':raw.hex()}]
    for index,row in enumerate(checks):evidence[f'checks.game_state.{index}']=unique_evidence(f'checks.game_state.{index}','equivalent_state_witnesses',[row['rva']])
    return updates,evidence,checks


def native_abi_evidence(image,entries,budget,*,real_forwarders=None):
    proof=_sqrt_native_abi_evidence(image,entries,budget)
    if proof.state=='confirmed':return proof
    # A protected mathematical native must not be the only route to ABI
    # evidence. The fallback still examines actual typed machine bodies.
    from war3_discovery_abi import typed_native_abi_evidence
    return typed_native_abi_evidence(image,entries,budget,real_forwarders=real_forwarders)


def _sqrt_native_abi_evidence(image,entries,budget):
    """Inspect typed native bodies independently of registration signatures.

    This establishes the shared primitive marshalling convention, not the
    business semantics of every native. Per-operation signature checks remain.
    """
    from capstone.x86 import X86_OP_REG
    from war3_discovery_abi import _body,_real_pointer,_return_epilogue,_unit_input_to_call
    witnesses=[]
    sqrt=entries.get('SquareRoot')
    if sqrt is None or sqrt.signature!='(R)R':
        return DiscoveryEvidence('native_abi','unresolved','missing_real_abi_sample')
    parsed=_body(image,sqrt,budget)
    if parsed is None:return DiscoveryEvidence('native_abi','unresolved','real_abi_body_unconfirmed')
    rva,raw,body=parsed
    # Preserve the input pointer in RBX, dereference it for scalar float comparison,
    # and return the float's bits in EAX. Reject XMM-only or by-value conventions.
    if not (_real_pointer(body,'rcx') and
            any(i.mnemonic=='mov' and len(i.operands)==2 and i.operands[0].type==X86_OP_REG and
                i.reg_name(i.operands[0].reg)=='eax' and i.operands[1].type==X86_OP_MEM and
                i.operands[1].size==4 and i.reg_name(i.operands[1].mem.base)=='rsp' and
                _return_epilogue(body,index) for index,i in enumerate(body))):
        return DiscoveryEvidence('native_abi','unresolved','real_machine_convention_differs')
    witnesses.append((rva,raw.hex()))
    bool_sites=[]
    for name,entry in entries.items():
        if not entry.signature.endswith(')B'):continue
        budget.check('正在核对原生调用约定')
        parsed=_body(image,entry,budget)
        if parsed is None:continue
        at,boolean_raw,insns=parsed
        for index, ins in enumerate(insns):
            if not ins.mnemonic.startswith('set') or ins.op_str!='al':continue
            if _return_epilogue(insns,index):
                bool_sites.append((at,boolean_raw.hex()))
                break
    unit=entries.get('GetUnitTypeId')
    if not bool_sites or unit is None or unit.signature!='(Hunit;)I':
        return DiscoveryEvidence('native_abi','unresolved','boolean_or_handle_convention_unconfirmed')
    parsed=_body(image,unit,budget)
    if parsed is None:return DiscoveryEvidence('native_abi','unresolved','unit_input_body_unconfirmed')
    at,unit_raw,insns=parsed
    call=next((i for i in insns if i.mnemonic=='call'),None)
    if call is None or call.operands[0].type!=X86_OP_IMM or not image.executable(call.operands[0].imm):
        return DiscoveryEvidence('native_abi','unresolved','unit_input_call_unconfirmed')
    if not _unit_input_to_call(insns,call):
        return DiscoveryEvidence('native_abi','unresolved','unit_input_clobbered')
    if len({rva,bool_sites[0][0],at})!=3:
        return DiscoveryEvidence('native_abi','unresolved','primitive_function_aliases')
    witnesses.append(bool_sites[0]);witnesses.append((at,unit_raw.hex()))
    return DiscoveryEvidence('native_abi','confirmed','typed_native_machine_conventions',anchors=tuple(witnesses),
                             detail='Win64 scalar handle input; real pointer argument and EAX-bit return; Boolean AL return. Individual native signatures remain mandatory.')


def locate_call_targets(image,references,budget):
    """Correlate two distinct known callers when the callee body is protected."""
    updates,evidence={},{}
    for path,ref in references.items():
        sites=ref.get('call_sites',())
        if not sites:continue
        votes={};witnesses={}
        for index,site in enumerate(sites):
            found,size=locate_reference(image,site,budget)
            # A nonunique call-site shape is not a vote, even if one target is near the old RVA.
            if len(found)!=1:continue
            instructions=list(decoder().disasm(image.read(found[0],size),found[0]))
            if not instructions or instructions[0].mnemonic!='call' or instructions[0].operands[0].type!=X86_OP_IMM:continue
            target=instructions[0].operands[0].imm
            if not image.executable(target):continue
            votes.setdefault(target,set()).add(index)
            witnesses.setdefault(target,[]).append(found[0])
        candidates=[target for target,origins in votes.items() if len(origins)>=2]
        proof=unique_evidence(path,'two_independent_native_call_sites',candidates,
                              tuple(at for target in candidates for at in witnesses[target]))
        evidence[path]=proof
        if proof.state=='confirmed':updates[path]=proof.candidates[0]
    return updates,evidence


def native_attack_layout(image,entries,budget):
    """Infer the unit attack member from the registered base-cooldown getter.

    The returned native value remains BASE cooldown. It is never substituted
    for the effective attack interval or actual attack speed.
    """
    from capstone.x86 import X86_OP_REG
    from war3_discovery_abi import _body,_register_family,_return_epilogue,VOLATILE
    entry=entries.get('BlzGetUnitAttackCooldown')
    if entry is None or entry.signature!='(Hunit;I)R':return {},{}
    parsed=_body(image,entry,budget)
    if parsed is None:return {},{}
    rva,raw,instructions=parsed
    first=next((ins for ins in instructions if ins.mnemonic=='call'),None)
    if first is None:return {},{}
    # This getter may reject weapon index > 1 before resolving the unit.
    # The scalar unit argument must still reach the first call unchanged.
    for ins in instructions:
        if ins.address>=first.address:break
        if ins.mnemonic not in ('mov','push','sub','nop','cmp','ja','jg'):return {},{}
        _,written=ins.regs_access()
        if any(_register_family(ins.reg_name(reg))=='rcx' for reg in written):return {},{}
        if (ins.mnemonic=='mov' and ins.operands[0].type==X86_OP_MEM and
            ins.reg_name(ins.operands[0].mem.base) not in ('rsp','rbp')):return {},{}
        if ins.mnemonic=='sub' and ins.op_str.split(',')[0]!='rsp':return {},{}
        if ins.mnemonic=='cmp' and ins.op_str not in ('edx, 1','r8d, 1'):return {},{}
    calls=[];unit_aliases=set();components={};returned_pointers=set();return_verified=False;offsets=[]
    for index,ins in enumerate(instructions):
        ops=ins.operands
        if ins.mnemonic=='call':
            if len(ops)!=1 or ops[0].type!=X86_OP_IMM or not image.executable(ops[0].imm):return {},{}
            calls.append(ops[0].imm)
            used=components.get('rcx')
            unit_aliases.difference_update(VOLATILE)
            components={reg:member for reg,member in components.items() if reg not in VOLATILE}
            returned_pointers={'rax'} if used is not None else set()
            if used is not None:offsets.append(used)
            if len(calls)==1:unit_aliases.add('rax')
            continue
        loaded_component=copied_unit=copied_component=copied_return=None
        if (len(ops)==2 and ins.mnemonic=='mov' and ops[0].type==X86_OP_REG and ops[0].size==8 and
            ops[1].type==X86_OP_MEM and ops[1].size==8 and
            ins.reg_name(ops[1].mem.base) in unit_aliases and not ops[1].mem.index):
            loaded_component=(ins.reg_name(ops[0].reg),ops[1].mem.disp)
        if len(ops)==2 and ins.mnemonic=='mov' and ops[0].type==ops[1].type==X86_OP_REG and ops[0].size==ops[1].size==8:
            dst,src=ins.reg_name(ops[0].reg),ins.reg_name(ops[1].reg)
            if src in unit_aliases:copied_unit=dst
            if src in components:copied_component=(dst,components[src])
            if src in returned_pointers:copied_return=dst
        if (len(ops)==2 and ins.mnemonic=='mov' and
            ops[0].type==X86_OP_REG and ins.reg_name(ops[0].reg)=='eax' and
            ops[1].type==X86_OP_MEM and ops[1].size==4 and
            ins.reg_name(ops[1].mem.base) in returned_pointers and not ops[1].mem.index and not ops[1].mem.disp and
            _return_epilogue(instructions,index)):
            return_verified=True
        _,written=ins.regs_access()
        changed={_register_family(ins.reg_name(reg)) for reg in written}
        unit_aliases.difference_update(changed)
        returned_pointers.difference_update(changed)
        components={reg:member for reg,member in components.items() if reg not in changed}
        if copied_unit is not None:unit_aliases.add(copied_unit)
        if copied_component is not None:components[copied_component[0]]=copied_component[1]
        if loaded_component is not None:components[loaded_component[0]]=loaded_component[1]
        if copied_return is not None:returned_pointers.add(copied_return)
    offsets=[value for value in offsets if 0<value<0x10000 and value%8==0]
    proof=unique_evidence('bridge_layout.unit_attack','native_base_cooldown_component_access',offsets,
                         ((rva,raw.hex()),))
    if len(calls)<2 or not return_verified:return {},{}
    # This identifies the member consumed by the native. It is not yet proof
    # that this pointer is the bridge's attack component; validate the Aatk
    # registry identity before replacing any executable configuration member.
    from dataclasses import replace
    return {},{proof.dependency:replace(proof,state='candidate' if proof.state=='confirmed' else proof.state)}
