# 2.0.3 stability fixes - 2026-09-18

## Observations

- `war3_loader.dll` is loaded in every inspected 3.0.0.24268 process. Its disk SHA-256 is
  `e32431e26f58d1201be3f48baed485114227864d8c6b871eae8e9528241ec8e9`.
- Existing loader evidence shows that it owns patched thread/exception entry wrappers, while the
  1826-entry Warcraft native table is embedded in the window-thread TLS `context5` object. The DLL
  has no exported selection/native dispatch API.
- Direct `IsFogEnabled` and `IsFogMaskEnabled` calls each reached an intentional null-read gate at
  handler-relative offset `0x3d2` (`33 c0 0f b6 00`).
- Runtime code inspection found the corresponding setter gates at `FogEnable+0x519` and
  `FogMaskEnable+0x3c9`, both using `41 0f b6 04 24` after zeroing `r12`.
- The previous MapFlags route changed flags without reliably refreshing the rendered fog state.
- The previous persistent hook could outlive a rebuilt game UI queue and later stall or fail.
- Exact-slot item replacement could remove the old item and then fail when
  `UnitAddItemToSlotById` rejected the new item in a full inventory.

## Implementation

- Current-engine dispatch now has no session parameter and always maps, installs, executes,
  unhooks, frees, and unmaps one independent batch. Engine acceptance requires verified callback,
  completed query, freed work/command blocks, and successful image unmap.
- The 3.0 route rejects every legacy helper operation, including native registration, before old
  persistent-hook installation can run.
- The product bridge, transport, ABI verifier, and spec no longer expose or package MapFlags.
- Fog calls use handlers discovered from the current TLS native table. Control-flow recovery is
  limited to four build-verified handler-relative null-read gates, read access to address zero,
  continuable AV, and one recovery per call. All other faults remain failures.
- Fog setters call both `FogEnable` and `FogMaskEnable`; success still requires
  `IsFogEnabled`/`IsFogMaskEnabled` readback to equal the requested final state.
- Exact-slot item replacement falls back to normal item creation only after the target slot is
  empty. A full inventory therefore forces the created item into that exact slot. Rollback uses
  the same path and restores charges.
- Dark mode defaults on and can be toggled. The Tk/ttk palette covers frames, labels, buttons,
  entries, spinboxes, comboboxes, notebooks, trees, headings, scrollbars, canvases, text widgets,
  and listboxes.

## Verified results

- PID 25680: strict query-gate recovery returned `(true, true)`.
- PID 23604 after process restart: strict query-gate recovery returned `(false, false)`.
- Both query runs used fresh one-shot hooks and released all mapped resources.
- Four accepted fog gate shapes and rejection variants are covered by compiled fixture tests.
- Current targeted suite after the final fog/item changes: 132 passed.
- All `test_24268*.py`: 535 passed.
- Final complete suite: 2293 passed, 17 skipped, 120 subtests passed.
- Dark-mode screenshot: `analysis/ui-dark-mode-preview.png`, 1196x819, 262881 bytes.
- GUI QA process closed; PID 23604 remained responsive.

## Live acceptance

- Fog roundtrip on PID 23604 passed: `(false,false) -> (true,true) -> (false,false)`.
  Both writes recovered six exact control-flow/tail gates and all five transactions released their
  hook, work block, command block, and mapped image. Evidence:
  `fog-live-roundtrip-final-23604.json`.
- Full six-slot inventory replacement on PID 23604 passed. Slot 0 was replaced while all slots were
  occupied, the normal-create fallback filled the exact empty slot, and replacement back to the
  original rawcode restored all six rawcode/charge pairs while slots 1-5 retained their handles.
  Evidence: `item-full-inventory-roundtrip-23604.json`.
- Compiled fixtures cover add-slot failure, normal-create fallback, and rollback failure handling.
- Final frozen runtime self-test passed with `frozen=true`; bundled bridge hash matches the rebuilt
  source DLL and the retired helper is absent.
