# 24268 transport compatibility audit — 2026-09-26

## External evidence

- Source log: `E:\baidudonwload\魔兽错误日志\log\trainer-error-latest.log`.
- The log identifies `app_version='2.0.6'`, `game_build='3.0.0.24268'`, and bridge SHA `f8257a5bfb3df980b161798e06464cf6fcb0b8dfdc2723230ac2feed502d1c79`.
- It failed on `sec_image_fallback` during `WH_CALLWNDPROC` installation: `bridge_install_trace=0x105`, `exception_code=0xc0000005`, `last_error=126`, no callback, and all mapped allocations were released.
- That log predates the current 2.0.7 artifact. It is evidence for the old failure route, not proof of current external success.

## Current compatibility change

- Normal dispatch remains `WH_CALLWNDPROC + SendMessageTimeout`.
- Only after a clean install failure with no callback and verified cleanup, dispatch retries once through `WH_GETMESSAGE + PostMessage`.
- The retry report preserves the first route, fallback route, bridge trace, exception, and release state. If the fallback also fails, the error says `compatibility fallback` rather than implying a same-route retry.
- No retry is attempted when the first route retains a thread, mapping, command block, or other allocation.

## Live verification

- Current process: PID `22708`, Warcraft III 3.0.0.24268; the game window was minimized and was not clicked or unpaused.
- Current 2.0.7 package read-only probe succeeded on the default route and returned controller `ATug`, total points `4`, used points `3`, remaining points `1`, native choices `UT1b`, `UT2b`, `UT5a`, and no anomalies.
- A forced `WH_GETMESSAGE + PostMessage` read-only probe also succeeded with the same state and no cleanup error.
- A live fallback probe against PID `22708` simulated only the first route's clean install failure, then executed the real fallback route. It returned `target_unit=1052556`, `bag_size=30`, and `equipment_count=9`; the business dispatch sequence was `send-failed -> posted`. A final ordinary `send` entry came from trainer shutdown cleanup, not a second business retry.
- Passing the target executable module as `hMod` was tested in an isolated bridge build and rejected locally with `0x106 / ERROR_MOD_NOT_FOUND`; that variant was discarded and is not in the worktree.

## Limits

- No current 2.0.7 external-machine run is present in the supplied log directory, so cross-machine success remains unverified.
