"""Bounded native-name bootstrap independent of GameSession.prepare()."""
from __future__ import annotations
import struct
from war3_profile_discovery import DiscoveryEvidence, DiscoveryError

ANCHORS = {"GetUnitTypeId":"(Hunit;)I", "GetUnitX":"(Hunit;)R",
           "GetPlayerState":"(Hplayer;Hplayerstate;)I", "UnitAddAbility":"(Hunit;I)B"}


class BudgetMemory:
    def __init__(self, memory, budget): self.memory,self.budget=memory,budget
    def read(self, address, size): return self.budget.read(self.memory,address,size)


def discover_registrations(memory, image, source, budget, *, heap_budget=64*1024*1024):
    """Return candidate contexts; caller must associate one with the current window TLS.

    Finding a name in a heap is not a registration, and finding a valid old table
    is not proof that it belongs to the current map. No live pointer is persisted.
    """
    from war3_game_profile import profile_scope
    from war3_native_table import NativeTable24268
    pointers=set()
    for name in ANCHORS:
        pointers.update(image.base+rva for rva in image.find(name.encode()+b"\0",budget))
    if not hasattr(memory,'regions'):
        return {},DiscoveryEvidence('native_table','unresolved','native_name_references')
    layout=source.section('native_table');contexts={};read=0
    bounded=BudgetMemory(memory,budget)
    regions=sorted((r for r in memory.regions() if r.typ==0x20000 and not r.protect&0x101),key=lambda r:r.size)
    chunks=[];exhausted=False
    for region in regions:
        budget.check('正在定位原生接口名称')
        tail=b''
        for offset in range(0,region.size,256*1024):
            size=min(256*1024,region.size-offset)
            if read+size>heap_budget:
                exhausted=True;break
            read+=size
            try:chunk=budget.read(memory,region.base+offset,size)
            except OSError:tail=b'';continue
            data=tail+chunk;origin=region.base+offset-len(tail)
            chunks.append((origin,data))
            for name in ANCHORS:
                needle=name.encode()+b"\0";pos=0
                while (pos:=data.find(needle,pos))>=0:
                    pointers.add(origin+pos);pos+=1
            tail=data[-255:]
        if exhausted:break
    visited=set();needles=tuple(struct.pack('<Q',value) for value in pointers)
    for origin,data in chunks:
        budget.check('正在核对原生接口注册链表')
        for needle in needles:
            pos=0
            while (pos:=data.find(needle,pos))>=0:
                budget.check()
                address=origin+pos;pos+=1
                if address%8:continue
                node=address-layout['name']
                if node in visited:continue
                visited.add(node)
                chain=set();current=node
                try:
                    for _ in range(8192):
                        if current&1:break
                        if current in chain or current<0x10000 or current%8:raise ValueError('invalid native chain')
                        chain.add(current)
                        current=struct.unpack('<Q',bounded.read(current+layout['next'],8))[0]
                    else:raise ValueError('native chain bound')
                    context=(current^1)-layout['terminal']-layout['table']
                    if context in contexts:continue
                    with profile_scope(source):table=NativeTable24268(bounded,context)
                    if not all(name in table.entries and table.entries[name].signature==sig for name,sig in ANCHORS.items()):continue
                    if not all(image.executable(table.entries[name].handler-image.base) for name in ANCHORS):continue
                    contexts[context]=table.entries
                except DiscoveryError:raise
                except (OSError,ValueError,RuntimeError):continue
    return contexts,DiscoveryEvidence('native_table','unresolved','native_name_references',
                    detail=('Bounded heap scan; ' if exhausted else '')+'registration candidates require active TLS association')


def associate_tls(memory, tls, contexts, budget, *, low=0x20, high=0x120):
    """Require a unique active TLS slot; no preference for the old offset."""
    found=[]
    for offset in range(low,high,8):
        try:value=struct.unpack('<Q',budget.read(memory,tls+offset,8))[0]
        except OSError:continue
        if value in contexts:
            again=struct.unpack('<Q',budget.read(memory,tls+offset,8))[0]
            if again==value:found.append((offset,value))
    if len(found)!=1:
        return None,DiscoveryEvidence('context.native_slot','ambiguous' if found else 'unresolved','active_tls_native_context')
    return found[0],DiscoveryEvidence('context.native_slot','confirmed','active_tls_native_context',(found[0][0],))


