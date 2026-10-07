"""Session-owned persistent timing module; never unload a live clock hook."""
import ctypes as c
import struct
from pathlib import Path
from types import SimpleNamespace

import pefile
import war3_engine_transport as transport
from war3_game_session import process_creation, SessionError, OperationEvidence

MAGIC=0x57435331
WORK_SIZE=88


class TimingHealthError(RuntimeError):
    """Exited control with a known broken clock path; unrelated writes stay usable."""
    def __init__(self,message,report=None):
        super().__init__(message)
        self.report=report or {}


class ResidentClockMismatch(RuntimeError):
    """Read-only validation rejected an older resident image; no new code ran."""
    def __init__(self,detail):
        super().__init__('游戏中驻留的是旧加速组件，请重开游戏后使用加速；其他功能仍可使用。')
        self.report=dict(operation='game_speed',cause='resident_clock_mismatch',
            detail=detail,dispatch_started=False,image_left_resident=True)


def encode_speed_factor(factor):
    """Encode user input without a product-imposed maximum multiplier."""
    import math
    if isinstance(factor,bool) or not isinstance(factor,(int,float)):
        raise ValueError('加速倍率必须为不小于 1 的有限数值')
    try:
        value=float(factor)
    except (OverflowError,ValueError) as exc:
        raise ValueError('倍率超出底层计时数值格式的表示范围') from exc
    if not math.isfinite(value) or value<1:
        raise ValueError('加速倍率必须为不小于 1 的有限数值')
    encoded=value*1000
    if not math.isfinite(encoded) or encoded>0xffffffff:
        raise ValueError('倍率超出底层计时数值格式的表示范围')
    return round(encoded)


