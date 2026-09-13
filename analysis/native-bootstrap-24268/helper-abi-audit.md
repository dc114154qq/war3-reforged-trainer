# 3.0 helper ABI comparison — 2026-09-13

The live 3.0 registration table was traversed again from the running game
process PID 16700. It contains 1826 registrations. All 55 names used by the
existing native helper are present in the current table.

The current signatures were compared with the old generated profile metadata
in `tools/war3_native_bootstrap_profile.h` (1689 entries). The 55 helper names
have **zero signature changes**. The live table supplies current handler RVAs
and the exact current addresses in `helper-abi-live.json`; the comparison is
in `helper-abi-diff.json`.

This narrows the 3.0 execution problem: the helper operation ABI and the live
native name/signature ABI are compatible at the metadata level. The pending
registration attempts are blocked at the game-thread dispatch entry (`WH_*`
message hook does not run), not by missing native names or signature drift.

The result does not prove that every helper internal resolver or mutation is
valid for 3.0. It proves that registration can use the current handler table
once a valid game-thread dispatch path is available. No native handler was
called and no game data was written during this audit.
