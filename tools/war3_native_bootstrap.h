/* Game-thread native-table bootstrap. Included after helper pointer validators. */
typedef struct War3BootstrapCodeCheck {
    uint32_t rva, size;
    uint64_t hash;
} War3BootstrapCodeCheck;
typedef struct War3BootstrapNative {
    const char *name, *signature;
    uint32_t rva;
    uint64_t code_hash;
} War3BootstrapNative;
#include "war3_native_bootstrap_profile.h"

typedef void *(__fastcall *War3ContextGetFn)(int32_t);
typedef uint32_t (__fastcall *War3NameHashFn)(const char *);
static uint8_t *g_bootstrap_module = NULL;

static uint64_t war3_bootstrap_hash(const uint8_t *data, size_t size) {
    uint64_t value = 14695981039346656037ULL;
    for (size_t i = 0; i < size; ++i) value = (value ^ data[i]) * 1099511628211ULL;
    return value;
}

static DWORD war3_bootstrap_validate_image(uint8_t *image) {
    DWORD error = ERROR_BAD_EXE_FORMAT;
    __try {
        IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)(void *)image;
        IMAGE_NT_HEADERS64 *nt;
        if (!image || dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew < 0x40 || dos->e_lfanew > 0x1000)
            __leave;
        nt = (IMAGE_NT_HEADERS64 *)(void *)(image + dos->e_lfanew);
        if (nt->Signature != IMAGE_NT_SIGNATURE || nt->FileHeader.Machine != IMAGE_FILE_MACHINE_AMD64 ||
            nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR64_MAGIC ||
            nt->FileHeader.TimeDateStamp != WAR3_BOOTSTRAP_TIMESTAMP ||
            nt->OptionalHeader.SizeOfImage != WAR3_BOOTSTRAP_IMAGE_SIZE) __leave;
        error = ERROR_REVISION_MISMATCH;
        for (size_t i = 0; i < sizeof(g_bootstrap_checks)/sizeof(g_bootstrap_checks[0]); ++i) {
            const War3BootstrapCodeCheck *check = &g_bootstrap_checks[i];
            if (!war3_readable_pointer((const void *)(uintptr_t)(image + check->rva)) ||
                war3_bootstrap_hash(image + check->rva, check->size) != check->hash) __leave;
        }
        error = ERROR_SUCCESS;
    } __except (EXCEPTION_EXECUTE_HANDLER) { error = ERROR_INVALID_ADDRESS; }
    return error;
}

static int war3_bootstrap_string_equal(const char *actual, const char *expected) {
    /* Bounds both malformed game strings and accidental missing terminators. */
    for (size_t i = 0; i < 256; ++i) {
        if (actual[i] != expected[i]) return 0;
        if (!expected[i]) return 1;
    }
    return 0;
}

static int war3_bootstrap_index(const char *name) {
    size_t lo = 0, hi = sizeof(g_bootstrap_names)/sizeof(g_bootstrap_names[0]);
    while (lo < hi) {
        size_t mid = lo + (hi-lo)/2;
        int order = strcmp(name, g_bootstrap_names[mid].name);
        if (!order) return (int)mid;
        if (order < 0) hi = mid; else lo = mid+1;
    }
    return -1;
}

/* Follow only the requested hash bucket. Never enumerate process regions/heap.
   The audited game lookup uses a signed link offset and low-bit end markers. */
static DWORD war3_bootstrap_find(
    uint8_t *table, uint32_t hash, const War3BootstrapNative *profile,
    uint8_t *image, uint64_t *handler
) {
    DWORD error = ERROR_PROC_NOT_FOUND;
    *handler = 0;
    __try {
        uint32_t mask = *(uint32_t *)(void *)(table + 0x40);
        uint8_t *buckets = *(uint8_t **)(void *)(table + 0x30);
        uint8_t *bucket;
        uintptr_t node;
        int32_t link_offset;
        if (mask == UINT32_MAX) __leave; /* initialized but empty table */
        if (mask > 65535u || ((mask + 1u) & mask) || !buckets) {
            error = ERROR_INVALID_DATA; __leave;
        }
        bucket = buckets + (size_t)(hash & mask) * 24u;
        link_offset = *(int32_t *)(void *)bucket;
        if (link_offset < -0x100 || link_offset > 0x100 || (link_offset & 7)) {
            error = ERROR_INVALID_DATA; __leave;
        }
        node = *(uintptr_t *)(void *)(bucket + 0x10);
        for (uint32_t steps = 0; steps < 4096u; ++steps) {
            uintptr_t next;
            if (!node || (node & 1u)) __leave;
            if ((node & 7u) || node < 0x10000u || node > 0x00007fffffffefffULL) {
                error = ERROR_INVALID_DATA; __leave;
            }
            next = *(uintptr_t *)(node + (intptr_t)link_offset + 8);
            if (*(uint32_t *)node == hash &&
                war3_bootstrap_string_equal(*(const char **)(node + 0x28), profile->name)) {
                uint64_t value = *(uint64_t *)(node + 0x30);
                if (value != (uint64_t)(uintptr_t)(image + profile->rva) ||
                    !war3_bootstrap_string_equal(*(const char **)(node + 0x40), profile->signature) ||
                    !war3_readable_pointer((const void *)(uintptr_t)value) ||
                    war3_bootstrap_hash((const uint8_t *)(uintptr_t)value, 64) != profile->code_hash) {
                    error = ERROR_INVALID_DATA; __leave;
                }
                *handler = value;
                error = ERROR_SUCCESS; __leave;
            }
            node = next;
        }
        error = ERROR_INVALID_DATA; /* cycle or excessive collision chain */
    } __except (EXCEPTION_EXECUTE_HANDLER) { error = ERROR_INVALID_ADDRESS; }
    return error;
}

