/* Process-local affine clocks. A used image stays resident at 1x on restoration:
   unloading it would make time jump backwards and invalidate live trampolines. */
#include <windows.h>
#include <stdint.h>
#include "../third_party/minhook/include/MinHook.h"

void *memcpy(void *destination,const void *source,size_t count){
    unsigned char *d=destination;const unsigned char *s=source;
    for(size_t i=0;i<count;++i)d[i]=s[i];return destination;
}
void *memset(void *destination,int value,size_t count){
    unsigned char *d=destination;for(size_t i=0;i<count;++i)d[i]=(unsigned char)value;
    return destination;
}

typedef struct Clock {uint64_t real_anchor,virtual_anchor;} Clock;
typedef struct SpeedWork {
    uint32_t magic,size,action,rate;
    uint64_t image_base,unwind_table;
    uint32_t unwind_count,reserved;
    uint32_t initialized,installed,current_rate,error,completed,pinned,hook_status,hook_mask;
    uint64_t qpc_calls,tick_calls;
} SpeedWork;
_Static_assert(sizeof(SpeedWork)==88,"Speed clock ABI");
__declspec(dllexport) const uint32_t speed_clock_abi[4]={0x57435331u,1u,88u,1000u};

static SRWLOCK state_lock=SRWLOCK_INIT;
static volatile LONG control_busy;
static volatile LONG64 qpc_calls,tick_calls;
static uint32_t initialized,installed,pinned,rate=1000,hook_mask;
static BOOL (WINAPI *real_qpc)(LARGE_INTEGER *);
static ULONGLONG (WINAPI *real_tick64)(void);
static DWORD (WINAPI *real_tick32)(void), (WINAPI *real_time)(void);
static Clock qpc,tick64,tick32,mm_time;
static void *targets[4];
static HANDLE registry_handle;
static uint64_t *registry_view;
static uint32_t table_registered;

