/* Shared indexed object resolver. Native handles are NOT full object handles. */
static uint64_t BridgeProfileResolveOwner(uint64_t base, uint64_t value, int full_identity) {
    uint64_t root, table, owner, slot;
    uint32_t low=(uint32_t)value,index=low & 0x7fffffffu,count,offset;
    if (!base || (full_identity && !value)) return 0;
    __try {
        root=*(volatile uint64_t *)(uintptr_t)(base+bridge_profile.registry_root_rva);
        if (!root) return 0;
        offset=(low & 0x80000000u) ? bridge_profile.alternate : bridge_profile.primary;
        table=*(volatile uint64_t *)(uintptr_t)(root+offset);
        count=*(volatile uint32_t *)(uintptr_t)(root+offset+bridge_profile.table_count);
        if (!table || index>=count || count>0x10000000u) return 0;
        slot=table+(uint64_t)index*bridge_profile.stride;
        if (*(volatile uint32_t *)(uintptr_t)slot!=0xfffffffeu) return 0;
        owner=*(volatile uint64_t *)(uintptr_t)(slot+bridge_profile.slot_owner);
        if (!owner) return 0;
        if (full_identity && *(volatile uint64_t *)(uintptr_t)(owner+bridge_profile.owner_handle)!=value) return 0;
        if (*(volatile uint64_t *)(uintptr_t)(root+offset)!=table ||
            *(volatile uint32_t *)(uintptr_t)(root+offset+bridge_profile.table_count)!=count ||
            *(volatile uint64_t *)(uintptr_t)(slot+bridge_profile.slot_owner)!=owner ||
            *(volatile uint64_t *)(uintptr_t)(base+bridge_profile.registry_root_rva)!=root) return 0;
        return owner;
    } __except(EXCEPTION_EXECUTE_HANDLER) {return 0;}
}
