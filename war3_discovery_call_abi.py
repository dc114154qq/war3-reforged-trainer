"""Read-only ABI witnesses across fully reviewed native caller/callee bodies.

Some native wrappers forward real pointers to a deterministic software-float
helper. A typed name alone is not proof: every complete body, direct call,
register/stack transfer and actual four-byte dereference is checked here.
"""
from collections import deque
import json
from capstone import CS_GRP_JUMP
from capstone.x86 import X86_OP_REG,X86_OP_MEM,X86_OP_IMM
from war3_discovery_abi import _body,_register_family,VOLATILE

REVIEWED_REAL_CALLERS=frozenset(('GroupPointOrder','GroupPointOrderById'))


def _match_body(image,entry,expected,budget):
    from war3_discovery_locators import decoder,signature
    raw=bytes.fromhex(expected)
    if not 24<=len(raw)<=768:raise ValueError('Reviewed ABI body extent exceeds bound')
    source=list(decoder().disasm(raw,0))
    if sum(i.size for i in source)!=len(raw):raise ValueError('Reviewed ABI body is incomplete')
    boundaries={i.address for i in source}
    if any(i.group(CS_GRP_JUMP) and (not i.operands or i.operands[0].type!=X86_OP_IMM or
            i.operands[0].imm not in boundaries) for i in source):
        raise ValueError('Reviewed ABI branch leaves its complete function')
    parsed=_body(image,entry,budget)
    if parsed is None:return None
    at,observed,actual=parsed
    if len(observed)!=len(raw) or len(actual)!=len(source):return None
    if any(ins.mnemonic=='call' and ins.operands[0].type==X86_OP_IMM and
           not image.executable(ins.operands[0].imm) for ins in actual):return None
    binary,mask=signature(raw,variable_fields=True)
    if any(flag and a!=b for a,b,flag in zip(binary,observed,mask)):return None
    if any(old.group(CS_GRP_JUMP) and new.operands[0].imm-at!=old.operands[0].imm
           for old,new in zip(source,actual)):return None
    return parsed


def _alias_flow(insns,registers,stack,budget,*,stop_call=None):
    """Bounded CFG walk; partial writes and calls invalidate pointer provenance.

    Stack addresses are relative to function entry RSP. The callee's first
    stack argument is entry+0x28; at the caller it is call-RSP+0x20.
    """
    by_address={ins.address:i for i,ins in enumerate(insns)}
    pending=deque([(0,dict(registers),dict(stack),0)])
    seen=set();calls=[];reads=set()
    while pending:
        budget.check('正在核对原生参数的寄存器与栈传递')
        index,aliases,slots,delta=pending.popleft()
        key=(index,tuple(sorted(aliases.items())),tuple(sorted(slots.items())),delta)
        if key in seen:continue
        seen.add(key)
        if len(seen)>512:return None
        if not 0<=index<len(insns):return None
        ins=insns[index];ops=ins.operands
        if ins.mnemonic=='ret':continue
        if ins.mnemonic=='call':
            if ins.address==stop_call:
                calls.append((dict(aliases),dict(slots),delta));continue
            aliases={r:v for r,v in aliases.items() if r not in VOLATILE}
            pending.append((index+1,aliases,slots,delta));continue
        if ins.group(CS_GRP_JUMP):
            if len(ops)!=1 or ops[0].type!=X86_OP_IMM or ops[0].imm not in by_address:return None
            pending.append((by_address[ops[0].imm],dict(aliases),dict(slots),delta))
            if ins.mnemonic!='jmp':pending.append((index+1,aliases,slots,delta))
            continue
        copied=None;spill=None
        if len(ops)==2 and ins.mnemonic=='mov':
            if ops[1].type==X86_OP_MEM and ops[1].size==4 and not ops[1].mem.index and ops[1].mem.disp==0:
                origin=aliases.get(_register_family(ins.reg_name(ops[1].mem.base)))
                if origin is not None:reads.add(origin)
            if ops[0].type==X86_OP_REG and ops[0].size==8:
                dest=_register_family(ins.reg_name(ops[0].reg));origin=None
                if ops[1].type==X86_OP_REG and ops[1].size==8:
                    origin=aliases.get(_register_family(ins.reg_name(ops[1].reg)))
                elif (ops[1].type==X86_OP_MEM and ops[1].size==8 and not ops[1].mem.index and
                      ins.reg_name(ops[1].mem.base)=='rsp'):
                    origin=slots.get(delta+ops[1].mem.disp)
                if origin is not None:copied=(dest,origin)
            if ops[0].type==X86_OP_MEM and ins.reg_name(ops[0].mem.base)=='rsp' and not ops[0].mem.index:
                address=delta+ops[0].mem.disp;width=ops[0].size
                origin=aliases.get(_register_family(ins.reg_name(ops[1].reg))) if ops[1].type==X86_OP_REG and ops[1].size==8 and width==8 else None
                spill=(address,width,origin)
        _,written=ins.regs_access()
        changed={_register_family(ins.reg_name(reg)) for reg in written}
        if 'rsp' in changed:
            if ins.mnemonic=='push':
                delta-=8;slots.pop(delta,None)
            elif ins.mnemonic=='pop':
                if len(ops)!=1 or ops[0].type!=X86_OP_REG:return None
                origin=slots.get(delta)
                if origin is not None:copied=(_register_family(ins.reg_name(ops[0].reg)),origin)
                delta+=8
            elif (ins.mnemonic in ('sub','add') and len(ops)==2 and ops[0].type==X86_OP_REG and
                  ins.reg_name(ops[0].reg)=='rsp' and ops[1].type==X86_OP_IMM):
                delta+=ops[1].imm*(1 if ins.mnemonic=='add' else -1)
            else:
                # Complex return frame restoration can follow all witnesses;
                # it is not treated as another argument-transfer path.
                continue
            if not -0x1000<=delta<=0:return None
        aliases={r:v for r,v in aliases.items() if r not in changed}
        if copied is not None:aliases[copied[0]]=copied[1]
        if spill is not None:
            address,width,origin=spill
            for at in list(slots):
                if at<address+width and address<at+8:slots.pop(at)
            if origin is not None:slots[address]=origin
        pending.append((index+1,aliases,slots,delta))
    return calls,reads


