"""Diagnostic-build-only timer for measuring actual game-time progression."""
import struct
import time
from war3_world_effect_protocol import SIGNATURES, build_work

TIMER_SIGNATURES=(('CreateTimer','()Htimer;'),('TimerStart','(Htimer;RBC)V'),
                  ('TimerGetElapsed','(Htimer;)R'),('DestroyTimer','(Htimer;)V'))


class GameTimerProbe:
    def __init__(self,engine):self.engine=engine;self.timer=None

    def action(self,action):
        engine=self.engine
        def build(entries,tls):
            payload=bytearray(build_work(entries,tls,0xfffffff9,1,
                success_limit=action,resolver=engine._effect_resolver))
            for offset,(name,signature) in zip((480,496,504,512),TIMER_SIGNATURES):
                if entries[name].signature!=signature:raise ValueError('Timer ABI differs: '+name)
                struct.pack_into('<Q',payload,offset,entries[name].handler)
            if self.timer is not None:struct.pack_into('<Q',payload,488,self.timer)
            return bytes(payload)
        def decode(payload,_count):
            error=struct.unpack_from('<I',payload,640)[0]
            if error:raise RuntimeError(f'Timer diagnostic failed: {error}')
            if action==0:return struct.unpack_from('<Q',payload,32)[0]
            if action==1:return struct.unpack_from('<f',payload,624)[0]
        return engine._execute('world_effect',tuple(n for n,_ in SIGNATURES+TIMER_SIGNATURES),
                               build,decode,{'diagnostic_timer':action})

    def start(self):self.timer=self.action(0);return self

    def measure(self,seconds=0.8):
        before=self.action(1);start=time.perf_counter();time.sleep(seconds)
        after=self.action(1);wall=time.perf_counter()-start
        return {'game_seconds':after-before,'wall_seconds':wall,'ratio':(after-before)/wall}

    def close(self):
        if self.timer is not None:self.action(2);self.timer=None
