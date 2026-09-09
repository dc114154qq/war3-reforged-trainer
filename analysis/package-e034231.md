# Base hero stat test handoff

Date: 2026-09-09. Source commit e034231; branch
`codex/v1.0.19-native-hero-base`. Application 1.0.19; native protocol 58.

Delivered file:
`C:/Users/14186/Desktop/xiugai/releases/1.0.19-e034231/War3ReforgedTrainer-v1.0.19-e034231.exe`

- EXE size: 18,644,388 bytes.
- EXE SHA256: `6deb0e9435fd348e3f084c811353c4e07f09d5e18e5950632e8f7dfb9392f460`.
- Helper SHA256: `355e99543ef17a371a72c17b17e81ad0733b5ee6f5d439e1ce45ba0594bde1d5`.

Tracked main PyInstaller spec built into previously absent
`dist-v1.0.19-hero-base-e034231` / `build-v1.0.19-hero-base-e034231` directories.
Delivery directory was also required to be absent. Older packages remain intact.

Verification inspected CArchive/PYZ content: controller and localization code
objects equal compilation of source at e034231; helper bytes equal tracked DLL.
PE machine is x64, subsystem Windows GUI, version resources 1.0.19.0. Delivered
copy bytes equal verified build output. Delivered EXE successfully ran its
offline `--runtime-self-test` with current-user RunAsInvoker, frozen=true,
bundled Capstone decoding and helper export loading. Both runtime dependency
hashes match their source files. No game hook was installed.

Evidence: `analysis/package-e034231.log`,
`analysis/package-e034231-verification.json`, delivered `runtime-self-test.json`.
Source validation scope and the resolved localization failure are recorded in
`analysis/native-hero-base-transaction.md`. No source changed since those checks;
they were not needlessly repeated for packaging.

The next gate is user gameplay testing of base strength/agility targets versus
freshly read values. The user's acceptance of 047b4e5 does not prove this new
setter path. Overall goal remains incomplete pending verification and other
unproven requirements. Per user instruction, stop changes after this EXE handoff
and wait for this package's feedback.
