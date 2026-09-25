# Hook route comparison, 2026-09-26

## Observations

- A no-op `WH_CALLWNDPROC` DLL was installed from the medium-integrity trainer
  process against local game PID 22708, window 461732. `SetWindowsHookExW`,
  `SendMessageTimeoutW`, and `UnhookWindowsHookEx` all reported success, but the
  target process did not list the DLL and the callback marker was absent.
- The same DLL and probe against a disposable medium-integrity window process
  (PID 49172) produced a callback marker with that target PID and thread ID.
  The control process exited after the test. Hook installation alone is therefore
  not evidence that the game ran the callback.
- The exact bridge DLL extracted from the current 2.0.7 EXE has SHA-256
  `65526D82111CEC90B9106CA119D4FDDA51A939038541878241347D7CF0472E2D`.
  Its read-only `unit_stats()` query on game PID 22708 returned one row through
  `sec_image_fallback`: stage 3, callback count 1, query stage 2, exception 0,
  and safe release confirmed.
- The tracked `tools/war3_bridge_24268.dll` differs byte-for-byte from the
  packaged DLL, but their `.text`, `.data`, `.pdata`, and `.reloc` section hashes
  match. Only PE timestamp and `.rdata` differ in this comparison. Use the
  packaged DLL when an exact-release test is required.

## Interpretation and gap

The game-specific absence of the ordinary DLL hook callback is consistent with
the previously observed target `LoadLibraryW` rejection. This is an inference,
not proof of the loader's exact policy. Copying the classic helper's trainer-side
hook installation into the 3.0 bridge is not established as a viable fallback.

The external 2.0.6 logs show a separate `SEC_IMAGE` hook-install exception
(`0x105`) before callback execution. The current 2.0.7 bridge records the fault
instruction/address, but no current-build log from that external machine exists.
Local success cannot establish that the external exception is fixed.
