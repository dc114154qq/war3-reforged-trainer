# 2.0.7 build audit

## Build identity

- Source workspace: `E:\xiugai\work\reforged-persistent-native`
- Branch: `codex/war3-2.0.7-integration-20260926`
- Release pointer: `dist-2.0.7-verified\current.json`
- Executable: `dist-2.0.7-verified\8CB39F647D5F\War3ReforgedTrainer-v2.0.7.exe`
- File version: `2.0.7.0`
- EXE SHA-256: `8CB39F647D5F386CAF1B0D69692893710799C064336897B314F683BC6108E12A`
- Bundled bridge SHA-256: `A2A6238FEA7320E75E21A19F3E3C515487899B4AA0F1257AA8A60C74404B649B`
- Bundled talent display DLL SHA-256: `C8B018C35BC32D5326B7CB9419AFDF582989897F5FA0D555CC2877C89DFB06DC`

## Verified in this build

- Focused regression suite: `76 passed`.
- Current running game read-only extension query: success; bag size `30`, two bag items, zero equipment items.
- Bridge callback and cleanup: success on the current process; no retained hook or mapped allocation.
- Release gate builds both native DLLs in isolation and verifies their bytes inside the EXE before updating `current.json`.

## Not claimed as complete

- Talent icon display: current paused target reached the bridge callback and cleaned up, but the target UI site read back as `0xC7` bytes and the display patch was not installed.
- External-machine compatibility: the old external log is diagnostic evidence only. A new run with this exact EXE is required to prove the old `0x105` failure is gone.
- Critical damage combat effect: field setter/readback is covered; actual combat damage is intentionally left for the user to test.
- Scarlet Frenzy cross-chapter backpack persistence: not proven by static script comparison; Forsaken Kingdom remains the known-good reference.

## Consistency correction

The earlier `dist-2.0.7` artifact was built before subsequent bridge edits and is stale. The verified artifact above is immutable; run `python tools/build_release_207.py --verify-only` before using it with a changed worktree. The source remains a checkpoint of an unfinished feature goal, not a claim that all gameplay fixes are complete.
