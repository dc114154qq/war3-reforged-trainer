"""Observe native machine ABI across readable typed bodies, without game calls."""
import re
from capstone.x86 import X86_OP_MEM,X86_OP_REG,X86_OP_IMM
from war3_profile_discovery import DiscoveryEvidence

BANNED=frozenset(('int','int1','int3','iret','iretq','iretd','retf','syscall','sysret','in','out',
                 'insb','outsb','insd','outsd','hlt','cli','sti','std','xlatb','fbld'))
VOLATILE=frozenset(('rax','rcx','rdx','r8','r9','r10','r11'))


def _register_family(name):
    """A write to any part of a GPR invalidates its pointer provenance."""
    for family,parts in (
        ('rax',('rax','eax','ax','al','ah')), ('rbx',('rbx','ebx','bx','bl','bh')),
        ('rcx',('rcx','ecx','cx','cl','ch')), ('rdx',('rdx','edx','dx','dl','dh')),
        ('rsi',('rsi','esi','si','sil')), ('rdi',('rdi','edi','di','dil')),
        ('rbp',('rbp','ebp','bp','bpl')), ('rsp',('rsp','esp','sp','spl')),
    ):
        if name in parts:return family
    match=re.fullmatch(r'(r(?:[89]|1[0-5]))[dwb]?',name)
    return match[1] if match else name


def _body(image,entry,budget):
    from capstone import CS_GRP_JUMP
    from war3_discovery_locators import decoder
    at=entry.handler-image.base;size=image.function_size(at)
    if size is None or not 12<=size<=768:return None
    budget.check('正在交叉核对原生调用约定')
    try:raw=image.read(at,size)
    except OSError:return None
    insns=list(decoder().disasm(raw,at))
    if (not insns or sum(i.size for i in insns)!=size or
        insns[0].mnemonic not in ('push','mov','sub','test','cmp','xor') or
        any(i.mnemonic in BANNED for i in insns)):return None
    boundaries={i.address for i in insns}
    if any(i.group(CS_GRP_JUMP) and
           (not i.operands or i.operands[0].type!=X86_OP_IMM or i.operands[0].imm not in boundaries)
           for i in insns):return None
    return at,raw,insns


def _parameters(signature):
    match=re.fullmatch(r'\((.*?)\)(?:[VIBRSC]|H\w+;)',signature)
    if match is None:return ()
    parts=re.findall(r'H\w+;|[IBRSC]',match[1])
    return tuple(parts) if ''.join(parts)==match[1] else ()


def _unit_input_to_call(insns,call):
    """A scalar unit argument reaches the first call through a stack prologue."""
    for ins in insns:
        if ins.address>=call.address:break
        if ins.mnemonic not in ('mov','push','sub','nop'):return False
        _,written=ins.regs_access()
        if any(_register_family(ins.reg_name(reg))=='rcx' for reg in written):return False
        if (ins.mnemonic=='mov' and ins.operands and ins.operands[0].type==X86_OP_MEM and
            ins.reg_name(ins.operands[0].mem.base) not in ('rsp','rbp')):return False
        if ins.mnemonic=='sub' and (not ins.operands or ins.op_str.split(',')[0]!='rsp'):return False
    return True


def _real_pointer(insns,register):
    aliases={register};observed=[]
    for ins in insns:
        ops=ins.operands
        if ins.mnemonic=='call':aliases.difference_update(VOLATILE);continue
        if (ins.mnemonic in ('movss','comiss','ucomiss') and len(ops)==2 and
            ops[1].type==X86_OP_MEM and ops[1].size==4 and not ops[1].mem.index and
            ops[1].mem.disp==0 and ins.reg_name(ops[1].mem.base) in aliases):
            observed.append(ins.address)
        copied=None
        if (ins.mnemonic=='mov' and len(ops)==2 and ops[0].type==X86_OP_REG and
            ops[0].size==8 and ops[1].type==X86_OP_REG and
            ins.reg_name(ops[1].reg) in aliases):
            copied=ins.reg_name(ops[0].reg)
        # Include implicit writes and both outputs of xchg. Checking only
        # operand zero misses r8d/sil clobbers and can turn an integer into a
        # falsely attested real-pointer argument.
        _,written=ins.regs_access()
        aliases.difference_update(_register_family(ins.reg_name(reg)) for reg in written)
        if copied is not None:aliases.add(copied)
    return bool(observed)


