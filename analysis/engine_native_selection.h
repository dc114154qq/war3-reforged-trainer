/* Current-engine selection query. Included after ProbeHookCommand/g_dispatch. */
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

__declspec(dllexport) uint64_t ProbeSelectionQuery(void) {
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
