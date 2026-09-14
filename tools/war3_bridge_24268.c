#include <windows.h>
#include <stdint.h>

typedef struct BridgeCommand {
    HWND window;
    HHOOK (WINAPI *set_hook)(int, HOOKPROC, HINSTANCE, DWORD);
    BOOL (WINAPI *unhook)(HHOOK);
    LRESULT (WINAPI *next_hook)(HHOOK, int, WPARAM, LPARAM);
    DWORD (WINAPI *current_tid)(void);
    DWORD (WINAPI *get_error)(void);
    HHOOK hook;
    DWORD target_tid, message;
    uintptr_t nonce;
    volatile LONG stage;
    DWORD last_error, callback_tid;
    volatile LONG callback_count, detached, active;
    void (WINAPI *sleep_ms)(DWORD);
    volatile LONG stop_requested;
    DWORD hook_kind;
    LPVOID (WINAPI *get_tls)(DWORD);
    BOOLEAN (WINAPI *add_table)(PRUNTIME_FUNCTION,DWORD,DWORD64);
    BOOLEAN (WINAPI *delete_table)(PRUNTIME_FUNCTION);
    PRUNTIME_FUNCTION unwind_table;
    DWORD64 image_base;
    uint64_t (*query)(void);
    uint64_t query_result;
    LPVOID tls_value;
    void *specific_handler;
    DWORD unwind_count, tls_index, query_stage, exception_code, unwind_registered, unwind_removed;
    void *work;
} BridgeCommand;
_Static_assert(sizeof(BridgeCommand) == 216, "BridgeCommand ABI");
static BridgeCommand *g_dispatch;
typedef EXCEPTION_DISPOSITION (*BridgeHandler)(PEXCEPTION_RECORD,void *,PCONTEXT,PDISPATCHER_CONTEXT);
EXCEPTION_DISPOSITION BridgeSpecificHandler(PEXCEPTION_RECORD e,void *f,PCONTEXT c,PDISPATCHER_CONTEXT d) {
    return ((BridgeHandler)g_dispatch->specific_handler)(e,f,c,d);
}
static LRESULT CALLBACK BridgeCallback(int code, WPARAM w, LPARAM l) {
    BridgeCommand *cmd = g_dispatch;
    LRESULT result;
    if (!cmd) return 0;
    InterlockedIncrement(&cmd->active);
    if (code >= 0 && l) {
        HWND hwnd;
        UINT message;
        WPARAM nonce;
        if (cmd->hook_kind == WH_GETMESSAGE) {
            const MSG *msg=(const MSG *)l;
            hwnd=msg->hwnd;message=msg->message;nonce=msg->wParam;
        } else {
            const CWPSTRUCT *msg=(const CWPSTRUCT *)l;
            hwnd=msg->hwnd;message=msg->message;nonce=msg->wParam;
        }
        if (hwnd == cmd->window && message == cmd->message && nonce == cmd->nonce &&
            cmd->stage == 2 && (cmd->hook_kind != WH_GETMESSAGE || w == PM_REMOVE)) {
            cmd->callback_tid = cmd->current_tid();
            InterlockedIncrement(&cmd->callback_count);
            __try {
                cmd->tls_value = cmd->get_tls(cmd->tls_index);
                if (cmd->query) {
                    cmd->query_stage = 1;
                    cmd->query_result = cmd->query();
                    cmd->query_stage = 2;
                }
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                cmd->exception_code = GetExceptionCode();
                cmd->query_stage = 3;
            }
            cmd->detached = cmd->unhook(cmd->hook);
            if (!cmd->detached) cmd->last_error = cmd->get_error();
            cmd->stage = 3;
        }
    }
    result = cmd->next_hook(NULL, code, w, l);
    InterlockedDecrement(&cmd->active);
    return result;
}

__declspec(dllexport) DWORD WINAPI BridgeInstall(BridgeCommand *cmd) {
    cmd->stage = 1;
    g_dispatch = cmd;
    cmd->unwind_registered = cmd->add_table(cmd->unwind_table, cmd->unwind_count, cmd->image_base);
    if (!cmd->unwind_registered) { cmd->last_error = cmd->get_error(); cmd->stage = 2; return 0; }
    cmd->hook = cmd->set_hook(cmd->hook_kind == WH_GETMESSAGE ? WH_GETMESSAGE : WH_CALLWNDPROC, BridgeCallback, NULL, cmd->target_tid);
    if (!cmd->hook) cmd->last_error = cmd->get_error();
    cmd->stage = 2;
    /* Hooks belong to the installing thread; keep it alive through dispatch. */
    if (cmd->hook) {
        while (!cmd->stop_requested) cmd->sleep_ms(1);
        if (!cmd->detached) {
            cmd->detached = cmd->unhook(cmd->hook);
            if (!cmd->detached) cmd->last_error = cmd->get_error();
        }
    }
    if ((!cmd->hook || cmd->detached) && !cmd->active)
        cmd->unwind_removed = cmd->delete_table(cmd->unwind_table);
    return 0;
}

