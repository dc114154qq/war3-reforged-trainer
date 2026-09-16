# 3.0 r12 Fix Evidence

## Observations

- `trainer-error-20260916-221905-870-pid18988.log`: `world_effect` failed before dispatch because `GroupEnumUnitsSelected` was missing from the current native table.
- `trainer-error-20260916-221829-299-pid18988.log` and `trainer-error-20260916-222015-811-pid18988.log`: `WORLD_SET_FOG` returned `3221225477` (`0xC0000005`) from the direct `FogEnable`/`FogMaskEnable` route. The first report also showed `FogEnable` as `image-noaccess-diagnostic-only` during preflight.
- The packaged source reported `app_version='3.0.0.24268'` even though the executable was named `v2.0.1`.

## Changes

- World-effect enumeration now reserves the historical selection block but finds a live local-player caster through `GroupEnumUnitsOfPlayer`; it no longer requires `GroupEnumUnitsSelected`.
- Map visibility fallback uses `ConvertMapFlag(1/2)`, `SetMapFlag`, and `IsMapFlagSet`, with readback validation.
- Camera projection prefers `CAMERA_FIELD_FIELD_OF_VIEW` index 2 and keeps index 3 only as a compatibility fallback.
- UI/log application version is `2.0.1`; game build remains separately recorded as `3.0.0.24268`.

## Verified

- Target tests: `16 passed` after the final test additions.
- Full offline suite: `2275 passed, 17 skipped, 120 subtests passed`.
- Bridge compilation: x64 ABI verified.
- Frozen runtime self-test: `ok=true`, `frozen=true`, bridge hash `50e3754fac5b21c00741f7cb195695f51125c2032e1b54c3a0db348e020a975e`, retired helper absent.
- Frozen source match: true; PE file version: `2.0.1.0`.

## Remaining

- Live map-visibility, fullscreen-effect, and teleport accuracy still need confirmation in the target 3.0 map because the current test machine was not available for a live operation during this build.
