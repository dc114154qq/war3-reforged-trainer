/* Current-build 24268 runtime item catalog enumeration and cleanup. */
typedef uint32_t (*CatalogChooseRandomItemFn)(uint32_t);
typedef uint64_t (*CatalogCreateItemFn)(uint32_t, float *, float *);
typedef void (*CatalogRemoveItemFn)(uint64_t);

typedef struct ItemCatalogWork {
    CatalogChooseRandomItemFn choose_random_item;
    CatalogCreateItemFn create_item;
    CatalogRemoveItemFn remove_item;
    void *expected_tls;
    uint32_t action, limit_word, x_bits, y_bits;
    uint32_t capacity, count, total, created, error, completed;
    uint64_t handles[];
} ItemCatalogWork;
_Static_assert(sizeof(ItemCatalogWork) == 72, "ItemCatalogWork ABI");
__declspec(dllexport) const uint32_t item_catalog_batch_abi[3] = {0x2426802Bu, 216u, 0u};

typedef struct CatalogCodeRange {
    const uint8_t *begin;
    size_t size;
} CatalogCodeRange;

#ifdef BRIDGE_TEST
static int catalog_fixture_enabled;
static uint32_t *catalog_fixture_count_pointer;
static uint64_t *catalog_fixture_root_pointer;
static int32_t *catalog_fixture_link_pointer;
static uint8_t catalog_fixture_rawcode_offset;
#endif

static int catalog_section_range(HMODULE module, CatalogCodeRange *range) {
    uint8_t *base;
    IMAGE_DOS_HEADER *dos;
    IMAGE_NT_HEADERS64 *nt;
    IMAGE_SECTION_HEADER *section;
    if (!module || !range) return 0;
    base = (uint8_t *)(void *)module;
    dos = (IMAGE_DOS_HEADER *)(void *)base;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) return 0;
    nt = (IMAGE_NT_HEADERS64 *)(void *)(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE || nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR64_MAGIC) return 0;
    section = IMAGE_FIRST_SECTION(nt);
    for (uint16_t index = 0; index < nt->FileHeader.NumberOfSections; ++index, ++section) {
        static const char text_name[8] = {'.','t','e','x','t',0,0,0};
        int matches = 1;
        for (uint32_t character = 0; character < 8; ++character)
            if (section->Name[character] != text_name[character]) matches = 0;
        if (matches) {
            range->begin = base + section->VirtualAddress;
            range->size = section->Misc.VirtualSize ? section->Misc.VirtualSize : section->SizeOfRawData;
            return range->begin && range->size;
        }
    }
    return 0;
}

static int catalog_in_range(const void *address, const CatalogCodeRange *range) {
    uintptr_t value = (uintptr_t)address;
    uintptr_t begin = (uintptr_t)range->begin;
    return value >= begin && value < begin + range->size;
}

static void *catalog_rel32_target(const uint8_t *instruction) {
    int32_t displacement;
    for (uint32_t index = 0; index < 4; ++index)
        ((uint8_t *)&displacement)[index] = instruction[index + 1];
    return (void *)(instruction + 5 + displacement);
}

static void *catalog_rip_target(const uint8_t *instruction, uint32_t length, uint32_t offset) {
    int32_t displacement;
    for (uint32_t index = 0; index < 4; ++index)
        ((uint8_t *)&displacement)[index] = instruction[offset + index];
    return (void *)(instruction + length + displacement);
}

static int catalog_pattern_matches(const uint8_t *candidate, const uint8_t *pattern,
                                   const uint8_t *fixed, size_t length) {
    for (size_t index = 0; index < length; ++index)
        if (fixed[index] && candidate[index] != pattern[index]) return 0;
    return 1;
}

static const uint8_t *catalog_find_unique(const uint8_t *begin, size_t size,
                                          const uint8_t *pattern, const uint8_t *fixed,
                                          size_t pattern_size) {
    const uint8_t *match = NULL;
    if (!begin || size < pattern_size) return NULL;
    for (size_t offset = 0; offset <= size - pattern_size; ++offset) {
        if (!catalog_pattern_matches(begin + offset, pattern, fixed, pattern_size)) continue;
        if (match) return NULL;
        match = begin + offset;
    }
    return match;
}

static int catalog_readable_pointer(const void *pointer) {
    uintptr_t value = (uintptr_t)pointer;
    return value >= 0x10000u && value < 0x800000000000ULL;
}

