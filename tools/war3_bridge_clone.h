/* Current-build clone transaction. A non-keep run removes every created object. */
#define CLONE_KEEP 0x01u
#define CLONE_PRESERVE_OWNER 0x02u
#define CLONE_COPY_ABILITIES 0x04u
#define CLONE_COPY_ITEMS 0x08u
#define CLONE_USE_SPAWN 0x10u
#define CLONE_MAX_ITEM_ABILITIES (6u * 128u)

typedef struct CloneRow {
    uint64_t clone;
    uint64_t owner;
    uint32_t rawcode;
    int32_t level;
    uint32_t ability_count;
    uint32_t item_count;
    uint32_t status;
    uint32_t reserved;
    uint32_t created_items;
    uint32_t pad;
} CloneRow;
_Static_assert(sizeof(CloneRow) == 48, "CloneRow ABI");

typedef struct CloneWork {
    SelectionWork selection;
    uint64_t (*owner)(uint64_t);
    uint32_t (*type_id)(uint64_t);
    uint32_t (*get_x)(uint64_t), (*get_y)(uint64_t), (*get_facing)(uint64_t);
    uint64_t (*create)(uint64_t, uint32_t, float *, float *, float *);
    void (*set_owner)(uint64_t, uint64_t, uint32_t);
    void (*remove_unit)(uint64_t);
    int32_t (*get_level)(uint64_t);
    void (*set_level)(uint64_t, int32_t, uint32_t);
    int32_t (*get_skill_points)(uint64_t);
    uint8_t (*modify_skill_points)(uint64_t, int32_t);
    uint64_t (*ability_by_index)(uint64_t, int32_t);
    uint32_t (*ability_id)(uint64_t);
    int32_t (*ability_level)(uint64_t, uint32_t);
    uint8_t (*add_ability)(uint64_t, uint32_t);
    int32_t (*set_ability_level)(uint64_t, uint32_t, int32_t);
    uint64_t (*item_ability_by_index)(uint64_t, int32_t);
    uint64_t (*item_in_slot)(uint64_t, int32_t);
    uint32_t (*item_type)(uint64_t);
    int32_t (*item_charges)(uint64_t);
    uint64_t (*add_item)(uint64_t, uint32_t);
    void (*set_item_charges)(uint64_t, int32_t);
    void (*detach_item)(uint64_t, uint64_t);
    void (*remove_item)(uint64_t);
    void *expected_tls;
    uint32_t flags, spawn_x_bits, spawn_y_bits, changed, error, completed, reserved, pad;
    CloneRow rows[24];
    void (*enum_owner)(uint64_t,uint64_t,uint64_t);
    uint8_t (*in_group)(uint64_t,uint64_t);
} CloneWork;
_Static_assert(sizeof(CloneWork) == 1888, "CloneWork ABI");
__declspec(dllexport) const uint32_t clone_batch_abi[3] = {0x24268063u, 216u, 1888u};

typedef struct CloneSourceIdentity {
    uint64_t native, full, object;
    uint32_t rawcode, reserved;
} CloneSourceIdentity;
typedef struct CloneBoundWork {
    CloneWork clone;
    uint64_t base;
    uint64_t (*resolve_unit)(uint64_t);
    uint32_t expected_count, reserved;
    CloneSourceIdentity sources[24];
} CloneBoundWork;
_Static_assert(sizeof(CloneSourceIdentity)==32,"CloneSourceIdentity ABI");
_Static_assert(sizeof(CloneBoundWork)==2680,"CloneBoundWork ABI");
__declspec(dllexport) const uint32_t clone_bound_abi[3]={0x24268064u,216u,2680u};

static int clone_source_matches(CloneBoundWork *bound,uint32_t index,SelectionRow *source) {
    if(!bound)return 1;
    if(index>=bound->expected_count || !bound->base || !bound->resolve_unit)return 0;
    CloneSourceIdentity *expected=&bound->sources[index];
    if(expected->reserved || source->unit!=expected->native || source->rawcode!=expected->rawcode)return 0;
    uint64_t object=bound->resolve_unit(source->unit);
    if(!object || object!=expected->object ||
       *(uint64_t *)(uintptr_t)(object+bridge_profile.object_handle)!=expected->full ||
       *(uint32_t *)(uintptr_t)(object+bridge_profile.object_rawcode)!=expected->rawcode)return 0;
    uint64_t owner=BridgeProfileResolveOwner(bound->base,expected->full,1);
    return owner && *(uint64_t *)(uintptr_t)(owner+bridge_profile.owner_data)==object;
}

