# Warcraft III Reforged Trainer 2.1.02 测试版 — 历史构建源码

本分支补齐当时个人网站发布的 2.1.02 测试版构建源码。文件逐一对应旧构建记录，不是将当前代码改名；不包含后来的 2.1.03/2.1.04 改动。支持范围是当时的 3.0.0.24268 / 3.0.1.24323。

只收录生产源码、适配数据、构建脚本、图标及依赖许可；不包含 EXE/DLL、测试、日志、逆向资料、网站或独立工具。`diagnostics/war3_native_profile.py` 是运行时 Native 数据依赖，必须保留。

## Windows 10/11 x64 构建

安装 Git、Python 3.12、LLVM/Clang、Windows SDK，然后在 PowerShell 执行：

```powershell
git clone --branch release/v2.1.02-beta https://github.com/dc114154qq/war3-reforged-trainer.git
Set-Location war3-reforged-trainer
git switch -c main
py -3.12 -m venv .venv
& .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-build.txt
python tools/build_release_210.py
python tools/build_release_210.py --verify-only
```

旧构建器限制构建分支，先在独立克隆中建立本地 main；不要强制切换现有工作树。输出位于 `dist-2.1.02-beta-verified/`。本次只补源码，不替换以前发布的安装包；当前用户版本仍请下载最新的 2.1.04。
