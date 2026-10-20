"""Prove bounded decoder paths from a RIP load to the typed player accessor.

The interpreter follows real branch targets, including overlapping instruction
streams. Unsupported instructions, unknown calls, holes and unbounded paths
reject that witness. No target profile values or frequency votes are inputs.
"""
from __future__ import annotations
from bisect import bisect_right
import re
from war3_profile_discovery import DiscoveryEvidence,DiscoveryError

MASK=(1<<64)-1
VOLATILE=('rax','rcx','rdx','r8','r9','r10','r11')


def _family(name):
    from war3_discovery_abi import _register_family
    return _register_family(name)


def _expr(value):return isinstance(value,tuple) and len(value)==3 and value[0]=='state'


def _rotate(value,n,left=True,width=64):
    n%=width;mask=(1<<width)-1;value&=mask
    if not n:return value
    return (((value<<n)|(value>>(width-n))) if left else ((value>>n)|(value<<(width-n))))&mask


def _normal(value):
    if not _expr(value):return None
    ops=list(value[2]);add2=0
    if ops and ops[-1][0]=='add':add2=ops.pop()[1]
    names=[k for k,v in ops]
    if names==['rol','xor','rol']:
        rol,key,last=(v for k,v in ops);ror=64-last
    elif names==['xor','ror','rol']:
        key,ror,rol=(v for k,v in ops);key=_rotate(key,rol)
    else:return None
    if not 0<rol<64 or not 0<ror<64:return None
    return value[1],(0,rol,key,ror,add2)


def _flags(result,width,*,cf=None,of=None):
    if result is None:return dict(cf=cf,of=of,zf=None,sf=None,pf=None)
    mask=(1<<width)-1;result&=mask
    return dict(cf=cf,of=of,zf=result==0,sf=bool(result&(1<<(width-1))),pf=(result&255).bit_count()%2==0)


def _condition(name,f):
    def inverse(x):return None if x is None else not x
    def both(a,b):return False if a is False or b is False else True if a is True and b is True else None
    def either(a,b):return True if a is True or b is True else False if a is False and b is False else None
    equal=None if f['sf'] is None or f['of'] is None else f['sf']==f['of']
    return {'je':f['zf'],'jz':f['zf'],'jne':inverse(f['zf']),'jnz':inverse(f['zf']),
        'jb':f['cf'],'jc':f['cf'],'jae':inverse(f['cf']),'jnc':inverse(f['cf']),
        'ja':both(inverse(f['cf']),inverse(f['zf'])),'jbe':either(f['cf'],f['zf']),
        'jo':f['of'],'jno':inverse(f['of']),'js':f['sf'],'jns':inverse(f['sf']),
        'jp':f['pf'],'jnp':inverse(f['pf']),'jg':both(inverse(f['zf']),equal),
        'jle':either(f['zf'],inverse(equal)),'jge':equal,'jl':inverse(equal)}.get(name)


