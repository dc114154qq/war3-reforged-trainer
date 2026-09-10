"""Offline production-guard cost; synthetic object tables, no game attachment."""
import ctypes
import json
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from test_native_identity_guard import HARNESS
from test_native_clone_unit_guard import CLONE

BENCH = r'''
__declspec(dllexport) DWORD clone_guard_cost(unsigned iterations,unsigned items,double *out) {
    NativeCommand source={0};War3CloneGuard guard={0};LARGE_INTEGER start,end,frequency;
    source.unit_handle=7;source.ops[0].kind=WAR3_NATIVE_OP_VALIDATE_UNIT_IDENTITY;
    source.ops[0].handler=(uint64_t)(uintptr_t)object;source.ops[0].arg0=full;
    source.ops[0].arg1=(uint64_t)(uintptr_t)owner;guard.source=&source;
    __try {
        DWORD error=war3_clone_capture_target(&guard,8);if(error) return error;
        if(items) {
            war3_clone_prepare_items(&guard,clone_slot);
            war3_clone_begin_item(&guard,0);
            war3_clone_track_item(&guard,0,80,0x49303031);
        }
        unsigned before=clone_calls;
        QueryPerformanceFrequency(&frequency);QueryPerformanceCounter(&start);
        for(unsigned n=0;n<iterations;++n) war3_clone_check(&guard);
        QueryPerformanceCounter(&end);
        out[0]=(double)(end.QuadPart-start.QuadPart)/frequency.QuadPart/iterations*1000000.0;
        out[1]=clone_calls-before;
    } __except(EXCEPTION_EXECUTE_HANDLER) {return GetExceptionCode();}
    return 0;
}
'''

with tempfile.TemporaryDirectory(prefix='war3-clone-cost-') as temporary:
    folder = Path(temporary)
    source = folder/'bench.c'
    library = folder/'bench.dll'
    source.write_text(HARNESS.replace('HELPER_SOURCE', (ROOT/'tools/war3_native_helper.c').as_posix()) + CLONE + BENCH, encoding='utf8')
    result = subprocess.run([shutil.which('clang'), '-shared', '-O2', '-Wno-microsoft-goto', str(source), '-o', str(library), '-luser32', '-lkernel32'], capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError(result.stderr[-4000:])
    native = ctypes.CDLL(str(library))
    try:
        native.clone_test.argtypes = [ctypes.c_wchar_p, *([ctypes.c_uint]*3), ctypes.POINTER(ctypes.c_uint)]
        native.clone_test.restype = ctypes.c_uint
        native.clone_guard_cost.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_double)]
        native.clone_guard_cost.restype = ctypes.c_uint
        state = (ctypes.c_uint*12)()
        assert native.clone_test(str(folder)+'\\', 3, 0, 0, state) == 0
        assert list(state[2:5]) == [1, 0, 1] and state[0] == 0
        report = {'scope': 'Production C guard only, synthetic native callbacks/object tables; excludes IPC, game engine work and live latency.'}
        for items in (0, 1):
            samples = []
            for _ in range(7):
                output = (ctypes.c_double*2)()
                assert native.clone_guard_cost(2000, items, output) == 0
                assert output[1] == (4000 if items else 0)
                samples.append(output[0])
            report['unit_and_item_pair' if items else 'unit_pair'] = {
                'median_microseconds': statistics.median(samples),
                'samples_microseconds': samples,
                'slot_queries_per_check': 2 if items else 0,
            }
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        import _ctypes
        _ctypes.FreeLibrary(native._handle)
