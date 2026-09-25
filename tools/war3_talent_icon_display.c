/* Dedicated UI-only module. Install/remove must run on the owning UI thread.
   A mapped instance must remain alive until removal is verified. */
#include <windows.h>
#include <stdint.h>
#include "war3_talent_icon_predicate.h"

typedef struct IconConfig {
    uint64_t game_base;
    void (*enable)(void *,uint8_t);
    DWORD (WINAPI *thread_id)(void);
    BOOL (WINAPI *protect)(void *,SIZE_T,DWORD,DWORD *);
    BOOL (WINAPI *flush)(HANDLE,const void *,SIZE_T);
    void *specific_handler;
    DWORD expected_tid,installed,error,calls,extra_enabled,predicate_faults;
    volatile LONG active;
    DWORD old_protection;
    uint8_t saved[36];
} IconConfig;
__declspec(dllexport) IconConfig icon_config;
__declspec(dllexport) void *icon_resume;
void IconThunk(void);
typedef EXCEPTION_DISPOSITION (*IconHandler)(PEXCEPTION_RECORD,void *,PCONTEXT,PDISPATCHER_CONTEXT);
EXCEPTION_DISPOSITION IconSpecificHandler(PEXCEPTION_RECORD e,void *f,PCONTEXT c,PDISPATCHER_CONTEXT d){
    return ((IconHandler)icon_config.specific_handler)(e,f,c,d);
}

static const uint8_t original[36]={
    0x48,0x8b,0x44,0x24,0x20,0x8b,0x8c,0x24,0x90,0,0,0,0x3b,0x0c,0x07,
    0x74,0x09,0x40,0x84,0xf6,0x75,0x04,0x33,0xd2,0xeb,0x02,0xb2,0x01,
    0x48,0x8b,0xcb,0xe8,0xa5,0x4b,0x1b,0xff};

static uint64_t IconOwner(uint64_t full){
    uint64_t root=*(uint64_t *)(uintptr_t)(icon_config.game_base+0x2f807f0ull);
    uint32_t low=(uint32_t)full,index=low&0x7fffffffu;
    uint32_t offset=(low&0x80000000u)?0x50u:0x18u;
    if(!root)return 0;
    uint64_t table=*(uint64_t *)(uintptr_t)(root+offset);
    uint32_t count=*(uint32_t *)(uintptr_t)(root+offset+0x18);
    if(!table || count>0x10000000u || index>=count)return 0;
    uint64_t slot=table+(uint64_t)index*16,owner=*(uint64_t *)(uintptr_t)(slot+8);
    if(*(uint32_t *)(uintptr_t)slot!=0xfffffffeu || !owner ||
       *(uint64_t *)(uintptr_t)(owner+0x20)!=full)return 0;
    return owner;
}

void IconEnable(void *button,uint8_t native_enabled,uint64_t controller,uint32_t choice){
    uint8_t enabled=native_enabled;
    InterlockedIncrement(&icon_config.active);
    ++icon_config.calls;
    if(!enabled){
        __try {
            uint64_t unit=controller?*(uint64_t *)(uintptr_t)(controller+0x68):0;
            if(unit){
                uint64_t owner=IconOwner(*(uint64_t *)(uintptr_t)(unit+0x18));
                enabled=TalentIconShouldEnable(0,owner,unit,choice);
                if(enabled)++icon_config.extra_enabled;
            }
        } __except(EXCEPTION_EXECUTE_HANDLER){++icon_config.predicate_faults;}
    }
    icon_config.enable(button,enabled);
    InterlockedDecrement(&icon_config.active);
}

static uint8_t PatchByte(uint32_t index){
    if(index==0)return 0xff;
    if(index==1)return 0x25;
    if(index<6)return 0;
    if(index<14)return (uint8_t)((uint64_t)(uintptr_t)&IconThunk>>((index-6)*8));
    return 0x90;
}

__declspec(dllexport) uint32_t IconInstall(void){
    IconConfig *c=&icon_config;DWORD old;
    if(!c->game_base || !c->enable || !c->specific_handler || !c->thread_id ||
       !c->protect || !c->flush || c->thread_id()!=c->expected_tid){c->error=1;return 0;}
    if(c->installed){c->error=2;return 0;}
    uint8_t *site=(uint8_t *)(uintptr_t)(c->game_base+0x10058c7ull);
    __try {
        /* Keep the observed bytes in the ABI scratch area on mismatch. This
           is diagnostic only; the game code is untouched on this path. */
        for(uint32_t i=0;i<36;++i)c->saved[i]=site[i];
        for(uint32_t i=0;i<36;++i)if(site[i]!=original[i]){c->error=3;return 0;}
        if(!c->protect(site,36,PAGE_EXECUTE_READWRITE,&old)){c->error=4;return 0;}
        c->old_protection=old;
        icon_resume=(void *)(uintptr_t)(c->game_base+0x10058ebull);
        /* Set before writing: even partial writes require retained mapping. */
        c->installed=1;
        for(uint32_t i=0;i<36;++i)site[i]=PatchByte(i);
        BOOL flushed=c->flush((HANDLE)(LONG_PTR)-1,site,36);
        BOOL protected_again=c->protect(site,36,old,&old);
        if(!flushed || !protected_again){c->error=5;return 0;}
        for(uint32_t i=0;i<36;++i)if(site[i]!=PatchByte(i)){c->error=6;return 0;}
        c->error=0;return 1;
    } __except(EXCEPTION_EXECUTE_HANDLER){c->error=GetExceptionCode();return 0;}
}

__declspec(dllexport) uint32_t IconRemove(void){
    IconConfig *c=&icon_config;DWORD old;
    if(!c->thread_id || c->thread_id()!=c->expected_tid || c->active){c->error=7;return 0;}
    if(!c->installed)return 1;
    uint8_t *site=(uint8_t *)(uintptr_t)(c->game_base+0x10058c7ull);
    __try {
        /* A third party may have replaced our patch. Never overwrite it. */
        for(uint32_t i=0;i<36;++i)if(site[i]!=PatchByte(i)){c->error=8;return 0;}
        if(!c->protect(site,36,PAGE_EXECUTE_READWRITE,&old)){c->error=9;return 0;}
        for(uint32_t i=0;i<36;++i)site[i]=c->saved[i];
        BOOL flushed=c->flush((HANDLE)(LONG_PTR)-1,site,36);
        BOOL protected_again=c->protect(site,36,c->old_protection,&old);
        if(!flushed || !protected_again){c->error=10;return 0;}
        for(uint32_t i=0;i<36;++i)if(site[i]!=original[i]){c->error=11;return 0;}
        c->installed=0;c->error=0;return 1;
    } __except(EXCEPTION_EXECUTE_HANDLER){c->error=GetExceptionCode();return 0;}
}

BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID reserved){
    (void)module;(void)reason;(void)reserved;return TRUE;
}
__declspec(dllexport) const uint32_t icon_display_abi[4]={0x24268045,1,sizeof(IconConfig),36};
__declspec(dllexport) const void *icon_relocation_anchor=(void *)&IconInstall;