def _return_epilogue(insns,index):
    # Require a direct, unchanged AL/EAX result at a real return; not merely a
    # boolean comparison or float temporary anywhere in the function.
    by_address={ins.address:i for i,ins in enumerate(insns)}
    cursor=index+1;seen=set()
    for _ in range(16):
        if cursor>=len(insns) or cursor in seen:return False
        seen.add(cursor);ins=insns[cursor]
        if ins.mnemonic=='ret':return True
        if ins.mnemonic=='jmp':
            if len(ins.operands)!=1 or ins.operands[0].type!=X86_OP_IMM:return False
            target=by_address.get(ins.operands[0].imm)
            if target is None:return False
            cursor=target;continue
        if ins.mnemonic not in ('mov','add','pop','nop'):return False
        _,written=ins.regs_access()
        if any(_register_family(ins.reg_name(reg))=='rax' for reg in written):return False
        cursor+=1
    return False


def typed_native_abi_evidence(image,entries,budget,*,real_forwarders=None):
    pointer_witnesses=[];real_returns=[];boolean_returns=[];handle_inputs=[]
    registers=('rcx','rdx','r8','r9')
    for name,entry in entries.items():
        parameters=_parameters(entry.signature)
        has_real='R' in parameters[:4];result=entry.signature.split(')')[-1]
        handle=bool(parameters and parameters[0]=='Hunit;')
        if not has_real and result not in ('R','B') and not handle:continue
        parsed=_body(image,entry,budget)
        if parsed is None:continue
        at,raw,insns=parsed;witness=(at,raw.hex())
        if has_real and any(_real_pointer(insns,registers[i]) for i,p in enumerate(parameters[:4]) if p=='R'):
            pointer_witnesses.append((name,witness))
        if result=='R':
            for index,ins in enumerate(insns):
                if (ins.mnemonic=='mov' and len(ins.operands)==2 and ins.operands[0].type==X86_OP_REG and
                    ins.reg_name(ins.operands[0].reg)=='eax' and ins.operands[1].type==X86_OP_MEM and
                    ins.operands[1].size==4 and not ins.operands[1].mem.index and
                    ins.reg_name(ins.operands[1].mem.base) in ('rax','rsp','rbx','rcx') and
                    _return_epilogue(insns,index)):
                    real_returns.append((name,witness));break
        if result=='B':
            if any(ins.mnemonic.startswith('set') and ins.op_str=='al' and
                   _return_epilogue(insns,index) for index,ins in enumerate(insns)):
                boolean_returns.append((name,witness))
        if handle:
            call=next((i for i in insns if i.mnemonic=='call'),None)
            if call is not None and call.operands[0].type==X86_OP_IMM and image.executable(call.operands[0].imm):
                if _unit_input_to_call(insns,call):
                    handle_inputs.append((name,witness,call.operands[0].imm))
    from war3_discovery_call_abi import reviewed_real_pointer_callers
    forwarded=reviewed_real_pointer_callers(image,entries,budget,recipes=real_forwarders)
    pointer_witnesses.extend((name,witness) for name,witness,closure in forwarded)
    # One dereference may be an incidental handle pointer. Require two
    # distinct typed real-argument consumers and independent return samples.
    missing=[]
    if len({w[1][0] for w in pointer_witnesses})<2:missing.append('real pointer arguments')
    if not real_returns:missing.append('real EAX-bit returns')
    if not boolean_returns:missing.append('boolean AL returns')
    if len({w[1][0] for w in handle_inputs})<2:missing.append('scalar unit handle inputs')
    if missing:return DiscoveryEvidence('native_abi','unresolved','readable_native_conventions_incomplete',
                                        detail='Missing: '+', '.join(missing))
    def distinct(rows):
        result=[];seen=set()
        for name,witness in rows:
            if witness[0] not in seen:
                seen.add(witness[0]);result.append((name,witness))
            if len(result)==2:break
        return result
    selected=(distinct(pointer_witnesses)+distinct(real_returns)+distinct(boolean_returns)+
              distinct([(n,w) for n,w,_ in handle_inputs]))
    selected_sites={w[0] for n,w in selected}
    witnesses=tuple(dict.fromkeys([w for n,w in selected]+[
        anchor for name,witness,closure in forwarded if witness[0] in selected_sites for anchor in closure]))
    return DiscoveryEvidence('native_abi','confirmed','cross_checked_typed_native_machine_conventions',
                             anchors=witnesses,detail='Observed real pointer arguments, EAX-bit real returns, AL booleans, scalar unit inputs: '+', '.join(n for n,_ in selected))
