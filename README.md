# Warcraft III Reforged Trainer 2.1.04 / 魔兽争霸 III 重制版修改器 2.1.04

本仓库包含 Warcraft III Reforged 修改器 2.1.04 的源码和版本适配数据。仓库不提交生成的 EXE、DLL、`dist` 目录、测试夹具、逆向分析证据或独立的改键软件源码。

This repository contains the source code and version adapter data for the Warcraft III Reforged Trainer 2.1.04. Generated EXE/DLL files, `dist` directories, test fixtures, reverse-engineering evidence, and the separate hotkey product are intentionally excluded.

## 构建环境 / Build Requirements

在 Windows 10/11 x64 上构建，需要安装：

Build on Windows 10/11 x64 with:

- Git
- Python 3.10 或更高版本，推荐 Python 3.12 / Python 3.10 or newer; Python 3.12 is recommended
- LLVM/Clang，并确保 `clang` 在 `PATH` 中 / LLVM/Clang with `clang` available in `PATH`
- Windows SDK 及其 x64 导入库，并确保 Clang 能够找到 / Windows SDK and its x64 import libraries available to the Clang toolchain

桥接 DLL、天赋图标模块和游戏加速模块由 Clang 编译。仅安装 Python 编译包不够，还必须安装 Windows 头文件和导入库。

The bridge DLL, talent-display module, and speed-clock module are compiled with Clang. Installing Python packages alone is not sufficient; the Windows headers and import libraries from the Windows SDK are also required.

## 从源码完整构建 / Build From Source

在 PowerShell 中，从仓库根目录执行以下命令：

From PowerShell, run the following commands in the repository root:

```powershell
git clone https://github.com/dc114154qq/war3-reforged-trainer.git
Set-Location war3-reforged-trainer
git switch main

py -3.12 -m venv .venv
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt

python tools/build_release_210.py
```

构建脚本会自动完成以下步骤：

The build script automatically performs all of these steps:

1. 检查当前源码版本、Git 工作树和游戏适配数据。 / Check the source version, Git worktree, and game adapter data.
2. 编译并校验 engine bridge。 / Compile and validate the engine bridge.
3. 编译并校验天赋图标显示模块。 / Compile and validate the talent-display module.
4. 编译并校验游戏速度模块。 / Compile and validate the speed-clock module.
5. 使用 `War3ReforgedTrainer-2.1.04.spec` 调用 PyInstaller。 / Invoke PyInstaller with `War3ReforgedTrainer-2.1.04.spec`.
6. 检查 Python 模块、游戏 profile、native ABI、版本资源和 MinHook 许可证。 / Check Python modules, game profiles, native ABIs, version resources, and the MinHook license.

不需要把预编译 DLL 或 EXE 放进源码目录。/ No prebuilt DLL or EXE needs to be placed in the source checkout.

验证后的 EXE 会写入以下被 Git 忽略的目录：

The verified executable is written below this Git-ignored directory:

```text
dist-2.1.04-verified/<sha256-prefix>/War3ReforgedTrainer-v2.1.04.exe
```

构建命令会打印实际输出路径。/ The build command prints the exact output path.

## 验证已有构建 / Verify an Existing Build

成功构建后，可以使用以下命令验证 EXE 和 manifest：

After a successful build, verify the executable and manifest with:

```powershell
python tools/build_release_210.py --verify-only
```

只有当前源码输入、Git 提交、记录的哈希、打包 profile 和 native 模块全部一致时，验证才会成功。如果源码已经变化，请先重新构建。

Verification succeeds only when the current source inputs, Git revision, recorded hashes, packaged profiles, and native modules match the recorded build. If the source has changed, build again before verifying.

## 构建输入 / Build Inputs

- `War3ReforgedTrainer-2.1.04.spec`：本版本实际使用的 PyInstaller 规格文件。 / The PyInstaller specification used by this release.
- `war3_*.py`、`war3_services/` 和 `diagnostics/` 中的运行时文件：修改器运行模块及显式 hidden-import。 / Runtime modules and explicit hidden imports used by the trainer.
- `profiles/`：严格匹配游戏构建的适配数据。 / Strict game-build adapter data.
- `tools/`：native 源码、构建脚本、profile 生成检查和 ABI 验证器。 / Native source, build scripts, profile checks, and ABI validators.
- `third_party/minhook/`：游戏速度模块所需的 MinHook 源码和许可证。 / MinHook source closure and license required by the speed-clock module.
- `assets/app_icon.ico`、`assets/app_icon.png`：EXE 和运行时界面图标。 / Executable and runtime UI icons.

构建器会在编译前后对这些输入计算哈希。`war3_hotkey_*` 文件属于独立的改键软件，不参与本修改器构建。

The builder hashes these inputs before and after compilation. The `war3_hotkey_*` files belong to a separate hotkey product and are not part of this trainer build.

`diagnostics/war3_native_profile.py` 保存运行时仍需读取的 Native 索引，因此这个目录名称虽为 diagnostics，它的这份数据文件仍是构建依赖。旧的持久钩子传输和独立代码/冷却/生命周期探针不属于当前生产入口。

`diagnostics/war3_native_profile.py` stores the Native index still read at runtime, so that data file remains a build dependency despite the directory name. The old persistent-hook transport and standalone code, cooldown, and lifecycle probes are outside the current production entry points.

## 版本适配范围 / Version Adapter Scope

当前分支包含 `profiles/` 中的游戏适配数据，包括已验证的 `3.0.0.24268` profile 和本分支提供的 `3.0.1` profile 数据。已识别为 Warcraft III、但没有精确适配包的同系列构建，会借用最近的已知适配层，并保留逐操作身份、读回与清理检查。这不等于该构建已经完成实机适配；只更换模块基址不代表完整兼容。

The current branch contains the game adapter data in `profiles/`, including the verified `3.0.0.24268` profile and the supported `3.0.1` profile data included in this branch. A recognized Warcraft III build without an exact profile borrows the nearest adapter in its version series while retaining per-operation identity, readback and cleanup checks. Borrowing is not proof of real-game compatibility; changing only a module base address is not a complete port.

## 仓库结构 / Repository Layout

- `main`、`master`：同步的当前维护源码入口。 / Synchronized maintained source entry points.
- `release/v*`：与已发布修改器版本对应的纯源码历史分支。 / Source-only historical branches for published trainer versions.
- `v*`：不可变的修改器发布标签。 / Immutable trainer release tags.
- `profiles/`：按游戏构建组织的版本适配数据。 / Build-specific adapter data.
- `tools/`：可构建的 native 源码和发布验证工具。 / Buildable native sources and release verification tools.

生成文件会被 Git 忽略。发布构建前请使用干净的 checkout。/ Generated files are ignored by Git. Use a clean checkout when producing a release artifact.

## 源码与发布版本对应 / Source and Release Alignment

发布新版本前，先提交该版本的生产构建输入，确认 `main` 与 `master` 指向同一源码提交，再建立 `release/v版本号` 源码分支并发布 EXE。不能只上传 EXE、把未提交工作树的修改留在本机。源码提交仅包含运行模块、实际适配数据、生产 native 源码、构建脚本、版本资源、依赖许可和这份构建说明；不要使用无筛选的 `git add .`。

Commit the production build inputs before publishing an executable, keep `main` and `master` aligned, and create a matching `release/vVERSION` source branch. Do not publish binaries from uncommitted source without supplying the corresponding source snapshot. Keep generated binaries, fixtures, logs, standalone probes, website and unrelated tools out of source commits. Published tags remain immutable; a corrected source snapshot must use its own source branch/archive rather than retargeting an existing release tag.
