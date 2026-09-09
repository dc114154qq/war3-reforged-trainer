#include "war3_native_buff_profile.h"
_Static_assert(sizeof(War3BuffData)==0x24,"buff data size");
_Static_assert(offsetof(War3BuffData,duration)==0x18,"buff duration offset");
_Static_assert(offsetof(War3BuffData,hero_duration)==0x1c,"buff hero duration offset");
_Static_assert(offsetof(War3BuffData,addon)==0x20,"buff addon offset");

/* Offset 0xa00 is overloaded by unrelated ability classes. Require the exact
   effect body whose call site proves this four-argument buff callback ABI. */
static DWORD war3_buff_constructor(uint64_t image,uint64_t effect,uint64_t *constructor) {
    *constructor=0;
    if(!image || effect!=image+WAR3_ROAR_EFFECT_RVA) return ERROR_NOT_SUPPORTED;
    uint64_t address=image+WAR3_BUFF_DATA_CONSTRUCTOR_RVA;
    if(!war3_readable_span(effect,WAR3_ROAR_EFFECT_SIZE) || !war3_executable_pointer(effect) ||
       !war3_readable_span(address,WAR3_BUFF_DATA_CONSTRUCTOR_SIZE) || !war3_executable_pointer(address))
        return ERROR_INVALID_ADDRESS;
    if(war3_bootstrap_hash((uint8_t *)(uintptr_t)effect,WAR3_ROAR_EFFECT_SIZE)!=WAR3_ROAR_EFFECT_HASH ||
       war3_bootstrap_hash((uint8_t *)(uintptr_t)address,WAR3_BUFF_DATA_CONSTRUCTOR_SIZE)!=WAR3_BUFF_DATA_CONSTRUCTOR_HASH)
        return ERROR_BAD_FORMAT;
    *constructor=address;return ERROR_SUCCESS;
}

static DWORD war3_invoke_bound_buff(const NativeCommand *cmd,uint32_t id,const uint64_t *identity,
                                  uint64_t constructor,uint64_t callback) {
    War3BuffData data={0};uint64_t after[10],vtable;DWORD error;
    if(!war3_executable_pointer(constructor) || !war3_executable_pointer(callback)) return ERROR_INVALID_ADDRESS;
    error=war3_direct_identity_memory(cmd,id,identity);if(error) return error;
    ((War3BuffDataConstructFn)(uintptr_t)constructor)(&data,identity[1],0);
    error=war3_action_ability_state(cmd,id,after);if(error) return error;
    if(!war3_action_same_ability(identity,after) || identity[8]!=after[8]) return ERROR_INVALID_HANDLE;
    error=war3_direct_identity_memory(cmd,id,identity);if(error) return error;
    vtable=*(uint64_t *)(uintptr_t)identity[1];
    if(!war3_readable_span(vtable,0xa08) || *(uint64_t *)(uintptr_t)(vtable+0xa00)!=callback)
        return ERROR_INVALID_DATA;
    float duration=data.duration;
    if(data.hero_duration>duration) duration=data.hero_duration;
    if(!(duration==duration) || duration<0.05f) duration=10.0f;
    else if(duration>3600.0f) duration=3600.0f;
    ((DirectAbilityBuffFn)(uintptr_t)callback)(identity[1],cmd->ops[0].handler,&data,&duration);
    return ERROR_SUCCESS;
}
