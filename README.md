# Warcraft III Reforged Trainer 2.1.03 — 历史构建源码

这是个人网站于 2026-10-04 发布的 2.1.03 对应源码，按当时的构建文件哈希恢复，不是将当前版本改名。支持范围为当时的 3.0.0.24268 / 3.0.1.24323；不包含后来的 24332 适配与 2.1.04 修改。

本分支仅包含生产源码、适配数据、构建脚本、图标及依赖许可，没有 EXE/DLL、测试、日志、网站或独立工具。`diagnostics/war3_native_profile.py` 是运行时 Native 数据依赖，保留该文件不代表收录整个逆向资料库。

## Windows 10/11 x64 构建

安装 Git、Python 3.12、LLVM/Clang、Windows SDK，确保 clang 和 SDK 导入库可用，然后在 PowerShell 中执行：

```powershell
git clone --branch release/v2.1.03 https://github.com/dc114154qq/war3-reforged-trainer.git
Set-Location war3-reforged-trainer
git switch -c main
py -3.12 -m venv .venv
& .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-build.txt
python tools/build_release_210.py
python tools/build_release_210.py --verify-only
```

输出为 `dist-2.1.03-verified/<sha256-prefix>/War3ReforgedTrainer-v2.1.03.exe`。旧构建器要求 main/master 等构建分支，所以下载历史分支后先建立本地 main；不要在当前开发工作树中强制切换。

This is the exact historical 2.1.03 production source reconstructed against its published build hashes. Use the release source branch in a separate checkout. Generated binaries, tests, logs and unrelated tools are excluded. A fresh build may differ in binary timestamp/path metadata; the published EXE is not replaced.