static DWORD catalog_resolve_loaded_list(
    const uint8_t *choose_random_item,
    uint32_t **count_pointer,
    uint64_t **root_pointer,
    int32_t **link_offset_pointer,
    uint8_t *rawcode_offset
) {
    static const uint8_t count_pattern[] = {0x8b,0x1d,0,0,0,0,0x85,0xdb,0x74};
    static const uint8_t count_fixed[] = {1,1,0,0,0,0,1,1,1};
    static const uint8_t root_pattern[] = {0x48,0x8b,0x05,0,0,0,0,0xa8,0x01};
    static const uint8_t root_fixed[] = {1,1,1,0,0,0,0,1,1};
    static const uint8_t offset_pattern[] = {0x48,0x63,0x05,0,0,0,0,0x48,0x8b,0x54,0x08,0x08};
    static const uint8_t offset_fixed[] = {1,1,1,0,0,0,0,1,1,1,1,1};
    static const uint8_t rawcode_pattern[] = {0x8b,0x59,0,0x8b,0xcb};
    static const uint8_t rawcode_fixed[] = {1,1,0,1,1};
#ifdef BRIDGE_TEST
    if (catalog_fixture_enabled) {
        *count_pointer = catalog_fixture_count_pointer;
        *root_pointer = catalog_fixture_root_pointer;
        *link_offset_pointer = catalog_fixture_link_pointer;
        *rawcode_offset = catalog_fixture_rawcode_offset;
        return ERROR_SUCCESS;
    }
#endif
    if (!catalog_readable_pointer(choose_random_item)) return ERROR_INVALID_ADDRESS;
    const uint8_t *enumerator = NULL, *count_match = NULL, *root_match = NULL;
    const uint8_t *offset_match = NULL, *rawcode_match = NULL;
    for (size_t offset = 0; offset < 0x60; ++offset) {
        const uint8_t *instruction = choose_random_item + offset;
        if (instruction[0] != 0xe8) continue;
        const uint8_t *target = (const uint8_t *)catalog_rel32_target(instruction);
        if (!catalog_readable_pointer(target)) continue;
        const uint8_t *a = catalog_find_unique(target, 0x180, count_pattern, count_fixed, sizeof(count_pattern));
        const uint8_t *b = catalog_find_unique(target, 0x180, root_pattern, root_fixed, sizeof(root_pattern));
        const uint8_t *c = catalog_find_unique(target, 0x180, offset_pattern, offset_fixed, sizeof(offset_pattern));
        const uint8_t *d = catalog_find_unique(target, 0x180, rawcode_pattern, rawcode_fixed, sizeof(rawcode_pattern));
        if (a && b && c && d) {
            if (enumerator && enumerator != target) return ERROR_MORE_DATA;
            enumerator = target;count_match = a;root_match = b;offset_match = c;rawcode_match = d;
        }
    }
    if (!enumerator) return ERROR_NOT_FOUND;
    *count_pointer = (uint32_t *)catalog_rip_target(count_match, 6, 2);
    *root_pointer = (uint64_t *)catalog_rip_target(root_match, 7, 3);
    *link_offset_pointer = (int32_t *)catalog_rip_target(offset_match, 7, 3);
    *rawcode_offset = rawcode_match[2];
    if (!catalog_readable_pointer(*count_pointer) || !catalog_readable_pointer(*root_pointer) ||
        !catalog_readable_pointer(*link_offset_pointer) || *rawcode_offset > 0x80u)
        return ERROR_INVALID_DATA;
    return ERROR_SUCCESS;
}

static int catalog_valid_rawcode(uint32_t rawcode) {
    for (int shift = 24; shift >= 0; shift -= 8) {
        uint8_t character = (uint8_t)(rawcode >> shift);
        if (character < 0x21u || character > 0x7eu) return 0;
    }
    return 1;
}

