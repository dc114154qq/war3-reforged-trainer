/* Map our import-free PE as SEC_IMAGE, invoke a diagnostic, then release our mapping. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <wchar.h>
typedef LONG (NTAPI *MapFn)(HANDLE,HANDLE,PVOID *,ULONG_PTR,SIZE_T,PLARGE_INTEGER,PSIZE_T,DWORD,ULONG,ULONG);
typedef LONG (NTAPI *UnmapFn)(HANDLE,PVOID);
typedef struct ProbeContext { void *load,*last_error,*path,*module;DWORD error,stage; } ProbeContext;
int wmain(int argc,wchar_t **argv) {
    if(argc!=4) return 2;
    DWORD pid=wcstoul(argv[1],NULL,10),exit_code=0;
    wchar_t bridge[MAX_PATH],target[MAX_PATH];
    DWORD b=GetFullPathNameW(argv[2],MAX_PATH,bridge,NULL),t=GetFullPathNameW(argv[3],MAX_PATH,target,NULL);
    if(!pid || !b || b>=MAX_PATH || !t || t>=MAX_PATH) return 3;
    HANDLE process=NULL,file=INVALID_HANDLE_VALUE,section=NULL,thread=NULL;
    HMODULE local=NULL;
    void *image=NULL,*argument=NULL;
    DWORD wait=WAIT_FAILED;SIZE_T view=0,got=0;
    MapFn map=(MapFn)(void *)GetProcAddress(GetModuleHandleW(L"ntdll.dll"),"NtMapViewOfSection");
    UnmapFn unmap=(UnmapFn)(void *)GetProcAddress(GetModuleHandleW(L"ntdll.dll"),"NtUnmapViewOfSection");
    HMODULE kernel=GetModuleHandleW(L"kernel32.dll");
    ProbeContext result={(void *)GetProcAddress(kernel,"LoadLibraryW"),
        (void *)GetProcAddress(kernel,"GetLastError"),NULL,NULL,0xffffffffu,0};
    printf("load=%p last_error=%p\n",result.load,result.last_error);
    int rc=4;
    process=OpenProcess(PROCESS_CREATE_THREAD|PROCESS_QUERY_INFORMATION|PROCESS_VM_OPERATION|PROCESS_VM_READ|PROCESS_VM_WRITE,FALSE,pid);
    if(!process || !map || !unmap) goto done;
    local=LoadLibraryExW(bridge,NULL,DONT_RESOLVE_DLL_REFERENCES);
    if(!local) goto done;
    FARPROC entry=GetProcAddress(local,"ImageProbe");
    if(!entry) goto done;
    SIZE_T entry_rva=(uint8_t *)(void *)entry-(uint8_t *)local;
    file=CreateFileW(bridge,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_DELETE,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE) goto done;
    section=CreateFileMappingW(file,NULL,PAGE_READONLY|SEC_IMAGE,0,0,NULL);
    if(!section) goto done;
    LONG status=map(section,process,&image,0,0,NULL,&view,2,0,PAGE_READONLY);
    printf("map_status=0x%lx mapped=%p view=%zu entry_rva=0x%zx\n",(DWORD)status,image,view,entry_rva);
    if(status<0 || entry_rva>=view) goto done;
    SIZE_T path_bytes=(t+1)*sizeof(wchar_t),size=sizeof(result)+path_bytes;
    argument=VirtualAllocEx(process,NULL,size,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
    if(!argument) goto done;
    result.path=(uint8_t *)argument+sizeof(result);
    if(!WriteProcessMemory(process,argument,&result,sizeof(result),NULL) ||
       !WriteProcessMemory(process,result.path,target,path_bytes,NULL)) goto done;
    thread=CreateRemoteThread(process,NULL,0,(LPTHREAD_START_ROUTINE)((uint8_t *)image+entry_rva),argument,0,NULL);
    if(!thread) goto done;
    wait=WaitForSingleObject(thread,15000);
    if(wait!=WAIT_OBJECT_0) {rc=5;goto done;}
    if(!GetExitCodeThread(thread,&exit_code) || !ReadProcessMemory(process,argument,&result,sizeof(result),&got) || got!=sizeof(result)) goto done;
    printf("pid=%lu wait=%lu exit=0x%lx stage=%lu module=%p error=%lu\n",pid,wait,exit_code,result.stage,result.module,result.error);
    rc=result.stage==2 && result.module ? 0 : 6;
done:
    if(rc) printf("diagnostic_failure=%d last_error=%lu\n",rc,GetLastError());
    if(thread && wait!=WAIT_OBJECT_0) printf("pending thread; retaining mapping and arguments\n");
    else {
        if(argument) VirtualFreeEx(process,argument,0,MEM_RELEASE);
        if(image && unmap) unmap(process,image);
    }
    if(thread) CloseHandle(thread);
    if(section) CloseHandle(section);
    if(file!=INVALID_HANDLE_VALUE) CloseHandle(file);
    if(local) FreeLibrary(local);
    if(process) CloseHandle(process);
    return rc;
}