__declspec(dllexport) DWORD WINAPI BridgeUninstall(BridgeCommand *cmd) {
    if (cmd->hook && !cmd->detached) {
        cmd->detached = cmd->unhook(cmd->hook);
        if (!cmd->detached) cmd->last_error = cmd->get_error();
    }
    return 0;
}

/* Current-engine selection query. Included after BridgeCommand/g_dispatch. */
typedef struct SelectionRow { uint64_t unit; uint32_t rawcode; int32_t level; } SelectionRow;
typedef struct SelectionWork {
    uint64_t (*local_player)(void);
    uint64_t (*create_group)(void);
    void (*enum_selected)(uint64_t,uint64_t,uint64_t);
    uint64_t (*first_of_group)(uint64_t);
    void (*remove_from_group)(uint64_t,uint64_t);
    void (*destroy_group)(uint64_t);
    uint32_t (*unit_type_id)(uint64_t);
    int32_t (*hero_level)(uint64_t);
    uint64_t player, temporary_group;
    uint32_t count, error, destroyed, reserved;
    SelectionRow rows[24];
} SelectionWork;
_Static_assert(sizeof(SelectionWork) == 480, "SelectionWork ABI");

__declspec(dllexport) const uint32_t probe_selection_abi[3] = {0x24268003u, 216u, 480u};

__declspec(dllexport) uint64_t BridgeSelect(void) {
    SelectionWork *work = (SelectionWork *)g_dispatch->work;
    int32_t index, prior;
    uint64_t group, unit;
    if (!work) return 0;
    work->count = 0;
    if (!work->local_player || !work->create_group || !work->enum_selected ||
        !work->first_of_group || !work->remove_from_group || !work->destroy_group ||
        !work->unit_type_id || !work->hero_level) { work->error = 5; return 0; }
    work->player = work->local_player();
    group = work->create_group();
    work->temporary_group = group;
    if (!group) { work->error = 1; return 0; }
    __try {
        work->enum_selected(group, work->player, 0);
        for (index = 0; index <= 24; ++index) {
            unit = work->first_of_group(group);
            if (!unit) break;
            if (index == 24) { work->error = 2; return 0; }
            SelectionRow *row = &work->rows[index];
            row->unit = unit;
            for (prior = 0; prior < index; ++prior)
                if (work->rows[prior].unit == row->unit) { work->error = 4; return 0; }
            row->rawcode = work->unit_type_id(row->unit);
            row->level = work->hero_level(row->unit);
            work->remove_from_group(group, unit);
        }
        work->count = (uint32_t)index;
        return (uint64_t)index;
    } __finally {
        work->destroy_group(group);
        work->destroyed = 1;
    }
}

typedef struct HeroWork {
    SelectionWork selection;
    void (*set_level)(uint64_t,int32_t,uint32_t);
    void *expected_tls;
    uint32_t target,changed,error,reserved;
    int32_t after[24];
} HeroWork;
_Static_assert(sizeof(HeroWork)==608,"HeroWork ABI");
__declspec(dllexport) const uint32_t bridge_abi[3]={0x24268010u,216u,608u};
__declspec(dllexport) uint64_t BridgeHeroQuery(void) {
    HeroWork *w=(HeroWork *)g_dispatch->work;
    uint32_t i,heroes=0;
    uint64_t count;
    if (!w) return 0;
    if (g_dispatch->tls_value!=w->expected_tls || !w->set_level || w->target>100000) {
        w->error=10;return 0;
    }
    count=BridgeSelect();
    if (w->selection.error || !w->selection.destroyed || count!=w->selection.count) {
        w->error=11;return count;
    }
    /* Validate all hero rows before the first write. Nonheroes are untouched. */
    for (i=0;i<count;++i) {
        SelectionRow *row=&w->selection.rows[i];
        if (row->level<=0) continue;
        ++heroes;
        if (w->selection.unit_type_id(row->unit)!=row->rawcode ||
            w->selection.hero_level(row->unit)!=row->level) {w->error=12;return count;}
    }
    if (!heroes) {w->error=13;return count;}
    for (i=0;i<count;++i) {
        SelectionRow *row=&w->selection.rows[i];
        if (row->level<=0) continue;
        if (w->selection.unit_type_id(row->unit)!=row->rawcode ||
            w->selection.hero_level(row->unit)!=row->level) {w->error=14;return count;}
        if (w->target && row->level!=(int32_t)w->target) {
            w->set_level(row->unit,(int32_t)w->target,0);
            ++w->changed;
        }
        w->after[i]=w->selection.hero_level(row->unit);
        if (w->after[i]!=(w->target ? (int32_t)w->target : row->level)) {w->error=15;return count;}
    }
    return count;
}
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID reserved) {
    (void)module;(void)reason;(void)reserved;return TRUE;
}
#include "war3_bridge_ability.h"
#ifdef BRIDGE_TEST
#include "war3_bridge_test_fixture.h"
#endif
