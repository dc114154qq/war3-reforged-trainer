# Warcraft III Modular Adapter Development Worktree

- Architecture development belongs to `E:\xiugai\work\reforged-modular-adapters`, branch `codex/war3-modular-adapters-20260926`, based on released `70446ba`. Run development commands here.
- Before inspecting or editing trainer code, verify `git rev-parse --show-toplevel`, `git branch --show-current`, `git status --short`, and the relevant source at `HEAD` in the intended worktree.
- The frozen 2.0.7 release worktree is `E:\xiugai\work\reforged-persistent-native`, branch `codex/war3-2.0.7-integration-20260926`. It is not this development branch. Do not run its release builder here or publish this refactor under the current task.
- `C:\Users\14186\Desktop\xiugai` is only an entry directory, not a Git repository. `E:\xiugai` is a separate parent repository. Neither describes this development worktree's source state.
- Native fixture DLLs and test artifacts may be built under `build/`; preserve tracked release DLLs, unrelated changes, probes and diagnostics. Do not clean/reset or prune other worktrees.
- Historical logs and `dist-*` folders describe their own builds. Check current source and the failing artifact's version/hash before claiming a historical fix is missing.
- The hook module-handle distinction already exists from `3a62d03`: loader-backed images pass their image base to `SetWindowsHookExW`; manually mapped `SEC_IMAGE` images retain `NULL`. Do not reapply that change without current failing-route evidence.
- For frozen 2.0.7 artifact verification only, run `python tools/build_release_207.py --verify-only` in the release worktree and use `dist-2.0.7-verified/current.json`. A failed check means source/artifact mismatch; never substitute older `dist-2.0.7`. Development changes do not make any existing EXE current.
- Local tests do not establish external-machine compatibility. Old external `0x105` logs prove neither success nor failure of the current build.
- See `ARCHITECTURE.md` for implementation boundaries and verification commands. The mandatory workflow below governs future adaptations.


## Mandatory game-update workflow / 游戏更新强制流程

每次游戏更新，固定按顺序执行：**识别构建 → 对比适配数据 → 验证公共依赖 → 按能力验证 → 发布适配包**。不得跳过验证直接沿用旧偏移，也不得把只修改模块基址描述为完整版本适配。

1. **识别构建**：读取实际游戏 PE 构建指纹，分别记录修改器版本、游戏版本、适配包版本和桥协议版本。PID、窗口标题和文件名不能代替构建身份；未知构建只生成只读诊断，不使用旧配置写入。
2. **对比适配数据**：以 `GameProfile` 为唯一版本数据来源，核对 RVA、对象布局、TLS、Native 注册表、调用约定和代码校验。优先按 Native 名称与签名定位，并独立验证实际 C ABI。地址/布局变化更新数据包；调用语义、解析算法或图标机器码变化更新对应适配模块，不能仅改构建号冒充兼容。
3. **验证公共依赖**：验证对象解析、句柄类型转换、执行上下文、桥协议与配置读回，以及进程重启/PID 复用、换图、窗口线程变化和对象销毁后的缓存失效。公共依赖失败阻止所有依赖操作；只有证明业务回调未执行且清理完成才能切换路线，部分写入、超时或清理不确定时禁止自动重放。
4. **按能力验证**：依次验证资源/单位、技能/物品、扩展背包/装备、天赋/图标，保留未修改功能的回归覆盖。比较同一快照的对象身份、字段、Native 映射和操作参数，写入按读回与业务后置条件验收；分别记录命令送达、状态读回、实际游戏效果。相同快照/规模/缓存条件下，中位耗时和 P95 均不得劣于基线 10%。夹具证明配置驱动与错误处理，不能证明真实新版本、实际游戏效果或外机兼容；问题外机须有当前产物的独立运行证据。未执行项明确标注，不能报为通过。
5. **发布适配包**：候选定位结果须唯一且通过结构、语义及能力验证，正式包须匹配游戏指纹、数据结构版本和桥接口版本。发布清单记录来源提交、版本、文件哈希、能力范围及验证缺口；仅在用户授权发布的任务中发布。数据包仅允许严格数据，不自动联网下载、不加载任意脚本；仅数据变化优先发适配包，调用语义或桥接口变化才升级相应模块/EXE。本规则本身不构成构建或发布授权。

新增/迁移功能必须经功能服务、统一 `GameSession`、类型化 `UnitRef`/`ItemRef` 和执行后端；不得重新在功能层散落版本地址、会话缓存或传输选路。保持快速外部字段访问与原生执行两个后端的职责边界，单项扩展失败只禁用依赖它的能力。

## External-machine fixes integrated from 2.0.8 and 2.0.9

- This architecture branch is based on 2.0.7 (`70446ba`) but also contains the complete external-machine repair delta through `873af7140f6af95f826565d8ae0397f840022b32`: mapped import initialization/protected loader recovery, gated apphelp native-hook recovery, and private callback exit/drain/diagnostics. Do not restore the 2.0.7 transport when adapting it.
- Keep loading and route selection in `war3_engine_transport.py`; preserve `prepare_operation`, profile configuration write/readback and fresh opened-process identity checks on every route. Keep delivery, callback exit, cleanup, readback and game effect as separate evidence in `GameSession`. Uncertain callback exit or cleanup must block replay.
- The user reported the published 2.0.9 successful on the previously failing machine on 2026-09-29. This is user-reported validation of that released artifact, not a claim that this unpublished architecture branch has run there. See `ARCHITECTURE.md` for migration scope and verification.

## 2.1.0 beta identity

The user assigned this experimental branch version `2.1.0`, release channel `beta`. Keep the UI's beta label, diagnostic channel, Windows prerelease flag and `RELEASE_NOTES_v2.1.0-beta.md` consistent. The dedicated builder is `tools/build_release_210.py`; its manifest and package checks must cover all services/protocols, the profile and the 2.0.8/2.0.9 bridge repairs. Do not use the frozen 2.0.7 builder for this branch. Release notes compare functionality with stable 2.0.9: structural optimization, no new intended game features, retained compatibility repairs. Publishing must be explicitly authorized and marked prerelease; preparing version metadata is not publication.
