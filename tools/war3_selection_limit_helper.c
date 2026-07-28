#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tlhelp32.h>

#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>

#define WAR3_SELECTION_MAGIC 0x4C533357u
#define WAR3_SELECTION_VERSION 27u
#define WAR3_SELECTION_STATUS_PENDING 1u
#define WAR3_SELECTION_STATUS_OK 2u
#define WAR3_SELECTION_STATUS_FAILED 3u

#define WAR3_SELECTION_ACTION_QUERY 0u
#define WAR3_SELECTION_ACTION_ENABLE 1u
#define WAR3_SELECTION_ACTION_DISABLE 2u
#define WAR3_SELECTION_ACTION_DIAGNOSTIC 3u

#define WAR3_SELECTION_STATE_UNKNOWN 0u
#define WAR3_SELECTION_STATE_DISABLED 1u
#define WAR3_SELECTION_STATE_ENABLED 2u

#define WAR3_SELECTION_PATCH_COUNT 14u
#define WAR3_ORDER_HANDLER_COUNT 6u
#define WAR3_ORDER_THREAD_STATE_COUNT 64u
#define WAR3_SELECTION_ANY 0x100u
#define ARRAY_COUNT(values) (sizeof(values) / sizeof((values)[0]))

#ifndef WAR3_CRASH_TRACE_ENABLED
#define WAR3_CRASH_TRACE_ENABLED 0
#endif

#ifndef WAR3_PORTRAIT_PATCHES_ENABLED
#define WAR3_PORTRAIT_PATCHES_ENABLED 0
#endif

#ifndef WAR3_SELECTION_PATCHES_ENABLED
#define WAR3_SELECTION_PATCHES_ENABLED 1
#endif

#ifndef WAR3_EARLY_ORDER_OBSERVER_PATCH_ENABLED
#define WAR3_EARLY_ORDER_OBSERVER_PATCH_ENABLED 1
#endif

#ifndef WAR3_CLIENTSDK_CALL_PROBE_ENABLED
#define WAR3_CLIENTSDK_CALL_PROBE_ENABLED 0
#endif

#ifndef WAR3_CLIENTSDK_NULL_GUARD_ENABLED
#define WAR3_CLIENTSDK_NULL_GUARD_ENABLED 0
#endif

#ifndef WAR3_DIRECT_SELECTION_PATCHES_ENABLED
#define WAR3_DIRECT_SELECTION_PATCHES_ENABLED 1
#endif

#ifndef WAR3_PERSISTENT_SELECTION_BREAKPOINTS_ENABLED
#define WAR3_PERSISTENT_SELECTION_BREAKPOINTS_ENABLED 0
#endif

#ifndef WAR3_EARLY_IMAGE_PATCH_ENABLED
#define WAR3_EARLY_IMAGE_PATCH_ENABLED 0
#endif

#ifndef WAR3_AUTO_ENABLE_ON_LOAD
#define WAR3_AUTO_ENABLE_ON_LOAD 0
#endif

#if WAR3_EARLY_IMAGE_PATCH_ENABLED
typedef DWORD (WINAPI *War3EarlyPatchCallback)(void *image, SIZE_T size);
DWORD WINAPI War3EarlyImagePatchInstall(War3EarlyPatchCallback callback);
void WINAPI War3EarlyImagePatchUninstall(void);
DWORD WINAPI War3EarlyImagePatchStatus(void);
void OrderDispatchObserverThunk(void);
void OrderDispatchObserverThunkSelfTest(void);
#endif

#define WAR3_CRASH_TRACE_MAGIC 0x43523357u
#define WAR3_CRASH_TRACE_VERSION 2u
#define WAR3_CRASH_TRACE_RECORD_COUNT 16u
#define WAR3_CLIENTSDK_NULL_CALL_RVA 0x00077cceu
#define WAR3_CLIENTSDK_CALL_PROBE_EXCEPTION 0xe0424350u
#define WAR3_CLIENTSDK_NULL_GUARD_EXCEPTION 0xe0424351u
#define WAR3_SELECTION_REQUEST_OBSERVER_ENABLE (-2)
#define WAR3_SELECTION_REQUEST_OBSERVER_DISABLE (-3)
#define WAR3_SELECTION_VTABLE_RVA 0x023d18d8u
#define WAR3_SELECTION_PLAYER_OFFSET 0x358u
#define WAR3_SELECTION_MIRROR_COUNT_OFFSET 0x3a8u
#define WAR3_SELECTION_LOCAL_COUNT_OFFSET 0x3f0u
#define WAR3_SELECTION_OBJECT_SIZE 0x3f8u
#define WAR3_UNIT_ORDER_DISPATCH_RVA 0x0123f430u
#define WAR3_ORDER_OBSERVER_CAVE_RVA 0x01260940u
#define WAR3_ORDER_SINGLE_RECIPIENT_FLAG 0x0004u
#define WAR3_ORDER_SMART_ID 0x000d0003u
#define WAR3_ORDER_SMART_ALT_ID 0x000d000du
#define WAR3_ORDER_OBSERVER_CAVE_SIZE 16u

typedef struct SelectionCommand {
    uint32_t magic;
    uint32_t version;
    uint32_t status;
    uint32_t action;
    uint32_t requested_limit;
    uint32_t state;
    uint32_t patch_count;
    uint32_t last_error;
    uint32_t failed_patch;
    uint32_t reserved;
    uint32_t selected_count;
    uint32_t breakpoint_mode;
    uint32_t breakpoint_thread_id;
    uint32_t reserved2;
    uint64_t patch_addresses[WAR3_SELECTION_PATCH_COUNT];
    uint64_t breakpoint_addresses[4];
    uint64_t hit_counts[WAR3_SELECTION_PATCH_COUNT];
    uint64_t diagnostic_hits[4];
    uint64_t diagnostic_context[9];
    uint64_t selection_manager;
} SelectionCommand;

typedef struct PatchSpec {
    const char *name;
    const uint16_t *signature;
    size_t signature_size;
    size_t patch_offset;
    uint32_t original_value;
    uint32_t enabled_value;
    size_t value_size;
} PatchSpec;

typedef struct OrderHandlerSpec {
    const char *name;
    uint32_t rbp_displacement;
    uint32_t old_frame_size;
    uint32_t new_frame_size;
    uint32_t old_array_size;
    uint32_t new_array_size;
    uint32_t cookie_offset;
    size_t memset_offset;
    size_t cookie_load_offset;
    size_t epilogue_offset;
    size_t instant_store_offset;
    size_t instant_load_offset;
    uint32_t instant_offset;
} OrderHandlerSpec;

typedef struct OrderHandlerRuntime {
    BYTE *entry;
    BYTE *stack_allocation;
    BYTE *cookie_store;
    BYTE *array_size;
    BYTE *cookie_load;
    BYTE *epilogue;
    BYTE *return_instruction;
    BYTE *instant_store;
    BYTE *instant_load;
} OrderHandlerRuntime;

typedef struct OrderThreadState {
    volatile LONG thread_id;
    uint32_t order_index;
    uint32_t order_active;
    uint32_t stack_expanded;
    uint32_t return_single_step;
    DWORD64 saved_dr0;
    DWORD64 saved_dr1;
    DWORD64 saved_dr2;
    DWORD64 saved_dr3;
    DWORD64 saved_dr7;
} OrderThreadState;

#if WAR3_CRASH_TRACE_ENABLED
#pragma pack(push, 1)
typedef struct CrashTraceRecord {
    uint64_t sequence;
    uint32_t exception_code;
    uint32_t thread_id;
    uint64_t exception_address;
    uint64_t rip;
    uint64_t rsp;
    uint64_t rbp;
    uint64_t rax;
    uint64_t rbx;
    uint64_t rcx;
    uint64_t rdx;
    uint64_t r8;
    uint64_t r9;
    uint64_t dr0;
    uint64_t dr1;
    uint64_t dr2;
    uint64_t dr3;
    uint64_t dr6;
    uint64_t dr7;
    uint64_t exception_information0;
    uint64_t exception_information1;
    uint64_t selection_manager;
    uint64_t stack[16];
    uint32_t eflags;
    uint32_t stack_count;
    uint32_t breakpoint_mode;
    uint32_t order_index;
    uint32_t order_active;
    uint32_t reserved;
} CrashTraceRecord;

typedef struct CrashTraceFile {
    uint32_t magic;
    uint32_t version;
    uint32_t process_id;
    uint32_t record_count;
    volatile LONG64 next_sequence;
    volatile LONG64 committed_sequence;
    volatile LONG process_detach_seen;
    volatile LONG writing;
    uint64_t reserved[3];
    CrashTraceRecord records[WAR3_CRASH_TRACE_RECORD_COUNT];
} CrashTraceFile;
#pragma pack(pop)
#endif

typedef uint8_t (__fastcall *OrderHandlerFunction)(void *self, void *data);
typedef void (__fastcall *UnitOrderDispatchFunction)(
    void *unit,
    void *order,
    uint16_t flags,
    uint8_t auxiliary
);

typedef struct OrderDispatchObservation {
    uint32_t count;
    uint16_t flags;
    uint8_t single_recipient;
    uint8_t invalid_return;
    uintptr_t invalid_return_rva;
    uint32_t invalid_registers;
} OrderDispatchObservation;

static const OrderHandlerSpec ORDER_SPECS[WAR3_ORDER_HANDLER_COUNT] = {
    {"basic order", 0xffffff10u, 0x1f0u, 0x370u, 0x180u, 0x300u, 0x0e8u,
     0x1cbu, 0x3c1u, 0x3d0u, 0u, 0u, 0u},
    {"target image order 2", 0xfffffd10u, 0x3f0u, 0x630u, 0x240u, 0x480u, 0x2e8u,
     0x069u, 0x884u, 0x893u, 0u, 0u, 0u},
    {"target image order", 0xfffffd30u, 0x3d0u, 0x610u, 0x240u, 0x480u, 0x2c0u,
     0x070u, 0x7d9u, 0x7e8u, 0u, 0u, 0u},
    {"fogged order 2", 0xfffffd60u, 0x3a0u, 0x580u, 0x1e0u, 0x3c0u, 0x298u,
     0x074u, 0x737u, 0x746u, 0x08du, 0x67cu, 0x280u},
    {"fogged order", 0xfffffd80u, 0x380u, 0x560u, 0x1e0u, 0x3c0u, 0x278u,
     0x071u, 0x705u, 0x714u, 0u, 0u, 0u},
    {"target point order", 0xfffffdf0u, 0x310u, 0x4f0u, 0x1e0u, 0x3c0u, 0x208u,
     0x060u, 0x68cu, 0x69bu, 0u, 0u, 0u},
};

static const uint16_t SIG_ADD_LOCAL[] = {
    0x83, 0xbd, 0xf0, 0x03, 0x00, 0x00, WAR3_SELECTION_ANY,
    0x0f, 0x83, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY,
    0x48, 0x89, 0x5c, 0x24, 0x70, 0x8b, 0x9d, 0x58, 0x03, 0x00, 0x00,
    0x48, 0x89, 0xb4, 0x24, 0x80, 0x00, 0x00, 0x00
};

static const uint16_t SIG_COMMAND_CTOR[] = {
    0x40, 0x80, 0xf7, 0x01, 0xc6, 0x44, 0x24, 0x48, 0x00, 0x40, 0x88, 0x7c, 0x24, 0x40,
    0xc6, 0x44, 0x24, 0x38, 0x01, 0xc6, 0x44, 0x24, 0x30, 0x01, 0xc7, 0x44, 0x24, 0x28,
    WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY,
    0xc6, 0x44, 0x24, 0x20, 0x00
};

static const uint16_t SIG_CAPACITY[] = {
    0x41, 0x8b, 0xde, 0x41, 0x8b, 0xc6, 0xba,
    WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY,
    0x8b, 0xca, 0x41, 0x2b, 0x4c, 0x24, 0x20, 0x40, 0x80, 0xfe, 0x01, 0x75,
    WAR3_SELECTION_ANY, 0x3b, 0xc8, 0x0f, 0x42, 0xd9
};

static const uint16_t SIG_CONTROL_SYNC[] = {
    0x41, 0x8b, 0x2e, 0x33, 0xdb, 0x85, 0xed, 0x74, WAR3_SELECTION_ANY,
    0x48, 0x89, 0x7c, 0x24, 0x48, 0x8b, 0xfb, 0x83, 0xfb, WAR3_SELECTION_ANY,
    0x73, 0x21, 0x49, 0x8b, 0x56, 0x08, 0x41, 0xb1, 0x01
};

static const uint16_t SIG_CONTROL_LOCAL[] = {
    0x41, 0x8b, 0x2e, 0x33, 0xdb, 0x85, 0xed, 0x74, WAR3_SELECTION_ANY,
    0x48, 0x89, 0x7c, 0x24, 0x48, 0x8b, 0xfb,
    0x0f, 0x1f, 0x80, 0x00, 0x00, 0x00, 0x00, 0x83, 0xfb, WAR3_SELECTION_ANY, 0x73, 0x21
};

static const uint16_t SIG_GRID_ROWS[] = {
    0x41, 0xb9, 0x07, 0x00, 0x00, 0x00, 0x4c, 0x8b, 0xc7, 0x41, 0x8b, 0xd1,
    0x48, 0x8b, 0x8f, 0xf8, 0x01, 0x00, 0x00, 0xe8,
    WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY,
    0xba, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY,
    0x44, 0x8d, 0x42, WAR3_SELECTION_ANY, 0x48, 0x8b, 0x8f, 0xf8, 0x01, 0x00, 0x00
};

static const uint16_t SIG_GRID_COLUMNS[] = {
    0xba, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY,
    0x44, 0x8d, 0x42, WAR3_SELECTION_ANY, 0x48, 0x8b, 0x8f, 0xf8, 0x01, 0x00, 0x00,
    0xe8, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, 0x33, 0xf6
};

static const uint16_t SIG_UI_CTOR_ROWS[] = {
    0x44, 0x8b, 0xc6, 0x8b, 0xd3, 0x48, 0x8b, 0x8f, 0xf8, 0x01, 0x00, 0x00, 0xe8,
    WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY,
    0xff, 0xc3, 0x83, 0xfb, 0x06, 0x7c, 0xb2, 0xff, 0xc6, 0x83, 0xfe,
    WAR3_SELECTION_ANY, 0x7c, 0x9b
};

static const uint16_t SIG_UI_INIT_ROWS[] = {
    0x44, 0x8b, 0xc7, 0x8b, 0xd3, 0x48, 0x8b, 0x8e, 0xf8, 0x01, 0x00, 0x00, 0xe8,
    WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY,
    0xff, 0xc3, 0x83, 0xfb, 0x06, 0x7c, 0xb2, 0xff, 0xc7, 0x83, 0xff,
    WAR3_SELECTION_ANY, 0x7c, 0x9f
};

static const uint16_t SIG_UI_DESTROY_ROWS[] = {
    0x33, 0xdb, 0x48, 0x8b, 0x86, 0xf8, 0x01, 0x00, 0x00,
    0x48, 0x8b, 0x90, 0x10, 0x02, 0x00, 0x00, 0x48, 0x8b, 0x44, 0x3a, 0x08,
    0x48, 0x8b, 0x0c, 0x18, 0x48, 0x81, 0xc1, 0xc0, 0x00, 0x00, 0x00,
    0x48, 0x8b, 0x01, 0xff, 0x10, 0x48, 0x83, 0xc3, 0x08, 0x48, 0x83, 0xfb, 0x30,
    0x7c, WAR3_SELECTION_ANY, 0x48, 0x83, 0xc7, 0x18, 0x48, 0x83, 0xff,
    WAR3_SELECTION_ANY, 0x7c, WAR3_SELECTION_ANY
};

static const uint16_t SIG_REFRESH_OUTER[] = {
    0x45, 0x85, 0xf6, 0x0f, 0x84,
    WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY,
    0x4c, 0x8b, 0xed, 0x0f, 0x1f, 0x80, 0x00, 0x00, 0x00, 0x00,
    0x83, 0xfe, WAR3_SELECTION_ANY, 0x0f, 0x83,
    WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY,
    0x48, 0x8b, 0x44, 0x24, 0x50
};

static const uint16_t SIG_REFRESH_INNER[] = {
    0x44, 0x8b, 0x7c, 0x24, 0x30, 0x45, 0x85, 0xff, 0x0f, 0x84,
    WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY,
    0x45, 0x33, 0xf6, 0x83, 0xfe, WAR3_SELECTION_ANY, 0x0f, 0x83,
    WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY,
    0x48, 0x8b, 0x44, 0x24, 0x38
};

static const uint16_t SIG_SELECTION_INPUT_LIMIT[] = {
    0x4d, 0x85, 0xe4, 0x0f, 0x84,
    WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY,
    0x0f, 0xb6, 0x75, 0x20, 0x40, 0x88, 0xb4, 0x24, 0xc0, 0x00, 0x00, 0x00,
    0x8b, 0x5d, 0x28, 0x83, 0xfb, WAR3_SELECTION_ANY, 0x0f, 0x87,
    WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY
};

static const uint16_t SIG_SELECTION_DRAG_CAPACITY[] = {
    0x8b, 0x45, 0x6f,
    0xba, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY,
    0x80, 0x39, 0x03,
    0x0f, 0x44, 0xc2,
    0x3b, 0xc6,
    0x0f, 0x42, 0xf0,
    0x8b, 0xd6,
    0x48, 0x8d, 0x4d, 0x8f,
    0xe8, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY, WAR3_SELECTION_ANY
};

static const PatchSpec PATCHES[WAR3_SELECTION_PATCH_COUNT] = {
    {"local selection", SIG_ADD_LOCAL, ARRAY_COUNT(SIG_ADD_LOCAL), 6, 0x0c, 0x18, 1},
    {"selection command", SIG_COMMAND_CTOR, ARRAY_COUNT(SIG_COMMAND_CTOR), 28, 0x0000000c, 0x00000018, 4},
    {"selection capacity", SIG_CAPACITY, ARRAY_COUNT(SIG_CAPACITY), 7, 0x0000000c, 0x00000018, 4},
    {"control group sync", SIG_CONTROL_SYNC, ARRAY_COUNT(SIG_CONTROL_SYNC), 18, 0x0c, 0x18, 1},
    {"control group local", SIG_CONTROL_LOCAL, ARRAY_COUNT(SIG_CONTROL_LOCAL), 25, 0x0c, 0x18, 1},
    {"portrait grid rows", SIG_GRID_ROWS, ARRAY_COUNT(SIG_GRID_ROWS), 25, 0x00000002, 0x00000004, 4},
    {"portrait grid columns", SIG_GRID_COLUMNS, ARRAY_COUNT(SIG_GRID_COLUMNS), 8, 0x04, 0x02, 1},
    {"portrait constructor", SIG_UI_CTOR_ROWS, ARRAY_COUNT(SIG_UI_CTOR_ROWS), 28, 0x02, 0x04, 1},
    {"portrait initializer", SIG_UI_INIT_ROWS, ARRAY_COUNT(SIG_UI_INIT_ROWS), 28, 0x02, 0x04, 1},
    {"portrait destructor", SIG_UI_DESTROY_ROWS, ARRAY_COUNT(SIG_UI_DESTROY_ROWS), 54, 0x30, 0x60, 1},
    {"portrait refresh outer", SIG_REFRESH_OUTER, ARRAY_COUNT(SIG_REFRESH_OUTER), 21, 0x0c, 0x18, 1},
    {"portrait refresh inner", SIG_REFRESH_INNER, ARRAY_COUNT(SIG_REFRESH_INNER), 19, 0x0c, 0x18, 1},
    {"selection input limit", SIG_SELECTION_INPUT_LIMIT, ARRAY_COUNT(SIG_SELECTION_INPUT_LIMIT), 26, 0x0c, 0x18, 1},
    {"selection drag capacity", SIG_SELECTION_DRAG_CAPACITY,
     ARRAY_COUNT(SIG_SELECTION_DRAG_CAPACITY), 4, 0x0000000c, 0x00000018, 4},
};

static int patch_enabled_in_variant(uint32_t index) {
#if !WAR3_SELECTION_PATCHES_ENABLED
    (void)index;
    return 0;
#elif WAR3_PORTRAIT_PATCHES_ENABLED
    (void)index;
    return 1;
#else
    return index < 5u || index > 11u;
#endif
}

static uint32_t variant_enabled_value(uint32_t index) {
    return patch_enabled_in_variant(index)
        ? PATCHES[index].enabled_value
        : PATCHES[index].original_value;
}

static volatile LONG g_processing = 0;
static HMODULE g_module = NULL;
static HMODULE g_self_reference = NULL;
static BYTE *g_patch_addresses[WAR3_SELECTION_PATCH_COUNT];
static int g_addresses_valid = 0;
static int g_enabled = 0;
static PVOID g_exception_handler = NULL;
static BYTE *g_selection_breakpoints[4];
static BYTE *g_frame_capacity_breakpoint = NULL;
static volatile LONG g_breakpoint_mode = 0;
static uintptr_t g_operation_return = 0;
static volatile LONG64 g_hit_counts[WAR3_SELECTION_PATCH_COUNT];
static BYTE *g_diagnostic_breakpoints[4];
static volatile LONG64 g_diagnostic_hits[4];
static volatile uint64_t g_diagnostic_context[9];
static volatile uintptr_t g_selection_manager = 0;
static volatile DWORD g_breakpoint_thread_id = 0;
static volatile DWORD g_window_thread_id = 0;
static OrderHandlerRuntime g_order_handlers[WAR3_ORDER_HANDLER_COUNT];
static int g_order_handlers_valid = 0;
static BYTE *g_order_dispatch_breakpoint = NULL;
static size_t g_order_dispatch_return_stack_offset = 0u;
static volatile LONG g_order_owner_thread_id = 0;
static OrderThreadState g_order_thread_states[WAR3_ORDER_THREAD_STATE_COUNT];
static volatile LONG g_order_resolution_stage = 0;
static OrderHandlerFunction g_original_order_functions[WAR3_ORDER_HANDLER_COUNT];
static uintptr_t g_order_pointer_slots[WAR3_ORDER_HANDLER_COUNT];
static volatile LONG g_order_hook_state = 0;
static volatile LONG g_order_wrapper_count = 0;
static volatile LONG g_order_replay_thread_id = 0;
static CRITICAL_SECTION g_order_route_lock;
static volatile LONG g_order_route_lock_initialized = 0;
static volatile LONG g_order_route_poisoned = 0;
static void *volatile g_unit_order_dispatch_original = NULL;
static volatile LONG g_order_observer_patch_applied = 0;
static volatile LONG g_order_observer_active = 0;
static volatile DWORD g_order_observer_thread_id = 0;
static volatile LONG g_order_observer_count = 0;
static volatile LONG g_order_observer_flags = 0;
static volatile LONG g_order_observer_single_recipient = 0;
static volatile LONG g_order_observer_invalid_return = 0;
static volatile LONG64 g_order_observer_invalid_return_rva = 0;
static volatile LONG g_order_observer_invalid_registers = 0;
static volatile LONG g_order_observer_breakpoint_active = 0;
static DWORD64 g_order_observer_saved_dr3 = 0u;
static DWORD64 g_order_observer_saved_dr7 = 0u;
static volatile LONG g_order_observer_test_mode = 0;
static uint8_t g_order_observer_test_r12 = 0u;
static uint8_t g_order_observer_test_r13 = 0u;
static uint8_t g_order_observer_test_dil = 0u;
static HANDLE g_selection_thread = NULL;
static HANDLE g_selection_request_event = NULL;
static HANDLE g_selection_ready_event = NULL;
static volatile LONG g_selection_thread_stop = 0;
static volatile LONG g_selection_request_pending = 0;
static volatile DWORD g_selection_request_thread_id = 0;
static volatile LONG g_selection_request_order_index = -1;
static volatile DWORD g_selection_request_error = ERROR_SUCCESS;
static volatile LONG g_extended_selection_active = 0;
static volatile LONG g_auto_enable_state = 0;
static volatile LONG g_auto_enable_attempts = 0;
static volatile DWORD g_auto_enable_error = ERROR_IO_PENDING;
static volatile DWORD g_auto_enable_thread_id = 0;

__declspec(dllexport) DWORD WINAPI War3SelectionLimitConfigureBreakpoints(
    DWORD thread_id,
    const uint64_t *addresses,
    uint32_t count,
    int enable
);
#if WAR3_CLIENTSDK_CALL_PROBE_ENABLED
static BYTE *g_clientsdk_call_breakpoint = NULL;
static volatile LONG g_clientsdk_call_armed = 0;
#endif
#if WAR3_CLIENTSDK_NULL_GUARD_ENABLED
static BYTE *g_clientsdk_guard_address = NULL;
static BYTE g_clientsdk_guard_original = 0;
static int8_t g_clientsdk_guard_displacement = 0;
static volatile LONG g_clientsdk_guard_installed = 0;
#endif

#if WAR3_CRASH_TRACE_ENABLED
static HANDLE g_crash_trace_file = INVALID_HANDLE_VALUE;
static HANDLE g_crash_trace_mapping = NULL;
static CrashTraceFile *g_crash_trace = NULL;

static DWORD open_crash_trace(void) {
    wchar_t path[MAX_PATH];
    wchar_t *separator;
    DWORD length;
    LARGE_INTEGER file_size;

    if (g_crash_trace) {
        return ERROR_SUCCESS;
    }
    length = GetModuleFileNameW(g_module, path, ARRAY_COUNT(path));
    if (!length) {
        return GetLastError();
    }
    if (length >= ARRAY_COUNT(path)) {
        return ERROR_INSUFFICIENT_BUFFER;
    }
    separator = wcsrchr(path, L'\\');
    if (!separator) {
        return ERROR_BAD_PATHNAME;
    }
    swprintf(
        separator + 1,
        ARRAY_COUNT(path) - (size_t)(separator + 1 - path),
        L"war3_selection_crash_%lu.bin",
        GetCurrentProcessId()
    );
    g_crash_trace_file = CreateFileW(
        path,
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL
    );
    if (g_crash_trace_file == INVALID_HANDLE_VALUE) {
        return GetLastError();
    }
    file_size.QuadPart = (LONGLONG)sizeof(CrashTraceFile);
    if (!SetFilePointerEx(g_crash_trace_file, file_size, NULL, FILE_BEGIN) ||
        !SetEndOfFile(g_crash_trace_file)) {
        DWORD error = GetLastError();
        CloseHandle(g_crash_trace_file);
        g_crash_trace_file = INVALID_HANDLE_VALUE;
        return error;
    }
    g_crash_trace_mapping = CreateFileMappingW(
        g_crash_trace_file,
        NULL,
        PAGE_READWRITE,
        0,
        0,
        NULL
    );
    if (!g_crash_trace_mapping) {
        DWORD error = GetLastError();
        CloseHandle(g_crash_trace_file);
        g_crash_trace_file = INVALID_HANDLE_VALUE;
        return error;
    }
    g_crash_trace = (CrashTraceFile *)MapViewOfFile(
        g_crash_trace_mapping,
        FILE_MAP_ALL_ACCESS,
        0,
        0,
        sizeof(CrashTraceFile)
    );
    if (!g_crash_trace) {
        DWORD error = GetLastError();
        CloseHandle(g_crash_trace_mapping);
        CloseHandle(g_crash_trace_file);
        g_crash_trace_mapping = NULL;
        g_crash_trace_file = INVALID_HANDLE_VALUE;
        return error;
    }
    ZeroMemory(g_crash_trace, sizeof(*g_crash_trace));
    g_crash_trace->magic = WAR3_CRASH_TRACE_MAGIC;
    g_crash_trace->version = WAR3_CRASH_TRACE_VERSION;
    g_crash_trace->process_id = GetCurrentProcessId();
    g_crash_trace->record_count = WAR3_CRASH_TRACE_RECORD_COUNT;
    FlushViewOfFile(g_crash_trace, sizeof(*g_crash_trace));
    return ERROR_SUCCESS;
}

