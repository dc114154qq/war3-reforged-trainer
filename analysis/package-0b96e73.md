# Clone checkpoint package — 2026-09-10

Source `0b96e73668c438df4b1a87aa30177587d61241bc`, branch
`codex/v1.0.19-bound-clone-abilities`. App 1.0.19, helper protocol 69,
game 2.0.4.23745 only.

Delivered unique EXE:
`C:/Users/14186/Desktop/xiugai/releases/1.0.19-0b96e73/War3ReforgedTrainer-v1.0.19-0b96e73.exe`.
18,653,976 bytes; SHA-256:
`7376c79bc73f10a3b6d6640b65c596fa27eb5911687a23d54225c714bceaabac`.
Helper SHA-256:
`8e633416819cf5515822279ec712bbf724ce8f64dbe1b699678c8dab4906c130`.

Tracked PyInstaller spec built into new build/dist directories suffixed
`v1.0.19-clone-0b96e73`. All previously delivered packages are preserved.
Verification executed `analysis/verify-clone-package.py 0b96e73`: embedded main,
localization and runtime-check code match compiled source; embedded helper bytes
match tracked DLL; PE is x64 GUI with file version 1.0.19.0. The delivered copy
matches build bytes. Its `--runtime-self-test` passed with frozen=true and matching
helper/decoder hashes, helper export loading and instruction decoding. Only this
offline self-test used RunAsInvoker; no game hook was installed by it.

Full source regression: **1685 tests and 113 subtests passed in 143.15 seconds**.
Evidence: `analysis/native-clone-abilities-final-regression.log`,
`analysis/package-0b96e73.log`, `analysis/package-0b96e73-verification.json`, and
the delivered `runtime-self-test.json`.

This checkpoint consolidates native field/object entrypoints and clone source,
target, item and ability identity work since accepted package 924dd59. It keeps
single-command cloning and removes repeated memory-permission queries from hot
clone guards. Actual ability creation/level readback is checked rather than
silently skipping an absent result.

The user is asked to check startup/prewarm, mixed/new unit reads and cloning with
skills/items/charges, plus group movement latency. Instructions are beside the
EXE. **No gameplay acceptance has been received for this package.** Stop further
implementation after this handoff and wait for user feedback, per the user's
instruction to provide an EXE and pause when gameplay testing is needed. Earlier
acceptance applies to 924dd59 only. The broader DLL goal remains active and
unproven; this handoff is not completion.
