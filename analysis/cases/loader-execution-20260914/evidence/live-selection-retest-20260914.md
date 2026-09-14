# Live selection retest — 2026-09-14

- PID `38352` was visible and responsive at initial check.
- Read-only native table traversal succeeded: 1826 nodes; all eight selection-query handlers present with expected signatures.
- First attempted selection dispatch used a null work pointer and was previously fixed by commit `aa76e7d`; no further null-work dispatch occurred in this turn.
- Corrected `SelectionWork` layout was prepared as 480 bytes (`10 QWORD + 4 DWORD + 24 rows`).
- The corrected retest stopped during object-registry initialization with `WinError 299` (partial ReadProcessMemory). It did not install a hook or call a game handler.
- No writes, cloning, ability, item, or elephant operations were executed.
- No EXE was packaged.
