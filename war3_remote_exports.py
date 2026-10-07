"""Read-only target PE exports; never rebase a local compatibility/shim pointer.

Windows export tables/forwarders follow Microsoft's PE specification. API-set
contracts are resolved from the target's namespace, not a local DLL address.
"""
import re
import struct


class RemoteExportError(RuntimeError):
    pass


def module_name(value):
    text=str(value).lower()
    if not re.fullmatch(r'[a-z0-9_.-]{1,260}',text):
        raise RemoteExportError('Invalid target system module name')
    return text if text.endswith(('.dll','.exe')) else text+'.dll'


class ApiSetNamespace:
    """Bounded Windows 10/11 v6 namespace snapshot from the target PEB."""
    def __init__(self,data):
        if len(data)<28:raise RemoteExportError('Incomplete target API-set namespace')
        version,size,_,count,offset,_,_=struct.unpack_from('<7I',data)
        if version!=6 or size!=len(data) or size>2*1024*1024 or count>16384:
            raise RemoteExportError('Unsupported or invalid target API-set namespace')
        self.data=data;self.entries={};self.hashed_entries={}
        if offset<28 or offset+count*24>size:
            raise RemoteExportError('Target API-set entries exceed namespace')
        for i in range(count):
            _,name,length,hashed,values,number=struct.unpack_from('<6I',data,offset+i*24)
            if hashed>length or not 1<=number<=128 or values+number*20>size:
                raise RemoteExportError('Invalid target API-set values')
            contract=self.text(name,length).lower()
            hosts=[]
            for j in range(number):
                _,alias,alias_length,host,host_length=struct.unpack_from('<5I',data,values+j*20)
                hosts.append((self.text(alias,alias_length).lower(),self.text(host,host_length)))
            if contract in self.entries:raise RemoteExportError('Duplicate target API-set contract')
            self.entries[contract]=hosts
            prefix=self.text(name,hashed).lower()
            self.hashed_entries.setdefault(prefix,[]).append(contract)

    def text(self,offset,length):
        if length%2 or length>1024 or offset<0 or offset+length>len(self.data):
            raise RemoteExportError('Target API-set string exceeds namespace')
        return self.data[offset:offset+length].decode('utf-16-le')

    def host(self,contract,importer=None):
        key=module_name(contract)[:-4]
        hosts=self.entries.get(key)
        if hosts is None:
            # v6 stores a HashedLength prefix excluding the final version
            # segment. Use that target-provided key, not a guessed newer DLL.
            prefix,separator,minor=key.rpartition('-')
            matches=self.hashed_entries.get(prefix,()) if separator and minor.isdecimal() else ()
            if len(matches)==1:hosts=self.entries[matches[0]]
            elif len(matches)>1:raise RemoteExportError('Ambiguous target API-set prefix: '+prefix)
        if hosts is None:raise RemoteExportError('Missing target API-set contract: '+key)
        parent=module_name(importer) if importer else ''
        aliases=[host for alias,host in hosts if alias and module_name(alias)==parent]
        choices=aliases or [host for alias,host in hosts if not alias]
        unique=set(filter(None,choices))
        if len(unique)!=1:raise RemoteExportError('Missing or ambiguous target API-set host: '+key)
        return module_name(unique.pop())