__declspec(dllexport) uint64_t BridgeItemCatalogQuery(void) {
    ItemCatalogWork *w = (ItemCatalogWork *)g_dispatch->work;
    uint32_t *count_pointer = NULL;
    uint64_t *root_pointer = NULL;
    int32_t *link_offset_pointer = NULL;
    uint8_t rawcode_offset = 0;
    uint64_t node = 0;
    uint32_t limit, validated = 0;
    if (!w || w->expected_tls != g_dispatch->tls_value ||
        w->action < 1 || w->action > 3 || w->capacity > 100000u || w->count > w->capacity) {
        if (w) w->error = ERROR_INVALID_PARAMETER;
        return 0;
    }
    if (w->action == 2) {
        if (!w->remove_item || !w->count) {w->error = ERROR_INVALID_PARAMETER;return 0;}
        __try {
            for (uint32_t index = 0; index < w->count; ++index) {
                if (!w->handles[index]) {w->error = ERROR_INVALID_HANDLE;return 0;}
                w->remove_item(w->handles[index]);
                ++w->created;
            }
            w->completed = 1;
        } __except(EXCEPTION_EXECUTE_HANDLER) {w->error = GetExceptionCode();}
        return w->created;
    }
    limit = w->limit_word & 0x7fffffffu;
    if (w->action == 3) {
        if (!w->create_item || w->choose_random_item || w->remove_item ||
            w->limit_word || !w->count || w->count != w->capacity) {
            w->error = ERROR_INVALID_PARAMETER;return 0;
        }
        union {uint32_t bits;float value;} x = {w->x_bits}, y = {w->y_bits};
        if (x.value != x.value || y.value != y.value) {w->error = ERROR_INVALID_PARAMETER;return 0;}
        __try {
            w->total = w->count;
            while (w->created < w->count) {
                uint64_t rawcode_word = w->handles[w->created];
                if (rawcode_word > 0xffffffffULL || !catalog_valid_rawcode((uint32_t)rawcode_word)) {
                    w->error = ERROR_INVALID_DATA;return 0;
                }
                uint64_t item = w->create_item((uint32_t)rawcode_word, &x.value, &y.value);
                if (!item) {w->error = ERROR_GEN_FAILURE;return 0;}
                w->handles[w->created++] = item;
            }
            w->completed = 1;
        } __except(EXCEPTION_EXECUTE_HANDLER) {w->error = GetExceptionCode();}
        return w->created;
    }
    if (!w->choose_random_item || !w->create_item || w->remove_item ||
        (w->limit_word & 0x7fffffffu) > 100000u || w->count ||
        ((w->limit_word & 0x80000000u) ? w->capacity : w->capacity != (limit ? limit : 100000u))) {
        w->error = ERROR_INVALID_PARAMETER;return 0;
    }
    DWORD resolve_error = ERROR_SUCCESS;
    __try {
        resolve_error = catalog_resolve_loaded_list(
            (const uint8_t *)(uintptr_t)w->choose_random_item,
            &count_pointer,&root_pointer,&link_offset_pointer,&rawcode_offset);
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        w->error = GetExceptionCode();
        return 0;
    }
    if (resolve_error != ERROR_SUCCESS) {
        w->error = resolve_error;return 0;
    }
    __try {
        uint32_t total = *count_pointer;
        uint64_t root = *root_pointer;
        int32_t link_offset = *link_offset_pointer;
        if (!total || total > 100000u || link_offset < -0x1000 || link_offset > 0x1000) {w->error = ERROR_INVALID_DATA;return 0;}
        node = (!root || (root & 1u)) ? 0 : root;
        while (validated < total) {
            uint64_t next;
            if (!node || !catalog_readable_pointer((void *)(uintptr_t)node)) {w->error = ERROR_INVALID_ADDRESS;return 0;}
            uint32_t rawcode = *(uint32_t *)(uintptr_t)(node + rawcode_offset);
            if (!catalog_valid_rawcode(rawcode)) {w->error = ERROR_INVALID_DATA;return 0;}
            next = *(uint64_t *)(uintptr_t)(node + link_offset + 8);
            if (next == node) {w->error = ERROR_CIRCULAR_DEPENDENCY;return 0;}
            node = (!next || (next & 1u)) ? 0 : next;
            ++validated;
        }
        if (node) {w->error = ERROR_MORE_DATA;return 0;}
        w->total = total;
        if (w->limit_word & 0x80000000u) {w->completed = 1;return total;}
        union {uint32_t bits;float value;} x = {w->x_bits}, y = {w->y_bits};
        if (x.value != x.value || y.value != y.value) {w->error = ERROR_INVALID_PARAMETER;return 0;}
        uint32_t capacity = limit && limit < total ? limit : total;
        node = (!root || (root & 1u)) ? 0 : root;
        while (node && w->created < capacity) {
            uint32_t rawcode = *(uint32_t *)(uintptr_t)(node + rawcode_offset);
            uint64_t next = *(uint64_t *)(uintptr_t)(node + link_offset + 8);
            uint64_t item = w->create_item(rawcode, &x.value, &y.value);
            if (item) w->handles[w->created++] = item;
            node = (!next || (next & 1u)) ? 0 : next;
        }
        w->completed = 1;
    } __except(EXCEPTION_EXECUTE_HANDLER) {w->error = GetExceptionCode();}
    return w->created;
}
