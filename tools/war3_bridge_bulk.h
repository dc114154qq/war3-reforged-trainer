/* Current-build 24268 batch for global and owner-group elephant operations. */
#define BULK_HEAL_LOCAL 1u
#define BULK_RESET_LOCAL_COOLDOWNS 2u
#define BULK_KILL_SELECTED_OWNER 3u
#define BULK_PEACE_MODE 4u
#define BULK_COMPLETE_LOCAL_STRUCTURES 5u

typedef struct BulkWork {
    SelectionWork selection;
    uint64_t (*get_local_player)(void);
    uint64_t (*create_group)(void);
    void (*enum_units_of_player)(uint64_t,uint64_t,uint64_t);
    uint64_t (*first_of_group)(uint64_t);
    uint8_t (*remove_from_group)(uint64_t,uint64_t);
    void (*destroy_group)(uint64_t);
    uint64_t (*get_owning_player)(uint64_t);
    uint32_t (*get_widget_life)(uint64_t);
    int32_t (*get_unit_max_hp)(uint64_t);
    void (*set_widget_life)(uint64_t,float *);
    void (*reset_cooldown)(uint64_t);
    void (*kill_unit)(uint64_t);
    uint64_t (*player)(int32_t);
    void (*set_player_alliance)(uint64_t,uint64_t,int32_t,uint32_t);
    uint64_t (*convert_unit_type)(int32_t);
    uint8_t (*is_unit_type)(uint64_t,uint64_t);
    void (*set_construction_progress)(uint64_t,int32_t);
    void (*set_upgrade_progress)(uint64_t,int32_t);
    void *expected_tls;
    uint32_t action,value,changed,error,completed,reserved;
} BulkWork;
_Static_assert(sizeof(BulkWork) == 656, "BulkWork ABI");
__declspec(dllexport) const uint32_t bulk_batch_abi[3] = {0x2426803Au,216u,656u};

static uint32_t BridgeBulkGroup(BulkWork *w, uint64_t player, uint32_t *changed) {
    uint64_t group, unit, structure_type = 0;
    uint32_t visited = 0;
    if (!player) return 0;
    if (w->action == BULK_COMPLETE_LOCAL_STRUCTURES) {
        structure_type = w->convert_unit_type(2);
        if (!structure_type) return 0;
    }
    group = w->create_group();
    if (!group) return 0;
    __try {
        w->enum_units_of_player(group, player, 0);
        while ((unit = w->first_of_group(group)) != 0) {
            if (++visited > 100000u || !w->remove_from_group(group, unit)) return 0;
            if (w->action == BULK_HEAL_LOCAL) {
                int32_t maximum = w->get_unit_max_hp(unit);
                float hp;
                if (maximum < 0 || maximum > 1000000000) return 0;
                hp = (float)maximum;
                w->set_widget_life(unit, &hp);
            } else if (w->action == BULK_RESET_LOCAL_COOLDOWNS) {
                w->reset_cooldown(unit);
            } else if (w->action == BULK_KILL_SELECTED_OWNER) {
                w->kill_unit(unit);
            } else if (w->is_unit_type(unit, structure_type)) {
                w->set_construction_progress(unit, 100);
                w->set_upgrade_progress(unit, 100);
            } else {
                continue;
            }
            ++*changed;
        }
    } __finally {
        w->destroy_group(group);
    }
    return 1;
}

__declspec(dllexport) uint64_t BridgeBulkQuery(void) {
    BulkWork *w = (BulkWork *)g_dispatch->work;
    uint64_t player = 0;
    uint32_t changed = 0;
    if (!w || w->expected_tls != g_dispatch->tls_value || w->action < BULK_HEAL_LOCAL ||
        w->action > BULK_COMPLETE_LOCAL_STRUCTURES || w->value > 1 || !w->create_group ||
        !w->enum_units_of_player || !w->first_of_group || !w->remove_from_group ||
        !w->destroy_group || !w->get_local_player || !w->player || !w->set_player_alliance ||
        !w->convert_unit_type || !w->is_unit_type || !w->set_construction_progress ||
        !w->set_upgrade_progress) {
        if (w) w->error = 140;
        return 0;
    }
    __try {
        if (w->action == BULK_PEACE_MODE) {
            int32_t source_id, other_id;
            for (source_id = 0; source_id < 24; ++source_id) {
                uint64_t source = w->player(source_id);
                if (!source) continue;
                for (other_id = 0; other_id < 24; ++other_id) {
                    uint64_t other;
                    if (source_id == other_id || !(other = w->player(other_id))) continue;
                    w->set_player_alliance(source, other, 0, w->value ? 1u : 0u);
                    ++changed;
                }
            }
        } else if (w->action == BULK_KILL_SELECTED_OWNER) {
            uint32_t count = (uint32_t)BridgeSelect();
            if (!count || w->selection.error || !w->selection.destroyed || !w->selection.count) {
                w->error = 141; return count;
            }
            player = w->get_owning_player(w->selection.rows[0].unit);
            if (!BridgeBulkGroup(w, player, &changed)) { w->error = 142; return count; }
        } else {
            player = w->get_local_player();
            if (!BridgeBulkGroup(w, player, &changed)) { w->error = 143; return 0; }
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        w->error = GetExceptionCode();
        return 0;
    }
    if (!changed && w->action != BULK_COMPLETE_LOCAL_STRUCTURES) { w->error = 144; return 0; }
    w->changed = changed;
    w->completed = 1;
    return changed ? changed : 1u;
}
