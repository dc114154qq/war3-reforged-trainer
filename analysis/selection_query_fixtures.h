/* Local-only fixtures for the exact SelectionWork query implementation. */
static SelectionWork *fixture_work(void) { return (SelectionWork *)g_dispatch->work; }
static uint64_t fixture_player(void) { return 0x100008; }
static uint64_t fixture_create(void) { return fixture_work()->reserved == 4 ? 0 : 0x123; }
static void fixture_enum(uint64_t group,uint64_t player,uint64_t filter) {
    if (fixture_work()->reserved == 5) { volatile uint64_t value = *(volatile uint64_t *)g_dispatch->nonce; (void)value; }
}
static uint64_t fixture_first(uint64_t group) {
    static uint32_t index;
    if (fixture_work()->reserved == 0) return 0;
    if (fixture_work()->reserved == 2) return 0x100000;
    if (fixture_work()->reserved == 3) return 0x100000;
    if (fixture_work()->reserved == 1) return index < 24 ? 0x100000 + index++ : 0;
    return index++ < 2 ? 0x100000 + index : 0;
}
static void fixture_remove(uint64_t group,uint64_t unit) { (void)group; (void)unit; }
static void fixture_destroy(uint64_t group) { (void)group; }
static uint32_t fixture_rawcode(uint64_t unit) { return 0x48303030 + (uint32_t)(unit - 0x100000); }
static int32_t fixture_level(uint64_t unit) {
    if (fixture_work()->reserved == 6) { volatile uint64_t value=*(volatile uint64_t *)g_dispatch->nonce; (void)value; }
    return unit == 0x100000 ? 7 : 0;
}
__declspec(dllexport) uint64_t ProbeSelectionFixtureQuery(void) {
    SelectionWork *work=fixture_work();
    work->local_player=fixture_player;work->create_group=fixture_create;work->enum_selected=fixture_enum;
    work->first_of_group=fixture_first;work->remove_from_group=fixture_remove;work->destroy_group=fixture_destroy;
    work->unit_type_id=fixture_rawcode;work->hero_level=fixture_level;
    return ProbeSelectionQuery();
}
