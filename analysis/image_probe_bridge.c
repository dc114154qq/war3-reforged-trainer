/* Import-free mapped-image diagnostic. All OS function pointers are supplied. */
#include "image_probe_context.h"
__declspec(dllexport) DWORD WINAPI ImageProbe(ProbeContext *context) {
    context->stage=1;
    if(context->mode==1) {
        if(!context->read_api || !context->last_error || !context->read_output || !context->read_pages ||
           !context->read_size || context->read_size>64u*1024u*1024u) {
            context->error=ERROR_INVALID_PARAMETER;context->stage=2;return 0;
        }
        context->read_failures=0;
        for(DWORD offset=0,index=0;offset<context->read_size;offset+=4096,index++) {
            SIZE_T count=context->read_size-offset,copied=0;
            if(count>4096) count=4096;
            BOOL ok=((BOOL (WINAPI *)(HANDLE,LPCVOID,LPVOID,SIZE_T,SIZE_T *))context->read_api)(
                (HANDLE)(LONG_PTR)-1,context->read_address+offset,context->read_output+offset,count,&copied);
            DWORD error=ok && copied==count ? 0 :
                ((DWORD (WINAPI *)(void))context->last_error)();
            if(!error && (!ok || copied!=count)) error=ERROR_PARTIAL_COPY;
            context->read_pages[index].copied=(DWORD)copied;
            context->read_pages[index].error=error;
            if(error) ++context->read_failures;
        }
        context->error=0;context->stage=2;return 0;
    }
    if(context->mode!=0) {context->error=ERROR_INVALID_PARAMETER;context->stage=2;return 0;}
    context->module=((HMODULE (WINAPI *)(LPCWSTR))context->load)(context->path);
    context->error=((DWORD (WINAPI *)(void))context->last_error)();
    context->stage=2;
    return 0;
}