class SpeedClockBackend:
    def __init__(self,engine,image):
        self.engine=engine
        self.image=Path(image).resolve()
        self.handle=None
        self.base=0
        self.created=None
        self.saved_rate=None
        self.last_result={}
        self.uncertain=False
        self.pinned=False
        self.unavailable_reason=None
        engine.session.resources['speed_clock']=self

    def _alive(self):
        if not self.handle:return False
        code=transport.U()
        get=transport.api(transport.k,'GetExitCodeProcess',c.c_int,transport.P,c.POINTER(transport.U))
        if not get(self.handle,c.byref(code)):raise c.WinError(c.get_last_error())
        return code.value==259

    def _validate(self):
        if not self._alive():raise SessionError('Original game process has exited')
        memory=SimpleNamespace(handle=self.handle,pid=self.engine.pid)
        if process_creation(memory)!=self.created or self.engine.session.identity.created!=self.created:
            raise SessionError('Timing module belongs to another process instance')

    def _discover(self):
        name=f'Local\\War3TrainerClock-{self.engine.pid:08x}-{self.created:016x}'
        open_mapping=transport.api(transport.k,'OpenFileMappingW',transport.P,transport.U,c.c_int,c.c_wchar_p)
        view_mapping=transport.api(transport.k,'MapViewOfFile',transport.P,transport.P,transport.U,transport.U,transport.U,transport.Z)
        unmap=transport.api(transport.k,'UnmapViewOfFile',c.c_int,transport.P)
        handle=open_mapping(4,False,name)
        if not handle:
            error=c.get_last_error()
            if error==2:return 0
            raise c.WinError(error)
        view=None
        try:
            view=view_mapping(handle,4,0,0,64)
            if not view:raise c.WinError(c.get_last_error())
            magic,pid,created,base,version,*_=struct.unpack('<8Q',c.string_at(view,64))
            if (magic,pid,created,version)!=(MAGIC,self.engine.pid,self.created,1):
                raise SessionError('Existing timing module identity differs')
            if not 0x10000<=base<0x800000000000 or base%0x10000:
                raise SessionError('Invalid existing timing image base')
            return base
        finally:
            if view:unmap(view)
            transport.p['close'](handle)

    def attach(self):
        try:
            return self._attach()
        except ResidentClockMismatch as exc:
            self.incompatible_resident=True
            self.unavailable_reason=str(exc)
            self.pinned=True
            # Only local handles belong to this attempt. Never invoke new RVAs
            # in the old image, unload it, or poison unrelated game features.
            raise
        except TimingHealthError:
            # A completed, identity-checked resident health query is not an
            # unresolved attachment. Keep the image pinned, not other features.
            raise
        except Exception as exc:
            if self.base:
                # A resident generation mismatch must never be retried using
                # the new image's export offsets against the old image.
                self.uncertain=True
                self.engine.session.uncertain=True
                self.engine.session.retained['speed_clock_attachment']={
                    'base':hex(self.base),'error':str(exc),'pinned':self.pinned}
            else:
                if self.handle:transport.p['close'](self.handle);self.handle=None
                if self.engine.session.resources.get('speed_clock') is self:
                    self.engine.session.resources.pop('speed_clock')
            raise

    def _attach(self):
        session=self.engine.session
        with self.engine.memory_factory(self.engine.pid) as memory:
            session.prepare(memory)
            self.created=session.identity.created
        self.pe=pefile.PE(str(self.image))
        self.exports={entry.name:entry.address for entry in self.pe.DIRECTORY_ENTRY_EXPORT.symbols}
        if (self.pe.FILE_HEADER.Machine!=0x8664 or
                self.pe.get_data(self.exports.get(b'speed_clock_abi',0),16)!=struct.pack('<4I',MAGIC,1,WORK_SIZE,1000)):
            raise ValueError('Speed clock module ABI differs')
        self.unwind=self.pe.OPTIONAL_HEADER.DATA_DIRECTORY[3]
        if not self.unwind.Size or self.unwind.Size%12:
            raise ValueError('Speed clock unwind table missing')
        self.handle=transport.p['open_process'](0x143a,False,self.engine.pid)
        if not self.handle:raise c.WinError(c.get_last_error())
        self._validate()
        self.base=self._discover()
        if self.base:
            self.pinned=True
            actual=transport.bytes_at(self.handle,self.base+self.exports[b'speed_clock_abi'],16)
            if actual!=struct.pack('<4I',MAGIC,1,WORK_SIZE,1000):
                raise ResidentClockMismatch('Resident timing ABI differs')
            header=transport.bytes_at(self.handle,self.base,4096)
            offset=struct.unpack_from('<I',header,60)[0]
            if (offset+88>len(header) or header[:2]!=b'MZ' or header[offset:offset+4]!=b'PE\0\0'
                    or struct.unpack_from('<I',header,offset+8)[0]!=self.pe.FILE_HEADER.TimeDateStamp
                    or struct.unpack_from('<I',header,offset+80)[0]!=self.pe.OPTIONAL_HEADER.SizeOfImage):
                raise ResidentClockMismatch('Resident timing image generation differs')
            mapped=self.pe.get_memory_mapped_image(ImageBase=self.base)
            for section in self.pe.sections:
                if section.Characteristics&0x20000000:
                    address=section.VirtualAddress;length=section.Misc_VirtualSize
                    if transport.bytes_at(self.handle,self.base+address,length)!=mapped[address:address+length]:
                        raise ResidentClockMismatch('Resident timing executable section differs')
            return self.query()
        file=section=None
        try:
            file=transport.x['create_file'](str(self.image),0x80000000,5,None,3,0x80,None)
            if file==transport.P(-1).value:file=None;raise c.WinError(c.get_last_error())
            section=transport.x['create_mapping'](file,None,0x1000002,0,0,None)
            if not section:raise c.WinError(c.get_last_error())
            view=transport.P();size=transport.Z()
            status=transport.x['map_section'](section,self.handle,c.byref(view),0,0,None,c.byref(size),2,0,2)
            if status<0 or not view.value:raise RuntimeError('Timing module mapping failed: '+hex(status&0xffffffff))
            self.base=view.value
            transport.initialize_mapped_imports(SimpleNamespace(handle=self.handle,pid=self.engine.pid),self.base,self.pe)
            return self.query()
        finally:
            if section:transport.p['close'](section)
            if file:transport.p['close'](file)

    def _call(self,action,rate=1000):
        if getattr(self,'incompatible_resident',False):
            raise ResidentClockMismatch('No control dispatch permitted against an incompatible resident')
        self._validate()
        if self.uncertain:raise RuntimeError('Timing control completion unknown; no automatic replay')
        payload=struct.pack('<4I2Q2I8I2Q',MAGIC,WORK_SIZE,action,rate,
                            self.base,self.base+self.unwind.VirtualAddress,self.unwind.Size//12,0,
                            *([0]*8),0,0)
        block=transport.p['alloc'](self.handle,None,WORK_SIZE,0x3000,4)
        if not block:raise c.WinError(c.get_last_error())
        completed=False
        health_report=None
        try:
            data=c.create_string_buffer(payload);written=transport.Z()
            if not transport.p['write'](self.handle,block,data,len(payload),c.byref(written)) or written.value!=len(payload):
                raise c.WinError(c.get_last_error())
            self.uncertain=True
            transport.remote_thread_call(self.handle,self.base+self.exports[b'SpeedControl'],block,5000)
            completed=True
            raw=transport.bytes_at(self.handle,block,WORK_SIZE)
            if raw[:40]!=payload[:40]:
                raise RuntimeError('Timing response identity differs')
            init,installed,current,error,done,pinned,hook_status,mask=struct.unpack_from('<8I',raw,40)
            qpc_calls,tick_calls=struct.unpack_from('<2Q',raw,72)
            self.pinned=bool(pinned)
            self.last_result=dict(initialized=bool(init),installed=bool(installed),rate=current/1000,
                error=error,completed=bool(done),pinned=bool(pinned),hook_status=hook_status,
                hook_mask=mask,qpc_calls=qpc_calls,tick_calls=tick_calls,image_base=hex(self.base))
            inactive_failure=(not init and not installed and not mask and pinned==1 and current==1000
                              and error==50 and not done)
            if inactive_failure:
                # No hook reached the enable step. Other feature backends stay
                # usable; keep the registered image resident but disable speed.
                self.uncertain=False
                detail={7:'计时接口地址没有执行权限',8:'当前系统计时入口不支持此加速方式',
                    9:'系统未能分配加速组件所需内存',10:'系统拒绝修改计时入口的内存保护',
                    11:'游戏进程未加载所需计时库',12:'系统缺少所需计时接口'}.get(
                        hook_status,'加速组件初始化失败')
                self.unavailable_reason=detail+'；本次未开启加速，其他功能仍可使用。'
                self.engine.session.last_evidence=OperationEvidence(delivered=True,callback_exited=True)
                raise RuntimeError(self.unavailable_reason)
            known_health_failure=(error in (5023,170) and done==1 and init==1 and installed==1
                and pinned==1 and current>=1000 and mask&7==7 and not mask&~15)
            if known_health_failure:
                self.uncertain=False
                self.engine.session.last_evidence=OperationEvidence(delivered=True,callback_exited=True)
                message=('加速控制正在更新，请稍后重试；其他功能仍可使用。' if error==170 else
                    '加速计时组件未通过生效检查，请重新开启加速；其他功能仍可使用。')
                health_report=dict(operation='game_speed',clock_state=dict(self.last_result),
                    cause='control_busy' if error==170 else 'clock_health_failed',
                    verification=dict(worker_exited=True,uncertain=False,cleanup_complete=False))
                raise TimingHealthError(message,health_report)
            state_invalid=(any(value not in (0,1) for value in (init,installed,done,pinned))
                or current<1000 or mask&~15
                or (installed and (not init or not pinned or mask&7!=7))
                or (init and not installed and pinned and mask))
            self.uncertain=bool(error) or not done
            if error or not done or state_invalid or (action==1 and (not installed or current!=rate or mask&7!=7)):
                self.uncertain=True
                raise RuntimeError('Timing control failed: '+str(self.last_result))
            self.uncertain=False
            if pinned and not init and not installed and not mask:
                self.unavailable_reason='游戏中已有未能启动的加速组件，请重开游戏后再试；其他功能仍可使用。'
            self.engine.session.last_evidence=OperationEvidence(delivered=True,readback_verified=True,
                callback_exited=True,cleanup_complete=False)
            return dict(self.last_result)
        finally:
            release_error=None
            # A timeout can leave the worker accessing this allocation.
            if completed or not self.uncertain:
                if not transport.p['free'](self.handle,block,0,0x8000):
                    self.uncertain=True
                    release_error=c.WinError(c.get_last_error())
                if not self.uncertain:
                    self.engine.session.last_evidence.cleanup_complete=True
            if self.uncertain:
                self.engine.session.uncertain=True
                self.engine.session.last_evidence=OperationEvidence(uncertain=True,callback_exited=completed)
                self.engine.session.retained['speed_clock']=dict(self.last_result,base=hex(self.base),
                    command_block=hex(block) if not completed or release_error else None)
            if health_report is not None:
                health_report['verification'].update(uncertain=self.uncertain,
                    cleanup_complete=not self.uncertain and release_error is None)
            if release_error is not None:raise release_error

    def query(self):return self._call(0)

    def set_rate(self,factor):
        encoded=encode_speed_factor(factor)
        if getattr(self,'unavailable_reason',None):raise RuntimeError(self.unavailable_reason)
        return self._call(1,encoded)

    def close(self):
        if not self.handle:return {'closed':True}
        if not self._alive():
            transport.p['close'](self.handle);self.handle=None;self.base=0
            return {'closed':True,'process_exited':True}
        if getattr(self,'incompatible_resident',False):
            transport.p['close'](self.handle);self.handle=None
            return {'closed':True,'restored_rate':None,'resident_until_process_exit':True,
                    'restart_required_for_speed':True}
        if self.uncertain:raise RuntimeError('Timing cleanup uncertain; image remains mapped')
        if self.pinned:
            if not getattr(self,'unavailable_reason',None):
                result=self.set_rate(1)
                if result['rate']!=1:raise RuntimeError('Timing restoration unverified')
        elif self.base:
            status=transport.x['unmap_section'](self.handle,transport.P(self.base))
            if status<0:raise RuntimeError('Unused timing image unmap failed')
            self.base=0
        transport.p['close'](self.handle);self.handle=None
        return {'closed':True,'restored_rate':1,'resident_until_process_exit':self.pinned}