def read_window_tls(memory, base, tls_index_rva, hwnd, pid, budget):
    """Read only the owning thread TEB. No game-frame/profile bootstrap is needed."""
    import ctypes as c
    from war3_thread_context import infer_tls_layout
    k=c.WinDLL('kernel32',use_last_error=True);u=c.WinDLL('user32',use_last_error=True)
    n=c.WinDLL('ntdll');P=c.c_void_p;U=c.c_ulong
    u.GetWindowThreadProcessId.argtypes=(P,c.POINTER(U));u.GetWindowThreadProcessId.restype=U
    owner=U();tid=u.GetWindowThreadProcessId(hwnd,c.byref(owner))
    if owner.value!=pid or not tid:raise DiscoveryError('游戏窗口与进程不一致，请重新连接。',code='identity')
    k.OpenThread.argtypes=(U,c.c_bool,U);k.OpenThread.restype=P
    k.CloseHandle.argtypes=(P,);k.CloseHandle.restype=c.c_int
    thread=k.OpenThread(0x40,False,tid)
    if not thread:raise c.WinError(c.get_last_error())
    try:
        n.NtQueryInformationThread.argtypes=(P,U,P,U,P);n.NtQueryInformationThread.restype=c.c_long
        data=(c.c_ulonglong*6)()
        if n.NtQueryInformationThread(thread,0,c.byref(data),c.sizeof(data),None)<0 or (data[2],data[3])!=(pid,tid):
            raise DiscoveryError('未能确认游戏线程身份。',code='identity')
        teb=data[1]
    finally:k.CloseHandle(thread)
    offsets=None
    for dll in (k,c.WinDLL('kernelbase')):
        try:offsets=infer_tls_layout(c.string_at(c.cast(dll.TlsGetValue,P).value,128));break
        except (ValueError, RuntimeError):continue
    if offsets is None:raise DiscoveryError('当前系统的线程布局尚未识别。',code='context')
    index=struct.unpack('<I',budget.read(memory,base+tls_index_rva,4))[0]
    if index>=1088:raise DiscoveryError('定位到的线程索引不符合当前系统范围。',code='context')
    if index<64:slot=teb+offsets[0]+index*8
    else:
        expansion=struct.unpack('<Q',budget.read(memory,teb+offsets[1],8))[0]
        if not 0x10000<=expansion<0x800000000000:raise DiscoveryError('游戏线程尚未初始化。',code='not_ready')
        slot=expansion+(index-64)*8
    import time
    until=min(budget.deadline,time.monotonic()+1.0)
    while True:
        budget.check('正在等待可读取的游戏线程数据')
        tls=struct.unpack('<Q',budget.read(memory,slot,8))[0]
        if 0x10000<=tls<0x800000000000 and not tls%8:
            if struct.unpack('<Q',budget.read(memory,slot,8))[0]==tls:
                break
        if time.monotonic()>=until:
            raise DiscoveryError('本轮未读到稳定的游戏线程数据；未执行游戏修改，可重新连接重试。',code='not_ready')
        time.sleep(.001)
    if (u.GetWindowThreadProcessId(hwnd,c.byref(owner))!=tid or owner.value!=pid or
        struct.unpack('<Q',budget.read(memory,slot,8))[0]!=tls):
        raise DiscoveryError('定位期间游戏线程数据发生变化，请重试。',code='not_ready')
    return tls


def discover_tls_registrations(memory,image,source,tls,budget):
    """Prefer bounded slots of the actual window thread over a broad heap scan."""
    from war3_game_profile import profile_scope
    from war3_native_table import NativeTable24268,_string
    bounded=BudgetMemory(memory,budget);layout=source.section('native_table');contexts={}
    for offset in range(0x20,0x120,8):
        budget.check('正在核对当前线程的原生接口')
        try:
            context=struct.unpack('<Q',bounded.read(tls+offset,8))[0]
            if not 0x10000<=context<0x800000000000 or context%8:continue
            head=struct.unpack('<Q',bounded.read(context+layout['table']+layout['head'],8))[0]
            if not 0x10000<=head<0x800000000000 or head%8:continue
            name_pointer=struct.unpack('<Q',bounded.read(head+layout['name'],8))[0]
            name=_string(bounded,name_pointer)
            if not name.replace('_','').isalnum() or len(name)>100:continue
            with profile_scope(source):table=NativeTable24268(bounded,context)
            if not all(n in table.entries and table.entries[n].signature==sig for n,sig in ANCHORS.items()):continue
            if not all(image.executable(table.entries[n].handler-image.base) for n in ANCHORS):continue
            contexts[context]=table.entries
        except DiscoveryError:raise
        except (OSError,ValueError,RuntimeError):continue
    return contexts


def discover_active_registrations(memory, image, source, tls, budget):
    """Use a validated source layout first; infer a changed layout only if needed.

    The inferred representation uses context-relative head/terminal offsets
    (table=0). A live linked list identifies those sums, not an arbitrary split
    into an embedded table's base and members. No runtime pointer is exported
    as adapter data.
    """
    contexts = discover_tls_registrations(memory, image, source, tls, budget)
    if contexts:
        return contexts, {}, {}
    return infer_registration_layout(memory, image, source, tls, budget)


