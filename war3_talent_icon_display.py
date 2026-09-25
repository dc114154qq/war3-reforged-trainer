"""Lifetime management for the optional native talent display correction."""
import ctypes as c
import struct
from pathlib import Path
from types import SimpleNamespace

import pefile
import war3_engine_transport as transport
from war3_object_registry import ObjectRegistry24268
from war3_selection_protocol import SIGNATURES
from war3_talent_icon_control_protocol import build_work,decode_work

ORIGINAL=bytes.fromhex('488b4424208b8c24900000003b0c0774094084f6750433d2eb02b201488bcbe8a54b1bff')
SITE_RVA=0x10058c7

class TalentIconDisplay:
    def __init__(self,engine,image):
        self.engine=engine
        self.image=Path(image).resolve()
        self.handle=None;self.base=0;self.registered=False;self.uncertain=False
        self.last_result={}

    def _write(self,address,data):
        blob=c.create_string_buffer(data);written=transport.Z()
        if not transport.p['write'](self.handle,address,blob,len(data),c.byref(written)) or written.value!=len(data):
            raise c.WinError(c.get_last_error())

    def _alive(self):
        if not self.handle:return False
        fn=transport.api(transport.k,'GetExitCodeProcess',c.c_int,transport.P,c.POINTER(transport.U))
        status=transport.U()
        if not fn(self.handle,c.byref(status)):raise c.WinError(c.get_last_error())
        return status.value==259

    def _control(self,action):
        if not self._alive():raise RuntimeError('Original game process has exited')
        memory=SimpleNamespace(handle=self.handle,pid=self.engine.pid)
        add=transport.resolve(memory,'ntdll','RtlAddFunctionTable')
        delete=transport.resolve(memory,'ntdll','RtlDeleteFunctionTable')
        args=(self.base,self.base+self.exports[b'IconInstall'],self.base+self.exports[b'IconRemove'],
              add,delete,self.base+self.unwind.VirtualAddress,self.base+self.exports[b'icon_config'],
              self.unwind.Size//12,action,int(self.registered))
        self.uncertain=True
        result=self.engine._execute('talent_icon_control',tuple(n for n,_ in SIGNATURES),
            lambda _entries,tls:build_work(tls,*args),decode_work,dict(action=action,display_image=str(self.image)))
        self.last_result=result;self.registered=result['registered'];self.uncertain=False
        return result

    def install(self):
        if self.base:raise RuntimeError('Display module already mapped; remove it before installing again')
        pe=pefile.PE(str(self.image));self.exports={e.name:e.address for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
        if pe.FILE_HEADER.Machine!=0x8664 or getattr(pe,'DIRECTORY_ENTRY_IMPORT',()):
            raise ValueError('Unsupported talent display module')
        if pe.get_data(self.exports[b'icon_display_abi'],16)!=struct.pack('<4I',0x24268045,1,120,36):
            raise ValueError('Talent display ABI differs')
        self.unwind=pe.OPTIONAL_HEADER.DATA_DIRECTORY[3]
        if not self.unwind.Size or self.unwind.Size%12:raise ValueError('Display unwind data missing')
        self.handle=transport.p['open_process'](0x143a,False,self.engine.pid)
        if not self.handle:raise c.WinError(c.get_last_error())
        file=section=None
        try:
            with self.engine.memory_factory(self.engine.pid) as memory:
                game=ObjectRegistry24268.attach(memory)
                self.game_base=game.base
                try:
                    code=memory.read(game.base+SITE_RVA,len(ORIGINAL))
                except OSError as exc:
                    # Some game code pages are readable only while dispatched
                    # on the UI thread. IconInstall still requires exact bytes
                    # before changing protection or writing anything.
                    self.code_preflight={'external_read_error':str(exc),'validation':'ui_thread_required'}
                else:
                    if code!=ORIGINAL:raise RuntimeError('Talent panel code differs from the verified display predicate')
                    self.code_preflight={'validation':'external_match_and_ui_thread_required'}
            memory=SimpleNamespace(handle=self.handle,pid=self.engine.pid)
            owner=transport.U();tid=transport.window_thread(self.engine.hwnd,c.byref(owner))
            if owner.value!=self.engine.pid or not tid:raise RuntimeError('Game window identity changed')
            file=transport.x['create_file'](str(self.image),0x80000000,5,None,3,0x80,None)
            if file==transport.P(-1).value:file=None;raise c.WinError(c.get_last_error())
            section=transport.x['create_mapping'](file,None,0x1000002,0,0,None)
            if not section:raise c.WinError(c.get_last_error())
            view=transport.P();size=transport.Z()
            status=transport.x['map_section'](section,self.handle,c.byref(view),0,0,None,c.byref(size),2,0,2)
            if status<0 or not view.value:raise RuntimeError('Talent display image mapping failed: '+hex(status&0xffffffff))
            self.base=int(view.value)
            config=struct.pack('<6Q8I36s4x',self.game_base,self.game_base+0x1ba490,
                transport.resolve(memory,'kernel32','GetCurrentThreadId'),
                transport.resolve(memory,'kernel32','VirtualProtect'),
                transport.resolve(memory,'kernel32','FlushInstructionCache'),
                transport.resolve(memory,'ntdll','__C_specific_handler'),tid,0,0,0,0,0,0,0,bytes(36))
            self._write(self.base+self.exports[b'icon_config'],config)
            result=self._control(0)
            if not result['success'] or not result['installed']:
                if result.get('error') == 3 and self.base:
                    try:
                        self.observed_code = transport.bytes_at(
                            self.handle,
                            self.base + self.exports[b'icon_config'] + 80,
                            len(ORIGINAL),
                        ).hex()
                    except Exception as exc:
                        self.observed_code_error = str(exc)
                raise RuntimeError('Talent icon installation failed: '+str(result))
            return self.snapshot()
        except Exception:
            if self.base and not self.uncertain:
                try:self.close()
                except Exception:pass  # Keep image/handle alive if cleanup cannot be proved.
            elif not self.base and self.handle:
                transport.p['close'](self.handle);self.handle=None
            raise
        finally:
            if section:transport.p['close'](section)
            if file:transport.p['close'](file)

    def snapshot(self):
        if not self.base or not self._alive():raise RuntimeError('Display module is not attached to a live game')
        data=transport.bytes_at(self.handle,self.base+self.exports[b'icon_config'],120)
        tid,installed,error,calls,extra,faults,active,protect=struct.unpack_from('<8I',data,48)
        return dict(image_base=hex(self.base),game_base=hex(self.game_base),thread_id=tid,
                    installed=bool(installed),error=error,calls=calls,extra_enabled=extra,
                    predicate_faults=faults,active=active,registered=self.registered)

    def close(self):
        if not self.handle:return dict(closed=True)
        if not self._alive():
            transport.p['close'](self.handle);self.handle=None;self.base=0
            return dict(closed=True,process_exited=True)
        if self.uncertain:raise RuntimeError('Display control completion unknown; mapped image retained')
        if self.base:
            state=self.snapshot()
            if state['installed'] or self.registered:
                result=self._control(1)
                if result['error'] or result['installed'] or result['registered'] or result['active']:
                    raise RuntimeError('Display removal unverified; image retained: '+str(result))
            # If install returned before patching, the module never owned the
            # game code. External reads of this page can return 299 even
            # though the game-thread validation already completed, so do not
            # turn diagnostic cleanup into a false restore failure.
            never_patched = (
                self.last_result.get('action') == 0
                and not self.last_result.get('installed')
                and not self.last_result.get('registered')
            )
            if not never_patched and transport.bytes_at(self.handle,self.game_base+SITE_RVA,len(ORIGINAL))!=ORIGINAL:
                raise RuntimeError('Original display instructions not restored; image retained')
            status=transport.x['unmap_section'](self.handle,transport.P(self.base))
            if status<0:raise RuntimeError('Display image unmap failed: '+hex(status&0xffffffff))
            self.base=0
        transport.p['close'](self.handle);self.handle=None
        return dict(closed=True,original_code_restored=True)
