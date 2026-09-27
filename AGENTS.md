# Isolated 2.0.7 loader repair worktree

- This directory is the user-authorized loader repair worktree `E:\xiugai\work\reforged-207-loader-fix`, based on published `70446ba`. Preserve both the release and modular-adapter worktrees. Before inspecting or editing trainer code, verify `git rev-parse --show-toplevel`, `git branch --show-current`, `git status --short`, and the relevant file at `HEAD` here.
- The required branch here is `codex/war3-207-loader-fix-20260927`. `C:\Users\14186\Desktop\xiugai` is only an entry directory, and `E:\xiugai` is a separate parent repository. Neither describes this trainer's current source or release.
- Historical logs, notes, and `dist-*` folders describe their own builds. Do not infer that a historical defect still exists without checking this worktree's source and the failing artifact's version/hash.
- In particular, the hook module-handle distinction is already present from `3a62d03`: loader-backed images pass their image base to `SetWindowsHookExW`; the manually mapped `SEC_IMAGE` fallback passes `NULL`. Do not reapply the old blanket handle change based on pre-2.0.7 logs.
- In the frozen release worktree only, verify the published executable with `python tools/build_release_207.py --verify-only`. The authoritative release pointer is `dist-2.0.7-verified/current.json`, which binds the branch, commit, source hashes, bundled DLL hashes, and EXE hash. After committing any change, rebuild before calling an EXE current.
- Preserve unrelated untracked probes, logs, and artifacts. Do not clean or prune other worktrees while investigating this trainer.
- Local bridge and fixture tests do not establish cross-machine compatibility. Report external-machine validation separately from local observations.
