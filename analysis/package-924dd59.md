# Consolidated inventory and transform test package

Source 924dd59, branch `codex/v1.0.19-direct-native-lookups`, 2026-09-10.
App 1.0.19, helper protocol 65, game target 2.0.4.23745.

Delivered to a new directory:
`C:/Users/14186/Desktop/xiugai/releases/1.0.19-924dd59/War3ReforgedTrainer-v1.0.19-924dd59.exe`.
Size 18,649,717 bytes; SHA-256:
`eba10933559b09e9f057ba75a86604f72a020042f3dc0bdf622dcf99ed0670cd`.
Helper SHA-256:
`bd3793f126c038f6108646b3e4efb8758d33a0b4878af2d8b6961d55db4ca04e`.

Built with the tracked PyInstaller spec into previously absent build/dist
directories suffixed `v1.0.19-inventory-transform-924dd59`. No previous delivery
was overwritten. CArchive/PYZ code objects match compilation of current main,
localization and offline-check source; embedded helper matches the tracked DLL.
PE resources report 1.0.19.0, x64 GUI. The delivered copy matches build bytes.
The delivered EXE passed --runtime-self-test with frozen=true, bundled helper
and decoder hashes, helper export loading and instruction decoding verified.
RunAsInvoker was used only for the offline test, which installs no game hook.

Evidence: `analysis/package-924dd59.log`,
`analysis/package-924dd59-verification.json`, the verification script and delivered
`runtime-self-test.json`. The verifier was adjusted to find the actual PYZ-00.pyz
archive entry before successful execution; application code did not change.

Previous C/controller changes passed 1443 tests and 113 subtests. The final
Python-only lookup simplification passed the relevant 83 tests and 21 subtests;
the full suite was not unnecessarily repeated for that narrow change.

This package consolidates inventory batches, item creation/duplication, scale,
position, ownership, owner-group kills and lookup simplification after the user's
c358dbc acceptance. That acceptance must not be reused for this build. Test
instructions are beside the EXE. Stop implementation after delivery and await
the user's gameplay feedback. The full DLL migration goal remains unproven.