static float clone_real(uint32_t bits) {
    union { uint32_t bits; float value; } value;
    value.bits = bits;
    return value.value;
}

static int clone_set_level(CloneWork *w, uint64_t unit, int32_t level) {
    /* Unknown setter exceptions belong to the transaction rollback. A matching
       value alone does not establish that an exception was harmless. */
    w->set_level(unit, level, 0);
    return w->get_level(unit) == level;
}

static int clone_set_ability_level(CloneWork *w, uint64_t unit, uint32_t rawcode, int32_t level) {
    AbilityWork ability = {0};
    ability.set_level = w->set_ability_level;
    ability.get_level = w->ability_level;
    ability.expected_tls = w->expected_tls;
    ability.rawcode = rawcode;
    return BridgeSetAbilityLevelChecked(&ability, unit, level) == level;
}

static int clone_is_essential_ability(uint32_t rawcode) {
    static const uint32_t essential[] = {
        0x416d6f76u, /* Amov */
        0x4161746bu, /* Aatk */
        0x41496e76u, /* AInv */
        0x41486572u, /* AHer */
        0x416c6f63u, /* Aloc */
        0x41747267u, /* Atrg, 3.0 engine-owned target component */
        0x42686561u, /* Bhea, 3.0 engine-owned component */
    };
    for (uint32_t index = 0; index < sizeof(essential) / sizeof(essential[0]); ++index)
        if (rawcode == essential[index]) return 1;
    return 0;
}

static int clone_is_noncopyable_ability(uint32_t rawcode) {
    /* 3.0 exposes engine buff objects (for example BNht) through the unit
       ability enumerator, but BlzUnitAddAbility cannot add them to a unit. */
    if (clone_is_essential_ability(rawcode)) return 1;
    return (rawcode >> 24) == (uint32_t)'B';
}

static int clone_has_ability(CloneWork *w, uint64_t unit, uint32_t rawcode) {
    for (int32_t index = 0; index < 128; ++index) {
        uint64_t ability = w->ability_by_index(unit, index);
        if (!ability) return 0;
        if (w->ability_id(ability) == rawcode) return 1;
    }
    return 0;
}

static int clone_is_item_ability(const uint32_t *item_abilities,
                                 uint32_t item_ability_count,
                                 uint32_t rawcode) {
    uint32_t index;
    for (index = 0; index < item_ability_count; ++index)
        if (item_abilities[index] == rawcode) return 1;
    return 0;
}

/* Keep engine calls out of an outlined __finally funclet. The same sequence
   runs in the local diagnostic control; preserve the first failure even when
   the temporary group's destruction also fails. */
__declspec(noinline) static int clone_removed_from_world(CloneWork *w,CloneRow *row) {
    uint64_t group=0;int absent=0;uint32_t error=0;BridgeFault first_fault={0};
    __try {
        group=w->selection.create_group();
        if(group){
            w->enum_owner(group,row->owner,0);
            absent=!w->in_group(row->clone,group);
        }
    } __except(BridgeExceptionFilter(GetExceptionInformation())) {
        error=GetExceptionCode();first_fault=bridge_fault;
    }
    if(group){
        __try {w->selection.destroy_group(group);}
        __except(BridgeExceptionFilter(GetExceptionInformation())) {
            if(!error){error=GetExceptionCode();first_fault=bridge_fault;}
        }
    }
    if(error){row->pad=error;bridge_fault=first_fault;}
    return group && !error && absent;
}

/* A removed unit may retain its native type while referenced. Verify world
   removal separately; a pending removal must never be reported as completed. */