def _trace(image,producer,end,accessor,disassembler,budget,*,start=None):
    from capstone.x86 import X86_OP_REG,X86_OP_IMM,X86_OP_MEM
    start=producer if start is None else start
    cache={};visited=set();hits=[];steps=0;pending=[(start,{},_flags(None,64),(),frozenset())]
    def instruction(pc):
        if pc not in cache:
            if not start<=pc<end:raise ValueError('flow leaves containing function')
            raw=image.read(pc,min(15,end-pc));ins=next(disassembler.disasm(raw,pc,count=1),None)
            if ins is None:raise ValueError('undecodable reached instruction')
            cache[pc]=ins
        return cache[pc]
    while pending:
        pc,registers,flags,stack,ancestry=pending.pop();path_tokens=set(ancestry)
        while True:
            steps+=1
            if steps%32==0:budget.check('正在证明状态解码到玩家访问器的控制流')
            if steps>2048 or len(pending)>64:return None,'flow_budget'
            token=(pc,tuple(sorted(registers.items())),tuple(sorted(flags.items())),stack)
            if token in path_tokens:return None,'cyclic_path'
            if token in visited:break
            path_tokens.add(token)
            visited.add(token)
            try:ins=instruction(pc)
            except DiscoveryError:raise
            except (OSError,ValueError):return None,'unreadable_or_invalid_path'
            next_pc=pc+ins.size;ops=ins.operands;name=ins.mnemonic
            def value(op):
                if op.type==X86_OP_IMM:return op.imm&((1<<(op.size*8))-1)
                if op.type!=X86_OP_REG:return None
                item=registers.get(_family(ins.reg_name(op.reg)))
                if isinstance(item,int):
                    if ins.reg_name(op.reg) in ('ah','bh','ch','dh'):return (item>>8)&255
                    return item&((1<<(op.size*8))-1)
                return item if op.size==8 else None
            def store(op,item):
                if op.type!=X86_OP_REG:raise ValueError('non-register destination')
                key=_family(ins.reg_name(op.reg));old=registers.get(key)
                if op.size in (4,8):registers[key]=item if op.size==8 or item is None else item&0xffffffff
                elif isinstance(item,int) and isinstance(old,int):
                    shift=8 if ins.reg_name(op.reg) in ('ah','bh','ch','dh') else 0
                    mask=((1<<(op.size*8))-1)<<shift;registers[key]=(old&~mask)|((item<<shift)&mask)
                else:registers[key]=None
            try:
                if name=='ret':break
                if name=='call':
                    if ops[0].type!=X86_OP_IMM:return None,'indirect_call'
                    if ops[0].imm!=accessor:return None,'unreviewed_call'
                    normalized=_normal(registers.get('rcx'))
                    if normalized is None:return None,'unproved_accessor_argument'
                    hits.append((normalized,pc+ins.size));break
                if name=='jmp':
                    if ops[0].type!=X86_OP_IMM:return None,'indirect_jump'
                    pc=ops[0].imm;continue
                if name.startswith('j'):
                    if ops[0].type!=X86_OP_IMM:return None,'indirect_branch'
                    choice=_condition(name,flags);target=ops[0].imm
                    if choice is None:
                        following=instruction(next_pc)
                        pairs={'je':'jne','jne':'je','ja':'jbe','jbe':'ja','jb':'jae','jae':'jb',
                               'jo':'jno','jno':'jo','js':'jns','jns':'js','jp':'jnp','jnp':'jp'}
                        if (pairs.get(name)==following.mnemonic and following.operands[0].type==X86_OP_IMM and
                                following.operands[0].imm==target):pc=target;continue
                        branch_flags=dict(flags);fall_flags=dict(flags)
                        if name in ('je','jne'):
                            branch_flags['zf']=name=='je';fall_flags['zf']=name!='je'
                        pending.append((target,dict(registers),branch_flags,stack,frozenset(path_tokens)))
                        flags=fall_flags;pc=next_pc;continue
                    pc=target if choice else next_pc;continue
                if name=='nop':pass
                elif name in ('clc','stc','cmc'):
                    flags['cf']=name=='stc' if name!='cmc' else None if flags['cf'] is None else not flags['cf']
                elif name=='push':stack+= (value(ops[0]),)
                elif name=='pop':
                    store(ops[0],stack[-1] if stack else None);stack=stack[:-1]
                elif name=='xchg' and len(ops)==2 and ops[0].type==ops[1].type==X86_OP_REG:
                    left,right=value(ops[0]),value(ops[1]);store(ops[0],right);store(ops[1],left)
                elif name in ('mov','movabs','movzx'):
                    if ops[0].type==X86_OP_MEM:
                        mem=ops[0].mem
                        if (name!='mov' or ins.reg_name(mem.base)!='rsp' or mem.index or
                                not 0<=mem.disp<512 or mem.disp%8 or ops[0].size!=8):return None,'unreviewed_memory_write'
                        if mem.disp//8<len(stack):
                            values=list(stack);values[-1-mem.disp//8]=value(ops[1]);stack=tuple(values)
                        elif mem.disp==0:return None,'unreviewed_return_slot_write'
                        pc=next_pc;continue
                    if ops[0].type!=X86_OP_REG:return None,'unreviewed_memory_write'
                    if pc==producer and ops[1].type==X86_OP_MEM and ins.reg_name(ops[1].mem.base)=='rip' and ops[0].size==8:
                        item=('state',pc+ins.size+ops[1].mem.disp,())
                    elif ops[1].type==X86_OP_REG and ops[0].size in (1,2,8) and ops[0].size==ops[1].size and ops[0].reg==ops[1].reg:
                        pc=next_pc;continue
                    else:item=value(ops[1])
                    store(ops[0],item)
                elif name in ('add','sub','xor','or','and','cmp','test','rol','ror','shl','shr','sal','sar','inc','dec'):
                    if ops[0].type!=X86_OP_REG:return None,'unreviewed_memory_arithmetic'
                    width=ops[0].size*8;mask=(1<<width)-1;left=value(ops[0]);right=value(ops[1]) if len(ops)>1 else 1
                    same=len(ops)>1 and ops[1].type==X86_OP_REG and ops[0].reg==ops[1].reg
                    item=None;old_cf=flags['cf']
                    if name in ('rol','ror','shl','shr','sal','sar'):
                        if not isinstance(right,int):return None,'variable_shift'
                        count=right&(63 if width==64 else 31)
                        if not count:pc=next_pc;continue
                        if name in ('rol','ror'):
                            item=_rotate(left,count,name=='rol',width) if isinstance(left,int) else (left[0],left[1],left[2]+((name,count),)) if _expr(left) and width==64 else None
                            flags['cf']=None;flags['of']=None
                        else:
                            signed=left-(1<<width) if isinstance(left,int) and left&(1<<(width-1)) else left
                            item=((left<<count) if name in ('shl','sal') else ((signed if name=='sar' else left)>>count))&mask if isinstance(left,int) else None
                            flags=_flags(item,width)
                    else:
                        operation='add' if name in ('add','inc') else 'sub' if name in ('sub','cmp','dec') else name
                        if operation=='xor' and same:item=0
                        elif isinstance(left,int) and isinstance(right,int):
                            item={'add':lambda:left+right,'sub':lambda:left-right,'xor':lambda:left^right,
                                  'and':lambda:left&right,'test':lambda:left&right,'or':lambda:left|right}[operation]()&mask
                        elif width==64 and _expr(left) and isinstance(right,int) and operation in ('add','sub','xor'):
                            item=(left[0],left[1],left[2]+(('add' if operation=='sub' else operation,(-right if operation=='sub' else right)&MASK),))
                        elif width==64 and isinstance(left,int) and _expr(right) and operation=='add':
                            item=(right[0],right[1],right[2]+(('add',left),))
                        logical=operation in ('xor','and','test','or')
                        flags=_flags(item if isinstance(item,int) else None,width,cf=False if logical else None,of=False if logical else None)
                        if name in ('inc','dec'):flags['cf']=old_cf
                    if name not in ('cmp','test'):
                        if _family(ins.reg_name(ops[0].reg))=='rsp':stack=()
                        store(ops[0],item)
                else:return None,'unsupported:'+name
            except DiscoveryError:raise
            except (ValueError,TypeError,KeyError,IndexError):return None,'unsupported_operand'
            pc=next_pc
    return (tuple(hits),None) if hits else (None,'no_accessor_path')


def locate_decoder_flow(image,accessor,budget):
    if accessor is None:return {},{},None
    from war3_discovery_locators import decoder
    disassembler=decoder();image.function_size(accessor)
    functions={k:v for k,v in image._runtime_functions.items() if v>k};starts=sorted(functions)
    witnesses={};attempts=0
    for segment in image.segments:
        if not segment.executable:continue
        for match in re.finditer(rb'\x48\x8b[\x0d\x1d]....\x48[\xb8-\xbb]........',segment.data,re.S):
            producer=segment.rva+match.start();index=bisect_right(starts,producer)-1
            if index<0:continue
            function=starts[index];end=functions[function]
            if not function<=producer<end or end-function>1024:continue
            attempts+=1;budget.check('正在定位有完整数据流的状态解码器')
            if attempts>4096:break
            result,error=_trace(image,producer,end,accessor,disassembler,budget,start=function)
            if result:
                for normalized,finish in result:
                    if 0<normalized[0]<image.size and normalized[0]%8==0:
                        witnesses.setdefault(normalized,{})[function]=(function,image.read(function,finish-function).hex(),producer)
    accepted={key:tuple(values.values()) for key,values in witnesses.items() if len(values)>=2}
    if len(accepted)!=1:
        state='ambiguous' if accepted else 'unresolved'
        return {},{'decoder.flow':DiscoveryEvidence('decoder.flow',state,'bounded_decoder_to_player_paths',detail=str(len(accepted))+' qualified identities')},None
    (root,values),rows=next(iter(accepted.items()));anchors=tuple((at,raw) for at,raw,_ in rows)
    config=dict(zip(('add1','rol','xor','ror','add2'),values))
    updates={'addresses.game_state':root,**{'decoder.'+k:v for k,v in config.items()},
             'modules.legacy_layout.implementation':'legacy_layout_24332_v1'}
    evidence={k:DiscoveryEvidence(k,'confirmed','proved_decoder_paths_to_typed_players',(v,),anchors) for k,v in updates.items()}
    evidence['decoder']=DiscoveryEvidence('decoder','confirmed','proved_decoder_paths_to_typed_players',anchors=anchors)
    evidence['decoder.flow']=DiscoveryEvidence('decoder.flow','confirmed','bounded_decoder_to_player_paths',anchors=anchors,
        detail=str(len(anchors))+' independent containing functions')
    producer=rows[0][2];head=image.read(producer,7)
    core=b''
    proved_bytes=bytes.fromhex(rows[0][1])
    offset=producer+7-rows[0][0]
    for ins in disassembler.disasm(proved_bytes[offset:offset+64],producer+7):
        if ins.mnemonic not in ('mov','movabs','xor','rol','ror','add'):break
        core+=bytes(ins.bytes)
    checks=[{'rva':producer,'bytes':head.hex()},{'rva':producer+7,'bytes':core.hex()}]
    for i,row in enumerate(checks):
        evidence['checks.game_state.'+str(i)]=DiscoveryEvidence('checks.game_state.'+str(i),'confirmed','proved_decoder_path_anchor',(row['rva'],),anchors)
    return updates,evidence,checks
