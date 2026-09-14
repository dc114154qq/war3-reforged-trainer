"""Refresh all production native bindings across synthetic context changes."""
import ctypes
import hashlib
import json
from pathlib import Path
import re
import shutil
import statistics
import subprocess

import pytest
import war3_reforged_trainer as module
from test_native_identity_guard import HARNESS

PREFIX=r'''
#include <stdint.h>
static uint8_t *refresh_image;
static HMODULE refresh_module(LPCWSTR name) {return refresh_image?(HMODULE)refresh_image:GetModuleHandleW(name);}
#define GetModuleHandleW refresh_module
'''

REFRESH=r'''
#define REFRESH_COUNT (sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]))
static uint8_t refresh_contexts[2][0x80],refresh_buckets[2][128*24],refresh_nodes[2][REFRESH_COUNT][0x48];
static unsigned refresh_current,refresh_missing,refresh_hashes;
static void *refresh_context(int32_t which) {
    if(which!=5) ++bad_arguments;
    return refresh_missing?NULL:refresh_contexts[refresh_current];
}
static uint32_t refresh_hash(const char *name) {
    ++refresh_hashes;
    for(unsigned n=0;n<REFRESH_COUNT;++n) if(!strcmp(name,g_persistent_native_names[n])) return n+1;
    ++bad_arguments;return 0;
}
static void refresh_jump(uint8_t *code,void *target) {
    code[0]=0x48;code[1]=0xb8;memcpy(code+2,&target,8);code[10]=0xff;code[11]=0xe0;
}
__declspec(dllexport) DWORD refresh_test(const uint8_t *code,unsigned size,unsigned failure,unsigned repeats,uint64_t *out) {
    if(size!=REFRESH_COUNT*64 || repeats<1 || repeats>10000) return ERROR_INVALID_PARAMETER;
    uint32_t image_size=0;
    for(unsigned n=0;n<REFRESH_COUNT;++n) {
        int i=war3_bootstrap_index(g_persistent_native_names[n]);
        if(i<0) return ERROR_PROC_NOT_FOUND;
        if(g_bootstrap_names[i].rva+4096>image_size) image_size=g_bootstrap_names[i].rva+4096;
    }
    refresh_image=VirtualAlloc(NULL,image_size,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);
    if(!refresh_image) return ERROR_OUTOFMEMORY;
    ZeroMemory(refresh_contexts,sizeof(refresh_contexts));ZeroMemory(refresh_buckets,sizeof(refresh_buckets));
    ZeroMemory(refresh_nodes,sizeof(refresh_nodes));refresh_hashes=refresh_current=refresh_missing=bad_arguments=0;
    refresh_jump(refresh_image+WAR3_BOOTSTRAP_CONTEXT_RVA,(void *)refresh_context);
    refresh_jump(refresh_image+WAR3_BOOTSTRAP_HASH_RVA,(void *)refresh_hash);
    for(unsigned n=0;n<REFRESH_COUNT;++n) {
        int i=war3_bootstrap_index(g_persistent_native_names[n]);
        memcpy(refresh_image+g_bootstrap_names[i].rva,code+n*64,64);
        for(unsigned c=0;c<2;++c) {
            uint8_t *table=refresh_contexts[c]+0x28,*bucket=refresh_buckets[c]+(n+1)*24,*node=refresh_nodes[c][n];
            *(uint32_t *)(table+0x40)=127;*(uint8_t **)(table+0x30)=refresh_buckets[c];
            *(uintptr_t *)(bucket+0x10)=(uintptr_t)node;
            *(uint32_t *)node=n+1;*(uintptr_t *)(node+8)=1;
            *(const char **)(node+0x28)=g_bootstrap_names[i].name;
            *(uint64_t *)(node+0x30)=(uint64_t)(uintptr_t)(refresh_image+g_bootstrap_names[i].rva);
            *(const char **)(node+0x40)=g_bootstrap_names[i].signature;
        }
    }
    FlushInstructionCache(GetCurrentProcess(),refresh_image,image_size);
    /* Model a previously validated module; validate_image is tested separately.
       Only the context/name-hash stubs execute; native code is fingerprint data. */
    g_bootstrap_module=refresh_image;
    DWORD error=war3_bootstrap_refresh();out[0]=error;
    if(error) goto finish;
    uint64_t previous[REFRESH_COUNT];
    for(unsigned n=0;n<REFRESH_COUNT;++n) {
        previous[n]=g_persistent_natives[n].handler;
        if(failure>=2) g_persistent_natives[n].handler=previous[n]=0x20000+n*0x100;
    }
    refresh_current=failure?1:0;refresh_missing=failure==2;
    unsigned index=failure==3?0:failure==4?REFRESH_COUNT/2:REFRESH_COUNT-1;
    uint8_t *node=refresh_nodes[1][index],*bucket=refresh_buckets[1]+(index+1)*24;
    int profile=war3_bootstrap_index(g_persistent_native_names[index]);
    if(failure>=3 && failure<=5) *(uintptr_t *)(bucket+0x10)=1;
    if(failure==6) *(const char **)(node+0x40)="wrong-signature";
    if(failure==7) *(uint64_t *)(node+0x30)+=1;
    if(failure==8) refresh_image[g_bootstrap_names[profile].rva+63]^=1;
    if(failure==9) *(uint32_t *)(refresh_contexts[1]+0x28+0x40)=5;
    if(failure==10) {*(const char **)(node+0x28)="collision";*(uintptr_t *)(node+8)=(uintptr_t)node;}
    refresh_hashes=0;LARGE_INTEGER a,b,freq;QueryPerformanceFrequency(&freq);QueryPerformanceCounter(&a);
    for(unsigned n=0;n<repeats;++n) {error=war3_bootstrap_refresh();if(error) break;}
    QueryPerformanceCounter(&b);
    out[1]=error;out[2]=g_persistent_ready;out[3]=1;
    for(unsigned n=0;n<REFRESH_COUNT;++n) if(g_persistent_natives[n].handler!=previous[n]) out[3]=0;
    out[4]=refresh_hashes;out[5]=(uint64_t)((b.QuadPart-a.QuadPart)*1000000000ULL/freq.QuadPart);
    /* Restore the first context and original code. A failed refresh must be
       recoverable without cached second-context records. */
    if(failure==8) refresh_image[g_bootstrap_names[profile].rva+63]^=1;
    refresh_current=refresh_missing=0;out[6]=war3_bootstrap_refresh();out[7]=g_persistent_ready;
    out[8]=1;
    for(unsigned n=0;n<REFRESH_COUNT;++n) {
        int i=war3_bootstrap_index(g_persistent_native_names[n]);
        if(g_persistent_natives[n].handler!=(uint64_t)(uintptr_t)(refresh_image+g_bootstrap_names[i].rva)) out[8]=0;
    }
finish:
    out[9]=bad_arguments;g_bootstrap_module=NULL;g_persistent_ready=0;
    VirtualFree(refresh_image,0,MEM_RELEASE);refresh_image=NULL;
    return error;
}
'''