def reviewed_real_pointer_callers(image,entries,budget,*,recipes=None):
    from types import SimpleNamespace
    from war3_discovery_abi import _parameters
    if recipes is None:
        from war3_game_profile import PROFILE_ROOT
        from war3_profile_discovery import RECIPE_VERSION
        book=json.loads((PROFILE_ROOT/'discovery/semantics.json').read_text(encoding='utf-8'))
        if book['recipe_version']!=RECIPE_VERSION:raise ValueError('ABI witness recipe version differs')
        recipes=book.get('native_abi_forwarders',())
    if not isinstance(recipes,(list,tuple)) or len(recipes)>8:raise ValueError('ABI forwarder list exceeds bound')
    result=[];seen=set()
    for row in recipes:
        if set(row)!={'native','signature','code','call_instruction','helper_code','real_parameters'}:
            raise ValueError('Invalid reviewed ABI forwarding recipe')
        name=row['native']
        if name not in REVIEWED_REAL_CALLERS or name in seen:raise ValueError('Unreviewed or duplicate ABI caller')
        seen.add(name);entry=entries.get(name)
        if entry is None or entry.signature!=row['signature']:continue
        parameters=_parameters(entry.signature)
        real=row['real_parameters']
        if (not isinstance(real,list) or len(real)!=2 or len(set(real))!=2 or
                any(type(index) is not int or not 0<=index<min(4,len(parameters)) or parameters[index]!='R' for index in real)):
            raise ValueError('ABI forwarding recipe must select two typed real arguments')
        caller=_match_body(image,entry,row['code'],budget)
        if caller is None:continue
        at,raw,insns=caller;index=row['call_instruction']
        if type(index) is not int or not 0<=index<len(insns):raise ValueError('Invalid reviewed ABI call selector')
        call=insns[index]
        if call.mnemonic!='call' or len(call.operands)!=1 or call.operands[0].type!=X86_OP_IMM:
            raise ValueError('ABI call selector is not a direct call')
        helper_at=call.operands[0].imm
        if not image.executable(helper_at):continue
        helper=_match_body(image,SimpleNamespace(handler=image.base+helper_at),row['helper_code'],budget)
        if helper is None:continue
        initial={('rcx','rdx','r8','r9')[i]:i for i in real}
        flow=_alias_flow(insns,initial,{},budget,stop_call=call.address)
        if flow is None or not flow[0]:continue
        observed=set();valid=True
        for aliases,slots,delta in flow[0]:
            callee_regs={r:v for r,v in aliases.items() if r in ('rcx','rdx','r8','r9')}
            callee_stack={address-delta+8:origin for address,origin in slots.items()
                          if delta+0x20<=address<delta+0x60}
            nested=_alias_flow(helper[2],callee_regs,callee_stack,budget)
            if nested is None or not set(real)<=nested[1]:valid=False;break
            observed.update(nested[1])
        if valid and set(real)<=observed:
            # The two native bodies are independent ABI callers; a shared
            # helper is retained as a required closure, never counted twice.
            result.append((name,(at,raw.hex()),((helper_at,helper[1].hex()),)))
    return result
