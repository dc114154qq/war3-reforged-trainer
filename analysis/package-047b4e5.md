# Independent 1.0.19 test package

Date: 2026-09-09. Source commit: 047b4e5.
Branch: `codex/v1.0.19-property-identity`; native protocol: 57.

Previous goal turn made progress by pinning snapshot identity before native
field calls. This turn packages that exact source for the user-owned gameplay
test gate. Overall goal remains unproven until the actual game requirements
are tested; no historical user acceptance is attributed to this package.

Artifact:
`C:/Users/14186/Desktop/xiugai/releases/1.0.19-047b4e5/War3ReforgedTrainer-v1.0.19-047b4e5.exe`

- Size: 18,641,688 bytes.
- EXE SHA256: `2c69b047df8eee196030bc047804edd2400bbaade9dd93a1f64441f7282dd218`.
- DLL SHA256: `2cd8a33f3ebe1f62dfbefbb2535d2be21af313e70e9b83ec855f1aa3a77aceb8`.
- App/file version remains 1.0.19 / 1.0.19.0. x64 Windows GUI executable.

Build used the tracked main spec with separate
`--distpath dist-v1.0.19-native-047b4e5` and
`--workpath build-v1.0.19-native-047b4e5`. Both destinations and the delivery
directory were required to be absent before creation. Older packages are intact.

## Verification

1. Exact source commit had passed 961 tests and 113 subtests (51.03 seconds);
   no source changes followed, so that suite was not needlessly repeated.
2. CArchiveReader extraction: embedded controller code object equals compilation
   of current source; embedded helper bytes equal the tracked DLL.
3. PE inspection: x64 machine, GUI subsystem, version 1.0.19.0.
4. Delivered copy hash equals the verified build output.
5. Delivered EXE ran `--runtime-self-test` successfully, frozen=true, checking
   bundled Capstone instruction decoding and loading the helper's War3HookProc.
   Both runtime hashes match the source dependencies. The offline subprocess
   ran as the current user with RunAsInvoker; no game hook was installed.

Evidence: `analysis/package-047b4e5.log`,
`analysis/package-047b4e5-verification.json`,
`analysis/package-047b4e5-runtime.json` and the delivered `runtime-self-test.json`.

The EXE has not been tested against the running game by this turn. Requested
handoff covers mixed/new-unit reads, target switching, group move/copy, skills
created from map resources and hero/inventory writes. Branch effect experiments
are retained and explicitly described as pending live confirmation.

Per the user's instruction, stop modifying this candidate and wait for feedback.
The persistent objective is not complete; this is a concrete test handoff.
