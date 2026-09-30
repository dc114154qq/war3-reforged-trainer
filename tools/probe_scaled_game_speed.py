"""Measure a bounded game speed change, then restore the original timing rate."""
import argparse
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from war3_reforged_trainer import War3Trainer
from war3_speed_clock_backend import SpeedClockBackend
from game_timer_probe import GameTimerProbe


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid',type=int,required=True)
    parser.add_argument('--clock',type=Path,required=True)
    parser.add_argument('--bridge',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--observe-seconds',type=float,default=0)
    parser.add_argument('--accelerated-seconds',type=float,default=0)
    args=parser.parse_args()
    trainer=War3Trainer(args.pid)
    engine=trainer._engine_instance_24268();engine.image=args.bridge.resolve()
    clock=SpeedClockBackend(engine,args.clock)
    timer=None;original=None;result={}
    try:
        result['clock_before']=clock.attach();original=result['clock_before']['rate']
        result['game_profile']=engine.session.profile.id
        timer=GameTimerProbe(engine).start()
        result['before']=timer.measure()
        if result['before']['ratio']<0.5:
            raise RuntimeError('Game time is not advancing; no acceleration installed')
        from war3_engine_transport import resolve
        with engine.memory_factory(engine.pid) as memory:
            native_qpc=resolve(memory,'ntdll','RtlQueryPerformanceCounter')
            original_code=memory.read(native_qpc,32)
        result['set']=clock.set_rate(2)
        with engine.memory_factory(engine.pid) as memory:
            result['native_qpc_unchanged']=memory.read(native_qpc,32)==original_code
        if not result['native_qpc_unchanged']:raise RuntimeError('Native QPC was unexpectedly modified')
        result['during']=timer.measure()
        active_started=time.perf_counter();active_last=active_started
        while time.perf_counter()-active_started<args.accelerated_seconds:
            if not clock._alive():raise RuntimeError('Game exited during sustained acceleration')
            time.sleep(0.5)
            active_now=time.perf_counter()
            if active_now-active_last>=20:
                print(json.dumps({'accelerated_alive_seconds':round(active_now-active_started,1)}),flush=True)
                active_last=active_now
        result['sustained_acceleration_seconds']=time.perf_counter()-active_started
        result['sustained_measurement']=timer.measure()
        result['observed_hooks']=clock.query()
        result['restore']=clock.set_rate(original)
        result['after']=timer.measure()
        baseline=result['before']['ratio']
        actual=result['during']['ratio']/baseline if baseline>0 else 0
        restored=result['after']['ratio']/baseline if baseline>0 else 0
        result['relative_acceleration']=actual
        result['relative_restoration']=restored
        result['effect_verified']=1.7<actual<2.3 and 0.85<restored<1.15
        print(json.dumps({'short_test':result['effect_verified'],'relative_acceleration':actual,
                          'native_qpc_unchanged':result['native_qpc_unchanged']}),flush=True)
        started=time.perf_counter();last_update=started
        while time.perf_counter()-started<args.observe_seconds:
            if not clock._alive():raise RuntimeError('Game exited during delayed stability observation')
            time.sleep(0.5)
            now=time.perf_counter()
            if now-last_update>=30:
                print(json.dumps({'alive_observation_seconds':round(now-started,1)}),flush=True)
                last_update=now
        result['alive_observation_seconds']=time.perf_counter()-started
        result['stability_observation_passed']=clock._alive()
    finally:
        try:
            if clock._alive():
                if original is not None:result['final_restore']=clock.set_rate(original)
                if timer is not None:timer.close()
            else:result['process_exited']=True
        finally:trainer.close()
        args.output.parent.mkdir(parents=True,exist_ok=True)
        pending=args.output.with_suffix('.tmp')
        pending.write_text(json.dumps(result,indent=2),encoding='utf-8');pending.replace(args.output)
    print(json.dumps(result))
    if not result.get('effect_verified'):raise SystemExit('Actual game-time acceleration not verified')


if __name__=='__main__':main()
