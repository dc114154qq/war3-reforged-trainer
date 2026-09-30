"""Persistent mapping and reconnection against a harmless child process."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from war3_reforged_trainer import ProcessMemory
from war3_game_session import process_creation
from war3_speed_clock_backend import SpeedClockBackend


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    child_code='''import ctypes as c,json,os
k=c.WinDLL('kernel32');k.QueryPerformanceCounter.argtypes=[c.POINTER(c.c_int64)]
k.QueryPerformanceFrequency.argtypes=[c.POINTER(c.c_int64)];k.Sleep.argtypes=[c.c_uint32]
f=c.c_int64();k.QueryPerformanceFrequency(c.byref(f))
print(os.getpid(),flush=True)
for line in __import__('sys').stdin:
 if line.strip()=='exit':break
 a=c.c_int64();b=c.c_int64();k.QueryPerformanceCounter(c.byref(a));k.Sleep(250);k.QueryPerformanceCounter(c.byref(b))
 print(json.dumps({'game_seconds':(b.value-a.value)/f.value}),flush=True)
'''
    child=subprocess.Popen([sys.executable,'-c',child_code],stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    clock=None
    result={}
    try:
        pid=int(child.stdout.readline())
        with ProcessMemory(pid) as memory:
            created=process_creation(memory)
        session=SimpleNamespace(resources={},retained={},identity=SimpleNamespace(pid=pid,created=created),prepare=lambda memory:None)
        engine=SimpleNamespace(pid=pid,session=session,memory_factory=ProcessMemory)
        clock=SpeedClockBackend(engine,args.image)
        result['attached']=clock.attach()
        base=clock.base
        result['set']=clock.set_rate(2)
        child.stdin.write('measure\n');child.stdin.flush()
        result['during']=json.loads(child.stdout.readline())
        assert 0.45<result['during']['game_seconds']<0.65,result
        result['closed']=clock.close()
        clock=SpeedClockBackend(engine,args.image)
        result['reconnected']=clock.attach()
        assert clock.base==base and result['reconnected']['rate']==1
        child.stdin.write('measure\n');child.stdin.flush()
        result['restored_timing']=json.loads(child.stdout.readline())
        assert 0.23<result['restored_timing']['game_seconds']<0.4,result
        result['set_again']=clock.set_rate(1.5)
        result['closed_again']=clock.close()
    finally:
        if clock is not None:clock.close()
        child.stdin.write('exit\n');child.stdin.flush()
        child.wait(timeout=10)
        child.stdin.close();child.stdout.close()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    pending=args.output.with_suffix('.tmp')
    pending.write_text(json.dumps(result,indent=2),encoding='utf-8');pending.replace(args.output)
    print(json.dumps(result))


if __name__=='__main__':main()
