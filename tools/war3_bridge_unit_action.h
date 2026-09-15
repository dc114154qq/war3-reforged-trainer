/* Current-build 24268 batch for unit state/actions used by the elephant panel. */
#define UNIT_ACTION_SET_INVULNERABLE 1u
#define UNIT_ACTION_SET_PATHING 2u
#define UNIT_ACTION_SET_PAUSED 3u
#define UNIT_ACTION_RESET_COOLDOWN 4u
#define UNIT_ACTION_KILL 5u
#define UNIT_ACTION_REMOVE 6u
#define UNIT_ACTION_EXPLODE 7u
#define UNIT_ACTION_SET_POSITION 8u
#define UNIT_ACTION_SET_SCALE 9u
#define UNIT_ACTION_TAKE_CONTROL 10u
#define UNIT_ACTION_QUERY_INVULNERABLE 11u
#define UNIT_ACTION_QUERY_PAUSED 12u
#define UNIT_ACTION_ADD_SKILL_POINTS 13u

typedef struct UnitActionRow {
    uint64_t unit;
    uint32_t before, after, status, reserved, actual_x_bits, actual_y_bits;
} UnitActionRow;
_Static_assert(sizeof(UnitActionRow) == 32, "UnitActionRow ABI");

typedef struct UnitActionWork {
    SelectionWork selection;
    void (*set_invulnerable)(uint64_t, uint32_t);
    uint8_t (*get_invulnerable)(uint64_t);
    void (*set_pathing)(uint64_t, uint32_t);
    void (*pause_unit)(uint64_t, uint32_t);
    uint8_t (*is_paused)(uint64_t);
    void (*reset_cooldown)(uint64_t);
    void (*kill_unit)(uint64_t);
    void (*remove_unit)(uint64_t);
    void (*set_exploded)(uint64_t, uint32_t);
    void (*set_scale)(uint64_t, float, float, float);
    void (*set_position)(uint64_t, float, float);
    float (*get_x)(uint64_t);
    float (*get_y)(uint64_t);
    void (*set_owner)(uint64_t, uint64_t, uint32_t);
    uint64_t (*get_owner)(uint64_t);
    uint8_t (*modify_skill_points)(uint64_t,uint32_t);
    void *expected_tls;
    uint32_t action, value, changed, error, completed, reserved;
    uint32_t x_bits, y_bits, scale_x_bits, scale_y_bits, scale_z_bits, pad;
    UnitActionRow rows[24];
} UnitActionWork;
_Static_assert(sizeof(UnitActionWork) == 1432, "UnitActionWork ABI");
__declspec(dllexport) const uint32_t unit_action_batch_abi[3] = {0x24268016u, 216u, 1432u};

static float UnitActionReal(uint32_t bits) {
    union { uint32_t bits; float value; } value;
    value.bits = bits;
    return value.value;
}

static int UnitActionFloatEqual(float left, float right) {
    float difference = left - right;
    if (difference < 0.0f) difference = -difference;
    return left == left && right == right && difference <= 0.01f;
}

static int UnitActionNeedsTypeCheck(uint32_t action) {
    return action != UNIT_ACTION_REMOVE && action != UNIT_ACTION_KILL && action != UNIT_ACTION_EXPLODE;
}

