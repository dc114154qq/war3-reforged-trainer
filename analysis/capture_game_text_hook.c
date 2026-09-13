/* Research-only one-shot module capture. No game functions or game writes. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static HINSTANCE instance;
static LONG started;
static void capture(void) {
    wchar_t path[MAX_PATH], result_path[MAX_PATH];
    DWORD error=0, written=0, failures=0;
    uint32_t size=0, rva=0;
    uint8_t *image=(uint8_t *)GetModuleHandleW(NULL), *copy=NULL;
    uint32_t *gaps=NULL;
    HANDLE file=INVALID_HANDLE_VALUE;
    DWORD n=GetModuleFileNameW(instance,path,MAX_PATH);
    if(!n || n>=MAX_PATH-40) return;
    wchar_t *slash=wcsrchr(path,L'\\'); if(!slash) return;
    swprintf(slash+1,40,L"capture-%lu",GetCurrentProcessId());
    wcscpy_s(result_path,MAX_PATH,path); wcscat_s(result_path,MAX_PATH,L".status");
    wcscat_s(path,MAX_PATH,L".raw");
    __try {
        IMAGE_DOS_HEADER *dos=(void *)image;
        if(!image || dos->e_magic!=IMAGE_DOS_SIGNATURE || dos->e_lfanew<0x40 || dos->e_lfanew>0x800) {error=193;__leave;}
        IMAGE_NT_HEADERS64 *nt=(void *)(image+dos->e_lfanew);
        if(nt->Signature!=IMAGE_NT_SIGNATURE || nt->FileHeader.TimeDateStamp!=0x6aa4de70u ||
           nt->OptionalHeader.SizeOfImage!=0xe155000u) {error=1306;__leave;}
        IMAGE_SECTION_HEADER *sec=IMAGE_FIRST_SECTION(nt);
        for(unsigned i=0;i<nt->FileHeader.NumberOfSections && i<32;i++) if(!memcmp(sec[i].Name,".text\0",6)) {
            rva=sec[i].VirtualAddress;size=sec[i].Misc.VirtualSize;break;
        }
        if(rva!=0x1000 || size!=36036822u) {error=13;__leave;}
        copy=VirtualAlloc(NULL,size,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
        gaps=VirtualAlloc(NULL,((size+4095)/4096)*4,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
        if(!copy || !gaps) {error=8;__leave;}
        for(uint32_t off=0;off<size;off+=4096) {
            uint32_t count=size-off; if(count>4096) count=4096;
            MEMORY_BASIC_INFORMATION mbi;
            if(!VirtualQuery(image+rva+off,&mbi,sizeof(mbi)) || mbi.State!=MEM_COMMIT || (mbi.Protect&PAGE_GUARD)) {
                gaps[failures++]=rva+off;continue;
            }
            SIZE_T got=0;
            if(!ReadProcessMemory(GetCurrentProcess(),image+rva+off,copy+off,count,&got) || got!=count) {
                gaps[failures++]=rva+off;memset(copy+off,0,count);
            }
        }
        file=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
        if(file==INVALID_HANDLE_VALUE) {error=GetLastError();__leave;}
        if(!WriteFile(file,copy,size,&written,NULL) || written!=size) error=ERROR_WRITE_FAULT;
    } __except(EXCEPTION_EXECUTE_HANDLER) {error=GetExceptionCode();}
    if(file!=INVALID_HANDLE_VALUE) CloseHandle(file);
    file=CreateFileW(result_path,GENERIC_WRITE,FILE_SHARE_READ,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file!=INVALID_HANDLE_VALUE) {
        uint32_t status[]={0x24268001u,error,size,failures};
        WriteFile(file,status,sizeof(status),&written,NULL);
        if(gaps && failures) WriteFile(file,gaps,failures*4,&written,NULL);
        CloseHandle(file);
    }
    if(copy) VirtualFree(copy,0,MEM_RELEASE);
    if(gaps) VirtualFree(gaps,0,MEM_RELEASE);
}
__declspec(dllexport) LRESULT CALLBACK CaptureHook(int code,WPARAM w,LPARAM l) {
    if(code>=0 && l) {
        CWPSTRUCT *msg=(CWPSTRUCT *)l;
        if(msg->message==WM_NULL && InterlockedCompareExchange(&started,1,0)==0) capture();
    }
    return CallNextHookEx(NULL,code,w,l);
}
BOOL WINAPI DllMain(HINSTANCE self,DWORD reason,LPVOID reserved) {
    (void)reserved;if(reason==DLL_PROCESS_ATTACH) instance=self;return TRUE;
}