static void close_crash_trace(void) {
    if (g_crash_trace) {
        FlushViewOfFile(g_crash_trace, sizeof(*g_crash_trace));
        UnmapViewOfFile(g_crash_trace);
        g_crash_trace = NULL;
    }
    if (g_crash_trace_mapping) {
        CloseHandle(g_crash_trace_mapping);
        g_crash_trace_mapping = NULL;
    }
    if (g_crash_trace_file != INVALID_HANDLE_VALUE) {
        CloseHandle(g_crash_trace_file);
        g_crash_trace_file = INVALID_HANDLE_VALUE;
    }
}

static void record_crash_trace(
    PEXCEPTION_POINTERS exception,
    const OrderThreadState *thread_state
) {
    CrashTraceFile *trace = g_crash_trace;
    CrashTraceRecord *record;
    CONTEXT *context;
    EXCEPTION_RECORD *exception_record;
    uint64_t sequence;
    uint32_t index;

    if (!trace || !exception || !exception->ExceptionRecord ||
        !exception->ContextRecord) {
        return;
    }
    if (InterlockedCompareExchange(&trace->writing, 1, 0) != 0) {
        return;
    }
    exception_record = exception->ExceptionRecord;
    context = exception->ContextRecord;
    sequence = (uint64_t)InterlockedIncrement64(&trace->next_sequence);
    index = (uint32_t)((sequence - 1u) % WAR3_CRASH_TRACE_RECORD_COUNT);
    record = &trace->records[index];
    ZeroMemory(record, sizeof(*record));
    record->sequence = sequence;
    record->exception_code = exception_record->ExceptionCode;
    record->thread_id = GetCurrentThreadId();
    record->exception_address =
        (uint64_t)(uintptr_t)exception_record->ExceptionAddress;
    record->rip = context->Rip;
    record->rsp = context->Rsp;
    record->rbp = context->Rbp;
    record->rax = context->Rax;
    record->rbx = context->Rbx;
    record->rcx = context->Rcx;
    record->rdx = context->Rdx;
    record->r8 = context->R8;
    record->r9 = context->R9;
    record->dr0 = context->Dr0;
    record->dr1 = context->Dr1;
    record->dr2 = context->Dr2;
    record->dr3 = context->Dr3;
    record->dr6 = context->Dr6;
    record->dr7 = context->Dr7;
    if (exception_record->NumberParameters > 0u) {
        record->exception_information0 =
            exception_record->ExceptionInformation[0];
    }
    if (exception_record->NumberParameters > 1u) {
        record->exception_information1 =
            exception_record->ExceptionInformation[1];
    }
    record->selection_manager = g_selection_manager;
    record->eflags = context->EFlags;
    __try {
        uint32_t stack_index;
        const uint64_t *stack = (const uint64_t *)(uintptr_t)context->Rsp;
        for (stack_index = 0; stack_index < ARRAY_COUNT(record->stack); ++stack_index) {
            record->stack[stack_index] = stack[stack_index];
            record->stack_count = stack_index + 1u;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    record->breakpoint_mode = (uint32_t)g_breakpoint_mode;
    if (thread_state) {
        record->order_index = thread_state->order_index;
        record->order_active = thread_state->order_active;
    }
    MemoryBarrier();
    InterlockedExchange64(&trace->committed_sequence, (LONG64)sequence);
    InterlockedExchange(&trace->writing, 0);
}

static void record_context_trace(
    DWORD exception_code,
    CONTEXT *context,
    const OrderThreadState *thread_state,
    uint64_t information0,
    uint64_t information1
) {
    EXCEPTION_RECORD exception_record;
    EXCEPTION_POINTERS exception;
    if (!context) {
        return;
    }
    ZeroMemory(&exception_record, sizeof(exception_record));
    ZeroMemory(&exception, sizeof(exception));
    exception_record.ExceptionCode = exception_code;
    exception_record.ExceptionAddress = (PVOID)(uintptr_t)context->Rip;
    exception_record.NumberParameters = 2u;
    exception_record.ExceptionInformation[0] = information0;
    exception_record.ExceptionInformation[1] = information1;
    exception.ExceptionRecord = &exception_record;
    exception.ContextRecord = context;
    record_crash_trace(&exception, thread_state);
}
#endif

typedef struct UnitListNode {
    struct UnitListNode *previous;
    struct UnitListNode *next;
    uintptr_t unit;
} UnitListNode;

typedef struct UnitSetView {
    uintptr_t vtable;
    uint32_t link_offset;
    uint32_t padding;
    UnitListNode *last;
    UnitListNode *first;
    uint32_t count;
    uint8_t enumerating;
} UnitSetView;

#define WAR3_MIRROR_UNIT_SET_OFFSET 0x388u
#define WAR3_LOCAL_UNIT_SET_OFFSET 0x3d0u
#define WAR3_NATIVE_SELECTION_LIMIT 12u
#define WAR3_UNIT_SET_ADD_RVA 0x0d7f430u
#define WAR3_UNIT_SET_REMOVE_RVA 0x0d7fbf0u
#define WAR3_ADD_TO_SUBGROUPS_RVA 0x0cae390u
#define WAR3_REMOVE_FROM_SUBGROUPS_RVA 0x0cb2f30u
#define WAR3_TRANSIENT_SYNC_TEST_ADDITIONS 0u

typedef void (__fastcall *UnitSetAddFunction)(
    UnitSetView *set,
    uintptr_t unit,
    uint8_t allow_duplicates,
    uint8_t group_like_units
);
typedef void (__fastcall *UnitSetRemoveFunction)(
    UnitSetView *set,
    uintptr_t unit
);
typedef void (__fastcall *SelectionSubgroupFunction)(
    void *selection,
    uintptr_t unit
);

typedef struct UnitSetSnapshot {
    uintptr_t vtable;
    uint32_t link_offset;
    uint32_t count;
    uintptr_t units[24];
} UnitSetSnapshot;

typedef struct OrderReplayState {
    UnitSetView *sync_set;
    UnitSetView *mirror_set;
    UnitSetView *local_set;
    UnitSetAddFunction add;
    UnitSetRemoveFunction remove;
    UnitSetSnapshot original_sync;
    UnitSetSnapshot original_mirror;
    UnitSetSnapshot original_local;
    uintptr_t extra_units[WAR3_NATIVE_SELECTION_LIMIT];
    uint32_t extra_count;
    uint32_t diagnostic_step;
    uint64_t diagnostic_value;
    int prepared;
    int sync_changed;
} OrderReplayState;

typedef struct TransientSyncState {
    void *selection;
    UnitSetView *sync_set;
    UnitSetRemoveFunction remove;
    SelectionSubgroupFunction remove_from_subgroups;
    uintptr_t added_units[24];
    uint8_t subgroup_added[24];
    uint32_t original_count;
    uint32_t added_count;
    uint32_t diagnostic_step;
    uint64_t diagnostic_value;
} TransientSyncState;

enum OrderDiagnosticStage {
    ORDER_DIAGNOSTIC_ENTER = 1,
    ORDER_DIAGNOSTIC_SYNC_PREPARE = 2,
    ORDER_DIAGNOSTIC_HANDLER_PREPARE = 3,
    ORDER_DIAGNOSTIC_ORIGINAL = 4,
    ORDER_DIAGNOSTIC_SYNC_RESTORE = 5,
    ORDER_DIAGNOSTIC_REPLAY_PREPARE = 6,
    ORDER_DIAGNOSTIC_REPLAY_INSTALL = 7,
    ORDER_DIAGNOSTIC_REPLAY_ORIGINAL = 8,
    ORDER_DIAGNOSTIC_REPLAY_RESTORE = 9,
    ORDER_DIAGNOSTIC_OBSERVER_RETURN = 10
};

static DWORD prepare_order_handler(uint32_t index);

static void record_order_diagnostic(
    uint32_t index,
    DWORD error,
    uint32_t stage,
    uint64_t detail0,
    uint64_t detail1,
    uint64_t detail2,
    uint64_t detail3
) {
    g_diagnostic_context[0] = index;
    g_diagnostic_context[1] = error;
    g_diagnostic_context[2] = GetCurrentThreadId();
    g_diagnostic_context[3] = index < WAR3_ORDER_HANDLER_COUNT
        ? g_order_pointer_slots[index]
        : 0u;
    g_diagnostic_context[4] = stage;
    g_diagnostic_context[5] = detail0;
    g_diagnostic_context[6] = detail1;
    g_diagnostic_context[7] = detail2;
    g_diagnostic_context[8] = detail3;
}

static int executable_image_protection(DWORD protection) {
    if (protection & (PAGE_GUARD | PAGE_NOACCESS)) {
        return 0;
    }
    protection &= 0xffu;
    return protection == PAGE_EXECUTE ||
        protection == PAGE_EXECUTE_READ ||
        protection == PAGE_EXECUTE_READWRITE ||
        protection == PAGE_EXECUTE_WRITECOPY;
}

#if WAR3_CLIENTSDK_NULL_GUARD_ENABLED
static DWORD write_executable_byte(
    BYTE *address,
    BYTE expected,
    BYTE replacement
) {
    MEMORY_BASIC_INFORMATION memory;
    SIZE_T written = 0;
    DWORD old_protection;
    DWORD restored_protection;
    if (!address || *address != expected ||
        !VirtualQuery(address, &memory, sizeof(memory)) ||
        memory.State != MEM_COMMIT ||
        !executable_image_protection(memory.Protect)) {
        return ERROR_INVALID_DATA;
    }
    if (WriteProcessMemory(
            GetCurrentProcess(),
            address,
            &replacement,
            sizeof(replacement),
            &written
        ) &&
        written == sizeof(replacement)) {
        FlushInstructionCache(GetCurrentProcess(), address, sizeof(replacement));
        return *address == replacement ? ERROR_SUCCESS : ERROR_WRITE_FAULT;
    }
    if (!VirtualProtect(
            address,
            sizeof(replacement),
            PAGE_EXECUTE_READWRITE,
            &old_protection
        )) {
        return GetLastError();
    }
    *address = replacement;
    FlushInstructionCache(GetCurrentProcess(), address, sizeof(replacement));
    if (!VirtualProtect(
            address,
            sizeof(replacement),
            old_protection,
            &restored_protection
        )) {
        return GetLastError();
    }
    return *address == replacement ? ERROR_SUCCESS : ERROR_WRITE_FAULT;
}

static DWORD install_clientsdk_null_guard(void) {
    HMODULE clientsdk = GetModuleHandleW(L"ClientSdk.dll");
    MEMORY_BASIC_INFORMATION memory;
    BYTE *address;
    BYTE bytes[4];
    DWORD error;
    if (!clientsdk ||
        WAR3_CLIENTSDK_NULL_CALL_RVA >
            UINTPTR_MAX - (uintptr_t)clientsdk) {
        return ERROR_MOD_NOT_FOUND;
    }
    address = (BYTE *)(
        (uintptr_t)clientsdk + WAR3_CLIENTSDK_NULL_CALL_RVA
    );
    if (!VirtualQuery(address, &memory, sizeof(memory)) ||
        memory.State != MEM_COMMIT ||
        (uintptr_t)memory.AllocationBase != (uintptr_t)clientsdk ||
        !executable_image_protection(memory.Protect)) {
        return ERROR_BAD_EXE_FORMAT;
    }
    __try {
        memcpy(bytes, address, sizeof(bytes));
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return ERROR_PARTIAL_COPY;
    }
    if (bytes[0] != 0x48u || bytes[1] != 0xffu || bytes[2] != 0x55u) {
        return ERROR_REVISION_MISMATCH;
    }
    g_clientsdk_guard_address = address;
    g_clientsdk_guard_original = bytes[0];
    g_clientsdk_guard_displacement = (int8_t)bytes[3];
    error = write_executable_byte(address, bytes[0], 0xccu);
    if (error != ERROR_SUCCESS) {
        g_clientsdk_guard_address = NULL;
        g_clientsdk_guard_original = 0;
        g_clientsdk_guard_displacement = 0;
        return error;
    }
    InterlockedExchange(&g_clientsdk_guard_installed, 1);
    return ERROR_SUCCESS;
}

static DWORD remove_clientsdk_null_guard(void) {
    DWORD error = ERROR_SUCCESS;
    if (InterlockedExchange(&g_clientsdk_guard_installed, 0) != 0 &&
        g_clientsdk_guard_address) {
        error = write_executable_byte(
            g_clientsdk_guard_address,
            0xccu,
            g_clientsdk_guard_original
        );
    }
    g_clientsdk_guard_address = NULL;
    g_clientsdk_guard_original = 0;
    g_clientsdk_guard_displacement = 0;
    return error;
}
#endif

static DWORD validate_unit_set_function(
    uintptr_t function,
    uintptr_t expected_rva
) {
    MEMORY_BASIC_INFORMATION memory;
    HMODULE module = GetModuleHandleW(NULL);
    uintptr_t module_base = (uintptr_t)module;
    if (!function || !module ||
        !VirtualQuery((const void *)function, &memory, sizeof(memory))) {
        return ERROR_INVALID_ADDRESS;
    }
    if (memory.State != MEM_COMMIT ||
        (memory.Type != MEM_IMAGE && memory.Type != MEM_MAPPED) ||
        !executable_image_protection(memory.Protect) ||
        (uintptr_t)memory.AllocationBase != module_base) {
        return ERROR_BAD_EXE_FORMAT;
    }
    if (function < module_base ||
        function - module_base != expected_rva) {
        return ERROR_REVISION_MISMATCH;
    }
    return ERROR_SUCCESS;
}

static DWORD resolve_known_image_function(
    uintptr_t rva,
    const BYTE *signature,
    size_t signature_size,
    uintptr_t *function
) {
    HMODULE module = GetModuleHandleW(NULL);
    uintptr_t module_base = (uintptr_t)module;
    uintptr_t address;
    DWORD error;
    if (!module || !function || rva > UINTPTR_MAX - module_base) {
        return ERROR_INVALID_ADDRESS;
    }
    address = module_base + rva;
    error = validate_unit_set_function(address, rva);
    if (error != ERROR_SUCCESS) {
        return error;
    }
    __try {
        if (memcmp((const void *)address, signature, signature_size) != 0) {
            return ERROR_REVISION_MISMATCH;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return ERROR_PARTIAL_COPY;
    }
    *function = address;
    return ERROR_SUCCESS;
}

static DWORD snapshot_unit_set(
    UnitSetView *set,
    UnitSetSnapshot *snapshot
) {
    UnitListNode *node;
    UnitListNode *sentinel;
    UnitListNode *previous;
    UnitListNode *first;
    UnitListNode *last;
    uintptr_t vtable;
    uint32_t link_offset;
    uint32_t count;
    uint32_t index;
    uint8_t enumerating;
    if (!set || !snapshot) {
        return ERROR_INVALID_PARAMETER;
    }
    ZeroMemory(snapshot, sizeof(*snapshot));
    __try {
        vtable = set->vtable;
        link_offset = set->link_offset;
        first = set->first;
        last = set->last;
        count = set->count;
        enumerating = set->enumerating;
        sentinel = (UnitListNode *)&set->last;
        if (!vtable || enumerating || count > ARRAY_COUNT(snapshot->units)) {
            return ERROR_INVALID_DATA;
        }
        if (count == 0u) {
            int null_empty = first == NULL && last == NULL;
            int sentinel_empty =
                (uintptr_t)first == ((uintptr_t)sentinel | 1u) &&
                last == sentinel;
            if (!null_empty && !sentinel_empty) {
                return ERROR_INVALID_DATA;
            }
        } else if (!first || !last) {
            return ERROR_INVALID_DATA;
        }
        previous = sentinel;
        node = first;
        for (index = 0; index < count; ++index) {
            uint32_t duplicate;
            if (!node || ((uintptr_t)node & (sizeof(uintptr_t) - 1u)) != 0u ||
                node->previous != previous ||
                !node->unit ||
                (node->unit & (sizeof(uintptr_t) - 1u)) != 0u) {
                return ERROR_INVALID_DATA;
            }
            for (duplicate = 0; duplicate < index; ++duplicate) {
                if (snapshot->units[duplicate] == node->unit) {
                    return ERROR_INVALID_DATA;
                }
            }
            snapshot->units[index] = node->unit;
            previous = node;
            node = node->next;
        }
        if ((count == 0u && previous != sentinel) ||
            (count != 0u &&
             ((uintptr_t)node != ((uintptr_t)sentinel | 1u) ||
              previous != last)) ||
            set->vtable != vtable ||
            set->link_offset != link_offset ||
            set->first != first ||
            set->last != last ||
            set->count != count ||
            set->enumerating != enumerating) {
            return ERROR_INVALID_DATA;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return ERROR_PARTIAL_COPY;
    }
    snapshot->vtable = vtable;
    snapshot->link_offset = link_offset;
    snapshot->count = count;
    return ERROR_SUCCESS;
}

static int snapshot_contains_unit(
    const UnitSetSnapshot *snapshot,
    uintptr_t unit
) {
    uint32_t index;
    for (index = 0; index < snapshot->count; ++index) {
        if (snapshot->units[index] == unit) {
            return 1;
        }
    }
    return 0;
}

static DWORD validate_order_replay_snapshots(OrderReplayState *state) {
    uint32_t index;
    if (!state) {
        return ERROR_INVALID_PARAMETER;
    }
    state->diagnostic_step = 5u;
    state->diagnostic_value =
        ((uint64_t)state->original_sync.count << 40u) |
        ((uint64_t)state->original_mirror.count << 20u) |
        state->original_local.count;
    state->extra_count = 0u;
    if (state->original_sync.count == 0u ||
        state->original_sync.count > WAR3_NATIVE_SELECTION_LIMIT ||
        state->original_local.count <= WAR3_NATIVE_SELECTION_LIMIT ||
        state->original_local.count > ARRAY_COUNT(state->original_local.units) ||
        state->original_mirror.count != state->original_local.count) {
        return ERROR_INVALID_DATA;
    }
    for (index = 0; index < state->original_sync.count; ++index) {
        if (!snapshot_contains_unit(
                &state->original_local,
                state->original_sync.units[index]
            )) {
            state->diagnostic_step = 6u;
            state->diagnostic_value = index;
            return ERROR_INVALID_DATA;
        }
    }
    for (index = 0; index < state->original_local.count; ++index) {
        uintptr_t unit = state->original_local.units[index];
        if (!snapshot_contains_unit(&state->original_mirror, unit)) {
            state->diagnostic_step = 7u;
            state->diagnostic_value = index;
            return ERROR_INVALID_DATA;
        }
        if (!snapshot_contains_unit(&state->original_sync, unit)) {
            if (state->extra_count >= ARRAY_COUNT(state->extra_units)) {
                state->diagnostic_step = 8u;
                state->diagnostic_value = state->extra_count;
                return ERROR_INSUFFICIENT_BUFFER;
            }
            state->extra_units[state->extra_count++] = unit;
        }
    }
    if (state->extra_count == 0u ||
        state->extra_count !=
            state->original_local.count - state->original_sync.count) {
        state->diagnostic_step = 9u;
        state->diagnostic_value = state->extra_count;
        return ERROR_INVALID_DATA;
    }
    return ERROR_SUCCESS;
}

static DWORD resolve_unit_set_functions(
    const UnitSetSnapshot *sync,
    UnitSetAddFunction *add,
    UnitSetRemoveFunction *remove
) {
    uintptr_t *vtable = (uintptr_t *)sync->vtable;
    uintptr_t add_address;
    uintptr_t remove_address;
    DWORD error;
    __try {
        add_address = vtable[1];
        remove_address = vtable[2];
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return ERROR_PARTIAL_COPY;
    }
    error = validate_unit_set_function(add_address, WAR3_UNIT_SET_ADD_RVA);
    if (error != ERROR_SUCCESS) {
        return error;
    }
    error = validate_unit_set_function(remove_address, WAR3_UNIT_SET_REMOVE_RVA);
    if (error != ERROR_SUCCESS) {
        return error;
    }
    *add = (UnitSetAddFunction)add_address;
    *remove = (UnitSetRemoveFunction)remove_address;
    return ERROR_SUCCESS;
}

static int unit_set_snapshots_equal(
    const UnitSetSnapshot *left,
    const UnitSetSnapshot *right
) {
    return left->vtable == right->vtable &&
        left->link_offset == right->link_offset &&
        left->count == right->count &&
        memcmp(
            left->units,
            right->units,
            left->count * sizeof(left->units[0])
        ) == 0;
}

static DWORD replay_remove_unit(
    OrderReplayState *state,
    uintptr_t unit
) {
    uint32_t before;
    uint32_t after;
    __try {
        if (!state->sync_set || !state->remove ||
            state->sync_set->enumerating ||
            state->sync_set->count == 0u) {
            return ERROR_INVALID_DATA;
        }
        before = state->sync_set->count;
        state->remove(state->sync_set, unit);
        after = state->sync_set->count;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return GetExceptionCode();
    }
    return after == before - 1u ? ERROR_SUCCESS : ERROR_INVALID_DATA;
}

static DWORD replay_add_unit(
    OrderReplayState *state,
    uintptr_t unit
) {
    uint32_t before;
    uint32_t after;
    __try {
        if (!state->sync_set || !state->add ||
            state->sync_set->enumerating ||
            state->sync_set->count >= WAR3_NATIVE_SELECTION_LIMIT) {
            return ERROR_INVALID_DATA;
        }
        before = state->sync_set->count;
        state->add(state->sync_set, unit, 0u, 0u);
        after = state->sync_set->count;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return GetExceptionCode();
    }
    return after == before + 1u ? ERROR_SUCCESS : ERROR_INVALID_DATA;
}

static DWORD prepare_order_replay(OrderReplayState *state) {
    uintptr_t manager = g_selection_manager;
    UnitSetAddFunction mirror_add;
    UnitSetAddFunction local_add;
    UnitSetRemoveFunction mirror_remove;
    UnitSetRemoveFunction local_remove;
    DWORD error;
    if (!state) {
        return ERROR_INVALID_PARAMETER;
    }
    ZeroMemory(state, sizeof(*state));
    state->diagnostic_step = 1u;
    if (!manager || !g_window_thread_id ||
        GetCurrentThreadId() != g_window_thread_id) {
        state->diagnostic_value = g_window_thread_id;
        return ERROR_INVALID_THREAD_ID;
    }
    state->sync_set = (UnitSetView *)manager;
    state->mirror_set =
        (UnitSetView *)(manager + WAR3_MIRROR_UNIT_SET_OFFSET);
    state->local_set =
        (UnitSetView *)(manager + WAR3_LOCAL_UNIT_SET_OFFSET);

    state->diagnostic_step = 2u;
    error = snapshot_unit_set(state->sync_set, &state->original_sync);
    if (error != ERROR_SUCCESS) {
        state->diagnostic_value = error;
        return error;
    }
    state->diagnostic_step = 3u;
    error = snapshot_unit_set(state->mirror_set, &state->original_mirror);
    if (error != ERROR_SUCCESS) {
        state->diagnostic_value = error;
        return error;
    }
    state->diagnostic_step = 4u;
    error = snapshot_unit_set(state->local_set, &state->original_local);
    if (error != ERROR_SUCCESS) {
        state->diagnostic_value = error;
        return error;
    }
    error = validate_order_replay_snapshots(state);
    if (error != ERROR_SUCCESS) {
        return error;
    }

    state->diagnostic_step = 10u;
    error = resolve_unit_set_functions(
        &state->original_sync,
        &state->add,
        &state->remove
    );
    if (error != ERROR_SUCCESS) {
        state->diagnostic_value = error;
        return error;
    }
    error = resolve_unit_set_functions(
        &state->original_mirror,
        &mirror_add,
        &mirror_remove
    );
    if (error != ERROR_SUCCESS) {
        state->diagnostic_value = error;
        return error;
    }
    error = resolve_unit_set_functions(
        &state->original_local,
        &local_add,
        &local_remove
    );
    if (error != ERROR_SUCCESS) {
        state->diagnostic_value = error;
        return error;
    }
    if (state->add != mirror_add || state->add != local_add ||
        state->remove != mirror_remove || state->remove != local_remove) {
        state->diagnostic_step = 11u;
        state->diagnostic_value =
            (uint64_t)(uintptr_t)state->add ^
            (uint64_t)(uintptr_t)state->remove;
        return ERROR_INVALID_DATA;
    }
    state->prepared = 1;
    return ERROR_SUCCESS;
}

static DWORD validate_order_replay_unchanged(OrderReplayState *state) {
    UnitSetSnapshot sync;
    UnitSetSnapshot mirror;
    UnitSetSnapshot local;
    DWORD error;
    error = snapshot_unit_set(state->sync_set, &sync);
    if (error == ERROR_SUCCESS) {
        error = snapshot_unit_set(state->mirror_set, &mirror);
    }
    if (error == ERROR_SUCCESS) {
        error = snapshot_unit_set(state->local_set, &local);
    }
    if (error != ERROR_SUCCESS) {
        return error;
    }
    return unit_set_snapshots_equal(&sync, &state->original_sync) &&
        unit_set_snapshots_equal(&mirror, &state->original_mirror) &&
        unit_set_snapshots_equal(&local, &state->original_local)
        ? ERROR_SUCCESS
        : ERROR_INVALID_DATA;
}

static DWORD install_extra_sync_batch(OrderReplayState *state) {
    UnitSetSnapshot expected;
    UnitSetSnapshot current;
    uint32_t index;
    DWORD error;
    if (!state || !state->prepared || state->extra_count == 0u ||
        state->extra_count > WAR3_NATIVE_SELECTION_LIMIT) {
        return ERROR_INVALID_STATE;
    }
    state->diagnostic_step = 20u;
    state->sync_changed = 1;
    index = state->original_sync.count;
    while (index > 0u) {
        --index;
        error = replay_remove_unit(state, state->original_sync.units[index]);
        if (error != ERROR_SUCCESS) {
            state->diagnostic_value =
                ((uint64_t)index << 32u) | error;
            return error;
        }
    }
    for (index = 0; index < state->extra_count; ++index) {
        error = replay_add_unit(state, state->extra_units[index]);
        if (error != ERROR_SUCCESS) {
            state->diagnostic_step = 21u;
            state->diagnostic_value =
                ((uint64_t)index << 32u) | error;
            return error;
        }
    }
    ZeroMemory(&expected, sizeof(expected));
    expected.vtable = state->original_sync.vtable;
    expected.link_offset = state->original_sync.link_offset;
    expected.count = state->extra_count;
    memcpy(
        expected.units,
        state->extra_units,
        state->extra_count * sizeof(expected.units[0])
    );
    error = snapshot_unit_set(state->sync_set, &current);
    if (error != ERROR_SUCCESS) {
        state->diagnostic_step = 22u;
        state->diagnostic_value = error;
        return error;
    }
    if (!unit_set_snapshots_equal(&current, &expected)) {
        state->diagnostic_step = 23u;
        state->diagnostic_value = current.count;
        return ERROR_INVALID_DATA;
    }
    return ERROR_SUCCESS;
}

static DWORD restore_original_sync(OrderReplayState *state) {
    UnitSetSnapshot current;
    UnitSetSnapshot restored;
    UnitSetSnapshot mirror;
    UnitSetSnapshot local;
    DWORD last_error = ERROR_INVALID_DATA;
    DWORD error = ERROR_SUCCESS;
    uint32_t attempt;
    uint32_t index;
    if (!state || !state->prepared || !state->sync_changed) {
        return ERROR_SUCCESS;
    }
    ZeroMemory(&restored, sizeof(restored));
    ZeroMemory(&mirror, sizeof(mirror));
    ZeroMemory(&local, sizeof(local));
    for (attempt = 0u; attempt < 3u; ++attempt) {
        state->diagnostic_step = 30u;
        error = snapshot_unit_set(state->sync_set, &current);
        if (error != ERROR_SUCCESS) {
            state->diagnostic_value =
                ((uint64_t)attempt << 32u) | error;
            last_error = error;
            continue;
        }
        index = current.count;
        while (index > 0u) {
            --index;
            error = replay_remove_unit(state, current.units[index]);
            if (error != ERROR_SUCCESS) {
                state->diagnostic_step = 31u;
                state->diagnostic_value =
                    ((uint64_t)attempt << 48u) |
                    ((uint64_t)index << 32u) |
                    error;
                last_error = error;
            }
        }
        error = snapshot_unit_set(state->sync_set, &current);
        if (error != ERROR_SUCCESS || current.count != 0u) {
            state->diagnostic_step = 32u;
            state->diagnostic_value =
                ((uint64_t)attempt << 48u) |
                ((uint64_t)current.count << 32u) |
                error;
            last_error = error != ERROR_SUCCESS
                ? error
                : ERROR_INVALID_DATA;
            continue;
        }
        error = ERROR_SUCCESS;
        for (index = 0; index < state->original_sync.count; ++index) {
            error = replay_add_unit(
                state,
                state->original_sync.units[index]
            );
            if (error != ERROR_SUCCESS) {
                state->diagnostic_step = 33u;
                state->diagnostic_value =
                    ((uint64_t)attempt << 48u) |
                    ((uint64_t)index << 32u) |
                    error;
                last_error = error;
                break;
            }
        }
        if (error != ERROR_SUCCESS) {
            continue;
        }
        ZeroMemory(&restored, sizeof(restored));
        ZeroMemory(&mirror, sizeof(mirror));
        ZeroMemory(&local, sizeof(local));
        error = snapshot_unit_set(state->sync_set, &restored);
        if (error == ERROR_SUCCESS) {
            error = snapshot_unit_set(state->mirror_set, &mirror);
        }
        if (error == ERROR_SUCCESS) {
            error = snapshot_unit_set(state->local_set, &local);
        }
        if (error != ERROR_SUCCESS ||
            !unit_set_snapshots_equal(&restored, &state->original_sync) ||
            !unit_set_snapshots_equal(&mirror, &state->original_mirror) ||
            !unit_set_snapshots_equal(&local, &state->original_local)) {
            state->diagnostic_step = 34u;
            state->diagnostic_value =
                ((uint64_t)restored.count << 48u) |
                ((uint64_t)mirror.count << 32u) |
                ((uint64_t)local.count << 16u) |
                (error & 0xffffu);
            last_error = error != ERROR_SUCCESS
                ? error
                : ERROR_INVALID_DATA;
            continue;
        }
        state->sync_changed = 0;
        return ERROR_SUCCESS;
    }
    InterlockedExchange(&g_order_route_poisoned, 1);
    return last_error;
}

static DWORD restore_transient_sync(TransientSyncState *state) {
    DWORD first_error = ERROR_SUCCESS;
    while (state && state->added_count != 0u) {
        uint32_t before = 0u;
        uint32_t after = 0u;
        uint32_t added_index = state->added_count - 1u;
        uintptr_t unit = state->added_units[added_index];
        DWORD error = ERROR_SUCCESS;
        __try {
            if (!state->sync_set || !state->remove ||
                !state->selection || !state->remove_from_subgroups ||
                state->sync_set->enumerating ||
                state->sync_set->count == 0u) {
                error = ERROR_INVALID_DATA;
            } else {
                before = state->sync_set->count;
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            error = GetExceptionCode();
        }
        if (state->subgroup_added[added_index] &&
            state->selection && state->remove_from_subgroups) {
            __try {
                state->remove_from_subgroups(state->selection, unit);
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                if (error == ERROR_SUCCESS) {
                    error = GetExceptionCode();
                }
            }
        }
        if (before != 0u && state->sync_set && state->remove) {
            __try {
                state->remove(state->sync_set, unit);
                after = state->sync_set->count;
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                if (error == ERROR_SUCCESS) {
                    error = GetExceptionCode();
                }
            }
            if (after != before - 1u && error == ERROR_SUCCESS) {
                error = ERROR_INVALID_DATA;
            }
        }
        --state->added_count;
        if (first_error == ERROR_SUCCESS && error != ERROR_SUCCESS) {
            first_error = error;
        }
    }
    return first_error;
}

static DWORD prepare_transient_sync(TransientSyncState *state) {
    uintptr_t manager = g_selection_manager;
    UnitSetView *sync_set;
    UnitSetView *local_set;
    UnitSetSnapshot sync;
    UnitSetSnapshot local;
    UnitSetAddFunction add;
    UnitSetAddFunction local_add;
    UnitSetRemoveFunction remove;
    UnitSetRemoveFunction local_remove;
    SelectionSubgroupFunction add_to_subgroups;
    SelectionSubgroupFunction remove_from_subgroups;
    uintptr_t subgroup_function_address;
    static const BYTE add_to_subgroups_signature[] = {
        0x48, 0x85, 0xd2, 0x0f, 0x84, 0x8d, 0x01, 0x00, 0x00,
        0x41, 0x54, 0x41, 0x55, 0x48, 0x83, 0xec, 0x58
    };
    static const BYTE remove_from_subgroups_signature[] = {
        0x48, 0x85, 0xd2, 0x0f, 0x84, 0x18, 0x02, 0x00, 0x00,
        0x48, 0x8b, 0xc4, 0x41, 0x55, 0x41, 0x57, 0x48, 0x83, 0xec, 0x58
    };
    uint32_t local_count;
    uint32_t index;
    DWORD error;
    if (!state) {
        return ERROR_INVALID_PARAMETER;
    }
    ZeroMemory(state, sizeof(*state));
    if (!manager) {
        return ERROR_SUCCESS;
    }
    sync_set = (UnitSetView *)manager;
    local_set = (UnitSetView *)(manager + WAR3_LOCAL_UNIT_SET_OFFSET);
    state->diagnostic_step = 1u;
    __try {
        local_count = local_set->count;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        state->diagnostic_value = GetExceptionCode();
        return ERROR_PARTIAL_COPY;
    }
    state->diagnostic_value = local_count;
    if (local_count <= 12u) {
        return ERROR_SUCCESS;
    }
    if (local_count > ARRAY_COUNT(local.units)) {
        return ERROR_INVALID_DATA;
    }
    state->diagnostic_step = 2u;
    error = snapshot_unit_set(local_set, &local);
    if (error != ERROR_SUCCESS) {
        state->diagnostic_value = error;
        return error;
    }
    state->diagnostic_step = 3u;
    error = snapshot_unit_set(sync_set, &sync);
    if (error != ERROR_SUCCESS) {
        state->diagnostic_value = error;
        return error;
    }
    state->diagnostic_step = 4u;
    state->diagnostic_value =
        ((uint64_t)sync.count << 32u) | (uint64_t)local.count;
    if (local.count != local_count ||
        sync.count > local.count ||
        sync.link_offset != local.link_offset) {
        return ERROR_INVALID_DATA;
    }
    for (index = 0; index < sync.count; ++index) {
        state->diagnostic_step = 5u;
        state->diagnostic_value = index;
        if (!snapshot_contains_unit(&local, sync.units[index])) {
            return ERROR_INVALID_DATA;
        }
    }
    if (sync.count == local.count) {
        return ERROR_SUCCESS;
    }
    state->diagnostic_step = 6u;
    error = resolve_unit_set_functions(&sync, &add, &remove);
    if (error != ERROR_SUCCESS) {
        state->diagnostic_value = error;
        return error;
    }
    state->diagnostic_step = 61u;
    error = resolve_unit_set_functions(
        &local,
        &local_add,
        &local_remove
    );
    if (error != ERROR_SUCCESS) {
        state->diagnostic_value = error;
        return error;
    }
    if (local_add != add || local_remove != remove) {
        state->diagnostic_value =
            (uint64_t)(uintptr_t)local_add ^
            (uint64_t)(uintptr_t)local_remove;
        return ERROR_INVALID_DATA;
    }
    state->diagnostic_step = 7u;
    error = resolve_known_image_function(
        WAR3_ADD_TO_SUBGROUPS_RVA,
        add_to_subgroups_signature,
        sizeof(add_to_subgroups_signature),
        &subgroup_function_address
    );
    if (error != ERROR_SUCCESS) {
        state->diagnostic_value = error;
        return error;
    }
    add_to_subgroups = (SelectionSubgroupFunction)subgroup_function_address;
    state->diagnostic_step = 8u;
    error = resolve_known_image_function(
        WAR3_REMOVE_FROM_SUBGROUPS_RVA,
        remove_from_subgroups_signature,
        sizeof(remove_from_subgroups_signature),
        &subgroup_function_address
    );
    if (error != ERROR_SUCCESS) {
        state->diagnostic_value = error;
        return error;
    }
    remove_from_subgroups =
        (SelectionSubgroupFunction)subgroup_function_address;
    state->selection = (void *)manager;
    state->sync_set = sync_set;
    state->remove = remove;
    state->remove_from_subgroups = remove_from_subgroups;
    state->original_count = sync.count;
    for (index = 0; index < local.count; ++index) {
        uint32_t before = UINT32_MAX;
        uint32_t after = UINT32_MAX;
        uintptr_t unit = local.units[index];
        DWORD call_error = ERROR_SUCCESS;
        if (snapshot_contains_unit(&sync, unit)) {
            continue;
        }
        if (state->added_count >= WAR3_TRANSIENT_SYNC_TEST_ADDITIONS) {
            break;
        }
        if (state->added_count >= ARRAY_COUNT(state->added_units)) {
            return ERROR_INSUFFICIENT_BUFFER;
        }
        state->diagnostic_step = 9u;
        state->diagnostic_value = unit;
        __try {
            if (sync_set->enumerating) {
                return ERROR_INVALID_DATA;
            }
            before = sync_set->count;
            add(sync_set, unit, 0u, 1u);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            call_error = GetExceptionCode();
        }
        __try {
            after = sync_set->count;
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            if (call_error == ERROR_SUCCESS) {
                call_error = GetExceptionCode();
            }
        }
        state->diagnostic_step = 10u;
        state->diagnostic_value =
            ((uint64_t)before << 32u) | (uint64_t)after;
        if (before != UINT32_MAX && after == before + 1u) {
            state->added_units[state->added_count] = unit;
            state->subgroup_added[state->added_count] = 0u;
            ++state->added_count;
        } else {
            return call_error != ERROR_SUCCESS
                ? call_error
                : ERROR_INVALID_DATA;
        }
        if (call_error != ERROR_SUCCESS) {
            state->diagnostic_step = 11u;
            state->diagnostic_value = call_error;
            return call_error;
        }
        state->diagnostic_step = 12u;
        state->diagnostic_value = unit;
        __try {
            add_to_subgroups((void *)manager, unit);
            state->subgroup_added[state->added_count - 1u] = 1u;
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            state->diagnostic_value = GetExceptionCode();
            return GetExceptionCode();
        }
    }
    state->diagnostic_step = 13u;
    state->diagnostic_value =
        ((uint64_t)state->original_count << 32u) |
        (uint64_t)state->added_count;
    if (sync_set->count != state->original_count + state->added_count) {
        return ERROR_INVALID_DATA;
    }
    return ERROR_SUCCESS;
}

static DWORD read_local_selection_count(uint32_t *count) {
    uintptr_t manager = g_selection_manager;
    UnitSetView *local_set;
    if (!count || !manager) {
        return ERROR_INVALID_ADDRESS;
    }
    local_set = (UnitSetView *)(manager + WAR3_LOCAL_UNIT_SET_OFFSET);
    __try {
        if (local_set->enumerating ||
            local_set->count > 24u) {
            return ERROR_INVALID_DATA;
        }
        *count = local_set->count;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return GetExceptionCode();
    }
    return ERROR_SUCCESS;
}

static UnitOrderDispatchFunction resolve_unit_order_dispatch(void) {
    void *address = InterlockedCompareExchangePointer(
        &g_unit_order_dispatch_original,
        NULL,
        NULL
    );
    if (!address) {
        HMODULE module = GetModuleHandleW(NULL);
        if (module) {
            address = (BYTE *)module + WAR3_UNIT_ORDER_DISPATCH_RVA;
            InterlockedCompareExchangePointer(
                &g_unit_order_dispatch_original,
                address,
                NULL
            );
            address = InterlockedCompareExchangePointer(
                &g_unit_order_dispatch_original,
                NULL,
                NULL
            );
        }
    }
    return (UnitOrderDispatchFunction)address;
}

static void record_unit_order_observation(
    uint16_t flags,
    uintptr_t return_address,
    uint8_t r12_value,
    uint8_t r13_value,
    uint8_t dil_value
) {
    if (InterlockedCompareExchange(&g_order_observer_active, 0, 0) &&
        g_order_observer_thread_id == GetCurrentThreadId()) {
        HMODULE module = GetModuleHandleW(NULL);
        uintptr_t return_rva = module &&
            return_address >= (uintptr_t)module
            ? return_address - (uintptr_t)module
            : UINTPTR_MAX;
        uint8_t single_recipient;
        if (InterlockedCompareExchange(
                &g_order_observer_test_mode,
                0,
                0
            )) {
            g_order_observer_test_r12 = r12_value;
            g_order_observer_test_r13 = r13_value;
            g_order_observer_test_dil = dil_value;
        }
        switch (return_rva) {
            case 0x0123fa18u:
            case 0x01240394u:
            case 0x01240bc6u:
            case 0x01242019u:
                single_recipient = r12_value;
                break;
            case 0x012418d8u:
                single_recipient = r13_value;
                break;
            case 0x01242b3du:
                single_recipient = dil_value;
                break;
            default:
                single_recipient = 0u;
                InterlockedExchange(
                    &g_order_observer_invalid_return,
                    1
                );
                InterlockedCompareExchange64(
                    &g_order_observer_invalid_return_rva,
                    (LONG64)return_rva,
                    0
                );
                InterlockedExchange(
                    &g_order_observer_invalid_registers,
                    (LONG)(
                        (uint32_t)r12_value |
                        ((uint32_t)r13_value << 8u) |
                        ((uint32_t)dil_value << 16u)
                    )
                );
                break;
        }
        InterlockedIncrement(&g_order_observer_count);
        InterlockedOr(&g_order_observer_flags, (LONG)flags);
        if (single_recipient) {
            InterlockedExchange(
                &g_order_observer_single_recipient,
                1
            );
        }
    }
}

void __fastcall War3SelectionObserveUnitOrder(
    void *unit,
    void *order,
    uint16_t flags,
    uint8_t auxiliary,
    uintptr_t return_address,
    uint8_t r12_value,
    uint8_t r13_value,
    uint8_t dil_value
) {
    UnitOrderDispatchFunction original;
    record_unit_order_observation(
        flags,
        return_address,
        r12_value,
        r13_value,
        dil_value
    );
    original = resolve_unit_order_dispatch();
    if (original) {
        original(unit, order, flags, auxiliary);
    }
}

static DWORD request_order_observer_breakpoint(int enable);

static DWORD begin_order_dispatch_observation(void) {
    DWORD thread_id = GetCurrentThreadId();
    DWORD error;
    if (!InterlockedCompareExchange(
            &g_order_observer_patch_applied,
            0,
            0
        )) {
        return ERROR_INVALID_STATE;
    }
    if (InterlockedCompareExchange(
            &g_order_observer_active,
            1,
            0
        ) != 0) {
        return ERROR_BUSY;
    }
    InterlockedExchange(&g_order_observer_count, 0);
    InterlockedExchange(&g_order_observer_flags, 0);
    InterlockedExchange(&g_order_observer_single_recipient, 0);
    InterlockedExchange(&g_order_observer_invalid_return, 0);
    InterlockedExchange64(&g_order_observer_invalid_return_rva, 0);
    InterlockedExchange(&g_order_observer_invalid_registers, 0);
    g_order_observer_thread_id = thread_id;
    FlushProcessWriteBuffers();
    error = g_order_dispatch_breakpoint && g_exception_handler
        ? request_order_observer_breakpoint(1)
        : ERROR_SUCCESS;
    if (error != ERROR_SUCCESS) {
        g_order_observer_thread_id = 0u;
        InterlockedExchange(&g_order_observer_active, 0);
        return error;
    }
    return ERROR_SUCCESS;
}

static DWORD end_order_dispatch_observation(
    OrderDispatchObservation *observation
) {
    DWORD thread_id = GetCurrentThreadId();
    DWORD breakpoint_error;
    if (!observation ||
        !InterlockedCompareExchange(&g_order_observer_active, 0, 0) ||
        g_order_observer_thread_id != thread_id) {
        return ERROR_INVALID_STATE;
    }
    breakpoint_error = InterlockedCompareExchange(
        &g_order_observer_breakpoint_active,
        0,
        0
    )
        ? request_order_observer_breakpoint(0)
        : ERROR_SUCCESS;
    InterlockedExchange(&g_order_observer_active, 0);
    FlushProcessWriteBuffers();
    observation->count = (uint32_t)InterlockedCompareExchange(
        &g_order_observer_count,
        0,
        0
    );
    observation->flags = (uint16_t)InterlockedCompareExchange(
        &g_order_observer_flags,
        0,
        0
    );
    observation->single_recipient = (uint8_t)InterlockedCompareExchange(
        &g_order_observer_single_recipient,
        0,
        0
    );
    observation->invalid_return = (uint8_t)InterlockedCompareExchange(
        &g_order_observer_invalid_return,
        0,
        0
    );
    observation->invalid_return_rva = (uintptr_t)InterlockedCompareExchange64(
        &g_order_observer_invalid_return_rva,
        0,
        0
    );
    observation->invalid_registers = (uint32_t)InterlockedCompareExchange(
        &g_order_observer_invalid_registers,
        0,
        0
    );
    g_order_observer_thread_id = 0;
    if (breakpoint_error != ERROR_SUCCESS) {
        return breakpoint_error;
    }
    return ERROR_SUCCESS;
}

static uint8_t route_extended_order(
    uint32_t index,
    void *self,
    void *data,
    OrderHandlerFunction original
) {
    DWORD thread_id = GetCurrentThreadId();
    LONG owner;
    DWORD error;
    DWORD cleanup_error = ERROR_SUCCESS;
    DWORD observation_error = ERROR_SUCCESS;
    OrderReplayState replay;
    OrderDispatchObservation primary_observation;
    OrderDispatchObservation replay_observation;
    int observation_active = 0;
    uint8_t result = 0u;
    uint8_t replay_result = 0u;

    ZeroMemory(&primary_observation, sizeof(primary_observation));
    ZeroMemory(&replay_observation, sizeof(replay_observation));
    owner = InterlockedCompareExchange(
        &g_order_replay_thread_id,
        (LONG)thread_id,
        0
    );
    if (owner != 0) {
        return 0u;
    }
    error = prepare_order_replay(&replay);
    if (error != ERROR_SUCCESS) {
        record_order_diagnostic(
            index,
            error,
            ORDER_DIAGNOSTIC_REPLAY_PREPARE,
            replay.diagnostic_step,
            replay.diagnostic_value,
            0u,
            0u
        );
        InterlockedCompareExchange(
            &g_order_replay_thread_id,
            0,
            (LONG)thread_id
        );
        return 0u;
    }
    record_order_diagnostic(
        index,
        ERROR_SUCCESS,
        ORDER_DIAGNOSTIC_ORIGINAL,
        replay.original_sync.count,
        replay.original_local.count,
        replay.extra_count,
        0u
    );
    __try {
        error = install_extra_sync_batch(&replay);
        if (error != ERROR_SUCCESS) {
            record_order_diagnostic(
                index,
                error,
                ORDER_DIAGNOSTIC_REPLAY_INSTALL,
                replay.diagnostic_step,
                replay.diagnostic_value,
                replay.extra_count,
                0u
            );
            __leave;
        }
        error = restore_original_sync(&replay);
        if (error != ERROR_SUCCESS) {
            record_order_diagnostic(
                index,
                error,
                ORDER_DIAGNOSTIC_REPLAY_RESTORE,
                replay.diagnostic_step,
                replay.diagnostic_value,
                replay.extra_count,
                0u
            );
            __leave;
        }
        error = validate_order_replay_unchanged(&replay);
        if (error != ERROR_SUCCESS) {
            __leave;
        }

        error = begin_order_dispatch_observation();
        if (error != ERROR_SUCCESS) {
            __leave;
        }
        observation_active = 1;
        result = original(self, data);
        observation_error = end_order_dispatch_observation(
            &primary_observation
        );
        observation_active = 0;
        if (observation_error != ERROR_SUCCESS) {
            error = observation_error;
            __leave;
        }
        if (!result) {
            error = ERROR_CANCELLED;
            __leave;
        }
        error = validate_order_replay_unchanged(&replay);
        if (error != ERROR_SUCCESS) {
            record_order_diagnostic(
                index,
                error,
                ORDER_DIAGNOSTIC_REPLAY_PREPARE,
                replay.original_sync.count,
                replay.original_mirror.count,
                replay.original_local.count,
                1u
            );
            __leave;
        }
        if (primary_observation.single_recipient &&
            primary_observation.count == 1u) {
            replay_result = 1u;
            error = ERROR_SUCCESS;
            record_order_diagnostic(
                index,
                ERROR_SUCCESS,
                ORDER_DIAGNOSTIC_REPLAY_ORIGINAL,
                primary_observation.count,
                primary_observation.flags,
                primary_observation.single_recipient,
                0u
            );
            __leave;
        }
        error = install_extra_sync_batch(&replay);
        if (error != ERROR_SUCCESS) {
            record_order_diagnostic(
                index,
                error,
                ORDER_DIAGNOSTIC_REPLAY_INSTALL,
                replay.diagnostic_step,
                replay.diagnostic_value,
                replay.extra_count,
                0u
            );
            __leave;
        }
        error = begin_order_dispatch_observation();
        if (error != ERROR_SUCCESS) {
            __leave;
        }
        observation_active = 1;
        replay_result = original(self, data);
        observation_error = end_order_dispatch_observation(
            &replay_observation
        );
        observation_active = 0;
        if (observation_error != ERROR_SUCCESS) {
            error = observation_error;
            __leave;
        }
        if (!replay_result) {
            error = ERROR_CANCELLED;
        }
        if (primary_observation.invalid_return ||
            replay_observation.invalid_return) {
            const OrderDispatchObservation *invalid_observation =
                primary_observation.invalid_return
                ? &primary_observation
                : &replay_observation;
            record_order_diagnostic(
                index,
                ERROR_REVISION_MISMATCH,
                ORDER_DIAGNOSTIC_OBSERVER_RETURN,
                invalid_observation->invalid_return_rva,
                invalid_observation->invalid_registers,
                ((uint64_t)primary_observation.count << 32u) |
                    replay_observation.count,
                ((uint64_t)result << 32u) | replay_result
            );
        } else {
            record_order_diagnostic(
                index,
                replay_result ? ERROR_SUCCESS : ERROR_CANCELLED,
                ORDER_DIAGNOSTIC_REPLAY_ORIGINAL,
                ((uint64_t)primary_observation.count << 32u) |
                    replay_observation.count,
                ((uint64_t)primary_observation.flags << 32u) |
                    replay_observation.flags,
                ((uint64_t)primary_observation.single_recipient << 32u) |
                    replay_observation.single_recipient,
                ((uint64_t)result << 32u) | replay_result
            );
        }
    } __finally {
        if (observation_active) {
            OrderDispatchObservation discarded;
            ZeroMemory(&discarded, sizeof(discarded));
            end_order_dispatch_observation(&discarded);
        }
        cleanup_error = restore_original_sync(&replay);
        if (cleanup_error != ERROR_SUCCESS) {
            record_order_diagnostic(
                index,
                cleanup_error,
                ORDER_DIAGNOSTIC_REPLAY_RESTORE,
                replay.diagnostic_step,
                replay.diagnostic_value,
                replay.extra_count,
                0u
            );
        }
        InterlockedCompareExchange(
            &g_order_replay_thread_id,
            0,
            (LONG)thread_id
        );
    }
    return cleanup_error == ERROR_SUCCESS &&
        error == ERROR_SUCCESS &&
        result &&
        replay_result
        ? 1u
        : 0u;
}

static uint8_t call_original_order(uint32_t index, void *self, void *data) {
    OrderHandlerFunction original;
    DWORD error;
    DWORD thread_id;
    uint32_t local_count = 0u;
    uint8_t result = 0u;
    if (index >= WAR3_ORDER_HANDLER_COUNT ||
        InterlockedCompareExchange(&g_order_hook_state, 0, 0) != 1) {
        return 0u;
    }
    InterlockedIncrement(&g_order_wrapper_count);
    if (InterlockedCompareExchange(&g_order_hook_state, 0, 0) != 1) {
        InterlockedDecrement(&g_order_wrapper_count);
        return 0u;
    }
    original = g_original_order_functions[index];
    InterlockedIncrement64(&g_diagnostic_hits[0]);
    record_order_diagnostic(
        index, ERROR_SUCCESS, ORDER_DIAGNOSTIC_ENTER,
        g_selection_manager, 0u, 0u, 0u
    );
    if (!original) {
        record_order_diagnostic(
            index, ERROR_INVALID_FUNCTION, ORDER_DIAGNOSTIC_ENTER,
            g_selection_manager, 0u, 0u, 0u
        );
        InterlockedDecrement(&g_order_wrapper_count);
        return 0u;
    }
    thread_id = GetCurrentThreadId();
    if ((DWORD)InterlockedCompareExchange(
            &g_order_replay_thread_id,
            0,
            0
        ) == thread_id) {
        __try {
            result = original(self, data);
        } __finally {
            InterlockedDecrement(&g_order_wrapper_count);
        }
        return result;
    }
    error = read_local_selection_count(&local_count);
    if (error != ERROR_SUCCESS) {
        record_order_diagnostic(
            index,
            error,
            ORDER_DIAGNOSTIC_REPLAY_PREPARE,
            g_selection_manager,
            0u,
            0u,
            0u
        );
        __try {
            result = original(self, data);
        } __finally {
            InterlockedDecrement(&g_order_wrapper_count);
        }
        return result;
    }
    if (local_count > WAR3_NATIVE_SELECTION_LIMIT) {
        if (InterlockedCompareExchange(
                &g_order_route_poisoned,
                0,
                0
            )) {
            record_order_diagnostic(
                index,
                ERROR_INVALID_STATE,
                ORDER_DIAGNOSTIC_REPLAY_RESTORE,
                g_selection_manager,
                local_count,
                0u,
                0u
            );
            InterlockedDecrement(&g_order_wrapper_count);
            return 0u;
        }
        if (!InterlockedCompareExchange(
                &g_order_route_lock_initialized,
                0,
                0
            ) ||
            !InterlockedCompareExchange(
                &g_order_observer_patch_applied,
                0,
                0
            )) {
            record_order_diagnostic(
                index,
                ERROR_NOT_READY,
                ORDER_DIAGNOSTIC_REPLAY_PREPARE,
                g_selection_manager,
                local_count,
                g_order_route_lock_initialized,
                g_order_observer_patch_applied
            );
            InterlockedDecrement(&g_order_wrapper_count);
            return 0u;
        }
        EnterCriticalSection(&g_order_route_lock);
        __try {
            result = route_extended_order(index, self, data, original);
        } __finally {
            LeaveCriticalSection(&g_order_route_lock);
            InterlockedDecrement(&g_order_wrapper_count);
        }
        return result;
    }
    record_order_diagnostic(
        index, ERROR_SUCCESS, ORDER_DIAGNOSTIC_ORIGINAL,
        g_selection_manager, local_count, 0u, 0u
    );
    __try {
        result = original(self, data);
    } __finally {
        InterlockedDecrement(&g_order_wrapper_count);
    }
    return result;
}

#define DEFINE_ORDER_WRAPPER(index) \
    static uint8_t __fastcall order_wrapper_##index(void *self, void *data) { \
        return call_original_order(index, self, data); \
    }

DEFINE_ORDER_WRAPPER(0)
DEFINE_ORDER_WRAPPER(1)
DEFINE_ORDER_WRAPPER(2)
DEFINE_ORDER_WRAPPER(3)
DEFINE_ORDER_WRAPPER(4)
DEFINE_ORDER_WRAPPER(5)

static const OrderHandlerFunction ORDER_WRAPPERS[WAR3_ORDER_HANDLER_COUNT] = {
    order_wrapper_0,
    order_wrapper_1,
    order_wrapper_2,
    order_wrapper_3,
    order_wrapper_4,
    order_wrapper_5,
};

#define BREAKPOINT_MODE_NORMAL 0
#define BREAKPOINT_MODE_DISPATCH 1
#define BREAKPOINT_MODE_POST_SELECTION 2
#define BREAKPOINT_MODE_DIAGNOSTIC 3
#define BREAKPOINT_MODE_ORDER 4
#define EFLAGS_RESUME 0x10000u
#define EFLAGS_TRAP 0x00000100u
#define EFLAGS_COMPARE_MASK 0x000008d5u

static int bytes_equal(const BYTE *address, uint32_t value, size_t size) {
    return memcmp(address, &value, size) == 0;
}

static int signature_matches(const BYTE *candidate, const uint16_t *signature, size_t size) {
    size_t index;
    for (index = 0; index < size; ++index) {
        if (signature[index] != WAR3_SELECTION_ANY && candidate[index] != (BYTE)signature[index]) {
            return 0;
        }
    }
    return 1;
}

static DWORD find_unique(
    BYTE *start,
    size_t size,
    const PatchSpec *spec,
    BYTE **match
) {
    BYTE *found = NULL;
    size_t offset;
    if (spec->signature_size > size) {
        return ERROR_NOT_FOUND;
    }
    for (offset = 0; offset <= size - spec->signature_size; ++offset) {
        if (!signature_matches(start + offset, spec->signature, spec->signature_size)) {
            continue;
        }
        if (found != NULL) {
            return ERROR_DUP_NAME;
        }
        found = start + offset;
    }
    if (found == NULL) {
        return ERROR_NOT_FOUND;
    }
    *match = found;
    return ERROR_SUCCESS;
}

static const BYTE ORDER_ENTRY_PREFIX[] = {
    0x48, 0x89, 0x5c, 0x24, 0x10,
    0x48, 0x89, 0x74, 0x24, 0x18,
    0x48, 0x89, 0x7c, 0x24, 0x20,
    0x55, 0x41, 0x54, 0x41, 0x55, 0x41, 0x56, 0x41, 0x57
};

static const uint16_t SIG_ORDER_DISPATCH[] = {
    0x48, 0x8b, 0x03, 0x49, 0x8b, 0xd2, 0x48, 0x8b, 0xcb, 0xff, 0x50, 0x20,
    0x45, 0x0f, 0xb6, 0xe4, 0x84, 0xc0, 0xb8, 0x01, 0x00, 0x00, 0x00,
    0x44, 0x0f, 0x45, 0xe0, 0x48, 0x8b, 0x84, 0x24
};

static const BYTE ORDER_DISPATCH_PROLOGUE[] = {
    0x4c, 0x89, 0x44, 0x24, 0x18,
    0x89, 0x54, 0x24, 0x10,
    0x53, 0x55, 0x56, 0x57,
    0x41, 0x54, 0x41, 0x55, 0x41, 0x56, 0x41, 0x57,
    0x48, 0x83, 0xec, 0x48
};

static const BYTE ORDER_DISPATCH_EPILOGUE[] = {
    0x48, 0x83, 0xc4, 0x48,
    0x41, 0x5f, 0x41, 0x5e, 0x41, 0x5d, 0x41, 0x5c,
    0x5f, 0x5e, 0x5d, 0x5b, 0xc3
};

#define WAR3_ORDER_DISPATCH_ENTRY_BACK_OFFSET 0x148u
#define WAR3_ORDER_DISPATCH_EPILOGUE_FORWARD_OFFSET 0x0d1u
#define WAR3_ORDER_DISPATCH_RETURN_STACK_OFFSET 0x088u

static int bytes_match_u32(
    const BYTE *address,
    const BYTE *prefix,
    size_t prefix_size,
    uint32_t value
) {
    return memcmp(address, prefix, prefix_size) == 0 &&
        memcmp(address + prefix_size, &value, sizeof(value)) == 0;
}

static int order_entry_matches(const BYTE *candidate, const OrderHandlerSpec *spec) {
    static const BYTE lea_rbp[] = {0x48, 0x8d, 0xac, 0x24};
    static const BYTE sub_rsp[] = {0x48, 0x81, 0xec};
    static const BYTE cookie_source[] = {0x48, 0x8b, 0x05};
    static const BYTE cookie_xor[] = {0x48, 0x33, 0xc4};
    static const BYTE cookie_store[] = {0x48, 0x89, 0x85};
    return memcmp(candidate, ORDER_ENTRY_PREFIX, sizeof(ORDER_ENTRY_PREFIX)) == 0 &&
        bytes_match_u32(candidate + 0x18u, lea_rbp, sizeof(lea_rbp), spec->rbp_displacement) &&
        bytes_match_u32(candidate + 0x20u, sub_rsp, sizeof(sub_rsp), spec->old_frame_size) &&
        memcmp(candidate + 0x27u, cookie_source, sizeof(cookie_source)) == 0 &&
        memcmp(candidate + 0x2eu, cookie_xor, sizeof(cookie_xor)) == 0 &&
        bytes_match_u32(candidate + 0x31u, cookie_store, sizeof(cookie_store), spec->cookie_offset);
}

static DWORD validate_order_handler(
    BYTE *entry,
    BYTE *text_end,
    const OrderHandlerSpec *spec,
    OrderHandlerRuntime *runtime
) {
    static const BYTE sub_rsp[] = {0x48, 0x81, 0xec};
    static const BYTE cookie_store[] = {0x48, 0x89, 0x85};
    static const BYTE array_size[] = {0x41, 0xb8};
    static const BYTE cookie_load[] = {0x48, 0x8b, 0x8d};
    static const BYTE epilogue[] = {0x4c, 0x8d, 0x9c, 0x24};
    static const BYTE instant_store[] = {0x4c, 0x89, 0xa5};
    static const BYTE instant_load[] = {0x48, 0x8b, 0x85};
    BYTE *last = entry + spec->epilogue_offset + 0x21u;
    if (last > text_end ||
        !bytes_match_u32(entry + 0x20u, sub_rsp, sizeof(sub_rsp), spec->old_frame_size) ||
        !bytes_match_u32(entry + 0x31u, cookie_store, sizeof(cookie_store), spec->cookie_offset) ||
        !bytes_match_u32(entry + spec->memset_offset, array_size, sizeof(array_size), spec->old_array_size) ||
        !bytes_match_u32(entry + spec->cookie_load_offset, cookie_load, sizeof(cookie_load), spec->cookie_offset) ||
        !bytes_match_u32(entry + spec->epilogue_offset, epilogue, sizeof(epilogue), spec->old_frame_size) ||
        entry[spec->epilogue_offset + 0x20u] != 0xc3u) {
        return ERROR_INVALID_DATA;
    }
    if (spec->instant_offset &&
        (!spec->instant_store_offset || !spec->instant_load_offset ||
         !bytes_match_u32(entry + spec->instant_store_offset,
                          instant_store, sizeof(instant_store), spec->instant_offset) ||
         !bytes_match_u32(entry + spec->instant_load_offset,
                          instant_load, sizeof(instant_load), spec->instant_offset))) {
        return ERROR_INVALID_DATA;
    }
    runtime->entry = entry;
    runtime->stack_allocation = entry + 0x20u;
    runtime->cookie_store = entry + 0x31u;
    runtime->array_size = entry + spec->memset_offset;
    runtime->cookie_load = entry + spec->cookie_load_offset;
    runtime->epilogue = entry + spec->epilogue_offset;
    runtime->return_instruction = runtime->epilogue + 0x20u;
    runtime->instant_store = spec->instant_store_offset
        ? entry + spec->instant_store_offset : NULL;
    runtime->instant_load = spec->instant_load_offset
        ? entry + spec->instant_load_offset : NULL;
    return ERROR_SUCCESS;
}

static DWORD resolve_order_handlers(BYTE *text, size_t text_size) {
    PatchSpec dispatch_spec = {
        "order dispatch",
        SIG_ORDER_DISPATCH,
        ARRAY_COUNT(SIG_ORDER_DISPATCH),
        9u,
        0u,
        0u,
        0u
    };
    BYTE *text_end = text + text_size;
    BYTE *dispatch_match = NULL;
    uint32_t index;
    DWORD error;
    ZeroMemory(g_order_handlers, sizeof(g_order_handlers));
    g_order_dispatch_breakpoint = NULL;
    g_order_dispatch_return_stack_offset = 0u;
    g_order_handlers_valid = 0;
    InterlockedExchange(&g_order_resolution_stage, 100);
    for (index = 0; index < WAR3_ORDER_HANDLER_COUNT; ++index) {
        const OrderHandlerSpec *spec = &ORDER_SPECS[index];
        BYTE *found = NULL;
        size_t offset;
        InterlockedExchange(&g_order_resolution_stage, (LONG)(1000u + index * 10u));
        for (offset = 0; offset + 0x38u <= text_size; ++offset) {
            BYTE *candidate = text + offset;
            if (!order_entry_matches(candidate, spec)) {
                continue;
            }
            if (found) {
                return ERROR_DUP_NAME;
            }
            found = candidate;
        }
        if (!found) {
            return ERROR_NOT_FOUND;
        }
        InterlockedExchange(&g_order_resolution_stage, (LONG)(1001u + index * 10u));
        error = validate_order_handler(found, text_end, spec, &g_order_handlers[index]);
        if (error != ERROR_SUCCESS) {
            return error;
        }
        InterlockedExchange(&g_order_resolution_stage, (LONG)(1002u + index * 10u));
    }
    InterlockedExchange(&g_order_resolution_stage, 2000);
    error = find_unique(text, text_size, &dispatch_spec, &dispatch_match);
    if (error != ERROR_SUCCESS) {
        return error;
    }
    if (dispatch_match < text + WAR3_ORDER_DISPATCH_ENTRY_BACK_OFFSET ||
        dispatch_match + WAR3_ORDER_DISPATCH_EPILOGUE_FORWARD_OFFSET +
            sizeof(ORDER_DISPATCH_EPILOGUE) > text_end ||
        memcmp(
            dispatch_match - WAR3_ORDER_DISPATCH_ENTRY_BACK_OFFSET,
            ORDER_DISPATCH_PROLOGUE,
            sizeof(ORDER_DISPATCH_PROLOGUE)
        ) != 0 ||
        memcmp(
            dispatch_match + WAR3_ORDER_DISPATCH_EPILOGUE_FORWARD_OFFSET,
            ORDER_DISPATCH_EPILOGUE,
            sizeof(ORDER_DISPATCH_EPILOGUE)
        ) != 0) {
        return ERROR_REVISION_MISMATCH;
    }
    g_order_dispatch_breakpoint = dispatch_match + dispatch_spec.patch_offset;
    g_order_dispatch_return_stack_offset =
        WAR3_ORDER_DISPATCH_RETURN_STACK_OFFSET;
    g_order_handlers_valid = 1;
    InterlockedExchange(&g_order_resolution_stage, 3000);
    return ERROR_SUCCESS;
}

static int writable_private_protection(DWORD protection) {
    DWORD base = protection & 0xffu;
    return !(protection & (PAGE_GUARD | PAGE_NOACCESS)) &&
        (base == PAGE_READWRITE ||
         base == PAGE_WRITECOPY ||
         base == PAGE_EXECUTE_READWRITE ||
         base == PAGE_EXECUTE_WRITECOPY);
}

static DWORD resolve_selection_manager(void) {
    SYSTEM_INFO system;
    BYTE *module = (BYTE *)GetModuleHandleW(NULL);
    uintptr_t expected_vtable;
    uintptr_t cursor;
    uintptr_t maximum;
    uintptr_t resolved = 0;
    uint32_t best_local_count = 0;
    int best_count = 0;
    if (!module ||
        WAR3_SELECTION_VTABLE_RVA > UINTPTR_MAX - (uintptr_t)module) {
        return ERROR_BAD_EXE_FORMAT;
    }
    expected_vtable = (uintptr_t)module + WAR3_SELECTION_VTABLE_RVA;
    GetNativeSystemInfo(&system);
    cursor = (uintptr_t)system.lpMinimumApplicationAddress;
    maximum = (uintptr_t)system.lpMaximumApplicationAddress;
    while (cursor < maximum) {
        MEMORY_BASIC_INFORMATION memory;
        uintptr_t region_start;
        uintptr_t region_end;
        if (!VirtualQuery((const void *)cursor, &memory, sizeof(memory))) {
            break;
        }
        region_start = (uintptr_t)memory.BaseAddress;
        if (region_start > UINTPTR_MAX - memory.RegionSize) {
            return ERROR_ARITHMETIC_OVERFLOW;
        }
        region_end = region_start + memory.RegionSize;
        if (region_end <= cursor) {
            return ERROR_ARITHMETIC_OVERFLOW;
        }
        if (memory.State == MEM_COMMIT &&
            memory.Type == MEM_PRIVATE &&
            writable_private_protection(memory.Protect) &&
            memory.RegionSize >= WAR3_SELECTION_OBJECT_SIZE) {
            uintptr_t address = (region_start + 7u) & ~(uintptr_t)7u;
            __try {
                for (; address <= region_end - WAR3_SELECTION_OBJECT_SIZE;
                     address += sizeof(uintptr_t)) {
                    uint32_t sync_count;
                    uint32_t mirror_count;
                    uint32_t local_count;
                    uint32_t player_id;
                    if (*(const uintptr_t *)address != expected_vtable) {
                        continue;
                    }
                    sync_count = *(const uint32_t *)(address + 0x20u);
                    player_id = *(const uint32_t *)(
                        address + WAR3_SELECTION_PLAYER_OFFSET
                    );
                    mirror_count = *(const uint32_t *)(
                        address + WAR3_SELECTION_MIRROR_COUNT_OFFSET
                    );
                    local_count = *(const uint32_t *)(
                        address + WAR3_SELECTION_LOCAL_COUNT_OFFSET
                    );
                    if (player_id != 0u ||
                        sync_count > 64u ||
                        mirror_count > 64u ||
                        local_count > 64u ||
                        sync_count > local_count ||
                        mirror_count > local_count) {
                        continue;
                    }
                    if (!resolved || local_count > best_local_count) {
                        resolved = address;
                        best_local_count = local_count;
                        best_count = 1;
                    } else if (local_count == best_local_count &&
                               address != resolved) {
                        ++best_count;
                    }
                }
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                return ERROR_PARTIAL_COPY;
            }
        }
        cursor = region_end;
    }
    if (!resolved) {
        return ERROR_NOT_FOUND;
    }
    if (best_count != 1) {
        return ERROR_DUP_NAME;
    }
    g_selection_manager = resolved;
    return ERROR_SUCCESS;
}

static DWORD resolve_order_pointer_slots(void) {
    SYSTEM_INFO system;
    MEMORY_BASIC_INFORMATION local_memory;
    uintptr_t resolved[WAR3_ORDER_HANDLER_COUNT];
    uint32_t match_counts[WAR3_ORDER_HANDLER_COUNT];
    uintptr_t cursor;
    uintptr_t excluded_allocation;
    uintptr_t maximum;
    if (!VirtualQuery(
            (const void *)resolved,
            &local_memory,
            sizeof(local_memory)
        )) {
        return GetLastError();
    }
    excluded_allocation = (uintptr_t)local_memory.AllocationBase;
    ZeroMemory(g_order_pointer_slots, sizeof(g_order_pointer_slots));
    ZeroMemory(resolved, sizeof(resolved));
    ZeroMemory(match_counts, sizeof(match_counts));
    GetNativeSystemInfo(&system);
    cursor = (uintptr_t)system.lpMinimumApplicationAddress;
    maximum = (uintptr_t)system.lpMaximumApplicationAddress;
    while (cursor < maximum) {
        MEMORY_BASIC_INFORMATION memory;
        uintptr_t region_start;
        uintptr_t region_end;
        if (!VirtualQuery((const void *)cursor, &memory, sizeof(memory))) {
            break;
        }
        region_start = (uintptr_t)memory.BaseAddress;
        region_end = region_start + memory.RegionSize;
        if (region_end <= cursor) {
            return ERROR_ARITHMETIC_OVERFLOW;
        }
        if (memory.State == MEM_COMMIT &&
            memory.Type == MEM_PRIVATE &&
            (uintptr_t)memory.AllocationBase != excluded_allocation &&
            writable_private_protection(memory.Protect)) {
            uintptr_t address = (region_start + 7u) & ~(uintptr_t)7u;
            __try {
                for (; address + sizeof(uintptr_t) <= region_end;
                     address += sizeof(uintptr_t)) {
                    uintptr_t value = *(const uintptr_t *)address;
                    uint32_t index;
                    for (index = 0;
                         index < WAR3_ORDER_HANDLER_COUNT;
                         ++index) {
                        if (value !=
                            (uintptr_t)g_order_handlers[index].entry) {
                            continue;
                        }
                        if (++match_counts[index] != 1u) {
                            return ERROR_DUP_NAME;
                        }
                        resolved[index] = address;
                        break;
                    }
                }
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                return ERROR_PARTIAL_COPY;
            }
        }
        cursor = region_end;
    }
    {
        uint32_t index;
        for (index = 0; index < WAR3_ORDER_HANDLER_COUNT; ++index) {
            if (match_counts[index] != 1u) {
                return ERROR_NOT_FOUND;
            }
        }
    }
    memcpy(
        g_order_pointer_slots,
        resolved,
        sizeof(g_order_pointer_slots)
    );
    return ERROR_SUCCESS;
}

static DWORD install_order_pointer_hooks(void) {
    uint32_t index;
    DWORD error = resolve_order_pointer_slots();
    if (error != ERROR_SUCCESS) {
        return error;
    }
    for (index = 0; index < WAR3_ORDER_HANDLER_COUNT; ++index) {
        g_original_order_functions[index] =
            (OrderHandlerFunction)g_order_handlers[index].entry;
        void *previous = InterlockedExchangePointer(
            (void *volatile *)g_order_pointer_slots[index],
            (void *)ORDER_WRAPPERS[index]
        );
        if (previous != (void *)g_order_handlers[index].entry) {
            uint32_t rollback = index;
            InterlockedExchangePointer(
                (void *volatile *)g_order_pointer_slots[index],
                previous
            );
            while (rollback > 0u) {
                --rollback;
                InterlockedExchangePointer(
                    (void *volatile *)g_order_pointer_slots[rollback],
                    (void *)g_order_handlers[rollback].entry
                );
            }
            ZeroMemory(g_order_pointer_slots, sizeof(g_order_pointer_slots));
            ZeroMemory(
                g_original_order_functions,
                sizeof(g_original_order_functions)
            );
            return ERROR_INVALID_DATA;
        }
    }
    FlushProcessWriteBuffers();
    InterlockedExchange(&g_order_hook_state, 1);
    return ERROR_SUCCESS;
}

static DWORD initialize_order_route_lock(void) {
    if (InterlockedCompareExchange(
            &g_order_route_lock_initialized,
            0,
            0
        )) {
        InterlockedExchange(&g_order_route_poisoned, 0);
        return ERROR_SUCCESS;
    }
    if (!InitializeCriticalSectionAndSpinCount(
            &g_order_route_lock,
            4000u
        )) {
        DWORD error = GetLastError();
        return error ? error : ERROR_NOT_ENOUGH_MEMORY;
    }
    InterlockedExchange(&g_order_route_poisoned, 0);
    InterlockedExchange(&g_order_route_lock_initialized, 1);
    return ERROR_SUCCESS;
}

static void delete_order_route_lock(void) {
    if (InterlockedExchange(
            &g_order_route_lock_initialized,
            0
        )) {
        DeleteCriticalSection(&g_order_route_lock);
    }
    InterlockedExchange(&g_order_route_poisoned, 0);
    InterlockedExchange(&g_order_replay_thread_id, 0);
}

static void remove_order_pointer_hooks(void) {
    uint32_t index;
    InterlockedExchange(&g_order_hook_state, 2);
    for (index = 0; index < WAR3_ORDER_HANDLER_COUNT; ++index) {
        if (!g_order_pointer_slots[index]) {
            continue;
        }
        InterlockedCompareExchangePointer(
            (void *volatile *)g_order_pointer_slots[index],
            (void *)g_order_handlers[index].entry,
            (void *)ORDER_WRAPPERS[index]
        );
    }
    FlushProcessWriteBuffers();
    while (InterlockedCompareExchange(&g_order_wrapper_count, 0, 0) != 0) {
        Sleep(0);
    }
    ZeroMemory(g_order_pointer_slots, sizeof(g_order_pointer_slots));
    ZeroMemory(g_original_order_functions, sizeof(g_original_order_functions));
    InterlockedExchange(&g_order_hook_state, 0);
}

#if WAR3_EARLY_IMAGE_PATCH_ENABLED
static DWORD find_text_section_in_image(
    BYTE *module,
    size_t image_size,
    BYTE **start,
    size_t *size
) {
    IMAGE_DOS_HEADER *dos;
    IMAGE_NT_HEADERS64 *nt;
    IMAGE_SECTION_HEADER *section;
    size_t nt_offset;
    size_t section_offset;
    size_t section_table_size;
    WORD index;
    if (!module || !start || !size ||
        image_size < sizeof(IMAGE_DOS_HEADER)) {
        return ERROR_INVALID_PARAMETER;
    }
    dos = (IMAGE_DOS_HEADER *)module;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew <= 0) {
        return ERROR_BAD_EXE_FORMAT;
    }
    nt_offset = (size_t)dos->e_lfanew;
    if (nt_offset > image_size ||
        image_size - nt_offset < sizeof(IMAGE_NT_HEADERS64)) {
        return ERROR_BAD_EXE_FORMAT;
    }
    nt = (IMAGE_NT_HEADERS64 *)(module + nt_offset);
    if (nt->Signature != IMAGE_NT_SIGNATURE ||
        nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR64_MAGIC ||
        nt->OptionalHeader.SizeOfImage != image_size ||
        nt->FileHeader.NumberOfSections == 0u ||
        nt->FileHeader.NumberOfSections > 96u) {
        return ERROR_BAD_EXE_FORMAT;
    }
    section = IMAGE_FIRST_SECTION(nt);
    section_offset = (size_t)((BYTE *)section - module);
    section_table_size =
        (size_t)nt->FileHeader.NumberOfSections * sizeof(*section);
    if (section_offset > image_size ||
        section_table_size > image_size - section_offset) {
        return ERROR_BAD_EXE_FORMAT;
    }
    for (index = 0; index < nt->FileHeader.NumberOfSections; ++index) {
        size_t virtual_address;
        size_t virtual_size;
        if (memcmp(section[index].Name, ".text", 5u) != 0) {
            continue;
        }
        virtual_address = section[index].VirtualAddress;
        virtual_size = section[index].Misc.VirtualSize;
        if (virtual_size == 0u || virtual_address > image_size ||
            virtual_size > image_size - virtual_address) {
            return ERROR_BAD_LENGTH;
        }
        *start = module + virtual_address;
        *size = virtual_size;
        return ERROR_SUCCESS;
    }
    return ERROR_NOT_FOUND;
}

static const uint32_t ORDER_DISPATCH_CALL_RVAS[
    WAR3_ORDER_HANDLER_COUNT
] = {
    0x0123fa13u,
    0x0124038fu,
    0x01240bc1u,
    0x012418d3u,
    0x01242014u,
    0x01242b38u,
};

static void build_relative_call(
    BYTE bytes[5],
    uint32_t call_rva,
    uint32_t target_rva
) {
    int32_t displacement = (int32_t)(
        (int64_t)target_rva - ((int64_t)call_rva + 5)
    );
    bytes[0] = 0xe8u;
    memcpy(bytes + 1u, &displacement, sizeof(displacement));
}

static void build_order_observer_cave(
    BYTE bytes[WAR3_ORDER_OBSERVER_CAVE_SIZE]
) {
    void (*thunk)(void) = OrderDispatchObserverThunk;
    uintptr_t address = 0u;
    ZeroMemory(bytes, WAR3_ORDER_OBSERVER_CAVE_SIZE);
    memcpy(&address, &thunk, sizeof(address));
    bytes[0] = 0x48u;
    bytes[1] = 0xb8u;
    memcpy(bytes + 2u, &address, sizeof(address));
    bytes[10] = 0xffu;
    bytes[11] = 0xe0u;
    memset(bytes + 12u, 0x90, WAR3_ORDER_OBSERVER_CAVE_SIZE - 12u);
}

static DWORD apply_order_observer_early_patch(
    BYTE *image,
    SIZE_T image_size
) {
    BYTE enabled_cave[WAR3_ORDER_OBSERVER_CAVE_SIZE];
    BYTE original_call[5];
    BYTE enabled_call[5];
    uint32_t index;
    int all_original = 1;
    int all_enabled = 1;
    DWORD error = ERROR_SUCCESS;
    if (!image ||
        WAR3_ORDER_OBSERVER_CAVE_RVA > image_size ||
        WAR3_ORDER_OBSERVER_CAVE_SIZE >
            image_size - WAR3_ORDER_OBSERVER_CAVE_RVA) {
        return ERROR_BAD_LENGTH;
    }
    build_order_observer_cave(enabled_cave);
    if (memcmp(
            image + WAR3_ORDER_OBSERVER_CAVE_RVA,
            enabled_cave,
            sizeof(enabled_cave)
        ) != 0) {
        all_enabled = 0;
    }
    for (index = 0; index < sizeof(enabled_cave); ++index) {
        if (image[WAR3_ORDER_OBSERVER_CAVE_RVA + index] != 0xccu) {
            all_original = 0;
            break;
        }
    }
    for (index = 0; index < WAR3_ORDER_HANDLER_COUNT; ++index) {
        uint32_t call_rva = ORDER_DISPATCH_CALL_RVAS[index];
        if (call_rva > image_size ||
            sizeof(original_call) > image_size - call_rva) {
            return ERROR_BAD_LENGTH;
        }
        build_relative_call(
            original_call,
            call_rva,
            WAR3_UNIT_ORDER_DISPATCH_RVA
        );
        build_relative_call(
            enabled_call,
            call_rva,
            WAR3_ORDER_OBSERVER_CAVE_RVA
        );
        if (memcmp(
                image + call_rva,
                original_call,
                sizeof(original_call)
            ) != 0) {
            all_original = 0;
        }
        if (memcmp(
                image + call_rva,
                enabled_call,
                sizeof(enabled_call)
            ) != 0) {
            all_enabled = 0;
        }
    }
    if (!all_original && !all_enabled) {
        return ERROR_INVALID_DATA;
    }
    if (all_original) {
        __try {
            memcpy(
                image + WAR3_ORDER_OBSERVER_CAVE_RVA,
                enabled_cave,
                sizeof(enabled_cave)
            );
            for (index = 0; index < WAR3_ORDER_HANDLER_COUNT; ++index) {
                uint32_t call_rva = ORDER_DISPATCH_CALL_RVAS[index];
                build_relative_call(
                    enabled_call,
                    call_rva,
                    WAR3_ORDER_OBSERVER_CAVE_RVA
                );
                memcpy(
                    image + call_rva,
                    enabled_call,
                    sizeof(enabled_call)
                );
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            error = GetExceptionCode();
        }
        if (error == ERROR_SUCCESS) {
            if (memcmp(
                    image + WAR3_ORDER_OBSERVER_CAVE_RVA,
                    enabled_cave,
                    sizeof(enabled_cave)
                ) != 0) {
                error = ERROR_WRITE_FAULT;
            }
            for (index = 0;
                 error == ERROR_SUCCESS &&
                 index < WAR3_ORDER_HANDLER_COUNT;
                 ++index) {
                uint32_t call_rva = ORDER_DISPATCH_CALL_RVAS[index];
                build_relative_call(
                    enabled_call,
                    call_rva,
                    WAR3_ORDER_OBSERVER_CAVE_RVA
                );
                if (memcmp(
                        image + call_rva,
                        enabled_call,
                        sizeof(enabled_call)
                    ) != 0) {
                    error = ERROR_WRITE_FAULT;
                }
            }
        }
        if (error != ERROR_SUCCESS) {
            __try {
                memset(
                    image + WAR3_ORDER_OBSERVER_CAVE_RVA,
                    0xcc,
                    WAR3_ORDER_OBSERVER_CAVE_SIZE
                );
                for (index = 0;
                     index < WAR3_ORDER_HANDLER_COUNT;
                     ++index) {
                    uint32_t call_rva =
                        ORDER_DISPATCH_CALL_RVAS[index];
                    build_relative_call(
                        original_call,
                        call_rva,
                        WAR3_UNIT_ORDER_DISPATCH_RVA
                    );
                    memcpy(
                        image + call_rva,
                        original_call,
                        sizeof(original_call)
                    );
                }
            } __except (EXCEPTION_EXECUTE_HANDLER) {
            }
            InterlockedExchange(&g_order_observer_patch_applied, 0);
            return error;
        }
    }
    {
        HMODULE module = GetModuleHandleW(NULL);
        if (!module) {
            return ERROR_MOD_NOT_FOUND;
        }
        InterlockedExchangePointer(
            &g_unit_order_dispatch_original,
            (BYTE *)module + WAR3_UNIT_ORDER_DISPATCH_RVA
        );
    }
    InterlockedExchange(&g_order_observer_patch_applied, 1);
    return ERROR_SUCCESS;
}
#endif

static DWORD find_text_section(BYTE **start, size_t *size) {
    BYTE *module = (BYTE *)GetModuleHandleW(NULL);
    IMAGE_DOS_HEADER *dos;
    IMAGE_NT_HEADERS64 *nt;
    IMAGE_SECTION_HEADER *section;
    WORD index;
    if (module == NULL) {
        return GetLastError();
    }
    dos = (IMAGE_DOS_HEADER *)module;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew <= 0) {
        return ERROR_BAD_EXE_FORMAT;
    }
    nt = (IMAGE_NT_HEADERS64 *)(module + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE || nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR64_MAGIC) {
        return ERROR_BAD_EXE_FORMAT;
    }
    section = IMAGE_FIRST_SECTION(nt);
    for (index = 0; index < nt->FileHeader.NumberOfSections; ++index) {
        if (memcmp(section[index].Name, ".text", 5) == 0) {
            *start = module + section[index].VirtualAddress;
            *size = section[index].Misc.VirtualSize;
            return *size != 0 ? ERROR_SUCCESS : ERROR_BAD_LENGTH;
        }
    }
    return ERROR_NOT_FOUND;
}

static DWORD resolve_patches_in_range(BYTE *start, size_t size, uint32_t *failed_patch) {
    uint32_t index;
    BYTE *match;
    DWORD error;
    for (index = 0; index < WAR3_SELECTION_PATCH_COUNT; ++index) {
        match = NULL;
        error = find_unique(start, size, &PATCHES[index], &match);
        if (error != ERROR_SUCCESS) {
            *failed_patch = index;
            g_addresses_valid = 0;
            return error;
        }
        g_patch_addresses[index] = match + PATCHES[index].patch_offset;
    }
    g_addresses_valid = 1;
    return ERROR_SUCCESS;
}

#if WAR3_EARLY_IMAGE_PATCH_ENABLED
__declspec(dllexport) DWORD WINAPI War3SelectionApplyEarlyImagePatches(
    void *image,
    SIZE_T image_size
) {
    BYTE *text = NULL;
    size_t text_size = 0u;
    uint32_t failed_patch = UINT32_MAX;
    uint32_t index;
    uint32_t changed = 0u;
    uint32_t changed_indexes[WAR3_SELECTION_PATCH_COUNT];
    DWORD error;
    error = find_text_section_in_image(
        (BYTE *)image,
        image_size,
        &text,
        &text_size
    );
    if (error != ERROR_SUCCESS) {
        return error;
    }
    error = resolve_patches_in_range(text, text_size, &failed_patch);
    if (error != ERROR_SUCCESS) {
        ZeroMemory(g_patch_addresses, sizeof(g_patch_addresses));
        g_addresses_valid = 0;
        return error;
    }
    __try {
        for (index = 0; index < WAR3_SELECTION_PATCH_COUNT; ++index) {
            uint32_t enabled_value = variant_enabled_value(index);
            if (!bytes_equal(
                    g_patch_addresses[index],
                    PATCHES[index].original_value,
                    PATCHES[index].value_size
                ) &&
                !bytes_equal(
                    g_patch_addresses[index],
                    enabled_value,
                    PATCHES[index].value_size
                )) {
                error = ERROR_INVALID_DATA;
                failed_patch = index;
                __leave;
            }
        }
        if (error == ERROR_SUCCESS) {
            for (index = 0; index < WAR3_SELECTION_PATCH_COUNT; ++index) {
                uint32_t enabled_value = variant_enabled_value(index);
                if (enabled_value == PATCHES[index].original_value ||
                    bytes_equal(
                        g_patch_addresses[index],
                        enabled_value,
                        PATCHES[index].value_size
                    )) {
                    continue;
                }
                memcpy(
                    g_patch_addresses[index],
                    &enabled_value,
                    PATCHES[index].value_size
                );
                changed_indexes[changed] = index;
                ++changed;
            }
            for (index = 0; index < WAR3_SELECTION_PATCH_COUNT; ++index) {
                uint32_t enabled_value = variant_enabled_value(index);
                if (!bytes_equal(
                        g_patch_addresses[index],
                        enabled_value,
                        PATCHES[index].value_size
                    )) {
                    error = ERROR_WRITE_FAULT;
                    failed_patch = index;
                    __leave;
                }
            }
            if (error == ERROR_SUCCESS) {
#if WAR3_EARLY_ORDER_OBSERVER_PATCH_ENABLED
                error = apply_order_observer_early_patch(
                    (BYTE *)image,
                    image_size
                );
                if (error != ERROR_SUCCESS) {
                    failed_patch = WAR3_SELECTION_PATCH_COUNT;
                }
#endif
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        error = GetExceptionCode();
    }
    if (error != ERROR_SUCCESS && changed != 0u) {
        while (changed > 0u) {
            uint32_t rollback_index;
            --changed;
            rollback_index = changed_indexes[changed];
            __try {
                memcpy(
                    g_patch_addresses[rollback_index],
                    &PATCHES[rollback_index].original_value,
                    PATCHES[rollback_index].value_size
                );
            } __except (EXCEPTION_EXECUTE_HANDLER) {
            }
        }
    }
    FlushInstructionCache(GetCurrentProcess(), text, text_size);
    ZeroMemory(g_patch_addresses, sizeof(g_patch_addresses));
    g_addresses_valid = 0;
    return error;
}
#endif

static DWORD resolve_runtime_breakpoints(BYTE *text, size_t text_size) {
    DWORD error;
    error = resolve_order_handlers(text, text_size);
    if (error != ERROR_SUCCESS) {
        return error;
    }
    g_selection_breakpoints[0] = g_patch_addresses[0] - 6u;
    g_selection_breakpoints[1] = g_patch_addresses[13] - 1u;
    g_selection_breakpoints[2] = g_patch_addresses[4] - 2u;
    g_selection_breakpoints[3] = g_patch_addresses[3] - 2u;
    g_frame_capacity_breakpoint = NULL;
#if WAR3_PERSISTENT_SELECTION_BREAKPOINTS_ENABLED
    InterlockedExchange(
        &g_order_observer_patch_applied,
        g_order_dispatch_breakpoint != NULL
    );
#endif
    return ERROR_SUCCESS;
}

static uint32_t parity_even8(uint8_t value) {
    value ^= value >> 4;
    value &= 0x0fu;
    return (0x6996u >> value) & 1u ? 0u : 1u;
}

static void emulate_cmp32(CONTEXT *context, uint32_t left, uint32_t right, size_t instruction_size) {
    uint32_t result = left - right;
    uint32_t flags = 0;
    if (left < right) {
        flags |= 0x00000001u;
    }
    if (parity_even8((uint8_t)result)) {
        flags |= 0x00000004u;
    }
    if ((left ^ right ^ result) & 0x10u) {
        flags |= 0x00000010u;
    }
    if (result == 0) {
        flags |= 0x00000040u;
    }
    if (result & 0x80000000u) {
        flags |= 0x00000080u;
    }
    if (((left ^ right) & (left ^ result) & 0x80000000u) != 0) {
        flags |= 0x00000800u;
    }
    context->EFlags = (context->EFlags & ~EFLAGS_COMPARE_MASK) | flags;
    context->Rip += instruction_size;
}

static void configure_normal_breakpoints(CONTEXT *context) {
#if WAR3_PERSISTENT_SELECTION_BREAKPOINTS_ENABLED
    context->Dr0 = (DWORD64)(uintptr_t)g_selection_breakpoints[0];
    context->Dr1 = (DWORD64)(uintptr_t)g_selection_breakpoints[1];
    context->Dr2 = (DWORD64)(uintptr_t)g_selection_breakpoints[2];
#if WAR3_CLIENTSDK_CALL_PROBE_ENABLED
    context->Dr3 = (DWORD64)(uintptr_t)g_clientsdk_call_breakpoint;
    context->Dr7 = g_clientsdk_call_breakpoint ? 0x55u : 0x15u;
#else
    context->Dr3 = (DWORD64)(uintptr_t)g_selection_breakpoints[3];
    context->Dr7 = 0x55u;
#endif
#else
    context->Dr0 = 0;
    context->Dr1 = 0;
    context->Dr2 = 0;
    context->Dr3 = 0;
    context->Dr7 = 0;
#endif
    context->Dr6 = 0;
    InterlockedExchange(&g_breakpoint_mode, BREAKPOINT_MODE_NORMAL);
}

static void configure_post_selection_breakpoints(CONTEXT *context) {
#if WAR3_PERSISTENT_SELECTION_BREAKPOINTS_ENABLED
    context->Dr0 = (DWORD64)(uintptr_t)g_selection_breakpoints[0];
    context->Dr1 = (DWORD64)(uintptr_t)g_selection_breakpoints[1];
    context->Dr2 = (DWORD64)(uintptr_t)g_selection_breakpoints[2];
#if WAR3_CLIENTSDK_CALL_PROBE_ENABLED
    context->Dr3 = (DWORD64)(uintptr_t)g_clientsdk_call_breakpoint;
    context->Dr7 = g_clientsdk_call_breakpoint ? 0x55u : 0x15u;
#else
    context->Dr3 = (DWORD64)(uintptr_t)g_selection_breakpoints[3];
    context->Dr7 = 0x55u;
#endif
    context->Dr6 = 0;
#else
    context->Dr0 = 0;
    context->Dr1 = 0;
    context->Dr2 = 0;
    context->Dr3 = 0;
    context->Dr6 = 0;
    context->Dr7 = 0;
#endif
    InterlockedExchange(&g_breakpoint_mode, BREAKPOINT_MODE_POST_SELECTION);
}

static int order_index_for_entry(uintptr_t address) {
    uint32_t index;
    for (index = 0; index < WAR3_ORDER_HANDLER_COUNT; ++index) {
        if ((uintptr_t)g_order_handlers[index].entry == address) {
            return (int)index;
        }
    }
    return -1;
}

static int is_order_breakpoint(uintptr_t address) {
    uint32_t index;
    for (index = 0; index < WAR3_ORDER_HANDLER_COUNT; ++index) {
        const OrderHandlerRuntime *runtime = &g_order_handlers[index];
        if (address == (uintptr_t)runtime->stack_allocation ||
            address == (uintptr_t)runtime->cookie_store ||
            address == (uintptr_t)runtime->array_size ||
            address == (uintptr_t)runtime->cookie_load ||
            address == (uintptr_t)runtime->epilogue ||
            address == (uintptr_t)runtime->return_instruction ||
            (runtime->instant_store && address == (uintptr_t)runtime->instant_store) ||
            (runtime->instant_load && address == (uintptr_t)runtime->instant_load)) {
            return 1;
        }
    }
    return 0;
}

static OrderThreadState *order_thread_state(DWORD thread_id, int create) {
    uint32_t index;
    for (index = 0; index < WAR3_ORDER_THREAD_STATE_COUNT; ++index) {
        LONG value = InterlockedCompareExchange(
            &g_order_thread_states[index].thread_id,
            0,
            0
        );
        if ((DWORD)value == thread_id) {
            return &g_order_thread_states[index];
        }
        if (create && value == 0 &&
            InterlockedCompareExchange(
                &g_order_thread_states[index].thread_id,
                (LONG)thread_id,
                0
            ) == 0) {
            return &g_order_thread_states[index];
        }
    }
    return NULL;
}

static void set_context_breakpoint(CONTEXT *context, uint32_t slot, uintptr_t address) {
    DWORD64 value = (DWORD64)address;
    if (slot == 0u) {
        context->Dr0 = value;
    } else if (slot == 1u) {
        context->Dr1 = value;
    } else if (slot == 2u) {
        context->Dr2 = value;
    } else if (slot == 3u) {
        context->Dr3 = value;
    } else {
        return;
    }
    context->Dr7 &= ~((DWORD64)0x3u << (slot * 2u));
    context->Dr7 &= ~((DWORD64)0xfu << (16u + slot * 4u));
    if (address) {
        context->Dr7 |= (DWORD64)0x1u << (slot * 2u);
    }
}

static void save_order_debug_registers(OrderThreadState *state, const CONTEXT *context) {
    state->saved_dr0 = context->Dr0;
    state->saved_dr1 = context->Dr1;
    state->saved_dr2 = context->Dr2;
    state->saved_dr3 = context->Dr3;
    state->saved_dr7 = context->Dr7;
}

static void restore_order_debug_registers(const OrderThreadState *state, CONTEXT *context) {
    context->Dr0 = state->saved_dr0;
    context->Dr1 = state->saved_dr1;
    context->Dr2 = state->saved_dr2;
    context->Dr3 = state->saved_dr3;
    context->Dr7 = state->saved_dr7;
    context->Dr6 = 0;
}

static void configure_order_breakpoints(
    CONTEXT *context,
    OrderThreadState *state,
    uint32_t order_index
) {
    const OrderHandlerRuntime *runtime = &g_order_handlers[order_index];
    save_order_debug_registers(state, context);
    set_context_breakpoint(context, 0u, (uintptr_t)runtime->stack_allocation);
    set_context_breakpoint(context, 1u, (uintptr_t)runtime->cookie_store);
    set_context_breakpoint(context, 2u, (uintptr_t)runtime->array_size);
    set_context_breakpoint(context, 3u, 0u);
    context->Dr6 = 0;
    state->order_index = order_index;
    state->order_active = 1u;
    state->stack_expanded = 0u;
    state->return_single_step = 0u;
    InterlockedExchange(&g_breakpoint_mode, BREAKPOINT_MODE_ORDER);
}

static int begin_order_handler(CONTEXT *context, uint32_t order_index) {
    DWORD thread_id = GetCurrentThreadId();
    OrderThreadState *state;
    if (thread_id != g_window_thread_id) {
        return 0;
    }
    if (InterlockedCompareExchange(
            &g_order_owner_thread_id,
            (LONG)thread_id,
            0
        ) != 0) {
        return 0;
    }
    state = order_thread_state(thread_id, 1);
    if (!state) {
        InterlockedExchange(&g_order_owner_thread_id, 0);
        return 0;
    }
    configure_order_breakpoints(context, state, order_index);
    InterlockedIncrement64(&g_diagnostic_hits[0]);
    return 1;
}

static void finish_order_handler(OrderThreadState *state, CONTEXT *context) {
    restore_order_debug_registers(state, context);
    state->order_active = 0u;
    state->stack_expanded = 0u;
    state->return_single_step = 0u;
    InterlockedExchange(&g_order_owner_thread_id, 0);
    InterlockedExchange(&g_breakpoint_mode, BREAKPOINT_MODE_NORMAL);
    InterlockedIncrement64(&g_diagnostic_hits[3]);
    InterlockedExchange(&state->thread_id, 0);
}

static DWORD configure_order_thread(
    DWORD thread_id,
    uint32_t order_index
) {
    HANDLE thread;
    CONTEXT context;
    OrderThreadState *state;
    DWORD suspended;
    DWORD error = ERROR_SUCCESS;
    if (!thread_id || order_index >= WAR3_ORDER_HANDLER_COUNT) {
        return ERROR_INVALID_PARAMETER;
    }
    thread = OpenThread(
        THREAD_GET_CONTEXT | THREAD_SET_CONTEXT |
            THREAD_SUSPEND_RESUME | THREAD_QUERY_INFORMATION,
        FALSE,
        thread_id
    );
    if (!thread) {
        return GetLastError();
    }
    suspended = SuspendThread(thread);
    if (suspended == (DWORD)-1) {
        error = GetLastError();
        CloseHandle(thread);
        return error;
    }
    ZeroMemory(&context, sizeof(context));
    context.ContextFlags = CONTEXT_DEBUG_REGISTERS;
    state = order_thread_state(thread_id, 1);
    if (!state) {
        error = ERROR_TOO_MANY_TCBS;
    } else if (!GetThreadContext(thread, &context)) {
        error = GetLastError();
    } else {
        configure_order_breakpoints(&context, state, order_index);
        if (!SetThreadContext(thread, &context)) {
            error = GetLastError();
        }
    }
    if (error != ERROR_SUCCESS && state) {
        state->order_active = 0u;
        state->stack_expanded = 0u;
        state->return_single_step = 0u;
        InterlockedExchange(&state->thread_id, 0);
        InterlockedExchange(&g_breakpoint_mode, BREAKPOINT_MODE_NORMAL);
    }
    if (ResumeThread(thread) == (DWORD)-1 && error == ERROR_SUCCESS) {
        error = GetLastError();
    }
    CloseHandle(thread);
    return error;
}

static DWORD configure_order_observer_thread(
    DWORD thread_id,
    int enable
) {
#if WAR3_PERSISTENT_SELECTION_BREAKPOINTS_ENABLED
    HANDLE thread;
    CONTEXT context;
    DWORD suspended;
    DWORD error = ERROR_SUCCESS;

    if (!thread_id || (enable && !g_order_dispatch_breakpoint)) {
        return ERROR_INVALID_PARAMETER;
    }
    if (enable == (InterlockedCompareExchange(
            &g_order_observer_breakpoint_active,
            0,
            0
        ) != 0)) {
        return ERROR_INVALID_STATE;
    }

    thread = OpenThread(
        THREAD_GET_CONTEXT | THREAD_SET_CONTEXT |
            THREAD_SUSPEND_RESUME | THREAD_QUERY_INFORMATION,
        FALSE,
        thread_id
    );
    if (!thread) {
        return GetLastError();
    }
    suspended = SuspendThread(thread);
    if (suspended == (DWORD)-1) {
        error = GetLastError();
        CloseHandle(thread);
        return error;
    }

    ZeroMemory(&context, sizeof(context));
    context.ContextFlags = CONTEXT_DEBUG_REGISTERS;
    if (!GetThreadContext(thread, &context)) {
        error = GetLastError();
    } else if (enable) {
        g_order_observer_saved_dr3 = context.Dr3;
        g_order_observer_saved_dr7 = context.Dr7;
        set_context_breakpoint(
            &context,
            3u,
            (uintptr_t)g_order_dispatch_breakpoint
        );
        context.Dr6 = 0u;
        if (!SetThreadContext(thread, &context)) {
            error = GetLastError();
            g_order_observer_saved_dr3 = 0u;
            g_order_observer_saved_dr7 = 0u;
        } else {
            InterlockedExchange(
                &g_order_observer_breakpoint_active,
                1
            );
        }
    } else {
        context.Dr3 = g_order_observer_saved_dr3;
        context.Dr7 = g_order_observer_saved_dr7;
        context.Dr6 = 0u;
        if (!SetThreadContext(thread, &context)) {
            error = GetLastError();
        } else {
            g_order_observer_saved_dr3 = 0u;
            g_order_observer_saved_dr7 = 0u;
            InterlockedExchange(
                &g_order_observer_breakpoint_active,
                0
            );
        }
    }

    if (ResumeThread(thread) == (DWORD)-1 && error == ERROR_SUCCESS) {
        error = GetLastError();
    }
    CloseHandle(thread);
    return error;
#else
    (void)thread_id;
    (void)enable;
    return ERROR_NOT_SUPPORTED;
#endif
}

static DWORD WINAPI selection_worker_thread(LPVOID parameter) {
    (void)parameter;
    for (;;) {
        DWORD wait_result = WaitForSingleObject(g_selection_request_event, INFINITE);
        DWORD error;
        DWORD thread_id;
        LONG order_index;
        if (wait_result != WAIT_OBJECT_0) {
            break;
        }
        if (InterlockedCompareExchange(&g_selection_thread_stop, 0, 0)) {
            break;
        }
        if (InterlockedCompareExchange(&g_selection_request_pending, 2, 1) != 1) {
            continue;
        }
        thread_id = g_selection_request_thread_id;
        order_index = g_selection_request_order_index;
        if (order_index >= 0) {
            error = configure_order_thread(
                thread_id,
                (uint32_t)order_index
            );
        } else if (order_index ==
                   WAR3_SELECTION_REQUEST_OBSERVER_ENABLE) {
            error = configure_order_observer_thread(thread_id, 1);
        } else if (order_index ==
                   WAR3_SELECTION_REQUEST_OBSERVER_DISABLE) {
            error = configure_order_observer_thread(thread_id, 0);
        } else {
            error = ERROR_INVALID_PARAMETER;
        }
        g_selection_request_error = error;
        InterlockedExchange(&g_selection_request_pending, 0);
        SetEvent(g_selection_ready_event);
    }
    InterlockedExchange(&g_selection_request_pending, 0);
    if (g_selection_ready_event) {
        SetEvent(g_selection_ready_event);
    }
    return 0;
}

static DWORD start_selection_worker(void) {
    if (g_selection_thread) {
        return ERROR_SUCCESS;
    }
    g_selection_request_event = CreateEventW(NULL, FALSE, FALSE, NULL);
    if (!g_selection_request_event) {
        return GetLastError();
    }
    g_selection_ready_event = CreateEventW(NULL, FALSE, FALSE, NULL);
    if (!g_selection_ready_event) {
        DWORD error = GetLastError();
        CloseHandle(g_selection_request_event);
        g_selection_request_event = NULL;
        return error;
    }
    InterlockedExchange(&g_selection_thread_stop, 0);
    InterlockedExchange(&g_selection_request_pending, 0);
    g_selection_thread = CreateThread(
        NULL,
        0,
        selection_worker_thread,
        NULL,
        0,
        NULL
    );
    if (!g_selection_thread) {
        DWORD error = GetLastError();
        CloseHandle(g_selection_ready_event);
        CloseHandle(g_selection_request_event);
        g_selection_ready_event = NULL;
        g_selection_request_event = NULL;
        return error;
    }
    return ERROR_SUCCESS;
}

static void stop_selection_worker(void) {
    HANDLE thread = g_selection_thread;
    if (!thread) {
        return;
    }
    InterlockedExchange(&g_selection_thread_stop, 1);
    if (g_selection_request_event) {
        SetEvent(g_selection_request_event);
    }
    WaitForSingleObject(thread, INFINITE);
    CloseHandle(thread);
    g_selection_thread = NULL;
    if (g_selection_ready_event) {
        CloseHandle(g_selection_ready_event);
        g_selection_ready_event = NULL;
    }
    if (g_selection_request_event) {
        CloseHandle(g_selection_request_event);
        g_selection_request_event = NULL;
    }
    InterlockedExchange(&g_selection_request_pending, 0);
    InterlockedExchange(&g_selection_thread_stop, 0);
}

static DWORD request_order_observer_breakpoint(int enable) {
    DWORD thread_id = GetCurrentThreadId();
    DWORD wait_result;
    DWORD error;

    if (!g_enabled ||
        !g_selection_thread ||
        thread_id != g_window_thread_id) {
        return ERROR_INVALID_STATE;
    }
    if (InterlockedCompareExchange(
            &g_selection_request_pending,
            1,
            0
        ) != 0) {
        return ERROR_BUSY;
    }

    ResetEvent(g_selection_ready_event);
    g_selection_request_thread_id = thread_id;
    g_selection_request_order_index = enable
        ? WAR3_SELECTION_REQUEST_OBSERVER_ENABLE
        : WAR3_SELECTION_REQUEST_OBSERVER_DISABLE;
    g_selection_request_error = ERROR_IO_PENDING;
    if (!SetEvent(g_selection_request_event)) {
        error = GetLastError();
        InterlockedExchange(&g_selection_request_pending, 0);
        return error;
    }

    wait_result = WaitForSingleObject(g_selection_ready_event, 5000u);
    if (wait_result == WAIT_TIMEOUT &&
        InterlockedCompareExchange(
            &g_selection_request_pending,
            0,
            1
        ) == 1) {
        return ERROR_TIMEOUT;
    }
    if (wait_result != WAIT_OBJECT_0) {
        wait_result = WaitForSingleObject(
            g_selection_ready_event,
            INFINITE
        );
    }
    if (wait_result != WAIT_OBJECT_0) {
        return ERROR_GEN_FAILURE;
    }
    return g_selection_request_error;
}

static DWORD prepare_order_handler(uint32_t index) {
    DWORD thread_id = GetCurrentThreadId();
    DWORD wait_result;
    DWORD error;
    if (!g_enabled || !g_selection_thread ||
        index >= WAR3_ORDER_HANDLER_COUNT) {
        return ERROR_INVALID_STATE;
    }
    if (InterlockedCompareExchange(
            &g_order_owner_thread_id,
            (LONG)thread_id,
            0
        ) != 0) {
        return ERROR_BUSY;
    }
    ResetEvent(g_selection_ready_event);
    g_selection_request_thread_id = thread_id;
    g_selection_request_order_index = (LONG)index;
    g_selection_request_error = ERROR_IO_PENDING;
    InterlockedExchange(&g_selection_request_pending, 1);
    if (!SetEvent(g_selection_request_event)) {
        error = GetLastError();
        InterlockedExchange(&g_selection_request_pending, 0);
        InterlockedExchange(&g_order_owner_thread_id, 0);
        return error;
    }
    wait_result = WaitForSingleObject(g_selection_ready_event, 5000u);
    if (wait_result == WAIT_TIMEOUT &&
        InterlockedCompareExchange(&g_selection_request_pending, 0, 1) == 1) {
        InterlockedExchange(&g_order_owner_thread_id, 0);
        return ERROR_TIMEOUT;
    }
    if (wait_result != WAIT_OBJECT_0) {
        wait_result = WaitForSingleObject(g_selection_ready_event, INFINITE);
    }
    if (wait_result != WAIT_OBJECT_0) {
        InterlockedExchange(&g_order_owner_thread_id, 0);
        return ERROR_GEN_FAILURE;
    }
    error = g_selection_request_error;
    if (error != ERROR_SUCCESS) {
        InterlockedExchange(&g_order_owner_thread_id, 0);
    }
    return error;
}

static void continue_original_instruction(CONTEXT *context, int restore_normal) {
    if (restore_normal) {
        configure_normal_breakpoints(context);
    }
    context->Dr6 = 0;
    context->EFlags |= EFLAGS_RESUME;
}

static int is_owned_breakpoint(uintptr_t rip) {
    uint32_t index;
    if (rip == (uintptr_t)g_selection_breakpoints[0] ||
        rip == (uintptr_t)g_selection_breakpoints[1] ||
        rip == (uintptr_t)g_selection_breakpoints[2] ||
        rip == (uintptr_t)g_selection_breakpoints[3] ||
        rip == (uintptr_t)(g_patch_addresses[1] - 4) ||
        rip == (uintptr_t)(g_patch_addresses[2] - 1) ||
        rip == (uintptr_t)g_frame_capacity_breakpoint ||
        rip == (uintptr_t)g_order_dispatch_breakpoint ||
        (g_operation_return && rip == g_operation_return) ||
        is_order_breakpoint(rip)) {
        return 1;
    }
#if WAR3_CLIENTSDK_CALL_PROBE_ENABLED
    if (g_clientsdk_call_armed &&
        rip == (uintptr_t)g_clientsdk_call_breakpoint) {
        return 1;
    }
#endif
    for (index = 0; index < 4u; ++index) {
        if (g_diagnostic_breakpoints[index] &&
            rip == (uintptr_t)g_diagnostic_breakpoints[index]) {
            return 1;
        }
    }
    return 0;
}

static int handle_order_breakpoint(
    CONTEXT *context,
    OrderThreadState *state,
    uintptr_t rip,
    uint32_t slot
) {
    const OrderHandlerSpec *spec;
    const OrderHandlerRuntime *runtime;
    uint32_t delta;
    if (!state || !state->order_active ||
        state->order_index >= WAR3_ORDER_HANDLER_COUNT) {
        return 0;
    }
    spec = &ORDER_SPECS[state->order_index];
    runtime = &g_order_handlers[state->order_index];
    delta = spec->new_frame_size - spec->old_frame_size;
    if (rip == (uintptr_t)runtime->stack_allocation) {
        context->Rsp -= spec->new_frame_size;
        context->Rbp -= delta;
        context->Rip += 7u;
        set_context_breakpoint(
            context,
            slot,
            (uintptr_t)(runtime->instant_store
                ? runtime->instant_store
                : runtime->cookie_load)
        );
        state->stack_expanded = 1u;
        InterlockedIncrement64(&g_diagnostic_hits[1]);
    } else if (rip == (uintptr_t)runtime->cookie_store) {
        *(uint64_t *)(uintptr_t)(context->Rbp + spec->cookie_offset + delta) =
            context->Rax;
        context->Rip += 7u;
        set_context_breakpoint(
            context,
            slot,
            (uintptr_t)(runtime->instant_store
                ? runtime->cookie_load : runtime->epilogue)
        );
    } else if (rip == (uintptr_t)runtime->array_size) {
        context->R8 = spec->new_array_size;
        context->Rip += 6u;
        if (runtime->instant_store) {
            set_context_breakpoint(context, slot, (uintptr_t)runtime->epilogue);
        }
        InterlockedIncrement64(&g_diagnostic_hits[2]);
    } else if (runtime->instant_store &&
               rip == (uintptr_t)runtime->instant_store) {
        *(uint64_t *)(uintptr_t)(context->Rbp + spec->instant_offset + delta) =
            context->R12;
        context->Rip += 7u;
        set_context_breakpoint(context, slot, (uintptr_t)runtime->instant_load);
    } else if (runtime->instant_load &&
               rip == (uintptr_t)runtime->instant_load) {
        context->Rax = *(uint64_t *)(uintptr_t)(
            context->Rbp + spec->instant_offset + delta
        );
        context->Rip += 7u;
        set_context_breakpoint(context, slot, 0u);
    } else if (rip == (uintptr_t)runtime->cookie_load) {
        context->Rcx = *(uint64_t *)(uintptr_t)(
            context->Rbp + spec->cookie_offset + delta
        );
        context->Rip += 7u;
        set_context_breakpoint(context, slot, 0u);
    } else if (rip == (uintptr_t)runtime->epilogue) {
        context->R11 = context->Rsp + spec->new_frame_size;
        context->Rip += 8u;
        set_context_breakpoint(context, 0u, (uintptr_t)runtime->return_instruction);
        set_context_breakpoint(context, 1u, 0u);
        set_context_breakpoint(context, 2u, 0u);
        set_context_breakpoint(context, 3u, 0u);
    } else if (rip == (uintptr_t)runtime->return_instruction) {
        restore_order_debug_registers(state, context);
        state->return_single_step = 1u;
        context->EFlags |= EFLAGS_TRAP | EFLAGS_RESUME;
    } else {
        return 0;
    }
    context->Dr6 = 0;
    return 1;
}

static LONG CALLBACK selection_exception_handler(PEXCEPTION_POINTERS exception) {
    CONTEXT *context;
    uintptr_t rip;
    uint32_t hit_mask;
    uint32_t slot;
    DWORD exception_code;
    DWORD thread_id;
    OrderThreadState *thread_state;
    if (!exception || !exception->ExceptionRecord || !exception->ContextRecord) {
        return EXCEPTION_CONTINUE_SEARCH;
    }
    exception_code = exception->ExceptionRecord->ExceptionCode;
    context = exception->ContextRecord;
    rip = (uintptr_t)context->Rip;
    thread_id = GetCurrentThreadId();
    thread_state = order_thread_state(thread_id, 0);

#if WAR3_CLIENTSDK_NULL_GUARD_ENABLED
    if (exception_code == EXCEPTION_BREAKPOINT &&
        InterlockedCompareExchange(
            &g_clientsdk_guard_installed,
            0,
            0
        ) != 0 &&
        exception->ExceptionRecord->ExceptionAddress ==
            g_clientsdk_guard_address) {
        uintptr_t target_address = (uintptr_t)(
            context->Rbp + g_clientsdk_guard_displacement
        );
        uintptr_t target = 0;
        int target_valid = 1;
        __try {
            target = *(const uintptr_t *)target_address;
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            target_valid = 0;
        }
        InterlockedIncrement64(&g_diagnostic_hits[3]);
        g_diagnostic_context[0] = WAR3_CLIENTSDK_NULL_GUARD_EXCEPTION;
        g_diagnostic_context[1] = context->Rbp;
        g_diagnostic_context[2] = context->Rax;
        g_diagnostic_context[3] = context->Rcx;
        g_diagnostic_context[4] = context->Rdx;
        g_diagnostic_context[5] = context->Rsp;
        g_diagnostic_context[6] = target_address;
        g_diagnostic_context[7] = target;
        g_diagnostic_context[8] = target_valid;
#if WAR3_CRASH_TRACE_ENABLED
        record_context_trace(
            WAR3_CLIENTSDK_NULL_GUARD_EXCEPTION,
            context,
            thread_state,
            target,
            target_address
        );
#endif
        if (target_valid && target) {
            uintptr_t return_address =
                (uintptr_t)g_clientsdk_guard_address + 4u;
            __try {
                context->Rsp -= sizeof(return_address);
                *(uintptr_t *)(uintptr_t)context->Rsp = return_address;
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                context->Rsp += sizeof(return_address);
                return EXCEPTION_CONTINUE_SEARCH;
            }
            context->Rip = target;
        } else {
            context->Rax = 0;
            context->Rip =
                (DWORD64)(uintptr_t)g_clientsdk_guard_address + 4u;
        }
        return EXCEPTION_CONTINUE_EXECUTION;
    }
#endif

    if (exception_code != EXCEPTION_SINGLE_STEP) {
#if WAR3_CRASH_TRACE_ENABLED
        record_crash_trace(exception, thread_state);
#endif
        if (thread_state && thread_state->order_active) {
            finish_order_handler(thread_state, context);
        }
        return EXCEPTION_CONTINUE_SEARCH;
    }
    hit_mask = (uint32_t)(context->Dr6 & 0x0fu);

    if (thread_state && thread_state->return_single_step) {
        uint32_t return_hit_mask = hit_mask;
        finish_order_handler(thread_state, context);
        context->EFlags &= ~EFLAGS_TRAP;
        context->Dr6 = (context->Dr6 & ~(DWORD64)0x0fu) | return_hit_mask;
        hit_mask = return_hit_mask;
        if (!hit_mask) {
            return EXCEPTION_CONTINUE_EXECUTION;
        }
    }
    if (!g_addresses_valid || !hit_mask || !is_owned_breakpoint(rip)) {
        return EXCEPTION_CONTINUE_SEARCH;
    }
    for (slot = 0; slot < 4u; ++slot) {
        uintptr_t slot_address = slot == 0u ? (uintptr_t)context->Dr0 :
            slot == 1u ? (uintptr_t)context->Dr1 :
            slot == 2u ? (uintptr_t)context->Dr2 : (uintptr_t)context->Dr3;
        if ((hit_mask & (1u << slot)) && slot_address == rip) {
            break;
        }
    }
    if (slot == 4u) {
        return EXCEPTION_CONTINUE_SEARCH;
    }
    g_breakpoint_thread_id = thread_id;

    if (!g_enabled) {
        context->Dr0 = 0;
        context->Dr1 = 0;
        context->Dr2 = 0;
        context->Dr3 = 0;
        context->Dr7 = 0;
        continue_original_instruction(context, 0);
        return EXCEPTION_CONTINUE_EXECUTION;
    }

    if (rip == (uintptr_t)g_order_dispatch_breakpoint) {
        if (InterlockedCompareExchange(
                &g_order_observer_active,
                0,
                0
            ) &&
            g_order_observer_thread_id == thread_id) {
            uintptr_t return_address = 0u;
            __try {
                return_address = *(const uintptr_t *)(
                    (uintptr_t)context->Rsp +
                    g_order_dispatch_return_stack_offset
                );
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                return_address = 0u;
            }
            record_unit_order_observation(
                (uint16_t)context->R8,
                return_address,
                (uint8_t)context->R12,
                (uint8_t)context->R13,
                (uint8_t)context->Rdi
            );
        } else {
            set_context_breakpoint(
                context,
                slot,
                (uintptr_t)g_selection_breakpoints[3]
            );
            InterlockedExchange(
                &g_order_observer_breakpoint_active,
                0
            );
        }
        context->Dr6 &= ~((DWORD64)1u << slot);
        context->EFlags |= EFLAGS_RESUME;
        return EXCEPTION_CONTINUE_EXECUTION;
    }

    if (thread_state && thread_state->order_active &&
        handle_order_breakpoint(context, thread_state, rip, slot)) {
        return EXCEPTION_CONTINUE_EXECUTION;
    }

#if WAR3_CLIENTSDK_CALL_PROBE_ENABLED
    if (rip == (uintptr_t)g_clientsdk_call_breakpoint) {
        uint64_t instruction = 0;
        uint64_t target = UINT64_MAX;
        uint64_t target_address = 0;
        BYTE bytes[sizeof(instruction)];
        ZeroMemory(bytes, sizeof(bytes));
        __try {
            memcpy(bytes, (const void *)rip, sizeof(bytes));
            memcpy(&instruction, bytes, sizeof(instruction));
            if (bytes[0] == 0x48u && bytes[1] == 0xffu &&
                bytes[2] == 0x55u) {
                intptr_t displacement = (intptr_t)(int8_t)bytes[3];
                target_address = (uint64_t)(
                    (uintptr_t)context->Rbp + displacement
                );
                target = *(const uint64_t *)(uintptr_t)target_address;
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            target = UINT64_MAX;
        }
        InterlockedIncrement64(&g_diagnostic_hits[3]);
        g_diagnostic_context[0] = WAR3_CLIENTSDK_CALL_PROBE_EXCEPTION;
        g_diagnostic_context[1] = context->Rbp;
        g_diagnostic_context[2] = context->Rax;
        g_diagnostic_context[3] = context->Rcx;
        g_diagnostic_context[4] = context->Rdx;
        g_diagnostic_context[5] = context->Rsp;
        g_diagnostic_context[6] = target_address;
        g_diagnostic_context[7] = target;
        g_diagnostic_context[8] = instruction;
#if WAR3_CRASH_TRACE_ENABLED
        record_context_trace(
            WAR3_CLIENTSDK_CALL_PROBE_EXCEPTION,
            context,
            thread_state,
            target,
            instruction
        );
#endif
        context->Dr6 &= ~((DWORD64)1u << slot);
        if (target == 0u || target == UINT64_MAX) {
            context->Rax = 0;
            context->Rip += 4u;
        } else {
            context->EFlags |= EFLAGS_RESUME;
        }
        return EXCEPTION_CONTINUE_EXECUTION;
    }
#endif

    {
        if (g_breakpoint_mode == BREAKPOINT_MODE_DIAGNOSTIC &&
            g_diagnostic_breakpoints[slot] &&
            rip == (uintptr_t)g_diagnostic_breakpoints[slot]) {
                InterlockedIncrement64(&g_diagnostic_hits[slot]);
                g_diagnostic_context[0] = (uint64_t)rip;
                g_diagnostic_context[1] = slot;
                g_diagnostic_context[2] = context->Rax;
                g_diagnostic_context[3] = context->Rbx;
                g_diagnostic_context[4] = context->Rcx;
                g_diagnostic_context[5] = context->Rdx;
                g_diagnostic_context[6] = context->R8;
                g_diagnostic_context[7] = context->Rsp;
                __try {
                    g_diagnostic_context[8] =
                        *(uint64_t *)(uintptr_t)context->Rsp;
                } __except (EXCEPTION_EXECUTE_HANDLER) {
                    g_diagnostic_context[8] = 0;
                }
                context->Dr6 &= ~(DWORD64)hit_mask;
                context->EFlags |= EFLAGS_RESUME;
                return EXCEPTION_CONTINUE_EXECUTION;
        }
    }

    if (rip == (uintptr_t)g_selection_breakpoints[0]) {
        uint32_t selected_count;
        InterlockedIncrement64(&g_hit_counts[0]);
        g_selection_manager = (uintptr_t)context->Rbp;
        __try {
            selected_count = *(uint32_t *)(uintptr_t)(context->Rbp + 0x3f0u);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            continue_original_instruction(context, g_breakpoint_mode == BREAKPOINT_MODE_DISPATCH);
            return EXCEPTION_CONTINUE_EXECUTION;
        }
        emulate_cmp32(context, selected_count, 24u, 7u);
        if (selected_count >= 13u) {
            InterlockedExchange(&g_extended_selection_active, 1);
        } else {
            InterlockedExchange(&g_extended_selection_active, 0);
        }
#if WAR3_CLIENTSDK_CALL_PROBE_ENABLED
        if (g_clientsdk_call_breakpoint) {
            InterlockedExchange(&g_clientsdk_call_armed, 1);
            set_context_breakpoint(
                context,
                3u,
                (uintptr_t)g_clientsdk_call_breakpoint
            );
        }
#else
            set_context_breakpoint(
                context,
                3u,
                (uintptr_t)g_selection_breakpoints[3]
            );
#endif
    } else if (rip == (uintptr_t)g_selection_breakpoints[1]) {
        InterlockedIncrement64(&g_hit_counts[13]);
        context->Rdx = 24u;
        context->Rip += 5u;
    } else if (rip == (uintptr_t)g_selection_breakpoints[2]) {
        InterlockedIncrement64(&g_hit_counts[4]);
        emulate_cmp32(context, (uint32_t)context->Rbx, 24u, 3u);
    } else if (rip == (uintptr_t)g_selection_breakpoints[3]) {
        InterlockedIncrement64(&g_hit_counts[3]);
        emulate_cmp32(context, (uint32_t)context->Rbx, 24u, 3u);
    } else if (rip == (uintptr_t)(g_patch_addresses[1] - 4)) {
        InterlockedIncrement64(&g_hit_counts[1]);
        __try {
            *(uint32_t *)(uintptr_t)(context->Rsp + 0x28u) = 24u;
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            continue_original_instruction(context, 1);
            return EXCEPTION_CONTINUE_EXECUTION;
        }
        context->Rip += 8u;
    } else if (rip == (uintptr_t)(g_patch_addresses[2] - 1)) {
        InterlockedIncrement64(&g_hit_counts[2]);
        context->Rdx = 24u;
        context->Rip += 5u;
    } else if (rip == (uintptr_t)g_frame_capacity_breakpoint) {
        InterlockedIncrement64(&g_hit_counts[13]);
        context->Rdx = 24u;
        context->Rip += 5u;
        if (GetCurrentThreadId() == g_window_thread_id) {
            context->Dr3 = (DWORD64)(uintptr_t)g_selection_breakpoints[3];
            g_operation_return = 0;
            InterlockedExchange(&g_breakpoint_mode, BREAKPOINT_MODE_NORMAL);
        }
    } else if (rip == g_operation_return) {
        configure_post_selection_breakpoints(context);
    } else {
        continue_original_instruction(context, 1);
        return EXCEPTION_CONTINUE_EXECUTION;
    }

    context->Dr6 &= ~(DWORD64)hit_mask;
    return EXCEPTION_CONTINUE_EXECUTION;
}

static DWORD classify_state(uint32_t *state, uint32_t *failed_patch) {
    uint32_t index;
    int matches_disabled = 1;
    int matches_enabled = 1;
    if (!g_addresses_valid) {
        return ERROR_INVALID_STATE;
    }
    for (index = 0; index < WAR3_SELECTION_PATCH_COUNT; ++index) {
        int matches_original = bytes_equal(
            g_patch_addresses[index],
            PATCHES[index].original_value,
            PATCHES[index].value_size
        );
        int matches_variant = bytes_equal(
            g_patch_addresses[index],
            variant_enabled_value(index),
            PATCHES[index].value_size
        );
        if (!matches_original) {
            matches_disabled = 0;
        }
        if (!matches_variant) {
            matches_enabled = 0;
        }
        if (!matches_original && !matches_variant) {
            *failed_patch = index;
            *state = WAR3_SELECTION_STATE_UNKNOWN;
            return ERROR_INVALID_DATA;
        }
    }
    if (matches_disabled) {
        *state = WAR3_SELECTION_STATE_DISABLED;
        return ERROR_SUCCESS;
    }
    if (matches_enabled) {
        *state = WAR3_SELECTION_STATE_ENABLED;
        return ERROR_SUCCESS;
    }
    *state = WAR3_SELECTION_STATE_UNKNOWN;
    return ERROR_INVALID_DATA;
}

static DWORD write_patch_value(
    uint32_t index,
    uint32_t expected,
    uint32_t replacement
) {
    const PatchSpec *spec;
    BYTE *address;
    MEMORY_BASIC_INFORMATION memory;
    SIZE_T written = 0;
    DWORD old_protection;
    DWORD restored_protection;
    if (index >= WAR3_SELECTION_PATCH_COUNT || !g_addresses_valid) {
        return ERROR_INVALID_PARAMETER;
    }
    spec = &PATCHES[index];
    address = g_patch_addresses[index];
    if (!bytes_equal(address, expected, spec->value_size)) {
        return ERROR_INVALID_DATA;
    }
    if (!VirtualQuery(address, &memory, sizeof(memory))) {
        return GetLastError();
    }
    if (memory.Type == MEM_IMAGE || memory.Type == MEM_MAPPED) {
        if (!WriteProcessMemory(
                GetCurrentProcess(),
                address,
                &replacement,
                spec->value_size,
                &written
            ) ||
            written != spec->value_size) {
            return GetLastError() ? GetLastError() : ERROR_WRITE_FAULT;
        }
        FlushInstructionCache(GetCurrentProcess(), address, spec->value_size);
        return bytes_equal(address, replacement, spec->value_size)
            ? ERROR_SUCCESS
            : ERROR_WRITE_FAULT;
    }
    if (!VirtualProtect(
            address,
            spec->value_size,
            PAGE_READWRITE,
            &old_protection
        )) {
        return GetLastError();
    }
    memcpy(address, &replacement, spec->value_size);
    FlushInstructionCache(GetCurrentProcess(), address, spec->value_size);
    if (!VirtualProtect(
            address,
            spec->value_size,
            old_protection,
            &restored_protection
        )) {
        return GetLastError();
    }
    if (!bytes_equal(address, replacement, spec->value_size)) {
        return ERROR_WRITE_FAULT;
    }
    return ERROR_SUCCESS;
}

static DWORD apply_selection_patches(
    int enable,
    uint32_t *failed_patch
) {
    DWORD error = ERROR_SUCCESS;
    uint32_t changed = 0;
    if (enable) {
        for (changed = 0; changed < WAR3_SELECTION_PATCH_COUNT; ++changed) {
            uint32_t enabled_value = variant_enabled_value(changed);
            if (enabled_value == PATCHES[changed].original_value) {
                continue;
            }
            error = write_patch_value(
                changed,
                PATCHES[changed].original_value,
                enabled_value
            );
            if (error != ERROR_SUCCESS) {
                uint32_t rollback = changed;
                *failed_patch = changed;
                while (rollback > 0u) {
                    --rollback;
                    enabled_value = variant_enabled_value(rollback);
                    if (enabled_value == PATCHES[rollback].original_value) {
                        continue;
                    }
                    write_patch_value(
                        rollback,
                        enabled_value,
                        PATCHES[rollback].original_value
                    );
                }
                return error;
            }
        }
        return ERROR_SUCCESS;
    }
    changed = WAR3_SELECTION_PATCH_COUNT;
    while (changed > 0u) {
        uint32_t enabled_value;
        --changed;
        enabled_value = variant_enabled_value(changed);
        if (enabled_value == PATCHES[changed].original_value) {
            continue;
        }
        error = write_patch_value(
            changed,
            enabled_value,
            PATCHES[changed].original_value
        );
        if (error != ERROR_SUCCESS) {
            *failed_patch = changed;
            return error;
        }
    }
    return ERROR_SUCCESS;
}

static DWORD retain_module(void) {
    wchar_t path[MAX_PATH];
    DWORD length;
    if (g_self_reference) {
        return ERROR_SUCCESS;
    }
    length = GetModuleFileNameW(g_module, path, ARRAY_COUNT(path));
    if (!length) {
        return GetLastError();
    }
    if (length >= ARRAY_COUNT(path)) {
        return ERROR_INSUFFICIENT_BUFFER;
    }
    g_self_reference = LoadLibraryW(path);
    return g_self_reference ? ERROR_SUCCESS : GetLastError();
}

typedef struct WindowThreadSearch {
    DWORD process_id;
    DWORD thread_id;
    uint64_t client_area;
} WindowThreadSearch;

static BOOL CALLBACK find_window_thread_callback(HWND window, LPARAM parameter) {
    WindowThreadSearch *search = (WindowThreadSearch *)(uintptr_t)parameter;
    DWORD process_id = 0u;
    DWORD thread_id;
    RECT client;
    uint64_t width;
    uint64_t height;
    uint64_t area;

    if (!search ||
        !IsWindowVisible(window) ||
        GetWindow(window, GW_OWNER) != NULL) {
        return TRUE;
    }

    thread_id = GetWindowThreadProcessId(window, &process_id);
    if (!thread_id || process_id != search->process_id) {
        return TRUE;
    }
    if (!GetClientRect(window, &client) ||
        client.right <= client.left ||
        client.bottom <= client.top) {
        return TRUE;
    }

    width = (uint64_t)(client.right - client.left);
    height = (uint64_t)(client.bottom - client.top);
    if (width < 640u || height < 360u) {
        return TRUE;
    }

    area = width * height;
    if (area > search->client_area) {
        search->client_area = area;
        search->thread_id = thread_id;
    }
    return TRUE;
}

static DWORD discover_window_thread_id(void) {
    WindowThreadSearch search;

    ZeroMemory(&search, sizeof(search));
    search.process_id = GetCurrentProcessId();
    EnumWindows(
        find_window_thread_callback,
        (LPARAM)(uintptr_t)&search
    );
    return search.thread_id;
}

static DWORD configure_persistent_selection_breakpoints(
    DWORD thread_id,
    int enable
) {
#if WAR3_PERSISTENT_SELECTION_BREAKPOINTS_ENABLED
    uint64_t addresses[4];
    uint32_t index;

    if (!thread_id) {
        return ERROR_INVALID_PARAMETER;
    }
    for (index = 0u; index < ARRAY_COUNT(addresses); ++index) {
        addresses[index] = (uint64_t)(uintptr_t)g_selection_breakpoints[index];
        if (enable && !addresses[index]) {
            return ERROR_INVALID_ADDRESS;
        }
    }
    return War3SelectionLimitConfigureBreakpoints(
        thread_id,
        enable ? addresses : NULL,
        enable ? (uint32_t)ARRAY_COUNT(addresses) : 0u,
        enable
    );
#else
    (void)thread_id;
    (void)enable;
    return ERROR_SUCCESS;
#endif
}

static int enable_action_accepts_state(uint32_t state) {
#if WAR3_DIRECT_SELECTION_PATCHES_ENABLED || \
    WAR3_PERSISTENT_SELECTION_BREAKPOINTS_ENABLED
#if WAR3_EARLY_IMAGE_PATCH_ENABLED
    return state == WAR3_SELECTION_STATE_DISABLED ||
        state == WAR3_SELECTION_STATE_ENABLED;
#else
    return state == WAR3_SELECTION_STATE_DISABLED;
#endif
#else
    return state == WAR3_SELECTION_STATE_ENABLED;
#endif
}

static int enable_action_needs_selection_patches(uint32_t state) {
#if WAR3_DIRECT_SELECTION_PATCHES_ENABLED
    return state != WAR3_SELECTION_STATE_ENABLED;
#else
    (void)state;
    return 0;
#endif
}

static DWORD execute_action(
    uint32_t action,
    uint32_t *state,
    uint32_t *failed_patch,
    const uint64_t *diagnostic_addresses
) {
    BYTE *text = NULL;
    size_t text_size = 0;
    DWORD error;
    uint32_t index;
    *failed_patch = UINT32_MAX;
    error = find_text_section(&text, &text_size);
    if (error != ERROR_SUCCESS) {
        return error;
    }
    error = resolve_patches_in_range(text, text_size, failed_patch);
    if (error != ERROR_SUCCESS) {
        return error;
    }
    error = resolve_runtime_breakpoints(text, text_size);
    if (error != ERROR_SUCCESS) {
        return error;
    }
    error = classify_state(state, failed_patch);
    if (error != ERROR_SUCCESS) {
        return error;
    }
    if (action == WAR3_SELECTION_ACTION_QUERY) {
        *state = g_enabled ? WAR3_SELECTION_STATE_ENABLED : WAR3_SELECTION_STATE_DISABLED;
        return ERROR_SUCCESS;
    }
    if (action == WAR3_SELECTION_ACTION_DIAGNOSTIC) {
        if (!diagnostic_addresses) {
            return ERROR_INVALID_STATE;
        }
        error = retain_module();
        if (error != ERROR_SUCCESS) {
            return error;
        }
        if (!g_exception_handler) {
            g_exception_handler = AddVectoredExceptionHandler(1, selection_exception_handler);
            if (!g_exception_handler) {
                return GetLastError();
            }
        }
        for (index = 0; index < 4u; ++index) {
            g_diagnostic_breakpoints[index] =
                (BYTE *)(uintptr_t)diagnostic_addresses[index];
            InterlockedExchange64(&g_diagnostic_hits[index], 0);
        }
        ZeroMemory((void *)g_diagnostic_context, sizeof(g_diagnostic_context));
        g_enabled = 1;
        g_window_thread_id = discover_window_thread_id();
        if (!g_window_thread_id) {
            g_window_thread_id = GetCurrentThreadId();
        }
        InterlockedExchange(&g_breakpoint_mode, BREAKPOINT_MODE_DIAGNOSTIC);
        *state = WAR3_SELECTION_STATE_ENABLED;
        return ERROR_SUCCESS;
    }
    if (action == WAR3_SELECTION_ACTION_ENABLE) {
        int created_exception_handler = 0;
        DWORD target_window_thread_id = g_window_thread_id;
#if WAR3_DIRECT_SELECTION_PATCHES_ENABLED
        int apply_direct_selection_patches =
            enable_action_needs_selection_patches(*state);
#endif
#if WAR3_CLIENTSDK_CALL_PROBE_ENABLED
        HMODULE clientsdk;
        MEMORY_BASIC_INFORMATION clientsdk_memory;
#endif
        if (!enable_action_accepts_state(*state)) {
            return ERROR_INVALID_DATA;
        }
        if (!target_window_thread_id) {
            target_window_thread_id = discover_window_thread_id();
        }
        if (!target_window_thread_id) {
            if (g_auto_enable_thread_id == GetCurrentThreadId() &&
                InterlockedCompareExchange(
                    &g_auto_enable_state,
                    0,
                    0
                ) == 1) {
                return ERROR_NOT_READY;
            }
            target_window_thread_id = GetCurrentThreadId();
        }
        error = retain_module();
        if (error != ERROR_SUCCESS) {
            return error;
        }
#if WAR3_CRASH_TRACE_ENABLED
        error = open_crash_trace();
        if (error != ERROR_SUCCESS) {
            return error;
        }
#endif
#if WAR3_CLIENTSDK_CALL_PROBE_ENABLED
        clientsdk = GetModuleHandleW(L"ClientSdk.dll");
        if (!clientsdk ||
            WAR3_CLIENTSDK_NULL_CALL_RVA >
                UINTPTR_MAX - (uintptr_t)clientsdk) {
            error = ERROR_MOD_NOT_FOUND;
        } else {
            g_clientsdk_call_breakpoint =
                (BYTE *)(uintptr_t)(
                    (uintptr_t)clientsdk + WAR3_CLIENTSDK_NULL_CALL_RVA
                );
            if (!VirtualQuery(
                    g_clientsdk_call_breakpoint,
                    &clientsdk_memory,
                    sizeof(clientsdk_memory)
                ) ||
                clientsdk_memory.State != MEM_COMMIT ||
                !executable_image_protection(clientsdk_memory.Protect)) {
                error = ERROR_BAD_EXE_FORMAT;
            }
        }
        if (error != ERROR_SUCCESS) {
            g_clientsdk_call_breakpoint = NULL;
#if WAR3_CRASH_TRACE_ENABLED
            close_crash_trace();
#endif
            return error;
        }
        InterlockedExchange(&g_clientsdk_call_armed, 1);
#endif
        if (!g_exception_handler) {
            g_exception_handler = AddVectoredExceptionHandler(
                1,
                selection_exception_handler
            );
            if (!g_exception_handler) {
                error = GetLastError();
#if WAR3_CRASH_TRACE_ENABLED
                close_crash_trace();
#endif
                return error;
            }
            created_exception_handler = 1;
        }
#if WAR3_CLIENTSDK_NULL_GUARD_ENABLED
        error = install_clientsdk_null_guard();
        if (error != ERROR_SUCCESS) {
            if (created_exception_handler) {
                RemoveVectoredExceptionHandler(g_exception_handler);
                g_exception_handler = NULL;
            }
#if WAR3_CRASH_TRACE_ENABLED
            close_crash_trace();
#endif
            return error;
        }
#endif
        g_window_thread_id = target_window_thread_id;
        error = start_selection_worker();
        if (error != ERROR_SUCCESS) {
            g_window_thread_id = 0u;
#if WAR3_CLIENTSDK_NULL_GUARD_ENABLED
            remove_clientsdk_null_guard();
#endif
            if (created_exception_handler) {
                RemoveVectoredExceptionHandler(g_exception_handler);
                g_exception_handler = NULL;
            }
#if WAR3_CRASH_TRACE_ENABLED
            close_crash_trace();
#endif
            return error;
        }
        ZeroMemory(g_order_thread_states, sizeof(g_order_thread_states));
        InterlockedExchange(&g_order_owner_thread_id, 0);
        InterlockedExchange(&g_extended_selection_active, 0);
        g_selection_manager = 0;
        error = resolve_selection_manager();
        if (error != ERROR_SUCCESS) {
            g_window_thread_id = 0;
            stop_selection_worker();
#if WAR3_CLIENTSDK_NULL_GUARD_ENABLED
            remove_clientsdk_null_guard();
#endif
            if (created_exception_handler) {
                RemoveVectoredExceptionHandler(g_exception_handler);
                g_exception_handler = NULL;
            }
#if WAR3_CRASH_TRACE_ENABLED
            close_crash_trace();
#endif
            return error;
        }
        error = initialize_order_route_lock();
        if (error != ERROR_SUCCESS) {
            g_selection_manager = 0;
            g_window_thread_id = 0;
            stop_selection_worker();
#if WAR3_CLIENTSDK_NULL_GUARD_ENABLED
            remove_clientsdk_null_guard();
#endif
            if (created_exception_handler) {
                RemoveVectoredExceptionHandler(g_exception_handler);
                g_exception_handler = NULL;
            }
#if WAR3_CRASH_TRACE_ENABLED
            close_crash_trace();
#endif
            return error;
        }
        g_enabled = 1;
        error = install_order_pointer_hooks();
        if (error != ERROR_SUCCESS) {
            g_enabled = 0;
            delete_order_route_lock();
            g_selection_manager = 0;
            g_window_thread_id = 0;
            stop_selection_worker();
#if WAR3_CLIENTSDK_NULL_GUARD_ENABLED
            remove_clientsdk_null_guard();
#endif
            if (created_exception_handler) {
                RemoveVectoredExceptionHandler(g_exception_handler);
                g_exception_handler = NULL;
            }
#if WAR3_CRASH_TRACE_ENABLED
            close_crash_trace();
#endif
            return error;
        }
#if WAR3_DIRECT_SELECTION_PATCHES_ENABLED
        if (apply_direct_selection_patches) {
            error = apply_selection_patches(1, failed_patch);
            if (error != ERROR_SUCCESS) {
                g_enabled = 0;
                remove_order_pointer_hooks();
                delete_order_route_lock();
                g_selection_manager = 0;
                g_window_thread_id = 0;
                stop_selection_worker();
#if WAR3_CLIENTSDK_NULL_GUARD_ENABLED
                remove_clientsdk_null_guard();
#endif
                if (created_exception_handler) {
                    RemoveVectoredExceptionHandler(g_exception_handler);
                    g_exception_handler = NULL;
                }
#if WAR3_CRASH_TRACE_ENABLED
                close_crash_trace();
#endif
                return error;
            }
        }
#endif
        error = configure_persistent_selection_breakpoints(
            g_window_thread_id,
            1
        );
        if (error != ERROR_SUCCESS) {
#if WAR3_DIRECT_SELECTION_PATCHES_ENABLED
            if (apply_direct_selection_patches) {
                uint32_t rollback_failed_patch = UINT32_MAX;
                apply_selection_patches(0, &rollback_failed_patch);
            }
#endif
            g_enabled = 0;
            remove_order_pointer_hooks();
            delete_order_route_lock();
            g_selection_manager = 0;
            g_window_thread_id = 0;
            stop_selection_worker();
#if WAR3_CLIENTSDK_NULL_GUARD_ENABLED
            remove_clientsdk_null_guard();
#endif
            if (created_exception_handler) {
                RemoveVectoredExceptionHandler(g_exception_handler);
                g_exception_handler = NULL;
            }
#if WAR3_CRASH_TRACE_ENABLED
            close_crash_trace();
#endif
            return error;
        }
        InterlockedExchange(&g_breakpoint_mode, BREAKPOINT_MODE_NORMAL);
        *state = WAR3_SELECTION_STATE_ENABLED;
    } else if (action == WAR3_SELECTION_ACTION_DISABLE) {
        DWORD patch_error = ERROR_SUCCESS;
        DWORD breakpoint_error = ERROR_SUCCESS;
#if WAR3_CLIENTSDK_NULL_GUARD_ENABLED
        DWORD guard_error = ERROR_SUCCESS;
#endif
        if (*state != WAR3_SELECTION_STATE_DISABLED && *state != WAR3_SELECTION_STATE_ENABLED) {
            return ERROR_INVALID_DATA;
        }
        if (InterlockedCompareExchange(&g_order_owner_thread_id, 0, 0) != 0) {
            return ERROR_BUSY;
        }
        if (g_window_thread_id) {
            breakpoint_error = configure_persistent_selection_breakpoints(
                g_window_thread_id,
                0
            );
        }
        g_enabled = 0;
        remove_order_pointer_hooks();
        delete_order_route_lock();
        stop_selection_worker();
        InterlockedExchange(&g_order_owner_thread_id, 0);
        InterlockedExchange(&g_order_observer_active, 0);
        InterlockedExchange(&g_order_observer_breakpoint_active, 0);
        g_order_observer_thread_id = 0u;
        g_order_observer_saved_dr3 = 0u;
        g_order_observer_saved_dr7 = 0u;
        g_window_thread_id = 0;
        InterlockedExchange(&g_extended_selection_active, 0);
#if WAR3_DIRECT_SELECTION_PATCHES_ENABLED
        if (*state == WAR3_SELECTION_STATE_ENABLED) {
            patch_error = apply_selection_patches(0, failed_patch);
        }
#endif
        g_selection_manager = 0;
        ZeroMemory(g_diagnostic_breakpoints, sizeof(g_diagnostic_breakpoints));
#if WAR3_CLIENTSDK_CALL_PROBE_ENABLED
        g_clientsdk_call_breakpoint = NULL;
        InterlockedExchange(&g_clientsdk_call_armed, 0);
#endif
#if WAR3_CLIENTSDK_NULL_GUARD_ENABLED
        guard_error = remove_clientsdk_null_guard();
#endif
        if (g_exception_handler) {
            RemoveVectoredExceptionHandler(g_exception_handler);
            g_exception_handler = NULL;
        }
#if WAR3_CRASH_TRACE_ENABLED
        close_crash_trace();
#endif
        if (patch_error != ERROR_SUCCESS) {
            *state = WAR3_SELECTION_STATE_UNKNOWN;
            return patch_error;
        }
        if (breakpoint_error != ERROR_SUCCESS) {
            *state = WAR3_SELECTION_STATE_UNKNOWN;
            return breakpoint_error;
        }
#if WAR3_CLIENTSDK_NULL_GUARD_ENABLED
        if (guard_error != ERROR_SUCCESS) {
            *state = WAR3_SELECTION_STATE_UNKNOWN;
            return guard_error;
        }
#endif
        *state = WAR3_SELECTION_STATE_DISABLED;
    } else {
        return ERROR_INVALID_PARAMETER;
    }
    return ERROR_SUCCESS;
}

#if WAR3_AUTO_ENABLE_ON_LOAD
#pragma pack(push, 1)
typedef struct AutoEnableStatus {
    uint32_t magic;
    uint32_t version;
    uint32_t state;
    uint32_t attempts;
    uint32_t last_error;
    uint32_t early_patch_error;
    uint32_t thread_id;
    uint32_t failed_patch;
    uint32_t window_thread_id;
    uint32_t breakpoint_thread_id;
    uint32_t observer_ready;
    uint32_t process_id;
    uint32_t order_resolution_stage;
    uint32_t sync_count;
    uint32_t mirror_count;
    uint32_t local_count;
    uint32_t observer_count;
    uint32_t observer_flags;
    uint32_t observer_single_recipient;
    uint32_t observer_invalid_return;
    uint32_t route_poisoned;
    uint64_t selection_manager;
    uint64_t diagnostic_hits[4];
    uint64_t diagnostic_context[9];
} AutoEnableStatus;
#pragma pack(pop)

static void write_auto_enable_status(
    uint32_t state,
    uint32_t failed_patch
) {
    wchar_t path[MAX_PATH];
    wchar_t *separator;
    DWORD length;
    DWORD written;
    HANDLE file;
    AutoEnableStatus status;
    length = GetModuleFileNameW(g_module, path, ARRAY_COUNT(path));
    if (!length || length >= ARRAY_COUNT(path)) {
        return;
    }
    separator = wcsrchr(path, L'\\');
    if (!separator) {
        return;
    }
    wcscpy_s(
        separator + 1,
        ARRAY_COUNT(path) - (size_t)(separator + 1 - path),
        L"war3_selection_auto_status.bin"
    );
    status.magic = 0x41533357u;
    status.version = 3u;
    status.state = state;
    status.attempts = (uint32_t)InterlockedCompareExchange(
        &g_auto_enable_attempts,
        0,
        0
    );
    status.last_error = g_auto_enable_error;
#if WAR3_EARLY_IMAGE_PATCH_ENABLED
    status.early_patch_error = War3EarlyImagePatchStatus();
#else
    status.early_patch_error = ERROR_NOT_SUPPORTED;
#endif
    status.thread_id = g_auto_enable_thread_id;
    status.failed_patch = failed_patch;
    status.window_thread_id = g_window_thread_id;
    status.breakpoint_thread_id = g_breakpoint_thread_id;
    status.observer_ready = (uint32_t)InterlockedCompareExchange(
        &g_order_observer_patch_applied,
        0,
        0
    );
    status.process_id = GetCurrentProcessId();
    status.order_resolution_stage = (uint32_t)InterlockedCompareExchange(
        &g_order_resolution_stage,
        0,
        0
    );
    status.sync_count = 0u;
    status.mirror_count = 0u;
    status.local_count = 0u;
    status.selection_manager = (uint64_t)g_selection_manager;
    if (g_selection_manager) {
        __try {
            status.sync_count =
                ((const UnitSetView *)(uintptr_t)g_selection_manager)
                    ->count;
            status.mirror_count =
                ((const UnitSetView *)(uintptr_t)(
                    g_selection_manager +
                    WAR3_MIRROR_UNIT_SET_OFFSET
                ))->count;
            status.local_count =
                ((const UnitSetView *)(uintptr_t)(
                    g_selection_manager +
                    WAR3_LOCAL_UNIT_SET_OFFSET
                ))->count;
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            status.sync_count = UINT32_MAX;
            status.mirror_count = UINT32_MAX;
            status.local_count = UINT32_MAX;
        }
    }
    status.observer_count = (uint32_t)InterlockedCompareExchange(
        &g_order_observer_count,
        0,
        0
    );
    status.observer_flags = (uint32_t)InterlockedCompareExchange(
        &g_order_observer_flags,
        0,
        0
    );
    status.observer_single_recipient =
        (uint32_t)InterlockedCompareExchange(
            &g_order_observer_single_recipient,
            0,
            0
        );
    status.observer_invalid_return =
        (uint32_t)InterlockedCompareExchange(
            &g_order_observer_invalid_return,
            0,
            0
        );
    status.route_poisoned = (uint32_t)InterlockedCompareExchange(
        &g_order_route_poisoned,
        0,
        0
    );
    for (uint32_t index = 0u; index < 4u; ++index) {
        status.diagnostic_hits[index] =
            (uint64_t)g_diagnostic_hits[index];
    }
    for (uint32_t index = 0u; index < 9u; ++index) {
        status.diagnostic_context[index] =
            (uint64_t)g_diagnostic_context[index];
    }
    file = CreateFileW(
        path,
        GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL
    );
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }
    WriteFile(file, &status, sizeof(status), &written, NULL);
    FlushFileBuffers(file);
    CloseHandle(file);
}

static DWORD WINAPI auto_enable_thread_proc(void *parameter) {
    uint32_t state = WAR3_SELECTION_STATE_UNKNOWN;
    uint32_t failed_patch = UINT32_MAX;
    DWORD error;
    LONG attempts;
    (void)parameter;
    g_auto_enable_thread_id = GetCurrentThreadId();
    write_auto_enable_status(1u, failed_patch);
    for (;;) {
        Sleep(500u);
        if (InterlockedCompareExchange(&g_auto_enable_state, 0, 0) != 1) {
            break;
        }
        attempts = InterlockedIncrement(&g_auto_enable_attempts);
#if WAR3_EARLY_IMAGE_PATCH_ENABLED
        error = War3EarlyImagePatchStatus();
        if (error != ERROR_SUCCESS) {
            g_auto_enable_error = error;
            if ((attempts % 4) == 0) {
                write_auto_enable_status(1u, failed_patch);
            }
            continue;
        }
#endif
        if (attempts < 4) {
            continue;
        }
        error = execute_action(
            WAR3_SELECTION_ACTION_ENABLE,
            &state,
            &failed_patch,
            NULL
        );
        g_auto_enable_error = error;
        if (error == ERROR_SUCCESS) {
            write_auto_enable_status(2u, failed_patch);
            InterlockedExchange(&g_auto_enable_state, 2);
            while (InterlockedCompareExchange(
                    &g_auto_enable_state,
                    0,
                    0
                ) == 2) {
                Sleep(1000u);
                write_auto_enable_status(2u, failed_patch);
            }
            break;
        }
        if ((attempts % 4) == 0) {
            write_auto_enable_status(1u, failed_patch);
        }
    }
    return g_auto_enable_error;
}
#endif

void WINAPI War3SelectionAutoBootstrap(void) {
#if WAR3_AUTO_ENABLE_ON_LOAD
    HANDLE thread;
    DWORD thread_id = 0u;
    if (InterlockedCompareExchange(&g_auto_enable_state, 1, 0) != 0) {
        return;
    }
    InterlockedExchange(&g_auto_enable_attempts, 0);
    g_auto_enable_error = ERROR_IO_PENDING;
    thread = CreateThread(
        NULL,
        0u,
        auto_enable_thread_proc,
        NULL,
        0u,
        &thread_id
    );
    if (!thread) {
        g_auto_enable_error = GetLastError();
        InterlockedExchange(&g_auto_enable_state, 0);
        write_auto_enable_status(0u, UINT32_MAX);
        return;
    }
    g_auto_enable_thread_id = thread_id;
    CloseHandle(thread);
#endif
}

static void command_path(wchar_t *path, DWORD count) {
    DWORD used = GetModuleFileNameW(g_module, path, count);
    wchar_t *separator;
    if (!used || used >= count) {
        path[0] = L'\0';
        return;
    }
    separator = wcsrchr(path, L'\\');
    if (!separator) {
        path[0] = L'\0';
        return;
    }
    used = (DWORD)(separator - path + 1);
    swprintf(path + used, count - used, L"war3_selection_limit_%lu.bin", GetCurrentProcessId());
}

static void run_command(void) {
    wchar_t path[MAX_PATH];
    SelectionCommand command;
    HANDLE file;
    DWORD read_count = 0;
    DWORD write_count = 0;
    uint32_t index;

    ZeroMemory(&command, sizeof(command));
    command_path(path, MAX_PATH);
    if (!path[0]) {
        return;
    }
    file = CreateFileW(path, GENERIC_READ | GENERIC_WRITE, 0, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }
    if (!ReadFile(file, &command, sizeof(command), &read_count, NULL) ||
        read_count != sizeof(command) ||
        command.magic != WAR3_SELECTION_MAGIC ||
        command.version != WAR3_SELECTION_VERSION ||
        command.status != WAR3_SELECTION_STATUS_PENDING ||
        command.requested_limit != 24u) {
        CloseHandle(file);
        return;
    }

    command.patch_count = WAR3_SELECTION_PATCH_COUNT;
    command.last_error = execute_action(
        command.action,
        &command.state,
        &command.failed_patch,
        command.diagnostic_context
    );
    if (g_addresses_valid) {
        for (index = 0; index < WAR3_SELECTION_PATCH_COUNT; ++index) {
            command.patch_addresses[index] = (uint64_t)(uintptr_t)g_patch_addresses[index];
        }
#if WAR3_PERSISTENT_SELECTION_BREAKPOINTS_ENABLED
        command.breakpoint_addresses[0] = (uint64_t)(uintptr_t)g_selection_breakpoints[0];
        command.breakpoint_addresses[1] = (uint64_t)(uintptr_t)g_selection_breakpoints[1];
        command.breakpoint_addresses[2] = (uint64_t)(uintptr_t)g_selection_breakpoints[2];
#if WAR3_CLIENTSDK_CALL_PROBE_ENABLED
        command.breakpoint_addresses[3] =
            (uint64_t)(uintptr_t)g_clientsdk_call_breakpoint;
#endif
#endif
#if !WAR3_CLIENTSDK_CALL_PROBE_ENABLED
        command.breakpoint_addresses[3] = 0;
#endif
    }
    command.selected_count = 0;
    if (g_selection_manager) {
        __try {
            command.selected_count = *(uint32_t *)(g_selection_manager + 0x3f0u);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            command.selected_count = 0;
        }
    }
    command.breakpoint_mode = (uint32_t)g_breakpoint_mode;
    command.breakpoint_thread_id = g_breakpoint_thread_id;
    command.reserved2 = (uint32_t)g_order_resolution_stage;
    command.selection_manager = (uint64_t)g_selection_manager;
    for (index = 0; index < WAR3_SELECTION_PATCH_COUNT; ++index) {
        command.hit_counts[index] = (uint64_t)g_hit_counts[index];
    }
    for (index = 0; index < 4u; ++index) {
        command.diagnostic_hits[index] = (uint64_t)g_diagnostic_hits[index];
    }
    for (index = 0; index < 9u; ++index) {
        command.diagnostic_context[index] = (uint64_t)g_diagnostic_context[index];
    }
    command.status = command.last_error == ERROR_SUCCESS
        ? WAR3_SELECTION_STATUS_OK
        : WAR3_SELECTION_STATUS_FAILED;
    SetFilePointer(file, 0, NULL, FILE_BEGIN);
    WriteFile(file, &command, sizeof(command), &write_count, NULL);
    SetEndOfFile(file);
    FlushFileBuffers(file);
    CloseHandle(file);
}

__declspec(dllexport) LRESULT CALLBACK War3SelectionLimitHookProc(int code, WPARAM w_param, LPARAM l_param) {
    if (code >= 0 && InterlockedCompareExchange(&g_processing, 1, 0) == 0) {
        __try {
            run_command();
        } __finally {
            InterlockedExchange(&g_processing, 0);
        }
    }
    return CallNextHookEx(NULL, code, w_param, l_param);
}

__declspec(dllexport) DWORD WINAPI War3SelectionLimitConfigureBreakpoints(
    DWORD thread_id,
    const uint64_t *addresses,
    uint32_t count,
    int enable
) {
    HANDLE thread;
    CONTEXT context;
    DWORD suspended;
    DWORD error = ERROR_SUCCESS;
    if (!thread_id || (enable && (!addresses || count != 4u))) {
        return ERROR_INVALID_PARAMETER;
    }
    thread = OpenThread(
        THREAD_GET_CONTEXT | THREAD_SET_CONTEXT | THREAD_SUSPEND_RESUME | THREAD_QUERY_INFORMATION,
        FALSE,
        thread_id
    );
    if (!thread) {
        return GetLastError();
    }
    suspended = SuspendThread(thread);
    if (suspended == (DWORD)-1) {
        error = GetLastError();
        CloseHandle(thread);
        return error;
    }
    ZeroMemory(&context, sizeof(context));
    context.ContextFlags = CONTEXT_DEBUG_REGISTERS;
    if (!GetThreadContext(thread, &context)) {
        error = GetLastError();
    } else {
        uint32_t slot;
        context.Dr0 = enable ? addresses[0] : 0;
        context.Dr1 = enable ? addresses[1] : 0;
        context.Dr2 = enable ? addresses[2] : 0;
        context.Dr3 = enable ? addresses[3] : 0;
        context.Dr6 = 0;
        context.Dr7 = 0;
        if (enable) {
            for (slot = 0; slot < 4u; ++slot) {
                if (addresses[slot]) {
                    context.Dr7 |= (DWORD64)1u << (slot * 2u);
                }
            }
        }
        if (!SetThreadContext(thread, &context)) {
            error = GetLastError();
        }
    }
    if (ResumeThread(thread) == (DWORD)-1 && error == ERROR_SUCCESS) {
        error = GetLastError();
    }
    CloseHandle(thread);
    if (error == ERROR_SUCCESS) {
        g_breakpoint_thread_id = enable ? thread_id : 0u;
    }
    return error;
}

__declspec(dllexport) DWORD WINAPI War3SelectionLimitConfigureProcessBreakpoints(
    DWORD process_id,
    const uint64_t *addresses,
    uint32_t count,
    int enable
) {
    HANDLE snapshot;
    THREADENTRY32 entry;
    DWORD first_error = ERROR_SUCCESS;
    DWORD configured = 0;
    if (!process_id || (enable && (!addresses || count != 4u))) {
        return ERROR_INVALID_PARAMETER;
    }
    snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    if (snapshot == INVALID_HANDLE_VALUE) {
        return GetLastError();
    }
    ZeroMemory(&entry, sizeof(entry));
    entry.dwSize = sizeof(entry);
    if (!Thread32First(snapshot, &entry)) {
        first_error = GetLastError();
        CloseHandle(snapshot);
        return first_error;
    }
    do {
        DWORD error;
        if (entry.th32OwnerProcessID != process_id) {
            continue;
        }
        error = War3SelectionLimitConfigureBreakpoints(
            entry.th32ThreadID,
            addresses,
            count,
            enable
        );
        if (error == ERROR_SUCCESS) {
            ++configured;
        } else if (first_error == ERROR_SUCCESS &&
                   error != ERROR_ACCESS_DENIED &&
                   error != ERROR_INVALID_PARAMETER) {
            first_error = error;
        }
    } while (Thread32Next(snapshot, &entry));
    CloseHandle(snapshot);
    if (!configured) {
        return first_error != ERROR_SUCCESS ? first_error : ERROR_NOT_FOUND;
    }
    return ERROR_SUCCESS;
}

static DWORD64 *debug_register(CONTEXT *context, uint32_t slot) {
    switch (slot) {
    case 0:
        return &context->Dr0;
    case 1:
        return &context->Dr1;
    case 2:
        return &context->Dr2;
    case 3:
        return &context->Dr3;
    default:
        return NULL;
    }
}

static DWORD configure_auxiliary_breakpoints(
    DWORD thread_id,
    uintptr_t frame_address,
    uintptr_t input_address,
    int enable
) {
    HANDLE thread;
    CONTEXT context;
    DWORD error = ERROR_SUCCESS;
    DWORD suspended;
    uint32_t slot;
    uintptr_t requested[2] = {frame_address, input_address};
    uint32_t requested_index;
    thread = OpenThread(
        THREAD_GET_CONTEXT | THREAD_SET_CONTEXT | THREAD_SUSPEND_RESUME | THREAD_QUERY_INFORMATION,
        FALSE,
        thread_id
    );
    if (!thread) {
        return GetLastError();
    }
    suspended = SuspendThread(thread);
    if (suspended == (DWORD)-1) {
        error = GetLastError();
        CloseHandle(thread);
        return error;
    }
    ZeroMemory(&context, sizeof(context));
    context.ContextFlags = CONTEXT_DEBUG_REGISTERS;
    if (!GetThreadContext(thread, &context)) {
        error = GetLastError();
        goto cleanup;
    }
    if (enable) {
        for (requested_index = 0; requested_index < 2u; ++requested_index) {
            if (!requested[requested_index]) {
                continue;
            }
            for (slot = 0; slot < 4u; ++slot) {
                DWORD64 *address = debug_register(&context, slot);
                if (address && *address == (DWORD64)requested[requested_index]) {
                    break;
                }
            }
            if (slot < 4u) {
                continue;
            }
            for (slot = 0; slot < 4u; ++slot) {
                DWORD64 *address = debug_register(&context, slot);
                if (address && *address == 0) {
                    *address = (DWORD64)requested[requested_index];
                    context.Dr7 &= ~((DWORD64)0x3u << (slot * 2u));
                    context.Dr7 &= ~((DWORD64)0xfu << (16u + slot * 4u));
                    context.Dr7 |= (DWORD64)0x1u << (slot * 2u);
                    context.Dr6 = 0;
                    break;
                }
            }
            if (slot == 4u) {
                error = ERROR_BUSY;
                goto cleanup;
            }
        }
        if (error == ERROR_SUCCESS && !SetThreadContext(thread, &context)) {
            error = GetLastError();
        }
    } else {
        for (slot = 0; slot < 4u; ++slot) {
            DWORD64 *address = debug_register(&context, slot);
            if (address && (*address == (DWORD64)frame_address ||
                            *address == (DWORD64)input_address)) {
                *address = 0;
                context.Dr7 &= ~((DWORD64)0x3u << (slot * 2u));
                context.Dr7 &= ~((DWORD64)0xfu << (16u + slot * 4u));
                context.Dr6 = 0;
            }
        }
        if (!SetThreadContext(thread, &context)) {
            error = GetLastError();
        }
    }

cleanup:
    ResumeThread(thread);
    CloseHandle(thread);
    return error;
}

__declspec(dllexport) DWORD WINAPI War3SelectionLimitConfigureAuxiliaryBreakpoints(
    DWORD process_id,
    DWORD window_thread_id,
    uint64_t frame_address,
    uint64_t input_address,
    int enable
) {
    HANDLE snapshot;
    THREADENTRY32 entry;
    DWORD configured = 0;
    DWORD first_error = ERROR_SUCCESS;
    if (!process_id || !window_thread_id ||
        (enable && (!frame_address || !input_address))) {
        return ERROR_INVALID_PARAMETER;
    }
    snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    if (snapshot == INVALID_HANDLE_VALUE) {
        return GetLastError();
    }
    ZeroMemory(&entry, sizeof(entry));
    entry.dwSize = sizeof(entry);
    if (!Thread32First(snapshot, &entry)) {
        first_error = GetLastError();
        CloseHandle(snapshot);
        return first_error;
    }
    do {
        DWORD error;
        if (entry.th32OwnerProcessID != process_id || entry.th32ThreadID == window_thread_id) {
            continue;
        }
        error = configure_auxiliary_breakpoints(
            entry.th32ThreadID,
            (uintptr_t)frame_address,
            (uintptr_t)input_address,
            enable
        );
        if (error == ERROR_SUCCESS) {
            ++configured;
        } else if (first_error == ERROR_SUCCESS && error != ERROR_ACCESS_DENIED && error != ERROR_BUSY) {
            first_error = error;
        }
    } while (Thread32Next(snapshot, &entry));
    CloseHandle(snapshot);
    if (!configured && first_error != ERROR_SUCCESS) {
        return first_error;
    }
    return ERROR_SUCCESS;
}

typedef struct ReplayTestSet {
    UnitSetView view;
    UnitListNode nodes[24];
} ReplayTestSet;

static UnitSetView *g_replay_test_watch_set = NULL;
static uint32_t g_replay_test_add_calls = 0u;
static uint32_t g_replay_test_remove_calls = 0u;
static uint32_t g_replay_test_fail_add_call = 0u;
static uint32_t g_replay_test_fail_remove_call = 0u;
static uint32_t g_replay_test_max_count = 0u;

static void __fastcall replay_test_add(
    UnitSetView *set,
    uintptr_t unit,
    uint8_t allow_duplicates,
    uint8_t group_like_units
) {
    ReplayTestSet *test_set = (ReplayTestSet *)set;
    UnitListNode *sentinel = (UnitListNode *)&set->last;
    UnitListNode *terminal =
        (UnitListNode *)((uintptr_t)sentinel | 1u);
    UnitListNode *node = NULL;
    uint32_t index;
    (void)allow_duplicates;
    (void)group_like_units;
    if (set == g_replay_test_watch_set) {
        ++g_replay_test_add_calls;
        if (g_replay_test_fail_add_call &&
            g_replay_test_add_calls == g_replay_test_fail_add_call) {
            return;
        }
    }
    for (index = 0; index < ARRAY_COUNT(test_set->nodes); ++index) {
        if (test_set->nodes[index].unit == unit) {
            return;
        }
        if (!node && test_set->nodes[index].unit == 0u) {
            node = &test_set->nodes[index];
        }
    }
    if (!node || !unit || set->count >= ARRAY_COUNT(test_set->nodes)) {
        return;
    }
    node->unit = unit;
    node->next = terminal;
    if (set->count == 0u) {
        node->previous = sentinel;
        set->first = node;
        set->last = node;
    } else {
        node->previous = set->last;
        set->last->next = node;
        set->last = node;
    }
    ++set->count;
    if (set == g_replay_test_watch_set &&
        set->count > g_replay_test_max_count) {
        g_replay_test_max_count = set->count;
    }
}

static void __fastcall replay_test_remove(
    UnitSetView *set,
    uintptr_t unit
) {
    ReplayTestSet *test_set = (ReplayTestSet *)set;
    UnitListNode *sentinel = (UnitListNode *)&set->last;
    UnitListNode *terminal =
        (UnitListNode *)((uintptr_t)sentinel | 1u);
    UnitListNode *node = NULL;
    UnitListNode *previous;
    UnitListNode *next;
    uint32_t index;
    if (set == g_replay_test_watch_set) {
        ++g_replay_test_remove_calls;
        if (g_replay_test_fail_remove_call &&
            g_replay_test_remove_calls ==
                g_replay_test_fail_remove_call) {
            return;
        }
    }
    for (index = 0; index < ARRAY_COUNT(test_set->nodes); ++index) {
        if (test_set->nodes[index].unit == unit) {
            node = &test_set->nodes[index];
            break;
        }
    }
    if (!node || set->count == 0u) {
        return;
    }
    previous = node->previous;
    next = node->next;
    if (previous == sentinel) {
        set->first = next;
    } else {
        previous->next = next;
    }
    if (next == terminal) {
        set->last = previous;
    } else {
        next->previous = previous;
    }
    node->previous = NULL;
    node->next = NULL;
    node->unit = 0u;
    --set->count;
}

static DWORD initialize_replay_test(
    OrderReplayState *state,
    ReplayTestSet *sync,
    ReplayTestSet *mirror,
    ReplayTestSet *local
) {
    DWORD error;
    uint32_t index;
    ZeroMemory(state, sizeof(*state));
    ZeroMemory(sync, sizeof(*sync));
    ZeroMemory(mirror, sizeof(*mirror));
    ZeroMemory(local, sizeof(*local));
    sync->view.vtable = 1u;
    sync->view.link_offset = 0x10u;
    mirror->view.vtable = 2u;
    mirror->view.link_offset = 0x20u;
    local->view.vtable = 3u;
    local->view.link_offset = 0x30u;
    for (index = 0; index < 24u; ++index) {
        uintptr_t unit = (uintptr_t)(0x1000u + index * 0x10u);
        replay_test_add(&mirror->view, unit, 0u, 0u);
        replay_test_add(&local->view, unit, 0u, 0u);
        if (index < WAR3_NATIVE_SELECTION_LIMIT) {
            replay_test_add(&sync->view, unit, 0u, 0u);
        }
    }
    state->sync_set = &sync->view;
    state->mirror_set = &mirror->view;
    state->local_set = &local->view;
    state->add = replay_test_add;
    state->remove = replay_test_remove;
    error = snapshot_unit_set(
        state->sync_set,
        &state->original_sync
    );
    if (error == ERROR_SUCCESS) {
        error = snapshot_unit_set(
            state->mirror_set,
            &state->original_mirror
        );
    }
    if (error == ERROR_SUCCESS) {
        error = snapshot_unit_set(
            state->local_set,
            &state->original_local
        );
    }
    if (error == ERROR_SUCCESS) {
        error = validate_order_replay_snapshots(state);
    }
    if (error == ERROR_SUCCESS) {
        state->prepared = 1;
    }
    return error;
}

static DWORD self_test_order_replay(void) {
    OrderReplayState state;
    ReplayTestSet sync;
    ReplayTestSet mirror;
    ReplayTestSet local;
    UnitSetSnapshot restored;
    uint32_t failure_mode;
    uint32_t failure_step;
    DWORD error;

    for (failure_mode = 0u; failure_mode < 5u; ++failure_mode) {
        uint32_t step_count = failure_mode == 0u
            ? 1u
            : WAR3_NATIVE_SELECTION_LIMIT;
        for (failure_step = 1u;
             failure_step <= step_count;
             ++failure_step) {
            g_replay_test_watch_set = NULL;
            g_replay_test_add_calls = 0u;
            g_replay_test_remove_calls = 0u;
            g_replay_test_fail_add_call = 0u;
            g_replay_test_fail_remove_call = 0u;
            g_replay_test_max_count = 0u;
            error = initialize_replay_test(
                &state,
                &sync,
                &mirror,
                &local
            );
            if (error != ERROR_SUCCESS) {
                return 0x10000u |
                    (failure_mode << 12u) |
                    (failure_step << 4u) |
                    (error & 0xfu);
            }
            g_replay_test_watch_set = state.sync_set;
            if (failure_mode == 1u) {
                g_replay_test_fail_remove_call = failure_step;
            } else if (failure_mode == 2u) {
                g_replay_test_fail_add_call = failure_step;
            }
            error = install_extra_sync_batch(&state);
            if (((failure_mode == 1u || failure_mode == 2u) &&
                 error == ERROR_SUCCESS) ||
                ((failure_mode == 0u || failure_mode >= 3u) &&
                 error != ERROR_SUCCESS)) {
                return 0x20000u |
                    (failure_mode << 12u) |
                    (failure_step << 4u) |
                    (error & 0xfu);
            }
            if (failure_mode == 1u || failure_mode == 2u) {
                g_replay_test_fail_add_call = 0u;
                g_replay_test_fail_remove_call = 0u;
            } else if (failure_mode == 3u) {
                g_replay_test_fail_remove_call =
                    g_replay_test_remove_calls + failure_step;
            } else if (failure_mode == 4u) {
                g_replay_test_fail_add_call =
                    g_replay_test_add_calls + failure_step;
            }
            error = restore_original_sync(&state);
            if (error != ERROR_SUCCESS ||
                g_replay_test_max_count > WAR3_NATIVE_SELECTION_LIMIT) {
                return 0x300000u |
                    (state.diagnostic_step << 12u) |
                    (failure_mode << 8u) |
                    (failure_step << 4u) |
                    (error & 0xfu);
            }
            error = snapshot_unit_set(state.sync_set, &restored);
            if (error != ERROR_SUCCESS ||
                !unit_set_snapshots_equal(
                    &restored,
                    &state.original_sync
                ) ||
                validate_order_replay_unchanged(&state) != ERROR_SUCCESS) {
                return 0x40000u |
                    (failure_mode << 12u) |
                    (failure_step << 4u) |
                    (error & 0xfu);
            }
        }
    }
    g_replay_test_watch_set = NULL;
    return ERROR_SUCCESS;
}

static volatile LONG g_observer_test_calls = 0;
static void *g_observer_test_unit = NULL;
static void *g_observer_test_order = NULL;
static uint16_t g_observer_test_flags = 0u;
static uint8_t g_observer_test_auxiliary = 0u;

static void __fastcall observer_test_dispatch(
    void *unit,
    void *order,
    uint16_t flags,
    uint8_t auxiliary
) {
    g_observer_test_unit = unit;
    g_observer_test_order = order;
    g_observer_test_flags = flags;
    g_observer_test_auxiliary = auxiliary;
    InterlockedIncrement(&g_observer_test_calls);
}

static DWORD self_test_order_observer(void) {
    static const struct {
        uintptr_t return_rva;
        uint8_t r12_value;
        uint8_t r13_value;
        uint8_t dil_value;
        uint8_t expected_single;
    } cases[] = {
        {0x0123fa18u, 1u, 0u, 0u, 1u},
        {0x012418d8u, 0u, 1u, 0u, 1u},
        {0x01242b3du, 0u, 0u, 1u, 1u},
        {0x01242b3du, 1u, 1u, 0u, 0u},
    };
    union {
        UnitOrderDispatchFunction function;
        void *address;
    } test_dispatch;
    void *saved_original;
    LONG saved_patch_state;
    LONG expected_calls = (LONG)ARRAY_COUNT(cases);
    uint16_t expected_flags = 0x1234u;
    uint8_t expected_auxiliary = 0x56u;
    HMODULE module;
    uint32_t index;
    DWORD error;
    test_dispatch.function = observer_test_dispatch;
    saved_original = InterlockedExchangePointer(
        &g_unit_order_dispatch_original,
        test_dispatch.address
    );
    saved_patch_state = InterlockedExchange(
        &g_order_observer_patch_applied,
        1
    );
    InterlockedExchange(&g_order_observer_active, 0);
    InterlockedExchange(&g_observer_test_calls, 0);
    g_observer_test_unit = NULL;
    g_observer_test_order = NULL;
    g_observer_test_flags = 0u;
    g_observer_test_auxiliary = 0u;
    module = GetModuleHandleW(NULL);
    error = module ? ERROR_SUCCESS : ERROR_MOD_NOT_FOUND;
    for (index = 0;
         error == ERROR_SUCCESS && index < ARRAY_COUNT(cases);
         ++index) {
        OrderDispatchObservation observation;
        ZeroMemory(&observation, sizeof(observation));
        error = begin_order_dispatch_observation();
        if (error != ERROR_SUCCESS) {
            break;
        }
        War3SelectionObserveUnitOrder(
            (void *)(uintptr_t)0x1000u,
            (void *)(uintptr_t)0x2000u,
            0x1234u,
            0x56u,
            (uintptr_t)module + cases[index].return_rva,
            cases[index].r12_value,
            cases[index].r13_value,
            cases[index].dil_value
        );
        error = end_order_dispatch_observation(&observation);
        if (error == ERROR_SUCCESS &&
            (observation.count != 1u ||
             observation.flags != 0x1234u ||
             observation.single_recipient !=
                cases[index].expected_single)) {
            error = ERROR_INVALID_DATA;
        }
    }
#if WAR3_EARLY_IMAGE_PATCH_ENABLED
    if (error == ERROR_SUCCESS) {
        OrderDispatchObservation observation;
        DWORD end_error;
        ZeroMemory(&observation, sizeof(observation));
        g_order_observer_test_r12 = 0u;
        g_order_observer_test_r13 = 0u;
        g_order_observer_test_dil = 0u;
        InterlockedExchange(&g_order_observer_test_mode, 1);
        error = begin_order_dispatch_observation();
        if (error == ERROR_SUCCESS) {
            OrderDispatchObserverThunkSelfTest();
            end_error = end_order_dispatch_observation(&observation);
            if (end_error != ERROR_REVISION_MISMATCH ||
                observation.count != 1u ||
                observation.flags != 0x4321u ||
                g_order_observer_test_r12 != 0x12u ||
                g_order_observer_test_r13 != 0x13u ||
                g_order_observer_test_dil != 0x14u) {
                error = ERROR_INVALID_DATA;
            }
        }
        InterlockedExchange(&g_order_observer_test_mode, 0);
        ++expected_calls;
        expected_flags = 0x4321u;
        expected_auxiliary = 0x65u;
    }
#endif
    if (error == ERROR_SUCCESS &&
        (InterlockedCompareExchange(&g_observer_test_calls, 0, 0) !=
            expected_calls ||
         g_observer_test_unit != (void *)(uintptr_t)0x1000u ||
         g_observer_test_order != (void *)(uintptr_t)0x2000u ||
         g_observer_test_flags != expected_flags ||
         g_observer_test_auxiliary != expected_auxiliary)) {
        error = ERROR_INVALID_DATA;
    }
    InterlockedExchange(&g_order_observer_active, 0);
    g_order_observer_thread_id = 0;
    InterlockedExchangePointer(
        &g_unit_order_dispatch_original,
        saved_original
    );
    InterlockedExchange(
        &g_order_observer_patch_applied,
        saved_patch_state
    );
    return error;
}

static volatile LONG g_hardware_observer_test_calls = 0;

__declspec(noinline) static void __fastcall
hardware_observer_test_dispatch(
    void *unit,
    void *order,
    uint16_t flags,
    uint8_t auxiliary
) {
    (void)unit;
    (void)order;
    (void)flags;
    (void)auxiliary;
    InterlockedIncrement(&g_hardware_observer_test_calls);
}

static DWORD self_test_hardware_order_observer(void) {
#if WAR3_PERSISTENT_SELECTION_BREAKPOINTS_ENABLED
    OrderDispatchObservation observation;
    UnitOrderDispatchFunction volatile dispatch =
        hardware_observer_test_dispatch;
    BYTE *saved_dispatch_breakpoint = g_order_dispatch_breakpoint;
    size_t saved_dispatch_return_stack_offset =
        g_order_dispatch_return_stack_offset;
    PVOID saved_exception_handler = g_exception_handler;
    DWORD saved_window_thread_id = g_window_thread_id;
    LONG saved_addresses_valid = g_addresses_valid;
    LONG saved_enabled = g_enabled;
    LONG saved_patch_state = InterlockedExchange(
        &g_order_observer_patch_applied,
        1
    );
    DWORD error;
    int created_handler = 0;
    int created_worker = 0;

    ZeroMemory(&observation, sizeof(observation));
    g_order_dispatch_breakpoint =
        (BYTE *)(uintptr_t)hardware_observer_test_dispatch;
    g_order_dispatch_return_stack_offset = 0u;
    g_window_thread_id = GetCurrentThreadId();
    g_addresses_valid = 1;
    g_enabled = 1;
    InterlockedExchange(&g_hardware_observer_test_calls, 0);
    InterlockedExchange(&g_order_observer_active, 0);
    InterlockedExchange(&g_order_observer_breakpoint_active, 0);

    if (!g_exception_handler) {
        g_exception_handler = AddVectoredExceptionHandler(
            1u,
            selection_exception_handler
        );
        if (!g_exception_handler) {
            error = GetLastError();
            goto cleanup;
        }
        created_handler = 1;
    }
    if (!g_selection_thread) {
        error = start_selection_worker();
        if (error != ERROR_SUCCESS) {
            goto cleanup;
        }
        created_worker = 1;
    }

    error = begin_order_dispatch_observation();
    if (error != ERROR_SUCCESS) {
        error = 0x81000000u | error;
        goto cleanup;
    }
    dispatch(
        (void *)(uintptr_t)0x1000u,
        (void *)(uintptr_t)0x2000u,
        0x5a5au,
        0xa5u
    );
    error = end_order_dispatch_observation(&observation);
    if (error != ERROR_SUCCESS) {
        error = 0x82000000u | error;
    } else if (!observation.invalid_return ||
               !observation.invalid_return_rva) {
        error = 0x82010000u;
    } else if (observation.count != 1u) {
        error = 0x83000000u | observation.count;
    } else if (observation.flags != 0x5a5au) {
        error = 0x84000000u | observation.flags;
    } else if (InterlockedCompareExchange(
            &g_hardware_observer_test_calls,
            0,
            0
        ) != 1) {
        error = 0x85000000u | (uint32_t)InterlockedCompareExchange(
            &g_hardware_observer_test_calls,
            0,
            0
        );
    } else if (InterlockedCompareExchange(
            &g_order_observer_breakpoint_active,
            0,
            0
        )) {
        error = 0x86000000u;
    } else {
        error = ERROR_SUCCESS;
    }

cleanup:
    if (InterlockedCompareExchange(
            &g_order_observer_breakpoint_active,
            0,
            0
        )) {
        OrderDispatchObservation discarded;
        ZeroMemory(&discarded, sizeof(discarded));
        end_order_dispatch_observation(&discarded);
    }
    InterlockedExchange(&g_order_observer_active, 0);
    InterlockedExchange(&g_order_observer_breakpoint_active, 0);
    g_order_observer_thread_id = 0u;
    g_order_observer_saved_dr3 = 0u;
    g_order_observer_saved_dr7 = 0u;
    if (created_handler && g_exception_handler) {
        RemoveVectoredExceptionHandler(g_exception_handler);
    }
    if (created_worker) {
        stop_selection_worker();
    }
    g_exception_handler = saved_exception_handler;
    g_order_dispatch_breakpoint = saved_dispatch_breakpoint;
    g_order_dispatch_return_stack_offset =
        saved_dispatch_return_stack_offset;
    g_window_thread_id = saved_window_thread_id;
    g_addresses_valid = saved_addresses_valid;
    g_enabled = saved_enabled;
    InterlockedExchange(
        &g_order_observer_patch_applied,
        saved_patch_state
    );
    return error;
#else
    return ERROR_NOT_SUPPORTED;
#endif
}

static DWORD self_test_order_emulation(void) {
    BYTE *buffer;
    uint32_t index;
    DWORD error = ERROR_SUCCESS;
    buffer = (BYTE *)VirtualAlloc(
        NULL,
        0x4000u,
        MEM_COMMIT | MEM_RESERVE,
        PAGE_READWRITE
    );
    if (!buffer) {
        return GetLastError();
    }
    for (index = 0; index < WAR3_ORDER_HANDLER_COUNT; ++index) {
        const OrderHandlerSpec *spec = &ORDER_SPECS[index];
        OrderHandlerRuntime *runtime = &g_order_handlers[index];
        OrderThreadState state;
        CONTEXT context;
        uintptr_t stack_before = (uintptr_t)buffer + 0x3000u;
        uintptr_t rbp_before = stack_before - (spec->old_frame_size - 0x100u);
        uintptr_t expected_rsp = stack_before - spec->new_frame_size;
        uintptr_t expected_rbp = expected_rsp + 0x100u;
        uint32_t delta = spec->new_frame_size - spec->old_frame_size;
        uint64_t cookie = 0x1122334455667788ull + index;
        ZeroMemory(&state, sizeof(state));
        ZeroMemory(&context, sizeof(context));
        ZeroMemory(runtime, sizeof(*runtime));
        runtime->stack_allocation = (BYTE *)(uintptr_t)0x1000u;
        runtime->cookie_store = (BYTE *)(uintptr_t)0x1010u;
        runtime->array_size = (BYTE *)(uintptr_t)0x1020u;
        runtime->cookie_load = (BYTE *)(uintptr_t)0x1030u;
        runtime->epilogue = (BYTE *)(uintptr_t)0x1040u;
        runtime->return_instruction = (BYTE *)(uintptr_t)0x1050u;
        if (spec->instant_offset) {
            runtime->instant_store = (BYTE *)(uintptr_t)0x1060u;
            runtime->instant_load = (BYTE *)(uintptr_t)0x1070u;
        }
        state.order_index = index;
        state.order_active = 1u;
        context.Rsp = stack_before;
        context.Rbp = rbp_before;
        if (!handle_order_breakpoint(
                &context,
                &state,
                (uintptr_t)runtime->stack_allocation,
                0u) ||
            context.Rsp != expected_rsp ||
            context.Rbp != expected_rbp ||
            !state.stack_expanded) {
            error = ERROR_INVALID_DATA;
            break;
        }
        context.Rax = cookie;
        if (!handle_order_breakpoint(
                &context,
                &state,
                (uintptr_t)runtime->cookie_store,
                1u) ||
            *(uint64_t *)(expected_rbp + spec->cookie_offset + delta) != cookie) {
            error = ERROR_INVALID_DATA;
            break;
        }
        context.R8 = 0u;
        if (!handle_order_breakpoint(
                &context,
                &state,
                (uintptr_t)runtime->array_size,
                2u) ||
            context.R8 != spec->new_array_size) {
            error = ERROR_INVALID_DATA;
            break;
        }
        if (spec->instant_offset) {
            uint64_t instant = 0x8877665544332211ull + index;
            context.R12 = instant;
            if (!handle_order_breakpoint(
                    &context,
                    &state,
                    (uintptr_t)runtime->instant_store,
                    0u) ||
                *(uint64_t *)(expected_rbp + spec->instant_offset + delta) != instant) {
                error = ERROR_INVALID_DATA;
                break;
            }
            context.Rax = 0u;
            if (!handle_order_breakpoint(
                    &context,
                    &state,
                    (uintptr_t)runtime->instant_load,
                    0u) ||
                context.Rax != instant) {
                error = ERROR_INVALID_DATA;
                break;
            }
        }
        context.Rcx = 0u;
        if (!handle_order_breakpoint(
                &context,
                &state,
                (uintptr_t)runtime->cookie_load,
                spec->instant_offset ? 1u : 0u) ||
            context.Rcx != cookie) {
            error = ERROR_INVALID_DATA;
            break;
        }
        if (!handle_order_breakpoint(
                &context,
                &state,
                (uintptr_t)runtime->epilogue,
                0u) ||
            context.R11 != stack_before ||
            context.Dr0 != (DWORD64)(uintptr_t)runtime->return_instruction) {
            error = ERROR_INVALID_DATA;
            break;
        }
        if (!handle_order_breakpoint(
                &context,
                &state,
                (uintptr_t)runtime->return_instruction,
                0u) ||
            !state.return_single_step ||
            !(context.EFlags & EFLAGS_TRAP) ||
            !(context.EFlags & EFLAGS_RESUME)) {
            error = ERROR_INVALID_DATA;
            break;
        }
    }
    ZeroMemory(g_order_handlers, sizeof(g_order_handlers));
    VirtualFree(buffer, 0, MEM_RELEASE);
    return error;
}

__declspec(dllexport) DWORD WINAPI War3SelectionLimitSelfTest(uint32_t scenario) {
    BYTE *buffer;
    size_t offsets[WAR3_SELECTION_PATCH_COUNT];
    size_t buffer_size = 0x4000;
    size_t cursor = 0x100;
    uint32_t index;
    uint32_t failed = UINT32_MAX;
    uint32_t state = WAR3_SELECTION_STATE_UNKNOWN;
    DWORD error = ERROR_SUCCESS;

    if (scenario == 3u) {
        return self_test_order_emulation();
    }
    if (scenario == 5u) {
        return self_test_order_replay();
    }
    if (scenario == 6u) {
        return self_test_order_observer();
    }
    if (scenario == 7u) {
        int expect_disabled;
        int expect_enabled;
#if WAR3_DIRECT_SELECTION_PATCHES_ENABLED || \
    WAR3_PERSISTENT_SELECTION_BREAKPOINTS_ENABLED
        expect_disabled = 1;
#if WAR3_EARLY_IMAGE_PATCH_ENABLED
        expect_enabled = 1;
#else
        expect_enabled = 0;
#endif
#else
        expect_disabled = 0;
        expect_enabled = 1;
#endif
        if (enable_action_accepts_state(WAR3_SELECTION_STATE_DISABLED) !=
                expect_disabled ||
            enable_action_accepts_state(WAR3_SELECTION_STATE_ENABLED) !=
                expect_enabled ||
            enable_action_accepts_state(WAR3_SELECTION_STATE_UNKNOWN)) {
            return ERROR_INVALID_DATA;
        }
#if WAR3_DIRECT_SELECTION_PATCHES_ENABLED
        if (!enable_action_needs_selection_patches(
                WAR3_SELECTION_STATE_DISABLED
            ) ||
            enable_action_needs_selection_patches(
                WAR3_SELECTION_STATE_ENABLED
            )) {
            return ERROR_INVALID_DATA;
        }
#endif
        return ERROR_SUCCESS;
    }
    if (scenario == 8u) {
        return self_test_hardware_order_observer();
    }
    buffer = (BYTE *)VirtualAlloc(NULL, buffer_size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!buffer) {
        return GetLastError();
    }
    memset(buffer, 0xcc, buffer_size);
    for (index = 0; index < WAR3_SELECTION_PATCH_COUNT; ++index) {
        size_t byte_index;
        offsets[index] = cursor;
        for (byte_index = 0; byte_index < PATCHES[index].signature_size; ++byte_index) {
            uint16_t value = PATCHES[index].signature[byte_index];
            buffer[cursor + byte_index] = value == WAR3_SELECTION_ANY ? 0x5a : (BYTE)value;
        }
        memcpy(
            buffer + cursor + PATCHES[index].patch_offset,
            &PATCHES[index].original_value,
            PATCHES[index].value_size
        );
        cursor += PATCHES[index].signature_size + 0x40;
    }
    if (scenario == 1u) {
        memcpy(buffer + cursor, buffer + offsets[0], PATCHES[0].signature_size);
    } else if (scenario == 2u) {
        buffer[offsets[4] + PATCHES[4].patch_offset] = 0x7f;
    }

    error = resolve_patches_in_range(buffer, buffer_size, &failed);
    if (scenario == 1u) {
        error = error == ERROR_DUP_NAME && failed == 0u ? ERROR_SUCCESS : ERROR_INVALID_DATA;
        goto cleanup;
    }
    if (error != ERROR_SUCCESS) {
        goto cleanup;
    }
    error = classify_state(&state, &failed);
    if (scenario == 2u) {
        error = error == ERROR_INVALID_DATA && failed == 4u ? ERROR_SUCCESS : ERROR_INVALID_DATA;
        goto cleanup;
    }
    if (error != ERROR_SUCCESS || state != WAR3_SELECTION_STATE_DISABLED) {
        error = ERROR_INVALID_STATE;
        goto cleanup;
    }
    if (scenario == 4u) {
        error = apply_selection_patches(1, &failed);
        if (error != ERROR_SUCCESS) {
            goto cleanup;
        }
        error = classify_state(&state, &failed);
        if (error != ERROR_SUCCESS || state != WAR3_SELECTION_STATE_ENABLED) {
            error = ERROR_INVALID_STATE;
            goto cleanup;
        }
        error = apply_selection_patches(0, &failed);
        if (error != ERROR_SUCCESS) {
            goto cleanup;
        }
        error = classify_state(&state, &failed);
        if (error != ERROR_SUCCESS || state != WAR3_SELECTION_STATE_DISABLED) {
            error = ERROR_INVALID_STATE;
        }
        goto cleanup;
    }
    if (scenario == 0u) {
        CONTEXT context;
        ZeroMemory(&context, sizeof(context));
        context.EFlags = 0x202u;
        context.Rip = 0x1000u;
        emulate_cmp32(&context, 12u, 24u, 3u);
        if ((context.EFlags & 0x1u) == 0 || context.Rip != 0x1003u) {
            error = ERROR_INVALID_DATA;
        }
    }

cleanup:
    g_addresses_valid = 0;
    ZeroMemory(g_patch_addresses, sizeof(g_patch_addresses));
    VirtualFree(buffer, 0, MEM_RELEASE);
    return error;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    if (reason == DLL_PROCESS_ATTACH) {
        g_module = instance;
        DisableThreadLibraryCalls(instance);
#if WAR3_EARLY_IMAGE_PATCH_ENABLED
        g_auto_enable_error = War3EarlyImagePatchInstall(
            War3SelectionApplyEarlyImagePatches
        );
#endif
#if WAR3_CRASH_TRACE_ENABLED
        if (open_crash_trace() == ERROR_SUCCESS && !g_exception_handler) {
            g_exception_handler = AddVectoredExceptionHandler(
                1,
                selection_exception_handler
            );
        }
#endif
#if WAR3_AUTO_ENABLE_ON_LOAD
        War3SelectionAutoBootstrap();
#endif
#if WAR3_CRASH_TRACE_ENABLED
    } else if (reason == DLL_PROCESS_DETACH && g_crash_trace) {
        InterlockedExchange(&g_crash_trace->process_detach_seen, 1);
#endif
    } else if (reason == DLL_PROCESS_DETACH) {
#if WAR3_EARLY_IMAGE_PATCH_ENABLED
        if (reserved == NULL) {
            War3EarlyImagePatchUninstall();
        }
#else
        (void)reserved;
#endif
    }
    return TRUE;
}