static DWORD war3_bootstrap_context(uint8_t **image_out, uint8_t **table_out) {
    uint8_t *image = (uint8_t *)GetModuleHandleW(NULL);
    uint8_t *context = NULL;
    DWORD error;
    if (!image) return ERROR_MOD_NOT_FOUND;
    if (g_bootstrap_module != image) {
        error = war3_bootstrap_validate_image(image);
        if (error) return error;
        /* Do not publish the module as ready until all required natives bind. */
    }
    __try {
        context = (uint8_t *)((War3ContextGetFn)(void *)(image + WAR3_BOOTSTRAP_CONTEXT_RVA))(5);
    } __except (EXCEPTION_EXECUTE_HANDLER) { return ERROR_INVALID_ADDRESS; }
    if (!context || !war3_readable_pointer(context)) return ERROR_NOT_READY;
    *image_out = image;
    *table_out = context + 0x28;
    return ERROR_SUCCESS;
}

static DWORD war3_bootstrap_query(uint8_t *image, uint8_t *table, uint32_t index, uint64_t *handler) {
    uint32_t hash;
    if (index >= sizeof(g_bootstrap_names)/sizeof(g_bootstrap_names[0])) return ERROR_INVALID_PARAMETER;
    __try {
        hash = ((War3NameHashFn)(void *)(image + WAR3_BOOTSTRAP_HASH_RVA))(g_bootstrap_names[index].name);
    } __except (EXCEPTION_EXECUTE_HANDLER) { return ERROR_INVALID_ADDRESS; }
    return war3_bootstrap_find(table, hash, &g_bootstrap_names[index], image, handler);
}

/* Transactional publication: any failed required binding leaves ready false. */
static DWORD war3_bootstrap_bind(uint8_t *image, uint8_t *table) {
    uint64_t handlers[sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0])];
    InterlockedExchange(&g_persistent_ready, 0);
    for (size_t i = 0; i < sizeof(handlers)/sizeof(handlers[0]); ++i) {
        int index = war3_bootstrap_index(g_persistent_native_names[i]);
        DWORD error;
        if (index < 0) return ERROR_PROC_NOT_FOUND;
        error = war3_bootstrap_query(image, table, (uint32_t)index, &handlers[i]);
        if (error) return error;
    }
    for (size_t i = 0; i < sizeof(handlers)/sizeof(handlers[0]); ++i) {
        g_persistent_natives[i].name = g_persistent_native_names[i];
        g_persistent_natives[i].handler = handlers[i];
    }
    g_persistent_unit_resolver = (uint64_t)(uintptr_t)(image + WAR3_BOOTSTRAP_UNIT_RVA);
    g_persistent_item_resolver = (uint64_t)(uintptr_t)(image + WAR3_BOOTSTRAP_ITEM_RVA);
    g_persistent_agent_resolver = (uint64_t)(uintptr_t)(image + WAR3_BOOTSTRAP_AGENT_RVA);
    g_persistent_ability_resolver = (uint64_t)(uintptr_t)(image + WAR3_BOOTSTRAP_ABILITY_RVA);
    g_bootstrap_module = image;
    InterlockedExchange(&g_persistent_ready, 1);
    return ERROR_SUCCESS;
}

static DWORD war3_bootstrap_refresh(void) {
    uint8_t *image, *table;
    DWORD error = war3_bootstrap_context(&image, &table);
    if (error) { InterlockedExchange(&g_persistent_ready, 0); return error; }
    return war3_bootstrap_bind(image, table);
}
