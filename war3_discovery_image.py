"""Read-only shared image observation for protected pages; never injects or changes protection."""
import ctypes as c
import struct
from war3_profile_discovery import DiscoveryImage,DiscoveryError


def capture_image(memory,base,fingerprint,budget):
    """Prefer a matching readable shared image, otherwise retain normal readable pages."""
    try:
        image=_shared_image(memory,base,fingerprint,budget)
        if image is not None:return image
    except DiscoveryError:raise
    except (OSError,ValueError):pass
    return DiscoveryImage.capture(memory,base,fingerprint,budget)


def _shared_image(memory,base,fingerprint,budget):
    if not hasattr(memory,'pid'):return None
    k=c.WinDLL('kernel32',use_last_error=True);nt=c.WinDLL('ntdll');P=c.c_void_p;U=c.c_ulong
    def api(lib,name,result,*types):
        fn=getattr(lib,name);fn.restype=result;fn.argtypes=types;return fn
    open_process=api(k,'OpenProcess',P,U,c.c_bool,U)
    close=api(k,'CloseHandle',c.c_bool,P)
    current=api(k,'GetCurrentProcess',P)
    duplicate=api(k,'DuplicateHandle',c.c_bool,P,P,P,c.POINTER(P),U,c.c_bool,U)
    query_process=api(nt,'NtQueryInformationProcess',c.c_long,P,U,P,U,c.POINTER(U))
    query_object=api(nt,'NtQueryObject',c.c_long,P,U,P,U,P)
    query_section=api(nt,'NtQuerySection',c.c_long,P,U,P,U,P)
    map_view=api(k,'MapViewOfFile',P,P,U,U,U,c.c_size_t)
    unmap=api(k,'UnmapViewOfFile',c.c_bool,P)
    read=api(k,'ReadProcessMemory',c.c_bool,P,P,P,c.c_size_t,c.POINTER(c.c_size_t))
    class Entry(c.Structure):
        _fields_=[('handle',P),('handles',c.c_size_t),('pointers',c.c_size_t),('access',U),('type',U),('attributes',U),('reserved',U)]
    class String(c.Structure):
        _fields_=[('length',c.c_ushort),('maximum',c.c_ushort),('buffer',P)]
    class Section(c.Structure):
        _fields_=[('base',P),('attributes',U),('size',c.c_longlong)]
    process=open_process(0x440,False,memory.pid)
    if not process:return None
    try:
        length=65536
        for _ in range(7):
            budget.check('正在读取游戏共享映像')
            if length>16*1024*1024:return None
            buffer=c.create_string_buffer(length);needed=U()
            status=query_process(process,51,buffer,length,c.byref(needed))
            if status>=0:break
            if status&0xffffffff not in (0xc0000004,0x80000005):return None
            length=max(length*2,needed.value)
        else:return None
        count=c.c_size_t.from_buffer(buffer).value
        if 16+count*c.sizeof(Entry)>length:return None
        for i in range(count):
            budget.check()
            item=Entry.from_buffer_copy(buffer,16+i*c.sizeof(Entry));dup=P();view=None
            if not duplicate(process,item.handle,current(),c.byref(dup),0,False,2):continue
            try:
                namebuf=c.create_string_buffer(2048)
                if query_object(dup,2,namebuf,len(namebuf),None)<0:continue
                name=String.from_buffer(namebuf)
                start=c.addressof(namebuf)
                if not start<=int(name.buffer or 0)<=start+2048-name.length or name.length>512:continue
                if c.wstring_at(name.buffer,name.length//2)!='Section':continue
                info=Section()
                if query_section(dup,0,c.byref(info),c.sizeof(info),None)<0 or info.size!=fingerprint[2]:continue
                view=map_view(dup,4,0,0,info.size)
                if not view:continue
                class View:
                    def read(self,address,size):
                        relative=address-base
                        if relative<0 or relative+size>info.size:raise OSError('shared image range')
                        buf=c.create_string_buffer(size);actual=c.c_size_t()
                        if not read(current(),view+relative,buf,size,c.byref(actual)) or actual.value!=size:
                            raise OSError('unreadable shared image page')
                        return buf.raw
                proxy=View()
                try:
                    dos=proxy.read(base,64);offset=struct.unpack_from('<I',dos,60)[0]
                    if dos[:2]!=b'MZ' or not 64<=offset<=4096:continue
                    head=proxy.read(base+offset,88)
                    actual=(struct.unpack_from('<H',head,4)[0],struct.unpack_from('<I',head,8)[0],struct.unpack_from('<I',head,80)[0])
                    if head[:4]!=b'PE\0\0' or actual!=tuple(fingerprint):continue
                    # Compare the running main module header, not just another section of equal size.
                    if memory.read(base+offset,88)!=head:continue
                    return DiscoveryImage.capture(proxy,base,fingerprint,budget)
                except OSError:continue
            finally:
                if view:unmap(view)
                close(dup)
    finally:close(process)
    return None


def file_type_descriptors(path,fingerprint,type_names,budget):
    """Read RTTI names from a matching PE file; RVAs, never file offsets."""
    import pefile
    result={name:[] for name in type_names}
    pe=pefile.PE(str(path),fast_load=True)
    try:
        actual=(pe.FILE_HEADER.Machine,pe.FILE_HEADER.TimeDateStamp,pe.OPTIONAL_HEADER.SizeOfImage)
        if actual!=tuple(fingerprint):raise DiscoveryError('游戏文件与已运行映像不一致。',code='identity')
        with open(path,'rb') as stream:
            for section in pe.sections:
                budget.check('正在读取原生类型信息')
                # MSVC TypeDescriptors commonly live in writable .data even
                # though we only read their names from the on-disk executable.
                if (section.Characteristics&0x20000000
                        or not section.Characteristics&0x40000000):continue
                if section.SizeOfRawData>32*1024*1024:continue
                stream.seek(section.PointerToRawData);data=stream.read(section.SizeOfRawData)
                for name in type_names:
                    needle=('.?AV'+name+'@@').encode()+b'\0';pos=0
                    while (pos:=data.find(needle,pos))>=0:
                        if pos>=16:result[name].append(section.VirtualAddress+pos-16)
                        pos+=1
    finally:pe.close()
    return {name:tuple(sorted(set(values))) for name,values in result.items()}
