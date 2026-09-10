# Consolidated bound-actions test package

2026-09-10. Source c358dbc; branch `codex/v1.0.19-bound-hero-progression`.
Application 1.0.19, native protocol 62.

Delivered:
`C:/Users/14186/Desktop/xiugai/releases/1.0.19-c358dbc/War3ReforgedTrainer-v1.0.19-c358dbc.exe`

- Size 18,646,310 bytes.
- EXE SHA256 `2559d531082121ff67cf0cacc5064ad58f3a9de60f0312915c80ca4fd8769db0`.
- Helper SHA256 `295d399d254c0793852404f4edff4d9aebe8b693d35059d7a3c4e48cbe79f3d6`.

Build used the tracked main PyInstaller spec and fresh, previously absent
`dist-v1.0.19-bound-actions-c358dbc` and `build-v1.0.19-bound-actions-c358dbc`
directories. The delivery directory was also required to be absent.
No existing package was overwritten.

Verification: CArchive/PYZ controller, localization and offline-check code
objects equal compilation of their source files; embedded helper bytes equal
the tracked DLL. PE resources report 1.0.19.0, x64 Windows GUI. Delivered copy
equals verified build output. The delivered EXE ran `--runtime-self-test`
successfully as the current user (RunAsInvoker for offline testing), frozen=true,
loading bundled helper/Capstone, checking the export and instruction decoding.
Runtime hashes match both source dependencies. No game hook was installed.

Evidence: `analysis/package-c358dbc.log`,
`analysis/package-c358dbc-verification.json`, delivered `runtime-self-test.json`.
Current source passed 1169 tests and 113 subtests in 63.61 seconds before
packaging; no code changed afterward, so the suite was not repeated here.

This bundle includes guarded all-attributes, simple unit actions, bound state
queries and hero level/skill-point transactions developed after the user's
e034231 acceptance. That acceptance does not apply to this package. User-owned
gameplay checks are documented beside the EXE; no current gameplay acceptance
is inferred. Per the user's instruction, stop changes after delivery and wait
for feedback. The full objective is not yet proven complete; remaining inventory
and other candidate paths still require their reachability/identity audits.

## Subsequent user feedback

On 2026-09-10 the user replied “测试没问题，继续吧” immediately after this
package handoff. Record this as acceptance of the requested c358dbc gameplay
checks and authorization to continue development. Do not reuse this feedback
as acceptance of later inventory or other changes. The delivered EXE is retained.