static uint64_t ScaleDelta(uint64_t delta,uint32_t factor){
    uint64_t whole=delta/1000,part=(delta%1000)*factor/1000;
    if(whole>(UINT64_MAX-part)/factor)return UINT64_MAX;
    return whole*factor+part;
}
static uint64_t ClockValue(Clock *clock,uint64_t now){
    uint64_t delta=now>=clock->real_anchor?now-clock->real_anchor:0;
    uint64_t scaled=ScaleDelta(delta,rate);
    return scaled>UINT64_MAX-clock->virtual_anchor?UINT64_MAX:clock->virtual_anchor+scaled;
}
static BOOL WINAPI ScaledQpc(LARGE_INTEGER *out){
    LARGE_INTEGER now;
    AcquireSRWLockShared(&state_lock);
    BOOL ok=real_qpc(&now);
    if(ok)out->QuadPart=(LONGLONG)ClockValue(&qpc,(uint64_t)now.QuadPart);
    ReleaseSRWLockShared(&state_lock);
    InterlockedIncrement64(&qpc_calls);return ok;
}
static ULONGLONG WINAPI ScaledTick64(void){
    AcquireSRWLockShared(&state_lock);
    uint64_t value=ClockValue(&tick64,real_tick64());
    ReleaseSRWLockShared(&state_lock);InterlockedIncrement64(&tick_calls);return value;
}
static DWORD WINAPI ScaledTick32(void){
    AcquireSRWLockShared(&state_lock);
    DWORD value=(DWORD)ClockValue(&tick32,real_tick64());
    ReleaseSRWLockShared(&state_lock);InterlockedIncrement64(&tick_calls);return value;
}
static DWORD WINAPI ScaledTime(void){
    AcquireSRWLockShared(&state_lock);
    DWORD value=(DWORD)ClockValue(&mm_time,real_tick64());
    ReleaseSRWLockShared(&state_lock);InterlockedIncrement64(&tick_calls);return value;
}
static void ChangeRate(uint32_t next){
    AcquireSRWLockExclusive(&state_lock);
    LARGE_INTEGER now;real_qpc(&now);
    uint64_t ms=real_tick64();
    Clock *clocks[4]={&qpc,&tick64,&tick32,&mm_time};
    for(uint32_t i=0;i<4;++i){
        uint64_t current=i?ms:(uint64_t)now.QuadPart;
        clocks[i]->virtual_anchor=ClockValue(clocks[i],current);
        clocks[i]->real_anchor=current;
    }
    rate=next;ReleaseSRWLockExclusive(&state_lock);
}
static FARPROC ExistingExport(const wchar_t *module,const char *name){
    HMODULE handle=GetModuleHandleW(module);return handle?GetProcAddress(handle,name):NULL;
}
static uint32_t CreateClockHooks(void){
    MH_STATUS status=MH_Initialize();
    if(status!=MH_OK)return status;
    /* Keep ntdll's framed QPC prologue and its unwind metadata untouched.
       The public kernel32 forwarding thunk has no stolen stack operations. */
    targets[0]=(void *)ExistingExport(L"kernel32.dll","QueryPerformanceCounter");
    if(!targets[0] || !(((uint8_t *)targets[0])[0]==0xff && ((uint8_t *)targets[0])[1]==0x25) &&
       !(((uint8_t *)targets[0])[0]==0x48 && ((uint8_t *)targets[0])[1]==0xff && ((uint8_t *)targets[0])[2]==0x25)){
        MH_Uninitialize();return MH_ERROR_UNSUPPORTED_FUNCTION;
    }
    targets[1]=(void *)ExistingExport(L"kernel32.dll","GetTickCount64");
    targets[2]=(void *)ExistingExport(L"kernel32.dll","GetTickCount");
    targets[3]=(void *)ExistingExport(L"winmm.dll","timeGetTime");
    void *detours[4]={ScaledQpc,ScaledTick64,ScaledTick32,ScaledTime};
    void **originals[4]={(void **)&real_qpc,(void **)&real_tick64,(void **)&real_tick32,(void **)&real_time};
    for(uint32_t i=0;i<4;++i){
        if(!targets[i]){if(i<3){status=MH_ERROR_FUNCTION_NOT_FOUND;goto failed;}continue;}
        status=MH_CreateHook(targets[i],detours[i],originals[i]);
        if(status!=MH_OK)goto failed;
        hook_mask|=1u<<i;
    }
    LARGE_INTEGER now;real_qpc(&now);uint64_t ms=real_tick64();
    qpc.real_anchor=qpc.virtual_anchor=(uint64_t)now.QuadPart;
    tick64.real_anchor=tick64.virtual_anchor=ms;
    tick32.real_anchor=mm_time.real_anchor=ms;
    tick32.virtual_anchor=real_tick32();mm_time.virtual_anchor=real_time?real_time():tick32.virtual_anchor;
    initialized=1;return MH_OK;
failed:
    MH_Uninitialize();hook_mask=0;return status;
}
static void AppendHex(wchar_t *out,uint64_t value,uint32_t digits){
    static const wchar_t hex[]=L"0123456789abcdef";
    for(uint32_t i=0;i<digits;++i)out[i]=hex[(value>>((digits-1-i)*4))&15];
}
static uint32_t Publish(SpeedWork *w){
    FILETIME created,exit,kernel,user;
    if(!GetProcessTimes(GetCurrentProcess(),&created,&exit,&kernel,&user))return GetLastError();
    uint64_t stamp=((uint64_t)created.dwHighDateTime<<32)|created.dwLowDateTime;
    wchar_t name[80]=L"Local\\War3TrainerClock-";
    uint32_t offset=0;while(name[offset])++offset;
    AppendHex(name+offset,GetCurrentProcessId(),8);offset+=8;name[offset++]=L'-';
    AppendHex(name+offset,stamp,16);offset+=16;name[offset]=0;
    registry_handle=CreateFileMappingW(INVALID_HANDLE_VALUE,NULL,PAGE_READWRITE,0,64,name);
    if(!registry_handle)return GetLastError();
    if(GetLastError()==ERROR_ALREADY_EXISTS){CloseHandle(registry_handle);registry_handle=NULL;return ERROR_ALREADY_EXISTS;}
    registry_view=MapViewOfFile(registry_handle,FILE_MAP_WRITE,0,0,64);
    if(!registry_view){DWORD error=GetLastError();CloseHandle(registry_handle);registry_handle=NULL;return error;}
    registry_view[0]=0x57435331u;registry_view[1]=GetCurrentProcessId();
    registry_view[2]=stamp;registry_view[3]=w->image_base;registry_view[4]=1;
    MemoryBarrier();return 0;
}
__declspec(dllexport) DWORD WINAPI SpeedControl(void *payload){
    SpeedWork *w=payload;
    if(!w || w->magic!=0x57435331u || w->size!=sizeof(*w) || w->action>1 ||
       w->rate<1000 || w->reserved)return ERROR_INVALID_PARAMETER;
    if(InterlockedCompareExchange(&control_busy,1,0)!=0){w->error=ERROR_BUSY;return ERROR_BUSY;}
    if(w->action==1 && !initialized){
        typedef BOOLEAN (WINAPI *AddTable)(PRUNTIME_FUNCTION,DWORD,DWORD64);
        AddTable add=(AddTable)ExistingExport(L"ntdll.dll","RtlAddFunctionTable");
        if(!table_registered && (!w->image_base || !w->unwind_table || !w->unwind_count || !add ||
           !add((PRUNTIME_FUNCTION)(uintptr_t)w->unwind_table,w->unwind_count,w->image_base))){
            w->error=ERROR_INVALID_DATA;goto done;
        }
        table_registered=1;
        pinned=1;
        if(!registry_handle){w->error=Publish(w);if(w->error)goto done;}
        w->hook_status=CreateClockHooks();
        if(w->hook_status!=MH_OK){w->error=ERROR_NOT_SUPPORTED;goto done;}
    }
    if(w->action==1){
        ChangeRate(w->rate);
        if(!installed){
            /* Even a partially enabled batch owns code that must stay mapped. */
            pinned=1;
            w->hook_status=MH_EnableHook(MH_ALL_HOOKS);
            if(w->hook_status!=MH_OK){ChangeRate(1000);w->error=ERROR_NOT_SUPPORTED;goto done;}
            installed=1;
        }
    }
    w->completed=1;
done:
    w->initialized=initialized;w->installed=installed;w->current_rate=rate;
    w->pinned=pinned;w->hook_mask=hook_mask;
    w->qpc_calls=(uint64_t)InterlockedCompareExchange64(&qpc_calls,0,0);
    w->tick_calls=(uint64_t)InterlockedCompareExchange64(&tick_calls,0,0);
    InterlockedExchange(&control_busy,0);return w->error;
}
BOOL WINAPI DllMain(HINSTANCE instance,DWORD reason,LPVOID reserved){
    (void)instance;(void)reason;(void)reserved;return TRUE;
}