static int clone_discard_row(CloneWork *w, CloneRow *row, uint64_t *items) {
    int cleaned = 1;
    for (uint32_t i = 0; i < row->created_items; ++i) {
        if (!items[i]) continue;
        __try {
            if (w->item_type(items[i])) {
                if (row->clone && w->type_id(row->clone))
                    w->detach_item(row->clone, items[i]);
                w->remove_item(items[i]);
                if (w->item_type(items[i])) cleaned = 0;
            }
        } __except(BridgeExceptionFilter(GetExceptionInformation())) {
            cleaned=0;if(!row->pad)row->pad=GetExceptionCode();
        }
    }
    if (row->clone) {
        __try {
            w->remove_unit(row->clone);
            if(!clone_removed_from_world(w,row))cleaned=0;
        } __except(BridgeExceptionFilter(GetExceptionInformation())) {
            cleaned=0;if(!row->pad)row->pad=GetExceptionCode();
        }
        row->status = cleaned ? 2 : 3;
    }
    return cleaned;
}

/* Bound the large skill snapshot to its own stack frame. The bridge has no
   CRT stack-probe dependency, and the transaction frame stays below one page. */
static void clone_copy_abilities(CloneWork *w, uint64_t source, CloneRow *row) {
    uint32_t source_item_abilities[CLONE_MAX_ITEM_ABILITIES] = {0};
    uint32_t source_item_ability_count = 0;
    uint64_t clone = row->clone;
    for (uint32_t slot = 0; slot < 6 && !w->error; ++slot) {
        uint64_t source_item = w->item_in_slot(source, (int32_t)slot);
        if (!source_item) continue;
        uint32_t item_index;
        for (item_index = 0; item_index < 128u; ++item_index) {
            uint64_t item_ability = w->item_ability_by_index(source_item, (int32_t)item_index);
            if (!item_ability) break;
            uint32_t rawcode = w->ability_id(item_ability);
            if (!rawcode || source_item_ability_count >= CLONE_MAX_ITEM_ABILITIES) {
                w->error = 70; break;
            }
            if (!clone_is_item_ability(source_item_abilities, source_item_ability_count, rawcode))
                source_item_abilities[source_item_ability_count++] = rawcode;
        }
        if (!w->error && item_index == 128u && w->item_ability_by_index(source_item, 128))
            w->error = 75;
    }
    uint32_t index;
    for (index = 0; index < 128 && !w->error; ++index) {
        uint64_t ability = w->ability_by_index(source, (int32_t)index);
        if (!ability) break;
        uint32_t rawcode = w->ability_id(ability);
        row->reserved = rawcode;
        if (!rawcode) { w->error = 65; break; }
        /* Engine components/item effects are not learned abilities.
           Filter them BEFORE asking for a positive skill level. */
        if (clone_is_item_ability(source_item_abilities, source_item_ability_count, rawcode) ||
            clone_is_noncopyable_ability(rawcode)) { row->reserved = 0; continue; }
        int32_t level = w->ability_level(source, rawcode);
        int32_t existing = w->ability_level(clone, rawcode);
        if (level <= 0) {
            if (!level && clone_has_ability(w, clone, rawcode)) { row->reserved = 0; continue; }
            w->error = 65; break;
        }
        if (!existing && !w->add_ability(clone, rawcode)) { w->error = 66; break; }
        existing = w->ability_level(clone, rawcode);
        if (existing != level && !clone_set_ability_level(w, clone, rawcode, level)) {
            w->error = 67; break;
        }
        ++row->ability_count; row->reserved = 0;
    }
    if (!w->error && index == 128 && w->ability_by_index(source, 128)) w->error = 75;
}

