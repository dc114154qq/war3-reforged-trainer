/* Read-only addition to the original talent button enable predicate.
   Caller must hold the UI/game-thread lifetime and an SEH boundary.
   This does not select talents, change tier records or consume points. */
static uint8_t TalentIconHasOwnedChoice(uint64_t owner,uint64_t unit,uint32_t choice){
    uint64_t node,previous;uint32_t found=0;
    if(!owner || !unit || !choice ||
       *(uint64_t *)(uintptr_t)(owner+0x90)!=unit ||
       *(uint64_t *)(uintptr_t)(owner+0x20)!=*(uint64_t *)(uintptr_t)(unit+0x18))return 0;
    node=*(uint64_t *)(uintptr_t)(owner+0xd8);previous=owner+0xd0;
    for(uint32_t index=0;node && index<4096u;++index){
        uint64_t wrapper,data,next;
        if(node<0x38)return 0;
        wrapper=node-0x38;
        if(*(uint64_t *)(uintptr_t)(wrapper+0x38)!=previous ||
           *(uint64_t *)(uintptr_t)(wrapper+0x50)!=owner)return 0;
        data=*(uint64_t *)(uintptr_t)(wrapper+0x90);
        next=*(uint64_t *)(uintptr_t)(wrapper+0x40);
        if(data && *(uint64_t *)(uintptr_t)(data+0x68)==unit &&
           *(uint32_t *)(uintptr_t)(data+0x70)==choice &&
           *(uint32_t *)(uintptr_t)(data+0x78)==choice &&
           !(*(uint32_t *)(uintptr_t)(data+0x38)&0x8u) &&
           *(uint64_t *)(uintptr_t)(data+0x18)==*(uint64_t *)(uintptr_t)(wrapper+0x20))found=1;
        previous=node;node=next;
    }
    return node?0:(uint8_t)found;
}

static uint8_t TalentIconShouldEnable(uint8_t native_enabled,uint64_t owner,uint64_t unit,uint32_t choice){
    if(native_enabled)return 1;
    return TalentIconHasOwnedChoice(owner,unit,choice);
}