def infer_registration_layout(memory, image, source, tls, budget, *, context_span=512, node_span=128):
    from dataclasses import replace
    import re
    from war3_game_profile import profile_scope, _freeze
    from war3_native_table import NativeTable24268, _string

    bounded = BudgetMemory(memory, budget)
    identifier = re.compile(r'[A-Za-z_][A-Za-z_0-9]{1,99}\Z')
    signature = re.compile(r'\((?:[IBRSC]|H[A-Za-z_][A-Za-z_0-9]*;)*\)(?:[VIBRSC]|H[A-Za-z_][A-Za-z_0-9]*;)\Z')
    strings, blocks = {}, {}
    def pointer(value):
        return 0x10000 <= value < 0x800000000000 and value % 8 == 0
    def string(address):
        if address not in strings:
            try: strings[address] = _string(bounded, address)
            except DiscoveryError: raise
            except (OSError, ValueError, RuntimeError): strings[address] = ''
        return strings[address]
    def words(address, size):
        key = (address, size)
        if key not in blocks:
            try: blocks[key] = bounded.read(address, size)
            except OSError:
                # An unreadable suffix must not hide a readable short node.
                values = []
                for offset in range(0, size, 8):
                    try: values.append(struct.unpack('<Q', bounded.read(address+offset, 8))[0])
                    except OSError: values.append(0)
                blocks[key] = struct.pack('<'+'Q'*len(values), *values)
        return tuple(enumerate(struct.unpack('<'+'Q'*(size//8), blocks[key])))

    contexts = set()
    for offset in range(0x20, 0x120, 8):
        budget.check('正在定位变化后的原生接口布局')
        try: value = struct.unpack('<Q', bounded.read(tls+offset, 8))[0]
        except OSError: continue
        if pointer(value): contexts.add(value)
    candidates = []
    for context in sorted(contexts):
        for head_index, head in words(context, context_span):
            if not pointer(head) or head == context: continue
            node_words = words(head, node_span)
            names = [(i*8, string(p)) for i,p in node_words if pointer(p)
                     and not image.executable(p-image.base) and identifier.fullmatch(string(p))]
            signatures = [(i*8, string(p)) for i,p in node_words if pointer(p)
                          and signature.fullmatch(string(p))]
            handlers = [(i*8,p) for i,p in node_words if image.executable(p-image.base)]
            if not names or not signatures or not handlers: continue
            for name_offset, _ in names:
                for signature_offset, _ in signatures:
                    for handler_offset, _ in handlers:
                        for next_index, first_next in node_words:
                            next_offset = next_index*8
                            if next_offset in (name_offset, signature_offset, handler_offset): continue
                            if not (pointer(first_next) or first_next & 1): continue
                            current, seen, anchors, terminal = head, set(), {}, None
                            for _ in range(8192):
                                budget.check()
                                if current & 1:
                                    relative = (current ^ 1)-context
                                    if 0 <= relative < context_span and relative % 8 == 0:
                                        terminal = relative
                                    break
                                if not pointer(current) or current in seen: break
                                seen.add(current)
                                values = dict(words(current, node_span))
                                name = string(values.get(name_offset//8, 0))
                                sig = string(values.get(signature_offset//8, 0))
                                handler = values.get(handler_offset//8, 0)
                                if not identifier.fullmatch(name) or not signature.fullmatch(sig) or not image.executable(handler-image.base): break
                                if name in anchors: break
                                anchors[name] = sig
                                current = values.get(next_offset//8, 0)
                            else: continue
                            if terminal is None or not all(anchors.get(n) == sig for n,sig in ANCHORS.items()): continue
                            layout = dict(table=0, head=head_index*8, terminal=terminal,
                                          next=next_offset, name=name_offset,
                                          handler=handler_offset, signature=signature_offset)
                            data = source.to_dict(); data['native_table'] = layout
                            probe = replace(source, data=_freeze(data))
                            try:
                                # Fresh reads, outside the candidate-search cache, prove
                                # all registrations and an unchanged head/terminal chain.
                                with profile_scope(probe): table = NativeTable24268(bounded, context)
                                if table.head != head or not all(n in table.entries and table.entries[n].signature == sig
                                                               for n,sig in ANCHORS.items()): continue
                                if not all(image.executable(e.handler-image.base) for e in table.entries.values()): continue
                            except DiscoveryError: raise
                            except (OSError, ValueError, RuntimeError): continue
                            candidates.append((context, layout, table.entries))
    unique = {(context, tuple(sorted(layout.items()))): (context, layout, entries)
              for context,layout,entries in candidates}
    if len(unique) != 1:
        proof = DiscoveryEvidence('native_table', 'ambiguous' if unique else 'unresolved',
                                  'registration_layout_graph', detail='No unique active registration layout')
        return {}, {}, {'native_table': proof}
    context, layout, entries = next(iter(unique.values()))
    association, slot = associate_tls(memory, tls, {context: entries}, budget)
    if association is None:
        return {}, {}, {'context.native_slot': slot}
    updates = {'native_table.'+key: value for key,value in layout.items()}
    evidence = {path: DiscoveryEvidence(path, 'confirmed', 'registration_names_signatures_handlers_and_terminal', (value,))
                for path,value in updates.items()}
    return {context: entries}, updates, evidence