@pytest.fixture(scope='module')
def refresh_native(tmp_path_factory):
    compiler=shutil.which('clang')
    if not compiler:pytest.skip('clang required')
    root=tmp_path_factory.mktemp('bootstrap-refresh');source=root/'test.c';library=root/'test.dll'
    harness=HARNESS.replace('#include "HELPER_SOURCE"',PREFIX+'\n#include "HELPER_SOURCE"\n#undef GetModuleHandleW')
    source.write_text(harness.replace('HELPER_SOURCE',(Path(__file__).parent/'analysis/fixtures/legacy-native-helper.c').as_posix())+REFRESH,encoding='utf8')
    subprocess.run([compiler,'-shared','-O2','-Wno-microsoft-goto',str(source),'-o',str(library),'-luser32','-lkernel32'],check=True,capture_output=True,timeout=60)
    lib=ctypes.CDLL(str(library));lib.refresh_test.argtypes=[ctypes.c_void_p,*([ctypes.c_uint]*3),ctypes.POINTER(ctypes.c_uint64)]
    lib.refresh_test.restype=ctypes.c_uint
    yield lib
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)


@pytest.fixture(scope='module')
def binding_code():
    root=Path(__file__).parent
    evidence=root/'analysis/native-bootstrap-20260907/module-text.bin'
    if not evidence.exists():pytest.skip('Captured text evidence unavailable')
    code=evidence.read_bytes()
    assert hashlib.sha256(code).hexdigest()=='0b62fa80e351e996e70addb66c5d3c8a818304ec6aa8dcf5fe6c0886cca4127c'
    profile=(root/'tools/war3_native_bootstrap_profile.h').read_text()
    rvas={name:int(rva,16) for name,rva in re.findall(r'\{"([^"]+)", "[^"]+", 0x([0-9a-f]+)u,',profile)}
    data=b''.join(code[rvas[name]-4096:rvas[name]-4096+64] for name in module.War3Trainer.PERSISTENT_NATIVE_NAMES)
    assert len(data)==55*64
    return data


def run(refresh_native,binding_code,failure=0,repeats=1):
    buf=ctypes.create_string_buffer(binding_code);out=(ctypes.c_uint64*10)()
    error=refresh_native.refresh_test(buf,len(binding_code),failure,repeats,out)
    assert out[0]==out[9]==0
    assert out[6]==0 and out[7]==out[8]==1
    return error,out


@pytest.mark.parametrize('failure',range(11))
def test_refresh_revalidates_current_context_and_never_publishes_partial_bindings(refresh_native,binding_code,failure):
    error,out=run(refresh_native,binding_code,failure)
    assert bool(error)==(failure>=2)
    assert out[2]==int(failure<2) and out[3]==1
    if failure<2:assert out[4]==55
    elif failure==2:assert out[4]==0
    elif failure==3:assert out[4]==1
    elif failure==4:assert out[4]==28
    else:assert out[4]<=55


def test_report_refresh_cost_without_latency_pass_threshold(refresh_native,binding_code):
    samples=[]
    for _ in range(5):
        error,out=run(refresh_native,binding_code,repeats=1000)
        assert error==0 and out[4]==55000
        samples.append(out[5]/1000/1000)
    report={'native_count':55,'iterations_per_sample':1000,'samples_us_per_refresh':samples,
            'median_us_per_refresh':statistics.median(samples),'min_us':min(samples),'max_us':max(samples),
            'scope':'Synthetic 55-bucket table, real captured native fingerprints; stub context getter and name hash. Not game latency.'}
    print('\nBOOTSTRAP_REFRESH_MEASUREMENT '+json.dumps(report))