static uint64_t BridgeCloneExecute(CloneWork *w,CloneBoundWork *bound) {
    uint32_t count;
    uint64_t created_items[24][6] = {0};
    uint64_t owners[24] = {0};
    uint32_t source_x[24] = {0}, source_y[24] = {0}, source_facing[24] = {0};
    if (!w || w->expected_tls != g_dispatch->tls_value ||
        !(w->flags & (CLONE_COPY_ABILITIES | CLONE_COPY_ITEMS)) ||
        !w->owner || !w->type_id || !w->get_x || !w->get_y || !w->get_facing ||
        !w->create || !w->remove_unit || !w->get_level || !w->set_level ||
        !w->get_skill_points || !w->modify_skill_points ||
        !w->ability_by_index || !w->ability_id || !w->ability_level ||
        !w->add_ability || !w->set_ability_level || !w->item_in_slot ||
        !w->item_ability_by_index || !w->item_type || !w->item_charges ||
        !w->add_item || !w->set_item_charges || !w->detach_item || !w->remove_item ||
        !w->enum_owner || !w->in_group) {
        if (w) w->error = 60;
        return 0;
    }
    count = (uint32_t)BridgeSelect();
    if (!count || count > 24 || w->selection.error || !w->selection.destroyed || count != w->selection.count) {
        w->error = 61;
        return count;
    }
    if(bound && (bound->reserved || bound->expected_count!=count)) {w->error=77;return count;}
    __try {
        /* Validate the whole selection before creating the first object. */
        for (uint32_t i = 0; i < count; ++i) {
            uint64_t source = w->selection.rows[i].unit;
            CloneRow *row = &w->rows[i];
            if(!clone_source_matches(bound,i,&w->selection.rows[i])) {w->error=77;break;}
            owners[i] = w->owner(source);
            source_x[i] = w->get_x(source); source_y[i] = w->get_y(source);
            source_facing[i] = w->get_facing(source);
            row->owner = (w->flags & CLONE_PRESERVE_OWNER) ? owners[i] : w->selection.player;
            row->rawcode = w->selection.rows[i].rawcode;
            if (!owners[i] || !row->owner || !row->rawcode ||
                w->type_id(source) != row->rawcode ||
                (source_x[i] & 0x7f800000u) == 0x7f800000u ||
                (source_y[i] & 0x7f800000u) == 0x7f800000u ||
                (source_facing[i] & 0x7f800000u) == 0x7f800000u ||
                ((w->flags & CLONE_USE_SPAWN) &&
                 ((w->spawn_x_bits & 0x7f800000u) == 0x7f800000u ||
                  (w->spawn_y_bits & 0x7f800000u) == 0x7f800000u))) {
                w->error = 62; break;
            }
        }
        for (uint32_t i = 0; i < count && !w->error; ++i) {
            uint64_t source = w->selection.rows[i].unit;
            CloneRow *row = &w->rows[i];
            float x = clone_real((w->flags & CLONE_USE_SPAWN) ? w->spawn_x_bits : source_x[i]);
            float y = clone_real((w->flags & CLONE_USE_SPAWN) ? w->spawn_y_bits : source_y[i]);
            float facing = clone_real(source_facing[i]);
            /* CreateUnit can execute campaign triggers. Recheck each source,
               and never treat a returned source/existing unit as a new clone. */
            if (!clone_source_matches(bound,i,&w->selection.rows[i]) ||
                w->type_id(source) != row->rawcode || w->owner(source) != owners[i] ||
                (w->selection.rows[i].level > 0 && w->get_level(source) != w->selection.rows[i].level)) {
                w->error = 72; break;
            }
            uint64_t clone = w->create(row->owner, row->rawcode, &x, &y, &facing);
            int duplicate = 0;
            for (uint32_t prior = 0; prior < count; ++prior)
                if (clone && clone == w->selection.rows[prior].unit) duplicate = 1;
            for (uint32_t prior = 0; prior < i; ++prior)
                if (clone && clone == w->rows[prior].clone) duplicate = 1;
            if (duplicate) { w->error = 76; break; }
            row->clone = clone;
            if (!clone || w->type_id(clone) != row->rawcode || w->owner(clone) != row->owner) {
                w->error = 63; break;
            }
            if (w->selection.rows[i].level > 0) {
                int32_t source_skill_points = w->get_skill_points(source);
                row->level = w->selection.rows[i].level;
                if (w->get_level(clone) != row->level && !clone_set_level(w, clone, row->level)) {
                    w->error = 64; break;
                }
                int32_t target_skill_points = w->get_skill_points(clone);
                int64_t delta = (int64_t)source_skill_points - target_skill_points;
                if (delta < -2147483648LL || delta > 2147483647LL ||
                    (delta && !w->modify_skill_points(clone, (int32_t)delta)) ||
                    w->get_skill_points(clone) != source_skill_points) {
                    w->error = 71; break;
                }
            }
            if (w->flags & CLONE_COPY_ABILITIES) clone_copy_abilities(w, source, row);
            if (!w->error && (w->flags & CLONE_COPY_ITEMS)) {
                for (uint32_t slot = 0; slot < 6; ++slot) {
                    uint64_t item = w->item_in_slot(source, (int32_t)slot);
                    if (!item) continue;
                    uint32_t rawcode = w->item_type(item);
                    int32_t charges = w->item_charges(item);
                    if (!rawcode || charges < 0) { w->error = 68; break; }
                    uint64_t new_item = w->add_item(clone, rawcode);
                    /* Register every creation BEFORE readback can fail/throw. */
                    if (new_item) created_items[i][row->created_items++] = new_item;
                    if (!new_item || w->item_type(new_item) != rawcode) { w->error = 68; break; }
                    if (w->item_charges(new_item) != charges) {
                        w->set_item_charges(new_item, charges);
                        if (w->item_charges(new_item) != charges) { w->error = 69; break; }
                    }
                    ++row->item_count;
                }
            }
            if (!w->error) { row->status = 1; ++w->changed; ++w->completed; }
        }
    } __except(BridgeExceptionFilter(GetExceptionInformation())) {
        w->reserved = GetExceptionCode(); w->error = 73;
    }
    if (w->error || !(w->flags & CLONE_KEEP)) {
        int cleaned = 1;BridgeFault body_fault=bridge_fault;
        for (uint32_t i = 0; i < count; ++i)
            if (!clone_discard_row(w, &w->rows[i], created_items[i])) cleaned = 0;
        if (!cleaned) { w->pad = w->error; w->error = 74; }
        if (w->error && cleaned) { w->changed = 0; w->completed = 0; }
        if(w->reserved && body_fault.code)bridge_fault=body_fault;
    }
    return count;
}

