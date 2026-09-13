/* Diagnostic LoadLibrary only. Never frees an argument still used by a thread. */
#include <windows.h>
#include <stdio.h>
#include <wchar.h>
int wmain(int argc,wchar_t **argv) {
    if(argc!=3) return 2;
    DWORD pid=wcstoul(argv[1],NULL,10),exit=0;
    wchar_t path[32768];DWORD length=GetFullPathNameW(argv[2],32768,path,NULL);
    if(!pid || !length || length>=32768) return 3;
    HANDLE process=OpenProcess(PROCESS_CREATE_THREAD|PROCESS_QUERY_INFORMATION|PROCESS_VM_OPERATION|
                               PROCESS_VM_WRITE|PROCESS_VM_READ,FALSE,pid);
    if(!process) {printf("open_error=%lu\n",GetLastError());return 4;}
    SIZE_T size=(length+1)*sizeof(wchar_t),written=0;
    void *remote=VirtualAllocEx(process,NULL,size,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
    if(!remote || !WriteProcessMemory(process,remote,path,size,&written) || written!=size) {
        printf("argument_error=%lu\n",GetLastError());
        if(remote) VirtualFreeEx(process,remote,0,MEM_RELEASE);CloseHandle(process);return 5;
    }
    /* Store both the pointer-sized result and the loader's own last error. */
    struct { void *load,*last_error,*path,*module; DWORD error; } result={
        (void *)LoadLibraryW,(void *)GetLastError,remote,(void *)(uintptr_t)0x12345678u,0xffffffffu};
    unsigned char stub[]={0x53,0x48,0x83,0xec,0x20,0x48,0x89,0xcb,0x48,0x8b,0x4b,0x10,
        0xff,0x13,0x48,0x89,0x43,0x18,0xff,0x53,0x08,0x89,0x43,0x20,0x31,0xc0,
        0x48,0x83,0xc4,0x20,0x5b,0xc3};
    void *remote_result=VirtualAllocEx(process,NULL,sizeof(result),MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
    void *code=VirtualAllocEx(process,NULL,sizeof(stub),MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
    DWORD previous=0;
    if(!remote_result || !code || !WriteProcessMemory(process,remote_result,&result,sizeof(result),NULL) ||
       !WriteProcessMemory(process,code,stub,sizeof(stub),NULL) ||
       !VirtualProtectEx(process,code,sizeof(stub),PAGE_EXECUTE_READ,&previous) ||
       !FlushInstructionCache(process,code,sizeof(stub))) {
        printf("setup_error=%lu\n",GetLastError());
        if(remote_result) VirtualFreeEx(process,remote_result,0,MEM_RELEASE);
        if(code) VirtualFreeEx(process,code,0,MEM_RELEASE);
        VirtualFreeEx(process,remote,0,MEM_RELEASE);CloseHandle(process);return 6;
    }
    HANDLE thread=CreateRemoteThread(process,NULL,0,(LPTHREAD_START_ROUTINE)code,remote_result,0,NULL);
    if(!thread) {printf("thread_error=%lu\n",GetLastError());VirtualFreeEx(process,code,0,MEM_RELEASE);VirtualFreeEx(process,remote_result,0,MEM_RELEASE);VirtualFreeEx(process,remote,0,MEM_RELEASE);CloseHandle(process);return 6;}
    DWORD wait=WaitForSingleObject(thread,15000);BOOL read_ok=FALSE;
    if(wait==WAIT_OBJECT_0) {
        GetExitCodeThread(thread,&exit);
        read_ok=ReadProcessMemory(process,remote_result,&result,sizeof(result),NULL);
        VirtualFreeEx(process,code,0,MEM_RELEASE);
        VirtualFreeEx(process,remote_result,0,MEM_RELEASE);
        VirtualFreeEx(process,remote,0,MEM_RELEASE);
    }
    printf("pid=%lu wait=%lu thread_exit=0x%lx read_ok=%u module=%p loader_error=%lu argument_retained=%u\n",pid,wait,exit,read_ok,result.module,result.error,wait!=WAIT_OBJECT_0);
    CloseHandle(thread);CloseHandle(process);
    return wait==WAIT_OBJECT_0 && read_ok && result.module && result.module!=(void *)(uintptr_t)0x12345678u && result.error!=0xffffffffu ? 0 : 7;
}