class RemoteExportResolver:
    def __init__(self,read,locate,api_set_host=None):
        self.read,self.locate,self.api_set_host=read,locate,api_set_host
        self.tables={};self.last_chain=[]

    def _table(self,base):
        if base in self.tables:return self.tables[base]
        dos=self.read(base,64)
        if dos[:2]!=b'MZ':raise RemoteExportError('Target system image has no DOS header')
        nt=struct.unpack_from('<I',dos,60)[0]
        if not 64<=nt<=1024*1024:raise RemoteExportError('Invalid target PE header offset')
        head=self.read(base+nt,24)
        if head[:4]!=b'PE\0\0':raise RemoteExportError('Target system image has no PE header')
        optional_size=struct.unpack_from('<H',head,20)[0]
        if not 112<=optional_size<=4096:raise RemoteExportError('Invalid target optional header')
        optional=self.read(base+nt+24,optional_size)
        magic=struct.unpack_from('<H',optional)[0]
        directory={0x10b:96,0x20b:112}.get(magic)
        if directory is None or directory+8>len(optional):
            raise RemoteExportError('Unsupported target system PE architecture')
        if struct.unpack_from('<I',optional,directory-4)[0]<1:
            raise RemoteExportError('Target system image has no export data directory')
        image_size=struct.unpack_from('<I',optional,56)[0]
        if not 4096<=image_size<=512*1024*1024 or nt+24+optional_size>image_size:
            raise RemoteExportError('Invalid target system image size')
        export,size=struct.unpack_from('<2I',optional,directory)
        if not export or not 40<=size<=8*1024*1024 or export+size>image_size:
            raise RemoteExportError('Invalid target export directory')
        blob=self.read(base+export,size)
        def data(rva,length):
            if rva<0 or length<0 or rva+length>image_size:
                raise RemoteExportError('Target export range exceeds image')
            if export<=rva and rva+length<=export+size:
                return blob[rva-export:rva-export+length]
            return self.read(base+rva,length)
        def text(rva,limit=512):
            result=bytearray()
            while len(result)<limit:
                address=base+rva+len(result)
                length=min(64,limit-len(result),4096-(address&4095),image_size-rva-len(result))
                if length<=0:break
                part=data(rva+len(result),length);end=part.find(b'\0')
                if end>=0:return bytes(result+part[:end]).decode('ascii')
                result.extend(part)
            raise RemoteExportError('Unterminated target export string')
        ordinal,count,names,functions,name_table,ordinals=struct.unpack_from('<6I',blob,16)
        if not 0<count<=131072 or names>65536:
            raise RemoteExportError('Invalid target export count')
        function_rvas=struct.unpack('<'+'I'*count,data(functions,count*4))
        name_rvas=struct.unpack('<'+'I'*names,data(name_table,names*4)) if names else ()
        indices=struct.unpack('<'+'H'*names,data(ordinals,names*2)) if names else ()
        named={}
        for rva,index in zip(name_rvas,indices):
            if index>=count:raise RemoteExportError('Target export ordinal exceeds function table')
            name=text(rva)
            if name in named:raise RemoteExportError('Duplicate target export name')
            named[name]=index
        table=dict(size=image_size,export=export,length=size,ordinal=ordinal,
                   functions=function_rvas,names=named,text=text)
        self.tables[base]=table
        return table

    def resolve(self,library,symbol):
        library=module_name(library);parent=None;seen=set();chain=[]
        self.last_chain=chain
        for _ in range(16):
            base=self.locate(library)
            if not base and library.startswith(('api-','ext-')) and self.api_set_host:
                host=module_name(self.api_set_host(library,parent))
                chain.append(dict(contract=library,host=host,source='target_api_set'))
                library=host;base=self.locate(library)
            if not base:raise RemoteExportError('Missing target system module: '+library)
            key=(base,symbol)
            if key in seen:raise RemoteExportError('Cyclic target export forwarder')
            seen.add(key);table=self._table(base)
            if isinstance(symbol,bool):raise RemoteExportError('Invalid target export symbol')
            if isinstance(symbol,int) or isinstance(symbol,str) and symbol.startswith('#'):
                try:index=int(str(symbol).lstrip('#'))-table['ordinal']
                except ValueError as exc:raise RemoteExportError('Invalid target export ordinal') from exc
            else:index=table['names'].get(symbol,-1)
            if not 0<=index<len(table['functions']):
                raise RemoteExportError('Missing target export: '+library+'!'+str(symbol))
            rva=table['functions'][index]
            if not rva or rva>=table['size']:raise RemoteExportError('Invalid target export RVA')
            if table['export']<=rva<table['export']+table['length']:
                forward=table['text'](rva)
                if '.' not in forward:raise RemoteExportError('Invalid target export forwarder')
                host,symbol=forward.rsplit('.',1)
                chain.append(dict(module=library,base=hex(base),forwarder=forward,source='target_pe_exports'))
                parent=library;library=module_name(host)
                continue
            address=base+rva
            chain.append(dict(module=library,base=hex(base),symbol=symbol,rva=hex(rva),
                              address=hex(address),source='target_pe_exports'))
            return address
        raise RemoteExportError('Target export forwarder depth exceeded')
