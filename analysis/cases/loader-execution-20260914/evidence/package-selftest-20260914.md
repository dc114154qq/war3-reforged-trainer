# 3.0 execution module build and packaged startup — 2026-09-14

- Commit with module/spec: `2a7bf2e`.
- `clang` build of `analysis/war3_engine_24268.c`: exit 0; DLL size 368,640 bytes; exported `War3HookProc`; ctypes LoadLibrary succeeded.
- PyInstaller build via `python -m PyInstaller`: exit 0.
- EXE: `C:\Users\14186\Desktop\xiugai\work\reforged-persistent-native\dist-3.0.0.24268-current\War3ReforgedTrainer-3.0.0.24268.exe`; size 18,700,653 bytes.
- Packaged startup self-test: exit 0; report `analysis/runtime-self-test-3.0.json` has `ok: true`, frozen true, decoder boundary check passed, retired helper absent.
- Static byte check found `war3_engine_24268.dll` embedded in the EXE.
- This proves packaging/startup only. It does not prove live game writes, cloning, ability, item, or elephant operations.
