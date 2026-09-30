"""Measure the compiled clock in a separate process, not the controller's clocks."""
import argparse
import ctypes as c
import json
import struct
from pathlib import Path
import pefile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    dll=c.WinDLL(str(args.image.resolve()))
    pe=pefile.PE(str(args.image))
    table=pe.OPTIONAL_HEADER.DATA_DIRECTORY[3]
    dll.SpeedControl.argtypes=[c.c_void_p];dll.SpeedControl.restype=c.c_uint32
    kernel=c.WinDLL('kernel32',use_last_error=True)
    ntdll=c.WinDLL('ntdll')
    native_address=c.cast(ntdll.RtlQueryPerformanceCounter,c.c_void_p).value
    native_before=c.string_at(native_address,32)
    kernel.Sleep.argtypes=[c.c_uint32]
    kernel.GetTickCount64.restype=c.c_uint64
    kernel.QueryPerformanceCounter.argtypes=[c.POINTER(c.c_int64)]
    kernel.QueryPerformanceFrequency.argtypes=[c.POINTER(c.c_int64)]
    frequency=c.c_int64();assert kernel.QueryPerformanceFrequency(c.byref(frequency))
    def qpc():
        value=c.c_int64();assert kernel.QueryPerformanceCounter(c.byref(value));return value.value
    def wall():
        value=c.c_uint64();kernel.GetSystemTimeAsFileTime(c.byref(value));return value.value
    def control(rate):
        payload=struct.pack('<4I2Q2I8I2Q',0x57435331,88,1,rate,dll._handle,
                            dll._handle+table.VirtualAddress,table.Size//12,0,*([0]*8),0,0)
        block=c.create_string_buffer(payload)
        error=dll.SpeedControl(block)
        state=struct.unpack_from('<8I',block.raw,40)
        assert error==0 and state[3]==0 and state[4]==1 and state[2]==rate,state
        return dict(initialized=state[0],installed=state[1],rate=state[2],pinned=state[5],mask=state[7])
    rows=[]
    last=qpc()
    try:
        for rate in (1000,1500,2000,3000,4000,8000,20000,100000,1000):
            state=control(rate)
            assert c.string_at(native_address,32)==native_before,'Native QPC code was modified'
            start_q,start_ms,start_wall=qpc(),kernel.GetTickCount64(),wall()
            assert start_q>=last
            # The millisecond clock advances in coarse Windows timer quanta.
            # A 250 ms sample magnifies that quantization error at high rates.
            kernel.Sleep(4000 if rate>4000 else 250)
            end_wall,end_ms,end_q=wall(),kernel.GetTickCount64(),qpc()
            elapsed=(end_wall-start_wall)/1e7
            q_ratio=(end_q-start_q)/frequency.value/elapsed
            tick_ratio=(end_ms-start_ms)/1000/elapsed
            assert end_q>=start_q
            assert abs(q_ratio-rate/1000)<0.12,(rate,q_ratio)
            expected=rate/1000
            tick_tolerance=(0.032*expected+0.002)/elapsed
            assert abs(tick_ratio-expected)<max(0.3,tick_tolerance),(rate,tick_ratio)
            rows.append(dict(state=state,wall_seconds=elapsed,qpc_ratio=q_ratio,tick_ratio=tick_ratio))
            last=end_q
    finally:
        restored=control(1000)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    pending=args.output.with_suffix('.tmp')
    pending.write_text(json.dumps(dict(rows=rows,restored=restored),indent=2),encoding='utf-8')
    pending.replace(args.output)
    print(json.dumps(dict(rows=rows,restored=restored)))


if __name__=='__main__':main()
