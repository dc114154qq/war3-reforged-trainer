/* 2.0.4.23745 UnitAddItemToSlotById, audited in native-call-contracts-23745.json.
   Hash the complete instruction prefix through the first RET, including every
   call site. Fixed offsets are used only after the complete code matches. */
#define WAR3_SLOT_HANDLER_RVA 0xcaae00u
#define WAR3_SLOT_CODE_SIZE 0xe4u
#define WAR3_SLOT_CODE_HASH 0xf54fceaf4a2f036aULL
#define WAR3_SLOT_CALL_OFFSET 0xcfu
#define WAR3_SLOT_ADD_RVA 0x1177560u

static DWORD war3_slot_add_from_handler(uint8_t *image,uint64_t handler,uint64_t *out) {
    *out=0;
    if(!image || handler!=(uint64_t)(uintptr_t)(image+WAR3_SLOT_HANDLER_RVA) ||
       !war3_readable_span(handler,WAR3_SLOT_CODE_SIZE) || !war3_executable_pointer(handler))
        return ERROR_INVALID_ADDRESS;
    __try {
        const uint8_t *code=(const uint8_t *)(uintptr_t)handler;
        if(war3_bootstrap_hash(code,WAR3_SLOT_CODE_SIZE)!=WAR3_SLOT_CODE_HASH ||
           code[WAR3_SLOT_CALL_OFFSET]!=0xe8) return ERROR_INVALID_DATA;
        int32_t displacement;memcpy(&displacement,code+WAR3_SLOT_CALL_OFFSET+1,4);
        uint64_t target=handler+WAR3_SLOT_CALL_OFFSET+5+(int64_t)displacement;
        if(target!=(uint64_t)(uintptr_t)(image+WAR3_SLOT_ADD_RVA) || !war3_executable_pointer(target))
            return ERROR_INVALID_ADDRESS;
        *out=target;
    } __except(EXCEPTION_EXECUTE_HANDLER) {return GetExceptionCode();}
    return ERROR_SUCCESS;
}

static DWORD war3_resolve_slot_add(uint64_t *out) {
    uint8_t *image,*table;uint64_t handler=0;*out=0;
    DWORD error=war3_bootstrap_context(&image,&table);
    if(error) return error;
    int index=war3_bootstrap_index("UnitAddItemToSlotById");
    if(index<0) return ERROR_PROC_NOT_FOUND;
    error=war3_bootstrap_query(image,table,(uint32_t)index,&handler);
    if(error) return error;
    return war3_slot_add_from_handler(image,handler,out);
}
