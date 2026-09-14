# Loader execution investigation — 2026-09-14

## Observed
- User confirmed the sole E-drive client; PID 22844, 15 unique selected units, one hero.
- Standard and minimal probes receive both callbacks in the local host. Neither receives a callback in the target; probes are not listed as target modules at the observation points.
- Moving each probe into the game directory did not change that result. Both hooks were removed. The temporary game-directory file was deleted; original game files were not overwritten.
- The minimal 3584-byte probe imports only nine functions from USER32/KERNEL32. Its negative target result does not support CRT initialization as the sole explanation.
- Sampled PEB callback-table pointers match local module-relative addresses; 109 unique USER32 entry prefixes (32 bytes) match. This does NOT prove all callback code is unchanged.
- Current target NtOpenFile and LdrInitializeThunk entry jumps differ from local; LdrLoadDll, NtMapViewOfSection and LoadLibraryExW prefixes match.

## Emulated, not live return values
- Workspace probe path returns 0xc0000136 in a copied-memory emulator. Game-directory loader path and equal-length probe filename both reach a syscall stop.
- First branch differences alone do not identify a rejection rule. Decision logs are capped at 4096 entries; the cap was reached.
- Disk-only prefix tracing resolves distinct TLS and DllMain first calls. It neither resolves imports nor validates calling those addresses in the game.
- Ordinal 1 export has only mov eax,1;ret. Adjacent code is not part of that export.

## Still unresolved
- Exact live DLL load failure and callback-delivery failure cause.
- Valid current-game engine execution context and handle ABI; level, clone/create, add/remove/replace ability operations remain incomplete.
- No inference of mandatory code-signature policy from these probes; queried mitigation flags were zero.

## Preservation
capture.zip retains original probe binaries, source, raw JSON and logs. Baseline C source is included separately. Manifest verifies every archived artifact. Failed experiments remain evidence, not pass results. Tool runtimes and skill libraries are not copied into Git. Cross-device live acceptance remains the user's post-delivery test.