__declspec(dllexport) uint64_t BridgeUnitActionQuery(void) {
    UnitActionWork *w = (UnitActionWork *)g_dispatch->work;
    uint32_t i;
    uint64_t count;
    float x, y, sx, sy, sz;
    if (!w || w->expected_tls != g_dispatch->tls_value || w->action < UNIT_ACTION_SET_INVULNERABLE ||
        w->action > UNIT_ACTION_ADD_SKILL_POINTS ||
        ((w->action == UNIT_ACTION_ADD_SKILL_POINTS && (w->value < 1 || w->value > 1000000)) ||
         (w->action != UNIT_ACTION_ADD_SKILL_POINTS && w->value > 1))) {
        if (w) w->error = 60;
        return 0;
    }
    if ((w->action == UNIT_ACTION_SET_INVULNERABLE || w->action == UNIT_ACTION_QUERY_INVULNERABLE) &&
        (!w->get_invulnerable || (w->action == UNIT_ACTION_SET_INVULNERABLE && !w->set_invulnerable))) w->error = 61;
    if (w->action == UNIT_ACTION_SET_PATHING && !w->set_pathing) w->error = 62;
    if ((w->action == UNIT_ACTION_SET_PAUSED || w->action == UNIT_ACTION_QUERY_PAUSED) &&
        (!w->is_paused || (w->action == UNIT_ACTION_SET_PAUSED && !w->pause_unit))) w->error = 63;
    if (w->action == UNIT_ACTION_RESET_COOLDOWN && !w->reset_cooldown) w->error = 64;
    if (w->action == UNIT_ACTION_KILL && !w->kill_unit) w->error = 65;
    if (w->action == UNIT_ACTION_REMOVE && !w->remove_unit) w->error = 66;
    if (w->action == UNIT_ACTION_EXPLODE && (!w->set_exploded || !w->kill_unit)) w->error = 67;
    if (w->action == UNIT_ACTION_SET_POSITION && (!w->set_position || !w->get_x || !w->get_y)) w->error = 68;
    if (w->action == UNIT_ACTION_SET_SCALE && !w->set_scale) w->error = 69;
    if (w->action == UNIT_ACTION_TAKE_CONTROL && (!w->set_owner || !w->get_owner)) w->error = 70;
    if (w->action == UNIT_ACTION_ADD_SKILL_POINTS && !w->modify_skill_points) w->error = 77;
    if (w->error) return 0;
    count = BridgeSelect();
    if (!count || w->selection.error || !w->selection.destroyed || count != w->selection.count) {
        w->error = 71;
        return count;
    }
    x = UnitActionReal(w->x_bits); y = UnitActionReal(w->y_bits);
    sx = UnitActionReal(w->scale_x_bits); sy = UnitActionReal(w->scale_y_bits); sz = UnitActionReal(w->scale_z_bits);
    for (i = 0; i < count; ++i) {
        SelectionRow *selected = &w->selection.rows[i];
        UnitActionRow *row = &w->rows[i];
        uint64_t unit = selected->unit;
        uint32_t before = 0, after = 0;
        row->unit = unit;
        if (w->action == UNIT_ACTION_ADD_SKILL_POINTS && selected->level <= 0) {
            row->status = 2; ++w->completed; continue;
        }
        if (UnitActionNeedsTypeCheck(w->action) && w->selection.unit_type_id(unit) != selected->rawcode) {
            w->error = 72; return count;
        }
        if (w->action == UNIT_ACTION_SET_INVULNERABLE || w->action == UNIT_ACTION_QUERY_INVULNERABLE) {
            before = w->get_invulnerable(unit) ? 1u : 0u;
            if (w->action == UNIT_ACTION_SET_INVULNERABLE) {
                w->set_invulnerable(unit, w->value);
                after = w->get_invulnerable(unit) ? 1u : 0u;
                if (after != w->value) { w->error = 73; return count; }
                if (before != after) ++w->changed;
            } else after = before;
        } else if (w->action == UNIT_ACTION_SET_PAUSED || w->action == UNIT_ACTION_QUERY_PAUSED) {
            before = w->is_paused(unit) ? 1u : 0u;
            if (w->action == UNIT_ACTION_SET_PAUSED) {
                w->pause_unit(unit, w->value);
                after = w->is_paused(unit) ? 1u : 0u;
                if (after != w->value) { w->error = 74; return count; }
                if (before != after) ++w->changed;
            } else after = before;
        } else if (w->action == UNIT_ACTION_SET_PATHING) {
            w->set_pathing(unit, w->value); ++w->changed;
        } else if (w->action == UNIT_ACTION_RESET_COOLDOWN) {
            w->reset_cooldown(unit); ++w->changed;
        } else if (w->action == UNIT_ACTION_KILL) {
            w->kill_unit(unit); ++w->changed;
        } else if (w->action == UNIT_ACTION_REMOVE) {
            w->remove_unit(unit); ++w->changed;
        } else if (w->action == UNIT_ACTION_EXPLODE) {
            w->set_exploded(unit, 1); w->kill_unit(unit); ++w->changed;
        } else if (w->action == UNIT_ACTION_SET_POSITION) {
            w->set_position(unit, x, y);
            row->actual_x_bits = ((union { float value; uint32_t bits; }){w->get_x(unit)}).bits;
            row->actual_y_bits = ((union { float value; uint32_t bits; }){w->get_y(unit)}).bits;
            if (!UnitActionFloatEqual(w->get_x(unit), x) || !UnitActionFloatEqual(w->get_y(unit), y)) { w->error = 75; return count; }
            ++w->changed;
        } else if (w->action == UNIT_ACTION_SET_SCALE) {
            w->set_scale(unit, sx, sy, sz); ++w->changed;
        } else if (w->action == UNIT_ACTION_TAKE_CONTROL) {
            before = w->get_owner(unit) == w->selection.player ? 1u : 0u;
            w->set_owner(unit, w->selection.player, 0);
            after = w->get_owner(unit) == w->selection.player ? 1u : 0u;
            if (!after) { w->error = 76; return count; }
            if (!before) ++w->changed;
        } else if (w->action == UNIT_ACTION_ADD_SKILL_POINTS) {
            if (!w->modify_skill_points(unit, w->value)) { w->error = 78; return count; }
            ++w->changed;
        }
        row->before = before; row->after = after; row->status = 1;
        ++w->completed;
    }
    return count;
}
