"""Decode real C snapshot output using fake natives, without a game process."""
import ctypes
import faulthandler
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import Mock

import war3_reforged_trainer as trainer_module


HARNESS = r'''
#include <windows.h>
static unsigned allocations, fail_allocation, allocation_calls;
static void *test_alloc(HANDLE heap, DWORD flags, SIZE_T size) {
    void *p;
    if (++allocation_calls == fail_allocation) return NULL;
    p = HeapAlloc(heap, flags, size);
    if (p) ++allocations;
    return p;
}
static void *test_realloc(HANDLE heap, DWORD flags, void *p, SIZE_T size) {
    if (++allocation_calls == fail_allocation) return NULL;
    return HeapReAlloc(heap, flags, p, size);
}
static BOOL test_free(HANDLE heap, DWORD flags, void *p) {
    BOOL ok = HeapFree(heap, flags, p);
    if (p && ok) --allocations;
    return ok;
}
#define HeapAlloc test_alloc
#define HeapReAlloc test_realloc
#define HeapFree test_free
#include "HELPER_SOURCE"
static unsigned sizes[13], selected, cursor, destroyed, fail_index, holes;
static unsigned target_unit, target_fault, enumerations, field_reads;
static unsigned recycle_point, recycle_unit;
static uint8_t objects[13][0x600], owners[13][0xc0], items[13][0x20];
static void recycle(unsigned point, uint64_t unit) {
    if (point != recycle_point || unit != recycle_unit) return;
    recycle_point = 0;
    *(uint64_t *)(objects[unit-1]+0x18) += 1ULL << 32;
    *(uint64_t *)(owners[unit-1]+0x20) = *(uint64_t *)(objects[unit-1]+0x18);
}
static uint64_t fake_create(void) { return 1; }
static uint64_t fake_player(void) { return 2; }
static void fake_enum(uint64_t g, uint64_t p, uint64_t f) { cursor = 0; ++enumerations; }
static uint64_t fake_first(uint64_t g) { return cursor < selected ? cursor + 1 : 0; }
static void fake_remove(uint64_t g, uint64_t u) { ++cursor; }
static void fake_destroy(uint64_t g) { ++destroyed; }
static uint64_t fake_owner(uint64_t u) { return 2; }
static int32_t fake_player_id(uint64_t p) { return 1; }
static uint32_t fake_type(uint64_t u) { ++field_reads; recycle(1,u); return 0x68666f6f; }
static uint32_t fake_real(uint64_t u) { recycle(3,u); return 0x3f800000; }
static uint32_t fake_state(uint64_t u, int32_t s) { recycle(2,u); return 0x40000000; }
static int32_t fake_hero(uint64_t u) { return u == 1 ? 5 : 0; }
static int32_t fake_stat(uint64_t u, uint32_t b) { return b ? 25 : 10; }
static uint64_t fake_unit(uint64_t u) { return (uint64_t)(uintptr_t)objects[u-1]; }
static uint64_t fake_agent(uint32_t slot, uint32_t serial) {
    return slot && slot <= 13 && *(uint64_t *)(owners[slot-1]+0x20) == (((uint64_t)serial<<32)|slot)
        ? (uint64_t)(uintptr_t)owners[slot-1] : 0;
}
static uint64_t fake_slot(uint64_t u, int32_t s) { return s == 0 ? u + 1000 : 0; }
static uint64_t fake_item(uint64_t u) { return (uint64_t)(uintptr_t)items[u-1001]; }
static uint32_t fake_item_type(uint64_t u) { return 0x49303031; }
static int32_t fake_charges(uint64_t u) { return (int32_t)(u - 1000); }
static uint64_t fake_ability(uint64_t u, int32_t i) {
    recycle(4,u);
    if ((unsigned)i == fail_index) RaiseException(0xe0000001u, 0, 0, NULL);
    if ((unsigned)i >= sizes[u-1] || (holes && i == 3)) return 0;
    return (u << 32) | (uint32_t)(i + 1);
}
static uint32_t fake_id(uint64_t a) {
    if (holes && (uint32_t)a == 6) return 0;
    return 0x41000000u + (uint32_t)(a >> 32) * 0x10000u + (uint32_t)a;
}
static int32_t fake_level(uint64_t u, uint32_t id) { return (int32_t)(id & 0xffffu); }
__declspec(dllexport) unsigned collect(unsigned n, const unsigned *counts, unsigned fail, unsigned sparse,
                                      uint64_t *out, unsigned out_capacity, unsigned *length, unsigned *units) {
    NativeCommand cmd = {0}; NativeOp op = {0}; uint64_t *payload = NULL;
    uint32_t payload_count = 0; DWORD error;
    selected = n; cursor = destroyed = 0; fail_index = fail; holes = sparse;
    enumerations = field_reads = 0;
    allocation_calls = 0;
    *length = *units = 0;
    if (n > 13) return ERROR_INVALID_PARAMETER;
    ZeroMemory(objects,sizeof(objects));
    for (unsigned i = 0; i < n; ++i) {
        uint64_t full = ((uint64_t)(i+1) << 32) | (i+1);
        sizes[i] = counts[i];
        *(uint64_t *)(items[i]+0x18) = full + 1000;
        *(uint64_t *)(objects[i]+0x18) = full;
        *(uint64_t *)(owners[i]+0x18) = 0x2b7733752b61676cULL;
        *(uint64_t *)(owners[i]+0x20) = full;
        *(uint64_t *)(owners[i]+0x90) = (uint64_t)(uintptr_t)objects[i];
    }
    for (unsigned i = 0; i < sizeof(g_persistent_natives)/sizeof(g_persistent_natives[0]); ++i) {
        const char *name = g_persistent_native_names[i];
        g_persistent_natives[i].name = name;
        g_persistent_natives[i].handler = (uint64_t)(uintptr_t)fake_create;
#define BIND(n, f) if (!strcmp(name, n)) g_persistent_natives[i].handler = (uint64_t)(uintptr_t)f
        BIND("CreateGroup", fake_create); BIND("GetLocalPlayer", fake_player);
        BIND("GroupEnumUnitsSelected", fake_enum); BIND("FirstOfGroup", fake_first);
        BIND("GroupRemoveUnit", fake_remove); BIND("DestroyGroup", fake_destroy);
        BIND("GetOwningPlayer", fake_owner); BIND("GetPlayerId", fake_player_id);
        BIND("GetUnitTypeId", fake_type); BIND("GetUnitState", fake_state);
        BIND("GetUnitX", fake_real); BIND("GetUnitY", fake_real); BIND("GetUnitMoveSpeed", fake_real);
        BIND("GetHeroLevel", fake_hero); BIND("GetHeroXP", fake_hero);
        BIND("GetHeroStr", fake_stat); BIND("GetHeroAgi", fake_stat); BIND("GetHeroInt", fake_stat);
        BIND("UnitItemInSlot", fake_slot); BIND("GetItemTypeId", fake_item_type); BIND("GetItemCharges", fake_charges);
        BIND("BlzGetUnitAbilityByIndex", fake_ability); BIND("BlzGetAbilityId", fake_id);
        BIND("GetUnitAbilityLevel", fake_level);
#undef BIND
    }
    g_persistent_ready = 0;
    g_persistent_unit_resolver = (uint64_t)(uintptr_t)fake_unit;
    g_persistent_agent_resolver = (uint64_t)(uintptr_t)fake_agent;
    g_persistent_item_resolver = (uint64_t)(uintptr_t)fake_item;
    cmd.op_count = 1;
    if (target_unit) {
        unsigned index = target_unit - 1;
        op.kind = WAR3_NATIVE_OP_PERSISTENT_UNIT_SNAPSHOT;
        cmd.unit_handle = target_unit;
        op.handler = (uint64_t)(uintptr_t)objects[index];
        op.arg0 = ((uint64_t)target_unit << 32) | target_unit;
        op.arg1 = (uint64_t)(uintptr_t)owners[index];
        if (target_fault == 1) ++op.handler;
        if (target_fault == 2) op.arg0 += 1ULL << 32;
        if (target_fault == 3) ++op.arg1;
        if (target_fault == 4) *(uint64_t *)(objects[index]+0x18) += 1ULL << 32;
        if (target_fault == 5) *(uint64_t *)(owners[index]+0x90) = 0;
        if (target_fault == 6) cmd.unit_handle = 0;
    }
    error = war3_persistent_selected_snapshot(&cmd, &op, &payload, &payload_count);
    if (!error) {
        if (payload_count > out_capacity) error = ERROR_INSUFFICIENT_BUFFER;
        else {
            if (payload_count) memcpy(out, payload, payload_count * sizeof(uint64_t));
            *length = payload_count; *units = (unsigned)op.result;
        }
    }
    if (payload) HeapFree(GetProcessHeap(), 0, payload);
    return error;
}
__declspec(dllexport) unsigned destroyed_count(void) { return destroyed; }
__declspec(dllexport) unsigned live_allocations(void) { return allocations; }
__declspec(dllexport) unsigned alloc_calls(void) { return allocation_calls; }
__declspec(dllexport) void set_fail_allocation(unsigned n) { fail_allocation = n; }
__declspec(dllexport) void set_target(unsigned n, unsigned fault) { target_unit = n; target_fault = fault; }
__declspec(dllexport) void set_recycle(unsigned point,unsigned unit) { recycle_point=point; recycle_unit=unit; }
__declspec(dllexport) unsigned enumeration_count(void) { return enumerations; }
__declspec(dllexport) unsigned field_read_count(void) { return field_reads; }
'''


class NativeSnapshotPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which("clang")
        if not compiler:
            raise unittest.SkipTest("clang is required for the native snapshot harness")
        directory = tempfile.TemporaryDirectory(prefix="war3-snapshot-test-")
        cls.addClassCleanup(directory.cleanup)
        source = Path(directory.name) / "snapshot.c"
        helper = Path(__file__).with_name("tools") / "war3_native_helper.c"
        source.write_text(HARNESS.replace("HELPER_SOURCE", helper.as_posix()), encoding="utf-8")
        library = source.with_suffix(".dll")
        subprocess.run([compiler, "-shared", "-O2", "-Wno-microsoft-goto", str(source),
                        "-o", str(library), "-luser32", "-lkernel32"],
                       check=True, capture_output=True, timeout=60)
        cls.native = ctypes.CDLL(str(library))
        import _ctypes
        cls.addClassCleanup(_ctypes.FreeLibrary, cls.native._handle)
        cls.native.collect.argtypes = [ctypes.c_uint, ctypes.POINTER(ctypes.c_uint), ctypes.c_uint,
                                      ctypes.c_uint, ctypes.POINTER(ctypes.c_uint64), ctypes.c_uint,
                                      ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint)]
        cls.native.collect.restype = ctypes.c_uint

    def collect(self, counts, fail=0xffffffff, sparse=False):
        payload = (ctypes.c_uint64 * 100000)()
        sizes = (ctypes.c_uint * len(counts))(*counts)
        length, units = ctypes.c_uint(), ctypes.c_uint()
        error = self.native.collect(len(counts), sizes, fail, sparse, payload, len(payload),
                                    ctypes.byref(length), ctypes.byref(units))
        self.assertEqual(self.native.live_allocations(), 0)
        return error, units.value, tuple(payload[:length.value])

    @staticmethod
    def parse(count, payload):
        trainer = object.__new__(trainer_module.War3Trainer)
        trainer.persistent_native_init = Mock()
        trainer._run_native_helper_ops = Mock(return_value=[trainer_module.NativeHelperOpResult(
            kind=trainer.NATIVE_HELPER_OP_PERSISTENT_SELECTED_SNAPSHOT, result=count, extra_results=payload,
        )])
        return trainer.persistent_native_selected_snapshots()

    def test_c_output_roundtrips_boundaries_and_mixed_groups(self):
        for counts in ((0,), (48,), (49,), (256,), (300,), (4096,),
                       (49, 0, 300, 48, 1), (4096,) * 12):
            with self.subTest(counts=counts):
                error, n, payload = self.collect(counts)
                self.assertEqual(error, 0)
                self.assertEqual(self.native.destroyed_count(), 1)
                self.assertEqual(len(payload), 154 * n + 2 * sum(max(0, c - 48) for c in counts))
                for unit, (snapshot, count) in enumerate(zip(self.parse(n, payload), counts), 1):
                    self.assertEqual(snapshot.handle, unit)
                    self.assertEqual(snapshot.full_handle, (unit << 32) | unit)
                    self.assertEqual(snapshot.ability_ids, tuple(0x41000000 + unit * 0x10000 + i + 1 for i in range(count)))
                    self.assertEqual(snapshot.ability_levels, tuple(range(1, count + 1)))
                    self.assertEqual(snapshot.hero_level, 5 if unit == 1 else 0)
                    self.assertEqual(snapshot.item_charges[0], unit)
                    self.assertEqual(snapshot.item_full_handles, (((unit << 32) | unit) + 1000,) + (0,) * 5)
                    self.assertEqual((snapshot.strength, snapshot.agility, snapshot.intelligence), (25 if unit == 1 else 0,) * 3)
                    self.assertEqual((snapshot.base_strength, snapshot.base_agility, snapshot.base_intelligence), (10 if unit == 1 else 0,) * 3)

    def test_sparse_legacy_range_keeps_later_entries(self):
        error, n, payload = self.collect((60,), sparse=True)
        self.assertEqual(error, 0)
        self.assertEqual(self.parse(n, payload)[0].ability_levels, tuple(i + 1 for i in range(60) if i not in (3, 5)))

    def test_overflow_has_no_partial_payload_and_releases_group(self):
        for counts in ((4097,), (0,) * 13):
            self.assertEqual(self.collect(counts), (234, 0, ()))
            self.assertEqual(self.native.destroyed_count(), 1)
        self.assertEqual(self.collect(()), (0, 0, ()))

    def test_exception_after_extension_allocation_releases_group(self):
        enabled = faulthandler.is_enabled()
        try:
            faulthandler.disable()
            self.assertEqual(self.collect((300,), fail=100), (0xe0000001, 0, ()))
        finally:
            if enabled:
                faulthandler.enable()
        self.assertEqual(self.native.destroyed_count(), 1)

    def test_parser_rejects_truncation_and_trailing_data(self):
        error, n, payload = self.collect((49, 300))
        self.assertEqual(error, 0)
        for bad in (payload[:-1], payload + (123,), payload[:139]):
            with self.assertRaises(RuntimeError):
                self.parse(n, bad)

    def test_each_allocation_failure_releases_all_owned_memory(self):
        self.assertEqual(self.collect((300, 49))[0], 0)
        calls = self.native.alloc_calls()
        self.assertGreater(calls, 3)
        try:
            for fail in range(1, calls + 1):
                with self.subTest(allocation=fail):
                    self.native.set_fail_allocation(fail)
                    self.assertEqual(self.collect((300, 49)), (14, 0, ()))
                    self.assertEqual(self.native.destroyed_count(), 0 if fail == 1 else 1)
        finally:
            self.native.set_fail_allocation(0)

    def test_parser_rejects_invalid_counts(self):
        for count in (-1, 13):
            with self.assertRaises(RuntimeError):
                self.parse(count, (0,) * 154 * max(0, count))
        for ability_count in (-1, 4097):
            row = [0] * 154
            row[41] = ability_count
            with self.assertRaises(RuntimeError):
                self.parse(1, tuple(row))

    def test_target_snapshot_does_not_enumerate_selection_and_keeps_extended_fields(self):
        try:
            self.native.set_target(2, 0)
            error, count, payload = self.collect((0, 300))
            self.assertEqual(error, 0)
            self.assertEqual(count, 1)
            snapshot = self.parse(count, payload)[0]
            self.assertEqual(snapshot.handle, 2)
            self.assertEqual(snapshot.full_handle, 0x200000002)
            self.assertEqual(len(snapshot.ability_ids), 300)
            self.assertEqual(snapshot.item_charges[0], 2)
            self.assertEqual(self.native.enumeration_count(), 0)
            self.assertEqual(self.native.destroyed_count(), 0)
        finally:
            self.native.set_target(0, 0)

    def test_target_mismatch_fails_before_any_field_native(self):
        try:
            for fault in range(1, 7):
                with self.subTest(fault=fault):
                    self.native.set_target(2, fault)
                    error, count, payload = self.collect((0, 10))
                    self.assertEqual(error, 13 if fault == 6 else 6)
                    self.assertEqual((count, payload), (0, ()))
                    self.assertEqual(self.native.field_read_count(), 0)
                    self.assertEqual(self.native.enumeration_count(), 0)
        finally:
            self.native.set_target(0, 0)

    def test_generation_change_during_fields_discards_whole_snapshot(self):
        try:
            for targeted in (False, True):
                for point in range(1, 5):
                    with self.subTest(targeted=targeted, point=point):
                        self.native.set_target(2 if targeted else 0, 0)
                        self.native.set_recycle(point, 2)
                        # In group mode, unit 1 has already produced an extended
                        # ability payload. Failure must discard that too.
                        self.assertEqual(self.collect((300, 10)), (6, 0, ()))
                        self.assertEqual(self.native.destroyed_count(), 0 if targeted else 1)
        finally:
            self.native.set_target(0, 0)
            self.native.set_recycle(0, 0)
