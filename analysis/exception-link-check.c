#include <windows.h>
typedef EXCEPTION_DISPOSITION (*Handler)(PEXCEPTION_RECORD,void *,PCONTEXT,PDISPATCHER_CONTEXT);
static Handler handler;
EXCEPTION_DISPOSITION ProbeSpecificHandler(PEXCEPTION_RECORD e,void *f,PCONTEXT c,PDISPATCHER_CONTEXT d) {
    return handler(e,f,c,d);
}
__declspec(dllexport) DWORD CheckFault(volatile DWORD *address, Handler supplied) {
    handler = supplied;
    __try { return *address; }
    __except (EXCEPTION_EXECUTE_HANDLER) { return GetExceptionCode(); }
}
BOOL WINAPI DllMain(HINSTANCE h,DWORD r,LPVOID p){return TRUE;}