__declspec(dllexport) uint64_t BridgeCloneQuery(void) {
    return BridgeCloneExecute((CloneWork *)g_dispatch->work,0);
}
__declspec(dllexport) uint64_t BridgeCloneBoundQuery(void) {
    CloneBoundWork *w=(CloneBoundWork *)g_dispatch->work;
    return BridgeCloneExecute(w?&w->clone:0,w);
}

#ifdef BRIDGE_DIAGNOSTIC
typedef struct CloneRemovalInspectWork {
    CloneWork clone;
    uint64_t (*resolve_unit)(uint64_t);
    uint64_t target;
    uint64_t object;
    uint32_t native_type, flags;
} CloneRemovalInspectWork;
__declspec(dllexport) const uint32_t clone_removal_inspect_abi[3]={0x24323061u,216u,1920u};
__declspec(dllexport) uint64_t BridgeCloneRemovalInspect(void) {
    CloneRemovalInspectWork *p=(CloneRemovalInspectWork *)g_dispatch->work;
    if(!p || !p->resolve_unit || !p->target) return 0;
    p->native_type=p->clone.type_id(p->target);
    p->object=p->resolve_unit(p->target);
    p->flags=p->object?*(uint32_t *)(uintptr_t)(p->object+0x38):0;
    p->clone.rows[0].clone=p->clone.ability_by_index(p->target,0);
    p->clone.rows[0].level=p->clone.ability_level(p->target,0x416d6f76u);
    return 1;
}
/* Read-only, paged observation of the exact enumerator used by cloning.
   Source index/page start occupy the unused spawn fields; no creation setter
   is called. This export is absent from production builds. */
__declspec(dllexport) uint64_t BridgeCloneInspect(void) {
    CloneWork *w = (CloneWork *)g_dispatch->work;
    uint32_t count = (uint32_t)BridgeSelect();
    if (!w || w->selection.error || !w->selection.destroyed || w->spawn_y_bits >= count || w->spawn_x_bits >= 128) {
        if (w) w->error = 61;
        return count;
    }
    uint64_t source = w->selection.rows[w->spawn_y_bits].unit;
    for (uint32_t index = w->spawn_x_bits; index < 128 && w->completed < 24; ++index) {
        uint64_t ability = w->ability_by_index(source, (int32_t)index);
        if (!ability) break;
        CloneRow *row = &w->rows[w->completed++];
        row->clone = ability; row->owner = source;
        row->rawcode = w->ability_id(ability);
        row->level = row->rawcode ? w->ability_level(source, row->rawcode) : 0;
        row->ability_count = index; row->status = 1;
    }
    return count;
}
#endif
